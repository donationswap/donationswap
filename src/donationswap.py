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

	def get_home_page(self, ip_address):
		country = self._geoip.lookup(ip_address)

		query = 'SELECT abbreviation, name, currency FROM countries ORDER BY name'
		pattern = '<option data="{currency}" {selected} value="{abbreviation}">{name}</option>'
		with database.Database() as db:
			countries = [
				pattern.format(
					currency=i['currency'],
					abbreviation=i['abbreviation'],
					name=i['name'],
					selected='selected' if country == i['abbreviation'] else '',
				)
				for i in db.read(query)
			]

		tmp = util.Template('index.html')
		tmp.replace({
			'{%COUNTRIES%}': '\n\t\t\t'.join(countries),
		})

		return tmp.content

	def get_start_page(self, ip_address, country=None, amount=None, charity=None):
		tmp = util.Template('initial_form_response.html')
		tmp.replace({
			'{%COUNTRY%}': country,
			'{%AMOUNT%}': amount,
			'{%CHARITY%}': charity,
		})
		return tmp.content
