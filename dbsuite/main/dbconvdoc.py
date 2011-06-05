# vim: set noet sw=4 ts=4:

import sys
import logging
import db2makedoc.converter
import db2makedoc.main
from db2makedoc.util import *

class ConvDocUtility(db2makedoc.main.Utility):
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

main = ConvDocUtility()

