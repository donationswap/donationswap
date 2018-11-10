#!/usr/bin/env python3

import eventlog

#xxx use entities instead of plain SQL

class Admin:

	def __init__(self, database):
		self._database = database

	def read_all(self):
		return {
			'currencies': self.read_currencies(),
			'charity_categories': self.read_charity_categories(),
			'charities': self.read_charities(),
			'countries': self.read_countries(),
			'charities_in_countries': self.read_charities_in_countries(),
		}

	# There is no create, update, or delete for this one on purpose.
	# All values are constants, because those are the exact
	# currency that our 3rd party currency library supports.
	def read_currencies(self):
		query = '''
			SELECT *
			FROM currencies
			ORDER BY iso;'''
		with self._database.connect() as db:
			return [
				{
					'id': i['id'],
					'iso': i['iso'],
					'name': i['name'],
				}
				for i in db.read(query)
			]

	def create_charity_category(self, name):
		query = '''
			INSERT INTO charity_categories (name)
			VALUES (%(name)s);'''
		with self._database.connect() as db:
			db.write(query, name=name)

	def read_charity_categories(self):
		query = '''
			SELECT *
			FROM charity_categories
			ORDER BY name;'''
		with self._database.connect() as db:
			return [
				{
					'id': i['id'],
					'name': i['name'],
				}
				for i in db.read(query)
			]

	def update_charity_category(self, id, name):
		query = '''
			UPDATE charity_categories
			SET name = %(name)s
			WHERE id = %(id)s;'''
		with self._database.connect() as db:
			db.write(query, id=id, name=name)

	def delete_charity_category(self, id):
		query = '''
			DELETE FROM charity_categories
			WHERE id = %(id)s;'''
		with self._database.connect() as db:
			db.write(query, id=id)

	def create_charity(self, name, category_id):
		query = '''
			INSERT INTO charities (name, category_id)
			VALUES (%(name)s, %(category_id)s);'''
		with self._database.connect() as db:
			db.write(query, name=name, category_id=category_id)

	def read_charities(self):
		query = '''
			SELECT *
			FROM charities
			ORDER BY name;'''
		with self._database.connect() as db:
			return [
				{
					'id': i['id'],
					'name': i['name'],
					'category_id': i['category_id'],
				}
				for i in db.read(query)
			]

	def update_charity(self, id, name, category_id):
		query = '''
			UPDATE charities
			SET name = %(name)s, category_id = %(category_id)s
			WHERE id = %(id)s;'''
		with self._database.connect() as db:
			db.write(query, id=id, name=name, category_id=category_id)

	def delete_charity(self, id):
		query = '''
			DELETE FROM charities
			WHERE id = %(id)s;'''
		with self._database.connect() as db:
			db.write(query, id=id)

	def create_country(self, name, live_in_name, iso_name, currency_id, min_donation_amount, min_donation_currency_id):
		query = '''
			INSERT INTO countries (name, live_in_name, iso_name, currency_id, min_donation_amount, min_donation_currency_id)
			VALUES (%(name)s, %(live_in_name)s, %(iso_name)s, %(currency_id)s, %(min_donation_amount)s, %(min_donation_currency_id)s);'''
		with self._database.connect() as db:
			db.write(query, name=name, live_in_name=live_in_name, iso_name=iso_name, currency_id=currency_id, min_donation_amount=min_donation_amount, min_donation_currency_id=min_donation_currency_id)

	def read_countries(self):
		query = '''
			SELECT *
			FROM countries
			ORDER BY name;'''
		with self._database.connect() as db:
			return [
				{
					'id': i['id'],
					'name': i['name'],
					'live_in_name': i['live_in_name'],
					'iso_name': i['iso_name'],
					'currency_id': i['currency_id'],
					'min_donation_amount': i['min_donation_amount'],
					'min_donation_currency_id': i['min_donation_currency_id'],
				}
				for i in db.read(query)
			]

	def update_country(self, id, name, live_in_name, iso_name, currency_id, min_donation_amount, min_donation_currency_id):
		query = '''
			UPDATE countries
			SET name = %(name)s, live_in_name = %(live_in_name)s, iso_name = %(iso_name)s, currency_id = %(currency_id)s, min_donation_amount = %(min_donation_amount)s, min_donation_currency_id = %(min_donation_currency_id)s
			WHERE id = %(id)s;'''
		with self._database.connect() as db:
			db.write(query, id=id, name=name, live_in_name=live_in_name, iso_name=iso_name, currency_id=currency_id, min_donation_amount=min_donation_amount, min_donation_currency_id=min_donation_currency_id)

	def delete_country(self, id):
		query = '''
			DELETE FROM countries
			WHERE id = %(id)s;'''
		with self._database.connect() as db:
			db.write(query, id=id)

	def create_charity_in_country(self, charity_id, country_id, tax_factor, instructions):
		query = '''
			INSERT INTO charities_in_countries (charity_id, country_id, tax_factor, instructions)
			VALUES (%(charity_id)s, %(country_id)s, %(tax_factor)s, %(instructions)s);'''
		with self._database.connect() as db:
			db.write(query, charity_id=charity_id, country_id=country_id, tax_factor=tax_factor, instructions=instructions)

	def read_charities_in_countries(self):
		query = '''
			SELECT *
			FROM charities_in_countries;'''
		with self._database.connect() as db:
			return [
				{
					'charity_id': i['charity_id'],
					'country_id': i['country_id'],
					'tax_factor': i['tax_factor'],
					'instructions': i['instructions'],
				}
				for i in db.read(query)
			]

	def update_charity_in_country(self, charity_id, country_id, tax_factor, instructions):
		query = '''
			UPDATE charities_in_countries
			SET tax_factor = %(tax_factor)s, instructions = %(instructions)s
			WHERE charity_id = %(charity_id)s AND country_id = %(country_id)s;'''
		with self._database.connect() as db:
			db.write(query, charity_id=charity_id, country_id=country_id, tax_factor=tax_factor, instructions=instructions)

	def delete_charity_in_country(self, charity_id, country_id):
		query = '''
			DELETE FROM charities_in_countries
			WHERE charity_id = %(charity_id)s AND country_id = %(country_id)s;'''
		with self._database.connect() as db:
			db.write(query, charity_id=charity_id, country_id=country_id)

	def read_log(self, min_timestamp, max_timestamp, event_types, offset, limit):
		with self._database.connect() as db:
			events = eventlog.get_events(
				db,
				min_timestamp=min_timestamp,
				max_timestamp=max_timestamp,
				event_types=event_types,
				offset=offset,
				limit=limit,
			)
		return events

	def get_unmatched_offers(self):
		'''Returns all offers that are
		* not matched and
		* not expired and
		* confirmed
		'''

		query = '''
			SELECT
				offer.id,
				country.name AS country,
				offer.amount,
				offer.min_amount,
				currency.iso AS currency,
				charity.name AS charity,
				offer.expires_ts,
				offer.email
			FROM offers offer
			JOIN countries country ON offer.country_id = country.id
			JOIN currencies currency ON country.currency_id = currency.id
			JOIN charities charity ON offer.charity_id = charity.id
			WHERE
				offer.confirmed
				AND offer.expires_ts > now()
				AND offer.id NOT IN (SELECT old_offer_id FROM matches)
				AND offer.id NOT IN (SELECT new_offer_id FROM matches)
			ORDER BY country ASC, charity ASC, expires_ts ASC
		'''
		with self._database.connect() as db:
			return [
				{
					'id': i['id'],
					'country': i['country'],
					'amount': i['amount'],
					'min_amount': i['min_amount'],
					'currency': i['currency'],
					'charity': i['charity'],
					'expires_ts': i['expires_ts'].strftime('%Y-%m-%d %H:%M:%S'),
					'email': i['email'],
				}
				for i in db.read(query)
			]
