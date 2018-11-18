#!/usr/bin/env python3

# pylint: disable=invalid-name
# pylint: disable=redefined-builtin

class EntityMixin: # pylint: disable=too-few-public-methods

	@classmethod
	def _load_entity(cls, row):
		entity = cls(row)
		cls._load_entity_impl(entity)
		return entity

	@classmethod
	def _load_entity_impl(cls, entity):
		raise NotImplementedError()

	def __repr__(self):
		return self.__class__.__name__

	def __str__(self):
		return self.__repr__()

class IdMixin: # pylint: disable=too-few-public-methods

	_by_id = {}

	@classmethod
	def by_id(cls, id):
		return cls._by_id.get(id, None)

	@classmethod
	def get_all(cls, callback=None):
		if callback is None:
			return list(cls._by_id.values())
		return list(filter(callback, cls._by_id.values()))

class SecretMixin: # pylint: disable=too-few-public-methods

	_by_secret = {}

	@classmethod
	def by_secret(cls, secret):
		return cls._by_secret.get(secret, None)

class Currency(EntityMixin, IdMixin):

	def __init__(self, row):
		self.id = row['id']
		self.iso = row['iso']
		self.name = row['name']

	def __repr__(self):
		return '{id}:{iso}:{name}'.format(**self.__dict__)

	@classmethod
	def _load_entity_impl(cls, entity):
		cls._by_id[entity.id] = entity

	@classmethod
	def load(cls, db):
		cls._by_id = {}
		for row in db.read('''SELECT * FROM currencies;'''):
			cls._load_entity(row)

class CharityCategory(EntityMixin, IdMixin):

	def __init__(self, row):
		self.id = row['id']
		self.name = row['name']

	def __repr__(self):
		return '{id}:{name}'.format(**self.__dict__)

	@classmethod
	def _load_entity_impl(cls, entity):
		cls._by_id[entity.id] = entity

	@classmethod
	def load(cls, db):
		cls._by_id = {}
		for row in db.read('''SELECT * FROM charity_categories;'''):
			cls._load_entity(row)

	@classmethod
	def create(cls, db, name):
		query = '''
			INSERT INTO charity_categories (name)
			VALUES (%(name)s)
			RETURNING *;'''
		row = db.read_one(query, name=name)
		db.written = True
		return cls._load_entity(row)

	def save(self, db):
		query = '''
			UPDATE charity_categories
			SET name = %(name)s
			WHERE id = %(id)s;'''
		db.write(query,
			id=self.id,
			name=self.name)

	def delete(self, db):
		query = '''
			DELETE FROM charity_categories
			WHERE id=%(id)s'''
		db.write(query, id=self.id)
		self._by_id.pop(self.id, None)

class Charity(EntityMixin, IdMixin):

	def __init__(self, row):
		self.id = row['id']
		self.name = row['name']
		self.category_id = row['category_id']

	def __repr__(self):
		return '{id}:{name}:{category_id}'.format(**self.__dict__)

	@classmethod
	def _load_entity_impl(cls, entity):
		cls._by_id[entity.id] = entity
		cls._by_name[entity.name] = entity

	@classmethod
	def load(cls, db):
		cls._by_id = {}
		cls._by_name = {}
		for row in db.read('''SELECT * FROM charities;'''):
			cls._load_entity(row)

	@classmethod
	def by_name(cls, name):
		return cls._by_name.get(name, None)

	@property
	def category(self):
		return CharityCategory.by_id(self.category_id)

	@classmethod
	def create(cls, db, name, category_id):
		query = '''
			INSERT INTO charities (name, category_id)
			VALUES (%(name)s, %(category_id)s)
			RETURNING *;'''
		row = db.read_one(query, name=name, category_id=category_id)
		db.written = True
		return cls._load_entity(row)

	def save(self, db):
		query = '''
			UPDATE charities
			SET name = %(name)s, category_id = %(category_id)s
			WHERE id = %(id)s;'''
		db.write(query,
			id=self.id,
			name=self.name,
			category_id=self.category_id)

	def delete(self, db):
		query = '''
			DELETE FROM charities
			WHERE id=%(id)s'''
		db.write(query, id=self.id)
		self._by_id.pop(self.id, None)
		self._by_name.pop(self.name, None)

