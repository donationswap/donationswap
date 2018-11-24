#!/usr/bin/env python3

import re
import unittest

import entities
import donationswap
import util

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

class TestBase(unittest.TestCase):

	def setUp(self):
		self.ds = donationswap.Donationswap('test-config.json')
		self.captcha = self.ds._captcha = MockCaptcha()
		self.currency = self.ds._currency = MockCurrency()
		self.geoip = self.ds._geoip = MockGeoIpCountry()
		self.mail = self.ds._mail = MockMail()

		with self.ds._database.connect() as db:
			currency = db.read_one('''
				SELECT min(id) AS id
				FROM currencies;
				''')['id']
			db.write('''
				INSERT INTO charity_categories (id, name)
				VALUES
				(1, 'category1'),
				(2, 'category2');
				''')
			db.write('''
				INSERT INTO charities (id, name, category_id)
				VALUES
				(1, 'charity1', 1),
				(2, 'charity2', 2);
				''')
			db.write('''
				INSERT INTO countries (id, name, iso_name, currency_id, min_donation_amount, min_donation_currency_id, gift_aid)
				VALUES
				(1, 'country1', 'c1', %(currency)s, 0, %(currency)s, 100),
				(2, 'country1', 'c2', %(currency)s, 0, %(currency)s, 100);
				''', currency=currency)
			entities.load(db)

	def tearDown(self):
		if not self.ds._database._connection_string.startswith('dbname=test '):
			raise ValueError('Only ever clean up the test database.')
		with self.ds._database.connect() as db:
			db.write('DELETE FROM matches;')
			db.write('DELETE FROM offers;')
			db.write('DELETE FROM charities_in_countries;')
			db.write('DELETE FROM charities;')
			db.write('DELETE FROM countries;')
			db.write('DELETE FROM charity_categories;')

class get_page(TestBase):

	def test_contact_exists(self):
		self.assertTrue('<title>Donation Swap</title>' in self.ds.get_page('contact.html'))

	def test_howto_exists(self):
		self.assertTrue('<title>Donation Swap</title>' in self.ds.get_page('howto.html'))

	def test_index_exists(self):
		self.assertTrue('<title>Donation Swap</title>' in self.ds.get_page('index.html'))

	def test_match_exists(self):
		self.assertTrue('<title>Donation Swap</title>' in self.ds.get_page('match.html'))

	def test_offer_exists(self):
		self.assertTrue('<title>Donation Swap</title>' in self.ds.get_page('offer.html'))

	def test_start_exists(self):
		self.assertTrue('<title>Donation Swap</title>' in self.ds.get_page('start.html'))

	def test_bad_filename_should_not_raise_exception(self):
		self.assertEqual('', self.ds.get_page('this-file-does-not-exist'))

class get_info(TestBase):

	def test_all_information_must_be_included(self):
		info = self.ds.get_info()
		self.assertEqual(sorted(info.keys()), ['charities', 'charities_in_countries', 'client_country', 'countries', 'today'])

	def test_client_country(self):
		self.geoip.country = 'c1'
		result = self.ds.get_info()['client_country']
		self.assertEqual(result, 1)

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
		with self.assertRaises(donationswap.DonationException):
			self._send_message()

