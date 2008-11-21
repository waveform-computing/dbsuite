# vim: set noet sw=4 ts=4:

from db2makedoc.plugins.html.document import HTMLObjectDocument

class CheckDocument(HTMLObjectDocument):
	def generate_body(self):
		body = super(CheckDocument, self).generate_body()
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
							tag.td(self.site.url_document('created.html').link()),
							tag.td(self.dbobject.created),
							tag.td(self.site.url_document('createdby.html').link()),
							tag.td(self.dbobject.owner)
						)
					),
					summary='Check attributes'
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
								tag.th('Field'),
								tag.th('Description', class_='nosort')
							)
						),
						tag.tbody((
							tag.tr(
								tag.td(field.name),
								tag.td(self.format_comment(field.description, summary=True))
							) for field in self.dbobject.fields
						)),
						id='field-ts',
						summary='Check fields'
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

