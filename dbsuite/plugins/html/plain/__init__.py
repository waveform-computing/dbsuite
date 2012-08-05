# vim: set et sw=4 sts=4:

"""Output plugin for plain HTML web pages."""

import dbsuite.plugins
import dbsuite.plugins.html
from dbsuite.db import Schema, Table, View, Alias
from dbsuite.plugins.html.plain.document import PlainSite


class OutputPlugin(dbsuite.plugins.html.HTMLOutputPlugin):
    """Output plugin for plain HTML web pages.

    This output plugin supports generating XHTML documentation with a fairly
    plain style. It includes syntax highlighted SQL information on various
    objects in the database (views, tables, etc.) and diagrams of the schema.
    """

    def __init__(self):
        super(OutputPlugin, self).__init__()
        self.site_class = PlainSite
        self.add_option('last_updated', default='true', convert=self.convert_bool,
            doc="""If true, the generated date of each page will be added to
            the footer""")
        self.add_option('stylesheets', default='', convert=self.convert_list,
            doc="""A comma separated list of additional stylesheet URLs which
            each generated HTML page will link to. Accepts $-prefixed
            substitutions (see path)""")
        self.add_option('max_graph_size', default='600x800',
            convert=lambda value: self.convert_list(value, separator='x',
            subconvert=lambda value: self.convert_int(value, minvalue=100),
            minvalues=2, maxvalues=2),
            doc="""The maximum size that diagrams are allowed to be on the
            page. If diagrams are larger, they will be resized to fit within
            the specified size. Values must be specified as "widthxheight",
            e.g.  "640x480". Defaults to "600x800".""")

    def configure(self, config):
        super(OutputPlugin, self).configure(config)
        # If diagrams are requested, check we can find GraphViz in the PATH
        # and import PIL
        if self.options['diagrams']:
            try:
                import PIL
            except ImportError:
                raise dbsuite.plugins.PluginConfigurationError('Diagrams requested, but the Python Imaging Library (PIL) was not found')
        supported_diagrams = set([Schema, Table, View, Alias])
        if self.options['diagrams'] - supported_diagrams:
            raise dbsuite.plugins.PluginConfigurationError('No diagram support for %s objects (supported objects are %s)' % (
                ', '.join(c.config_names[0] for c in self.options['diagrams'] - supported_diagrams),
                ', '.join(c.config_names[0] for c in supported_diagrams)
            ))

    def substitute(self):
        return super(OutputPlugin, self).substitute() + ('stylesheets',)
