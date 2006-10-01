#!/usr/bin/env python
# $Header$
# vim: set noet sw=4 ts=4:

import sys
mswindows = sys.platform == "win32"

# Standard modules
import optparse
import ConfigParser
import logging
import fnmatch
import os
import imp
import textwrap

__version__ = "0.1"

def main():
	# Parse the command line arguments
	usage = "%prog [options]"
	version = "%%prog %s Database Documentation Generator" % (__version__,)
	parser = optparse.OptionParser(usage=usage, version=version)
	parser.set_defaults(
		config=None,
		listplugins=None,
		plugin=None,
		logfile="",
		loglevel=logging.WARNING)
	parser.add_option("-c", "--config", dest="config",
		help="""specify the configuration file from which to read settings""")
	parser.add_option("-q", "--quiet", dest="loglevel", action="store_const", const=logging.ERROR,
		help="""produce less console output""")
	parser.add_option("-v", "--verbose", dest="loglevel", action="store_const", const=logging.INFO,
		help="""produce more console output""")
	parser.add_option("-l", "--log-file", dest="logfile",
		help="""log messages to the specified file""")
	parser.add_option("", "--help-plugins", dest="listplugins", action="store_true",
		help="""list the available input and output plugins""")
	parser.add_option("", "--help-plugin", dest="plugin",
		help="""display information about the specified plugin""")
	(options, args) = parser.parse_args()
	# Check for list/help actions
	if options.listplugins:
		list_plugins()
		return
	elif options.plugin:
		help_plugin(options.plugin)
		return
	# Check the options
	if len(args) > 0:
		parser.error("you may not specify any filenames")
	if options.database is None:
		parser.error("you must specify a database with --database or -d")
	if not options.username:
		logging.info("Username not specified, using implicit login")
	elif not options.password:
		parser.error("Username was specified, but password was not (try running again with --pass)")
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
		import db.database
		import input.db2udbluw
		import output.html.w3
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
			data = input.db2udbluw.Input(connection)
			logging.info("Building database object hierarchy")
			database = db.database.Database(data, options.database)
			logging.info("Writing output with w3 handler")
			output.html.w3.Output(database, options.outputpath)
		finally:
			connection.close()
			connection = None
	except Exception, e:
		logging.error(str(e))
		raise
		sys.exit(1)
	else:
		sys.exit(0)

def list_plugins():
	"""Pretty-print a list of the available input and output plugins."""
	import input
	tw = textwrap.TextWrapper()
	tw.initial_indent = ' '*8
	tw.subsequent_indent = tw.initial_indent
	print "Available Input Plugins:"
	for (name, plugin) in plugins(input):
		print ' '*4 + name
		print tw.fill(plugin.__doc__.split('\n')[0])
	import output
	print ""
	print "Available Output Plugins:"
	for (name, plugin) in plugins(output):
		print ' '*4 + name
		print tw.fill(plugin.__doc__.split('\n')[0])

def help_plugin(plugin_name):
	"""Pretty-print some help text for the specified plugin."""
	plugin = load_plugin(plugin_name)
	print "Name:\n    %s\n" % plugin_name
	tw = textwrap.TextWrapper()
	tw.initial_indent = ' '*4
	tw.subsequent_indent = tw.initial_indent
	plugin_desc = '\n\n'.join(tw.fill(para) for para in plugin.__doc__.split('\n\n'))
	print "Description:\n%s\n" % plugin_desc
	if hasattr(plugin, 'options'):
		print "Options:"
		tw.initial_indent = ' '*8
		tw.subsequent_indent = tw.initial_indent
		for (option_name, option_desc) in plugin.options.iteritems():
			print ' '*4 + option_name
			print tw.fill(option_desc)

def is_input_plugin(module):
	"""Determines whether the specified module is an input plugin.

	A module is an input plugin if it exports a callable (function or class
	definition) called Input.
	"""
	return hasattr(module, 'Input') and callable(module.Input)

def is_output_plugin(module):
	"""Determines whether the specified module is an output plugin.

	A module is an output plugin if it exports a callable (function or class
	definition) called Output.
	"""
	return hasattr(module, 'Output') and callable(module.Output)

def is_plugin(module):
	"""Determines whether the specified module is a plugin of either kind."""
	return is_input_plugin(module) or is_output_plugin(module)

def plugins(root, name=None):
	"""Generator returning all input and output plugins in a package.

	Given a root package (root), this generator function recursively searches
	all paths in the package for modules which contain a callable (function or
	class definition) named Input or Output. It yields a 2-tuple containing the
	plugin's fully qualified module name and the module itself.
	"""
	if name is None:
		name = root.__name__
	path = os.path.sep.join(root.__path__)
	files = os.listdir(path)
	dirs = [
		i for i in files
		if os.path.isdir(os.path.join(path, i)) and i != 'CVS'
	]
	files = [
		i[:-3] for i in fnmatch.filter(files, '*.py')
		if os.path.isfile(os.path.join(path, i)) and i != '__init__.py'
	]
	# Deal with file-based modules first
	for f in files:
		try:
			(modfile, modpath, moddesc) = imp.find_module(f, root.__path__)
			try:
				m = imp.load_module(f, modfile, modpath, moddesc)
			finally:
				# Caller is responsible for closing the file object returned by
				# find_module()
				if isinstance(modfile, file) and not modfile.closed:
					modfile.close()
		except ImportError:
			continue
		if is_plugin(m):
			yield ('%s.%s' % (name, f), m)
	# Then deal with directory-based modules (packages)
	for d in dirs:
		try:
			(modfile, modpath, moddesc) = imp.find_module(d, root.__path__)
			# modfile will be None in the case of a directory module so there's
			# no need to close() it
			m = imp.load_module(d, modfile, modpath, moddesc)
		except ImportError:
			continue
		if is_plugin(m):
			yield ('%s.%s' % (name, d), m)
		# Recursively call ourselves with the directory module
		for (n, m) in plugins(m, '%s.%s' % (name, m.__name__)):
			yield (n, m)

def load_plugin(name):
	"""Given an absolute name, load an input or output plugin."""
	root = None
	parts = name.split('.')
	for p in parts:
		try:
			(modfile, modpath, moddesc) = imp.find_module(p, root)
			try:
				module = imp.load_module(p, modfile, modpath, moddesc)
				if hasattr(module, '__path__'):
					root = module.__path__
			finally:
				# Caller is responsible for closing the file object returned by
				# find_module()
				if isinstance(modfile, file) and not modfile.closed:
					modfile.close()
		except ImportError:
			raise Exception('Unable to locate or load plugin %s' % name)
	if not is_plugin(module):
		raise Exception('Module %s does not appear to be an input or output plugin' % name)
	return module

if __name__ == '__main__':
	try:
		# Use Psyco, if available
		import psyco
		psyco.full()
	except ImportError:
		pass
	main()
