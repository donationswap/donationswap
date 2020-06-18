#!/usr/bin/env python3

'''
xxx do not hardcode paths
'''

import datetime
import glob
import os
import random
import re
import subprocess
import sys

import config
import database
import entities
import geoip
import mail

CONFIG_FILENAME = '/srv/web/app-config.json'

class PrintReceiver: # pylint: disable=too-few-public-methods

	def __init__(self, target):
		self._target = target

	def write(self, msg):
		self._target.append(msg)

def _print_file_info(filename):
	print('"%s"' % os.path.basename(filename), end=' ')
	if os.path.isfile(filename):
		print('%s bytes' % os.path.getsize(filename), end=', ')
		ctime = datetime.datetime.fromtimestamp(os.path.getctime(filename))
		print('ctime: %s' % ctime.strftime('%Y-%m-%d %H:%M:%S'), end=', ')
		mtime = datetime.datetime.fromtimestamp(os.path.getmtime(filename))
		print('mtime: %s' % mtime.strftime('%Y-%m-%d %H:%M:%S'), end=', ')
		print('age: %s' % (datetime.datetime.utcnow() - min(ctime, mtime)))
	else:
		print('MISSING.')

def _send_mail(msg, to):
	cfg = config.Config(CONFIG_FILENAME)
    m = mail.Mail(cfg.watchdog_email_user, cfg.watchdog_email_password,
                  cfg.watchdog_email_smtp, cfg.watchdog_email_sender_name)
	m.send('Donation Swap Watchdog', msg, to=to, send_async=False)

def check_backups():
	filenames = sorted(glob.glob('/srv/backup/*'))
	print('total file count: %s' % len(filenames))

	print('oldest 5:')
	for i in filenames[:5]:
		_print_file_info(i)

	print('newest 5:')
	for i in filenames[-5:]:
		_print_file_info(i)

def check_certificate_expiration():
	command = 'echo | openssl s_client -connect donationswap.eahub.org:443 2> /dev/null | openssl x509 -noout -enddate'
	proc = subprocess.run(command, shell=True, stdout=subprocess.PIPE)
	print(proc.stdout.decode('utf-8'))

def check_disk_space():
	command = 'du -hs /srv/*'
	print(command)
	proc = subprocess.run(command, shell=True, stdout=subprocess.PIPE, timeout=5)
	print(proc.stdout.decode('utf-8'))

	command = 'df -h'
	print(command)
	proc = subprocess.run(command, shell=True, stdout=subprocess.PIPE, timeout=5)
	print(proc.stdout.decode('utf-8'))

def check_entities():
	cfg = config.Config(CONFIG_FILENAME)
	dat = database.Database(cfg.db_connection_string)
	with dat.connect() as db:
		entities.load(db)
		print('Charity Categories: %s' % len(entities.CharityCategory.get_all()))
		print('Charities: %s' % len(entities.Charity.get_all()))
		print('Countries: %s' % len(entities.Country.get_all()))
		print('Charities In Countries: %s' % len(entities.CharityInCountry.get_all()))
		print('Offers: %s' % len(entities.Offer.get_all()))
		print('Unmatched offers: %s' % len(entities.Offer.get_unmatched_offers(db)))
		print('Matches: %s' % len(entities.Match.get_all()))

def check_exchange_rate():
	_print_file_info('/srv/web/data/currency.json')

def check_geoip():

	def _create_random_ip_address():
		return '%s.%s.%s.%s' % (
			random.randrange(1, 256),
			random.randrange(0, 256),
			random.randrange(0, 256),
			random.randrange(0, 256),
		)

	FILENAME = '/srv/web/data/GeoLite2-Country.mmdb'

	_print_file_info(FILENAME)
	print('Random samples:')
	geo = geoip.GeoIpCountry(FILENAME)
	for _ in range(5):
		address = _create_random_ip_address()
		iso = geo.lookup(address)
		print('%s: %s' % (address, iso))

def check_logfiles():
	for i in sorted(glob.glob('/srv/web/log/*')):
		_print_file_info(i)

def check_website_visits():
	PATTERN = r'.* Website visitor from .. with IP address "(?P<ip>.+)"'
	visits_by_date = {}

	for filename in glob.glob('/srv/web/log/*'):
		with open(filename, 'r') as f:
			for line in f:
				match = re.match(PATTERN, line)
				if not match:
					continue
				ip = match.group('ip')
				date = line[:10]
				visits_by_date.setdefault(date, set())
				visits_by_date[date].add(ip)

	for date, count in sorted(visits_by_date.items()):
		print('%s: %s' % (date, len(count)))

def _execute_one(fn):
	result = [
		fn.__name__[len('check_'):].upper().replace('_', ' '),
	]

	sys.stdout = PrintReceiver(result)

	start_time = datetime.datetime.utcnow()

	try:
		fn()
	except Exception as e: # pylint: disable=broad-except
		result.append('%s\n' % ('*' * 40))
		result.append('ERROR\n')
		result.append('%s\n' % e)
		result.append('%s\n' % ('*' * 40))

	end_time = datetime.datetime.utcnow()
	result[0] += ' (%s)\n' % (end_time - start_time)

	sys.stdout = sys.__stdout__

	return ''.join(result)

def main(enable_email=True):
	CHECKS = [
		check_backups,
		check_certificate_expiration,
		check_disk_space,
		check_entities,
		check_exchange_rate,
		check_geoip,
		check_logfiles,
		check_website_visits,
	]

	result = []
	for check in CHECKS:
		result.append(_execute_one(check))

	result = '\n'.join(result)

	if enable_email:
		cfg = config.Config(CONFIG_FILENAME)
		_send_mail(result, cfg.watchdog_receivers)
	else:
		print(result)

if __name__ == '__main__':
	main()
