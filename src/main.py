#!/usr/bin/env python3

import argparse
import logging
import os
import ssl
import sys

import tornado.httpserver # `sudo pip3 install tornado`
import tornado.ioloop
import tornado.web

import donationswap
import util


def setup_logging():
	LOG_MAX_FILESIZE = 2**20 # 1 MB

	class CustomFormatter(logging.Formatter):
		def __init__(self):
			super(CustomFormatter, self).__init__(fmt='%(asctime)s', datefmt='%Y-%m-%d %H:%M:%S')

		def formatMessage(self, record):
			fmt = '%(asctime)s %(levelname)-8s %(pathname)s:%(lineno)s %(message)s'
			return fmt % record.__dict__

	logger = logging.getLogger()
	logger.setLevel(level=logging.DEBUG)
	formatter = CustomFormatter()

	file_handler = logging.handlers.RotatingFileHandler('log/web.txt', maxBytes=LOG_MAX_FILESIZE, backupCount=10)
	file_handler.setFormatter(formatter)
	file_handler.setLevel(level=logging.INFO)
	logger.addHandler(file_handler)

	console_handler = logging.StreamHandler()
	console_handler.setFormatter(formatter)
	console_handler.setLevel(level=logging.INFO)
	logger.addHandler(console_handler)


def _set_default_headers(self):
	# Don't reveal which webserver we're using. It's a security thing.
	# This way (as opposed to overriding `set_default_headers()`)
	# also works for error handlers.
	self.set_header('Server', 'DonationSwapServer')

tornado.web.RequestHandler.set_default_headers = _set_default_headers


class HttpRedirectHandler(tornado.web.RequestHandler):

	def initialize(self, https_port):
		self.https_port = https_port

	def prepare(self):
		if self.request.protocol == 'http':
			url = 'https://%s' % self.request.host
			if self.https_port != 443:
				url += ':%s' % self.https_port
			self.redirect(url, permanent=False)


class Handler(tornado.web.RequestHandler):

	def initialize(self, logic):
		self.logic = logic # pylint: disable=attribute-defined-outside-init


class MainHandler(Handler):

	def get(self, *args, **kwargs):
		page = self.logic.get_home_page(self.request.remote_ip)

		self.set_header('Content-Type', 'text/html; charset=utf-8')
		self.write(page)


class StartHandler(Handler):

	def get(self, *args, **kwargs):
		page = self.logic.get_start_page(self.request.remote_ip)

		self.set_header('Content-Type', 'text/html; charset=utf-8')
		self.write(page)

	def post(self, *args, **kwargs):
		page = self.logic.get_start_page(
			self.request.remote_ip,
			country=self.get_body_argument('country'),
			amount=self.get_body_argument('amount'),
			charity=self.get_body_argument('charity')
		)

		self.set_header('Content-Type', 'text/html; charset=utf-8')
		self.write(page)


def start(port=443, daemonize=True, http_redirect_port=None):
	setup_logging()
	print(http_redirect_port)

	if port < 1024 and not os.getuid() == 0:
		print('Port %s requires root permissions.' % port, file=sys.stderr)
		sys.exit(1)

	if http_redirect_port is not None:
		logging.info('Redirecting http://:%s to https://:%s', http_redirect_port, port)
		tornado.web.Application([
			(r'/.*', HttpRedirectHandler, {'https_port': port})
		]).listen(http_redirect_port)

	dependencies = {
		'logic': donationswap.Donationswap(),
	}

	application = tornado.web.Application(
		[
			(r'/', MainHandler, dependencies),
			(r'/start/?', StartHandler, dependencies),
		],
		static_path=os.path.join(os.path.dirname(__file__), 'static'),
	)

	if os.path.exists('/etc/letsencrypt/live/donationswap.eahub.org/privkey.pem'):
		ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
		ssl_context.load_cert_chain(
			'/etc/letsencrypt/live/donationswap.eahub.org/fullchain.pem',
			'/etc/letsencrypt/live/donationswap.eahub.org/privkey.pem'
		)
	else:
		logging.warning('SSL Certificate not found. Traffic will NOT be encrypted.')
		ssl_context = None

	logging.info('Starting webserver.')

	server = tornado.httpserver.HTTPServer(application, ssl_options=ssl_context)

	server.listen(port)

	if daemonize:
		util.daemonize('/var/run/webserver.pid')

	if os.geteuid() == 0: # we don't need root privileges any more
		util.drop_privileges()

	tornado.ioloop.IOLoop.current().start()

def main():
	parser = argparse.ArgumentParser(description='The Web Server.')
	parser.add_argument('--port', '-p', type=int, default=443)
	parser.add_argument('--daemonize', '-d', action='store_true')
	parser.add_argument('--no-http-redirect', action='store_true')
	args = parser.parse_args()

	start(
		port=args.port,
		daemonize=args.daemonize,
		http_redirect_port=None if args.no_http_redirect else 80
	)

if __name__ == '__main__':
	main()
