#!/usr/bin/env python3

'''
This is the logic layer, where the rules of donation swapping
are implemented, without any reference to the web server.

Abstracting this out makes it easier to change to a different
web server in the future.

Dependency structure:

.----------------------------------------------------------------------------------------------.
| main                                                                                         |       web layer
'----------------------------------------------------------------------------------------------'
                .------------------------------------------------------------------------------.
                | donationswap                                                                 |       "business logic"
                '------------------------------------------------------------------------------'
                                                                       .-----------------------------.
                                                                       | matchmaker (transparent)    | (Conway's law)
                                                                       '-----------------------------'
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
import logging
import os
import re
import struct
import time

import captcha
import config
import currency
import database
import entities
import geoip
import mail
import matchmaker
import util

OFFER_TTL_ONE_WEEK = 0
OFFER_TTL_ONE_MONTH = 1
OFFER_TTL_THREE_MONTHS = 2

def ajax(f):
	f.allow_ajax = True
	return f

#xxx commit code (with deploy script)

#xxx enter charities into database

#xxx add name to offer

#xxx write up workflow for Catherine

#xxx custom validation
#xxx minimum donation amount of 50 Euros (or equivalent),
#xxx except for Ireland, where it's 250 Euros.

#xxx expiration date input field

#xxx delete expired offers that aren't part of a match
#xxx delete unapproved matches after... dunno... a week?

#xxx a donation offer is pointless if
#    - it is to the only tax-deductible charity in the country OR
#    - it is to a charity that is tax-decuctible everywhere

class Donationswap:

	def __init__(self, config_path):
		self._config = config.Config(config_path)

		self._database = database.Database(self._config.db_connection_string)

		self._captcha = captcha.Captcha(self._config.captcha_secret)
		self._entities = entities.Entities(self._database)
		self._currency = currency.Currency(self._config.currency_cache, self._config.fixer_apikey)
		self._geoip = geoip.GeoIpCountry(self._config.geoip_datafile)
		self._mail = mail.Mail(self._config.email_user, self._config.email_password, self._config.email_smtp, self._config.email_sender_name)
		self._matchmaker = matchmaker.Matchmaker(self._database, self._currency)

		self._ip_address = None

	@staticmethod
	def _create_secret():
		timestamp_bytes = struct.pack('!d', time.time())
		random_bytes = os.urandom(10)
		return base64.b64encode(timestamp_bytes + random_bytes).decode('utf-8')

	def _send_mail_about_match(self, my_offer, their_offer, match_secret):
		my_country = self._entities.get_country_by_abbreviation(my_offer['country'])
		their_country = self._entities.get_country_by_abbreviation(their_offer['country'])

		replacements = {
			'{%YOUR_COUNTRY%}': my_country['name'],
			'{%YOUR_CHARITY%}': self._entities.get_charity_by_abbreviation(my_offer['charity']),
			'{%YOUR_AMOUNT%}': my_offer['amount'],
			'{%YOUR_CURRENCY%}': my_country['currency'],
			'{%THEIR_COUNTRY%}': their_country['name'],
			'{%THEIR_CHARITY%}': self._entities.get_charity_by_abbreviation(their_offer['charity']),
			'{%THEIR_AMOUNT%}': their_offer['amount'],
			'{%THEIR_CURRENCY%}': their_country['currency'],
			'{%THEIR_AMOUNT_CONVERTED%}': self._currency.convert(their_offer['amount'], their_country['currency'], my_country['currency']),
			'{%SECRET%}': '%s%s' % (my_offer['secret'], match_secret),
			# Do NOT put their email address here.
			# Wait until both parties approved the match.
		}
		self._mail.send(
			'We may have found a matching donation for you',
			util.Template('match-suggested-email.txt').replace(replacements).content,
			html=util.Template('match-suggested-email.html').replace(replacements).content,
			to=my_offer['email']
		)

	def _send_mail_about_deal(self, my_offer, their_offer):
		my_country = self._entities.get_country_by_abbreviation(my_offer['country'])
		their_country = self._entities.get_country_by_abbreviation(their_offer['country'])

		replacements = {
			'{%YOUR_COUNTRY%}': my_country['name'],
			'{%YOUR_CHARITY%}': self._entities.get_charity_by_abbreviation(my_offer['charity']),
			'{%YOUR_AMOUNT%}': my_offer['amount'],
			'{%YOUR_CURRENCY%}': my_country['currency'],
			'{%THEIR_COUNTRY%}': their_country['name'],
			'{%THEIR_CHARITY%}': self._entities.get_charity_by_abbreviation(their_offer['charity']),
			'{%THEIR_AMOUNT%}': their_offer['amount'],
			'{%THEIR_CURRENCY%}': their_country['currency'],
			'{%THEIR_AMOUNT_CONVERTED%}': self._currency.convert(their_offer['amount'], their_country['currency'], my_country['currency']),
			# This is where we include the email address
			'{%THEIR_EMAIL%}': their_offer['email'],
		}
		self._mail.send(
			'We may have found a matching donation for you',
			util.Template('match-approved-email.txt').replace(replacements).content,
			html=util.Template('match-approved-email.html').replace(replacements).content,
			to=my_offer['email']
		)

	def _find_match_for_offer(self, offer_id):
		matching_offer_id = self._matchmaker.find_match(offer_id)

		if matching_offer_id is None:
			return None

		match_secret = self._create_secret()

		self._entities.insert_match(
			new_offer_id=offer_id,
			old_offer_id=matching_offer_id,
			secret=match_secret
		)

		new_offer = self._entities.get_offer_by_id(offer_id)
		old_offer = self._entities.get_offer_by_id(matching_offer_id)

		self._send_mail_about_match(old_offer, new_offer, match_secret)
		self._send_mail_about_match(new_offer, old_offer, match_secret)

		return match_secret

	def _get_match_and_offers(self, secret):
		if len(secret) != 48:
			return None, None, None # invalid secret

		offer_secret = secret[:24]
		match_secret = secret[24:]

		match = self._entities.get_match_by_secret(match_secret)
		if match is None:
			return None, None, None # match not found

		new_offer = self._entities.get_offer_by_id(match['new_offer_id'])
		old_offer = self._entities.get_offer_by_id(match['old_offer_id'])

		if new_offer['secret'] == offer_secret:
			my_offer = new_offer
			their_offer = old_offer
		elif old_offer['secret'] == offer_secret:
			my_offer = old_offer
			their_offer = new_offer
		else:
			return None, None, None # offer not found

		return match, old_offer, new_offer, my_offer, their_offer

	def run_ajax(self, command, ip_address, args):
		method = getattr(self, command, None)
		if method is None:
			return None # method does not exist
		if not getattr(method, 'allow_ajax', False):
			return None # ajax not allowed

		self._ip_address = ip_address

		try:
			return method(**args)
		except Exception: # pylint: disable=broad-except
			logging.error('Ajax Error', exc_info=True)
			raise

	@staticmethod
	def get_page(name):
		return util.Template(name).content

	@ajax
	def get_info(self):
		client_country = self._geoip.lookup(self._ip_address)

		logging.info('Website visitor from %s with IP address "%s".', client_country, self._ip_address)

		return {
			'charities': [
				{
					'name': i['name'],
					'abbreviation': i['abbreviation'],
				}
				for i in self._entities.charities
			],
			'client_country': client_country,
			'countries': [
				{
					'currency': i['currency'],
					'abbreviation': i['abbreviation'],
					'live_in_name': i['live_in_name'] or i['name'],
					'name': i['name']
				}
				for i in self._entities.countries
			],
		}

	@ajax
	def send_contact_message(self, captcha_response, message, name=None, email=None):
		is_legit = self._captcha.is_legit(self._ip_address, captcha_response)

		if not is_legit:
			raise ValueError('bad captcha response')

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

	@ajax
	def create_offer(self, captcha_response, country, amount, charity, email, time_to_live):
		# validate
		is_legit = self._captcha.is_legit(self._ip_address, captcha_response)

		if not is_legit:
			raise ValueError('bad captcha response')

		if self._entities.get_country_by_abbreviation(country) is None:
			raise ValueError('country not found')

		amount = int(amount)

		if amount < 0:
			raise ValueError('negative amount')

		if self._entities.get_charity_by_abbreviation(charity) is None:
			raise ValueError('charity not found')

		email = email.strip()
		if not re.fullmatch(r'.+?@.+\..+', email):
			raise ValueError('bad email address')

		time_to_live = int(time_to_live)

		if 0 <= time_to_live <= 2:
			time_to_live = [
				'1 week',
				'1 month',
				'3 months',
			][time_to_live]
		else:
			raise ValueError('bad ttl')

		secret = self._create_secret()

		self._entities.insert_offer(email, secret, country, amount, charity, time_to_live)

		# send email
		replacements = {
			'{%URL%}': 'https://donationswap.eahub.org/offer/#%s' % secret,
			'{%CHARITY%}': self._entities.get_charity_by_abbreviation(charity)['name'],
			'{%CURRENCY%}': self._entities.get_country_by_abbreviation(country)['currency'],
			'{%AMOUNT%}': amount,
		}
		self._mail.send(
			'Please confirm your donation offer',
			util.Template('new-post-email.txt').replace(replacements).content,
			html=util.Template('new-post-email.html').replace(replacements).content,
			to=email
		)

		# Do NOT return the secret here.
		# We've sent an email to verify the email address,
		# and email should be the only way to receive the secret.
		return None

	@ajax
	def confirm_offer(self, secret):
		offer = self._entities.get_offer_by_secret(secret)
		if offer is None:
			return None

		# caller knows the secret (which we emailed)
		# => caller received email
		# => email address is valid
		# => offer is valid
		# => mark it as confirmed, and try to find a match for it.
		if not offer['confirmed']:
			offer_id = offer['id']
			self._entities.confirm_offer(offer_id)
			match_secret = self._find_match_for_offer(offer_id)
		else:
			match_secret = None

		return {
			'was_confirmed': offer['confirmed'],
			'currency': offer['currency'],
			'amount': offer['amount'],
			'charity': offer['charity'],
			'created_ts': offer['created_ts'].isoformat(' '),
			'expires_ts': offer['expires_ts'].isoformat(' '),
			'match_secret': match_secret,
		}

	@ajax
	def delete_offer(self, secret):
		self._entities.delete_offer(secret)

	@ajax
	def get_match(self, secret):
		_, _, _, my_offer, their_offer = self._get_match_and_offers(secret)
		if my_offer is None or their_offer is None:
			return None

		my_country = self._entities.get_country_by_abbreviation(my_offer['country'])
		their_country = self._entities.get_country_by_abbreviation(their_offer['country'])

		return {
			'my_country': my_country['name'],
			'my_charity': my_offer['charity'],
			'my_amount': my_offer['amount'],
			'my_currency': my_country['currency'],
			'their_country': their_country['name'],
			'their_charity': their_offer['charity'],
			'their_amount': their_offer['amount'],
			'their_currency': their_country['currency'],
			'their_amount_converted': self._currency.convert(their_offer['amount'], their_country['currency'], my_country['currency']),
			# Do NOT put their email address here.
			# Wait until both parties approved the match.
		}

	@ajax
	def approve_match(self, secret):
		match, old_offer, new_offer, my_offer, _ = self._get_match_and_offers(secret)

		if my_offer == old_offer:
			match['old_agrees'] = True
			self._entities.update_match_agree_old(match['id'])
		elif my_offer == new_offer:
			match['new_agrees'] = True
			self._entities.update_match_agree_new(match['id'])

		if match['old_agrees'] and match['new_agrees']:
			#xxx send only one email, but to both
			self._send_mail_about_deal(old_offer, new_offer)
			self._send_mail_about_deal(new_offer, old_offer)

	@ajax
	def decline_match(self, secret, reason):
		pass #xxx
