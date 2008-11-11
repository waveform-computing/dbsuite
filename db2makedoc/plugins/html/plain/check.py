# vim: set noet sw=4 ts=4:

from db2makedoc.db import Check
from db2makedoc.plugins.html.plain.document import PlainObjectDocument

class PlainCheckDocument(PlainObjectDocument):
	def __init__(self, site, check):
		assert isinstance(check, Check)
		super(PlainCheckDocument, self).__init__(site, check)

	def generate_sections(self):
		tag = self.tag
		result = super(PlainCheckDocument, self).generate_sections()
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
						tag.td(self.site.url_document('created.html').link()),
						tag.td(self.dbobject.created),
						tag.td(self.site.url_document('createdby.html').link()),
						tag.td(self.dbobject.owner)
					)
				),
				summary='Check attributes'
			)
		))
		if len(self.dbobject.fields) > 0:
			result.append((
				'fields', 'Fields',
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
				)
			))
		if self.dbobject.create_sql:
			result.append((
				'sql', 'SQL Definition',
				self.format_sql(self.dbobject.create_sql, number_lines=True, id='sql-def')
			))
		return result

