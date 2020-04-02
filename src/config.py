#!/usr/bin/env python3

import json
import logging

class Config:
	# pylint: disable=too-few-public-methods
	# pylint: disable=too-many-instance-attributes
	'''
	This is where "global" configuration variables live.

	A variable goes here if
	* the value should not be checked in (like passwords), or
	* developers/testers may want to use a different value (like data paths)
	'''

	def __init__(self, filename):
		logging.info('Loading configuration from "%s".', filename)

		with open(filename, 'r') as f:
			content = f.read()
		data = json.loads(content)

		self.captcha_secret = data['captcha_secret']
		self.captcha_site_key = data['captcha_site_key']
		self.contact_message_receivers = data['contact_message_receivers']
		self.cookie_key = data['cookie_key']
		self.currency_cache = data['currency_cache']
		self.db_connection_string = data['db_connection_string']
		self.email_password = data['email_password']
		self.email_sender_name = data['email_sender_name']
		self.email_smtp = data['email_smtp']
		self.email_user = data['email_user']
		self.fixer_apikey = data['fixer_apikey']
		self.geoip_datafile = data['geoip_datafile']
		self.watchdog_receivers = data['watchdog_receivers']

		# could just do this, but explicit is better than implicit
		#for k, v in data.items():
		#	setattr(self, k, v)
