#!/usr/bin/env python3

'''
Wrapper for a 3rd party geoip tool that returns the country of an IP address.
It works for IPv4 and IPv6 addresses.

MaxMind GeoIP2 documentation:
https://geoip2.readthedocs.io/en/latest/

According to https://dev.maxmind.com/geoip/geoip2/geolite2/,
the database is updated on the first Tuesday of each month.

Download it from here:
https://geolite.maxmind.com/download/geoip/database/GeoLite2-Country.tar.gz

Note that it needs to be unpacked before it can be used:
wget https://geolite.maxmind.com/download/geoip/database/GeoLite2-Country.tar.gz -O foobar.tar.gz
tar -xvzf foobar.tar.gz

This text needs to be added to the UI to meet the licensing requirements:
This product includes GeoLite2 data created by MaxMind, available from
<a href="http://www.maxmind.com">http://www.maxmind.com</a>.
'''

import logging

import geoip2.database # `sudo pip3 install geoip2`

class GeoIpCountry: # pylint: disable=too-few-public-methods

	def __init__(self, filename):
		logging.info('Loading geoip data from "%s"...', filename)
		self._read = None

	def lookup(self, ip_address):
		try:
			if self._read is None:
				self._reader = geoip2.database.Reader(filename)
			match = self._reader.country(ip_address)
			return match.country.iso_code.lower()
		except geoip2.errors.AddressNotFoundError:
			return None
		except Exception: # pylint: disable=broad-except
			logging.error('Error looking up country by IP address "%s".', ip_address, exc_info=True)
			return None
