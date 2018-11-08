#!/usr/bin/env python3

import argparse
import datetime
import json
import logging
import urllib.parse

import config
import currency
import database
import donationswap
import entities
import mail
import util

from matching.charity import Charity
from matching.country import Country
from matching.donor import Donor
from matching.offer import Offer
from matching.matcher import Matcher

class Matchmaker:

	def __init__(self, config_path, dry_run=False):
		self._dry_run = dry_run
		self._config = config.Config(config_path)
		self._database = database.Database(self._config.db_connection_string)
		self._currency = currency.Currency(self._config.currency_cache, self._config.fixer_apikey)
		self._mail = mail.Mail(self._config.email_user, self._config.email_password, self._config.email_smtp, self._config.email_sender_name)

		with self._database.connect() as db:
			entities.load(db)

	def _send_mail_about_expired_offer(self, offer):
		replacements = {
			'{%NAME%}': 'xxx (name not implemented yet)', #offer.name
			'{%AMOUNT%}': offer.amount,
			'{%MIN_AMOUNT%}': 'xxx',
			'{%CURRENCY%}': offer.country.currency.iso,
			'{%CHARITY%}': offer.charity.name,
			'{%ARGS%}': '#%s' % urllib.parse.quote(json.dumps({
				'country': offer.country_id,
				'amount': offer.amount,
				'charity': offer.charity_id,
				'expires': [
					offer.expires_ts.day,
					offer.expires_ts.month,
					offer.expires_ts.year,
				],
				'email': offer.email,
			}))
		}

		logging.info('Sending expiration email to %s.', offer.email)

		self._mail.send(
			'Your offer has expired',
			util.Template('offer-expired-email.txt').replace(replacements).content,
			html=util.Template('offer-expired-email.html').replace(replacements).content,
			to=offer.email
		)

	def _delete_expired_offers(self):
		'''An offer is considered expired if it has not been confirmed
		for 24 hours. We delete it and send the donor an email.'''

		one_day_ago = datetime.datetime.utcnow() - datetime.timedelta(days=1)
		with self._database.connect() as db:
			for offer in entities.Offer.get_all(lambda x: not x.confirmed and x.created_ts < one_day_ago):
				logging.info('Deleting expired offer.')
				offer.delete(db)
				self._send_mail_about_expired_offer(offer)

	def _send_mail_about_match_feedback(match):
		replacements = {
		}

		logging.info('Sending match feedback email to %s and %s', (
			match.old_offer.email,
			match.new_offer.email,
		))

		pass #xxx

	def _delete_old_matches(self):
		'''Four weeks after a match was made we delete it and
		send the two donors a feedback email.

		(It only gets to be four weeks old if it was accepted by both
		donors, otherwise it would have been deleted within 72 hours.)'''

		four_weeks_ageo = datetime.datetime.utcnow() - datetime.timedelta(days=28)

		with self._database.connect() as db:
			for match in entities.Match.get_all(lambda x: x.new_agrees is True and x.old_agrees is True and x.created_ts < four_weeks_ago):
				match.delete(db)
				self._send_mail_about_match_feedback(match)

	def clean(self):
		self._delete_expired_offers()
		self._delete_old_matches()

		now = datetime.datetime.utcnow()
		two_days = datetime.timedelta(days=2)
		one_week = datetime.timedelta(days=7)

		with self._database.connect() as db:

			# delete declined matches immediately
			for match in entities.Match.get_all(lambda x: x.new_agrees is False or x.old_agrees is False):
				match.delete(db)

			# delete unapproved matches after one week
			for match in entities.Match.get_all(lambda x: x.new_agrees is None or x.old_agrees is None and x.created_ts + one_week < now):
				match.delete(db)

			#xxx also...
			# ... delete expired offers that aren't part of a match
			# ... signal the web server to update its cache

	def _is_good_match(self, offer1, offer2):

		#xxx if (offer1, offer2) in declined_matches: return False

		logging.info('Comparing %s and %s.', offer1.id, offer2.id)

		if offer1.charity_id == offer2.charity_id:
			logging.info('same charity.')
			return False
		if offer1.country_id == offer2.country_id:
			logging.info('same country.')
			return False
		if offer1.email == offer2.email:
			logging.info('same email.')
			return False

		dbCountry1 = offer1.country
		dbCountry2 = offer2.country

		# TODO: UK and ireland(?) GiftAid
		multiplier1 = 1
		multiplier2 = 1

		exchangeRate1VsUSA = self._currency.convert(1, dbCountry1.currency.iso, "USD")
		exchangeRate2VsUSA = self._currency.convert(1, dbCountry1.currency.iso, "USD")

		country1Charities = []
		country2Charities = []

		charityCache = {}
		country1TaxReturn = 0
		country2TaxReturn = 0

		for charity in entities.Charity.get_all():
			if (charity.name not in charityCache):
				charityCache[charity.name] = Charity(charity.name)

			charityInCountry1 = entities.CharityInCountry.by_charity_and_country_id(charity.id, dbCountry1.id)
			charityInCountry2 = entities.CharityInCountry.by_charity_and_country_id(charity.id, dbCountry2.id)
			if (charityInCountry1 != None):
				country1Charities.append(charityCache[charity.name])
				if (offer1.charity == charity):
					country1TaxReturn = charityInCountry1.tax_factor

			if (charityInCountry2 != None):
				country2Charities.append(charityCache[charity.name])
				if (offer2.charity == charity):
					country2TaxReturn = charityInCountry2.tax_factor

		country1 = Country(dbCountry1.name, dbCountry1.currency.iso, country1Charities, country1TaxReturn, exchangeRate1VsUSA, multiplier1)
		country2 = Country(dbCountry2.name, dbCountry2.currency.iso, country2Charities, country2TaxReturn, exchangeRate2VsUSA, multiplier2)

		offer1Created = 0
		offer2Created = 0
		amount1 = offer1.amount
		amount2 = offer2.amount
		donor1 = Donor(offer1.email, country1)
		donor2 = Donor(offer2.email, country2)

		#xxx offers SHOULD have approximately the same amount (taking tax benefits into account)
		#    for development, however, everthing goes.
		matchingOffer1 = Offer(donor1, amount1 * 0.5, amount1, [charityCache[offer1.charity.name]], offer1Created)
		matchingOffer2 = Offer(donor2, amount2 * 0.5, amount2, [charityCache[offer2.charity.name]], offer2Created)

		result = Matcher("USD").match(matchingOffer1, [matchingOffer2])
		return result != None

	def find_matches(self, force_pair=None):
		'''Compares every offer to every other offer.'''

		matches = []

		with self._database.connect() as db:
			offers = entities.Offer.get_match_candidates(db)

		logging.info('There are %s eligible offers to match up.', len(offers))

		if force_pair is not None:
			force_pair = sorted(force_pair)

		while offers:
			offer1 = offers.pop()
			for offer2 in offers:
				if force_pair is None:
					is_good = self._is_good_match(offer1, offer2)
				else:
					is_good = sorted([offer1, offer2]) == force_pair

				if is_good:
					matches.append((offer1, offer2))
					offers.remove(offer2)
					break

		logging.info('Found %s matching pairs.', len(matches))

		return matches

	def _send_mail_about_match(self, my_offer, their_offer, match_secret):
		your_amount_in_their_currency = self._currency.convert(
			their_offer.amount,
			their_offer.country.currency.iso,
			my_offer.country.currency.iso)

		replacements = {
			'{%YOUR_NAME%}': 'xxx add name', #xxx my_offer.name,
			'{%YOUR_COUNTRY%}': my_offer.country.name,
			'{%YOUR_CHARITY%}': my_offer.charity.name,
			'{%YOUR_AMOUNT%}': my_offer.amount,
			'{%YOUR_MIN_AMOUNT%}': 'xxx',
			'{%YOUR_CURRENCY%}': my_offer.country.currency.iso,
			'{%THEIR_COUNTRY%}': their_offer.country.name,
			'{%THEIR_CHARITY%}': their_offer.charity.name,
			'{%THEIR_AMOUNT%}': their_offer.amount,
			'{%THEIR_CURRENCY%}': their_offer.country.currency.iso,
			'{%THEIR_AMOUNT_CONVERTED%}': your_amount_in_their_currency,
			'{%SECRET%}': '%s%s' % (my_offer.secret, match_secret),
			# Do NOT put their email address here.
			# Wait until both parties approved the match.
		}

		logging.info('Sending match email to %s.', my_offer.email)

		self._mail.send(
			'We may have found a matching donation for you',
			util.Template('match-suggested-email.txt').replace(replacements).content,
			html=util.Template('match-suggested-email.html').replace(replacements).content,
			to=my_offer.email
		)

	def process_found_matches(self, matches):
		for (offer1, offer2) in matches:
			if self._dry_run:
				logging.info('Doing nothing, because this is a dry run; offer1=%s; offer2=%s.', offer1, offer2)
				continue

			match_secret = donationswap.create_secret()

			if offer1.created_ts < offer2.created_ts:
				old_offer, new_offer = offer1, offer2
			else:
				old_offer, new_offer = offer2, offer1

			logging.info('Creating match between offers %s and %s.', new_offer.id, old_offer.id)
			with self._database.connect() as db:
				entities.Match.create(db, match_secret, new_offer.id, old_offer.id)

			self._send_mail_about_match(old_offer, new_offer, match_secret)
			self._send_mail_about_match(new_offer, old_offer, match_secret)

	def _send_mail_about_deal(self, old_offer, new_offer):
		old_amount_in_new_currency = self._currency.convert(
			old_offer.amount,
			old_offer.country.currency.iso,
			new_offer.country.currency.iso)
		new_amount_in_old_currency = self._currency.convert(
			new_offer.amount,
			new_offer.country.currency.iso,
			old_offer.country.currency.iso)

		tmp = entities.CharityInCountry.by_charity_and_country_id(new_offer.charity.id, new_offer.country.id)
		if tmp is not None:
			old_instructions = tmp.instructions
		else:
			old_instructions = 'Sorry, there are no instructions available (yet).'

		tmp = entities.CharityInCountry.by_charity_and_country_id(old_offer.charity.id, new_offer.country.id)
		if tmp is not None:
			new_instructions = tmp.instructions
		else:
			new_instructions = 'Sorry, there are no instructions available (yet).'

		replacements = {
			'{%OLD_NAME%}': '<xxx name not supported yet', #xxx old_offer.name,
			'{%OLD_COUNTRY%}': old_offer.country.name,
			'{%OLD_CHARITY%}': old_offer.charity.name,
			'{%OLD_AMOUNT%}': old_offer.amount,
			'{%OLD_CURRENCY%}': old_offer.country.currency.iso,
			'{%OLD_EMAIL%}': old_offer.email,
			'{%OLD_AMOUNT_CONVERTED%}': old_amount_in_new_currency,
			'{%OLD_INSTRUCTIONS%}': old_instructions,
			'{%NEW_NAME%}': '<xxx name not supported yet', #xxx new_offer.name,
			'{%NEW_COUNTRY%}': new_offer.country.name,
			'{%NEW_CHARITY%}': new_offer.charity.name,
			'{%NEW_AMOUNT%}': new_offer.amount,
			'{%NEW_CURRENCY%}': new_offer.country.currency.iso,
			'{%NEW_EMAIL%}': new_offer.email,
			'{%NEW_AMOUNT_CONVERTED%}': new_amount_in_old_currency,
			'{%NEW_INSTRUCTIONS%}': new_instructions,
		}

		logging.info('Sending deal email to %s and %s.', old_offer.email, new_offer.email)

		self._mail.send(
			'Here is your match!',
			util.Template('match-approved-email.txt').replace(replacements).content,
			html=util.Template('match-approved-email.html').replace(replacements).content,
			to=[old_offer.email, new_offer.email]
		)

	def process_approved_matches(self):
		approved_matches = entities.Match.get_all(lambda x: x.new_agrees and x.old_agrees)
		for match in approved_matches:
			if self._dry_run:
				logging.info('Doing nothing, because this is a dry run; match=%s.', match)
				continue

			self._send_mail_about_deal(match.old_offer, match.new_offer)
			#xxx do not delete completed match for 1 month
			#xxx make site with these instructions, put URL in email.
			with self._database.connect() as db:
				match.delete(db)

def main():
	util.setup_logging('log/matchmaker.txt')
	parser = argparse.ArgumentParser(description='The Match Maker.')
	parser.add_argument('config_path')
	parser.add_argument('--doit', action='store_true')
	parser.add_argument('--force-pair', '-fp', help='comma-separated pair of IDs for which "is match" is forced to True')
	args = parser.parse_args()

	if args.force_pair is not None:
		tmp = args.force_pair.split(',')
		args.force_pair = int(tmp[0]), int(tmp[1])

	matchmaker = Matchmaker(args.config_path, dry_run=not args.doit)

	matchmaker.clean()

	matches = matchmaker.find_matches()
	matchmaker.process_found_matches(matches)

	matchmaker.process_approved_matches()

if __name__ == '__main__':
	main()
