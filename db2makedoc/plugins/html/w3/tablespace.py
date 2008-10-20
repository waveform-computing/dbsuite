# vim: set noet sw=4 ts=4:

from db2makedoc.db import Tablespace
from db2makedoc.plugins.html.w3.document import W3ObjectDocument, tag

class W3TablespaceDocument(W3ObjectDocument):
	def __init__(self, site, tablespace):
		assert isinstance(tablespace, Tablespace)
		super(W3TablespaceDocument, self).__init__(site, tablespace)

	def generate_sections(self):
		result = super(W3TablespaceDocument, self).generate_sections()
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
						tag.td(self.site.url_document('tables.html').link()),
						tag.td(len(self.dbobject.table_list))
					),
					tag.tr(
						tag.td(self.site.url_document('createdby.html').link()),
						tag.td(self.dbobject.owner),
						tag.td(self.site.url_document('indexes.html').link()),
						tag.td(len(self.dbobject.index_list))
					),
					tag.tr(
						tag.td(self.site.url_document('tbspacetype.html').link()),
						tag.td(self.dbobject.type, colspan=3)
					)
				)
			)
		))
		if len(self.dbobject.table_list) > 0:
			result.append((
				'tables', 'Tables',
				tag.table(
					tag.thead(
						tag.tr(
							tag.th('Name'),
							tag.th('Description', class_='nosort')
						)
					),
					tag.tbody((
						tag.tr(
							tag.td(self.site.link_to(table)),
							tag.td(self.format_comment(table.description, summary=True))
						) for table in self.dbobject.table_list
					)),
					id='table-ts'
				)
			))
		if len(self.dbobject.index_list) > 0:
			result.append((
				'indexes', 'Indexes',
				tag.table(
					tag.thead(
						tag.tr(
							tag.th('Name'),
							tag.th('Applies To'),
							tag.th('Description', class_='nosort')
						)
					),
					tag.tbody((
						tag.tr(
							tag.td(self.site.link_to(index)),
							tag.td(self.site.link_to(index.table)),
							tag.td(self.format_comment(index.description, summary=True))
						) for index in self.dbobject.index_list
					)),
					id='index-ts'
				)
			))
		return result

