#!/usr/bin/env python3

'''This is where global variables go.'''

import json
import logging

db_connection_string = None
email_password = None
email_sender = None
email_user = None
geoip_datafile = None

def initialize(filename):
	logging.info('Loading configuration from "%s".', filename)

	with open(filename, 'r') as f:
		content = f.read()
	data = json.loads(content)

	global db_connection_string
	db_connection_string = data.get('db_connection_string', None)

	global email_password
	email_password = data.get('email_password', None)

	global email_sender
	email_sender = data.get('email_sender', None)

	global email_user
	email_user = data.get('email_user', None)

	global geoip_datafile
	geoip_datafile = data.get('geoip_datafile', None)
