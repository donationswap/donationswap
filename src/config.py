#!/usr/bin/env python3

'''This is where "global" configuration variables live.'''

import json
import logging
import sys

def initialize(filename):
	logging.info('Loading configuration from "%s".', filename)

	with open(filename, 'r') as f:
		content = f.read()
	data = json.loads(content)

	module = sys.modules[__name__]

	for k, v in data.items():
		setattr(module, k, v)
