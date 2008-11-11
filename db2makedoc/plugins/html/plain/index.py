# vim: set noet sw=4 ts=4:

from db2makedoc.db import Index
from db2makedoc.plugins.html.plain.document import PlainObjectDocument

class PlainIndexDocument(PlainObjectDocument):
	def __init__(self, site, index):
		assert isinstance(index, Index)
		super(PlainIndexDocument, self).__init__(site, index)

	def generate_sections(self):
		tag = self.tag
		result = super(PlainIndexDocument, self).generate_sections()
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
						tag.td('Table'),
						tag.td(self.site.link_to(self.dbobject.table)),
						tag.td('Tablespace'),
						tag.td(self.site.link_to(self.dbobject.tablespace))
					),
					tag.tr(
						tag.td(self.site.url_document('created.html').link()),
						tag.td(self.dbobject.created),
						tag.td(self.site.url_document('laststats.html').link()),
						tag.td(self.dbobject.last_stats)
					),
					tag.tr(
						tag.td(self.site.url_document('createdby.html').link()),
						tag.td(self.dbobject.owner),
						tag.td(self.site.url_document('colcount.html').link()),
						tag.td(len(self.dbobject.field_list))
					),
					tag.tr(
						tag.td(self.site.url_document('unique.html').link()),
						tag.td(self.dbobject.unique),
						tag.td(self.site.url_document('cardinality.html').link()),
						tag.td(self.dbobject.cardinality)
					)
					# XXX Include size?
					# XXX Include system?
				),
				summary='Index attributes'
			)
		))
		if len(self.dbobject.field_list) > 0:
			result.append((
				'fields', 'Fields',
				tag.table(
					tag.thead(
						tag.tr(
							tag.th('#'),
							tag.th('Name'),
							tag.th('Order'),
							tag.th('Description', class_='nosort')
						)
					),
					tag.tbody((
						tag.tr(
							tag.td(position + 1),
							tag.td(field.name),
							tag.td(ordering),
							tag.td(self.format_comment(field.description, summary=True))
						) for (position, (field, ordering)) in enumerate(self.dbobject.field_list)
					)),
					id='field-ts',
					summary='Index fields'
				)
			))
		if self.dbobject.create_sql:
			result.append((
				'sql', 'SQL Definition',
				self.format_sql(self.dbobject.create_sql, number_lines=True, id='sql-def')
			))
		return result