class create_offer(TestBase):

	def _create_offer(self, name='Ava of Animalia', country=1, amount=42, min_amount=1, charity=1, email='user@test.test'):
		return self.ds.create_offer(
			captcha_response='irrelevant',
			name=name,
			country=country,
			amount=amount,
			min_amount=min_amount,
			charity=charity,
			email=email,
			expiration={
				'day': 28,
				'month': 2,
				'year': 2012,
			}
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
		with self.assertRaises(donationswap.DonationException):
			self._create_offer()
		self.assertEqual(self._get_offer(), None)
		self.assertEqual(self.mail.calls, {})

	def test_bad_name(self):
		with self.assertRaises(donationswap.DonationException):
			self._create_offer(name='')
		self.assertEqual(self._get_offer(), None)
		self.assertEqual(self.mail.calls, {})

	def test_bad_country(self):
		with self.assertRaises(donationswap.DonationException):
			self._create_offer(country=100)
		self.assertEqual(self._get_offer(), None)
		self.assertEqual(self.mail.calls, {})

	def test_bad_amount(self):
		with self.assertRaises(donationswap.DonationException):
			self._create_offer(amount='fourty-two')
		self.assertEqual(self._get_offer(), None)
		self.assertEqual(self.mail.calls, {})

	def test_invalid_amount(self):
		with self.assertRaises(donationswap.DonationException):
			self._create_offer(amount=-42)
		self.assertEqual(self._get_offer(), None)
		self.assertEqual(self.mail.calls, {})

	def test_bad_min_amount(self):
		with self.assertRaises(donationswap.DonationException):
			self._create_offer(min_amount='fourty-two')
		self.assertEqual(self._get_offer(), None)
		self.assertEqual(self.mail.calls, {})

	def test_invalid_min_amount(self):
		with self.assertRaises(donationswap.DonationException):
			self._create_offer(min_amount=-42)
		self.assertEqual(self._get_offer(), None)
		self.assertEqual(self.mail.calls, {})

	def test_bad_charity(self):
		with self.assertRaises(donationswap.DonationException):
			self._create_offer(charity=100)
		self.assertEqual(self._get_offer(), None)
		self.assertEqual(self.mail.calls, {})

	def test_bad_email_address(self):
		with self.assertRaises(donationswap.DonationException):
			self._create_offer(email='user-at-test-dot-test')
		self.assertEqual(self._get_offer(), None)
		self.assertEqual(self.mail.calls, {})

class confirm_offer(TestBase):

	def test_happy_path_no_match(self):
		self.ds.create_offer(
			captcha_response='irrelevant',
			name='Buzz of Protozania',
			country=1,
			amount=42,
			min_amount=42,
			charity=1,
			email='user@test.test',
			expiration={
				'day': 28,
				'month': 2,
				'year': 2012,
			}
		)
		offer = entities.Offer.get_all(lambda x: x.email == 'user@test.test')[0]

		result = self.ds.confirm_offer(offer.secret)
		self.assertEqual(result['was_confirmed'], False)
		self.assertEqual(result['currency'], 'AED')
		self.assertEqual(result['amount'], 42)
		self.assertEqual(result['charity'], 'charity1'),

		self.assertTrue(offer.confirmed)

	def test_invalid_secret(self):
		result = self.ds.confirm_offer('this-secret-does-not-exist')
		self.assertEqual(result, None)

class delete_offer(TestBase):

	def test_happy_path(self):
		self.ds.create_offer(
			captcha_response='irrelevant',
			name='Ava of Animalia',
			country=1,
			amount=42,
			min_amount=42,
			charity=1,
			email='user@test.test',
			expiration={
				'day': 28,
				'month': 2,
				'year': 2012,
			}
		)
		offers = entities.Offer.get_all(lambda x: x.email == 'user@test.test')
		self.ds.delete_offer(offers[0].secret)

		offers = entities.Offer.get_all(lambda x: x.email == 'user@test.test')
		self.assertEqual(len(offers), 0)

class Templates(unittest.TestCase):
	'''Make sure all templates exist and contain the expected placeholders.'''

	def _check_expected_placeholders(self, txt, placeholders):
		for placeholder in placeholders:
			self.assertTrue(placeholder in txt, 'Missing expected placeholder %s.' % placeholder)
		for found_placeholder in re.findall(r'{%.+?%}', txt):
			self.assertTrue(found_placeholder in placeholders, 'Found unused placeholder %s.' % found_placeholder)

	def test_contact_email(self):
		placeholders = [
			'{%IP_ADDRESS%}',
			'{%COUNTRY%}',
			'{%NAME%}',
			'{%EMAIL%}',
			'{%MESSAGE%}',
		]
		txt = util.Template('contact-email.txt').content
		self._check_expected_placeholders(txt, placeholders)

	def test_match_appoved_email(self):
		placeholders = [
			'{%NAME_A%}',
			'{%COUNTRY_A%}',
			'{%CHARITY_A%}',
			'{%ACTUAL_AMOUNT_A%}',
			'{%CURRENCY_A%}',
			'{%EMAIL_A%}',
			'{%INSTRUCTIONS_A%}',
			'{%NAME_B%}',
			'{%COUNTRY_B%}',
			'{%CHARITY_B%}',
			'{%ACTUAL_AMOUNT_B%}',
			'{%CURRENCY_B%}',
			'{%EMAIL_B%}',
			'{%INSTRUCTIONS_B%}',
			'{%ONE_CURRENCY_A_AS_B%}',
			'{%TO_CHARITY_A%}',
			'{%TO_CHARITY_B%}',
			'{%GIFT_AID_INSERT_A_TXT%}',
			'{%GIFT_AID_INSERT_B_TXT%}',
		]
		txt = util.Template('match-approved-email.txt').content
		self._check_expected_placeholders(txt, placeholders)
		txt = util.Template('match-approved-email.html').content
		self._check_expected_placeholders(txt, placeholders)

	def test_match_suggested_email(self):
		placeholders = [
			'{%YOUR_NAME%}',
			'{%YOUR_CHARITY%}',
			'{%YOUR_AMOUNT%}',
			'{%YOUR_MIN_AMOUNT%}',
			'{%YOUR_ACTUAL_AMOUNT%}',
			'{%YOUR_CURRENCY%}',
			'{%THEIR_CHARITY%}',
			'{%SECRET%}',
		]
		txt = util.Template('match-suggested-email.txt').content
		self._check_expected_placeholders(txt, placeholders)
		txt = util.Template('match-suggested-email.html').content
		self._check_expected_placeholders(txt, placeholders)

	def test_new_post_email(self):
		placeholders = [
			'{%NAME%}',
			'{%SECRET%}',
			'{%CHARITY%}',
			'{%CURRENCY%}',
			'{%AMOUNT%}',
			'{%MIN_AMOUNT%}',
		]
		txt = util.Template('new-post-email.txt').content
		self._check_expected_placeholders(txt, placeholders)
		txt = util.Template('new-post-email.html').content
		self._check_expected_placeholders(txt, placeholders)

	def test_email_subjects(self):
		data = util.Template('email-subjects.json').json()
		self.assertTrue('match-declined-email' in data)
		self.assertTrue('match-decliner-email' in data)
		self.assertTrue('new-post-email' in data)

	def test_errors_and_warnings(self):
		data = util.Template('errors-and-warnings.json').json()
		self.assertTrue('bad amount' in data)
		self.assertTrue('bad captcha' in data)
		self.assertTrue('bad email address' in data)
		self.assertTrue('bad expiration date' in data)
		self.assertTrue('bad min_amount' in data)
		self.assertTrue('charity not found' in data)
		self.assertTrue('country not found' in data)
		self.assertTrue('match not found' in data)
		self.assertTrue('no name provided' in data)

if __name__ == '__main__':
	unittest.main(verbosity=2)
