#!/usr/bin/env python3

from charity import *
from country import *
from donor import *
from offer import *
from swapmath import *

class Matcher:

	def __init__(self, baseCurrency):
		self.baseCurrency = baseCurrency

	def match(self, offer, all_offers):
		for existing in sorted(all_offers, key=lambda o : o.timeOffered):
			ourCountry = offer.donor.country
			theirCountry = existing.donor.country
			ourMultiplier = ourCountry.valueToCharityMultiplier * ourCountry.exchangeRateVsUSA
			theirMultiplier = theirCountry.valueToCharityMultiplier * theirCountry.exchangeRateVsUSA

			#trivial checks
			if ourMultiplier * offer.amountMin > theirMultiplier * existing.amountMax:
				continue
			if ourMultiplier * offer.amountMax < theirMultiplier * existing.amountMin:
				continue
			if ourCountry == theirCountry:
				continue

			charityTheyDonateToForUs = None
			charityWeDonateToForThem = None
			#check whether out target charity is deductable in the other country and vice versa
			for ourTarget in offer.targetCharities:
				if ourTarget in theirCountry.charities:
					charityTheyDonateToForUs = ourTarget
					if charityTheyDonateToForUs not in ourCountry.charities:
						break
			for theirTarget in existing.targetCharities:
				if theirTarget in ourCountry.charities:
					charityWeDonateToForThem = theirTarget
					if charityWeDonateToForThem not in theirCountry.charities:
						break
			if charityTheyDonateToForUs == None or charityWeDonateToForThem == None:
				continue

			#check whether we could DIY it anyway
			if charityTheyDonateToForUs in ourCountry.charities and charityWeDonateToForThem in theirCountry.charities:
				continue

			return SwapMath(
				charityA4B = charityWeDonateToForThem,
				charityB4A = charityTheyDonateToForUs,
				amountCharitiesGet = min(ourMultiplier * offer.amountMax, theirMultiplier * existing.amountMax),
				baseCurrency = self.baseCurrency,
				offerA = offer,
				offerB = existing
			)
		return None