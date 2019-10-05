#!/usr/bin/env python3

import datetime
from email.mime.application import MIMEApplication

import config
import mail
import donationswap

'''
xxx do not hardcode paths
'''
CONFIG_FILENAME = '/srv/web/app-config.json'
CONFIG = config.Config(CONFIG_FILENAME)

def send_mail(msg, to, filename, data):
	m = mail.Mail(CONFIG.email_user, CONFIG.email_password, CONFIG.email_smtp, CONFIG.email_sender_name)

	smtp_msg = m._prepare_msg('Donation Swap Stats Update', msg, msg, to, None, None)

	part = MIMEApplication(data, Name=filename)
	part['Content-Disposition'] = 'attachment; filename="' + filename + '"'
	smtp_msg.attach(part)

	m._send_msg(smtp_msg)

def makeData(data):
	compiledData = "date match generated, USD value, charity1, country1, charity2, country2\n"

	for match in data:
		compiledData += "{}, {}, {}, {}, {}, {}\n".format(match['created_ts'], match['value'], match['details']['new_offer_charity'], match['details']['new_offer_country'], match['details']['old_offer_charity'], match['details']['old_offer_country'])

	return compiledData

if __name__ == "__main__":
	swapper = donationswap.Donationswap(CONFIG_FILENAME)

	nowYear = datetime.date.today().year
	nowMonth = datetime.date.today().month
	lastMonth = nowMonth - 1
	lastYear = nowYear
	if (lastMonth <= 0):
		lastMonth += 12
		lastYear -= 1

	min_timestamp = "{0}-{1:0>2}-01".format(lastYear, lastMonth)
	max_timestamp = "{0}-{1:0>2}-01".format(nowYear, nowMonth)

	# cache issues?
	swapper._currency._read_live()

	data = swapper.read_log_stats(None, min_timestamp, max_timestamp, 0, 1000000)['data']

	filename = "StatsUpdate-{}-{}.csv".format(lastMonth, lastYear)

	send_mail(
		"See Attached: '" + filename + "'",
		CONFIG.contact_message_receivers['to'],
		filename,
		makeData(data))

