# vim: set noet sw=4 ts=4:

from db2makedoc.db import Index
from db2makedoc.plugins.html.plain.document import PlainMainDocument

class PlainIndexDocument(PlainMainDocument):
	def __init__(self, site, index):
		assert isinstance(index, Index)
		super(PlainIndexDocument, self).__init__(site, index)

	def _create_sections(self):
		fields = [(field, ordering, position) for (position, (field, ordering)) in enumerate(self.dbobject.field_list)]
		fields = sorted(fields, key=lambda (field, ordering, position): field.name)
		self._section('description', 'Description')
		self._add(self._p(self._format_comment(self.dbobject.description)))
		self._section('attributes', 'Attributes')
		self._add(self._table(head=[(
				"Attribute",
				"Value",
				"Attribute",
				"Value"
			)],
			data=[
				(
					'Table',
					self._a_to(self.dbobject.table),
					'Tablespace',
					self._a_to(self.dbobject.tablespace),
				),
				(
					'Created',
					self.dbobject.created,
					'Last Statistics',
					self.dbobject.last_stats,
				),
				(
					'Owner',
					self.dbobject.owner,
					'Columns',
					len(fields),
				),
				(
					'Unique',
					self.dbobject.unique,
					'Cardinality',
					self.dbobject.cardinality,
				),
				# XXX Include size?
				# XXX Include system?
			]
		))
		if len(fields) > 0:
			self._section('fields', 'Fields')
			self._add(self._table(
				head=[(
					"#",
					"Name",
					"Order",
					"Description"
				)],
				data=[(
					position + 1,
					field.name,
					ordering,
					self._format_comment(field.description, summary=True)
				) for (field, ordering, position) in fields]
			))
		self._section('sql', 'SQL Definition')
		self._add(self._pre(self._format_sql(self.dbobject.create_sql),
			attrs={'class': 'sql'}))

