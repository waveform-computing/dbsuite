# $Header$
# vim: set noet sw=4 ts=4:

import sys
mswindows = sys.platform == "win32"
import optparse
import ConfigParser
import logging
import fnmatch
import os
import imp
import textwrap
import db2makedoc.db
import db2makedoc.plugins

# Constants
__version__ = "1.0.0"
PLUGIN_OPTION = 'plugin'

# Localizable strings
USAGE_TEMPLATE = '%prog [options] configs...'
VERSION_TEMPLATE = '%%prog %s Database Documentation Generator' % __version__

CONFIG_HELP = 'specify the configuration file from which to read settings'
QUIET_HELP = 'produce less console output'
VERBOSE_HELP = 'produce more console output'
LOG_FILE_HELP = 'log messages to the specified file'
HELP_PLUGINS_HELP = 'list the available input and output plugins'
HELP_PLUGIN_HELP = 'display information about the specified plugin'
DEBUG_HELP = 'enables debug mode'

NO_FILES_ERR = 'you did not specify any filenames'
MISSING_VALUE_ERR = '%s: [%s]: missing a "%s" value'
INVALID_PLUGIN_ERR = '%s: [%s]: invalid plugin name "%s" (plugin names must be fully qualified; must begin with "input." or "output.")'
PLUGIN_IMPORT_ERR = '%s: [%s]: plugin "%s" not found or failed to load (error: %s)'
PLUGIN_EXEC_ERR = '%s: [%s]: plugin "%s" failed (error: %s)'

READING_INPUT_MSG = '%s: [%s]: Reading input (%s)'
WRITING_OUTPUT_MSG = '%s: [%s]: Generating output (%s)'
INPUT_PLUGINS_MSG = 'Available input plugins:'
OUTPUT_PLUGINS_MSG = 'Available output plugins:'
PLUGIN_NAME_MSG = 'Name:'
PLUGIN_DESC_MSG = 'Description:'
PLUGIN_OPTIONS_MSG = 'Options:'

# Formatting strings
if not mswindows and hasattr(sys.stdout, 'isatty') and sys.stdout.isatty():
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

def main():
	# Parse the command line arguments
	usage = USAGE_TEMPLATE
	version = VERSION_TEMPLATE
	parser = optparse.OptionParser(usage=usage, version=version)
	parser.set_defaults(
		debug=False,
		config=None,
		listplugins=None,
		plugin=None,
		logfile="",
		loglevel=logging.WARNING
	)
	parser.add_option("-q", "--quiet", dest="loglevel", action="store_const", const=logging.ERROR, help=QUIET_HELP)
	parser.add_option("-v", "--verbose", dest="loglevel", action="store_const", const=logging.DEBUG, help=VERBOSE_HELP)
	parser.add_option("-l", "--log-file", dest="logfile", help=LOG_FILE_HELP)
	parser.add_option("", "--help-plugins", dest="listplugins", action="store_true", help=HELP_PLUGINS_HELP)
	parser.add_option("", "--help-plugin", dest="plugin", help=HELP_PLUGIN_HELP)
	parser.add_option("-D", "--debug", dest="debug", action="store_true", help=DEBUG_HELP)
	(options, args) = parser.parse_args()
	# Deal with one-shot actions (help, etc.)
	if options.listplugins:
		list_plugins()
		return
	elif options.plugin:
		help_plugin(options.plugin)
		return
	# Check the options & args
	if len(args) == 0:
		parser.error(NO_FILES_ERR)
	# Set up some logging stuff
	console = logging.StreamHandler(sys.stderr)
	console.setFormatter(logging.Formatter('%(message)s'))
	console.setLevel(options.loglevel)
	logging.getLogger().addHandler(console)
	if options.logfile:
		logfile = logging.FileHandler(options.logfile)
		logfile.setFormatter(logging.Formatter('%(asctime)s, %(levelname)s, %(message)s'))
		logfile.setLevel(logging.INFO) # Log file always logs at INFO level
		logging.getLogger().addHandler(logfile)
	# Set up the exceptions hook for uncaught exceptions and the logging
	# levels if --debug was given
	if options.debug:
		console.setLevel(logging.DEBUG)
		if options.logfile:
			logfile.setLevel(logging.DEBUG)
		logging.getLogger().setLevel(logging.DEBUG)
	else:
		logging.getLogger().setLevel(logging.INFO)
		sys.excepthook = production_excepthook
	# Loop over each provided configuration file
	for config_file in args:
		# Read the configuration file
		parser = ConfigParser.SafeConfigParser()
		parser.read(config_file)
		# Sort sections into input and output sections
		input_sections = []
		output_sections = []
		for section in parser.sections():
			if not parser.has_option(section, PLUGIN_OPTION):
				raise Exception(MISSING_VALUE_ERR % (config_file, section, PLUGIN_OPTION))
			s = parser.get(section, PLUGIN_OPTION)
			p = load_plugin(parser.get(section, PLUGIN_OPTION))
			if is_input_plugin(p):
				input_sections.append(section)
			elif is_output_plugin(p):
				output_sections.append(section)
			else:
				raise Exception(INVALID_PLUGIN_ERR % (config_file, section, s))
		# Run each output section for each input section
		for input_section in input_sections:
			s = parser.get(input_section, PLUGIN_OPTION)
			try:
				input_plugin = load_plugin(s)
			except ImportError, e:
				raise Exception(PLUGIN_IMPORT_ERR % (config_file, input_section, s, str(e)))
			# Get input_plugin to read data from the source specified by the
			# configuration values from input_section
			logging.info(READING_INPUT_MSG % (config_file, input_section, s))
			try:
				ip = input_plugin.InputPlugin()
				ip.configure(dict(parser.items(input_section)))
				ip.open()
				try:
					# Construct the internal representation of the metadata
					db = db2makedoc.db.Database(ip)
				finally:
					ip.close()
			except Exception, e:
				# Unless we're in debug mode, just log errors and continue on
				# to the next ip section
				logging.error(PLUGIN_EXEC_ERR % (config_file, input_section, s, str(e)))
				if options.debug:
					raise
				continue
			for output_section in output_sections:
				s = parser.get(output_section, PLUGIN_OPTION)
				try:
					output_plugin = load_plugin(s)
				except ImportError, e:
					raise Exception(PLUGIN_IMPORT_ERR % (config_file, output_section, s, str(e)))
				# Get the output_plugin to generate output from db
				logging.info(WRITING_OUTPUT_MSG % (config_file, output_section, s))
				try:
					op = output_plugin.OutputPlugin()
					op.configure(dict(parser.items(output_section)))
					op.execute(db)
				except Exception, e:
					# Again, just log errors and continue onto the next output
					# section unless in debug mode
					logging.error(PLUGIN_EXEC_ERR % (config_file, output_section, s, str(e)))
					if options.debug:
						raise

