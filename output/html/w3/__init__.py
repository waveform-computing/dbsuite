#!/usr/bin/env python
# $Header$
# vim: set noet sw=4 ts=4:

"""Output plugin for w3v8 style web pages.

This output plugin supports generating XHTML documentation conforming to the
internal IBM w3v8 style. It includes syntax highlighted SQL information on
various objects in the database (views, tables, etc.) and SVG diagrams of the
schema.
"""

from output.html.w3.document import W3Site
from output.html.w3.database import W3DatabaseDocument
from output.html.w3.schema import W3SchemaDocument
from output.html.w3.table import W3TableDocument
from output.html.w3.view import W3ViewDocument
from output.html.w3.alias import W3AliasDocument
from output.html.w3.uniquekey import W3UniqueKeyDocument
from output.html.w3.foreignkey import W3ForeignKeyDocument
from output.html.w3.check import W3CheckDocument
from output.html.w3.index import W3IndexDocument
from output.html.w3.trigger import W3TriggerDocument
from output.html.w3.function import W3FunctionDocument
from output.html.w3.procedure import W3ProcedureDocument
from output.html.w3.tablespace import W3TablespaceDocument

options = {
	'path': 'The root folder into which all files (HTML, CSS, SVG, etc.) will be written',
}

def Output(database, outputpath):
	# Construct the site object
	site = W3Site(database)
	site.baseurl = ''
	site.basepath = outputpath
	# XXX Construct the SQL stylesheet
	# XXX Construct all popups
	# Construct all document objects (the document objects will add themselves
	# to the documents attribute of the site object)
	W3DatabaseDocument(site, database)
	for schema in database.schemas.itervalues():
		W3SchemaDocument(site, schema)
		for table in schema.tables.itervalues():
			W3TableDocument(site, table)
			for uniquekey in table.uniqueKeys.itervalues():
				W3UniqueKeyDocument(site, uniquekey)
			for foreignkey in table.foreignKeys.itervalues():
				W3ForeignKeyDocument(site, foreignkey)
			for check in table.checks.itervalues():
				W3CheckDocument(site, check)
		for view in schema.views.itervalues():
			W3ViewDocument(site, view)
		for alias in schema.aliases.itervalues():
			W3AliasDocument(site, alias)
		for index in schema.indexes.itervalues():
			W3IndexDocument(site, index)
		for function in schema.specificFunctions.itervalues():
			W3FunctionDocument(site, function)
		for procedure in schema.specificProcedures.itervalues():
			W3ProcedureDocument(site, procedure)
		for trigger in schema.triggers.itervalues():
			W3TriggerDocument(site, trigger)
	for tablespace in database.tablespaces.itervalues():
		W3TablespaceDocument(site, tablespace)
	# Write all the documents in the site
	for doc in site.documents:
		doc.write()

