#!/bin/env python
# $Header$
# vim: set noet sw=4 ts=4:

import db.tablespace
import output.html.w3

class W3TablespaceDocument(output.html.w3.W3Document):
	def __init__(self, dbobject, htmlver=XHTML10, htmlstyle=STRICT):
		assert isinstance(self.dbobject, db.tablespace.Tablespace)
		super(W3TablespaceDocument, self).__init__(dbobject, htmlver, htmlstyle)

	def create_sections(self):
		tables = [obj for (name, obj) in sorted(self.dbobject.tables.items(), key=lambda (name, obj): name)]
		indexes = [obj for (name, obj) in sorted(self.dbobject.indexes.items(), key=lambda (name, obj): name)]
		self.section('description', 'Description')
		self.add(self.p(self.format_description(self.dbobject.description)))
		self.section('attributes', 'Attributes')
		self.add(self.p("""The following table notes various "vital statistics"
			of the tablespace."""))
		self.add(self.table(
			head=[(
				'Attribute',
				'Value',
				'Attribute',
				'Value'
			)],
			data=[
				(
					self.a('created.html', 'Created', popup=True),
					self.dbobject.created,
					self.a('tables.html', '# Tables', popup=True),
					len(tables),
				),
				(
					self.a('createdby.html', 'Created By', popup=True),
					self.dbobject.definer,
					self.a('cardinality.html', '# Indexes', popup=True),
					len(indexes),
				),
				(
					self.a('managedby.html', 'Managed By', popup=True),
					self.dbobject.managedBy,
					self.a('self.dbobjecttype.html', 'Data Type', popup=True),
					self.dbobject.dataType,
				),
				(
					self.a('extentsize.html', 'Extent Size', popup=True),
					self.dbobject.extentSize,
					self.a('prefetchsize.html', 'Prefetch Size', popup=True),
					self.dbobject.prefetchSize,
				),
				(
					self.a('pagesize.html', 'Page Size', popup=True),
					self.dbobject.pageSize,
					self.a('droprecovery.html', 'Drop Recovery', popup=True),
					self.dbobject.dropRecovery,
				),
			]))
		if len(tables) > 0:
			self.section('tables', 'Tables')
			self.add(self.p("""The following table contains all the tables that
				the tablespace contains. Click on a table name to view the
				documentation for that table."""))
			self.add(self.table(
				head=[(
					'Name',
					'Description'
				)],
				data=[(
					self.a_to(table, qualifiedname=True),
					self.format_description(table.description, firstline=True)
				) for table in tables]
			))
		if len(indexes) > 0:
			self.section('indexes', 'Indexes')
			self.add(self.p("""The following table contains all the indexes
				that the tablespace contains. Click on an index name to view
				the documentation for that index."""))
			self.add(self.table(
				head=[(
					'Name',
					'Applies To',
					'Description'
				)],
				data=[(
					self.a_to(index, qualifiedname=True),
					self.a_to(index.table, qualifiedname=True),
					self.format_description(index.description, firstline=True)
				) for index in indexes]
			))

