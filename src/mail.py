#!/usr/bin/env python3

import email.mime.multipart
import email.mime.text
import logging
import smtplib

import config

def _populate(msg, key, value):
	if value is not None:
		if isinstance(value, list):
			msg[key] = ', '.join(value)
		else:
			msg[key] = value

def send_email(subject, text, html=None, to=None, cc=None, bcc=None):
	try:
		if html is None:
			msg = email.mime.text.MIMEText(text)
		else:
			msg = email.mime.multipart.MIMEMultipart('alternative')
			msg.attach(email.mime.text.MIMEText(text, 'plain'))
			msg.attach(email.mime.text.MIMEText(html, 'html'))

		_populate(msg, 'From', config.email_user)
		_populate(msg, 'Subject', subject)
		_populate(msg, 'To', to)
		_populate(msg, 'Cc', cc)
		_populate(msg, 'Bcc', bcc)

		with smtplib.SMTP(config.email_sender) as s:
			s.starttls()
			s.login(user=config.email_user, password=config.email_password)
			s.send_message(msg)

		return True

	except Exception: # pylint: disable=broad-except
		logging.error('Error sending email: subject="%s", text="%s", to="%s", cc="%s", bcc="%s".', subject, text, to, cc, bcc)
		return False
