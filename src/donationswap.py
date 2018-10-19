#!/usr/bin/env python3

'''
This is the logic layer, where the rules of donation swapping
are implemented, without any reference to the web server.

Abstracting this out makes it easier to change to a different
web server in the future.
'''

import captcha
import config
import currency
import database
import geoip
import mail
import util

class Donationswap:

	def __init__(self):
		config.initialize('app-config.json')
		self._captcha = captcha.Captcha(config.captcha_secret)
		self._currency = currency.Currency(config.currency_cache, config.fixer_apikey)
		self._geoip = geoip.GeoIpCountry(config.geoip_datafile)
		self._mail = mail.Mail(config.email_user, config.email_password, config.email_smtp)

	@staticmethod
	def _get_countries():
		query = 'SELECT id, abbreviation, name, live_in_name, currency FROM countries ORDER BY name'
		with database.Database() as db:
			return [i for i in db.read(query)]

	@staticmethod
	def _get_charities():
		query = 'SELECT id, abbreviation, name FROM charities ORDER BY name'
		with database.Database() as db:
			return [i for i in db.read(query)]

	def get_home_page(self, ip_address):
		country = self._geoip.lookup(ip_address)

		pattern = '<option data="{currency}" {selected} value="{abbreviation}">{name}</option>'
		countries = [
			pattern.format(
				currency=i['currency'],
				abbreviation=i['abbreviation'],
				name=i['live_in_name'] or i['name'],
				selected='selected' if country == i['abbreviation'] else '',
			)
			for i in self._get_countries()
		]

		pattern = '<option value="{abbreviation}">{name}</option>'
		charities = [
			pattern.format(
				abbreviation=i['abbreviation'],
				name=i['name']
			)
			for i in self._get_charities()
		]

		tmp = util.Template('index.html')
		tmp.replace({
			'{%COUNTRIES%}': '\n\t\t\t'.join(countries),
			'{%CHARITIES%}': '\n\t\t\t'.join(charities),
		})

		return tmp.content

	def get_contact_page(self):
		return util.Template('contact.html').content

	def send_contact_message(self, ip_address, message, name=None, email=None):
		message = message.strip()
		if not message:
			return 'message is empty'

		tmp = util.Template('contact-email.txt')
		tmp.replace({
			'{%IP_ADDRESS%}': ip_address,
			'{%COUNTRY%}': self._geoip.lookup(ip_address),
			'{%NAME%}': name or 'n/a',
			'{%EMAIL%}': email or 'n/a',
			'{%MESSAGE%}': message,
		})

		success = self._mail.send(
			'Message for donationswap.eahub.org',
			tmp.content,
			to=config.contact_message_receivers.get('to', []),
			cc=config.contact_message_receivers.get('cc', []),
			bcc=config.contact_message_receivers.get('bcc', [])
		)

		if not success:
			return 'Something unexpected happened on our server. Your message could not be sent. Sorry.'

		return None

	def get_contact_success_page(self):
		return 'xxx'

	def get_contact_error_page(self, error, message=None, name=None, email=None):
		return error #xxx

	def get_start_page(self, ip_address, country=None, amount=None, charity=None):
		country = country or self._geoip.lookup(ip_address)
		amount = amount or 100
		charity = charity or 'amf'

		pattern = '<option data="{currency}" {selected} value="{abbreviation}">{name}</option>'
		countries = [
			pattern.format(
				currency=i['currency'],
				abbreviation=i['abbreviation'],
				name=util.html_escape(i['name']),
				selected='selected' if country == i['abbreviation'] else '',
			)
			for i in self._get_countries()
		]

		pattern = '<option {selected} value="{abbreviation}">{name}</option>'
		charities = [
			pattern.format(
				abbreviation=i['abbreviation'],
				name=util.html_escape(i['name']),
				selected='selected' if charity == i['abbreviation'] else '',
			)
			for i in self._get_charities()
		]

		tmp = util.Template('start.html')
		tmp.replace({
			'{%COUNTRIES%}': '\n\t\t\t\t\t\t'.join(countries),
			'{%AMOUNT%}': amount,
			'{%CHARITIES%}': '\n\t\t\t\t\t\t'.join(charities),
		})

		return tmp.content

	def create_post(self, ip_address, captcha_response, country, amount, charity, email):
		is_legit = self._captcha.is_legit(ip_address, captcha_response)

		if not is_legit:
			return None

		#xxx insert into database

		#xxx send email

		print(ip_address)
		print(captcha_response)
		print(country)
		print(amount)
		print(charity)
		print(email)

		#xxx return whether or not there are matches
