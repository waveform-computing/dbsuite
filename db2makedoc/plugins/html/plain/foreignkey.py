# vim: set noet sw=4 ts=4:

from db2makedoc.db import ForeignKey
from db2makedoc.plugins.html.plain.document import PlainObjectDocument, tag

rules = {
	'C': 'Cascade',
	'N': 'Set NULL',
	'A': 'Raise Error',
	'R': 'Raise Error',
}

class PlainForeignKeyDocument(PlainObjectDocument):
	def __init__(self, site, foreignkey):
		assert isinstance(foreignkey, ForeignKey)
		super(PlainForeignKeyDocument, self).__init__(site, foreignkey)
	
	def generate_sections(self):
		result = super(PlainForeignKeyDocument, self).generate_sections()
		fields = [(field1, field2, index) for (index, (field1, field2)) in enumerate(self.dbobject.fields)]
		fields = sorted(fields, key=lambda(field1, field2, position): field1.name)
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
		if len(fields) > 0:
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
						) for (field1, field2, index) in fields
					))
				)
			))
		result.append((
			'sql', 'SQL Definition',
			self.format_sql(self.dbobject.create_sql, number_lines=True)
		))
		return result

