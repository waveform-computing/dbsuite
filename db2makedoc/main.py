# vim: set noet sw=4 ts=4:

import sys
import optparse
import ConfigParser
import logging
import fnmatch
import os
import imp
import locale
import textwrap
import traceback
import db2makedoc.db
import db2makedoc.plugins
from db2makedoc.util import *

__version__ = "1.0.0"

# Use the user's default locale instead of C
locale.setlocale(locale.LC_ALL, '')

# Formatting strings
if not sys.platform.startswith('win') and hasattr(sys.stdout, 'isatty') and sys.stdout.isatty():
	BOLD = '\x1b[1m'
	NORMAL = '\x1b[0m'
	RED = '\x1b[31m'
	GREEN = '\x1b[32m'
	BLUE = '\x1b[34m'
else:
	BOLD = ''
	NORMAL = ''
	RED = ''
	GREEN = ''
	BLUE = ''

def main(args=None):
	if args is None:
		args = sys.argv[1:]
	# Parse the command line arguments
	parser = optparse.OptionParser(
		usage='%prog [options] configs...',
		version='%%prog %s Database Documentation Generator' % __version__,
		description="""\
This utility generates documentation (in a variety of formats) from the system
catalog in IBM DB2 databases. At least one configuration file (an INI-style
file) must be specified. See the documentation for more information on the
required syntax and content of this file. The available command line options
are listed below.""")
	parser.set_defaults(
		debug=False,
		test=False,
		config=None,
		listplugins=False,
		plugin=None,
		logfile='',
		loglevel=logging.WARNING
	)
	parser.add_option('-q', '--quiet', dest='loglevel', action='store_const', const=logging.ERROR,
		help="""produce less console output""")
	parser.add_option('-v', '--verbose', dest='loglevel', action='store_const', const=logging.INFO,
		help="""produce more console output""")
	parser.add_option('-l', '--log-file', dest='logfile',
		help="""log messages to the specified file""")
	parser.add_option('', '--help-plugins', dest='listplugins', action='store_true',
		help="""list the available input and output plugins""")
	parser.add_option('', '--help-plugin', dest='plugin',
		help="""display information about the the specified plugin""")
	parser.add_option('-n', '--dry-run', dest='test', action='store_true',
		help="""test a configuration without actually executing anything""")
	parser.add_option('-D', '--debug', dest='debug', action='store_true',
		help="""enables debug mode (runs db2makedoc under PDB)""")
	(options, args) = parser.parse_args(args)
	# Set up some logging stuff
	console = logging.StreamHandler(sys.stderr)
	console.setFormatter(logging.Formatter('%(message)s'))
	console.setLevel(options.loglevel)
	logging.getLogger().addHandler(console)
	if options.logfile:
		logfile = logging.FileHandler(options.logfile)
		logfile.setFormatter(logging.Formatter('%(asctime)s, %(levelname)s, %(message)s'))
		logfile.setLevel(logging.DEBUG)
		logging.getLogger().addHandler(logfile)
	# Set up the exceptions hook for uncaught exceptions and the logging
	# levels if --debug was given
	if options.debug:
		console.setLevel(logging.DEBUG)
		logging.getLogger().setLevel(logging.DEBUG)
	else:
		logging.getLogger().setLevel(logging.INFO)
		sys.excepthook = production_excepthook
	# Call one of the action routines depending on the options
	if options.listplugins:
		list_plugins()
	elif options.plugin:
		help_plugin(options.plugin)
	elif len(args) == 0:
		parser.error('You must specify at least one configuration file')
	elif options.test:
		test_config(args)
	elif options.debug:
		import pdb
		pdb.runcall(make_docs, args)
	else:
		make_docs(args)

def production_excepthook(type, value, tb):
	"""Exception hook for non-debug mode."""
	# I/O errors and plugin errors should be simple to solve - no need to
	# bother the user with a full stack trace, just the error message will
	# suffice. Same for user interrupts
	if issubclass(type, (IOError, KeyboardInterrupt, db2makedoc.plugins.PluginError)):
		logging.critical(str(value))
	else:
		# Otherwise, log the stack trace and the exception into the log file
		# for debugging purposes
		for line in traceback.format_exception(type, value, tb):
			for s in line.rstrip().split('\n'):
				logging.critical(s)
	# Pass a failure exit code to the calling shell
	sys.exit(1)