class Country(EntityMixin, IdMixin):

	def __init__(self, row):
		self.id = row['id']
		self.name = row['name']
		self.live_in_name = row['live_in_name']
		self.iso_name = row['iso_name']
		self.currency_id = row['currency_id']
		self.min_donation_amount = row['min_donation_amount']
		self.min_donation_currency_id = row['min_donation_currency_id']
		self.gift_aid = row['gift_aid']

	def __repr__(self):
		return '{id}:{name}:{iso_name}:{currency_id}'.format(**self.__dict__)

	@classmethod
	def _load_entity_impl(cls, entity):
		cls._by_id[entity.id] = entity
		cls._by_iso_name[entity.iso_name] = entity

	@classmethod
	def load(cls, db):
		cls._by_id = {}
		cls._by_iso_name = {}
		for row in db.read('''SELECT * FROM countries;'''):
			cls._load_entity(row)

	@property
	def currency(self):
		return Currency.by_id(self.currency_id)

	@property
	def min_donation_currency(self):
		return Currency.by_id(self.min_donation_currency_id)

	@property
	def gift_aid_multipler(self):
		return (self.gift_aid / 100.0) + 1

	@classmethod
	def by_iso_name(cls, iso_name):
		return cls._by_iso_name.get(iso_name, None)

	@classmethod
	def create(cls, db, name, live_in_name, iso_name, currency_id, min_donation_amount, min_donation_currency_id, gift_aid):
		query = '''
			INSERT INTO countries (name, live_in_name, iso_name, currency_id, min_donation_amount, min_donation_currency_id, gift_aid)
			VALUES (%(name)s, %(live_in_name)s, %(iso_name)s, %(currency_id)s, %(min_donation_amount)s, %(min_donation_currency_id)s, %(gift_aid)s)
			RETURNING *;'''
		row = db.read_one(query, name=name, live_in_name=live_in_name, iso_name=iso_name, currency_id=currency_id, min_donation_amount=min_donation_amount, min_donation_currency_id=min_donation_currency_id)
		db.written = True
		return cls._load_entity(row)

	def save(self, db):
		query = '''
			UPDATE countries
			SET name = %(name)s, live_in_name = %(live_in_name)s, iso_name = %(iso_name)s, currency_id = %(currency_id)s, min_donation_amount = %(min_donation_amount)s, min_donation_currency_id = %(min_donation_currency_id)s
			WHERE id = %(id)s;'''
		db.write(query,
			id=self.id,
			name=self.name,
			live_in_name=self.live_in_name,
			iso_name=self.iso_name,
			currency_id=self.currency_id,
			min_donation_amount=self.min_donation_amount,
			min_donation_currency_id=self.min_donation_currency_id,
			gift_aid=self.gift_aid)

	def delete(self, db):
		query = '''
			DELETE FROM countries
			WHERE id=%(id)s'''
		db.write(query, id=self.id)
		self._by_id.pop(self.id, None)
		self._by_iso_name.pop(self.iso_name, None)

