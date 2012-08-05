# vim: set et sw=4 sts=4:

import sys
import logging
import dbsuite.converter
import dbsuite.main
from dbsuite.compat import *

class ConvDocUtility(dbsuite.main.Utility):
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
            'luw81': dbsuite.converter.InfoCenterSource81,
            'luw82': dbsuite.converter.InfoCenterSource82,
            'luw91': dbsuite.converter.InfoCenterSource91,
            'luw95': dbsuite.converter.InfoCenterSource95,
            'luw97': dbsuite.converter.InfoCenterSource97,
            'xml':   dbsuite.converter.XMLSource,
        }
        self.converters = {
            'comment': dbsuite.converter.CommentConverter,
            'insert':  dbsuite.converter.InsertConverter,
            'update':  dbsuite.converter.UpdateConverter,
            'merge':   dbsuite.converter.MergeConverter,
            'xml':     dbsuite.converter.XMLConverter,
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
                sys.stdout.write(line.encode(self.encoding))
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

