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

"""Provides a set of base classes for HTML based output plugins.

This package defines a set of utility classes which make it easier to construct
output plugins capable of producing HTML documents (or, more precisely, a
website containing HTML documents amongst other things).
"""

from __future__ import (
    unicode_literals,
    print_function,
    absolute_import,
    division,
    )

import os
import sys
import codecs
import logging
from string import Template

import dbsuite.db
import dbsuite.plugins
from dbsuite.plugins.html.document import WebSite


class HTMLOutputPlugin(dbsuite.plugins.OutputPlugin):
    """Abstract base class for HTML output plugins.

    Note: This class is deliberately not called "OutputPlugin" as it cannot be
    used directly (it is an abstract class). Calling it something other than
    "OutputPlugin" prevents it from being seen by the main application as a
    valid output plugin.

    Developers wishing to derive a concrete plugin from this class need to call
    their class "OutputPlugin" in order for the main application to use it.
    """

    def __init__(self):
        super(HTMLOutputPlugin, self).__init__()
        self.site_class = WebSite
        self.add_option(
            'path', default='.', convert=self.convert_path,
            doc='The folder into which all files (HTML, CSS, SVG, etc.) will '
            'be written. Use $db or ${db} to include the name of the database '
            'in the path. The $dblower, $dbupper, and $dbtitle substitutions '
            'are also available, for forced lowercase, UPPERCASE, and '
            'Titlecase versions of the name respectively. You may also refer '
            'to environment variables with $-prefixed substitutions. To '
            'include a literal $, use $$.')
        self.add_option(
            'top', default='index',
            doc='The base name (without path or extension) of the top-level '
            'file in the output (i.e. the file documenting the database itself). '
            'The default "index" results in the top-level file being named '
            '"index.html". Change this if you wish to have a separate index.html '
            'file which is not touched by dbsuite. Accepts $-prefixed '
            'substitutions (see path)')
        self.add_option(
            'encoding', default='UTF-8',
            doc='The character encoding to use for all text-based files '
            '(HTML, JavaScript, CSS, SVG, etc.)')
        self.add_option(
            'home_title', default='Home',
            doc='The title of the homepage link included in all documents. '
            'Accepts $-prefixed substitutions (see path')
        self.add_option(
            'home_url', default='/',
            doc='The URL of the homepage link included in all documents. '
            'This can point anywhere; it does not have to be a link to one of '
            'the documents output by the plugin. Accepts $-prefixed '
            'substitutions (see path)')
        self.add_option(
            'icon_url', default='/favicon.ico',
            doc='The location of the icon (aka "favicon") for the generated '
            'pages. Defaults to the standard /favicon.ico location. Accepts '
            '$-prefixed substitutions (see path)')
        self.add_option(
            'icon_type', default='image/x-icon',
            doc='The MIME type of the icon referenced by the icon_url option. '
            'Defaults to the Microsoft icon format (image/x-icon).')
        self.add_option(
            'author_name', default='',
            doc='The name of the author of the generated documents')
        self.add_option(
            'author_email', default='',
            doc='The e-mail address of the author of the generated documents')
        self.add_option(
            'copyright', default='',
            doc='The copyright message to embed in the generated documents')
        self.add_option(
            'site_title', default='$db Documentation',
            doc='The title of the site as a whole. Defaults to "$db '
            'Documentation" where dbname is the name of the database for which '
            'documentation is being generated. Accepts $-prefixed substitutions '
            '(see path)')
        self.add_option(
            'tbspace_list', default='true', convert=self.convert_bool,
            doc='If True, include a list of all tablespaces in the top level '
            'document. For some database architectures (e.g. DB2 for z/OS) this '
            'list tends to be inordinately long and relatively useless')
        self.add_option(
            'search', default='false', convert=self.convert_bool,
            doc='If True, a full-text-search database will be generated and '
            'a small PHP script will be included with the output for searching '
            'purposes')
        self.add_option(
            'diagrams', default='', convert=self.convert_dbclasses,
            doc='A comma separated list of the object types for which '
            'diagrams should be generated, e.g. "schemas, relations". Currently '
            'only diagrams of schemas and relations (tables, views, and aliases) '
            'are supported. Note that schema diagrams may require an extremely '
            'large amount of RAM (1Gb+) to process')
        self.add_option(
            'indexes', default='',
            convert=lambda value: self.convert_dbclasses(value, abstract=True),
            doc='A comma separated list of the object types for which '
            'alphabetical index lists should be generated, e.g. "schemas, '
            'tables, fields, all". The value "all" generates an index of all '
            'objects in the database, regardless of type.')
        self.add_option(
            'lang', default='en-US',
            convert=lambda value: self.convert_list(value, separator='-', minvalues=2, maxvalues=2),
            doc='The ISO639 language code indicating the language that the '
            'site uses. Note that this is used both for the XML language, and '
            'for the language-specific stemming algorithm (if search is '
            'true)')
        self.add_option(
            'threads', default='1',
            convert=lambda value: self.convert_int(value, minvalue=1),
            doc='The number of threads to utilize when writing the output. '
            'Defaults to 1. If you have more than 1 processor or core, setting '
            'this to 2 or more may yield better performance (although values '
            'above 4 usually make no difference)')

    def configure(self, config):
        super(HTMLOutputPlugin, self).configure(config)
        # Check that the specified encoding exists (the following lookup()
        # method will raise a LookupError if it can't find the encoding)
        try:
            codecs.lookup(self.options['encoding'])
        except LookupError:
            raise dbsuite.plugins.PluginConfigurationError(
                'Unknown character encoding "%s"' % self.options['encoding'])
        # If search is True, check that the Xapian bindings are available
        if self.options['search']:
            try:
                import xapian
            except ImportError:
                raise dbsuite.plugins.PluginConfigurationError(
                    'Search is enabled, but the Python Xapian bindings were '
                    'not found')
        # If diagrams are requested, check pygraphviz is available
        if self.options['diagrams']:
            try:
                import pygraphviz
            except ImportError:
                raise dbsuite.plugins.PluginConfigurationError(
                    'Diagrams have been requested, but the Python pygraphviz '
                    'library was not found')

    def substitute(self):
        """Returns the list of options which can accept $-prefixed substitutions."""
        # Override this in descendents if additional string options are introduced
        return ('path', 'top', 'home_title', 'home_url', 'site_title', 'icon_url')

    def build_site(self, database):
        """Invokes the plugin to produce documentation.

        Descendent classes should NOT override this method, but instead
        override the methods of the WebSite class. To customize the class,
        set self.site_class to a different class in descendent constructors.

        The process of producing the site and associated document objects
        was moved into this method which is specific to HTML output plugins
        for the purpose of making a "live" server of database documentation
        which didn't require the writing of the documentation to disk.
        """
        # Take a copy of the options if we haven't already
        if not hasattr(self, 'options_templates'):
            self.options_templates = dict(self.options)
        # Build the dictionary of substitutions for $-prefixed variable
        # references in all substitutable options (path et al.)
        # XXX What if we're called multiple times? This will screw-up
        # susbtitutions which include $
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
        return self.site_class(database, self.options)

    def execute(self, database):
        """Invokes the plugin to write documentation to disk.

        Descendent classes should NOT override this method, but instead
        override the methods of the Website class. To customize the class,
        set self.site_class to a different class in descendent constructors.
        """
        super(HTMLOutputPlugin, self).execute(database)
        self.build_site(database).write()
