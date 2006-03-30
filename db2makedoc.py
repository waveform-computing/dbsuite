#!/usr/bin/env python
# $Header$
# vim: set noet sw=4 ts=4:

import logging
import db.database
import input.db2udbluw
import output.w3

def main():
	# Configure the output
	logging.basicConfig(level = logging.INFO)
	# Find a suitable connection library and create a database connection
	try:
		import DB2
		connection = DB2.Connection("DQSMS")
	except ImportError:
		import dbi
		import odbc
		connection = odbc.odbc("DQSMS/dave/St4rGate")
	try:
		logging.info("Building metadata cache")
		data = input.db2udbluw.Cache(connection)
		logging.info("Building database object hierarchy")
		database = db.database.Database(data, "DQSMS")
		logging.info("Writing output with w3 handler")
		output.w3.DocOutput(database, "../public_html/dqsms")
	finally:
		connection.close()
		connection = None

if __name__ == '__main__':
	main()
