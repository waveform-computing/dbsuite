# vim: set noet sw=4 ts=4:

import sys
import optparse
import ConfigParser
import logging
import locale
import textwrap
import traceback
import db2makedoc.db
import db2makedoc.plugins
import db2makedoc.highlighters
from db2makedoc.util import *

__version__ = "1.1.0"

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

class OptionParser(optparse.OptionParser):
	# This custom option parser class simply overrides the error method to
	# raise an exception instead of instantly exiting.  This allows our custom
	# exception handlers a chance to do something with the exception if they
	# want to.
	def error(self, msg):
		raise optparse.OptParseError(msg)

def db2makedoc_main(args=None):
	if args is None:
		args = sys.argv[1:]
	# Parse the command line arguments
	parser = OptionParser(
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
	parser.add_option('', '--help-plugins', dest='listplugins', action='store_true',
		help="""list the available input and output plugins""")
	parser.add_option('', '--help-plugin', dest='plugin',
		help="""display information about the the specified plugin""")
	parser.add_option('-n', '--dry-run', dest='test', action='store_true',
		help="""test a configuration without actually executing anything""")
	configure_options(parser)
	(options, args) = parser.parse_args(args)
	configure_logging(options)
	try:
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
		return 0
	except:
		if options.debug:
			raise
		else:
			return handle_exception(*sys.exc_info())

def db2tidysql_main(args=None):
	if args is None:
		args = sys.argv[1:]
	# Parse the command line arguments
	parser = OptionParser(
		usage='%prog [options] files...',
		version='%%prog %s SQL reformatter' % __version__,
		description="""\
This utility reformats SQL for human consumption using the same parser that the
db2makedoc application uses for generating SQL in documentation. Either specify
the name of a file containing the SQL to reformat, or specify - to indicate
that stdin should be read. The reformatted SQL will be written to stdout in
either case. The available command line options are listed below.""")
	parser.set_defaults(
		debug=False,
		terminator=';',
		loglevel=logging.WARNING
	)
	parser.add_option('-t', '--terminator', dest='terminator',
		help="""specify the statement terminator (default=';')""")
	configure_options(parser)
	(options, args) = parser.parse_args(args)
	configure_logging(options)
	try:
		# Call one of the action routines depending on the options
		done_stdin = False
		highlighter = db2makedoc.highlighters.SQLHighlighter()
		for sql_file in args:
			if sql_file == '-':
				if not done_stdin:
					done_stdin = True
					sql_file = sys.stdin
				else:
					raise IOError('Cannot read input from stdin multiple times')
			else:
				sql_file = open(sql_file, 'rU')
			sql = sql_file.read()
			sql = highlighter.parse_to_string(sql, terminator=options.terminator)
			sys.stdout.write(sql)
			sys.stdout.flush()
		return 0
	except:
		if options.debug:
			raise
		else:
			return handle_exception(*sys.exc_info())

def handle_exception(type, value, tb):
	"""Exception hook for non-debug mode."""
	if issubclass(type, (SystemExit, KeyboardInterrupt)):
		# Just ignore system exit and keyboard interrupt errors (after all,
		# they're user generated)
		return 130
	elif issubclass(type, (IOError, db2makedoc.plugins.PluginError)):
		# For simple errors like IOError and PluginError just output the
		# message which should be sufficient for the end user (no need to
		# confuse them with a full stack trace)
		logging.critical(str(value))
		return 1
	elif issubclass(type, (optparse.OptParseError,)):
		# For option parser errors output the error along with a message
		# indicating how the help page can be displayed
		logging.critical(str(value))
		logging.critical('Try the --help option for more information.')
		return 2
	else:
		# Otherwise, log the stack trace and the exception into the log file
		# for debugging purposes
		for line in traceback.format_exception(type, value, tb):
			for s in line.rstrip().split('\n'):
				logging.critical(s)
		return 1

def configure_options(parser):
	"""Sets up various command line options which are common to all utilities."""
	parser.add_option('-q', '--quiet', dest='loglevel', action='store_const', const=logging.ERROR,
		help="""produce less console output""")
	parser.add_option('-v', '--verbose', dest='loglevel', action='store_const', const=logging.INFO,
		help="""produce more console output""")
	parser.add_option('-l', '--log-file', dest='logfile',
		help="""log messages to the specified file""")
	parser.add_option('-D', '--debug', dest='debug', action='store_true',
		help="""enables debug mode (runs under PDB)""")

def configure_logging(options):
	"""Sets up the logging environment given a common set of command line options."""
	console = logging.StreamHandler(sys.stderr)
	console.setFormatter(logging.Formatter('%(message)s'))
	console.setLevel(options.loglevel)
	logging.getLogger().addHandler(console)
	if options.logfile:
		logfile = logging.FileHandler(options.logfile)
		logfile.setFormatter(logging.Formatter('%(asctime)s, %(levelname)s, %(message)s'))
		logfile.setLevel(logging.DEBUG)
		logging.getLogger().addHandler(logfile)
	if options.debug:
		console.setLevel(logging.DEBUG)
		logging.getLogger().setLevel(logging.DEBUG)
	else:
		logging.getLogger().setLevel(logging.INFO)

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
		plugin = db2makedoc.plugins.load_plugin(plugin_name)
		if issubclass(plugin, db2makedoc.plugins.InputPlugin):
			inputs.append((section, plugin()))
		elif issubclass(plugin, db2makedoc.plugins.OutputPlugin):
			outputs.append((section, plugin()))
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
	plugins = list(db2makedoc.plugins.get_plugins())
	input_plugins = sorted(
		(
			(name, cls)
			for (name, cls) in plugins
			if issubclass(cls, db2makedoc.plugins.InputPlugin)
		), key=itemgetter(0)
	)
	output_plugins = sorted(
		(
			(name, cls)
			for (name, cls) in plugins
			if issubclass(cls, db2makedoc.plugins.OutputPlugin)
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
			print tw.fill(plugin.description(summary=True))
			print
	if len(output_plugins) > 0:
		print BOLD + BLUE + 'Available output plugins:' + NORMAL
		for (name, plugin) in output_plugins:
			print ' '*4 + BOLD + name + NORMAL
			print tw.fill(plugin.description(summary=True))
			print

def help_plugin(plugin_name):
	"""Pretty-print some help text for the specified plugin."""
	plugin = db2makedoc.plugins.load_plugin(plugin_name)()
	print BOLD + BLUE + 'Name:' + NORMAL
	print ' '*4 + BOLD + plugin_name + NORMAL
	print
	tw = textwrap.TextWrapper()
	tw.width = terminal_size()[0] - 2
	tw.initial_indent = ' '*4
	tw.subsequent_indent = tw.initial_indent
	plugin_desc = '\n\n'.join(
		tw.fill(para)
		for para in plugin.description().split('\n\n')
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

