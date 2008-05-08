# vim: set noet sw=4 ts=4:

from db2makedoc.db import Check
from db2makedoc.plugins.html.plain.document import PlainMainDocument, tag

class PlainCheckDocument(PlainMainDocument):
	def __init__(self, site, check):
		assert isinstance(check, Check)
		super(PlainCheckDocument, self).__init__(site, check)

	def generate_sections(self):
		result = super(PlainCheckDocument, self).generate_sections()
		fields = sorted(list(self.dbobject.fields), key=lambda field: field.name)
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
				)
			)
		))
		if len(fields) > 0:
			result.append((
				'fields', 'Fields',
				tag.table(
					tag.thead(
						tag.tr(
							tag.th('Field'),
							tag.th('Description')
						)
					),
					tag.tbody((
						tag.tr(
							tag.td(field.name),
							tag.td(self.format_comment(field.description, summary=True))
						) for field in fields
					))
				)
			))
		result.append((
			'sql', 'SQL Definition',
			tag.pre(self.format_sql(self.dbobject.create_sql), class_='sql')
		))
		return result

