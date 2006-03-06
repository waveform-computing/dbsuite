#!/bin/env python
# $Header$
# vim: set noet sw=4 ts=4:

import re
import time
import datetime
import math

__all__ = ['makeDateTime', 'makeBoolean']

def makeDateTime(value):
	"""Converts a date-time value from a database query to a datetime object"""
	if (value is None) or (value == ""):
		return None
	elif type(value) == type(""):
		return datetime.datetime(*(int(x) for x in re.match(r"(\d{4})-(\d{2})-(\d{2})-(\d{2}).(\d{2}).(\d{2}).(\d{6})\d*", value).groups()))
	elif hasattr(value, 'value') and (type(value.value) == int):
		return datetime.datetime.fromtimestamp(value.value)
	else:
		raise ValueError("Unable to convert date-time value")

def makeBoolean(value, trueValue='Y', falseValue='N', noneValue=' ', unknownError=False, unknownResult=None):
	"""Converts a character-based value into a boolean value"""
	try:
		return {trueValue: True, falseValue: False, noneValue: None}[value]
	except KeyError:
		if unknownError:
			raise
		else:
			return unknownResult

def formatSize(value, precisePowers=True):
	"""Formats sizes with standard K/M/G/T/etc. suffixes"""
	power = math.log(value, 2)
	if not precisePowers or (power == int(power)):
		suffix = ['', 'K', 'M', 'G', 'T', 'E', 'P'][int(power / 10)]
		size = value / (2 ** ((int(power) / 10) * 10))
		if precisePowers:
			return "%d%s" % (int(size), suffix)
		else:
			return "%f%s" % (size, suffix)
	else:
		return str(value)
	

def main():
	pass

if __name__ == "__main__":
	main()
