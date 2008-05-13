# vim: set noet sw=4 ts=4:

"""Provides a set of base classes for HTML based output plugins.

This package defines a set of utility classes which make it easier to construct
output plugins capable of producing HTML documents (or, more precisely, a
website containing HTML documents amongst other things).
"""

import os
import sys
mswindows = sys.platform[:5] == 'win32'
import codecs
import db2makedoc.plugins
from db2makedoc.plugins.html.document import WebSite, SQLCSSDocument
from db2makedoc.graph import DEFAULT_CONVERTER

class HTMLOutputPlugin(db2makedoc.plugins.OutputPlugin):
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
		self.add_option('path', default='.', convert=self.convert_path, 
			doc="""The folder into which all files (HTML, CSS, SVG, etc.) will
			be written""")
		self.add_option('encoding', default='UTF-8',
			doc="""The character encoding to use for all text-based files
			(HTML, JavaScript, CSS, SVG, etc.)""")
		self.add_option('home_title', default='Home',
			doc="""The title of the homepage link included in all documents""")
		self.add_option('home_url', default='/',
			doc="""The URL of the homepage link included in all documents.
			This can point anywhere; it does not have to be a link to one of
			the documents output by the plugin""")
		self.add_option('author_name', default='',
			doc="""The name of the author of the generated documents""")
		self.add_option('author_email', default='',
			doc="""The e-mail address of the author of the generated documents""")
		self.add_option('copyright', default='',
			doc="""The copyright message to embed in the generated documents""")
		self.add_option('site_title', default=None,
			doc="""The title of the site as a whole. Defaults to "dbname
			Documentation" where dbname is the name of the database for which
			documentation is being generated""")
		self.add_option('search', default='false', convert=self.convert_bool,
			doc="""If True, a full-text-search database will be generated and
			a small PHP script will be included with the output for searching
			purposes""")
		self.add_option('diagrams', default='',
			convert=lambda value: self.convert_set(value,
			subconvert=lambda value: value.lower()),
			doc="""A comma separated list of the object types for which
			diagrams should be generated. Supported values are currently:
			alias, schema, table, view, relation (equivalent to
			"alias,table,view"). Node that schema diagrams may require an
			extremely large amount of RAM to process """)
		self.add_option('lang', default='en-US', convert=lambda value: self.convert_list(value, separator='-', minvalues=2, maxvalues=2),
			doc="""The ISO639 language code indicating the language that the
			site uses. Defaults to en-US. Note that this is used both for the
			XML language, and for the language-specific stemming algorithm
			(if search is true)""")
		self.add_option('threads', default='1', convert=lambda value: self.convert_int(value, minvalue=1),
			doc="""The number of threads to utilize when writing the output.
			Defaults to 1. If you have more than 1 processor or core, setting
			this to 2 or more may yield better performance (although values
			above 4 usually make no difference)""")
	
	def configure(self, config):
		super(HTMLOutputPlugin, self).configure(config)
		# Check that the specified encoding exists (the following lookup()
		# method will raise a LookupError if it can't find the encoding)
		try:
			codecs.lookup(self.options['encoding'])
		except:
			raise db2makedoc.plugins.PluginConfigurationError('Unknown character encoding "%s"' % self.options['encoding'])
		# If search is True, check that the Xapian bindings are
		# available
		if self.options['search']:
			try:
				import xapian
			except ImportError:
				raise db2makedoc.plugins.PluginConfigurationError('Search is enabled, but the Python Xapian bindings were not found')
		# If diagrams are requested, check we can find GraphViz in the PATH
		if self.options['diagrams']:
			gvexe = DEFAULT_CONVERTER
			if mswindows:
				gvexe = os.extsep.join([gvexe, 'exe'])
			found = reduce(lambda x,y: x or y, [
				os.path.exists(os.path.join(path, gvexe))
				for path in os.environ.get('PATH', os.defpath).split(os.pathsep)
			], False)
			if not found:
				raise db2makedoc.plugins.PluginConfigurationError('Diagrams requested, but the GraphViz utility (%s) was not found in the PATH' % gvexe)

	def execute(self, database):
		"""Invokes the plugin to produce documentation.
		
		Descendent classes should NOT override this method, but instead
		override the methods of the website class. To customize the class,
		set self.site_class to a different class in descendent constructors.
		"""
		super(HTMLOutputPlugin, self).execute(database)
		site = self.site_class(database, self.options)
		self.create_documents(site)
		site.write()
	
	def create_documents(self, site):
		"""Creates the documents in the web-site.

		The basic implementation in this class simply calls create_document for
		each object in the database hierarchy.  The create_document method
		should be overridden in descendents to create a document of the
		appropriate class.

		This method should be overridden in descendents if they wish to add
		extra (non database object) documents to the site. For example, style
		sheets, JavaScript libraries, or static HTML documents.
		"""
		SQLCSSDocument(site)
		site.database.touch(self.create_document, site)
	
	def create_document(self, dbobject, site):
		"""Creates a document for a specific database object.

		This a stub method to be overridden in descendents. The concrete
		implementation should create a document instance (or instances)
		appropriate to the type of database object passed to the method.
		"""
		pass
	
