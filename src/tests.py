#!/usr/bin/env python3

import datetime
import unittest

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

class TestBase(unittest.TestCase):

	def setUp(self):
		self.ds = donationswap.Donationswap('test-config.json')
		self.captcha = self.ds._captcha = MockCaptcha()
		self.currency = self.ds._currency = MockCurrency()
		self.entities = self.ds._entities = WrapEntities(self.ds._database)
		self.geoip = self.ds._geoip = MockGeoIpCountry()
		self.mail = self.ds._mail = MockMail()
		self.matchmaker = self.ds._matchmaker = MockMatchmaker()

	def tearDown(self):
		if not self.ds._database._connection_string.startswith('dbname=test '):
			raise ValueError('Only ever clean up the test database.')
		with self.ds._database.connect() as db:
			db.write('DELETE FROM matches;')
			db.write('DELETE FROM offers;')

class get_page(TestBase):

	def test_index_exists(self):
		self.assertTrue('<title>Donation Swap</title>' in self.ds.get_page('index.html'))

	def test_faq_exists(self):
		self.assertTrue('<title>Donation Swap</title>' in self.ds.get_page('faq.html'))

	def test_contact_exists(self):
		self.assertTrue('<title>Donation Swap</title>' in self.ds.get_page('contact.html'))

	def test_offer_exists(self):
		self.assertTrue('<title>Donation Swap</title>' in self.ds.get_page('offer.html'))

	def test_match_exists(self):
		self.assertTrue('<title>Donation Swap</title>' in self.ds.get_page('match.html'))

	def test_bad_filename_should_not_raise_exception(self):
		self.assertEqual('', self.ds.get_page('this-file-does-not-exist'))

class get_info(TestBase):

	def test_all_information_must_be_included(self):
		info = self.ds.get_info()
		self.assertEqual(sorted(info.keys()), ['charities', 'client_country', 'countries'])

	def test_client_country(self):
		COUNTRY = datetime.datetime.utcnow() # any "random" value
		self.geoip.country = COUNTRY
		self.assertEqual(self.ds.get_info()['client_country'], COUNTRY)

class send_contact_message(TestBase):

	def _send_message(self):
		self.ds.send_contact_message(
			captcha_response='irrelevant',
			message='hello world',
			name='my name',
			email='my email address'
		)

	def test_happy_path(self):
		self.ds._ip_address = 'ip'
		self._send_message()

		calls = self.mail.calls['send']
		self.assertEqual(len(calls), 1)

		call = calls[0]
		self.assertTrue('hello world' in call['text'])

	def test_bad_captcha(self):
		self.captcha.should_pass = False
		with self.assertRaises(ValueError):
			self._send_message()

class create_offer(TestBase):

	def _create_offer(self, country='nz', amount=42, charity='amf', email='user@test.test', time_to_live=donationswap.OFFER_TTL_THREE_MONTHS):
		return self.ds.create_offer(
			captcha_response='irrelevant',
			country=country,
			amount=amount,
			charity=charity,
			email=email,
			time_to_live=time_to_live
		)

	def _get_offer(self):
		with self.ds._database.connect() as db:
			return db.read_one('SELECT * FROM offers;')

	def test_happy_path(self):
		result = self._create_offer()

		self.assertEqual(result, None)

		offer = self._get_offer()
		self.assertEqual(offer['email'], 'user@test.test')
		self.assertFalse(offer['confirmed'])
		self.assertEqual(offer['amount'], 42)

		self.assertEqual(len(self.mail.calls['send']), 1)
		self.assertEqual(self.mail.calls['send'][-1]['to'], 'user@test.test')

	def test_bad_captcha(self):
		self.captcha.should_pass = False
		with self.assertRaises(ValueError):
			self._create_offer()
		self.assertEqual(self._get_offer(), None)
		self.assertEqual(self.mail.calls, {})

	def test_bad_country(self):
		with self.assertRaises(ValueError):
			self._create_offer(country='this-country-does-not-exist')
		self.assertEqual(self._get_offer(), None)
		self.assertEqual(self.mail.calls, {})

	def test_bad_amount(self):
		with self.assertRaises(ValueError):
			self._create_offer(amount='fourty-two')
		self.assertEqual(self._get_offer(), None)
		self.assertEqual(self.mail.calls, {})

	def test_invalid_amount(self):
		with self.assertRaises(ValueError):
			self._create_offer(amount=-42)
		self.assertEqual(self._get_offer(), None)
		self.assertEqual(self.mail.calls, {})

	def test_bad_charity(self):
		with self.assertRaises(ValueError):
			self._create_offer(charity='this-charity-does-not-exist')
		self.assertEqual(self._get_offer(), None)
		self.assertEqual(self.mail.calls, {})

	def test_bad_email_address(self):
		with self.assertRaises(ValueError):
			self._create_offer(email='user-at-test-dot-test')
		self.assertEqual(self._get_offer(), None)
		self.assertEqual(self.mail.calls, {})

	def test_invalid_time_to_live(self):
		with self.assertRaises(ValueError):
			self._create_offer(time_to_live='one')
		self.assertEqual(self._get_offer(), None)
		self.assertEqual(self.mail.calls, {})

	def test_bad_time_to_live(self):
		with self.assertRaises(ValueError):
			self._create_offer(time_to_live=3)
		self.assertEqual(self._get_offer(), None)
		self.assertEqual(self.mail.calls, {})

