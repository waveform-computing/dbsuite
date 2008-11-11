# vim: set noet sw=4 ts=4:

from db2makedoc.db import UniqueKey
from db2makedoc.plugins.html.plain.document import PlainObjectDocument

class PlainUniqueKeyDocument(PlainObjectDocument):
	def __init__(self, site, uniquekey):
		assert isinstance(uniquekey, UniqueKey)
		super(PlainUniqueKeyDocument, self).__init__(site, uniquekey)

	def generate_sections(self):
		tag = self.tag
		result = super(PlainUniqueKeyDocument, self).generate_sections()
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
						tag.td(self.site.url_document('createdby.html').link()),
						tag.td(self.dbobject.owner),
						tag.td(self.site.url_document('colcount.html').link()),
						tag.td(len(self.dbobject.fields))
					)
				),
				summary='Unique key attributes'
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
					summary='Unique key fields'
				)
			))
		if self.dbobject.create_sql:
			result.append((
				'sql', 'SQL Definition',
				self.format_sql(self.dbobject.create_sql, number_lines=True, id='sql-def')
			))
		return result

