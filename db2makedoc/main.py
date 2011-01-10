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
import db2makedoc.converter
from db2makedoc.util import *

__version__ = "1.1.1"

# Use the user's default locale instead of C
locale.setlocale(locale.LC_ALL, '')

# Get the default output encoding from the default locale
ENCODING = locale.getdefaultlocale()[1]

class HelpFormatter(optparse.IndentedHelpFormatter):
	# Customize the width of help output
	def __init__(self):
		width = min(130, terminal_size()[0] - 2)
		optparse.IndentedHelpFormatter.__init__(self, max_help_position=width/3, width=width)

class OptionParser(optparse.OptionParser):
	# Customize error handling to raise an exception (default simply prints an
	# error and terminates execution)
	def error(self, msg):
		raise optparse.OptParseError(msg)

class Utility(object):
	# This class is the abstract base class for each of the command line
	# utility classes defined below. It provides some basic facilities like an
	# option parser, console pretty-printing, logging and exception handling

	def __init__(self, usage=None, version=None, description=None):
		super(Utility, self).__init__()
		self.wrapper = textwrap.TextWrapper()
		self.wrapper.width = min(130, terminal_size()[0] - 2)
		if usage is None:
			usage = self.__doc__.split('\n')[0]
		if version is None:
			version = '%%prog %s' % __version__
		if description is None:
			description = self.wrapper.fill('\n'.join(
				line.lstrip()
				for line in self.__doc__.split('\n')[1:]
				if line.lstrip()
			))
		self.parser = OptionParser(
			usage=usage,
			version=version,
			description=description,
			formatter=HelpFormatter()
		)
		self.parser.set_defaults(
			debug=False,
			logfile='',
			loglevel=logging.WARNING
		)
		self.parser.add_option('-q', '--quiet', dest='loglevel', action='store_const', const=logging.ERROR,
			help="""produce less console output""")
		self.parser.add_option('-v', '--verbose', dest='loglevel', action='store_const', const=logging.INFO,
			help="""produce more console output""")
		self.parser.add_option('-l', '--log-file', dest='logfile',
			help="""log messages to the specified file""")
		self.parser.add_option('-D', '--debug', dest='debug', action='store_true',
			help="""enables debug mode (runs under PDB)""")

	def __call__(self, args=None):
		if args is None:
			args = sys.argv[1:]
		(options, args) = self.parser.parse_args(args)
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
		if options.debug:
			import pdb
			return pdb.runcall(self.main, options, args)
		else:
			try:
				return self.main(options, args) or 0
			except:
				return self.handle(*sys.exc_info())

	def handle(self, type, value, tb):
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
			# Otherwise, log the stack trace and the exception into the log
			# file for debugging purposes
			for line in traceback.format_exception(type, value, tb):
				for s in line.rstrip().split('\n'):
					logging.critical(s)
			return 1

	def pprint(self, s, indent=None, initial_indent='', subsequent_indent=''):
		"""Pretty-print routine for console output.

		This routine exists to provide pretty-printing capabilities for console
		output.  It makes use of a TextWrapper instance which is configured on
		startup with the width of the console to wrap text nicely.

		The s parameter provides the string or list of strings (used as a list
		of paragraphs) to print. The indent, initial_indent and
		subsequent_indent parameters are passed to the TextWrapper instance to
		specify indentations.  Either provide indent alone (which will be used
		as both initial_indent and subsequent_indent), or provide intial_indent
		and subsequent_indent separately.
		"""
		if indent is None:
			self.wrapper.initial_indent = initial_indent
			self.wrapper.subsequent_indent = subsequent_indent
		else:
			self.wrapper.initial_indent = indent
			self.wrapper.subsequent_indent = indent
		if isinstance(s, basestring):
			s = [s]
		first = True
		for para in s:
			if first:
				first = False
			else:
				sys.stdout.write('\n')
			para = self.wrapper.fill(para)
			if isinstance(para, unicode):
				para = para.encode(ENCODING)
			sys.stdout.write(para + '\n')

	def main(self, options, args):
		pass

### db2makedoc ###############################################################

