#!/usr/bin/env python3

class Matchmaker:

	def __init__(self, database):
		self._database = database

	def find_match(self, offer_id):
		'''Returns the id of a matching offer, or None.'''

		#xxx offer must not have expired yet
		#xxx offer must not be in another undeclined match
		#xxx offer must have different charity
		#xxx offer must have different country
		#xxx offer should have approximately the same amount (taking tax benefits into account)

		with self._database.connect() as db:
			for row in db.read('SELECT * offer'):
				pass #xxx

		return None
