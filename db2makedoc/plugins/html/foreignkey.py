# vim: set noet sw=4 ts=4:

from db2makedoc.plugins.html.document import HTMLObjectDocument

rules = {
	'C': 'Cascade',
	'N': 'Set NULL',
	'A': 'Raise Error',
	'R': 'Raise Error',
}

class ForeignKeyDocument(HTMLObjectDocument):
	def generate_body(self):
		body = super(ForeignKeyDocument, self).generate_body()
		tag = self.tag
		body.append(
			tag.div(
				tag.h3('Description'),
				tag.p(self.format_comment(self.dbobject.description)),
				class_='section',
				id='description'

			)
		)
		body.append(
			tag.div(
				tag.h3('Attributes'),
				tag.p_attributes(self.dbobject),
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
					),
					summary='Foreign key attributes'
				),
				class_='section',
				id='attributes'
			)
		)
		if len(self.dbobject.fields) > 0:
			body.append(
				tag.div(
					tag.h3('Fields'),
					tag.p_constraint_fields(self.dbobject),
					tag.table(
						tag.thead(
							tag.tr(
								tag.th('#'),
								tag.th('Field'),
								tag.th('Parent'),
								tag.th('Description', class_='nosort')
							)
						),
						tag.tbody((
							tag.tr(
								tag.td(index + 1),
								tag.td(field1.name),
								tag.td(field2.name),
								tag.td(self.format_comment(field1.description, summary=True))
							) for (index, (field1, field2)) in enumerate(self.dbobject.fields)
						)),
						id='field-ts',
						summary='Foreign key fields'
					),
					class_='section',
					id='fields'
				)
			)
		if self.dbobject.create_sql:
			body.append(
				tag.div(
					tag.h3('SQL Definition'),
					tag.p_sql_definition(self.dbobject),
					self.format_sql(self.dbobject.create_sql, number_lines=True, id='sql-def'),
					class_='section',
					id='sql'
				)
			)
		return body

