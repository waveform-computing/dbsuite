#!/usr/bin/env python
# $Header$
# vim: set noet sw=4 ts=4:

import sys
mswindows = sys.platform == "win32"

import optparse
import ConfigParser
import logging

import db.database
import input.db2udbluw
import output.w3

__version__ = "0.1"

def main():
	# Parse the command line arguments
	usage = "%prog [options] scripts..."
	version = "%%prog %s" % (__version__,)
	parser = optparse.OptionParser(usage=usage, version=version)
	parser.set_defaults(
		database="",
		username="",
		password="",
		outputpath=".",
		logfile="",
		loglevel=logging.WARNING)
	parser.add_option("-d", "--database", dest="database",
		help="""specify the locally cataloged name of the database to create documentation for""")
	parser.add_option("-u", "--user", dest="username",
		help="""specify the name of the user used to connect to the database""")
	parser.add_option("-p", "--pass", dest="password",
		help="""specify the password of the user given by --user""")
	parser.add_option("-q", "--quiet", dest="loglevel", action="store_const", const=logging.ERROR,
		help="""produce less console output""")
	parser.add_option("-v", "--verbose", dest="loglevel", action="store_const", const=logging.INFO,
		help="""produce more console output""")
	parser.add_option("-l", "--log-file", dest="logfile",
		help="""log messages to the specified file""")
	parser.add_option("-o", "--output", dest="outputpath",
		help="""specify the directory to write output to""")
	(options, args) = parser.parse_args()
	if len(args) > 0:
		parser.error("you may not specify any filenames")
	# Set up some logging objects
	console = logging.StreamHandler(sys.stderr)
	console.setFormatter(logging.Formatter('%(message)s'))
	console.setLevel(options.loglevel)
	logging.getLogger().addHandler(console)
	if options.logfile:
		logfile = logging.FileHandler(options.logfile)
		logfile.setFormatter(logging.Formatter('%(asctime)s, %(levelname)s, %(message)s'))
		logfile.setLevel(logging.INFO) # Log file always logs at INFO level
		logging.getLogger().addHandler(logfile)
	logging.getLogger().setLevel(logging.DEBUG)
	try:
		# Check the options
		if not options.username:
			logging.info("Username not specified, using implicit login")
		elif not options.password:
			raise Exception("Username was specified, but password was not (try running again with --pass)")
		# Find a suitable connection library and create a database connection
		try:
			import DB2
			if options.username:
				connection = DB2.Connection(options.database, options.username, options.password)
			else:
				connection = DB2.Connection(options.database)
		except ImportError:
			import dbi
			import odbc
			if options.username:
				connection = odbc.odbc("%s/%s/%s" % (options.database, options.username, options.password))
			else:
				connection = odbc.odbc(options.database)
		# Build the output
		# XXX Add configuration options to allow use of different input and
		# output layers
		try:
			logging.info("Building metadata cache")
			data = input.db2udbluw.Cache(connection)
			logging.info("Building database object hierarchy")
			database = db.database.Database(data, options.database)
			logging.info("Writing output with w3 handler")
			output.w3.DocOutput(database, options.outputpath)
		finally:
			connection.close()
			connection = None
	except Exception, e:
		logging.error(str(e))
		sys.exit(1)
	else:
		sys.exit(0)

if __name__ == '__main__':
	try:
		# Use Psyco, if available
		import psyco
		psyco.full()
	except ImportError:
		pass
	main()
