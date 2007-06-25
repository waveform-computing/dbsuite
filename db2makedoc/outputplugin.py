# $Header$
# vim: set noet sw=4 ts=4:

import sys
import logging

class OutputPlugin(object):
	def __init__(self, database, config):
		"""Initializes an instance of the class.

		The database parameter passed to the constructor represents the
		database that the plugin is to build documentation for. From this
		object other objects representing all relations, indexes, etc. in the
		database can be reached.

		The config parameter contains a dictionary of values with the plugin
		configuration, as obtained from the configuration file specified by the
		user on the command line.

		The constructor is expected to immediately build the documentation with
		these two pieces of information (the class constructor is effectively
		nothing more than a function - in fact an output plugin can just as
		well be implemented as a function taking the same parameters; provided
		it is callable the main application won't care).
		"""
		super(OutputPlugin, self).__init__()
