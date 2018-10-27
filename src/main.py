#!/usr/bin/env python3

import argparse
import json
import logging
import os
import ssl
import sys

import tornado.httpserver # `sudo pip3 install tornado`
import tornado.ioloop
import tornado.web

import donationswap
import util

def _set_default_headers(self):
	# Don't reveal which webserver we're using. It's a security thing.
	# This way (as opposed to overriding `set_default_headers()`)
	# also works for the default error handlers.
	self.set_header('Server', 'DonationSwapServer')

tornado.web.RequestHandler.set_default_headers = _set_default_headers

class BaseHandler(tornado.web.RequestHandler):

	def initialize(self, logic):
		self.logic = logic # pylint: disable=attribute-defined-outside-init

class CertbotHandler(BaseHandler):
	'''
	sudo certbot renew --webroot --webroot-path /srv/web/static/
	'''

	def get(self, secret):
		filename = os.path.join('static', '.well-known', 'acme-challenge', secret)
		with open(filename, 'rb') as f:
			response = f.read()
		self.set_header('Content-Type', 'text/plain')
		self.write(response)

class HttpRedirectHandler(BaseHandler):

	def initialize(self, https_port):
		self.https_port = https_port

	def prepare(self):
		if self.request.protocol == 'http':
			url = 'https://%s' % self.request.host
			if self.https_port != 443:
				url += ':%s' % self.https_port
			self.redirect(url, permanent=False)

class AjaxHandler(BaseHandler):

	def post(self, action):
		payload = json.loads(self.request.body.decode('utf-8'))

		result = self.logic.run_ajax(action, self.request.remote_ip, payload)

		self.set_header('Content-Type', 'application/json; charset=utf-8')
		self.write(json.dumps(result))

class TemplateHandler(BaseHandler):

	def initialize(self, logic, page_name):
		# pylint: disable=attribute-defined-outside-init
		self.logic = logic
		self._page_name = page_name

	def get(self):
		page = self.logic.get_page(self._page_name)
		if page:
			self.set_header('Content-Type', 'text/html; charset=utf-8')
			self.write(page)
		else:
			self.set_status(404)
			self.write('404 File Not Found')

def start(port=443, daemonize=True, http_redirect_port=None):
	if port < 1024 and not os.getuid() == 0:
		print('Port %s requires root permissions.' % port, file=sys.stderr)
		sys.exit(1)

	util.setup_logging('log/web.txt')

	if http_redirect_port is not None:
		logging.info('Redirecting http://:%s to https://:%s', http_redirect_port, port)
		tornado.web.Application([
			(r'/.well-known/acme-challenge/(.+)', CertbotHandler),
			(r'/.*', HttpRedirectHandler, {'https_port': port})
		]).listen(http_redirect_port)

	logic = donationswap.Donationswap('app-config.json')

	def args(kv=None):
		result = {
			'logic': logic,
		}
		if kv:
			result.update(kv)
		return result

	application = tornado.web.Application(
		[
			(r'/', TemplateHandler, args({'page_name': 'index.html'})),
			(r'/ajax/(.+)', AjaxHandler, args()),
			(r'/contact/?', TemplateHandler, args({'page_name': 'contact.html'})),
			(r'/faq/?', TemplateHandler, args({'page_name': 'faq.html'})),
			(r'/match/?', TemplateHandler, args({'page_name': 'match.html'})),
			(r'/offer/?', TemplateHandler, args({'page_name': 'offer.html'})),
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
