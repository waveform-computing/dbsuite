# vim: set noet sw=4 ts=4:

"""Output plugin for plain HTML web pages."""

import os
import db2makedoc.plugins.html

from db2makedoc.db import Database, Schema, Table, View, Alias, UniqueKey, ForeignKey, Check, Index, Trigger, Function, Procedure, Tablespace
from db2makedoc.plugins.html.plain.document import PlainSite, PlainCSSDocument
from db2makedoc.plugins.html.plain.database import PlainDatabaseDocument
from db2makedoc.plugins.html.plain.schema import PlainSchemaDocument, PlainSchemaGraph
from db2makedoc.plugins.html.plain.table import PlainTableDocument, PlainTableGraph
from db2makedoc.plugins.html.plain.view import PlainViewDocument, PlainViewGraph
from db2makedoc.plugins.html.plain.alias import PlainAliasDocument, PlainAliasGraph
from db2makedoc.plugins.html.plain.uniquekey import PlainUniqueKeyDocument
from db2makedoc.plugins.html.plain.foreignkey import PlainForeignKeyDocument
from db2makedoc.plugins.html.plain.check import PlainCheckDocument
from db2makedoc.plugins.html.plain.index import PlainIndexDocument
from db2makedoc.plugins.html.plain.trigger import PlainTriggerDocument
from db2makedoc.plugins.html.plain.function import PlainFunctionDocument
from db2makedoc.plugins.html.plain.procedure import PlainProcedureDocument
from db2makedoc.plugins.html.plain.tablespace import PlainTablespaceDocument

# Constants
LAST_UPDATED_OPTION = 'last_updated'
STYLESHEETS_OPTION = 'stylesheets'
MAX_GRAPH_SIZE_OPTION = 'max_graph_size'

# Localizable strings
LAST_UPDATED_DESC = """If true, the generated date of each page will be added
	to the footer (optional)"""
STYLESHEETS_DESC = """A comma separated list of additional stylesheets
	which each generated HTML page will link to (optional)"""
MAX_GRAPH_SIZE_DESC="""The maximum size that diagrams are allowed to be on
	the page. If diagrams are larger, they will be resized and a zoom function
	will permit viewing the full size image. Values must be specified as
	"widthxheight", e.g. "640x480". Defaults to "600x800"."""


class OutputPlugin(db2makedoc.plugins.html.HTMLOutputPlugin):
	"""Output plugin for plain HTML web pages.

	This output plugin supports generating XHTML documentation with a fairly
	plain style.  It includes syntax highlighted SQL information on various
	objects in the database (views, tables, etc.) and diagrams of the schema.
	"""

	def __init__(self):
		"""Initializes an instance of the class."""
		super(OutputPlugin, self).__init__()
		self.add_option(LAST_UPDATED_OPTION, default='true', doc=LAST_UPDATED_DESC,
			convert=self.convert_bool)
		self.add_option(STYLESHEETS_OPTION, default=None, doc=STYLESHEETS_DESC,
			convert=self.convert_list)
		self.add_option(MAX_GRAPH_SIZE_OPTION, default='600x800', doc=MAX_GRAPH_SIZE_DESC,
			convert=lambda value: self.convert_list(value, separator='x',
			subconvert=lambda value: self.convert_int(value, minvalue=100),
			minvalues=2, maxvalues=2))
	
	def _init_site(self, database):
		# Overridden to use the PlainSite class instead of HTMLSite
		return PlainSite(database)

	def _config_site(self, site):
		# Overridden to handle extra config attributes in PlainSite
		super(OutputPlugin, self)._config_site(site)
		site.last_updated = self.options[LAST_UPDATED_OPTION]
		site.stylesheets = self.options[STYLESHEETS_OPTION]
		site.max_graph_size = self.options[MAX_GRAPH_SIZE_OPTION]
	
	def _create_documents(self, site):
		# Overridden to add static CSS and JavaScript documents
		PlainCSSDocument(site)
		super(OutputPlugin, self)._create_documents(site)
	
	def _create_document(self, dbobject, site):
		# Overridden to generate documents and graphs for specific types of
		# database objects. Document and graph classes are determined from a
		# dictionary lookup (a perfect class match is tested for first,
		# followed by a subclass match).
		class_map = {
			Database:   [PlainDatabaseDocument],
			Schema:     [PlainSchemaGraph, PlainSchemaDocument],
			Table:      [PlainTableGraph, PlainTableDocument],
			View:       [PlainViewGraph, PlainViewDocument],
			Alias:      [PlainAliasGraph, PlainAliasDocument],
			UniqueKey:  [PlainUniqueKeyDocument],
			ForeignKey: [PlainForeignKeyDocument],
			Check:      [PlainCheckDocument],
			Index:      [PlainIndexDocument],
			Trigger:    [PlainTriggerDocument],
			Function:   [PlainFunctionDocument],
			Procedure:  [PlainProcedureDocument],
			Tablespace: [PlainTablespaceDocument],
		}
		classes = class_map.get(type(dbobject))
		if classes is None:
			for dbclass in class_map:
				if isinstance(dbobject, dbclass):
					classes = class_map[dbclass]
		if classes is not None:
			for docclass in classes:
				docclass(site, dbobject)

