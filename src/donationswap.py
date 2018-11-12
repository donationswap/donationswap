#!/usr/bin/env python3

'''
This is the logic layer, where the rules of donation swapping
are implemented, without any reference to the web server.

Abstracting this out makes it easier to change to a different
web server in the future.

Dependency structure:

.----------------------------------------------------------------------------------------------------.
| main                                                                                               | web layer
'----------------------------------------------------------------------------------------------------'
                .------------------------------------------------------------------------------------.
                | donationswap                                                                       | "business logic"
                '------------------------------------------------------------------------------------'
                                                                                    .----------.
                                                                                    | entities |
                                                                                    '----------'
            .------. .--------. .------------. .---------. .---------. .----------. .----------------.
            | util | | config | | captcha    | | geoip   | | mail    | | currency | | database       | helper classes
            '------' '--------' '------------' '---------' '---------' '----------' '----------------'
.---------.                     .------------. .---------. .---------. .----------. .----------------.
| tornado |                     | Google     | | geoip2  | | SMTP    | | fixer.io | | psycopg2,      | third party
| library |                     | re-Captcha | | website | | account | | website  | | postgres db    |
'---------'                     '------------' '---------' '-------  ' '----------' '----------------'
'''

import base64
import datetime
import logging
import os
import re
import struct
import time

import admin
import captcha
import config
import currency
import database
import entities
import eventlog
import geoip
import mail
import util


#xxx change email to have minimum amount
#    in match creation email and match confirmation email
#    also on /match/

#xxx default min_amount to half of amount

#xxx run matchmaker every 5 minutes or so

#xxx find out what information the matching algorithm provides
#    (and add it to the email)

#xxx allow admins to force a match

#xxx when a user declines a match, they should get asked if
#    they want to delete their own (now suspended) offer.

#xxx send feedback email after a month (don't delete match after sending out the deal email)
#    add "completed_ts" column to match

#xxx consolidate databases

#xxx find a way to not hard-code subject lines and error messages

#xxx post MVP features:
#- a donation offer is pointless if
#  - it is to the only tax-deductible charity in the country OR
#  - it is to a charity that is tax-decuctible everywhere
# - add "never match me with any of these charity" blacklist button.
# - add "blacklist charity" to offer.
# - blacklist users who agreed to the match but didn't acutally donate.
# - support crypto currencies.
# - add link to match email for user to create offer for remaining amount

def ajax(f):
	f.allow_ajax = True
	return f

def create_secret():
	timestamp_bytes = struct.pack('!d', time.time())
	random_bytes = os.urandom(10)
	return base64.b64encode(timestamp_bytes + random_bytes).decode('utf-8')

class DonationException(Exception):
	pass

