#!/usr/bin/env python3

from charity import *
from country import *
from donor import *
from offer import *

class SwapMath():

	def __init__(self, charityA4B, charityB4A, charityGetAmount, offerA, offerB):
		self.charityADonatingToForB = charityA4B
		self.charityBDonatingToForA = charityB4A

		self.amountCharitiesGet = charityGetAmount

		self.donorA = offerA.donor
		self.donorB = offerB.donor

		self.countryAExchangeVsUSA = offerA.donor.country.exchangeRateVsUSA
		self.countryBExchangeVsUSA = offerB.donor.country.exchangeRateVsUSA

		#thank you UK
		self.countryAValueToCharityMultipler = offerA.donor.country.valueToCharityMultiplier
		self.countryBValueToCharityMultipler = offerB.donor.country.valueToCharityMultiplier

		self.amountAPays = charityGetAmount / offerA.donor.country.exchangeRateVsUSA / offerA.donor.country.valueToCharityMultiplier
		self.amountBPays = charityGetAmount / offerB.donor.country.exchangeRateVsUSA / offerB.donor.country.valueToCharityMultiplier

		self.taxReturnForA = self.amountAPays * offerA.donor.country.taxReturn
		self.taxReturnForB = self.amountBPays * offerB.donor.country.taxReturn

	def GetSummary(self):
		maths = "Charities {charity1} and {charity2} get {totalBase} {baseCurrency} each.\n".format(
			charity1 = self.charityADonatingToForB.name,
			charity2 = self.charityBDonatingToForA.name,
			totalBase = self.amountCharitiesGet,
			baseCurrency = "USD"
		)

		personTemplate1 = "{name} will pay {pay} {currency} to {charity}.\n"
		maths += personTemplate1.format(
			name = self.donorA.email,
			pay = self.amountAPays,
			currency = "NZD",
			charity = self.charityADonatingToForB
		)
		maths += personTemplate1.format(
			name = self.donorB.email,
			pay = self.amountBPays,
			currency = "USD",
			charity = self.charityBDonatingToForA
		)

		personTemplate2 = "{name} should recieve about {taxBack} {currency} in Tax Returns.\n"
		maths += personTemplate2.format(
			name = self.donorA.email,
			taxBack = self.taxReturnForA,
			currency = "NZD"
		)
		maths += personTemplate2.format(
			name = self.donorB.email,
			pay = self.taxReturnForB,
			currency = "USD"
		)

		return maths

	def __str__(self):
		return "Swap for " + str(self.amountCharitiesGet)

	def __repr__(self):
		return self.__str__()