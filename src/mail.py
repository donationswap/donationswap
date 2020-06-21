#!/usr/bin/env python3

import email.mime.multipart
import email.mime.text
import logging
import smtplib
import threading

class Mail: # pylint: disable=too-few-public-methods

	def __init__(self, user, password, smtp_host, from_address, sender_name=None):
		self._user = user
		self._password = password
		self._smtp_host = smtp_host
		self._sender_name = sender_name
		self._from_address = from_address

	@staticmethod
	def _populate(msg, key, value):
		if value is not None:
			if isinstance(value, list):
				msg[key] = ', '.join(value)
			else:
				msg[key] = value

	def _prepare_msg(self, subject, text, html, to, cc, bcc):
		if html is None:
			msg = email.mime.text.MIMEText(text)
		else:
			msg = email.mime.multipart.MIMEMultipart('alternative')
			msg.attach(email.mime.text.MIMEText(text, 'plain'))
			msg.attach(email.mime.text.MIMEText(html, 'html'))

		if self._sender_name:
			self._populate(msg, 'From', '%s <%s>' % (self._sender_name, self._from_address))
		else:
			self._populate(msg, 'From', self._from_address)

		self._populate(msg, 'Subject', subject)
		self._populate(msg, 'To', to)
		self._populate(msg, 'Cc', cc)
		self._populate(msg, 'Bcc', bcc)

		return msg

	def _send_msg(self, msg):
		with smtplib.SMTP(self._smtp_host) as s:
			s.starttls()
			s.login(user=self._user, password=self._password)
			s.send_message(msg)

	def send(self, subject, text, html=None, to=None, cc=None, bcc=None, send_async=True):
		msg = self._prepare_msg(subject, text, html, to, cc, bcc)

		logging.info('Sending email. to=%s, cc=%s, bcc=%s.', to, cc, bcc)

		if send_async:
			threading.Thread(target=self._send_msg, args=(msg,)).start()
		else:
			self._send_msg(msg)