def production_excepthook(type, value, traceback):
	"""Exception hook for non-debug mode.

	This exception hook uses the logging infrastructure set up by main to
	record fatal (uncaught) exceptions. It also sets the app's exit code to an
	appropriate value (currently 1 for any uncaught exception), and avoids
	printing the stack trace (which'd just confuse most users). Users can
	enable the normal exception hook by using the --debug or -D args.
	"""
	logging.critical(str(value))
	sys.exit(1)

def list_plugins():
	"""Pretty-print a list of the available input and output plugins."""
	# Get all plugins and separate them into input and output lists, sorted by
	# name. The prefix of the root plugin package ("db2makedoc.plugins") is
	# stripped from the qualified name of each plugin module
	plugins = [
		(name[len(db2makedoc.plugins.__name__)+1:], plugin)
		for (name, plugin) in get_plugins(db2makedoc.plugins)
	]
	input_plugins = [
		(name, plugin.InputPlugin)
		for (name, plugin) in plugins
		if is_input_plugin(plugin)
	]
	output_plugins = [
		(name, plugin.OutputPlugin)
		for (name, plugin) in plugins
		if is_output_plugin(plugin)
	]
	input_plugins = sorted(input_plugins, key=lambda(name, plugin): name)
	output_plugins = sorted(output_plugins, key=lambda(name, plugin): name)
	# Format and output the lists
	tw = textwrap.TextWrapper()
	tw.initial_indent = ' '*8
	tw.subsequent_indent = tw.initial_indent
	print BOLD + BLUE + INPUT_PLUGINS_MSG + NORMAL
	for (name, plugin) in input_plugins:
		print ' '*4 + BOLD + name + NORMAL
		print tw.fill(get_plugin_desc(plugin, summary=True))
	print ''
	print BOLD + BLUE + OUTPUT_PLUGINS_MSG + NORMAL
	for (name, plugin) in output_plugins:
		print ' '*4 + BOLD + name + NORMAL
		print tw.fill(get_plugin_desc(plugin, summary=True))
	print ''

def help_plugin(plugin_name):
	"""Pretty-print some help text for the specified plugin."""
	plugin = load_plugin(plugin_name)
	if is_input_plugin(plugin):
		plugin = plugin.InputPlugin()
	elif is_output_plugin(plugin):
		plugin = plugin.OutputPlugin()
	else:
		assert False
	print BOLD + BLUE + PLUGIN_NAME_MSG + NORMAL
	print ' '*4 + BOLD + plugin_name + NORMAL
	print ''
	tw = textwrap.TextWrapper()
	tw.initial_indent = ' '*4
	tw.subsequent_indent = tw.initial_indent
	plugin_desc = '\n\n'.join(
		tw.fill(para)
		for para in get_plugin_desc(plugin).split('\n\n')
	)
	print BOLD + BLUE + PLUGIN_DESC_MSG + NORMAL
	print plugin_desc
	print ''
	if hasattr(plugin, 'options'):
		print BOLD + BLUE + PLUGIN_OPTIONS_MSG + NORMAL
		tw.initial_indent = ' '*8
		tw.subsequent_indent = tw.initial_indent
		for (name, (default, desc)) in sorted(plugin.options.iteritems(), key=lambda(name, desc): name):
			print ' '*4 + BOLD + name + NORMAL,
			if default is not None:
				print '(default: %s)' % default
			else:
				print
			desc = '\n'.join(line.lstrip() for line in desc.split('\n'))
			print tw.fill(desc)
	print ""

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
	class definition) named Input or Output. It yields a 2-tuple containing the
	plugin's qualified module name (minues the plugin root's name) and the
	module itself.
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
		for (n, m) in get_plugins(m, '%s.%s' % (name, m.__name__)):
			yield (n, m)

def load_plugin(name):
	"""Given a name relative to the plugin root, load an input or output plugin."""
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
	return module

def get_plugin_desc(plugin, summary=False):
	"""Retrieves the description of the plugin.

	A plugin's description is stored in its classes' docstring. The first line
	of the docstring is assumed to be the summary text. Leading indentation is
	stripped from all lines. If the summary parameter is True, the first line
	of the description is returned.
	"""
	s = plugin.__doc__
	# Strip leading indentation
	s = [line.lstrip() for line in s.split('\n')]
	if summary:
		return s[0]
	else:
		return '\n'.join(s)

if __name__ == '__main__':
	try:
		# Use Psyco, if available
		import psyco
		psyco.full()
	except ImportError:
		pass
	main()
