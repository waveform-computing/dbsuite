# vim: set noet sw=4 ts=4:

from db2makedoc.db import UniqueKey
from db2makedoc.plugins.html.w3.document import W3ObjectDocument, tag

class W3UniqueKeyDocument(W3ObjectDocument):
	def __init__(self, site, uniquekey):
		assert isinstance(uniquekey, UniqueKey)
		super(W3UniqueKeyDocument, self).__init__(site, uniquekey)

	def generate_sections(self):
		result = super(W3UniqueKeyDocument, self).generate_sections()
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
						tag.td(self.site.url_document('createdby.html').link()),
						tag.td(self.dbobject.owner),
						tag.td(self.site.url_document('colcount.html').link()),
						tag.td(len(fields))
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
			'sql', 'SQL Definition', [
				tag.p(tag.a('Line #s On/Off', href='#', onclick='javascript:return toggleLineNums("sqldef");', class_='zoom')),
				self.format_sql(self.dbobject.create_sql, number_lines=True, id='sqldef')
			]
		))
		return result

