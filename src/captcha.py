#!/usr/bin/env python3

import json
import urllib.parse
import urllib.request

class Captcha: # pylint: disable=too-few-public-methods

	def __init__(self, secret):
		self._secret = secret

	def is_legit(self, ip_address, captcha_response):
		args = {
			'remoteip': ip_address, # optional (but probably useful)
			'response': captcha_response,
			'secret': self._secret,
		}
		request = urllib.request.Request('https://www.google.com/recaptcha/api/siteverify', urllib.parse.urlencode(args).encode())
		response = urllib.request.urlopen(request).read().decode()
		data = json.loads(response)
		return data['success']