class CharityInCountry(EntityMixin):

	def __init__(self, row):
		self.charity_id = row['charity_id']
		self.country_id = row['country_id']
		self.tax_factor = row['tax_factor']
		self.instructions = row['instructions']

	def __repr__(self):
		return '{charity_id}:{country_id}:{tax_factor}'.format(**self.__dict__)

	@classmethod
	def _load_entity_impl(cls, entity):
		cls._all.append(entity)
		cls._by_charity_and_country_id.setdefault(entity.charity_id, {})[entity.country_id] = entity

	@classmethod
	def load(cls, db):
		cls._all = []
		cls._by_charity_and_country_id = {}
		for row in db.read('''SELECT * FROM charities_in_countries;'''):
			cls._load_entity(row)

	@property
	def charity(self):
		return Charity.by_id(self.charity_id)

	@property
	def country(self):
		return Country.by_id(self.country_id)

	@classmethod
	def by_charity_and_country_id(cls, charity_id, country_id):
		return cls._by_charity_and_country_id.get(charity_id, {}).get(country_id, None)

	@classmethod
	def get_all(cls, callback=None):
		if callback is None:
			return cls._all[:]
		return list(filter(callback, cls._all[:]))

	@classmethod
	def create(cls, db, charity_id, country_id, tax_factor, instructions):
		query = '''
			INSERT INTO charities_in_countries (charity_id, country_id, tax_factor, instructions)
			VALUES (%(charity_id)s, %(country_id)s, %(tax_factor)s, %(instructions)s)
			RETURNING *;'''
		row = db.read_one(query, charity_id=charity_id, country_id=country_id, tax_factor=tax_factor, instructions=instructions)
		db.written = True
		return cls._load_entity(row)

	def save(self, db):
		query = '''
			UPDATE charities_in_countries
			SET tax_factor = %(tax_factor)s, instructions = %(instructions)s
			WHERE charity_id = %(charity_id)s AND country_id = %(country_id)s;'''
		db.write(query,
			charity_id=self.charity_id,
			country_id=self.country_id,
			tax_factor=self.tax_factor,
			instructions=self.instructions)

	def delete(self, db):
		query = '''
			DELETE FROM charities_in_countries
			WHERE charity_id=%(charity_id)s AND country_id=%(country_id)s'''
		db.write(query, charity_id=self.charity_id, country_id=self.country_id)
		self._all.remove(self)
		self._by_charity_and_country_id.get(self.charity_id, {}).pop(self.country_id, None)

class Offer(EntityMixin, IdMixin, SecretMixin): # pylint: disable=too-many-instance-attributes

	def __init__(self, row):
		self.id = row['id']
		self.secret = row['secret']
		self.name = row['name']
		self.email = row['email']
		self.country_id = row['country_id']
		self.amount = row['amount']
		self.min_amount = row['min_amount']
		self.charity_id = row['charity_id']
		self.created_ts = row['created_ts']
		self.expires_ts = row['expires_ts']
		self.confirmed = row['confirmed']

	def __repr__(self):
		return '{id}:{name}:{email}:{amount}'.format(**self.__dict__)

	@classmethod
	def _load_entity_impl(cls, entity):
		cls._by_id[entity.id] = entity
		cls._by_secret[entity.secret] = entity

	@classmethod
	def load(cls, db):
		cls._by_id = {}
		cls._by_secret = {}
		for row in db.read('''SELECT * FROM offers ORDER BY created_ts;'''):
			cls._load_entity(row)

	@property
	def charity(self):
		return Charity.by_id(self.charity_id)

	@property
	def country(self):
		return Country.by_id(self.country_id)

	@classmethod
	def get_unmatched_offers(cls, db):
		query = '''
			SELECT offer.id AS id
			FROM offers offer
			JOIN countries country ON offer.country_id = country.id
			JOIN charities charity ON offer.charity_id = charity.id
			WHERE
				offer.confirmed
				AND offer.expires_ts > now()
				AND offer.id NOT IN (SELECT old_offer_id FROM matches)
				AND offer.id NOT IN (SELECT new_offer_id FROM matches)
			ORDER BY country ASC, charity ASC, expires_ts ASC;
		'''
		return [
			cls.by_id(i['id'])
			for i in db.read(query)
		]

	@classmethod
	def get_expired_offers(cls, db):
		query = '''
			SELECT offer.id AS id
			FROM offers offer
			WHERE offer.expires_ts < now()
			AND offer.id NOT IN (SELECT old_offer_id FROM matches)
			AND offer.id NOT IN (SELECT new_offer_id FROM matches);
		'''
		return [
			cls.by_id(i['id'])
			for i in db.read(query)
		]

	@classmethod
	def create(cls, db, secret, name, email, country_id, amount, min_amount, charity_id, expires_ts):
		query = '''
			INSERT INTO offers
			(secret, name, email, country_id, amount, min_amount, charity_id, expires_ts, confirmed)
			VALUES
			(%(secret)s, %(name)s, %(email)s, %(country_id)s, %(amount)s, %(min_amount)s, %(charity_id)s, %(expires_ts)s, false)
			RETURNING *;
		'''
		row = db.write_read_one(query,
			secret=secret,
			name=name,
			email=email,
			country_id=country_id,
			amount=amount,
			min_amount=min_amount,
			charity_id=charity_id,
			expires_ts=expires_ts
		)
		return cls._load_entity(row)

	def confirm(self, db):
		query = '''
			UPDATE offers
			SET confirmed = true
			WHERE id = %(id)s;
		'''
		db.write(query, id=self.id)
		self.confirmed = True

	def suspend(self, db):
		#xxx introducing a new "suspended" column would be more honest
		#    (created_ts should NEVER be updated)
		query = '''
			UPDATE offers
			SET confirmed = false, created_ts = now()
			WHERE id = %(id)s;
		'''
		db.write(query, id=self.id)
		self.confirmed = False

	def delete(self, db):
		query = '''
			DELETE FROM offers
			WHERE id = %(id)s;
		'''
		db.write(query, id=self.id)
		self._by_id.pop(self.id, None)
		self._by_secret.pop(self.secret, None)

