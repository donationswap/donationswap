#!/usr/bin/env python3

import datetime

import donationswap

CONFIG_FILENAME = '/srv/web/app-config.json'

if __name__ == "__main__":
	swapper = donationswap.Donationswap(CONFIG_FILENAME)

	nowYear = datetime.date.today().year
	nowMonth = datetime.date.today().month
	lastMonth = nowMonth - 1
	lastYear = nowYear
	if (lastMonth <= 0) :
		lastMonth += 12
		lastYear -= 1

	min_timestamp = "{0}-{1:0>2}-01".format(nowYear, nowMonth)
	max_timestamp = "{0}-{1:0>2}-01".format(lastYear, lastMonth)

	data = swapper.read_log_stats(None, min_timestamp, max_timestamp, 0, 1000000)

	print(data)