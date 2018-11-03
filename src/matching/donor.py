#!/usr/bin/env python3

class Donor:

	def __init__(self, email, country):
		self.email = email
		self.country = country

	def __str__(self):
		return self.email

	def __repr__(self):
		return self.__str__()