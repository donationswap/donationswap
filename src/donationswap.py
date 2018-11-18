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
import json
import logging
import os
import re
import struct
import time
import urllib.parse

from passlib.apps import custom_app_context as pwd_context # `sudo pip3 install passlib`

import captcha
import config
import currency
import database
import entities
import eventlog
import geoip
import mail
import util

#xxx separate js files

#xxx add etags

#xxx find out what information the matching algorithm provides
#    (and add it to the email)

#xxx add minimum donation amount to offer validation

#xxx move all `style="..."` stuff into style.css

#xxx layout html emails

#xxx delete db backups after 3 months

#xxx feedback page

#xxx use local time on admin pages

#xxx remove tax factor

#xxx anonymize (remove name+email) event log after 3 months

#xxx make sure certbot works when the time comes

#xxx revoke external db access from /etc/postgresql/9.6/main/pg_hba.conf

# post MVP features:
# - a donation offer is pointless if
#   - it is to the only tax-deductible charity in the country OR
#   - it is to a charity that is tax-decuctible everywhere OR
#   - it is to a charity that is tax-deductible nowhere.
# - add "blacklist charity" to offer.
# - blacklist users who agreed to the match but didn't acutally donate.
# - support crypto currencies.
# - add link to match email for user to create offer for remaining amount.
# - charities should have hyperlinks.

# pylint: disable=too-many-lines

def ajax(f):
	f.allow_ajax = True
	return f

def admin_ajax(f):
	f.allow_admin_ajax = True
	return f

def create_secret():
	timestamp_bytes = struct.pack('!d', time.time())
	random_bytes = os.urandom(10)
	return base64.b64encode(timestamp_bytes + random_bytes).decode('utf-8')

class DonationException(Exception):
	pass