class Donationswap: # pylint: disable=too-many-instance-attributes

	def __init__(self, config_path):
		self._config = config.Config(config_path)

		self._database = database.Database(self._config.db_connection_string)

		self._admin = admin.Admin(self._database)
		self._captcha = captcha.Captcha(self._config.captcha_secret)
		self._currency = currency.Currency(self._config.currency_cache, self._config.fixer_apikey)
		self._geoip = geoip.GeoIpCountry(self._config.geoip_datafile)
		self._mail = mail.Mail(self._config.email_user, self._config.email_password, self._config.email_smtp, self._config.email_sender_name)

		with self._database.connect() as db:
			entities.load(db)

		self._ip_address = None

	def get_cookie_key(self):
		return self._config.cookie_key

	@staticmethod
	def _int(number, msg):
		try:
			return int(number)
		except ValueError:
			raise DonationException(msg)

	def _get_match_and_offers(self, secret):
		if len(secret) != 48:
			logging.debug('invalid secret length.')
			return None, None, None, None, None

		offer_secret = secret[:24]
		match_secret = secret[24:]

		match = entities.Match.by_secret(match_secret)

		if match is None:
			# not cached yet? reload from db
			logging.debug('reloading matches')
			with self._database.connect() as db:
				entities.Match.load(db)
			match = entities.Match.by_secret(match_secret)

		if match is None:
			logging.debug('match with secret "%s" not found.', match_secret)
			return None, None, None, None, None

		new_offer = match.new_offer
		old_offer = match.old_offer

		if new_offer.secret == offer_secret:
			my_offer = new_offer
			their_offer = old_offer
		elif old_offer.secret == offer_secret:
			my_offer = old_offer
			their_offer = new_offer
		else:
			logging.debug('offer with secret "%s" not found.', offer_secret)
			return None, None, None, None, None

		return match, old_offer, new_offer, my_offer, their_offer

	def run_ajax(self, command, ip_address, args):
		'''Ajax methods don't have their error messages exposed.'''

		method = getattr(self, command, None)
		if method is None:
			return False, None # method does not exist
		if not getattr(method, 'allow_ajax', False):
			return False, None # ajax not allowed

		self._ip_address = ip_address

		try:
			return True, method(**args)
		except DonationException as e:
			return False, str(e)
		except Exception: # pylint: disable=broad-except
			logging.error('Ajax Error', exc_info=True)
			return False, None

	def run_admin_ajax(self, user_secret, command, args):
		'''Admin ajax methods do have their error messages exposed.'''

		with self._database.connect() as db:
			query = '''SELECT * FROM admins WHERE secret = %(secret)s;'''
			user = db.read_one(query, secret=user_secret)
		if user is None:
			self._admin.user = None
		else:
			self._admin.user = {
				'id': user['id'],
				'email': user['email'],
			}

		if command.startswith('_'):
			return False, 'method forbidden'
		method = getattr(self._admin, command, None)
		if method is None:
			return False, 'method does not exist'

		try:
			return True, method(**args)
		except Exception as e: # pylint: disable=broad-except
			logging.error('Ajax Admin Error', exc_info=True)
			return False, str(e)

	@staticmethod
	def get_page(name):
		return util.Template(name).content

	@ajax
	def send_contact_message(self, captcha_response, message, name=None, email=None):
		is_legit = self._captcha.is_legit(self._ip_address, captcha_response)

		if not is_legit:
			raise DonationException('bad captcha response')

		tmp = util.Template('contact-email.txt')
		tmp.replace({
			'{%IP_ADDRESS%}': self._ip_address,
			'{%COUNTRY%}': self._geoip.lookup(self._ip_address),
			'{%NAME%}': name or 'n/a',
			'{%EMAIL%}': email or 'n/a',
			'{%MESSAGE%}': message.strip(),
		})

		send_to = self._config.contact_message_receivers.get('to', [])
		send_cc = self._config.contact_message_receivers.get('cc', [])
		send_bcc = self._config.contact_message_receivers.get('bcc', [])

		with self._database.connect() as db:
			eventlog.sent_contact_message(db, tmp.content, send_to, send_cc, send_bcc)

		self._mail.send(
			'Message for donationswap.eahub.org', #xxx do not hardcode subjects
			tmp.content,
			to=send_to,
			cc=send_cc,
			bcc=send_bcc
		)

	@staticmethod
	def _get_charities_info():
		return [
			{
				'id': i.id,
				'name': i.name,
				'category': i.category.name,
			}
			for i in sorted(entities.Charity.get_all(), key=lambda i: i.category.name + i.name)
		]

	def _get_countries_info(self):
		return [
			{
				'id': i.id,
				'name': i.name,
				'iso_name': i.iso_name,
				'live_in_name': i.live_in_name or i.name,
				'currency_iso': i.currency.iso,
				'currency_name': i.currency.name,
				'min_donation_amount': self._currency.convert(
					i.min_donation_amount,
					i.min_donation_currency.iso,
					i.currency.iso
				)
			}
			for i in sorted(entities.Country.get_all(), key=lambda i: i.name)
		]

	@staticmethod
	@ajax
	def get_info(self):
		client_country_iso = self._geoip.lookup(self._ip_address)
		client_country = entities.Country.by_iso_name(client_country_iso)
		if client_country:
			client_country_id = client_country.id
		else:
			client_country_id = None

		logging.info('Website visitor from %s with IP address "%s".', client_country_iso, self._ip_address)

		today = datetime.datetime.utcnow()

		return {
			'charities': self._get_charities_info(),
			'client_country': client_country_id,
			'countries': self._get_countries_info(),
			'today': {
				'day': today.day,
				'month': today.month,
				'year': today.year,
			},
		}

	@ajax
	def get_charity_in_country_info(self, charity_id, country_id): # pylint: disable=no-self-use
		charity_in_country = entities.CharityInCountry.by_charity_and_country_id(charity_id, country_id)
		if charity_in_country is not None:
			return charity_in_country.instructions
		return None

	def _validate_offer(self, captcha_response, name, country, amount, min_amount, charity, email, expiration):
		is_legit = self._captcha.is_legit(self._ip_address, captcha_response)

		if not is_legit:
			raise DonationException('bad captcha response')


		name = name.strip()
		if not name:
			raise DonationException('no name provided')

		country = entities.Country.by_id(country)
		if country is None:
			raise DonationException('country not found')

		amount = self._int(amount, 'invalid amount')
		if amount < 0:
			raise DonationException('negative amount')

		min_amount = self._int(min_amount, 'invalid min_amount')
		if min_amount < 0:
			raise DonationException('negative min_amount')


		charity = entities.Charity.by_id(charity)
		if charity is None:
			raise DonationException('charity not found')

		email = email.strip()
		if not re.fullmatch(r'.+?@.+\..+', email):
			raise DonationException('bad email address')

		expires_ts = '%04i-%02i-%02i' % (
			self._int(expiration['year'], 'invalid expiration date'),
			self._int(expiration['month'], 'invalid expiration date'),
			self._int(expiration['day'], 'invalid expiration date')
		)
		try:
			expires_ts = datetime.datetime.strptime(expires_ts, '%Y-%m-%d')
		except ValueError:
			DonationException('invalid expiration date')

		return name, country, amount, min_amount, charity, email, expires_ts

	@ajax
	def create_offer(self, captcha_response, name, country, amount, min_amount, charity, email, expiration):
		name, country, amount, min_amount, charity, email, expires_ts = self._validate_offer(captcha_response, name, country, amount, min_amount, charity, email, expiration)

		secret = create_secret()
		# Do NOT return this secret to the client via this method.
		# Only put it in the email, so that having the link acts as email address verification.

		with self._database.connect() as db:
			offer = entities.Offer.create(db, secret, name, email, country.id, amount, min_amount, charity.id, expires_ts)
			eventlog.created_offer(db, offer)

		replacements = {
			'{%NAME%}': offer.name,
			'{%SECRET%}': offer.secret,
			'{%CHARITY%}': offer.charity.name,
			'{%CURRENCY%}': offer.country.currency.iso,
			'{%AMOUNT%}': offer.amount,
			'{%MIN_AMOUNT%}': offer.min_amount,
		}
		self._mail.send(
			'Please confirm your donation offer',
			util.Template('new-post-email.txt').replace(replacements).content,
			html=util.Template('new-post-email.html').replace(replacements).content,
			to=email
		)

	@ajax
	def confirm_offer(self, secret):
		offer = entities.Offer.by_secret(secret)
		if offer is None:
			return None

		# caller knows the secret (which we emailed)
		# => caller received email
		# => email address is valid
		# caller clicked on link we emailed
		# => offer is confirmed
		# => mark it as confirmed in db, and try to find a match for it.

		was_confirmed = offer.confirmed

		if not was_confirmed:
			with self._database.connect() as db:
				offer.confirm(db)
				eventlog.confirmed_offer(db, offer)

		return {
			'was_confirmed': was_confirmed,
			'currency': offer.country.currency.iso,
			'amount': offer.amount,
			'charity': offer.charity.name,
			'created_ts': offer.created_ts.isoformat(' '),
			'expires_ts': offer.expires_ts.isoformat(' '),
		}

	@ajax
	def delete_offer(self, secret):
		offer = entities.Offer.by_secret(secret)
		if offer is not None:
			with self._database.connect() as db:
				offer.delete(db)
				eventlog.deleted_offer(db, offer)

	@ajax
	def get_match(self, secret):
		_, _, _, my_offer, their_offer = self._get_match_and_offers(secret)
		if my_offer is None or their_offer is None:
			return None

		my_amount_converted = self._currency.convert(
				my_offer.amount,
				my_offer.country.currency.iso,
				their_offer.country.currency.iso)
		their_amount_converted = self._currency.convert(
				their_offer.amount,
				their_offer.country.currency.iso,
				my_offer.country.currency.iso)

		return {
			'my_country': my_offer.country.name,
			'my_charity': my_offer.charity.name,
			'my_amount': my_offer.amount,
			'my_currency': my_offer.country.currency.iso,
			'my_amount_converted': my_amount_converted,
			'their_country': their_offer.country.name,
			'their_charity': their_offer.charity.name,
			'their_amount': their_offer.amount,
			'their_currency': their_offer.country.currency.iso,
			'their_amount_converted': their_amount_converted,
			# Do NOT put their email address here.
			# Wait until both parties approved the match.
		}

	@ajax
	def approve_match(self, secret):
		match, old_offer, new_offer, my_offer, _ = self._get_match_and_offers(secret)

		if match is None:
			raise DonationException('Could not find that match. Deleted? Declined? Expired?')

		if my_offer == old_offer:
			with self._database.connect() as db:
				match.agree_old(db)
				eventlog.approved_match(db, match, my_offer)
		elif my_offer == new_offer:
			with self._database.connect() as db:
				match.agree_new(db)
				eventlog.approved_match(db, match, my_offer)

	@ajax
	def decline_match(self, secret, feedback):
		match, old_offer, new_offer, my_offer, other_offer = self._get_match_and_offers(secret)

		if match is None:
			raise DonationException('Could not find that match. Deleted? Declined? Expired?')

		with self._database.connect() as db:
			query = '''
				INSERT INTO declined_matches (new_offer_id, old_offer_id)
				VALUES (%(id_old)s, %(id_new)s);
			'''
			db.write(query, id_old=old_offer.id, id_new=new_offer.id)
			match.delete(db)
			my_offer.suspend(db)
			eventlog.declined_match(db, match, my_offer, feedback)

			replacements = {
				'{%NAME%}': my_offer.name,
				'{%OFFER_SECRET%}': my_offer.secret,
			}
			self._mail.send(
				'You declined a match',
				util.Template('match-decliner-email.txt').replace(replacements).content,
				html=util.Template('match-decliner-email.html').replace(replacements).content,
				to=my_offer.email
			)

			replacements = {
				'{%NAME%}': other_offer.name,
				'{%OFFER_SECRET%}': other_offer.secret,
			}
			self._mail.send(
				'A match you approved has been declined',
				util.Template('match-decliner-email.txt').replace(replacements).content,
				html=util.Template('match-declined-email.html').replace(replacements).content,
				to=other_offer.email
			)
