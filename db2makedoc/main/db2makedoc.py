import optparse
import ConfigParser
import logging
import db2makedoc.db
import db2makedoc.plugins
import db2makedoc.main
from db2makedoc.util import *

class MakeDocUtility(db2makedoc.main.Utility):
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

main = MakeDocUtility()

