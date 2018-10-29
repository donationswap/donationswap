#!/usr/bin/env python3

class Country:

	def __init__(self, name, currency, charities, taxReturn, exchangeRateVsUSA, valueToCharityMultiplier = 1):
		self.name = name
		self.currency = currency
		self.charities = charities
		self.taxReturn = taxReturn
		self.exchangeRateVsUSA = exchangeRateVsUSA
		self.valueToCharityMultiplier = valueToCharityMultiplier

	def __str__(self):
		return self.name

	def __repr__(self):
		return self.__str__()