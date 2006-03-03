#!/usr/bin/env python
# $Header$
# vim: set noet sw=4 ts=4:

import logging
import docdatabase
import docoutput_w3

def main():
	# Configure the output
	logging.basicConfig(level = logging.INFO)
	# Find a suitable connection library and create a database connection
	try:
		import DB2
		conn = DB2.Connection("DQSMS")
	except ImportError:
		import dbi
		import odbc
		conn = odbc.odbc("DQSMS/dave/St4rGate")
	try:
		docoutput_w3.DocOutput(docdatabase.DocDatabase("DQSMS", conn), "../public_html/dqsms")
	finally:
		conn.close()
		conn = None

if __name__ == '__main__':
	main()
