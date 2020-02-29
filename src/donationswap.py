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

#xxx anonymize (remove name+email) event log after 3 months

#xxx make sure certbot works when the time comes

#xxx revoke external db access from /etc/postgresql/9.6/main/pg_hba.conf

# post MVP features:
# - a donation offer is pointless if
#   - it is to the only tax-deductible charity in the country OR
#   - it is to a charity that is tax-decuctible everywhere OR
#   - it is to a charity that is not tax-deductible anywhere.
# - add "blacklist charity" to offer.
# - blacklist donors who agreed to the match but didn't acutally donate.
# - support crypto currencies.
# - add link to match email for user to create offer for remaining amount.
# - charities should have hyperlinks.
# - layout html emails.

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
	raw_secret = timestamp_bytes + random_bytes
	secret = base64.b64encode(raw_secret, altchars=b'-_')
	return secret.decode('utf-8')

class DonationException(Exception):
	pass

class Donationswap:
	# pylint: disable=too-many-instance-attributes
	# pylint: disable=too-many-public-methods

	STATIC_VERSION = 4 # cache-breaker

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

	def get_page(self, name):
		content = util.Template(name).content

		# This acts as a cache breaker -- just increment
		# self.STATIC_VERSION whenever a static file has changed,
		# so the client will know to re-request it from the server.
		# The only exception are files referenced in style.css,
		# which must be handled manually.
		content = re.sub('src="/static/(.*?)"', lambda m: 'src="/static/%s?v=%s"' % (m.group(1), self.STATIC_VERSION), content)
		content = re.sub('href="/static/(.*?)"', lambda m: 'href="/static/%s?v=%s"' % (m.group(1), self.STATIC_VERSION), content)

		return content

	def _send_mail_about_unconfirmed_offer(self, offer):
		replacements = {
			'{%NAME%}': offer.name,
			'{%AMOUNT%}': offer.amount,
			'{%MIN_AMOUNT%}': offer.min_amount,
			'{%CURRENCY%}': offer.country.currency.iso,
			'{%CHARITY%}': offer.charity.name,
			'{%ARGS%}': '#%s' % urllib.parse.quote(json.dumps({
				'name': offer.name,
				'country': offer.country_id,
				'amount': offer.amount,
				'min_amount': offer.min_amount,
				'charity': offer.charity_id,
				'email': offer.email,
				'expires': {
					'day': offer.expires_ts.day,
					'month': offer.expires_ts.month,
					'year': offer.expires_ts.year,
				}
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
		newExpirey = offer.expires_ts + (offer.expires_ts - offer.created_ts)
		replacements = {
			'{%NAME%}': offer.name,
			'{%AMOUNT%}': offer.amount,
			'{%MIN_AMOUNT%}': offer.min_amount,
			'{%CURRENCY%}': offer.country.currency.iso,
			'{%CHARITY%}': offer.charity.name,
			'{%ARGS%}': '#%s' % urllib.parse.quote(json.dumps({
				'name': offer.name,
				'country': offer.country_id,
				'amount': offer.amount,
				'min_amount': offer.min_amount,
				'charity': offer.charity_id,
				'email': offer.email,
				'expires': {
					'day': newExpirey.day,
					'month': newExpirey.month,
					'year': newExpirey.year,
				}
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

	def _send_mail_about_unconfirmed_matches(self, match):
		new_offer = entities.Offer.by_id(match.new_offer_id)
		old_offer = entities.Offer.by_id(match.old_offer_id)

		new_replacements = {
			'{%NAME%}': new_offer.name,
			'{%OFFER_SECRET%}': new_offer.secret,
			'{%ARGS%}': '#%s' % urllib.parse.quote(json.dumps({
				'name': new_offer.name,
				'country': new_offer.country_id,
				'amount': new_offer.amount,
				'min_amount': new_offer.min_amount,
				'charity': new_offer.charity_id,
				'email': new_offer.email,
				'expires': {
					'day': new_offer.expires_ts.day,
					'month': new_offer.expires_ts.month,
					'year': new_offer.expires_ts.year,
				}
			}))
		}

		old_replacements = {
			'{%NAME%}': old_offer.name,
			'{%OFFER_SECRET%}': old_offer.secret,
			'{%ARGS%}': '#%s' % urllib.parse.quote(json.dumps({
				'name': old_offer.name,
				'country': old_offer.country_id,
				'amount': old_offer.amount,
				'min_amount': old_offer.min_amount,
				'charity': old_offer.charity_id,
				'email': old_offer.email,
				'expires': {
					'day': old_offer.expires_ts.day,
					'month': old_offer.expires_ts.month,
					'year': old_offer.expires_ts.year,
				}
			}))
		}

		#TODO: needs args applied to a new offer rather than reconfirming old offer

		if (match.new_agrees == True):
			self._mail.send(
				util.Template('email-subjects.json').json('match-unconfirmed-email'),
				util.Template('match-unconfirmed-email.txt').replace(new_replacements).content,
				html=util.Template('match-unconfirmed-email.html').replace(new_replacements).content,
				to=new_offer.email)
		else:
			self._mail.send(
				util.Template('email-subjects.json').json('match-unconfirmer-email'),
				util.Template('match-unconfirmer-email.txt').replace(new_replacements).content,
				html=util.Template('match-unconfirmer-email.html').replace(new_replacements).content,
				to=new_offer.email)

		if (match.old_agrees == True):
			self._mail.send(
				util.Template('email-subjects.json').json('match-unconfirmed-email'),
				util.Template('match-unconfirmed-email.txt').replace(old_replacements).content,
				html=util.Template('match-unconfirmed-email.html').replace(old_replacements).content,
				to=old_offer.email)
		else:
			self._mail.send(
				util.Template('email-subjects.json').json('match-unconfirmer-email'),
				util.Template('match-unconfirmer-email.txt').replace(old_replacements).content,
				html=util.Template('match-unconfirmer-email.html').replace(old_replacements).content,
				to=old_offer.email)

	def _delete_unconfirmed_matches(self):
		return 0 #TODO: needs testing

		count = 0
		three_days_ago = datetime.datetime.utcnow() - datetime.timedelta(days=3)

		with self._database.connect() as db:
			for match in entities.Match.get_unconfirmed_matches(db):
				if (match.created_ts < three_days_ago):
					logging.info('Deleting unconfirmed match %s', match.id)
					# match.delete(db) #TODO: check workflow with marc
					eventlog.match_unconfirmed(db, match)
					self._send_mail_about_unconfirmed_match(match)
					count += 1

		return count

	def _send_feedback_email(self, match):
		new_offer = entities.Offer.by_id(match.new_offer_id)
		old_offer = entities.Offer.by_id(match.old_offer_id)

		new_actual_amount, old_actual_amount = self._get_actual_amounts(match, new_offer, old_offer)

		new_replacements = {
			'{%NAME%}': new_offer.name,
			'{%NAME_OTHER%}': old_offer.name,
			'{%AMOUNT%}': new_actual_amount,
			'{%CURRENCY%}': new_offer.country.currency.iso,
			'{%CHARITY%}': new_offer.charity.name,
			'{%AMOUNT_OTHER%}': old_actual_amount,
			'{%CURRENCY_OTHER%}': old_offer.country.currency.iso,
			'{%CHARITY_OTHER%}': old_offer.charity.name,
			'{%OFFER_SECRET%}': urllib.parse.quote(new_offer.secret)
		}

		old_replacements = {
			'{%NAME%}': old_offer.name,
			'{%NAME_OTHER%}': new_offer.name,
			'{%AMOUNT%}':old_actual_amount,
			'{%CURRENCY%}': old_offer.country.currency.iso,
			'{%CHARITY%}': old_offer.charity.name,
			'{%AMOUNT_OTHER%}': new_actual_amount,
			'{%CURRENCY_OTHER%}': new_offer.country.currency.iso,
			'{%CHARITY_OTHER%}': new_offer.charity.name,
			'{%OFFER_SECRET%}': urllib.parse.quote(old_offer.secret)
		}

		self._mail.send(
			util.Template('email-subjects.json').json('feedback-email'),
			util.Template('feedback-email.txt').replace(new_replacements).content,
			html=util.Template('feedback-email.html').replace(new_replacements).content,
			to=new_offer.email)

		self._mail.send(
			util.Template('email-subjects.json').json('feedback-email'),
			util.Template('feedback-email.txt').replace(old_replacements).content,
			html=util.Template('feedback-email.html').replace(old_replacements).content,
			to=old_offer.email)

	def _delete_expired_matches(self):
		'''Send a feedback email one month after creation.'''
		count = 0
		one_month_ago = datetime.datetime.utcnow() - datetime.timedelta(days=31)

		with self._database.connect() as db:
			for match in entities.Match.get_feedback_ready_matches(db):
				if (match.created_ts < one_month_ago):
					logging.info('Requesting feedback for match %s', match.id)
					eventlog.match_feedback(db, match)
					match.set_feedback_requested(db)
					self._send_feedback_email(match)
					count += 1
		#xxx delete two offers and one match one week after feedback_ts TODO elsewhere maybe?
		return count

	def clean_up(self):
		'''This method gets called once per hour by a cronjob.'''

		# We _may_ have downloaded a new geoip database,
		# in which case we have to load it.
		# This is rare (once per month), and this method
		# gets called often (once per hour), but loading is fast,
		# so I guess it's alright.
		self._geoip.clear()

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

		if min_amount > amount:
			raise DonationException(errors.json('min_amount_larger'))

		min_allowed_amount = self._currency.convert(
			country.min_donation_amount,
			country.min_donation_currency,
			country.currency)

		if min_amount < min_allowed_amount:
			raise DonationException(errors.json('min_amount_too_small') % (
				country.min_donation_amount, country.min_donation_currency.iso))

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

		replacements = {
			'{%CHARITY%}': offer.charity.name,
			'{%CURRENCY%}': offer.country.currency.iso,
			'{%AMOUNT%}': offer.amount,
			'{%MIN_AMOUNT%}': offer.min_amount,
			'{%COUNTRY%}': offer.country.name
		}

		self._mail.send(
			util.Template('email-subjects.json').json('post-confirmed-email'),
			util.Template('post-confirmed-email.txt').replace(replacements).content,
			html=util.Template('post-confirmed-email.html').replace(replacements).content,
			to=self._config.contact_message_receivers['to']
		)

		return {
			'was_confirmed': was_confirmed,
			'name': offer.name,
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
			offer_b.country.currency.iso) * offer_a.country.gift_aid_multiplier
		amount_b_in_currency_a = self._currency.convert(
			offer_b.amount,
			offer_b.country.currency.iso,
			offer_a.country.currency.iso) * offer_b.country.gift_aid_multiplier

		if amount_a_in_currency_b < offer_b.min_amount * offer_b.country.gift_aid_multiplier:
			return 0, 'amount mismatch'
		if amount_b_in_currency_a < offer_a.min_amount * offer_a.country.gift_aid_multiplier:
			return 0, 'amount mismatch'

		#xxx only count as "benefit" if own charity isn't tax-deductible, but other donor's one is
		#    (otherwise we would reward pointless swaps, where both donors already get their tax back)
		#    J -> we can start by checking whether we would have gotten a benefit by donating to our chosen charity anyway
		a_would_have_benefit = entities.CharityInCountry.by_charity_and_country_id(offer_a.charity_id, offer_a.country_id) is not None
		b_would_have_benefit = entities.CharityInCountry.by_charity_and_country_id(offer_b.charity_id, offer_b.country_id) is not None

		if a_would_have_benefit and b_would_have_benefit:
			return 0, 'both would benefit from donating to their chosen charity anyway'

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

		# TODO
		#xxx
		# scoring should be impacted by a_would_have_benefit and b_would_have_benefit
		# if either is true *0.5?

		# amounts are equal => score = 1
		# amounts are vastly different => score = almost 0
		amount_a_in_nzd = self._currency.convert(
			offer_a.amount,
			offer_a.country.currency.iso,
			'NZD') * offer_a.country.gift_aid_multiplier
		amount_b_in_nzd = self._currency.convert(
			offer_b.amount,
			offer_b.country.currency.iso,
			'NZD') * offer_b.country.gift_aid_multiplier

		score = 1 - (amount_a_in_nzd - amount_b_in_nzd)**2 / max(amount_a_in_nzd, amount_b_in_nzd)**2

		if a_will_benefit and b_will_benefit:
			factor, reason = 1, 'both benefit'
		else:
			factor, reason = 0.5, 'only one will benefit'

		score *= factor

		score = round(score, 4)
		return score, reason

	def _get_actual_amounts(self, match, my_offer, their_offer):

		# DB check
		if (match.new_actual_amount > 0 and match.old_actual_amount > 0):
			if (match.new_offer_id == my_offer.id and match.old_offer_id == their_offer.id):
				return match.new_actual_amount, match.old_actual_amount
			elif (match.old_offer_id == my_offer.id and match.new_offer_id == their_offer.id):
				return match.old_actual_amount, match.new_actual_amount

		currencyData = self._currency

		try:
			one_day_ago = datetime.datetime.utcnow() - datetime.timedelta(days=1)
			if (match.created_ts < one_day_ago) :
				url = 'http://data.fixer.io/api/{:04d}-{:02d}-{:02d}?access_key=%s' % (match.created_ts.year, match.created_ts.month, match.created_ts.day, self._secret)
				with urllib.request.urlopen(url) as f:
					content = f.read()
					data = json.loads(content.decode('utf-8'))
					if data.get('success', False):
						currencyData = currency.HistoricCurrency(data)
		except:
			pass # just use now currency if we can't get historic

		match.new_amount_suggested
		match.old_amount_suggested
		match.created_ts

		if currencyData.is_more_money(
			my_offer.amount * my_offer.country.gift_aid_multiplier,
			my_offer.country.currency.iso,
			their_offer.amount * their_offer.country.gift_aid_multiplier,
			their_offer.country.currency.iso
		):
			my_actual_amount = currencyData.convert(
				their_offer.amount * their_offer.country.gift_aid_multiplier / my_offer.country.gift_aid_multiplier,
				their_offer.country.currency.iso,
				my_offer.country.currency.iso)
			their_actual_amount = their_offer.amount
		else:
			my_actual_amount = my_offer.amount
			their_actual_amount = currencyData.convert(
				my_offer.amount  * my_offer.country.gift_aid_multiplier / their_offer.country.gift_aid_multiplier,
				my_offer.country.currency.iso,
				their_offer.country.currency.iso)

		# save to DB
		if (match.new_offer_id == my_offer.id and match.old_offer_id == their_offer.id):
			with self._database.connect() as db:
				match.set_new_amount_suggested_requested(db, my_actual_amount)
				match.set_old_amount_suggested_requested(db, their_actual_amount)
		elif (match.old_offer_id == my_offer.id and match.new_offer_id == their_offer.id):
			with self._database.connect() as db:
				match.set_old_amount_suggested_requested(db, my_actual_amount)
				match.set_new_amount_suggested_requested(db, their_actual_amount)

		return my_actual_amount, their_actual_amount

	@ajax
	def get_match(self, secret):
		match, old_offer, new_offer, my_offer, their_offer = self._get_match_and_offers(secret)
		if my_offer is None or their_offer is None:
			return None

		my_actual_amount, their_actual_amount = self._get_actual_amounts(match, my_offer, their_offer)

		can_edit = False
		if my_offer.id == new_offer.id:
			can_edit = match.new_agrees is None
		elif my_offer.id == old_offer.id:
			can_edit = match.old_agrees is None

		return {
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

	@staticmethod
	def _get_gift_aid_insert(offer, to_charity_amount, charity_receiving):
		if offer.country.gift_aid_multiplier <= 1:
			return "", ""

		# hardcoding might be bad practice,
		# but if we have to do more work due to more gift aid, it's not such a bad thing,
		# I'm also happy to move this to the database eventually
		gift_aid_name = "UK government Gift Aid"
		if offer.country.iso_name == "IE":
			gift_aid_name = "Irish government contribution"

		replacements = {
			'{%GIFT_AID_NAME%}': gift_aid_name,
			'{%GIFT_AID_AMOUNT%}': offer.country.gift_aid,
			'{%TO_CHARITY%}': to_charity_amount,
			'{%CURRENCY%}': offer.country.currency.iso,
			'{%CHARITY_NAME%}': charity_receiving,
		}

		txt = util.Template('gift-aid-insert.txt').replace(replacements).content
		html = util.Template('gift-aid-insert.html').replace(replacements).content

		return txt, html

	def _send_mail_about_approved_match(self, match, offer_a, offer_b):

		actual_amount_a, actual_amount_b = self._get_actual_amounts(match, offer_a, offer_b)
		to_charity_a = actual_amount_a * offer_a.country.gift_aid_multiplier
		to_charity_b = actual_amount_b * offer_b.country.gift_aid_multiplier

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

		gift_aid_insert_a_txt, gift_aid_insert_a_html = self._get_gift_aid_insert(offer_a, to_charity_a, offer_b.charity.name)
		gift_aid_insert_b_txt, gift_aid_insert_b_html = self._get_gift_aid_insert(offer_b, to_charity_b, offer_a.charity.name)

		currency_a_as_b = self._currency.convert(
			1000,
			offer_a.country.currency.iso,
			offer_b.country.currency.iso) / 1000.0

		replacements = {
			'{%NAME_A%}': offer_a.name,
			'{%COUNTRY_A%}': offer_a.country.name,
			'{%CHARITY_A%}': offer_a.charity.name,
			'{%ACTUAL_AMOUNT_A%}': actual_amount_a, # the amount A donates
			'{%CURRENCY_A%}': offer_a.country.currency.iso,
			'{%EMAIL_A%}': offer_a.email,
			'{%INSTRUCTIONS_A%}': instructions_a,
			'{%TO_CHARITY_A%}': to_charity_a, # the amount received from A's donation
			'{%GIFT_AID_INSERT_A_TXT%}': gift_aid_insert_a_txt,
			'{%GIFT_AID_INSERT_A_HTML%}': gift_aid_insert_a_html,
			'{%ONE_CURRENCY_A_AS_B%}': currency_a_as_b,
			'{%NAME_B%}': offer_b.name,
			'{%COUNTRY_B%}': offer_b.country.name,
			'{%CHARITY_B%}': offer_b.charity.name,
			'{%ACTUAL_AMOUNT_B%}': actual_amount_b,
			'{%CURRENCY_B%}': offer_b.country.currency.iso,
			'{%EMAIL_B%}': offer_b.email,
			'{%INSTRUCTIONS_B%}': instructions_b,
			'{%TO_CHARITY_B%}': to_charity_b,
			'{%GIFT_AID_INSERT_B_TXT%}': gift_aid_insert_b_txt,
			'{%GIFT_AID_INSERT_B_HTML%}': gift_aid_insert_b_html,
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
			# this error is shown directly to the user, don't put any sensitive details in it!
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
			self._send_mail_about_approved_match(match, old_offer, new_offer)

	@ajax
	def decline_match(self, secret, feedback):
		match, old_offer, new_offer, my_offer, other_offer = self._get_match_and_offers(secret)

		if match is None:
			# this error is shown directly to the user, don't put any sensitive details in it!
			raise DonationException(
				util.Template('errors-and-warnings.json').json('match not found')
			)

		with self._database.connect() as db:
			query = '''
				do $$ begin
					IF NOT EXISTS (SELECT * FROM declined_matches WHERE new_offer_id=%(id_old)s AND old_offer_id=%(id_new)s) THEN
						INSERT INTO declined_matches (new_offer_id, old_offer_id)
						VALUES (%(id_old)s, %(id_new)s);
					END IF;
				end $$;
			'''
			db.write(query, id_old=old_offer.id, id_new=new_offer.id)
			match.delete(db)
			my_offer.suspend(db)
			eventlog.declined_match(db, match, my_offer, feedback)

			#TODO: needs args applied to a new offer rather than reconfirming old offer
			replacements = {
				'{%NAME%}': my_offer.name,
				'{%OFFER_SECRET%}': my_offer.secret,
			}
			self._mail.send(
				util.Template('email-subjects.json').json('match-decliner-email'),
				util.Template('match-decliner-email.txt').replace(replacements).content,
				html=util.Template('match-decliner-email.html').replace(replacements).content,
				to=my_offer.email
			)

			email_subject = 'match-declined-email'
			if other_offer == old_offer and match.old_agrees:
				email_subject = 'match-approved-declined-email'
			elif other_offer == new_offer and match.new_agrees:
				email_subject = 'match-approved-declined-email'

			#TODO: needs args applied to a new offer rather than reconfirming old offer
			replacements = {
				'{%NAME%}': other_offer.name,
				'{%OFFER_SECRET%}': other_offer.secret,
			}
			self._mail.send(
				util.Template('email-subjects.json').json(email_subject),
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
	def update_country(self, _, country_id, name, live_in_name, iso_name, currency_id, min_donation_amount, min_donation_currency_id, gift_aid):
		country = entities.Country.by_id(country_id)
		country.name = name
		country.live_in_name = live_in_name
		country.iso_name = iso_name
		country.currency_id = currency_id
		country.min_donation_amount = min_donation_amount
		country.min_donation_currency_id = min_donation_currency_id
		country.gift_aid = gift_aid
		with self._database.connect() as db:
			country.save(db)

	@admin_ajax
	def delete_country(self, _, country_id):
		with self._database.connect() as db:
			entities.Country.by_id(country_id).delete(db)

	@admin_ajax
	def create_charity_in_country(self, _, charity_id, country_id, instructions):
		with self._database.connect() as db:
			entities.CharityInCountry.create(db, charity_id, country_id, instructions)

	@admin_ajax
	def update_charity_in_country(self, _, charity_id, country_id, instructions):
		charity_in_country = entities.CharityInCountry.by_charity_and_country_id(charity_id, country_id)
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

	@admin_ajax
	def read_log_stats(self, _, min_timestamp, max_timestamp, offset, limit):
		approved = {}
		final = {
			'total_count': 0,
			'filtered_count': 0,
			'offset': offset,
			'limit': limit,
			'data': [],
		}
		finalData = []

		# get generated and accepted events
		events = self.read_log(_, min_timestamp, max_timestamp, [21, 22], offset, limit)

		with self._database.connect() as db:
			for event in events["data"]:
				if event["event_type"] == "match generated":
					# take the generated events as a base
					try:
						newOffer = entities.Offer.by_id(event["details"]["new_offer_id"])
						oldOffer = entities.Offer.by_id(event["details"]["old_offer_id"])
						newval, _ = self._get_actual_amounts(entities.Match.by_id(event["detail"]["match_id"]), newOffer, oldOffer)
						newval = newval * newOffer.country.gift_aid_multiplier
						event["value"] = self._currency.convert(newval, newOffer.country.currency.iso, "USD")
					except:
						event["value"] = "ERR"
					finalData.append(event)
				else:
					# record approved offers against their match id
					try:
						if event["details"]["match_id"] in approved:
							approved[event["details"]["match_id"]].append(event["details"]["offer_id"])
						else:
							approved[event["details"]["match_id"]] = [ event["details"]["offer_id"] ]
					except:
						pass

		final["total_count"] = len(finalData)

		# remove generated matches that were not approved by both sides
		idx = len(finalData) - 1
		while (idx > 0):
			rem = True
			try:
				match_id = finalData[idx]["details"]["match_id"]
				if (match_id in approved) and (finalData[idx]["details"]["new_offer_id"] in approved[match_id]) and (finalData[idx]["details"]["old_offer_id"] in approved[match_id]):
					rem = False
			except:
				pass

			if rem:
				del finalData[idx]
			idx -= 1

		final["filtered_count"] = len(finalData)
		final["data"] = finalData
		return final
			

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
				'amount_for_charity_localized': self._currency.convert(
					offer.amount * offer.country.gift_aid_multiplier,
					offer.country.currency.iso,
					admin_currency.iso),
				'min_amount_for_charity_localized': self._currency.convert(
					offer.min_amount * offer.country.gift_aid_multiplier,
					offer.country.currency.iso,
					admin_currency.iso),
				'currency_localized': admin_currency.iso,
				'offer_secret': offer.secret,
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
		my_actual_amount, _ = self._get_actual_amounts(entities.Match.by_secret(match_secret), my_offer, their_offer)

		replacements = {
			'{%YOUR_NAME%}': my_offer.name,
			'{%YOUR_CHARITY%}': my_offer.charity.name,
			'{%YOUR_AMOUNT%}': my_offer.amount,
			'{%YOUR_MIN_AMOUNT%}': my_offer.min_amount,
			'{%YOUR_ACTUAL_AMOUNT%}': my_actual_amount,
			'{%YOUR_CURRENCY%}': my_offer.country.currency.iso,
			'{%THEIR_CHARITY%}': their_offer.charity.name,
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
