# vim: set noet sw=4 ts=4:

from db2makedoc.db import ForeignKey
from db2makedoc.plugins.html.plain.document import PlainMainDocument

class PlainForeignKeyDocument(PlainMainDocument):
	def __init__(self, site, foreignkey):
		assert isinstance(foreignkey, ForeignKey)
		super(PlainForeignKeyDocument, self).__init__(site, foreignkey)
	
	def _create_sections(self):
		rules = {
			'C': 'Cascade',
			'N': 'Set NULL',
			'A': 'Raise Error',
			'R': 'Raise Error',
		}
		self._section('description', 'Description')
		self._add(self._p(self._format_comment(self.dbobject.description)))
		self._section('attributes', 'Attributes')
		self._add(self._table(
			head=[(
				"Attribute",
				"Value",
				"Attribute",
				"Value"
			)],
			data=[
				(
					'Referenced Table',
					self._a_to(self.dbobject.ref_table),
					'Referenced Key',
					self._a_to(self.dbobject.ref_key),
				),
				(
					'Created',
					self.dbobject.created,
					'Owner',
					self.dbobject.owner,
				),
				(
					'Delete Rule',
					rules[self.dbobject.delete_rule],
					'Update Rule',
					rules[self.dbobject.update_rule],
				),
			]
		))
		fields = [(field1, field2, index) for (index, (field1, field2)) in enumerate(self.dbobject.fields)]
		fields = sorted(fields, key=lambda(field1, field2, position): field1.name)
		if len(fields) > 0:
			self._section('fields', 'Fields')
			self._add(self._table(
				head=[(
					"#",
					"Field",
					"Parent",
					"Description"
				)],
				data=[(
					index + 1,
					field1.name,
					field2.name,
					self._format_comment(field1.description, summary=True)
				) for (field1, field2, index) in fields]
			))
		self._section('sql', 'SQL Definition')
		self._add(self._pre(self._format_sql(self.dbobject.create_sql),
			attrs={'class': 'sql'}))

