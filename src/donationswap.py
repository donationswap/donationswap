#!/usr/bin/env python3

'''
This is the logic layer, where the rules of donation swapping
are implemented, without any reference to the web server.

Abstracting this out makes it easier to change to a different
web server in the future.
'''

import logging

import config
import database
import geoip
import util

class Donationswap:

	def __init__(self):
		config.initialize('app-config.json')
		self._geoip = geoip.GeoIpCountry(config.geoip_datafile)

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

	def create_post(self):
		pass #xxx
