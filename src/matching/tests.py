#!/usr/bin/env python3

import unittest
import datetime
from charity import *
from country import *
from donor import *
from matcher import *
from offer import *
from swapmath import *

def secondsSinceEpoch():
	return (datetime.datetime.utcnow() - datetime.datetime.utcfromtimestamp(0)).total_seconds()

class Tests(unittest.TestCase):

	def setUp(self):
		self.charity_amf = Charity("Against Malaria Foundation")
		self.charity_gfi = Charity("Good Food Institute")

		#exchange rates set to 1 for the base tests
		self.country_NZ = Country('New Zealand', 'NZD', [self.charity_amf], 0.33, 1)
		self.country_USA = Country('USA', 'USD', [self.charity_amf, self.charity_gfi], 0.30, 1)
		self.country_UK = Country('UK', 'GBP', [self.charity_amf, self.charity_gfi], 0.2, 1, 1.25)
		
		self.donor_NZ = Donor('nz.user@notAnEmail.com', self.country_NZ)
		self.donor_USA = Donor('us.user@notAnEmail.com', self.country_USA)
		self.donor_UK = Donor('uk.user@notAnEmail.com', self.country_UK)

		self.trivial_offer_NZ = Offer(self.donor_NZ, 100, 200, [self.charity_amf, self.charity_gfi], 1539398365.377)
		self.trivial_offer_USA = Offer(self.donor_USA, 100, 200, [self.charity_amf, self.charity_gfi], 1539398365.377)
		self.trivial_offer_UK = Offer(self.donor_UK, 100, 200, [self.charity_amf, self.charity_gfi], 1539398365.377)

		self.SetupSwapMathResults()

	def tearDown(self):
		pass

	def test_trivialMatch(self):
		offer = Offer(self.donor_USA, 150, 150, [self.charity_amf, self.charity_gfi], secondsSinceEpoch())
		match = Matcher("USD").match(offer, [self.trivial_offer_NZ])
		self.assertEqual(match, SwapMath(self.charity_gfi, self.charity_amf, 150, "USD", offer, self.trivial_offer_NZ))

	def test_trivialMatchTheOtherWay(self):
		offer = Offer(self.donor_USA, 150, 150, [self.charity_amf, self.charity_gfi], secondsSinceEpoch())
		match = Matcher("USD").match(self.trivial_offer_NZ, [offer])
		self.assertEqual(match, SwapMath(self.charity_amf, self.charity_gfi, 150, "USD", self.trivial_offer_NZ, offer))

	def test_dontMatchIfNoTaxSaving(self):
		someOtherCharity = Charity("Some Other Charity")
		someNZParrelell = Country('New Zealand2', 'NZD', [someOtherCharity], 0.33, 1)
		donorFromNZParrellell = Donor('nz2.user@notAnEmail.com', someNZParrelell)
		offer1 = Offer(self.donor_NZ, 150, 150, [self.charity_gfi], secondsSinceEpoch())
		offer2 = Offer(donorFromNZParrellell, 150, 150, [self.charity_amf], secondsSinceEpoch())
		match = Matcher("USD").match(offer1, [offer2])
		self.assertEqual(match, None)

	def test_dontMatchIfNoTaxSavingTheOtherWay(self):
		someOtherCharity = Charity("Some Other Charity")
		someNZParrelell = Country('New Zealand2', 'NZD', [someOtherCharity], 0.33, 1)
		donorFromNZParrellell = Donor('nz2.user@notAnEmail.com', someNZParrelell)
		offer1 = Offer(self.donor_NZ, 150, 150, [self.charity_gfi], secondsSinceEpoch())
		offer2 = Offer(donorFromNZParrellell, 150, 150, [self.charity_amf], secondsSinceEpoch())
		match = Matcher("USD").match(offer2, [offer1])
		self.assertEqual(match, None)

	def test_tooSmall(self):
		offer = Offer(self.donor_USA, 75, 75, [self.charity_amf, self.charity_gfi], secondsSinceEpoch())
		match = Matcher("USD").match(offer, [self.trivial_offer_NZ])
		self.assertEqual(match, None)

	def test_tooSmallTheOtherWay(self):
		offer = Offer(self.donor_USA, 75, 75, [self.charity_amf, self.charity_gfi], secondsSinceEpoch())
		match = Matcher("USD").match(self.trivial_offer_NZ, [offer])
		self.assertEqual(match, None)

	def test_tooBig(self):
		offer = Offer(self.donor_USA, 250, 250, [self.charity_amf, self.charity_gfi], secondsSinceEpoch())
		match = Matcher("USD").match(offer, [self.trivial_offer_NZ])
		self.assertEqual(match, None)

	def test_tooBigTheOtherWay(self):
		offer = Offer(self.donor_USA, 250, 250, [self.charity_amf, self.charity_gfi], secondsSinceEpoch())
		match = Matcher("USD").match(self.trivial_offer_NZ, [offer])
		self.assertEqual(match, None)

	def test_emptyIsFine(self):
		offer = Offer(self.donor_USA, 150, 150, [self.charity_amf, self.charity_gfi], secondsSinceEpoch())
		match = Matcher("USD").match(offer, [])
		self.assertEqual(match, None)

	def test_takeTheEarliestAvailable(self):
		offer1 = Offer(self.donor_USA, 150, 150, [self.charity_amf, self.charity_gfi], secondsSinceEpoch())
		offer2 = Offer(self.donor_NZ, 150, 150, [self.charity_gfi], secondsSinceEpoch())
		offer3 = Offer(self.donor_NZ, 150, 150, [self.charity_gfi], secondsSinceEpoch() - 1)
		match = Matcher("USD").match(offer1, [offer2, offer3])
		self.assertEqual(match, SwapMath(self.charity_gfi, self.charity_amf, 150, "USD", offer1, offer3))

	def test_dontMatchIfDIYJustAsGood(self):
		offer1 = Offer(self.donor_USA, 100, 200, [self.charity_amf, self.charity_gfi], secondsSinceEpoch())
		offer2 = Offer(self.donor_UK, 100, 200, [self.charity_amf, self.charity_gfi], secondsSinceEpoch())
		match = Matcher("USD").match(offer1, [offer2])
		self.assertEqual(match, None)

	def test_matchAfterNoDIYJustAsGood(self):
		offer1 = Offer(self.donor_USA, 100, 200, [self.charity_amf, self.charity_gfi], secondsSinceEpoch())
		offer2 = Offer(self.donor_UK, 100, 200, [self.charity_amf, self.charity_gfi], secondsSinceEpoch())
		offer3 = Offer(self.donor_NZ, 100, 200, [self.charity_gfi], secondsSinceEpoch())
		match = Matcher("USD").match(offer1, [offer2, offer3])
		self.assertEqual(match, SwapMath(self.charity_gfi, self.charity_amf, 200, "USD", offer1, offer3))

	def test_matchAfterNoMatch(self):
		offer1 = Offer(self.donor_USA, 150, 150, [self.charity_amf, self.charity_gfi], secondsSinceEpoch())
		offer2 = Offer(self.donor_NZ, 151, 151, [self.charity_gfi], secondsSinceEpoch())
		offer3 = Offer(self.donor_NZ, 150, 150, [self.charity_gfi], secondsSinceEpoch())
		match = Matcher("USD").match(offer1, [offer2, offer3])
		self.assertEqual(match, SwapMath(self.charity_gfi, self.charity_amf, 150, "USD", offer1, offer3))

	def test_trivialMatchWithUKFunk(self):
		offer = Offer(self.donor_UK, 120, 120, [self.charity_amf, self.charity_gfi], secondsSinceEpoch())
		match = Matcher("USD").match(offer, [self.trivial_offer_NZ])
		self.assertEqual(match, SwapMath(self.charity_gfi, self.charity_amf, 150, "USD", offer, self.trivial_offer_NZ))

	def test_trivialMatchWithUKFunkTheOtherWay(self):
		offer = Offer(self.donor_UK, 120, 120, [self.charity_amf, self.charity_gfi], secondsSinceEpoch())
		match = Matcher("USD").match(self.trivial_offer_NZ, [offer])
		self.assertEqual(match, SwapMath(self.charity_amf, self.charity_gfi, 150, "USD", self.trivial_offer_NZ, offer))

	def test_noMatchBecauseUKFunk(self):
		offer = Offer(self.donor_UK, 180, 180, [self.charity_amf, self.charity_gfi], secondsSinceEpoch())
		match = Matcher("USD").match(offer, [self.trivial_offer_NZ])
		self.assertEqual(match, None)

	def test_noMatchBecauseUKFunkTheOtherWay(self):
		offer = Offer(self.donor_UK, 180, 180, [self.charity_amf, self.charity_gfi], secondsSinceEpoch())
		match = Matcher("USD").match(self.trivial_offer_NZ, [offer])
		self.assertEqual(match, None)

	def test_noMatchBecauseExchangeRates(self):
		someNZParrelell = Country('New Zealand3', 'NZD', [self.charity_amf], 0.33, 0.65)
		donorFromNZParrellell = Donor('nz3.user@notAnEmail.com', someNZParrelell)
		offer = Offer(donorFromNZParrellell, 150, 150, [self.charity_gfi], secondsSinceEpoch())
		match = Matcher("USD").match(offer, [self.trivial_offer_USA])
		self.assertEqual(match, None)

	def test_noMatchBecauseExchangeRatesTheOtherWay(self):
		someNZParrelell = Country('New Zealand3', 'NZD', [self.charity_amf], 0.33, 0.65)
		donorFromNZParrellell = Donor('nz3.user@notAnEmail.com', someNZParrelell)
		offer = Offer(donorFromNZParrellell, 150, 150, [self.charity_gfi], secondsSinceEpoch())
		match = Matcher("USD").match(self.trivial_offer_USA, [offer])
		self.assertEqual(match, None)

	def test_matchRespectsExchangeRates(self):
		someNZParrelell = Country('New Zealand3', 'NZD', [self.charity_amf], 0.33, 0.65)
		donorFromNZParrellell = Donor('nz3.user@notAnEmail.com', someNZParrelell)
		offer = Offer(donorFromNZParrellell, 200, 200, [self.charity_gfi], secondsSinceEpoch())
		match = Matcher("USD").match(offer, [self.trivial_offer_USA])
		self.assertEqual(match, SwapMath(self.charity_amf, self.charity_gfi, 130, "USD", offer, self.trivial_offer_USA))

	def test_matchRespectsExchangeRatesTheOtherWay(self):
		someNZParrelell = Country('New Zealand3', 'NZD', [self.charity_amf], 0.33, 0.65)
		donorFromNZParrellell = Donor('nz3.user@notAnEmail.com', someNZParrelell)
		offer = Offer(donorFromNZParrellell, 200, 200, [self.charity_gfi], secondsSinceEpoch())
		match = Matcher("USD").match(self.trivial_offer_USA, [offer])
		self.assertEqual(match, SwapMath(self.charity_gfi, self.charity_amf, 130, "USD", self.trivial_offer_USA, offer))

	def test_noMatchBecauseUSADoesntLikeAMF(self):
		offer = Offer(self.donor_USA, 150, 150, [self.charity_gfi], secondsSinceEpoch())
		match = Matcher("USD").match(offer, [self.trivial_offer_NZ])
		self.assertEqual(match, None)

	def test_noMatchBecauseUSADoesntLikeAMFTheOtherWay(self):
		offer = Offer(self.donor_USA, 150, 150, [self.charity_gfi], secondsSinceEpoch())
		match = Matcher("USD").match(self.trivial_offer_NZ, [offer])
		self.assertEqual(match, None)

