# $Header$
# vim: set noet sw=4 ts=4:

"""Output plugin for IBM Intranet w3v8 style web pages."""

import os
import db2makedoc.plugins.html

from db2makedoc.db import Database, Schema, Table, View, Alias, UniqueKey, ForeignKey, Check, Index, Trigger, Function, Procedure, Tablespace
from db2makedoc.plugins.html.w3.document import W3Site, W3CSSDocument, W3JavaScriptDocument, W3PopupDocument
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
BREADCRUMBS_OPTION = 'breadcrumbs'
LAST_UPDATED_OPTION = 'last_updated'
FEEDBACK_URL_OPTION = 'feedback_url'
MENU_ITEMS_OPTION = 'menu_items'
RELATED_ITEMS_OPTION = 'related_items'

# Localizable strings
BREADCRUMBS_DESC = """If true, breadcrumb links will be shown at the
	top of each page (optional)"""
LAST_UPDATED_DESC = """If true, a line will be added to the top of
	each page showing the date on which the page was generated
	(optional)"""
FEEDBACK_URL_DESC = """The URL which the feedback link at the top right of
	each page points to (defaults to the standard w3 feedback page)"""
MENU_ITEMS_DESC="""A comma-separated list of name=url values to appear in
	the left-hand menu. The special URL # denotes the position of of the
	database document, e.g.  My App=/myapp,Data Dictionary=#,Admin=/admin. If
	the special URL does not appear in the list, the database document will
	be the last menu entry. Note that the "%s" and "%s" values are implicitly
	included at the top of this list""" % (
		db2makedoc.plugins.html.HOME_TITLE_OPTION,
		db2makedoc.plugins.html.HOME_URL_OPTION
	)
RELATED_ITEMS_DESC="""A comma-separated list of links to add after the
	left-hand menu.  Links are name=url values, see the "%s" description for an
	example""" % MENU_ITEMS_OPTION


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
		self.add_option(BREADCRUMBS_OPTION, default='true', doc=BREADCRUMBS_DESC, convert=self.convert_bool)
		self.add_option(LAST_UPDATED_OPTION, default='true', doc=LAST_UPDATED_DESC, convert=self.convert_bool)
		self.add_option(FEEDBACK_URL_OPTION, default='http://w3.ibm.com/feedback/', doc=FEEDBACK_URL_DESC)
		self.add_option(MENU_ITEMS_OPTION, default=None, doc=MENU_ITEMS_DESC, convert=self.convert_odict)
		self.add_option(RELATED_ITEMS_OPTION, default=None, doc=RELATED_ITEMS_DESC, convert=self.convert_odict)
	
	def _init_site(self, database):
		# Overridden to use the W3Site class instead of HTMLSite
		return W3Site(database)

	def _config_site(self, site):
		# Overridden to handle extra config attributes in W3Site
		super(OutputPlugin, self)._config_site(site)
		site.breadcrumbs = self.options[BREADCRUMBS_OPTION]
		site.last_updated = self.options[LAST_UPDATED_OPTION]
		if self.options[MENU_ITEMS_OPTION]:
			site.menu_items = self.options[MENU_ITEMS_OPTION]
		if self.options[RELATED_ITEMS_OPTION]:
			site.related_items = self.options[RELATED_ITEMS_OPTION]
	
	def _create_documents(self, site):
		# Overridden to add static CSS, JavaScript, and HTML documents
		W3CSSDocument(site)
		W3JavaScriptDocument(site)
		for (url, title, body) in W3_POPUPS:
			W3PopupDocument(site, url, title, body)
		super(OutputPlugin, self)._create_documents(site)
	
	def _create_document(self, dbobject, site):
		# Overridden to generate documents and graphs for specific types of
		# database objects. Document and graph classes are determined from a
		# dictionary lookup (a perfect class match is check for first, followed
		# by a subclass match).
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

