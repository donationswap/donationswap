#!/usr/bin/env python3

import argparse

import donationswap
import entities

def main():
	logic = donationswap.Donationswap('app-config.json')
	logic.automation_mode = True

	parser = argparse.ArgumentParser()
	sub_parsers = parser.add_subparsers()

	create_offer_parser = sub_parsers.add_parser('+offer')
	create_offer_parser.add_argument('-n', '--name', help='The preferred name of the donor', required=True)
	create_offer_parser.add_argument('-c', '--country', help='The ISO name of the country', required=True)
	create_offer_parser.add_argument('-e', '--email', help='The email address of the donor', required=True)
	create_offer_parser.add_argument('-a', '--amount', required=True, type=int)
	create_offer_parser.add_argument('--min-amount', type=int)
	create_offer_parser.add_argument('--charity', help='The full name of the charity', required=True)
	create_offer_parser.add_argument('--auto-confirm', help='The new offer will be confirmed', action='store_true')
	def create_offer_handler(args):
		country = entities.Country.by_iso_name(args.country)
		if country is None:
			raise ValueError('"%s" is not the ISO code of a supported country.' % args.country)
		if args.min_amount is None:
			args.min_amount = round(args.amount / 2)
		charity = entities.Charity.by_name(args.charity)
		print('Creating offer:')
		print('   Name: %s' % args.name)
		print('   Country: %s' % args.country)
		print('   Amount: %s %s' % (args.amount, country.currency.iso))
		print('   MinAmount: %s %s' % (args.min_amount, country.currency.iso))
		print('   Email: %s' % args.email)
		offer = logic.create_offer(
			captcha_response=None,
			name=args.name,
			country=country.id,
			amount=args.amount,
			min_amount=args.min_amount,
			charity=charity.id,
			email=args.email,
			expiration={
				'day': 31,
				'month': 12,
				'year': 2200, # this will cause problems eventually, but we'll be dead by then
			}
		)
		if args.auto_confirm:
			logic.confirm_offer(offer.secret)
		print('   Secret: %s' % offer.secret)
		print('   ID: %s' % offer.id)
	create_offer_parser.set_defaults(func=create_offer_handler)

	all_args = parser.parse_args()
	if getattr(all_args, 'func', None) is None:
		parser.print_help()
	else:
		all_args.func(all_args)

if __name__ == '__main__':
	main()