class MakeDocUtility(Utility):
	"""%prog [options] configs...
	
	This utility generates documentation (in a variety of formats) from the
	system catalog in IBM DB2 databases. At least one configuration file (an
	INI-style file) must be specified. See the documentation for more
	information on the required syntax and content of this file. The available
	command line options are listed below.
	"""

	def __init__(self):
		super(MakeDocUtility, self).__init__()
		self.parser.set_defaults(test=False, config=None, plugin=None)
		self.parser.add_option('', '--list-plugins', dest='plugin', action='store_const', const='*',
			help="""list the available input and output plugins""")
		self.parser.add_option('', '--help-plugin', dest='plugin',
			help="""display information about the the specified plugin""")
		self.parser.add_option('-n', '--dry-run', dest='test', action='store_true',
			help="""test a configuration without actually executing anything""")
		# retained for backward compatibility
		self.parser.add_option('', '--help-plugins', dest='plugin', action='store_const', const='*',
			help=optparse.SUPPRESS_HELP)

	def main(self, options, args):
		super(MakeDocUtility, self).main(options, args)
		if options.plugin == '*':
			self.list_plugins()
		elif options.plugin:
			self.help_plugin(options.plugin)
		elif len(args) == 0:
			self.parser.error('you must specify at least one configuration file')
		elif options.test:
			self.test_config(args)
		else:
			self.make_docs(args)
		return 0

	def process_config(self, config_file):
		"""Parses and prepares plugins from a configuration file.

		The config_file parameter specifies a configuration filename, or
		file-like object to process. The routine parses each section in the
		configuration, constructing and configuring the plugin specified by
		each. The routine returns a 2-tuple of (inputs, outputs). "inputs" and
		"outputs" are lists of 2-tuples of (section-name, plugin) where
		"section-name" is the name of a section, and "plugin" is the
		constructed and configured plugin object.
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
			plugin = db2makedoc.plugins.load_plugin(plugin_name)()
			if isinstance(plugin, db2makedoc.plugins.InputPlugin):
				inputs.append((section, plugin))
			elif isinstance(plugin, db2makedoc.plugins.OutputPlugin):
				outputs.append((section, plugin))
			else:
				raise db2makedoc.plugins.PluginConfigurationError('Plugin "%s" is not a valid input or output plugin' % plugin_name)
			logging.info('Configuring plugin "%s"' % plugin_name)
			plugin.configure(dict(
				(name, value.replace('\n', ''))
				for (name, value) in parser.items(section)
			))
		return (inputs, outputs)

	def test_config(self, config_files):
		"""Main routine for configuration testing.

		The config_files parameter specifies a list of configuration file
		names, or file-like objects to test. This routine opens each
		configuration file in turn, loads the specified plugins and applies
		their configuration. It then outputs the configuration for each plugin.
		"""
		for config_file in config_files:
			(inputs, outputs) = self.process_config(config_file)
			for (section, plugin) in inputs + outputs:
				logging.debug('Active configuration for section [%s]:' % section)
				for name, value in plugin.options.iteritems():
					logging.debug('%s=%s' % (name, repr(value)))

	def make_docs(self, config_files):
		"""Main routine for documentation creation.

		The config_files parameter specifies a list of configuration file
		names, or file-like objects to process. This routine opens each
		configuration file in turn, analyzes the content (in terms of input and
		output sections) then runs each output section for each input section.

		If you wish to call db2makedoc as part of another Python script, this
		is the routine to call (ignore parse_cmdline which does other stuff
		like fiddling around with logging and exception hooks, which you
		probably don't want).
		"""
		for config_file in config_files:
			(inputs, outputs) = self.process_config(config_file)
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

	def list_plugins(self):
		"""Pretty-print a list of the available input and output plugins."""
		# Get all plugins and separate them into input and output lists, sorted
		# by name. The prefix of the root plugin package ("db2makedoc.plugins")
		# is stripped from the qualified name of each plugin module
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
		if len(input_plugins) > 0:
			self.pprint('Available input plugins:')
			for (name, plugin) in input_plugins:
				self.pprint(name, indent=' '*4)
				self.pprint(plugin.description(summary=True), indent=' '*8)
				self.pprint('')
		if len(output_plugins) > 0:
			self.pprint('Available output plugins:')
			for (name, plugin) in output_plugins:
				self.pprint(name, indent=' '*4)
				self.pprint(plugin.description(summary=True), indent=' '*8)
				self.pprint('')

	def help_plugin(self, plugin_name):
		"""Pretty-print some help text for the specified plugin."""
		plugin = db2makedoc.plugins.load_plugin(plugin_name)()
		self.pprint('Name:')
		self.pprint(plugin_name, indent=' '*4)
		self.pprint('')
		self.pprint('Description:')
		self.pprint(plugin.description().split('\n\n'), indent=' '*4)
		self.pprint('')
		if hasattr(plugin, 'options'):
			self.pprint('Options:')
			for (name, (default, desc, _)) in sorted(plugin.options.iteritems(), key=lambda(name, desc): name):
				if default:
					self.pprint('%s (default "%s")' % (name, default), indent=' '*4)
				else:
					self.pprint(name, indent=' '*4)
				desc = '\n'.join(line.lstrip() for line in desc.split('\n'))
				self.pprint(desc, indent=' '*8)
				self.pprint('')

db2makedoc_main = MakeDocUtility()

### db2convdoc utility #######################################################

class ConvDocUtility(Utility):
	"""%prog [options] source converter

	This utility generates SYSCAT (or DOCCAT) compatible comments from a
	variety of sources, primarily various versions of the DB2 for LUW
	InfoCenter. The mandatory "source" parameter specifies the source, while
	the "converter" parameter specifies the output format for the documentation
	(output is always dumped to stdout for redirection). Use the various "list"
	and "help" options to find out more about what sources and converters are
	available.
	"""

	def __init__(self):
		super(ConvDocUtility, self).__init__()
		self.parser.set_defaults(source=None, conv=None)
		self.parser.add_option('--list-sources', dest=u'source', action=u'store_const', const=u'*',
			help=u"""list all available sources""")
		self.parser.add_option('--help-source', dest=u'source',
			help=u"""display help about the named source""")
		self.parser.add_option('--list-converters', dest=u'conv', action=u'store_const', const=u'*',
			help=u"""list all available converters""")
		self.parser.add_option('--help-converter', dest=u'conv',
			help=u"""display help about the named converter""")
		self.sources = {
			'luw81': db2makedoc.converter.InfoCenterSource81,
			'luw82': db2makedoc.converter.InfoCenterSource82,
			'luw91': db2makedoc.converter.InfoCenterSource91,
			'luw95': db2makedoc.converter.InfoCenterSource95,
			'luw97': db2makedoc.converter.InfoCenterSource97,
			'xml':   db2makedoc.converter.XMLSource,
		}
		self.converters = {
			'comment': db2makedoc.converter.CommentConverter,
			'insert':  db2makedoc.converter.InsertConverter,
			'update':  db2makedoc.converter.UpdateConverter,
			'merge':   db2makedoc.converter.MergeConverter,
			'xml':     db2makedoc.converter.XMLConverter,
		}

	def main(self, options, args):
		super(ConvDocUtility, self).main(options, args)
		if options.source == '*':
			self.list_sources()
		elif options.source:
			self.help_source(options.source)
		elif options.conv == '*':
			self.list_converters()
		elif options.conv:
			self.help_converter(options.conv)
		elif len(args) == 2:
			try:
				source = self.sources[args[0]]
			except KeyError:
				self.parser.error('invalid source: %s' % args[0])
			try:
				converter = self.converters[args[1]]
			except KeyError:
				self.parser.error('invalid converter: %s' % args[1])
			for line in converter(source()):
				sys.stdout.write(line.encode(ENCODING))
		else:
			self.parser.error('you must specify a source and a converter')
		return 0

	def class_summary(self, cls):
		return cls.__doc__.split('\n')[0]

	def class_description(self, cls):
		return '\n'.join(line.lstrip() for line in cls.__doc__.split('\n')).split('\n\n')

	def list_classes(self, header, classes):
		self.pprint(header)
		for (key, cls) in sorted(classes.iteritems()):
			self.pprint(key, indent=' '*4)
			self.pprint(self.class_summary(cls), indent=' '*8)
			self.pprint('')

	def help_class(self, key, cls):
		self.pprint('Name:')
		self.pprint(key, indent=' '*4)
		self.pprint('')
		self.pprint('Description:')
		self.pprint(self.class_description(cls), indent=' '*4)
		self.pprint('')

	def list_sources(self):
		self.list_classes('Available sources:', self.sources)

	def list_converters(self):
		self.list_classes('Available converters:', self.converters)

	def help_source(self, key):
		try:
			self.help_class(key, self.sources[key])
		except KeyError:
			self.parser.error('no such source: %s' % key)

	def help_converter(self, key):
		try:
			self.help_class(key, self.converters[key])
		except KeyError:
			self.parser.error('no such converter: %s' % key)

db2convdoc_main = ConvDocUtility()

### db2tidysql utility #######################################################

class TidySqlUtility(Utility):
	"""%prog [options] files...

	This utility reformats SQL for human consumption using the same parser that
	the db2makedoc application uses for generating SQL in documentation. Either
	specify the name of a file containing the SQL to reformat, or specify - to
	indicate that stdin should be read. The reformatted SQL will be written to
	stdout in either case. The available command line options are listed below.
	"""

	def __init__(self):
		super(TidySqlUtility, self).__init__()
		self.parser.set_defaults(terminator=';')
		self.parser.add_option('-t', '--terminator', dest='terminator',
			help="""specify the statement terminator (default=';')""")

	def main(self, options, args):
		super(TidySqlUtility, self).main(options, args)
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

db2tidysql_main = TidySqlUtility()

