#!/usr/bin/env python3

'''
This program backs up the postgres database if necessary.

Don't use '.' as path, because it runs as the postgres user,
and '.' will point to the home directory of the postgres user,
which is /var/lib/postgres.
'''

import argparse
import datetime
import glob
import os
import subprocess

FILENAME_PATTERN = '????-??-??_??-??.%s.sql'

def _get_latest_backup_filename(path, db_name):
	pattern = os.path.join(path, FILENAME_PATTERN % db_name)
	names = glob.glob(pattern)
	names.sort()
	if names:
		return names[-1]
	return None

def _generate_backup_filename(path, db_name, now=None):
	if now is None:
		now = datetime.datetime.utcnow()
	timestamp = now.strftime('%Y-%m-%d_%H-%M')
	filename = '%s.%s.sql' % (timestamp, db_name)
	return os.path.join(path, filename)

def _pg_dump(db_name, filename):
	if os.geteuid() != 0:
		raise ValueError('You must be root do to this.')

	command = ' '.join([
		'pg_dump',
		db_name,
		'--data-only',
		'--file=%s' % filename,
		'--no-owner',
		'--column-inserts',
		'--quote-all-identifiers'
	])

	subprocess.run(
		[
			'su',
			'-',
			'postgres',
			'-c',
			command
		],
		check=True
	)

def _files_are_identical(filename_a, filename_b):
	if filename_a is None or not os.path.exists(filename_a):
		return False
	if filename_b is None or not os.path.exists(filename_b):
		return False

	size_a = os.path.getsize(filename_a)
	size_b = os.path.getsize(filename_b)
	if size_a != size_b:
		return False

	with open(filename_a, 'rb') as fa:
		with open(filename_b, 'rb') as fb:
			while True:
				chunk_a = fa.read(20*1024)
				chunk_b = fb.read(20*1024)
				if not chunk_a:
					return True
				if chunk_a != chunk_b:
					return False

def backup(path, db_name):
	previous_filename = _get_latest_backup_filename(path, db_name)
	filename = _generate_backup_filename(path, db_name)
	print('Backup of %s ' % filename, end='', flush=True)
	_pg_dump(db_name, filename)
	if _files_are_identical(filename, previous_filename):
		print('redundant.')
		os.remove(filename)
	else:
		print('done.')

def delete_old_backups(path, db_name):
	now = datetime.datetime.utcnow()
	oldest = now - datetime.timedelta(days=90)
	filename = _generate_backup_filename(path, db_name, now=oldest)
	for i in sorted(glob.glob(os.path.join(path, FILENAME_PATTERN % db_name))):
		if i < filename:
			print('Deleting %s' % i)
			os.remove(i)

def main():
	parser = argparse.ArgumentParser()
	parser.add_argument('path')
	parser.add_argument('db_names', nargs='+')
	args = parser.parse_args()
	for i in args.db_names:
		backup(args.path, i)
		delete_old_backups(args.path, i)

if __name__ == '__main__':
	main()
