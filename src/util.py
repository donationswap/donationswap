#!/usr/bin/env python3

import grp
import logging
import os
import pwd
import re

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
