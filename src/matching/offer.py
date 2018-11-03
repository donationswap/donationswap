#!/usr/bin/env python3

class Offer:

	def __init__(self, donor, amountMin, amountMax, targetCharities, timeOffered):
		self.donor = donor
		self.amountMin = amountMin
		self.amountMax = amountMax
		self.targetCharities = targetCharities
		self.timeOffered = timeOffered

	def __str__(self):
		return "Offer from " + str(self.amountMin) + " to " + str(self.amountMax)

	def __repr__(self):
		return self.__str__()