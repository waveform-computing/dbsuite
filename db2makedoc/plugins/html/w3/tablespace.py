# $Header$
# vim: set noet sw=4 ts=4:

from db2makedoc.db.tablespace import Tablespace
from db2makedoc.plugins.html.w3.document import W3MainDocument

class W3TablespaceDocument(W3MainDocument):
	def __init__(self, site, tablespace):
		assert isinstance(tablespace, Tablespace)
		super(W3TablespaceDocument, self).__init__(site, tablespace)

	def create_sections(self):
		tables = [obj for (name, obj) in sorted(self.dbobject.tables.items(), key=lambda (name, obj): name)]
		indexes = [obj for (name, obj) in sorted(self.dbobject.indexes.items(), key=lambda (name, obj): name)]
		self.section('description', 'Description')
		self.add(self.p(self.format_comment(self.dbobject.description)))
		self.section('attributes', 'Attributes')
		self.add(self.table(
			head=[(
				'Attribute',
				'Value',
				'Attribute',
				'Value'
			)],
			data=[
				(
					self.a(self.site.documents['created.html']),
					self.dbobject.created,
					self.a(self.site.documents['tables.html']),
					len(tables),
				),
				(
					self.a(self.site.documents['createdby.html']),
					self.dbobject.definer,
					self.a(self.site.documents['cardinality.html']),
					len(indexes),
				),
				(
					self.a(self.site.documents['managedby.html']),
					self.dbobject.managed_by,
					self.a(self.site.documents['tbspacetype.html']),
					self.dbobject.data_type,
				),
				(
					self.a(self.site.documents['extentsize.html']),
					self.dbobject.extent_size,
					self.a(self.site.documents['prefetchsize.html']),
					self.dbobject.prefetch_size,
				),
				(
					self.a(self.site.documents['pagesize.html']),
					self.dbobject.page_size,
					self.a(self.site.documents['droprecovery.html']),
					self.dbobject.drop_recovery,
				),
			]))
		if len(tables) > 0:
			self.section('tables', 'Tables')
			self.add(self.table(
				head=[(
					'Name',
					'Description'
				)],
				data=[(
					self.a_to(table, qualifiedname=True),
					self.format_comment(table.description, summary=True)
				) for table in tables]
			))
		if len(indexes) > 0:
			self.section('indexes', 'Indexes')
			self.add(self.table(
				head=[(
					'Name',
					'Applies To',
					'Description'
				)],
				data=[(
					self.a_to(index, qualifiedname=True),
					self.a_to(index.table, qualifiedname=True),
					self.format_comment(index.description, summary=True)
				) for index in indexes]
			))

