# $Header$
# vim: set noet sw=4 ts=4:

import math

def quote_str(s, qchar="'"):
	return "%s%s%s" % (qchar, s.replace(qchar, qchar*2), qchar)

def format_size(value, for_sql=True):
	"""Formats sizes with standard K/M/G/T/etc. suffixes"""
	if value is None:
		return None
	elif value == 0:
		return str(value)
	else:
		power = math.log(value, 2)
		index = int(power / 10)
		if not for_sql or (value % (1024 ** index) == 0):
			if for_sql:
				suffix = ['', 'K', 'M', 'G', 'T', 'E', 'P'][index]
				size = value / (1024 ** index)
				return "%d%s" % (int(size), suffix)
			else:
				suffix = ['b', 'Kb', 'Mb', 'Gb', 'Tb', 'Eb', 'Pb'][index]
				size = float(value) / (1024 ** index)
				return "%.2f %s" % (size, suffix)
		else:
			return str(value)

def format_ident(value, ident_quotes='"'):
	"""Formats an identifier (an object name) for use in SQL, quoting as necessary"""
	identchars = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_$#@0123456789")
	firstchars = identchars - set("0123456789")
	if len(value) == 0:
		raise ValueError("Invalid identifier")
	if not value[0] in firstchars:
		return quote_str(value, ident_quotes)
	for c in value[1:]:
		if not c in identchars:
			return quote_str(value, ident_quotes)
	return value.upper()
