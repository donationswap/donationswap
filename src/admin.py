#!/usr/bin/env python3

from passlib.apps import custom_app_context as pwd_context # `sudo pip3 install passlib`

import donationswap
import eventlog

#xxx use entities instead of plain SQL

class Admin: # pylint: disable=too-many-public-methods

	def __init__(self, database):
		self._database = database
		self.user = None

	def _assert_user(self):
		if self.user is None:
			raise ValueError('Must be logged in.')

	def login(self, email, password):
		with self._database.connect() as db:
			query = '''
				SELECT password_hash
				FROM admins
				WHERE email = %(email)s;
			'''
			row = db.read_one(query, email=email)
			if row is None:
				password_hash = None
			else:
				password_hash = row['password_hash']

			# We run this even if password_hash is None, because
			# otherwise "user does not exist" would return MUCH
			# faster than "password is wrong", which is bad security.
			success = pwd_context.verify(password, password_hash)

			if not success:
				raise ValueError('User not found or wrong password.')

			secret = donationswap.create_secret()

			query = '''
				UPDATE admins
				SET secret=%(secret)s, last_login_ts=now()
				WHERE email=%(email)s;
			'''
			db.write(query, email=email, secret=secret)

			return secret

	def logout(self):
		self._assert_user()

		with self._database.connect() as db:
			query = '''
				UPDATE admins
				SET secret=null
				WHERE id = %(admin_id)s;
			'''
			db.write(query, admin_id=self.user['id'])

	def change_password(self, old_password, new_password):
		self._assert_user()

		with self._database.connect() as db:
			query = '''
				SELECT password_hash
				FROM admins
				WHERE id = %(admin_id)s;
			'''
			password_hash = db.read_one(query, admin_id=self.user['id'])['password_hash']
			success = pwd_context.verify(old_password, password_hash)

			if not success:
				raise ValueError('Current password is incorrect.')

			password_hash = pwd_context.encrypt(new_password)
			query = '''
				UPDATE admins
				SET password_hash = %(password_hash)s
				WHERE id = %(admin_id)s;
			'''
			db.write(query, password_hash=password_hash, admin_id=self.user['id'])

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
		self._assert_user()

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
		self._assert_user()

		query = '''
			INSERT INTO charity_categories (name)
			VALUES (%(name)s);'''
		with self._database.connect() as db:
			db.write(query, name=name)

	def read_charity_categories(self):
		self._assert_user()

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
		self._assert_user()

		query = '''
			UPDATE charity_categories
			SET name = %(name)s
			WHERE id = %(id)s;'''
		with self._database.connect() as db:
			db.write(query, id=id, name=name)

	def delete_charity_category(self, id):
		self._assert_user()

		query = '''
			DELETE FROM charity_categories
			WHERE id = %(id)s;'''
		with self._database.connect() as db:
			db.write(query, id=id)

	def create_charity(self, name, category_id):
		self._assert_user()

		query = '''
			INSERT INTO charities (name, category_id)
			VALUES (%(name)s, %(category_id)s);'''
		with self._database.connect() as db:
			db.write(query, name=name, category_id=category_id)

	def read_charities(self):
		self._assert_user()

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
		self._assert_user()

		query = '''
			UPDATE charities
			SET name = %(name)s, category_id = %(category_id)s
			WHERE id = %(id)s;'''
		with self._database.connect() as db:
			db.write(query, id=id, name=name, category_id=category_id)

	def delete_charity(self, id):
		self._assert_user()

		query = '''
			DELETE FROM charities
			WHERE id = %(id)s;'''
		with self._database.connect() as db:
			db.write(query, id=id)

	def create_country(self, name, live_in_name, iso_name, currency_id, min_donation_amount, min_donation_currency_id):
		self._assert_user()

		query = '''
			INSERT INTO countries (name, live_in_name, iso_name, currency_id, min_donation_amount, min_donation_currency_id)
			VALUES (%(name)s, %(live_in_name)s, %(iso_name)s, %(currency_id)s, %(min_donation_amount)s, %(min_donation_currency_id)s);'''
		with self._database.connect() as db:
			db.write(query, name=name, live_in_name=live_in_name, iso_name=iso_name, currency_id=currency_id, min_donation_amount=min_donation_amount, min_donation_currency_id=min_donation_currency_id)

	def read_countries(self):
		self._assert_user()

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
		self._assert_user()

		query = '''
			UPDATE countries
			SET name = %(name)s, live_in_name = %(live_in_name)s, iso_name = %(iso_name)s, currency_id = %(currency_id)s, min_donation_amount = %(min_donation_amount)s, min_donation_currency_id = %(min_donation_currency_id)s
			WHERE id = %(id)s;'''
		with self._database.connect() as db:
			db.write(query, id=id, name=name, live_in_name=live_in_name, iso_name=iso_name, currency_id=currency_id, min_donation_amount=min_donation_amount, min_donation_currency_id=min_donation_currency_id)

	def delete_country(self, id):
		self._assert_user()

		query = '''
			DELETE FROM countries
			WHERE id = %(id)s;'''
		with self._database.connect() as db:
			db.write(query, id=id)

	def create_charity_in_country(self, charity_id, country_id, tax_factor, instructions):
		self._assert_user()

		query = '''
			INSERT INTO charities_in_countries (charity_id, country_id, tax_factor, instructions)
			VALUES (%(charity_id)s, %(country_id)s, %(tax_factor)s, %(instructions)s);'''
		with self._database.connect() as db:
			db.write(query, charity_id=charity_id, country_id=country_id, tax_factor=tax_factor, instructions=instructions)

	def read_charities_in_countries(self):
		self._assert_user()

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
		self._assert_user()

		query = '''
			UPDATE charities_in_countries
			SET tax_factor = %(tax_factor)s, instructions = %(instructions)s
			WHERE charity_id = %(charity_id)s AND country_id = %(country_id)s;'''
		with self._database.connect() as db:
			db.write(query, charity_id=charity_id, country_id=country_id, tax_factor=tax_factor, instructions=instructions)

	def delete_charity_in_country(self, charity_id, country_id):
		self._assert_user()

		query = '''
			DELETE FROM charities_in_countries
			WHERE charity_id = %(charity_id)s AND country_id = %(country_id)s;'''
		with self._database.connect() as db:
			db.write(query, charity_id=charity_id, country_id=country_id)

	def read_log(self, min_timestamp, max_timestamp, event_types, offset, limit):
		self._assert_user()

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
		self._assert_user()

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
