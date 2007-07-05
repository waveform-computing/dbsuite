# $Header$
# vim: set noet sw=4 ts=4:

from db2makedoc.db import Tablespace
from db2makedoc.plugins.html.w3.document import W3MainDocument

class W3TablespaceDocument(W3MainDocument):
	def __init__(self, site, tablespace):
		assert isinstance(tablespace, Tablespace)
		super(W3TablespaceDocument, self).__init__(site, tablespace)

	def _create_sections(self):
		tables = [obj for (name, obj) in sorted(self.dbobject.tables.items(), key=lambda (name, obj): name)]
		indexes = [obj for (name, obj) in sorted(self.dbobject.indexes.items(), key=lambda (name, obj): name)]
		self._section('description', 'Description')
		self._add(self._p(self._format_comment(self.dbobject.description)))
		self._section('attributes', 'Attributes')
		self._add(self._table(
			head=[(
				'Attribute',
				'Value',
				'Attribute',
				'Value'
			)],
			data=[
				(
					self._a(self.site.url_document('created.html')),
					self.dbobject.created,
					self._a(self.site.url_document('tables.html')),
					len(tables),
				),
				(
					self._a(self.site.url_document('createdby.html')),
					self.dbobject.owner,
					self._a(self.site.url_document('cardinality.html')),
					len(indexes),
				),
				(
					self._a(self.site.url_document('tbspacetype.html')),
					(self.dbobject.type, {'colspan': 3}),
				),
			]))
		if len(tables) > 0:
			self._section('tables', 'Tables')
			self._add(self._table(
				head=[(
					'Name',
					'Description'
				)],
				data=[(
					self._a_to(table, qualifiedname=True),
					self._format_comment(table.description, summary=True)
				) for table in tables]
			))
		if len(indexes) > 0:
			self._section('indexes', 'Indexes')
			self._add(self._table(
				head=[(
					'Name',
					'Applies To',
					'Description'
				)],
				data=[(
					self._a_to(index, qualifiedname=True),
					self._a_to(index.table, qualifiedname=True),
					self._format_comment(index.description, summary=True)
				) for index in indexes]
			))

