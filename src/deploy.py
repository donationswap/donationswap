#!/usr/bin/env python3

import argparse
import glob
import os
import shutil

FILE_LIST = [
	('backup.py', 0o555),
	('captcha.py', 0o444),
	('config.py', 0o444),
	('currency.py', 0o444),
	('database.py', 0o444),
	('donationswap.py', 0o444),
	('entities.py', 0o444),
	('eventlog.py', 0o444),
	('geoip.py', 0o444),
	('mail.py', 0o444),
	('main.py', 0o544),
	('matching', 0o777),
	('matching/*', 0o444),
	('matchmaker.py', 0o555),
	('util.py', 0o444),
	('data', 0o777),
	('data/*', 0o444),
	('log', 0o777),
	('static', 0o777),
	('static/*', 0o444),
	('templates', 0o777),
	('templates/*', 0o444),
]

def deploy(target):
	source = os.path.dirname(os.path.abspath(__file__))
	target = os.path.abspath(target)

	print('Deploying webserver')
	print('Source = %s' % source)
	print('Target = %s' % target)
	print()

	if os.path.exists(target) and os.path.samefile(source, target):
		print('Error: source == target.')
		return

	if not os.path.exists(target):
		print('Creating target directory.')
		os.mkdir(target)
		os.chmod(target, 0o777)

	for (pattern, mode) in FILE_LIST:
		for filename in glob.glob(os.path.join(source, pattern)):
			filename = filename[len(source)+1:] # remove path prefix
			s = os.path.join(source, filename)
			t = os.path.join(target, filename)
			if os.path.isfile(s):
				if os.path.exists(t):
					print('Replacing %s' % filename)
					os.chmod(t, 0o666)
					os.remove(t)
				else:
					print('Copying %s' % filename)
				shutil.copy(s, t)
				os.chmod(t, mode)
			elif os.path.isdir(s):
				if not os.path.exists(t):
					print('Creating %s' % filename)
					os.mkdir(t)
				os.chmod(t, mode)

	print('Done. Make sure app-config.json is good.')

if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument('path', help='where to deploy to')
	args = parser.parse_args()

	deploy(args.path)
