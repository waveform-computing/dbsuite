# vim: set noet sw=4 ts=4:

from db2makedoc.db import ForeignKey
from db2makedoc.plugins.html.w3.document import W3ObjectDocument, tag

rules = {
	'C': 'Cascade',
	'N': 'Set NULL',
	'A': 'Raise Error',
	'R': 'Raise Error',
}

class W3ForeignKeyDocument(W3ObjectDocument):
	def __init__(self, site, foreignkey):
		assert isinstance(foreignkey, ForeignKey)
		super(W3ForeignKeyDocument, self).__init__(site, foreignkey)
	
	def generate_sections(self):
		result = super(W3ForeignKeyDocument, self).generate_sections()
		result.append((
			'description', 'Description',
			tag.p(self.format_comment(self.dbobject.description))
		))
		result.append((
			'attributes', 'Attributes',
			tag.table(
				tag.thead(
					tag.tr(
						tag.th('Attribute'),
						tag.th('Value'),
						tag.th('Attribute'),
						tag.th('Value')
					)
				),
				tag.tbody(
					tag.tr(
						tag.td('Referenced Table'),
						tag.td(self.site.link_to(self.dbobject.ref_table)),
						tag.td('Referenced Key'),
						tag.td(self.site.link_to(self.dbobject.ref_key))
					),
					tag.tr(
						tag.td(self.site.url_document('created.html').link()),
						tag.td(self.dbobject.created),
						tag.td(self.site.url_document('createdby.html').link()),
						tag.td(self.dbobject.owner)
					),
					tag.tr(
						tag.td(self.site.url_document('deleterule.html').link()),
						tag.td(rules[self.dbobject.delete_rule]),
						tag.td(self.site.url_document('updaterule.html').link()),
						tag.td(rules[self.dbobject.update_rule])
					)
				)
			)
		))
		if len(self.dbobject.fields) > 0:
			result.append((
				'fields', 'Fields',
				tag.table(
					tag.thead(
						tag.tr(
							tag.th('#'),
							tag.th('Field'),
							tag.th('Parent'),
							tag.th('Description')
						)
					),
					tag.tbody((
						tag.tr(
							tag.td(index + 1),
							tag.td(field1.name),
							tag.td(field2.name),
							tag.td(self.format_comment(field1.description, summary=True))
						) for (index, (field1, field2)) in enumerate(self.dbobject.fields)
					))
				)
			))
		if self.dbobject.create_sql:
			result.append((
				'sql', 'SQL Definition', [
					tag.p(tag.a('Line #s On/Off', href='#', onclick='javascript:return toggleLineNums("sqldef");', class_='zoom')),
					self.format_sql(self.dbobject.create_sql, number_lines=True, id='sqldef')
				]
			))
		return result