class Donationswap:
	# pylint: disable=too-many-instance-attributes
	# pylint: disable=too-many-public-methods

	def __init__(self, config_path):
		self._config = config.Config(config_path)

		self._database = database.Database(self._config.db_connection_string)

		self._captcha = captcha.Captcha(self._config.captcha_secret)
		self._currency = currency.Currency(self._config.currency_cache, self._config.fixer_apikey)
		self._geoip = geoip.GeoIpCountry(self._config.geoip_datafile)
		self._mail = mail.Mail(self._config.email_user, self._config.email_password, self._config.email_smtp, self._config.email_sender_name)

		with self._database.connect() as db:
			entities.load(db)

		self._ip_address = None

		self.automation_mode = False

	def get_cookie_key(self):
		return self._config.cookie_key

	@staticmethod
	def _int(number, msg):
		try:
			return int(number)
		except (TypeError, ValueError):
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
			t1 = time.time()
			result = method(**args)
			t2 = time.time()
			logging.debug('Benchmark: %s: %s sec.', command, t2-t1)
			return True, result
		except DonationException as e:
			return False, str(e)
		except Exception: # pylint: disable=broad-except
			logging.error('Ajax Error', exc_info=True)
			return False, None

	def run_admin_ajax(self, user_secret, command, ip_address, args):
		'''Admin ajax methods do have their error messages exposed.'''

		with self._database.connect() as db:
			query = '''SELECT * FROM admins WHERE secret = %(secret)s;'''
			user = db.read_one(query, secret=user_secret)
		if user is None:
			return False, 'Must be logged in.'
		user = {
			'id': user['id'],
			'email': user['email'],
			'currency_id': user['currency_id'],
		}

		method = getattr(self, command, None)
		if method is None:
			return False, 'method does not exist'
		if not getattr(method, 'allow_admin_ajax', False):
			return False, 'not an admin-ajax method'

		self._ip_address = ip_address

		try:
			t1 = time.time()
			result = method(user, **args)
			t2 = time.time()
			logging.debug('Benchmark: %s: %s sec.', command, t2-t1)
			return True, result
		except Exception as e: # pylint: disable=broad-except
			logging.error('Ajax Admin Error', exc_info=True)
			return False, str(e)

	@staticmethod
	def get_page(name):
		return util.Template(name).content

	def _send_mail_about_unconfirmed_offer(self, offer):
		replacements = {
			'{%NAME%}': offer.name,
			'{%AMOUNT%}': offer.amount,
			'{%MIN_AMOUNT%}': offer.min_amount,
			'{%CURRENCY%}': offer.country.currency.iso,
			'{%CHARITY%}': offer.charity.name,
			'{%ARGS%}': '#%s' % urllib.parse.quote(json.dumps({
				'country': offer.country_id,
				'amount': offer.amount,
				'charity': offer.charity_id,
				'email': offer.email,
			}))
		}

		self._mail.send(
			util.Template('email-subjects.json').json('offer-unconfirmed-email'),
			util.Template('offer-unconfirmed-email.txt').replace(replacements).content,
			html=util.Template('offer-unconfirmed-email.html').replace(replacements).content,
			to=offer.email
		)

	def _delete_unconfirmed_offers(self):
		'''An offer is considered unconfirmed if it has not
		been confirmed for 24 hours.
		We delete it and send the donor an email.'''

		count = 0
		one_day_ago = datetime.datetime.utcnow() - datetime.timedelta(days=1)

		with self._database.connect() as db:
			for offer in entities.Offer.get_all(lambda x: not x.confirmed and x.created_ts < one_day_ago):
				logging.info('Deleting unconfirmed offer %s.', offer.id)
				offer.delete(db)
				eventlog.offer_unconfirmed(db, offer)
				self._send_mail_about_unconfirmed_offer(offer)
				count += 1

		return count

	def _send_mail_about_expired_offer(self, offer):
		replacements = {
			'{%NAME%}': offer.name,
			'{%AMOUNT%}': offer.amount,
			'{%MIN_AMOUNT%}': offer.min_amount,
			'{%CURRENCY%}': offer.country.currency.iso,
			'{%CHARITY%}': offer.charity.name,
			'{%ARGS%}': '#%s' % urllib.parse.quote(json.dumps({
				'country': offer.country_id,
				'amount': offer.amount,
				'charity': offer.charity_id,
				'email': offer.email,
			}))
		}

		self._mail.send(
			util.Template('email-subjects.json').json('offer-expired-email'),
			util.Template('offer-expired-email.txt').replace(replacements).content,
			html=util.Template('offer-expired-email.html').replace(replacements).content,
			to=offer.email
		)

	def _delete_expired_offers(self):
		'''An offer is considered expired if its expiration date
		is in the past and it is not part of a match.
		We delete it and send the donor an email.'''

		count = 0

		with self._database.connect() as db:
			for offer in entities.Offer.get_expired_offers(db):
				logging.info('Deleting expired offer %s.', offer.id)
				offer.delete(db)
				eventlog.offer_expired(db, offer)
				self._send_mail_about_expired_offer(offer)
				count += 1

		return count

	def _delete_unconfirmed_matches(self):
		return 0 #xxx not confirmed after 72 hours

	def _delete_expired_matches(self):
		'''Send a feedback email one month after creation.'''
		#xxx add "feedback_ts" column
		#xxx send email to matches older than 4 weeks with empty "feedback_ts"
		#xxx update feedback_ts
		#xxx delete two offers and one match one week after feedback_ts
		return 0 #xxx

	def clean_up(self):
		'''This method gets called once per hour by a cronjob.'''

		counts = {
			'unconfirmed_offers': self._delete_unconfirmed_offers(),
			'expired_offers': self._delete_expired_offers(),
			'unconfirmed_matches': self._delete_unconfirmed_matches(),
			'expired_matches': self._delete_expired_matches(),
		}

		return '%s\n' % '\n'.join('%s=%s' % i for i in sorted(counts.items()))

	@ajax
	def send_contact_message(self, captcha_response, message, name=None, email=None):
		if not self.automation_mode and not self._captcha.is_legit(self._ip_address, captcha_response):
			raise DonationException(
				util.Template('errors-and-warnings.json').json('bad captcha')
			)

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
			'Message for donationswap.eahub.org',
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
	def _get_charities_in_countries_info():
		result = {}
		for country in entities.Country.get_all():
			result[country.id] = []
			for charity in entities.Charity.get_all():
				charity_in_country = entities.CharityInCountry.by_charity_and_country_id(charity.id, country.id)
				if charity_in_country is not None:
					result[country.id].append(charity.id)
		return result

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
			'charities_in_countries': self._get_charities_in_countries_info(),
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

	def _validate_offer(self, name, country, amount, min_amount, charity, email, expiration):
		errors = util.Template('errors-and-warnings.json')

		name = name.strip()
		if not name:
			raise DonationException(errors.json('no name provided'))

		country = entities.Country.by_id(country)
		if country is None:
			raise DonationException(errors.json('country not found'))

		amount = self._int(amount, errors.json('bad amount'))
		if amount < 0:
			raise DonationException(errors.json('bad amount'))

		min_amount = self._int(min_amount, errors.json('bad min_amount'))
		if min_amount < 0:
			raise DonationException(errors.json('bad min_amount'))


		charity = entities.Charity.by_id(charity)
		if charity is None:
			raise DonationException(errors.json('charity not found'))

		email = email.strip()
		if not re.fullmatch(r'.+?@.+\..+', email):
			raise DonationException(errors.json('bad email address'))

		expires_ts = '%04i-%02i-%02i' % (
			self._int(expiration['year'], errors.json('bad expiration date')),
			self._int(expiration['month'], errors.json('bad expiration date')),
			self._int(expiration['day'], errors.json('bad expiration date')),
		)
		try:
			expires_ts = datetime.datetime.strptime(expires_ts, '%Y-%m-%d')
		except ValueError:
			raise DonationException(errors.json('bad expiration date'))

		return name, country, amount, min_amount, charity, email, expires_ts

	@ajax
	def validate_offer(self, captcha_response, name, country, amount, min_amount, charity, email, expiration):
		# pylint: disable=unused-argument
		try:
			self._validate_offer(name, country, amount, min_amount, charity, email, expiration)
			return None
		except DonationException as e:
			return str(e)

	@ajax
	def create_offer(self, captcha_response, name, country, amount, min_amount, charity, email, expiration):
		errors = util.Template('errors-and-warnings.json')
		if not self.automation_mode and not self._captcha.is_legit(self._ip_address, captcha_response):
			raise DonationException(errors.json('bad captcha'))

		name, country, amount, min_amount, charity, email, expires_ts = self._validate_offer(name, country, amount, min_amount, charity, email, expiration)

		secret = create_secret()
		# Do NOT return this secret to the client via this method.
		# Only put it in the email, so that having the link acts as email address verification.

		with self._database.connect() as db:
			offer = entities.Offer.create(db, secret, name, email, country.id, amount, min_amount, charity.id, expires_ts)
			eventlog.created_offer(db, offer)

		if self.automation_mode:
			return offer

		replacements = {
			'{%NAME%}': offer.name,
			'{%SECRET%}': offer.secret,
			'{%CHARITY%}': offer.charity.name,
			'{%CURRENCY%}': offer.country.currency.iso,
			'{%AMOUNT%}': offer.amount,
			'{%MIN_AMOUNT%}': offer.min_amount,
		}
		self._mail.send(
			util.Template('email-subjects.json').json('new-post-email'),
			util.Template('new-post-email.txt').replace(replacements).content,
			html=util.Template('new-post-email.html').replace(replacements).content,
			to=email
		)

		return None

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
			'min_amount': offer.min_amount,
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

	def _get_match_score(self, offer_a, offer_b, db):
		if offer_a.id == offer_b.id:
			return 0, 'same offer'

		if offer_a.charity_id == offer_b.charity_id:
			return 0, 'same charity'

		if offer_a.country_id == offer_b.country_id:
			return 0, 'same country'

		if offer_a.email.lower() == offer_b.email.lower():
			return 0, 'same email address'

		amount_a_in_currency_b = self._currency.convert(
			offer_a.amount,
			offer_a.country.currency.iso,
			offer_b.country.currency.iso) * offer_a.country.gift_aid_multipler
		amount_b_in_currency_a = self._currency.convert(
			offer_b.amount,
			offer_b.country.currency.iso,
			offer_a.country.currency.iso) * offer_b.country.gift_aid_multipler

		if amount_a_in_currency_b < offer_b.min_amount * offer_b.country.gift_aid_multipler:
			return 0, 'amount mismatch'
		if amount_b_in_currency_a < offer_a.min_amount * offer_a.country.gift_aid_multipler:
			return 0, 'amount mismatch'

		a_will_benefit = entities.CharityInCountry.by_charity_and_country_id(offer_b.charity_id, offer_a.country_id) is not None
		b_will_benefit = entities.CharityInCountry.by_charity_and_country_id(offer_a.charity_id, offer_b.country_id) is not None

		if not a_will_benefit and not b_will_benefit:
			return 0, 'nobody will benefit'

		query = '''
			SELECT 1
			FROM declined_matches
			WHERE (new_offer_id = %(id_a)s AND old_offer_id = %(id_b)s)
				OR (new_offer_id = %(id_b)s AND old_offer_id = %(id_a)s);
		'''
		declined = db.read_one(query, id_a=offer_a.id, id_b=offer_b.id) or False
		if declined:
			return 0, 'match declined'

		# amounts are equal => score = 1
		# amounts are vastly different => score = almost 0
		amount_a_in_nzd = self._currency.convert(
			offer_a.amount,
			offer_a.country.currency.iso,
			'NZD') * offer_a.country.gift_aid_multipler
		amount_b_in_nzd = self._currency.convert(
			offer_b.amount,
			offer_b.country.currency.iso,
			'NZD') * offer_b.country.gift_aid_multipler

		score = 1 - (amount_a_in_nzd - amount_b_in_nzd)**2 / max(amount_a_in_nzd, amount_b_in_nzd)**2

		if a_will_benefit and b_will_benefit:
			factor, reason = 1, 'both benefit'
		else:
			factor, reason = 0.5, 'only one will benefit'

		score *= factor

		score = round(score, 4)
		return score, reason

	def getActualAmounts(self, my_offer, their_offer):
		if self._currency.is_more_money(
			my_offer.amount * my_offer.country.gift_aid_multiplier,
			my_offer.country.currency.iso,
			their_offer.amount * their_offer.country.gift_aid_multiplier,
			their_offer.country.currency.iso
		):
			my_actual_amount = self._currency.convert(
				their_offer.amount * their_offer.country.gift_aid_multiplier / my_offer.country.gift_aid_multiplier,
				their_offer.country.currency.iso,
				my_offer.country.currency.iso)
			their_actual_amount = their_offer.amount
		else:
			my_actual_amount = my_offer.amount
			their_actual_amount = self._currency.convert(
				my_offer.amount  * my_offer.country.gift_aid_multiplier / their_offer.country.gift_aid_multiplier,
				my_offer.country.currency.iso,
				their_offer.country.currency.iso)

		return my_actual_amount, their_actual_amount

	@ajax
	def get_match(self, secret):
		match, old_offer, new_offer, my_offer, their_offer = self._get_match_and_offers(secret)
		if my_offer is None or their_offer is None:
			return None

		my_actual_amount, their_actual_amount = self.getActualAmounts(my_offer, their_offer)

		can_edit = False
		if my_offer.id == new_offer.id:
			can_edit = match.new_agrees is None
		elif my_offer.id == old_offer.id:
			can_edit = match.old_agrees is None

		return {
			#xxx add calculation
			'my_country': my_offer.country.name,
			'my_charity': my_offer.charity.name,
			'my_amount': my_actual_amount,
			'my_currency': my_offer.country.currency.iso,
			'their_country': their_offer.country.name,
			'their_charity': their_offer.charity.name,
			'their_amount': their_actual_amount,
			'their_currency': their_offer.country.currency.iso,
			'can_edit': can_edit,
			# Do NOT put their email address here.
			# Wait until both parties approved the match.
		}

	def _send_mail_about_approved_match(self, offer_a, offer_b):
		if self._currency.is_more_money(
			offer_a.amount,
			offer_a.country.currency.iso,
			offer_b.amount,
			offer_b.country.currency.iso
		):
			actual_amount_a = self._currency.convert(
				offer_b.amount,
				offer_b.country.currency.iso,
				offer_a.country.currency.iso)
			actual_amount_b = offer_b.amount
		else:
			actual_amount_a = offer_a.amount
			actual_amount_b = self._currency.convert(
				offer_a.amount,
				offer_a.country.currency.iso,
				offer_b.country.currency.iso)

		tmp = entities.CharityInCountry.by_charity_and_country_id(
			offer_b.charity.id,
			offer_a.country.id)
		if tmp is not None:
			instructions_a = tmp.instructions
		else:
			instructions_a = 'Sorry, there are no instructions available (yet).'

		tmp = entities.CharityInCountry.by_charity_and_country_id(
			offer_a.charity.id,
			offer_b.country.id)
		if tmp is not None:
			instructions_b = tmp.instructions
		else:
			instructions_b = 'Sorry, there are no instructions available (yet).'

		replacements = {
			#xxx add calculation
			'{%NAME_A%}': offer_a.name,
			'{%COUNTRY_A%}': offer_a.country.name,
			'{%CHARITY_A%}': offer_a.charity.name,
			'{%ACTUAL_AMOUNT_A%}': actual_amount_a,
			'{%CURRENCY_A%}': offer_a.country.currency.iso,
			'{%EMAIL_A%}': offer_a.email,
			'{%INSTRUCTIONS_A%}': instructions_a,
			'{%NAME_B%}': offer_b.name,
			'{%COUNTRY_B%}': offer_b.country.name,
			'{%CHARITY_B%}': offer_b.charity.name,
			'{%ACTUAL_AMOUNT_B%}': actual_amount_b,
			'{%CURRENCY_B%}': offer_b.country.currency.iso,
			'{%EMAIL_B%}': offer_b.email,
			'{%INSTRUCTIONS_B%}': instructions_b,
		}

		logging.info('Sending deal email to %s and %s.', offer_a.email, offer_b.email)

		self._mail.send(
			util.Template('email-subjects.json').json('match-approved-email'),
			util.Template('match-approved-email.txt').replace(replacements).content,
			html=util.Template('match-approved-email.html').replace(replacements).content,
			to=[offer_a.email, offer_b.email]
		)

	@ajax
	def approve_match(self, secret):
		match, old_offer, new_offer, my_offer, _ = self._get_match_and_offers(secret)

		if match is None:
			raise DonationException(
				util.Template('errors-and-warnings.json').json('match not found')
			)

		if my_offer == old_offer:
			with self._database.connect() as db:
				match.agree_old(db)
				eventlog.approved_match(db, match, my_offer)
		elif my_offer == new_offer:
			with self._database.connect() as db:
				match.agree_new(db)
				eventlog.approved_match(db, match, my_offer)

		if match.old_agrees and match.new_agrees:
			self._send_mail_about_approved_match(old_offer, new_offer)

	@ajax
	def decline_match(self, secret, feedback):
		match, old_offer, new_offer, my_offer, other_offer = self._get_match_and_offers(secret)

		if match is None:
			raise DonationException(
				util.Template('errors-and-warnings.json').json('match not found')
			)

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
				util.Template('match-decliner-email.json').json('new-post-email'),
				util.Template('match-decliner-email.txt').replace(replacements).content,
				html=util.Template('match-decliner-email.html').replace(replacements).content,
				to=my_offer.email
			)

			replacements = {
				'{%NAME%}': other_offer.name,
				'{%OFFER_SECRET%}': other_offer.secret,
			}
			self._mail.send(
				util.Template('match-declined-email.json').json('new-post-email'),
				util.Template('match-declined-email.txt').replace(replacements).content,
				html=util.Template('match-declined-email.html').replace(replacements).content,
				to=other_offer.email
			)

	@ajax
	def login(self, email, password):
		with self._database.connect() as db:
			query = '''
				SELECT password_hash
				FROM admins
				WHERE email = %(email)s;
			'''
			row = db.read_one(query, email=email)
			if row is None:
				password_hash = None
			else:
				password_hash = row['password_hash']

			# We run this even if password_hash is None, because
			# otherwise "user does not exist" would return MUCH
			# faster than "password is wrong", which is bad security.
			success = pwd_context.verify(password, password_hash)

			if not success:
				raise ValueError('User not found or wrong password.')

			secret = create_secret()

			query = '''
				UPDATE admins
				SET secret=%(secret)s, last_login_ts=now()
				WHERE email=%(email)s;
			'''
			db.write(query, email=email, secret=secret)

			return secret

	@admin_ajax
	def logout(self, user):
		with self._database.connect() as db:
			query = '''
				UPDATE admins
				SET secret=null
				WHERE id = %(admin_id)s;
			'''
			db.write(query, admin_id=user['id'])

	@admin_ajax
	def change_password(self, user, old_password, new_password):
		with self._database.connect() as db:
			query = '''
				SELECT password_hash
				FROM admins
				WHERE id = %(admin_id)s;
			'''
			password_hash = db.read_one(query, admin_id=user['id'])['password_hash']
			success = pwd_context.verify(old_password, password_hash)

			if not success:
				raise ValueError('Current password is incorrect.')

			password_hash = pwd_context.encrypt(new_password)
			query = '''
				UPDATE admins
				SET password_hash = %(password_hash)s
				WHERE id = %(admin_id)s;
			'''
			db.write(query, password_hash=password_hash, admin_id=user['id'])

	@admin_ajax
	def get_admin_info(self, user): # pylint: disable=no-self-use
		return user

	@admin_ajax
	def get_currencies(self, _): # pylint: disable=no-self-use
		return [
			{
				'id': i.id,
				'name': '%s (%s)' % (i.iso, i.name),
			}
			for i in sorted(
				entities.Currency.get_all(),
				key=lambda x: x.iso)
		]

	@admin_ajax
	def set_admin_currency(self, user, currency_id):
		with self._database.connect() as db:
			query = '''
				UPDATE admins
				SET currency_id = %(currency_id)s
				WHERE id = %(id)s;
			'''
			db.write(query, currency_id=currency_id, id=user['id'])
			return True

	@admin_ajax
	def read_all(self, _): # pylint: disable=no-self-use
		return {
			'currencies': [
				{
					'id': i.id,
					'iso': i.iso,
					'name': i.name,
				}
				for i in sorted(
					entities.Currency.get_all(),
					key=lambda x: x.iso)
			],
			'charity_categories': [
				{
					'id': i.id,
					'name': i.name,
				}
				for i in sorted(
					entities.CharityCategory.get_all(),
					key=lambda x: x.name)
			],
			'charities': [
				{
					'id': i.id,
					'name': i.name,
					'category_id': i.category_id,
				}
				for i in sorted(
					entities.Charity.get_all(),
					key=lambda x: x.name)
			],
			'countries': [
				{
					'id': i.id,
					'name': i.name,
					'live_in_name': i.live_in_name,
					'iso_name': i.iso_name,
					'currency_id': i.currency_id,
					'min_donation_amount': i.min_donation_amount,
					'min_donation_currency_id': i.min_donation_currency_id,
					'gift_aid': i.gift_aid
				}
				for i in sorted(
					entities.Country.get_all(),
					key=lambda x: x.iso_name)
			],
			'charities_in_countries': [
				{
					'charity_id': i.charity_id,
					'country_id': i.country_id,
					'tax_factor': i.tax_factor,
					'instructions': i.instructions,
				}
				for i in entities.CharityInCountry.get_all()
			],
		}

	@admin_ajax
	def create_charity_category(self, _, name):
		with self._database.connect() as db:
			entities.CharityCategory.create(db, name)

	@admin_ajax
	def update_charity_category(self, _, category_id, name):
		category = entities.CharityCategory.by_id(category_id)
		category.name = name
		with self._database.connect() as db:
			category.save(db)

	@admin_ajax
	def delete_charity_category(self, _, category_id):
		with self._database.connect() as db:
			entities.CharityCategory.by_id(category_id).delete(db)

	@admin_ajax
	def create_charity(self, _, name, category_id):
		with self._database.connect() as db:
			entities.Charity.create(db, name, category_id)

	@admin_ajax
	def update_charity(self, _, charity_id, name, category_id):
		charity = entities.Charity.by_id(charity_id)
		charity.name = name
		charity.category_id = category_id
		with self._database.connect() as db:
			charity.save(db)

	@admin_ajax
	def delete_charity(self, _, charity_id):
		with self._database.connect() as db:
			entities.Charity.by_id(charity_id).delete(db)

	@admin_ajax
	def create_country(self, _, name, live_in_name, iso_name, currency_id, min_donation_amount, min_donation_currency_id, gift_aid):
		with self._database.connect() as db:
			entities.Country.create(db, name, live_in_name, iso_name, currency_id, min_donation_amount, min_donation_currency_id, gift_aid)

	@admin_ajax
	def update_country(self, _, country_id, name, live_in_name, iso_name, currency_id, min_donation_amount, min_donation_currency_id):
		country = entities.Country.by_id(country_id)
		country.name = name
		country.live_in_name = live_in_name
		country.iso_name = iso_name
		country.currency_id = currency_id
		country.min_donation_amount = min_donation_amount
		country.min_donation_currency_id = min_donation_currency_id
		with self._database.connect() as db:
			country.save(db)

	@admin_ajax
	def delete_country(self, _, country_id):
		with self._database.connect() as db:
			entities.Country.by_id(country_id).delete(db)

	@admin_ajax
	def create_charity_in_country(self, _, charity_id, country_id, tax_factor, instructions):
		with self._database.connect() as db:
			entities.CharityInCountry.create(db, charity_id, country_id, tax_factor, instructions)

	@admin_ajax
	def update_charity_in_country(self, _, charity_id, country_id, tax_factor, instructions):
		charity_in_country = entities.CharityInCountry.by_charity_and_country_id(charity_id, country_id)
		charity_in_country.tax_factor = tax_factor
		charity_in_country.instructions = instructions
		with self._database.connect() as db:
			charity_in_country.save(db)

	@admin_ajax
	def delete_charity_in_country(self, _, charity_id, country_id):
		with self._database.connect() as db:
			entities.CharityInCountry.by_charity_and_country_id(charity_id, country_id).delete(db)

	@admin_ajax
	def read_log(self, _, min_timestamp, max_timestamp, event_types, offset, limit):
		with self._database.connect() as db:
			events = eventlog.get_events(
				db,
				min_timestamp=min_timestamp,
				max_timestamp=max_timestamp,
				event_types=event_types,
				offset=offset,
				limit=limit,
			)
		return events

	def _get_unmatched_offers(self):
		'''Returns all offers that are confirmed and
		not expired and not matched.'''

		with self._database.connect() as db:
			entities.Offer.load(db) # only necessary because of console.py
			return entities.Offer.get_unmatched_offers(db)

	@admin_ajax
	def get_unmatched_offers(self, user):
		admin_currency = entities.Currency.by_id(user['currency_id'])
		return [
			{
				'id': offer.id,
				'country': offer.country.name,
				'amount': offer.amount,
				'min_amount': offer.min_amount,
				'currency': offer.country.currency.iso,
				'charity': offer.charity.name,
				'expires_ts': offer.expires_ts.strftime('%Y-%m-%d %H:%M:%S'),
				'email': offer.email,
				'name': offer.name,
				'amount_localized': self._currency.convert(
					offer.amount,
					offer.country.currency.iso,
					admin_currency.iso),
				'min_amount_localized': self._currency.convert(
					offer.min_amount,
					offer.country.currency.iso,
					admin_currency.iso),
				'currency_localized': admin_currency.iso
			}
			for offer in self._get_unmatched_offers()
		]

	@admin_ajax
	def get_match_scores(self, _, offer_id):
		with self._database.connect() as db:
			offer_a = entities.Offer.by_id(offer_id)
			return {
				offer_b.id: self._get_match_score(offer_a, offer_b, db)
				for offer_b in self._get_unmatched_offers()
			}

	def _send_mail_about_match(self, my_offer, their_offer, match_secret):
		their_amount_in_your_currency = self._currency.convert(
			their_offer.amount,
			their_offer.country.currency.iso,
			my_offer.country.currency.iso)

		my_actual_amount, their_actual_amount = self.getActualAmounts(my_offer, their_offer)

		replacements = {
			'{%YOUR_NAME%}': my_offer.name,
			'{%YOUR_CHARITY%}': my_offer.charity.name,
			'{%YOUR_AMOUNT%}': my_offer.amount,
			'{%YOUR_MIN_AMOUNT%}': my_offer.min_amount,
			'{%YOUR_ACTUAL_AMOUNT%}': my_actual_amount,
			'{%YOUR_CURRENCY%}': my_offer.country.currency.iso,
			'{%THEIR_CHARITY%}': their_offer.charity.name,
			'{%THEIR_AMOUNT%}': their_offer.amount,
			'{%THEIR_CURRENCY%}': their_offer.country.currency.iso,
			'{%THEIR_AMOUNT_CONVERTED%}': their_amount_in_your_currency,
			'{%THEIR_ACTUAL_AMOUNT%}': their_actual_amount,
			'{%SECRET%}': '%s%s' % (my_offer.secret, match_secret),
			# Do NOT put their email address here.
			# Wait until both parties approved the match.
		}

		logging.info('Sending match email to %s.', my_offer.email)

		self._mail.send(
			util.Template('email-subjects.json').json('match-suggested-email'),
			util.Template('match-suggested-email.txt').replace(replacements).content,
			html=util.Template('match-suggested-email.html').replace(replacements).content,
			to=my_offer.email
		)

	@admin_ajax
	def create_match(self, _, offer_a_id, offer_b_id):
		offer_a = entities.Offer.by_id(offer_a_id)
		offer_b = entities.Offer.by_id(offer_b_id)

		match_secret = create_secret()

		if offer_a.created_ts < offer_b.created_ts:
			old_offer, new_offer = offer_a, offer_b
		else:
			old_offer, new_offer = offer_b, offer_a

		with self._database.connect() as db:
			match = entities.Match.create(db, match_secret, new_offer.id, old_offer.id)
			eventlog.match_generated(db, match)
			self._send_mail_about_match(old_offer, new_offer, match_secret)
			self._send_mail_about_match(new_offer, old_offer, match_secret)
