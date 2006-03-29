#!/bin/env python
# $Header$
# vim: set noet sw=4 ts=4:

import math

def quoteStr(s, qchar="'"):
	return "%s%s%s" % (qchar, s.replace(qchar, qchar*2), qchar)

def formatSize(value, precisePowers=True):
	"""Formats sizes with standard K/M/G/T/etc. suffixes"""
	power = math.log(value, 2)
	index = int(power / 10)
	if not precisePowers or (value % (1024 ** index) == 0):
		suffix = ['', 'K', 'M', 'G', 'T', 'E', 'P'][index]
		size = value / (1024 ** index)
		if precisePowers:
			return "%d%s" % (int(size), suffix)
		else:
			return "%f%s" % (size, suffix)
	else:
		return str(value)

def formatIdentifier(value):
	"""Formats an identifier (an object name) for use in SQL, quoting as necessary"""
	identchars = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_$#@0123456789")
	firstchars = identchars - set("0123456789")
	if len(value) == 0:
		raise ValueError("Invalid identifier")
	if not value[0] in firstchars:
		return quoteStr(value, '"')
	for c in value[1:]:
		if not c in identchars:
			return quoteStr(value, '"')
	return value.upper()

def main():
	pass

if __name__ == "__main__":
	main()
