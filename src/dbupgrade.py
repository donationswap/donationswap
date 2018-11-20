#!/usr/bin/env python3

import argparse
import glob
import os
import sys

import database

def _already_executed(db, filename):
	return db.read_one('''
		SELECT EXISTS (
			SELECT 1
			FROM dbupgrade
			WHERE script_name = %(name)s
		) AS exists
	''', name=filename)['exists']

def _upgrade_one(db, script, filename):
	try:
		print('Processing %s' % filename)
		db.execute_script(script)
		db.write('''
			INSERT INTO dbupgrade
			(script_name)
			VALUES
			(%(name)s);
		''', name=filename)
	except Exception as e: # pylint: disable=broad-except
		print('Error: %s' % e, file=sys.stderr)
		sys.exit(1)

def upgrade_database(name, sql_path):
	_database = database.Database("dbname=%s host=127.0.0.1 user=postgres password='databasepassword'" % name)

	print('Upgrading database "%s" with scripts from "%s".' % (name, os.path.abspath(sql_path)))
	with _database.connect() as db:
		pattern = os.path.join(sql_path, 'upgrades', '*.sql')
		for full_filename in sorted(glob.glob(pattern)):
			filename = os.path.basename(full_filename)
			if not _already_executed(db, filename):
				with open(full_filename, 'r') as f:
					script = f.read()
				_upgrade_one(db, script, filename)
	print('Done.')

def main():
	parser = argparse.ArgumentParser()
	parser.add_argument('dbname')
	parser.add_argument('-p', '--path', default='sql')
	args = parser.parse_args()

	upgrade_database(args.dbname, args.path)

if __name__ == '__main__':
	main()
