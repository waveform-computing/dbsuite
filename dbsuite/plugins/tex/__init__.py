# vim: set et sw=4 sts=4:

# Copyright 2012 Dave Hughes.
#
# This file is part of dbsuite.
#
# dbsuite is free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# dbsuite is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# dbsuite.  If not, see <http://www.gnu.org/licenses/>.

"""Output plugin for LaTeX documentation."""

from __future__ import (
    unicode_literals,
    print_function,
    absolute_import,
    division,
    )

import os
import sys
import logging
from string import Template

import dbsuite.db
import dbsuite.plugins
from dbsuite.plugins.tex.document import TeXDocumentation


class OutputPlugin(dbsuite.plugins.OutputPlugin):
    """Output plugin for LaTeX documentation.

    This output plugin supports generating PDF documentation via the TeX
    type-setting system, specifically the LaTeX variant (including various PDF
    facilities). It includes syntax highlighted SQL information on various
    objects in the database (views, tables, etc.), diagrams of the schema, and
    hyperlinks within generated PDFs.

    Note that the generated documentation tends to be extremely lengthy for a
    printed medium. It is strongly suggested that you limit the input plugin to
    a single schema when using this output plugin.

    An example command line for converting the output into a PDF is "pdflatex
    -shell-escape sample.tex" (this may need to be run several times to resolve
    references depending on what content is included).
    """

    def __init__(self):
        super(OutputPlugin, self).__init__()
        self.add_option('filename', default=None, convert=self.convert_path,
            doc="""The path and filename for the TeX output file. Use $db or
            ${db} to include the name of the database in the filename. The
            $dblower and $dbupper substitutions are also available, for forced
            lowercase and uppercase versions of the name respectively. To
            include a literal $, use $$""")
        self.add_option('paper_size', default='a4paper',
            doc="""The size of paper to use in the document. Must be specified
            as a TeX paper size understood by the geometry package. See your
            LaTeX distribution's geometry package for more information about
            available paper sizes""")
        self.add_option('bookmarks', default='true', convert=self.convert_bool,
            doc="""Specifies whether or not to generate bookmarks in PDF output
            (for use with pdflatex)""")
        self.add_option('binding_size', default='',
            doc="""Specifies the extra space left on the inner edge of the
            paper for binding printed output. Specified as TeX dimensions, i.e.
            an actual measurement or a TeX command. See your LaTeX
            distribution's geometry package for more information""")
        self.add_option('margin_size', default='', convert=self.convert_list,
            doc="""Specifies the paper margins as either a single dimension
            (applies to all sides), two dimensions (top & bottom, left &
            right), or four dimesions (top, right, bottom, left). Left is
            equivalent to inner, and right to outer margins when two_side is
            true. Specified as TeX dimensions, i.e. actual measurements of TeX
            commands. See your LaTeX distribution's geometry package for more
            information""")
        self.add_option('landscape', default='false', convert=self.convert_bool,
            doc="""If true, the document will default to a landscape
            orientation""")
        self.add_option('two_side', default='false', convert=self.convert_bool,
            doc="""If true, the document will use two sided output, resulting
            in mirrored margins for left and right pages""")
        self.add_option('font_packages', default='', convert=self.convert_list,
            doc="""A comma separated list of font packages to load in the
            document preamble.  Common font packages are avant, courier,
            bookman, charter, chancery, and newcent. See your LaTeX
            distribution's psnfss documentation for more information about the
            available font packages""")
        self.add_option('font_size', default='10pt',
            doc="""The default font size used by the document. Can be one of
            10pt (the default), 11pt, or 12pt""")
        self.add_option('encoding', default='utf8x',
            doc="""The character encoding to use for the TeX output file.
            Specified as a TeX encoding. See your LaTeX distribution's inputenc
            documentation for more information on available encodings""")
        self.add_option('doc_title', default='$db Documentation',
            doc="""The title of the document. Accepts $-prefixed substitutions
            (see filename)""")
        self.add_option('author_name', default='',
            doc="""The name of the author of the document""")
        self.add_option('author_email', default='',
            doc="""The e-mail address of the author of the document""")
        self.add_option('copyright', default='',
            doc="""The copyright message to embed in the document""")
        self.add_option('diagrams', default='', convert=self.convert_dbclasses,
            doc="""A comma separated list of the object types for which
            diagrams should be generated, e.g. "schemas, relations". Currently
            only diagrams of schemas and relations (tables, views, and aliases)
            are supported. Note that schema diagrams may require an extremely
            large amount of RAM (1Gb+) to process""")
        self.add_option('toc', default='true', convert=self.convert_bool,
            doc="""Specifies whether or not to generate a Table of Contents at
            the start of the document""")
        self.add_option('toc_level', default='1', convert=self.convert_int,
            doc="""Specifies the depth of headers that will be included in the
            Table of Contents at the start of the document when "toc" is true.
            Defaults to 1 meaning only top level headers are included""")
        self.add_option('index', default='false', convert=self.convert_bool,
            doc="""Specifies whether or not to generate an alphabetical index
            at the end of the document""")
        self.add_option('lang', default='en-US',
            convert=lambda value: self.convert_list(value, separator='-', minvalues=2, maxvalues=2),
            doc="""The ISO639 language code indicating the language that the
            document uses.""")

    def configure(self, config):
        super(OutputPlugin, self).configure(config)
        # Ensure the filename was specified
        if not self.options['filename']:
            raise dbsuite.plugins.PluginConfigurationError('The filename option must be specified')
        self.options['path'] = os.path.dirname(self.options['filename'])
        # If diagrams are requested, check we can find GraphViz in the PATH
        if self.options['diagrams']:
            try:
                import pygraphviz
            except ImportError:
                raise dbsuite.plugins.PluginConfigurationError('Diagrams have been requested, but the Python pygraphviz was not found')
            try:
                import networkx
            except ImportError:
                raise dbsuite.plugins.PluginConfigurationError('Diagrams have been requested, but the Python networkx was not found')

    def substitute(self):
        """Returns the list of options which can accept $-prefixed substitutions."""
        # Override this in descendents if additional string options are introduced
        return ('filename', 'path', 'doc_title')

    def execute(self, database):
        """Invokes the plugin to produce documentation."""
        super(OutputPlugin, self).execute(database)
        # Take a copy of the options if we haven't already
        if not hasattr(self, 'options_templates'):
            self.options_templates = dict(self.options)
        # Build the dictionary of substitutions for $-prefixed variable
        # references in all substitutable options (path et al.)
        values = dict(os.environ)
        values.update({
            'db': database.name,
            'dblower': database.name.lower(),
            'dbupper': database.name.upper(),
            'dbtitle': database.name.title(),
        })
        self.options = dict(self.options_templates)
        for option in self.substitute():
            if isinstance(self.options[option], basestring):
                self.options[option] = Template(self.options[option]).safe_substitute(values)
        doc = TeXDocumentation(database, self.options)
        doc.write()
