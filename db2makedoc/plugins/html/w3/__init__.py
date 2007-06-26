# $Header$
# vim: set noet sw=4 ts=4:

"""Output plugin for IBM Intranet w3v8 style web pages."""

import os
import db2makedoc.outputplugin
from db2makedoc.plugins.html.w3.document import W3Site, W3CSSDocument, W3PopupDocument
from db2makedoc.plugins.html.w3.database import W3DatabaseDocument
from db2makedoc.plugins.html.w3.schema import W3SchemaDocument, W3SchemaGraph
from db2makedoc.plugins.html.w3.table import W3TableDocument, W3TableGraph
from db2makedoc.plugins.html.w3.view import W3ViewDocument, W3ViewGraph
from db2makedoc.plugins.html.w3.alias import W3AliasDocument, W3AliasGraph
from db2makedoc.plugins.html.w3.uniquekey import W3UniqueKeyDocument
from db2makedoc.plugins.html.w3.foreignkey import W3ForeignKeyDocument
from db2makedoc.plugins.html.w3.check import W3CheckDocument
from db2makedoc.plugins.html.w3.index import W3IndexDocument
from db2makedoc.plugins.html.w3.trigger import W3TriggerDocument
from db2makedoc.plugins.html.w3.function import W3FunctionDocument
from db2makedoc.plugins.html.w3.procedure import W3ProcedureDocument
from db2makedoc.plugins.html.w3.tablespace import W3TablespaceDocument
from db2makedoc.plugins.html.w3.popups import W3_POPUPS

# Constants
PATH_OPTION = 'path'
AUTHOR_NAME_OPTION = 'author_name'
AUTHOR_MAIL_OPTION = 'author_email'
COPYRIGHT_OPTION = 'copyright'

# Localizable strings
PATH_DESC = 'The folder into which all files (HTML, CSS, SVG, etc.) will be written (optional)'
AUTHOR_NAME_DESC = 'The name of the author of the generated documentation (optional)'
AUTHOR_MAIL_DESC = 'The e-mail address of the author of the generated documentation (optional)'
COPYRIGHT_DESC = 'The copyright message to embed in the generated documentation (optional)'

# Plugin options dictionary
options = {
	PATH_OPTION: PATH_DESC,
	AUTHOR_NAME_OPTION: AUTHOR_NAME_DESC,
	AUTHOR_MAIL_OPTION: AUTHOR_MAIL_DESC,
	COPYRIGHT_OPTION: COPYRIGHT_DESC,
}

class OutputPlugin(db2makedoc.outputplugin.OutputPlugin):
	"""Output plugin for IBM Intranet w3v8 style web pages.

	This output plugin supports generating XHTML documentation conforming to
	the internal IBM w3v8 style [1]. It includes syntax highlighted SQL
	information on various objects in the database (views, tables, etc.) and
	diagrams of the schema.

	[1] http://w3.ibm.com/standards/intranet/homepage/v8/index.html
	"""

	def __init__(self):
		"""Initializes an instance of the class."""
		super(OutputPlugin, self).__init__()
		self.add_option(PATH_OPTION, default='.', doc=PATH_DESC)
		self.add_option(AUTHOR_NAME_OPTION, default=None, doc=AUTHOR_NAME_DESC)
		self.add_option(AUTHOR_MAIL_OPTION, default=None, doc=AUTHOR_MAIL_DESC)
		self.add_option(COPYRIGHT_OPTION, default=None, doc=COPYRIGHT_DESC)

	def execute(self, database):
		"""Invokes the plugin to produce documentation."""
		super(OutputPlugin, self).execute(database)
		site = W3Site(database)
		site.baseurl = ''
		site.basepath = os.path.expanduser(os.path.expandvars(self.options[PATH_OPTION]))
		if AUTHOR_NAME_OPTION in config:
			site.author_name = self.options[AUTHOR_NAME_OPTION]
		if AUTHOR_MAIL_OPTION in config:
			site.author_email = self.options[AUTHOR_MAIL_OPTION]
		if COPYRIGHT_OPTION in config:
			site.copyright = self.options[COPYRIGHT_OPTION]
		# Construct the supplementary SQL stylesheet
		W3CSSDocument(site, 'sql.css')
		# Construct all popups (this must be done before constructing database
		# object documents as some of the templates refer to the popup document
		# objects)
		for (url, title, body) in W3_POPUPS:
			W3PopupDocument(site, url, title, body)
		# Construct all graphs (the graphs will add themselves to the documents
		# attribute of the site object)
		for schema in database.schemas.itervalues():
			W3SchemaGraph(site, schema)
			for table in schema.tables.itervalues():
				W3TableGraph(site, table)
			for view in schema.views.itervalues():
				W3ViewGraph(site, view)
			for alias in schema.aliases.itervalues():
				W3AliasGraph(site, alias)
		# Construct all document objects (the document objects will add themselves
		# to the documents attribute of the site object)
		W3DatabaseDocument(site, database)
		for schema in database.schemas.itervalues():
			W3SchemaDocument(site, schema)
			for table in schema.tables.itervalues():
				W3TableDocument(site, table)
				for uniquekey in table.unique_keys.itervalues():
					W3UniqueKeyDocument(site, uniquekey)
				for foreignkey in table.foreign_keys.itervalues():
					W3ForeignKeyDocument(site, foreignkey)
				for check in table.checks.itervalues():
					W3CheckDocument(site, check)
			for view in schema.views.itervalues():
				W3ViewDocument(site, view)
			for alias in schema.aliases.itervalues():
				W3AliasDocument(site, alias)
			for index in schema.indexes.itervalues():
				W3IndexDocument(site, index)
			for function in schema.specific_functions.itervalues():
				W3FunctionDocument(site, function)
			for procedure in schema.specific_procedures.itervalues():
				W3ProcedureDocument(site, procedure)
			for trigger in schema.triggers.itervalues():
				W3TriggerDocument(site, trigger)
		for tablespace in database.tablespaces.itervalues():
			W3TablespaceDocument(site, tablespace)
		# Write all the documents in the site
		for doc in site.documents.itervalues():
			doc.write()

