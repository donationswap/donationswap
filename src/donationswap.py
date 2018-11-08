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
import geoip
import mail
import util

def ajax(f):
	f.allow_ajax = True
	return f

#xxx name, min_amount
#xxx add "show only tax-deductible charities" checkbox to /start/

#xxx add declined_matches table with offer1_id and offer2_id column.
#xxx add permanent record to database

#xxx when a user declines a match, they should get asked if
#    they want to delete their own (now suspended) offer.

#xxx send feedback email after a month.

#xxx add link to from /start/ to /readonlyadmin/ so potential donors
#    can learn more about charities.

#xxx make /start/ so that it can be pre-populated with ?country=42&charity=27
#    so we can email URLs

#xxx find a way for Catherine to get statistics out of the db
#    (unmatched offers etc.)

#xxx post MVP features:
#- a donation offer is pointless if
#  - it is to the only tax-deductible charity in the country OR
#  - it is to a charity that is tax-decuctible everywhere
# - add "never match me with any of these charity" blacklist button.
# - add "blacklist charity" to offer.
# - blacklist users who agreed to the match but didn't acutally donate.
# - support crypto currencies.

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

	@staticmethod
	def _int(number, msg):
		try:
			return int(number)
		except ValueError:
			raise DonationException(msg)

	@staticmethod
	def _get_match_and_offers(secret):
		if len(secret) != 48:
			logging.debug('invalid secret length.')
			return None, None, None, None, None

		offer_secret = secret[:24]
		match_secret = secret[24:]

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

	def run_admin_ajax(self, command, args):
		'''Admin ajax methods do have their error messages exposed.'''

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

		self._mail.send(
			'Message for donationswap.eahub.org',
			tmp.content,
			to=self._config.contact_message_receivers.get('to', []),
			cc=self._config.contact_message_receivers.get('cc', []),
			bcc=self._config.contact_message_receivers.get('bcc', [])
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

	def _validate_offer(self, captcha_response, country, amount, charity, email, expiration):
		is_legit = self._captcha.is_legit(self._ip_address, captcha_response)

		if not is_legit:
			raise DonationException('bad captcha response')

		country = entities.Country.by_id(country)
		if country is None:
			raise DonationException('country not found')

		amount = self._int(amount, 'invalid amount')

		if amount < 0:
			raise DonationException('negative amount')

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

		return country, amount, charity, email, expires_ts

	@ajax
	def create_offer(self, captcha_response, country, amount, charity, email, expiration):
		#xxx add name to offer (so we can start the email with "Dear <name>")

		country, amount, charity, email, expires_ts = self._validate_offer(captcha_response, country, amount, charity, email, expiration)

		secret = create_secret()
		# Do NOT return this secret to the client via this method.
		# Only put it in the email, so that having the link acts as email address verification.

		with self._database.connect() as db:
			entities.Offer.create(db, secret, email, country.id, amount, charity.id, expires_ts)

		replacements = {
			'{%NAME%}': 'xxx',
			'{%SECRET%}': secret,
			'{%CHARITY%}': charity.name,
			'{%CURRENCY%}': country.currency.iso,
			'{%AMOUNT%}': amount,
			'{%MIN_AMOUNT%}': 'xxx',
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
		elif my_offer == new_offer:
			with self._database.connect() as db:
				match.agree_new(db)

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

			#xxx add to permanent record

			#xxx feedback isn't actually used yet

			replacements = {
				'{%NAME%}': 'xxx (name not implemented yet)', #offer.name
				'{%OFFER_SECRET%}': my_offer.secret,
			}
			self._mail.send(
				'You declined a match',
				util.Template('match-decliner-email.txt').replace(replacements).content,
				html=util.Template('match-decliner-email.html').replace(replacements).content,
				to=my_offer.email
			)

			replacements = {
				'{%NAME%}': 'xxx (name not implemented yet)', #offer.name
				'{%OFFER_SECRET%}': other_offer.secret,
			}
			self._mail.send(
				'A match you approved has been declined',
				util.Template('match-decliner-email.txt').replace(replacements).content,
				html=util.Template('match-declined-email.html').replace(replacements).content,
				to=other_offer.email
			)