class Match(EntityMixin, IdMixin, SecretMixin):

	def __init__(self, row):
		self.id = row['id']
		self.secret = row['secret']
		self.new_offer_id = row['new_offer_id']
		self.old_offer_id = row['old_offer_id']
		self.new_agrees = row['new_agrees']
		self.old_agrees = row['old_agrees']
		self.created_ts = row['created_ts']

	def __repr__(self):
		return '{id}:{new_offer_id}:{old_offer_id}'.format(**self.__dict__)

	@classmethod
	def _load_entity_impl(cls, entity):
		cls._by_id[entity.id] = entity
		cls._by_secret[entity.secret] = entity

	@classmethod
	def load(cls, db):
		cls._by_id = {}
		cls._by_secret = {}
		for row in db.read('''SELECT * FROM matches;'''):
			cls._load_entity(row)

	@property
	def new_offer(self):
		return Offer.by_id(self.new_offer_id)

	@property
	def old_offer(self):
		return Offer.by_id(self.old_offer_id)

	@classmethod
	def create(cls, db, secret, new_offer_id, old_offer_id):
		query = '''
			INSERT INTO matches
			(secret, new_offer_id, old_offer_id)
			VALUES
			(%(s)s, %(noid)s, %(ooid)s)
			RETURNING *;
		'''
		row = db.write_read_one(query, s=secret, noid=new_offer_id, ooid=old_offer_id)
		return cls._load_entity(row)

	def agree_old(self, db):
		query = '''
		UPDATE matches
		SET old_agrees = true
		WHERE id = %(id)s;
		'''
		db.write(query, id=self.id)
		self.old_agrees = True

	def agree_new(self, db):
		query = '''
		UPDATE matches
		SET new_agrees = true
		WHERE id = %(id)s;
		'''
		db.write(query, id=self.id)
		self.new_agrees = True

	def delete(self, db):
		query = '''
			DELETE FROM matches
			WHERE id = %(id)s;
		'''
		db.write(query, id=self.id)
		self._by_id.pop(self.id, None)
		self._by_secret.pop(self.secret, None)

def load(db):
	Currency.load(db)
	CharityCategory.load(db)
	Charity.load(db)
	Country.load(db)
	CharityInCountry.load(db)
	Offer.load(db)
	Match.load(db)
