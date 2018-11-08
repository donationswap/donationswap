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

	@classmethod
	def load(cls, db):
		cls._by_id = {}
		for row in db.read('''SELECT * FROM charities;'''):
			cls._load_entity(row)

	@property
	def category(self):
		return CharityCategory.by_id(self.category_id)

class Country(EntityMixin, IdMixin):

	def __init__(self, row):
		self.id = row['id']
		self.name = row['name']
		self.live_in_name = row['live_in_name']
		self.iso_name = row['iso_name']
		self.currency_id = row['currency_id']
		self.min_donation_amount = row['min_donation_amount']
		self.min_donation_currency_id = row['min_donation_currency_id']

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

	@classmethod
	def by_iso_name(cls, id):
		return cls._by_iso_name.get(id, None)

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
		cls._by_charity_and_country_id.setdefault(entity.charity_id, {})[entity.country_id] = entity

	@classmethod
	def load(cls, db):
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

class Offer(EntityMixin, IdMixin, SecretMixin): # pylint: disable=too-many-instance-attributes

	def __init__(self, row):
		self.id = row['id']
		self.secret = row['secret']
		self.email = row['email']
		self.country_id = row['country_id']
		self.amount = row['amount']
		self.charity_id = row['charity_id']
		self.created_ts = row['created_ts']
		self.expires_ts = row['expires_ts']
		self.confirmed = row['confirmed']

	def __repr__(self):
		return '{id}:{email}:{amount}'.format(**self.__dict__)

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
	def create(cls, db, secret, email, country_id, amount, charity_id, expires_ts):
		query = '''
			INSERT INTO offers
			(secret, email, country_id, amount, charity_id, expires_ts, confirmed)
			VALUES
			(%(secret)s, %(email)s, %(country_id)s, %(amount)s, %(charity_id)s, %(expires_ts)s, false)
			RETURNING *;
		'''
		row = db.write_read_one(query,
			secret=secret,
			email=email,
			country_id=country_id,
			amount=amount,
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

	@classmethod
	def get_match_candidates(cls, db):
		query = '''
			SELECT * FROM offers
			WHERE confirmed AND expires_ts > now() AND
				NOT EXISTS(SELECT 1 FROM matches WHERE old_offer_id = offers.id) AND
				NOT EXISTS(SELECT 1 FROM matches WHERE new_offer_id = offers.id);
		'''
		db.read(query)
		ids = set(i['id'] for i in db.read(query))
		return cls.get_all(lambda x: x.id in ids)

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
