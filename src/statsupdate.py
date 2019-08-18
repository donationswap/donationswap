#!/usr/bin/env python3

import datetime

import config
import mail
import donationswap

CONFIG_FILENAME = '/srv/web/app-config.json'

def send_mail(msg, to, filename):
	cfg = config.Config(CONFIG_FILENAME)
	m = mail.Mail(cfg.email_user, cfg.email_password, cfg.email_smtp, cfg.email_sender_name)
	m.send('Donation Swap Stats Update', msg, to=to, send_async=False)

def makeFile(filename, data):
	fileData = "date match generated, USD value, charity1, country1, charity2, country2\n"

	for match in data:
		fileData += "{}, {}, {}, {}, {}, {}\n".format(match['created_ts'], match['value'], match['details']['new_offer_charity'], match['details']['new_offer_country'], match['details']['old_offer_charity'], match['details']['old_offer_country'])

	FILE = open(filename, 'w')
	FILE.write(fileData)
	FILE.close()

if __name__ == "__main__":
	swapper = donationswap.Donationswap(CONFIG_FILENAME)

	nowYear = datetime.date.today().year
	nowMonth = datetime.date.today().month
	lastMonth = nowMonth - 1
	lastYear = nowYear
	if (lastMonth <= 0):
		lastMonth += 12
		lastYear -= 1

	min_timestamp = "{0}-{1:0>2}-01".format(nowYear, nowMonth)
	max_timestamp = "{0}-{1:0>2}-01".format(lastYear, lastMonth)

	data = swapper.read_log_stats(None, min_timestamp, max_timestamp, 0, 1000000)['data']

	filename = "StatsUpdate-{}-{}.csv".format(nowMonth, nowYear)
	makeFile(filename, data)

	print(data)
	print()
	#send_mail("Testing!", ["j.lallu25@gmail.com"], filename)