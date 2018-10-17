#!/usr/bin/env python3

import psycopg2 # `sudo pip3 install psycopg2-binary`
import psycopg2.extras

import config

class Database:
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

	def __init__(self):
		self._connection = psycopg2.connect(config.db_connection_string)
		self._cursor = self._connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
		self._written = False

	def __enter__(self):
		return self

	def __exit__(self, exc_type, exc_val, exc_tb):
		if self._written:
			if exc_type: # do not commit on exception
				self.rollback()
			else:
				self.commit()
		self.close()

	def commit(self):
		'''You probably won't need this, but it's there if needed.'''

		self._connection.commit()

	def rollback(self):
		'''You probably won't need this, but it's there if needed.'''

		self._connection.rollback()

	def close(self):
		'''You probably won't need this, but it's there if needed.'''

		self._cursor.close()
		self._connection.close()

	def _get_row_iterator(self):
		while True:
			row = self._cursor.fetchone()
			if row is None:
				break
			yield row

	def read(self, cmd, **args):
		self._cursor.execute(cmd, args)
		return self._get_row_iterator()

	def write(self, cmd, **args):
		self._cursor.execute(cmd, args)
		self._written = True

if __name__ == '__main__':
	with Database('marc') as db:
		for i in db.read('SELECT * FROM foobar WHERE id < %(max_id)s', max_id=4200):
			print(i['id'], i['name'])