def process_config(config_file):
	"""Parses and prepares plugins from a configuration file.

	The config_file parameter specifies a configuration filename, or file-like
	object to process. The routine parses each section in the configuration,
	constructing and configuring the plugin specified by each. The routine
	returns a 2-tuple of (inputs, outputs). "inputs" and "outputs" are lists of
	2-tuples of (section-name, plugin) where "section-name" is the name of a
	section, and "plugin" is the constructed and configured plugin object.
	"""
	parser = ConfigParser.SafeConfigParser()
	if isinstance(config_file, basestring):
		if not parser.read(config_file):
			raise IOError('Failed to read configuration file "%s"' % config_file)
	elif hasattr(config_file, 'read'):
		parser.readfp(config_file)
		if hasattr(config_file, 'name'):
			config_file = config_file.name
		else:
			config_file = '<unknown>'
	logging.info('Reading configuration file "%s"' % config_file)
	# Sort sections into inputs and outputs, which are lists containing
	# (section, module) tuples, where module is the module containing the
	# plugin specified by the section.
	inputs = []
	outputs = []
	for section in parser.sections():
		logging.info('Reading section [%s]' % section)
		if not parser.has_option(section, 'plugin'):
			raise db2makedoc.plugins.PluginConfigurationError('No "plugin" value found')
		plugin_name = parser.get(section, 'plugin')
		try:
			plugin_module = load_plugin(plugin_name)
		except ImportError, e:
			raise db2makedoc.plugins.PluginLoadError('Plugin "%s" failed to load: %s' % (plugin_name, str(e)))
		if is_input_plugin(plugin_module):
			plugin = plugin_module.InputPlugin()
			inputs.append((section, plugin))
		elif is_output_plugin(plugin_module):
			plugin = plugin_module.OutputPlugin()
			outputs.append((section, plugin))
		else:
			raise db2makedoc.plugins.PluginConfigurationError('Plugin "%s" is not a valid input or output plugin' % plugin_name)
		logging.info('Configuring plugin "%s"' % plugin_name)
		plugin.configure(dict(
			(name, value.replace('\n', ''))
			for (name, value) in parser.items(section)
		))
	return (inputs, outputs)

def test_config(config_files):
	"""Main routine for configuration testing.

	The config_files parameter specifies a list of configuration file names, or
	file-like objects to test. This routine opens each configuration file in 
	turn, loads the specified plugins and applies their configuration. It
	then outputs the configuration for each plugin.
	"""
	for config_file in config_files:
		(inputs, outputs) = process_config(config_file)
		for (section, plugin) in inputs + outputs:
			logging.debug('Active configuration for section [%s]:' % section)
			for name, value in plugin.options.iteritems():
				logging.debug('%s=%s' % (name, repr(value)))

def make_docs(config_files):
	"""Main routine for documentation creation.

	The config_files parameter specifies a list of configuration file names, or
	file-like objects to process. This routine opens each configuration file in
	turn, analyzes the content (in terms of input and output sections) then
	runs each output section for each input section.

	If you wish to call db2makedoc as part of another Python script, this is
	the routine to call (ignore parse_cmdline which does other stuff like
	fiddling around with logging and exception hooks, which you probably don't
	want).
	"""
	for config_file in config_files:
		(inputs, outputs) = process_config(config_file)
		for (section, input) in inputs:
			logging.info('Executing input section [%s]' % section)
			input.open()
			try:
				db = db2makedoc.db.Database(input)
			finally:
				input.close()
			for (section, output) in outputs:
				logging.info('Executing output section [%s]' % section)
				output.execute(db)

def list_plugins():
	"""Pretty-print a list of the available input and output plugins."""
	# Get all plugins and separate them into input and output lists, sorted by
	# name. The prefix of the root plugin package ("db2makedoc.plugins") is
	# stripped from the qualified name of each plugin module
	plugins = [
		(name[len(db2makedoc.plugins.__name__)+1:], plugin)
		for (name, plugin) in get_plugins(db2makedoc.plugins)
	]
	input_plugins = sorted(
		(
			(name, plugin.InputPlugin)
			for (name, plugin) in plugins
			if is_input_plugin(plugin)
		), key=itemgetter(0)
	)
	output_plugins = sorted(
		(
			(name, plugin.OutputPlugin)
			for (name, plugin) in plugins
			if is_output_plugin(plugin)
		), key=itemgetter(0)
	)
	# Format and output the lists
	tw = textwrap.TextWrapper()
	tw.width = terminal_size()[0] - 2
	tw.initial_indent = ' '*8
	tw.subsequent_indent = tw.initial_indent
	if len(input_plugins) > 0:
		print BOLD + BLUE + 'Available input plugins:' + NORMAL
		for (name, plugin) in input_plugins:
			print ' '*4 + BOLD + name + NORMAL
			print tw.fill(get_plugin_desc(plugin, summary=True))
			print
	if len(output_plugins) > 0:
		print BOLD + BLUE + 'Available output plugins:' + NORMAL
		for (name, plugin) in output_plugins:
			print ' '*4 + BOLD + name + NORMAL
			print tw.fill(get_plugin_desc(plugin, summary=True))
			print

