# vim: set noet sw=4 ts=4:

"""Output plugin for plain HTML web pages."""

import os
import logging
import db2makedoc.plugins
import db2makedoc.plugins.html

from db2makedoc.db import (
	Database, Schema, Table, View, Alias, UniqueKey, ForeignKey,
	Check, Index, Trigger, Function, Procedure, Tablespace
)
from db2makedoc.plugins.html.plain.document import (
	PlainSite, PlainSearchDocument, PlainSiteIndexDocument,
	PlainExternalDocument, PlainCSSDocument, PlainPopupDocument
)
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
from db2makedoc.plugins.html.plain.popups import POPUPS


class OutputPlugin(db2makedoc.plugins.html.HTMLOutputPlugin):
	"""Output plugin for plain HTML web pages.

	This output plugin supports generating XHTML documentation with a fairly
	plain style. It includes syntax highlighted SQL information on various
	objects in the database (views, tables, etc.) and diagrams of the schema.
	"""

	def __init__(self):
		"""Initializes an instance of the class."""
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
				raise db2makedoc.plugins.PluginConfigurationError('Diagrams requested, but the Python Imaging Library (PIL) was not found')
		# Build the map of document classes
		self.class_map = {
			Database:   set([PlainDatabaseDocument]),
			Schema:     set([PlainSchemaDocument]),
			Table:      set([PlainTableDocument]),
			View:       set([PlainViewDocument]),
			Alias:      set([PlainAliasDocument]),
			UniqueKey:  set([PlainUniqueKeyDocument]),
			ForeignKey: set([PlainForeignKeyDocument]),
			Check:      set([PlainCheckDocument]),
			Index:      set([PlainIndexDocument]),
			Trigger:    set([PlainTriggerDocument]),
			Function:   set([PlainFunctionDocument]),
			Procedure:  set([PlainProcedureDocument]),
			Tablespace: set([PlainTablespaceDocument]),
		}
		graph_map = {
			Schema:  PlainSchemaGraph,
			Table:   PlainTableGraph,
			View:    PlainViewGraph,
			Alias:   PlainAliasGraph,
		}
		for item in self.options['diagrams']:
			try:
				self.class_map[item].add(graph_map[item])
			except KeyError:
				raise db2makedoc.plugins.PluginConfigurationError('No diagram support for "%s" objects (supported objects are %s)' % (
					item.config_names[0],
					', '.join(c.config_names[0] for c in graph_map.iterkeys()))
				)

	def substitute(self):
		return super(OutputPlugin, self).substitute() + ('stylesheets',)

	def create_documents(self, site):
		# Overridden to add static documents (CSS, PHP, etc.)
		PlainCSSDocument(site)
		if site.search:
			PlainSearchDocument(site)
		for (url, title, body) in POPUPS:
			PlainPopupDocument(site, url, title, body)
		# Call inherited method to generate documents for all objects
		super(OutputPlugin, self).create_documents(site)
		# Add index documents for all indexed classes
		for dbclass in site.index_maps:
			for letter in site.index_maps[dbclass]:
				PlainSiteIndexDocument(site, dbclass, letter)
	
	def create_document(self, dbobject, site):
		# Overridden to generate documents and graphs for specific types of
		# database objects. Document and graph classes are determined from a
		# dictionary lookup (a perfect class match is tested for first,
		# followed by a subclass match).
		classes = self.class_map.get(type(dbobject))
		if classes is None:
			for dbclass in self.class_map:
				if isinstance(dbobject, dbclass):
					classes = self.class_map[dbclass]
		if classes is not None:
			for docclass in classes:
				docclass(site, dbobject)

