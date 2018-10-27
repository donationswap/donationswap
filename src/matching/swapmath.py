#!/usr/bin/env python3

from charity import *
from country import *
from donor import *
from offer import *

class SwapMath():

	def __init__(self, charityA4B, charityB4A, amountCharitiesGet, offerA, offerB):
		self.charityADonatingToForB = charityA4B
		self.charityBDonatingToForA = charityB4A

		self.amountCharitiesGet = amountCharitiesGet

		self.offerA = offerA
		self.offerB = offerB

		self.countryAExchangeVsUSA = offerA.donor.country.exchangeRateVsUSA
		self.countryBExchangeVsUSA = offerB.donor.country.exchangeRateVsUSA

		#thank you UK
		self.countryAValueToCharityMultipler = offerA.donor.country.valueToCharityMultiplier
		self.countryBValueToCharityMultipler = offerB.donor.country.valueToCharityMultiplier

		self.amountAPays = amountCharitiesGet / offerA.donor.country.exchangeRateVsUSA / offerA.donor.country.valueToCharityMultiplier
		self.amountBPays = amountCharitiesGet / offerB.donor.country.exchangeRateVsUSA / offerB.donor.country.valueToCharityMultiplier

		self.taxReturnForA = self.amountAPays * offerA.donor.country.taxReturn
		self.taxReturnForB = self.amountBPays * offerB.donor.country.taxReturn

	def GetSummary(self):
		summary = "Charities {charity1} and {charity2} get {totalBase} {baseCurrency} each.\n".format(
			charity1 = self.charityADonatingToForB.name,
			charity2 = self.charityBDonatingToForA.name,
			totalBase = self.amountCharitiesGet,
			baseCurrency = "USD"
		)

		personTemplate1 = "{name} will pay {pay} {currency} to {charity}.\n"
		summary += personTemplate1.format(
			name = self.offerA.donor.email,
			pay = self.amountAPays,
			currency = "NZD",
			charity = self.charityADonatingToForB
		)
		summary += personTemplate1.format(
			name = self.offerB.donor.email,
			pay = self.amountBPays,
			currency = "USD",
			charity = self.charityBDonatingToForA
		)

		personTemplate2 = "{name} should recieve about {taxBack} {currency} in Tax Returns.\n"
		summary += personTemplate2.format(
			name = self.offerA.donor.email,
			taxBack = self.taxReturnForA,
			currency = "NZD"
		)
		summary += personTemplate2.format(
			name = self.offerB.donor.email,
			pay = self.taxReturnForB,
			currency = "USD"
		)

		return summary

	def GetMathHtml(self):
		template = ""
		# todo handle UK stuff
		with open("../templates/donation_calculation.html") as f:
			template = f.read()
		return template.format(
			totalBase = self.amountCharitiesGet,
			baseCurrency = "USD",
			person1 = self.offerA.donor.email,
			person2 = self.offerB.donor.email,
			country1ExchangeRate = self.countryAExchangeVsUSA,
			country2ExchangeRate = self.countryBExchangeVsUSA,
			amount1Pays = self.amountAPays,
			amount2Pays = self.amountBPays,
			country1Currency = "C1D",
			country2Currency = "C2D",
			country1TaxReturn = self.offerA.donor.country.taxReturn,
			country2TaxReturn = self.offerB.donor.country.taxReturn,
			taxReturnForDonor1 = self.taxReturnForA,
			taxReturnForDonor2 = self.taxReturnForB
		)

	def __str__(self):
		return "Swap for " + str(self.amountCharitiesGet)

	def __repr__(self):
		return self.__str__()

	def __eq__(self, other):
		return \
			self.amountAPays == other.amountAPays and \
			self.amountBPays == other.amountBPays and \
			self.amountCharitiesGet == other.amountCharitiesGet and \
			self.charityADonatingToForB == other.charityADonatingToForB and \
			self.charityBDonatingToForA == other.charityBDonatingToForA and \
			self.countryAExchangeVsUSA == other.countryAExchangeVsUSA and \
			self.countryAValueToCharityMultipler == other.countryAValueToCharityMultipler and \
			self.countryBExchangeVsUSA == other.countryBExchangeVsUSA and \
			self.countryBValueToCharityMultipler == other.countryBValueToCharityMultipler and \
			self.offerA == other.offerA and \
			self.offerB == other.offerB and \
			self.taxReturnForA == other.taxReturnForA and \
			self.taxReturnForB == other.taxReturnForB
