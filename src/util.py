#!/usr/bin/env python3

import grp
import logging
import os
import pwd
import re

def setup_logging(path):
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

	os.makedirs(os.path.dirname(path), mode=0o777, exist_ok=True)
	file_handler = logging.handlers.RotatingFileHandler(path, maxBytes=LOG_MAX_FILESIZE, backupCount=10)
	file_handler.setFormatter(formatter)
	file_handler.setLevel(level=logging.INFO)
	logger.addHandler(file_handler)

	console_handler = logging.StreamHandler()
	console_handler.setFormatter(formatter)
	console_handler.setLevel(level=logging.INFO)
	logger.addHandler(console_handler)

def daemonize(pidfile=None):
	'''Turns the current process into a daemon.
	If pidfile is set, it writes the process id to it.
	Returns the process id.'''

	logging.info('Daemonizing.')

	cwd = os.getcwd() # remember current working directory

	try:
		pid = os.fork()
	except OSError as e:
		raise Exception('%s [%d]' % (e.strerror, e.errno))

	if pid != 0:
		# pylint: disable=protected-access
		os._exit(0)

	os.setsid()

	try:
		pid = os.fork()
	except OSError as e:
		raise Exception('%s [%d]' % (e.strerror, e.errno))

	if pid != 0:
		# pylint: disable=protected-access
		os._exit(0)

	os.chdir('/')
	os.umask(0)

	os.open(os.devnull, os.O_RDWR) # standard input (0)
	os.dup2(0, 1) # sys.stdout > /dev/null
	os.dup2(0, 2) # sys.stderr > /dev/null

	pid = os.getpid()

	if pidfile is not None:
		with open(pidfile, 'w') as f:
			f.write('%s' % pid)

	os.chdir(cwd) # restore current working directory

	return pid

def drop_privileges(user='nobody', group='nogroup'):
	'''Changes the current process' user and group.'''

	logging.info('Dropping root privileges.')

	user = pwd.getpwnam(user)
	group = grp.getgrnam(group)
	os.setgroups([group.gr_gid])
	os.setgid(group.gr_gid)
	os.setuid(user.pw_uid)

def html_escape(txt):
	return txt.replace('<', '&lt;').replace('>', '&gt;')

class Template:

	def __init__(self, filename):
		self.content = self._load_file(filename)
		self.populate_file_references()

	@staticmethod
	def _load_file(filename):
		filename = os.path.join('templates', filename)

		if os.path.isfile(filename):
			with open(filename, encoding='utf-8', mode='r') as f:
				return f.read()
		else:
			return ''

	def populate_file_references(self):
		'''Replace all occurrences of `{%FILE=...%}` with the content of that file.
		This gets called automatically from the constructor,
		but for deep template structures you _might_ want to call it again.
		(In that case, you should rethink your structure because it's too deep.)'''

		def _replace(match):
			filename = match.groupdict()['filename']
			return self._load_file(filename)

		for _ in range(5): # doing only 5 rounds is easier than detecting nested recursion
			changed_content = re.sub(r'{%FILE=(?P<filename>.+?)%}', _replace, self.content)
			if changed_content == self.content:
				break
			self.content = changed_content

		return self

	def replace(self, replacements=None, **kwargs):
		if not isinstance(replacements, dict):
			replacements = {}

		replacements.update(kwargs)

		for k, v in replacements.items():
			self.content = self.content.replace(k, str(v))

		return self
