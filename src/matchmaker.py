#!/usr/bin/env python3

class Matchmaker:

	def _send_mail_about_match_feedback(self, match):
		replacements = {
		}

		#xxx

		logging.info('Sending match feedback email to %s and %s',
			match.old_offer.email,
			match.new_offer.email,
		)

	def _delete_old_matches(self):
		'''Four weeks after a match was made we delete it and
		send the two donors a feedback email.

		(It only gets to be four weeks old if it was accepted by both
		donors, otherwise it would have been deleted within 72 hours.)'''

		four_weeks_ago = datetime.datetime.utcnow() - datetime.timedelta(days=28)

		with self._database.connect() as db:
			for match in entities.Match.get_all(lambda x: x.new_agrees is True and x.old_agrees is True and x.created_ts < four_weeks_ago):
				match.delete(db)
				self._send_mail_about_match_feedback(match)

	def clean(self):
		#xxx self._delete_unconfirmed_offers()
		#xxx self._delete_unapproved_matches()
		self._delete_old_matches()

		now = datetime.datetime.utcnow()
		one_week = datetime.timedelta(days=7)

		with self._database.connect() as db:

			# delete unapproved matches after one week
			for match in entities.Match.get_all(lambda x: (x.new_agrees is None or x.old_agrees is None) and x.created_ts + one_week < now):
				eventlog.match_expired(db, match)
				match.delete(db)

			#xxx also...
			# ... delete expired offers that aren't part of a match

#xxx move this into donationswap.py when I understand it

import entities

from matching.charity import Charity
from matching.country import Country
from matching.donor import Donor
from matching.offer import Offer
from matching.matcher import Matcher

def _is_good_match(self, offer1, offer2):

	dbCountry1 = offer1.country
	dbCountry2 = offer2.country

	# TODO: UK and ireland(?) GiftAid
	multiplier1 = 1
	multiplier2 = 1

	exchangeRate1VsUSA = self._currency.convert(1000, dbCountry1.currency.iso, 'USD') / 1000.0
	exchangeRate2VsUSA = self._currency.convert(1000, dbCountry2.currency.iso, 'USD') / 1000.0

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
		if (charityInCountry1 is not None):
			country1Charities.append(charityCache[charity.name])
			if (offer1.charity == charity):
				country1TaxReturn = charityInCountry1.tax_factor

		if (charityInCountry2 is not None):
			country2Charities.append(charityCache[charity.name])
			if (offer2.charity == charity):
				country2TaxReturn = charityInCountry2.tax_factor

	country1 = Country(dbCountry1.name, dbCountry1.currency.iso, country1Charities, country1TaxReturn, exchangeRate1VsUSA, multiplier1)
	country2 = Country(dbCountry2.name, dbCountry2.currency.iso, country2Charities, country2TaxReturn, exchangeRate2VsUSA, multiplier2)

	offer1Created = 0
	offer2Created = 0
	amount1 = offer1.amount
	amount2 = offer2.amount
	donor1 = Donor(offer1.name, offer1.email, country1)
	donor2 = Donor(offer2.name, offer2.email, country2)

	#xxx offers SHOULD have approximately the same amount (taking tax benefits into account)
	#    for development, however, everthing goes.
	matchingOffer1 = Offer(donor1, amount1 * 0.5, amount1, [charityCache[offer1.charity.name]], offer1Created)
	matchingOffer2 = Offer(donor2, amount2 * 0.5, amount2, [charityCache[offer2.charity.name]], offer2Created)

	result = Matcher('USD').match(matchingOffer1, [matchingOffer2])
	return result is not None