# SwapMath Tests
	def SetupSwapMathResults(self):
		self.swapMathSummary = """Charities Good Food Institute and Against Malaria Foundation get 130 USD each.
us.user@notAnEmail.com will pay 130 USD to Good Food Institute.
nz3.user@notAnEmail.com will pay 200.0 NZD to Against Malaria Foundation.
us.user@notAnEmail.com should recieve about 39.0 USD in Tax Returns.
nz3.user@notAnEmail.com should recieve about 66.0 NZD in Tax Returns.
"""
		self.swapMathMathHtml = """<table>
	<tbody>
		<th>Maths</th>
		<tr>
			<td>Total to Charity:</td>
			<td>130 USD</td>
		</tr>
		<tr>
			<td></td>
			<th>us.user@notAnEmail.com</th>
			<th>nz3.user@notAnEmail.com</th>
		</tr>charity1
		<tr>
			<td>Charty to Donate to</td>
			<td>Good Food Institute</td>
			<td>Against Malaria Foundation</td>
		</tr>
		<tr>
			<td>Exchange Rates</td>
			<td>1</td>
			<td>0.65</td>
		</tr>
		<tr>
			<td>Amount To Pay</td>
			<td>total USD * exchange rate = total to pay in USD<br />
				130 USD * 1 = 130 USD</td>
			<td>total USD * exchange rate = total to pay in NZD<br />
				130 USD * 0.65 = 200.0 NZD</td>
		</tr>
		<tr>
			<td>Tax Return</td>
			<td>amount to pay * tax rate = tax return<br />
				130 USD * 0.3 = 39.0 USD</td>
			<td>amount to pay * tax rate = tax return<br />
				200.0 NZD * 0.33 = 66.0 NZD</td>
		</tr>
	</tbody>
</table>"""

	def test_SwapMathSummary(self):
		someNZParrelell = Country('New Zealand3', 'NZD', [self.charity_amf], 0.33, 0.65)
		donorFromNZParrellell = Donor('nz3.user@notAnEmail.com', someNZParrelell)
		offer = Offer(donorFromNZParrellell, 200, 200, [self.charity_gfi], secondsSinceEpoch())
		swapMath = SwapMath(self.charity_gfi, self.charity_amf, 130, "USD", self.trivial_offer_USA, offer)
		self.assertEqual(swapMath.GetSummary(), self.swapMathSummary)

	def test_SwapMathMathHtml(self):
		someNZParrelell = Country('New Zealand3', 'NZD', [self.charity_amf], 0.33, 0.65)
		donorFromNZParrellell = Donor('nz3.user@notAnEmail.com', someNZParrelell)
		offer = Offer(donorFromNZParrellell, 200, 200, [self.charity_gfi], secondsSinceEpoch())
		swapMath = SwapMath(self.charity_gfi, self.charity_amf, 130, "USD", self.trivial_offer_USA, offer)
		self.assertEqual(swapMath.GetMathHtml(), self.swapMathMathHtml)

if __name__ == '__main__':
	unittest.main()