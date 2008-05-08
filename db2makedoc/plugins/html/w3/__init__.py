# vim: set noet sw=4 ts=4:

"""Output plugin for IBM Intranet w3v8 style web pages."""

import os
import db2makedoc.plugins.html

from db2makedoc.db import Database, Schema, Table, View, Alias, UniqueKey, ForeignKey, Check, Index, Trigger, Function, Procedure, Tablespace
from db2makedoc.plugins.html.w3.document import W3Site, W3CSSDocument, W3JavaScriptDocument, W3SearchDocument, W3PopupDocument
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
from db2makedoc.plugins.html.w3.popups import POPUPS


class OutputPlugin(db2makedoc.plugins.html.HTMLOutputPlugin):
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
		self.site_class = W3Site
		self.add_option('breadcrumbs', default='true', convert=self.convert_bool,
			doc="""If true, breadcrumb links will be shown at the top of each
			page (optional)""")
		self.add_option('last_updated', default='true', convert=self.convert_bool,
			doc= """If true, a line will be added to the top of each page
			showing the date on which the page was generated (optional)""")
		self.add_option('feedback_url', default='http://w3.ibm.com/feedback/',
			doc="""The URL which the feedback link at the top right of each
			page points to (defaults to the standard w3 feedback page)""")
		self.add_option('menu_items', default=None, convert=self.convert_odict,
			doc="""A comma-separated list of name=url values to appear in the
			left-hand menu. The special URL # denotes the position of of the
			database document, e.g.  My App=/myapp,Data
			Dictionary=#,Admin=/admin. If the special URL does not appear in
			the list, the database document will be the last menu entry. Note
			that the "home_title" and "home_url" values are implicitly included
			at the top of this list""")
		self.add_option('related_items', default=None, convert=self.convert_odict,
			doc="""A comma-separated list of links to add after the left-hand
			menu. Links are name=url values, see the "menu_items" description
			for an example""")
		self.add_option('max_graph_size', default='600x800',
			convert=lambda value: self.convert_list(value, separator='x',
			subconvert=lambda value: self.convert_int(value, minvalue=100),
			minvalues=2, maxvalues=2),
			doc="""The maximum size that diagrams are allowed to be on the
			page. If diagrams are larger, they will be resized and a zoom
			function will permit viewing the full size image. Values must be
			specified as "widthxheight", e.g. "640x480". Defaults to
			"600x800".""")
	
	def _config_site(self, site):
		# Overridden to handle extra config attributes in W3Site
		super(OutputPlugin, self)._config_site(site)
		site.breadcrumbs = self.options[BREADCRUMBS_OPTION]
		site.last_updated = self.options[LAST_UPDATED_OPTION]
		site.max_graph_size = self.options[MAX_GRAPH_SIZE_OPTION]
		if self.options[MENU_ITEMS_OPTION]:
			site.menu_items = self.options[MENU_ITEMS_OPTION]
		if self.options[RELATED_ITEMS_OPTION]:
			site.related_items = self.options[RELATED_ITEMS_OPTION]
	
	def create_documents(self, site):
		# Overridden to add static CSS, JavaScript, and HTML documents
		W3CSSDocument(site)
		W3JavaScriptDocument(site)
		if site.search:
			W3SearchDocument(site)
		for (url, title, body) in POPUPS:
			W3PopupDocument(site, url, title, body)
		super(OutputPlugin, self).create_documents(site)
	
	def create_document(self, dbobject, site):
		# Overridden to generate documents and graphs for specific types of
		# database objects. Document and graph classes are determined from a
		# dictionary lookup (a perfect class match is tested for first,
		# followed by a subclass match).
		class_map = {
			Database:   [W3DatabaseDocument],
			Schema:     [W3SchemaGraph, W3SchemaDocument],
			Table:      [W3TableGraph, W3TableDocument],
			View:       [W3ViewGraph, W3ViewDocument],
			Alias:      [W3AliasGraph, W3AliasDocument],
			UniqueKey:  [W3UniqueKeyDocument],
			ForeignKey: [W3ForeignKeyDocument],
			Check:      [W3CheckDocument],
			Index:      [W3IndexDocument],
			Trigger:    [W3TriggerDocument],
			Function:   [W3FunctionDocument],
			Procedure:  [W3ProcedureDocument],
			Tablespace: [W3TablespaceDocument],
		}
		classes = class_map.get(type(dbobject))
		if classes is None:
			for dbclass in class_map:
				if isinstance(dbobject, dbclass):
					classes = class_map[dbclass]
		if classes is not None:
			for docclass in classes:
				docclass(site, dbobject)

