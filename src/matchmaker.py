#!/usr/bin/env python3

class Matchmaker:

	def __init__(self, database):
		self._database = database

	def find_match(self, offer_id):
		'''Returns the id of a matching offer, or None.'''

		# offer MUST not have expired yet
		# offer MUST not be in another undeclined match
		# offer MUST have different charity
		# offer MUST have different country
		# offer MUST have different email address
		# offer SHOULD have approximately the same amount (taking tax benefits into account)
		# (See https://www.ietf.org/rfc/rfc2119.txt for "MUST" and "SHOULD")

		# for now, let's just return a random offer
		with self._database.connect() as db:
			matching_offer = db.read_one('SELECT * FROM offers WHERE id != %(id)s ', id=offer_id)
		if matching_offer is not None:
			return matching_offer['id']

		return None