def help_plugin(plugin_name):
	"""Pretty-print some help text for the specified plugin."""
	try:
		plugin = load_plugin(plugin_name)
	except ImportError, e:
		raise db2makedoc.plugins.PluginLoadError('Plugin "%s" failed to load: %s' % (plugin_name, str(e)))
	if is_input_plugin(plugin):
		plugin = plugin.InputPlugin()
	elif is_output_plugin(plugin):
		plugin = plugin.OutputPlugin()
	else:
		assert False
	print BOLD + BLUE + 'Name:' + NORMAL
	print ' '*4 + BOLD + plugin_name + NORMAL
	print
	tw = textwrap.TextWrapper()
	tw.width = terminal_size()[0] - 2
	tw.initial_indent = ' '*4
	tw.subsequent_indent = tw.initial_indent
	plugin_desc = '\n\n'.join(
		tw.fill(para)
		for para in get_plugin_desc(plugin).split('\n\n')
	)
	print BOLD + BLUE + 'Description:' + NORMAL
	print plugin_desc
	print
	if hasattr(plugin, 'options'):
		print BOLD + BLUE + 'Options:' + NORMAL
		tw.initial_indent = ' '*8
		tw.subsequent_indent = tw.initial_indent
		for (name, (default, desc, _)) in sorted(plugin.options.iteritems(), key=lambda(name, desc): name):
			print ' '*4 + BOLD + name + NORMAL,
			if default:
				print '(default: "%s")' % default
			else:
				print
			desc = '\n'.join(line.lstrip() for line in desc.split('\n'))
			print tw.fill(desc)
			print

def is_input_plugin(module):
	"""Determines whether the specified module is an input plugin.

	A module is an input plugin if it exports a callable (function or class
	definition) called Input.
	"""
	return hasattr(module, 'InputPlugin') and issubclass(module.InputPlugin, db2makedoc.plugins.InputPlugin)

def is_output_plugin(module):
	"""Determines whether the specified module is an output plugin.

	A module is an output plugin if it exports a callable (function or class
	definition) called Output.
	"""
	return hasattr(module, 'OutputPlugin') and issubclass(module.OutputPlugin, db2makedoc.plugins.OutputPlugin)

def is_plugin(module):
	"""Determines whether the specified module is a plugin of either kind."""
	return is_input_plugin(module) or is_output_plugin(module)

def get_plugins(root, name=None):
	"""Generator returning all input and output plugins in a package.

	Given a root package (root), this generator function recursively searches
	all paths in the package for modules which contain a callable (function or
	class definition) named InputPlugin or OutputPlugin. It yields a 2-tuple
	containing the plugin's qualified module name (minus the plugin root's
	name) and the module itself.
	"""
	if name is None:
		name = root.__name__
	logging.debug('Retrieving all plugins in %s' % name)
	path = os.path.sep.join(root.__path__)
	files = os.listdir(path)
	dirs = (
		i for i in files
		if os.path.isdir(os.path.join(path, i)) and i != 'CVS' and i != '.svn'
	)
	files = (
		i[:-3] for i in fnmatch.filter(files, '*.py')
		if os.path.isfile(os.path.join(path, i)) and i != '__init__.py'
	)
	# Deal with file-based modules first
	for f in files:
		try:
			(modfile, modpath, moddesc) = imp.find_module(f, root.__path__)
			try:
				logging.debug('Attempting to import file %s' % modpath)
				m = imp.load_module(f, modfile, modpath, moddesc)
			finally:
				# Caller is responsible for closing the file object returned by
				# find_module()
				if isinstance(modfile, file) and not modfile.closed:
					modfile.close()
		except ImportError, e:
			logging.debug(str(e))
			continue
		if is_plugin(m):
			yield ('%s.%s' % (name, f), m)
	# Then deal with directory-based modules (packages)
	for d in dirs:
		try:
			(modfile, modpath, moddesc) = imp.find_module(d, root.__path__)
			# modfile will be None in the case of a directory module so there's
			# no need to close() it
			logging.debug('Attempting to import package %s' % modpath)
			m = imp.load_module(d, modfile, modpath, moddesc)
		except ImportError, e:
			logging.debug(str(e))
			continue
		if is_plugin(m):
			yield ('%s.%s' % (name, d), m)
		# Recursively call ourselves with the directory module
		for (n, m) in get_plugins(m, '%s.%s' % (name, d)):
			yield (n, m)

_plugin_cache = {}
def load_plugin(name):
	"""Given a name relative to the plugin root, load an input or output plugin."""
	# Loaded modules are cached. Otherwise, we may wind up attempting to load
	# the same module multiple times which leads to interest effects on class
	# definitions!
	global _plugin_cache
	logging.info('Loading plugin "%s"' % name)
	try:
		return _plugin_cache[name]
	except KeyError:
		root = None
		parts = db2makedoc.plugins.__name__.split('.') + name.split('.')
		for p in parts:
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
		_plugin_cache[name] = module
		return module

def get_plugin_desc(plugin, summary=False):
	"""Retrieves the description of the plugin.

	A plugin's description is stored in its classes' docstring. The first line
	of the docstring is assumed to be the summary text. Leading indentation is
	stripped from all lines. If the summary parameter is True, the first line
	of the description is returned.
	"""
	# Strip leading indentation
	s = [line.lstrip() for line in plugin.__doc__.split('\n')]
	if summary:
		return s[0]
	else:
		return '\n'.join(s)

if __name__ == '__main__':
	main()
