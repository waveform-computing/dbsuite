# $Header$
# vim: set noet sw=4 ts=4:

from db2makedoc.db.foreignkey import ForeignKey
from db2makedoc.plugins.html.w3.document import W3MainDocument

class W3ForeignKeyDocument(W3MainDocument):
	def __init__(self, site, foreignkey):
		assert isinstance(foreignkey, ForeignKey)
		super(W3ForeignKeyDocument, self).__init__(site, foreignkey)
	
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
					self._a(self.site.documents['created.html']),
					self.dbobject.created,
					self._a(self.site.documents['createdby.html']),
					self.dbobject.owner,
				),
				(
					self._a(self.site.documents['deleterule.html']),
					rules[self.dbobject.delete_rule],
					self._a(self.site.documents['updaterule.html']),
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