class confirm_offer(TestBase):

	def test_happy_path_no_match(self):
		self.ds.create_offer(
			captcha_response='irrelevant',
			country='nz',
			amount=42,
			charity='amf',
			email='user@test.test',
			time_to_live=donationswap.OFFER_TTL_THREE_MONTHS
		)
		with self.ds._database.connect() as db:
			offer = db.read_one('SELECT * FROM offers;')

		result = self.ds.confirm_offer(offer['secret'])
		self.assertEqual(result['was_confirmed'], False)
		self.assertEqual(result['currency'], 'NZD')
		self.assertEqual(result['amount'], 42)
		self.assertEqual(result['charity'], 'Against Malaria Foundation'),
		# ignore created_ts and expires_ts
		self.assertEqual(result['match_secret'], None)

		with self.ds._database.connect() as db:
			offer = db.read_one('SELECT * FROM offers;')
		self.assertTrue(offer['confirmed'])

	def test_invalid_secret(self):
		result = self.ds.confirm_offer('this-secret-does-not-exist')
		self.assertEqual(result, None)

class delete_offer(TestBase):

	def test_happy_path(self):
		self.ds.create_offer(
			captcha_response='irrelevant',
			country='nz',
			amount=42,
			charity='amf',
			email='user@test.test',
			time_to_live=donationswap.OFFER_TTL_THREE_MONTHS
		)
		with self.ds._database.connect() as db:
			offer = db.read_one('SELECT * FROM offers;')
		self.assertTrue(offer is not None)

		self.ds.delete_offer(offer['secret'])

		with self.ds._database.connect() as db:
			offer = db.read_one('SELECT * FROM offers;')
		self.assertTrue(offer is None)

class Workflow(TestBase):

	def test_happy_path(self):
		# User A creates an offer.
		self.ds.create_offer(
			captcha_response='irrelevant',
			country='nz',
			amount=42,
			charity='amf',
			email='user1@test.test',
			time_to_live=donationswap.OFFER_TTL_ONE_WEEK)

		# This triggers an email to the user.
		self.assertEqual(self.mail.calls['send'][-1]['to'], 'user1@test.test')

		# User A confirms the offer.
		secret_a = self.entities.offers[-1]
		offer = self.ds.confirm_offer(secret_a)
		self.assertEqual(offer['amount'], 42)

		# (hack it so this offer will be the match for the next offer)
		self.matchmaker.match_result = self.entities.get_offer_by_secret(secret_a)['id']

		# User B creates an offer.
		self.ds.create_offer(
			captcha_response='irrelevant',
			country='gb',
			amount=27,
			charity='hka',
			email='user2@test.test',
			time_to_live=donationswap.OFFER_TTL_ONE_WEEK)

		# This triggers an email to the user.
		self.assertEqual(self.mail.calls['send'][-1]['to'], 'user2@test.test')

		# User B confirms the offer.
		secret_b = self.entities.offers[-1]
		offer = self.ds.confirm_offer(secret_b)
		self.assertEqual(offer['amount'], 27)

		# This triggers a successful search for a match.

		# Emails are sent to both users.
		self.assertEqual(self.mail.calls['send'][-2]['to'], 'user1@test.test')
		self.assertEqual(self.mail.calls['send'][-1]['to'], 'user2@test.test')
		match_a = self.ds.get_match(secret_a + offer['match_secret'])
		match_b = self.ds.get_match(secret_b + offer['match_secret'])
		self.assertEqual(match_a['their_amount'], 27)
		self.assertEqual(match_b['their_amount'], 42)

		# User A approve the match.
		self.ds.approve_match(secret_a + offer['match_secret'])
		match = self.entities.get_match_by_secret(offer['match_secret'])
		self.assertEqual(match['old_agrees'], True)
		self.assertEqual(match['new_agrees'], None)

		# No email is sent.
		self.assertEqual(len(self.mail.calls['send']), 4)

		# User B approves the match.
		self.ds.approve_match(secret_b + offer['match_secret'])
		match = self.entities.get_match_by_secret(offer['match_secret'])
		self.assertEqual(match['old_agrees'], True)
		self.assertEqual(match['new_agrees'], True)

		# Emails are sent to both users.
		self.assertEqual(len(self.mail.calls['send']), 6)
		self.assertEqual(self.mail.calls['send'][-2]['to'], 'user1@test.test')
		self.assertEqual(self.mail.calls['send'][-1]['to'], 'user2@test.test')
		self.assertTrue('user2@test.test' in self.mail.calls['send'][-2]['text'])
		self.assertTrue('user1@test.test' in self.mail.calls['send'][-1]['text'])

if __name__ == '__main__':
	unittest.main(verbosity=2)
