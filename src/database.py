#!/usr/bin/env python3

import logging

import psycopg2 # `sudo pip3 install psycopg2-binary`
import psycopg2.extras


class Database: # pylint: disable=too-few-public-methods
	'''
	Database adapter class.
	Ideally this will be used as a contex manager,
	i.e. with the "with" keyword:

	`with Database('dbname') as db:
		for i in db.read('SELECT * FROM table'):
			print(i['id'], i['name'])`

	Configuration files for postgres daemon:
	/etc/postgresql/9.6/main/pg_hba.conf
	/etc/postgresql/9.6/main/postgresql.conf

	How to change the default user's password:
	ALTER USER postgres PASSWORD 'databasepassword';

	Documentation of the psycopg python module:
	http://initd.org/psycopg/docs/
	'''

	def __init__(self, connection_string):
		self._connection_string = connection_string

	def connect(self):
		return Connection(self._connection_string)

class Connection:

	def __init__(self, connection_string):
		self._connection = psycopg2.connect(connection_string)
		self._cursor = self._connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
		self.written = False

	def __enter__(self):
		return self

	def __exit__(self, exc_type, exc_val, exc_tb):
		if self.written:
			if exc_type: # do not commit on exception
				logging.error('exception during transaction', exc_info=True)
				self._connection.rollback()
			else:
				self._connection.commit()
		self._cursor.close()
		self._connection.close()

	def _get_row_iterator(self):
		while True:
			row = self._cursor.fetchone()
			if row is None:
				break
			yield row

	def read(self, query, **args):
		self._cursor.execute(query, args)
		return self._get_row_iterator()

	def read_one(self, query, **args):
		for i in self.read(query, **args):
			return i

	def write(self, cmd, **args):
		self._cursor.execute(cmd, args)
		self.written = True

	def write_read_one(self, query, **args):
		self.written = True
		return self.read_one(query, **args)

	def execute_script(self, script):
		self._cursor.execute(script)

	def escape(self, query, **args):
		return self._cursor.mogrify(query, args).decode('utf-8')
