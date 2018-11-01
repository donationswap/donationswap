#!/usr/bin/env python3

import entities
import currency
import matching

class Matchmaker:

	def __init__(self, database, currency):
		self._database = database
		self._currency = currency

		self._entities = None
		self._charityCache = {}
		self._countryCache = {}

	def find_match(self, offer_id):
		'''Returns the id of a matching offer, or None.'''

		# offer MUST not have expired yet
		# offer MUST not be in another undeclined match
		# offer MUST have different charity
		# offer MUST have different country
		# offer MUST have different email address
		# offer SHOULD have approximately the same amount (taking tax benefits into account)
		# (See https://www.ietf.org/rfc/rfc2119.txt for "MUST" and "SHOULD")

		# TODO: Smart Caching
		self._entities = entities.Entities(self._database)

		charities = self._entities.charities()
		countries = self._entities.countries()
		offers = [] #self._entities.offers()

		allOffers = []

		print("CHARITIES")
		for charityToBuild in charities:
			print(charityToBuild)

		print("COUNTRIES")
		for countryToBuild in countries:
			print(countryToBuild)

		print("OFFERS")
		for offerToBuild in offers:
			print(offerToBuild)

		with self._database.connect() as db:
			thisOfferToBuild = db.read_one('SELECT * FROM offers WHERE id = %(id)s ', id=offer_id)
			thisOffer = None

		matching_offer = matching.matcher.Matcher("USD").match(thisOffer, allOffers)

		# TODO: finish implementation
		# fallback to marc's stuff

		# for now, let's just return a random offer
		with self._database.connect() as db:
			matching_offer = db.read_one('SELECT * FROM offers WHERE id != %(id)s ', id=offer_id)
		if matching_offer is not None:
			return matching_offer['id']

		return None
