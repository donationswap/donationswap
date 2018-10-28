#!/usr/bin/env python3

class Entities:

	def __init__(self, database):
		self._database = database

		#xxx clear self._countries and self._charities cache every once in a while

		query = '''SELECT * FROM countries ORDER BY name;'''
		with self._database.connect() as db:
			self._countries = [i for i in db.read(query)]

		query = '''SELECT * FROM charities ORDER BY name;'''
		with self._database.connect() as db:
			self._charities = [i for i in db.read(query)]

	@property
	def countries(self):
		return self._countries[:] # shallow copy

	def get_country_by_abbreviation(self, abbreviation):
		for i in self._countries:
			if i['abbreviation'] == abbreviation:
				return i
		return None

	@property
	def charities(self):
		return self._charities[:] # shallow copy

	def get_charity_by_abbreviation(self, abbreviation):
		for i in self._charities:
			if i['abbreviation'] == abbreviation:
				return i
		return None

	def insert_offer(self, email, secret, country, amount, charity, time_to_live):
		query = '''
			INSERT INTO offers
			(email, secret, country_id, amount, charity_id, expires_ts)
			VALUES
			(
				%(email)s,
				%(secret)s,
				(
					SELECT id
					FROM countries
					WHERE abbreviation = %(country)s
				),
				%(amount)s,
				(
					SELECT id
					FROM charities
					WHERE abbreviation = %(charity)s
				),
				now() + %(time_to_live)s
			);
		'''
		with self._database.connect() as db:
			db.write(query,
				email=email,
				secret=secret,
				country=country,
				amount=amount,
				charity=charity,
				time_to_live=time_to_live)

	def get_offer_by_id(self, offer_id):
		query = '''
			SELECT offers.*, charities.name AS charity, countries.abbreviation as country, countries.currency
			FROM offers
			JOIN charities ON offers.charity_id = charities.id
			JOIN countries ON offers.country_id = countries.id
			WHERE offers.id = %(id)s AND expires_ts > now();
		'''
		with self._database.connect() as db:
			return db.read_one(query, id=offer_id)

	def get_offer_by_secret(self, secret):
		query = '''
			SELECT offers.*, charities.name AS charity, countries.abbreviation as country, countries.currency
			FROM offers
			JOIN charities ON offers.charity_id = charities.id
			JOIN countries ON offers.country_id = countries.id
			WHERE secret = %(secret)s AND expires_ts > now();
		'''
		with self._database.connect() as db:
			return db.read_one(query, secret=secret)

	def confirm_offer(self, offer_id):
		query = '''
			UPDATE offers
			SET confirmed = true
			WHERE id = %(id)s;
		'''
		with self._database.connect() as db:
			db.write(query, id=offer_id)

	def delete_offer(self, secret):
		query = '''
			DELETE FROM offers
			WHERE secret = %(secret)s;
		'''
		with self._database.connect() as db:
			db.write(query, secret=secret)

	def insert_match(self, new_offer_id, old_offer_id, secret):
		query = '''
			INSERT INTO matches
			(secret, new_offer_id, old_offer_id)
			VALUES
			(%(s)s, %(noid)s, %(ooid)s);
		'''
		with self._database.connect() as db:
			db.write(query, s=secret, noid=new_offer_id, ooid=old_offer_id)

	def get_match_by_secret(self, secret):
		query = '''
			SELECT *
			FROM matches
			WHERE secret = %(secret)s;
		'''
		with self._database.connect() as db:
			return db.read_one(query, secret=secret)

	def _update_match_agree(self, match_id, column_name):
		query = '''
			UPDATE matches
			SET %s = true
			WHERE id = %%(id)s;
		''' % column_name
		with self._database.connect() as db:
			db.write(query, id=match_id)

	def update_match_agree_new(self, match_id):
		self._update_match_agree(match_id, 'new_agrees')

	def update_match_agree_old(self, match_id):
		self._update_match_agree(match_id, 'old_agrees')
