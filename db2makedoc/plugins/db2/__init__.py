# vim: set noet sw=4 ts=4:

"""Generic utility routines for the db2.* input plugins"""

import sys
mswindows = sys.platform.startswith('win')
import locale
import codecs
import logging
import datetime
import re

__all__ = ['connect', 'make_str', 'make_int', 'make_bool', 'make_datetime']

def connect(dsn, username=None, password=None):
	"""Create a connection to the specified database.

	This utility method attempts to connect to the database named by dsn using
	the (optional) username and password provided. The method attempts to use a
	variety of connection frameworks (PyDB2, pyodbc, IBM's official DB2 driver,
	PythonWin's ODBC stuff and mxODBC) depending on the underlying platform.

	Note that the queries in the methods below are written to be agnostic to
	the quirks of the various connection frameworks (e.g. PythonWin's ODBC
	module doesn't correctly handle certain dates hence why all DATE and
	TIMESTAMP fields are CAST to CHAR in the queries below).
	"""
	logging.info('Connecting to database "%s"' % dsn)
	# Try the PyDB2 driver
	try:
		import DB2
	except ImportError:
		pass
	else:
		logging.info('Using PyDB2 driver')
		if username is not None:
			return DB2.connect(dsn, username, password)
		else:
			return DB2.connect(dsn)
	# Try the pyodbc driver
	try:
		import pyodbc
	except ImportError:
		pass
	else:
		logging.info('Using pyodbc driver')
		# XXX Check whether escaping/quoting is required
		# XXX Should there be a way to specify the driver name? Given that on
		# unixODBC the driver alias is specified in odbcinst.ini, and on
		# Windows with DB2 9+ one can have multiple DB2 ODBC drivers installed
		# with differentiating suffixes
		if username is not None:
			return pyodbc.connect('driver=IBM DB2 ODBC DRIVER;dsn=%s;uid=%s;pwd=%s' % (dsn, username, password))
		else:
			return pyodbc.connect('driver=IBM DB2 ODBC DRIVER;dsn=%s' % dsn)
	# Try the "official" IBM DB2 Python driver (but avoid it if possible)
	try:
		import ibm_db
		import ibm_db_dbi
		# XXX Shut the "official" driver up (stupid warnings)
		ibm_db_dbi.logger.setLevel(logging.ERROR)
	except ImportError:
		pass
	else:
		logging.info('Using IBM DB2 Python driver')
		if username is not None:
			return ibm_db_dbi.connect(dsn, username, password)
		else:
			return ibm_db_dbi.connect(dsn)
	# Try the mxODBC driver
	try:
		import mx.ODBC
	except ImportError:
		pass
	else:
		logging.info('Using mxODBC driver')
		# XXX Check whether escaping/quoting is required
		# XXX See discussion about driver names above
		if username is not None:
			connectstr = 'driver=IBM DB2 ODBC DRIVER;dsn=%s;uid=%s;pwd=%s' % (dsn, username, password)
		else:
			connectstr = 'driver=IBM DB2 ODBC DRIVER;dsn=%s' % dsn
		if mswindows:
			import mx.ODBC.Windows
			return mx.ODBC.Windows.DriverConnect(connectstr)
		else:
			import mx.ODBC.iODBC
			return mx.ODBC.iODBC.DriverConnect(connectstr)
	# Try the PythonWin ODBC driver
	try:
		import dbi
		import odbc
	except ImportError:
		pass
	else:
		logging.info('Using PyWin32 odbc driver')
		if username is not None:
			# XXX Check whether escaping/quoting is required
			return odbc.odbc("%s/%s/%s" % (dsn, username, password))
		else:
			return odbc.odbc(dsn)
	raise ImportError('Unable to find a suitable connection framework; please install PyDB2, pyodbc, PyWin32, or mxODBC')

decoder = codecs.getdecoder(locale.getpreferredencoding(False))
def make_str(value):
	"""Converts a string into a unicode object.

	If value is None, returns None. If the value is a string, uses the encoding
	obtained from the current locale to decode the string into a Unicode
	object.  This is because the DB2 driver defaults to using the locale
	according to the LANG environment variable, regardless of the application's
	locale, while Python always defaults to decoding ASCII regardless of locale
	resulting in problems with non-ASCII characters occuring in output from by
	DB2.
	"""
	if value is None:
		return None
	elif isinstance(value, unicode):
		return value
	elif isinstance(value, basestring):
		return decoder(value)[0]
	else:
		raise ValueError('Invalid string value %s' % repr(value))

def make_int(value):
	"""Converts a numeric value into an integer / long.

	If value is None, returns None. If the value is a string, refuse to convert
	it. Otherwise performs a straight int() conversion on value.
	"""
	if value is None:
		return None
	elif isinstance(value, basestring):
		raise ValueError('Invalid integer value %s' % repr(value))
	else:
		return int(value)

def make_datetime(value):
	"""Converts a date-time value from a database query to a datetime object.

	If value is None or a blank string, returns None. If value is a string
	containing an ISO8601 formatted date ("YYYY-MM-DD HH:MM:SS.NNNNNN") it is
	converted to a standard Python datetime value. If value is has a integer
	"value" attribute it is assumed to be a UNIX timestamp and is converted
	into a Python datetime value.

	Basically this routine exists to convert a database framework-specific
	representation of a datetime value into a standard Python datetime value.
	"""
	if value is None:
		return None
	elif isinstance(value, datetime.datetime):
		return value
	elif isinstance(value, datetime.date):
		return datetime.datetime.combine(value, datetime.time.min)
	elif isinstance(value, basestring):
		return datetime.datetime(*([int(x) for x in re.match(r'(\d{4})-(\d{2})-(\d{2})[T -](\d{2})[:.](\d{2})[:.](\d{2})\.(\d{6})\d*', value).groups()]))
	elif hasattr(value, 'value') and isinstance(value.value, int):
		return datetime.datetime.fromtimestamp(value.value)
	else:
		raise ValueError('Invalid date-time value %s' % repr(value))

def make_bool(value, true_value='Y', false_value='N', none_value=' ', unknown_error=False, unknown_result=None):
	"""Converts a character-based value into a boolean value.

	If value equals true_value, false_value, or none_value return true, false,
	or None respectively. If it matches none of them and unknown_error is false
	(the default), returns unknown_result (defaults to None).  Otherwise if
	unknown_error is true, the a KeyError is raised.
	"""
	try:
		return {true_value: True, false_value: False, none_value: None}[value]
	except KeyError:
		if unknown_error:
			raise ValueError('Invalid boolean value %s' % repr(value))
		else:
			return unknown_result

