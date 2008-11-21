# vim: set noet sw=4 ts=4:

from db2makedoc.plugins.html.document import HTMLObjectDocument

class TablespaceDocument(HTMLObjectDocument):
	def generate_body(self):
		body = super(TablespaceDocument, self).generate_body()
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
					),
					summary='Tablespace attributes'
				),
				class_='section',
				id='attributes'
			)
		)
		if len(self.dbobject.table_list) > 0:
			body.append(
				tag.div(
					tag.h3('Tables'),
					tag.p("""The following table lists all tables that store
						their data (but not necessarily their indexes or LOB
						data) in this tablespace. Click on a table's name to
						view the documentation for that table."""),
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
						id='table-ts',
						summary='Tablespace tables'
					),
					class_='section',
					id='tables'
				)
			)
		if len(self.dbobject.index_list) > 0:
			body.append(
				tag.div(
					tag.h3('Indexes'),
					tag.p("""The following table lists all indexes that store
						their data in this tablespace, and the tables each
						index applies to. Click on an index's name to view the
						documentation for that index. Click on a table's name
						to view the documentation for that table."""),
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
						id='index-ts',
						summary='Tablespace indexes'
					),
					class_='section',
					id='indexes'
				)
			)
		return body

