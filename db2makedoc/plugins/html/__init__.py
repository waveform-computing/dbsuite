# $Header$
# vim: set noet sw=4 ts=4:

"""Provides a set of base classes for HTML based output plugins.

This package defines a set of utility classes which make it easier to construct
output plugins capable of producing HTML documents (or, more precisely, a
website containing HTML documents amongst other things).
"""

import os
import codecs
import db2makedoc.plugins
from db2makedoc.plugins.html.document import WebSite

PATH_OPTION = 'path'
ENCODING_OPTION = 'encoding'
HOME_TITLE_OPTION = 'home_title'
HOME_URL_OPTION = 'home_url'
AUTHOR_NAME_OPTION = 'author_name'
AUTHOR_MAIL_OPTION = 'author_email'
COPYRIGHT_OPTION = 'copyright'
SITE_TITLE_OPTION = 'site_title'

PATH_DESC = """The folder into which all files (HTML, CSS, SVG, etc.) will
	be written (optional)"""
ENCODING_DESC = """The character encoding to use for all text-based files
	(HTML, JavaScript, CSS, SVG, etc.) (optional)"""
HOME_TITLE_DESC = """The title of the homepage link included in all
	documents"""
HOME_URL_DESC = """The URL of the homepage link included in all documents.
	This can point anywhere; it does not have to be a link to one of the
	documents output by the plugin"""
AUTHOR_NAME_DESC = """The name of the author of the generated
	documentation (optional)"""
AUTHOR_MAIL_DESC = """The e-mail address of the author of the generated
	documentation (optional)"""
COPYRIGHT_DESC = """The copyright message to embed in the generated
	documentation (optional)"""
SITE_TITLE_DESC="""The title of the site as a whole. Defaults to "dbname
	Documentation" where dbname is the name of the database for which
	documentation is being generated"""


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
		self.add_option(PATH_OPTION, default='.', doc=PATH_DESC, convert=self.convert_path)
		self.add_option(ENCODING_OPTION, default='UTF-8', doc=ENCODING_DESC)
		self.add_option(HOME_TITLE_OPTION, default='Home', doc=HOME_TITLE_DESC)
		self.add_option(HOME_URL_OPTION, default='/', doc=HOME_URL_DESC)
		self.add_option(AUTHOR_NAME_OPTION, default=None, doc=AUTHOR_NAME_DESC)
		self.add_option(AUTHOR_MAIL_OPTION, default=None, doc=AUTHOR_MAIL_DESC)
		self.add_option(COPYRIGHT_OPTION, default=None, doc=COPYRIGHT_DESC)
		self.add_option(SITE_TITLE_OPTION, default=None, doc=SITE_TITLE_DESC)
	
	def configure(self, config):
		super(HTMLOutputPlugin, self).configure(config)
		# check that the specified encoding exists (the following lookup()
		# method will raise a LookupError if it can't find the encoding)
		codecs.lookup(self.options[ENCODING_OPTION])

	def execute(self, database):
		"""Invokes the plugin to produce documentation.
		
		Descendent classes should NOT override this method, but instead
		override the _init_site(), _config_site(), _create_documents(), and/or
		_create_document() methods below which are called directly or
		indirectly from this one.
		"""
		super(HTMLOutputPlugin, self).execute(database)
		site = self._init_site(database)
		assert isinstance(site, WebSite)
		self._config_site(site)
		self._create_documents(site)
		site.write()
	
	def _init_site(self, database):
		"""Instantiates an object to represent the collection of documents.
		
		Descendents should override this method if they wish to use a more
		specialized class than the generic WebSite class implemented in this
		plugin. Naturally, in such cases this inherited method should NOT be
		called.
		"""
		return WebSite(database)

	def _config_site(self, site):
		"""Configures the site instance.

		This method simply exists to copy settings from the plugin's
		configuraiton to the site object. Descendents should override this if
		they introduce new configuration options.

		Note that plugin configuration validation should still be performed
		by overriding the inherited configure() method.
		"""
		site.base_url = ''
		site.base_path = self.options[PATH_OPTION]
		site.encoding = self.options[ENCODING_OPTION]
		site.author_name = self.options[AUTHOR_NAME_OPTION]
		site.author_email = self.options[AUTHOR_MAIL_OPTION]
		site.copyright = self.options[COPYRIGHT_OPTION]
		if self.options[SITE_TITLE_OPTION]:
			site.title = self.options[SITE_TITLE_OPTION]

	def _create_documents(self, site):
		"""Creates the documents in the web-site.

		The basic implementation in this class simply calls _create_document
		for each object in the database hierarchy, along with the site object
		which will own the document. The _create_document method should be
		overridden in descendents to create a document of the appropriate
		class.

		This method should be overridden in descendents if they wish to add
		extra (non database object) documents to the site. For example, style
		sheets, JavaScript libraries, or static HTML documents.
		"""
		site.database.touch(self._create_document, site)
	
	def _create_document(self, dbobject, site):
		"""Creates a document for a specific database object.

		This a stub method to be overridden in descendents. The concrete
		implementation should create a document instance (or instances)
		appropriate to the type of database object passed to the method. The
		site parameter provides the site object to be passed to the constructor
		of the document(s) class(es).
		"""
		pass
