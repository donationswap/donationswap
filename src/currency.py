#!/usr/bin/env python3

import json
import logging
import os
import threading
import time
import urllib.request

class Currency:

	def __init__(self, cache_filename, secret):
		self._cache_filename = cache_filename
		self._secret = secret
		self._data = None
		self._file_lock = threading.Lock()

	def _read_cache(self):
		if os.path.isfile(self._cache_filename):
			with self._file_lock:
				with open(self._cache_filename, 'r') as f:
					content = f.read()
			self._data = json.loads(content)

	def _write_cache(self):
		content = json.dumps(self._data)
		with self._file_lock:
			with open(self._cache_filename, 'w') as f:
				f.write(content)

	def _read_live(self):
		logging.info('Downloading currency exchange rates from fixer.io...')
		# https is a premium feature
		url = 'http://data.fixer.io/api/latest?access_key=%s' % self._secret
		with urllib.request.urlopen(url) as f:
			content = f.read()
		data = json.loads(content.decode('utf-8'))
		if data.get('success', False):
			self._data = data
		else:
			logging.error('Failed to download currency exchange rates from fixer.io: %s', content, exc_info=True)

	def _get_data(self):
		if self._data is None:
			self._read_cache()
		age = time.time() - (self._data or {}).get('timestamp', 0)
		if self._data is None or age > 60*60:
			self._read_live()
			self._write_cache()
		return self._data

	def get_supported_currencies(self):
		return list(self._data['rates'].keys())

	def convert(self, amount, from_currency, to_currency):
		data = self._get_data()

		if from_currency != data['base']: # convert to base currency
			amount /= data['rates'].get(from_currency, 1)

		amount *= data['rates'].get(to_currency, 1)

		return int(amount)
