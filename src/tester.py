#!/usr/bin/env python3

import datetime

import entities
import donationswap

class MockCaptcha:

	def __init__(self):
		self.calls = {}
		self.should_pass = True

	def is_legit(self, ip_address, captcha_response):
		self.calls.setdefault('is_legit', []).append(locals())
		return self.should_pass

class MockCurrency:

	def __init__(self):
		self.calls = {}
		self.from_factor = 1
		self.to_factor = 2

	def convert(self, amount, from_currency, to_currency):
		self.calls.setdefault('convert', []).append(locals())
		return int(amount / self.from_factor * self.to_factor)

class WrapEntities(entities.Entities):

	def __init__(self, database):
		super().__init__(database)
		self.offers = []
		self.matches = []

	def insert_offer(self, email, secret, country, amount, charity, time_to_live):
		super().insert_offer(email, secret, country, amount, charity, time_to_live)
		self.offers.append(secret)

	def insert_match(self, new_offer_id, old_offer_id, secret):
		super().insert_match(new_offer_id, old_offer_id, secret)
		self.matches.append(secret)

class MockGeoIpCountry:

	def __init__(self):
		self.calls = {}
		self.country = None

	def lookup(self, ip_address):
		self.calls.setdefault('lookup', []).append(locals())
		return self.country

class MockMail:

	def __init__(self):
		self.calls = {}

	def send(self, subject, text, html=None, to=None, cc=None, bcc=None):
		self.calls.setdefault('send', []).append(locals())

class MockMatchmaker:

	def __init__(self):
		self.calls = {}
		self.match_result = None

	def find_match(self, offer_id):
		self.calls.setdefault('send', []).append(locals())
		return self.match_result

ds = donationswap.Donationswap('test-config.json')
captcha = ds._captcha = MockCaptcha()
currency = ds._currency = MockCurrency()
entities = ds._entities = WrapEntities(ds._database)
geoip = ds._geoip = MockGeoIpCountry()
mail = ds._mail = MockMail()
matchmaker = ds._matchmaker = MockMatchmaker()

# user A creates (and confirms) an offer
ds.create_offer(
	captcha_response='irrelevant',
	country='nz',
	amount=42,
	charity='amf',
	email='user1@test.test',
	time_to_live=donationswap.OFFER_TTL_ONE_WEEK)
secret_a = entities.offers[-1]
ds.confirm_offer(secret_a)

# hack it so this offer will be the match for the next offer
matchmaker.match_result = entities.get_offer_by_secret(secret_a)['id']

# user B creates (and confirms) an offer
ds.create_offer(
	captcha_response='irrelevant',
	country='uk',
	amount=27,
	charity='hka',
	email='user2@test.test',
	time_to_live=donationswap.OFFER_TTL_ONE_WEEK)
secret_b = entities.offers[-1]
offer = ds.confirm_offer(secret_b)

print(ds.get_match(secret_a + offer['match_secret']))
print(ds.get_match(secret_b + offer['match_secret']))
