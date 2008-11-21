# vim: set noet sw=4 ts=4:

from db2makedoc.plugins.html.document import HTMLObjectDocument

class DatabaseDocument(HTMLObjectDocument):
	def generate_body(self):
		body = super(DatabaseDocument, self).generate_body()
		tag = self.tag
		body.append(
			tag.div(
				tag.h3('Description'),
				tag.p(self.format_comment(self.dbobject.description)),
				class_='section',
				id='description'
			)
		)
		if len(self.dbobject.schema_list) > 0:
			body.append(
				tag.div(
					tag.h3('Schemas'),
					tag.p("""The following table contains all schemas (logical
						object containers) in the database. Click on a schema
						name to view the documentation for that schema,
						including a list of all objects that exist within it."""),
					tag.table(
						tag.thead(
							tag.tr(
								tag.th('Name'),
								tag.th('Description', class_='nosort')
							)
						),
						tag.tbody((
							tag.tr(
								tag.td(self.site.link_to(schema)),
								tag.td(self.format_comment(schema.description, summary=True))
							) for schema in self.dbobject.schema_list
						)),
						id='schema-ts',
						summary='Database schemas'
					),
					class_='section',
					id='schemas'
				)
			)
		if self.site.tbspace_list and len(self.dbobject.tablespace_list) > 0:
			body.append(
				tag.div(
					tag.h3('Tablespaces'),
					tag.p("""The following table contains all tablespaces
						(physical object containers) in the database. Click on
						a tablespace name to view the documentation for that
						tablespace, including a list of all tables and/or
						indexes that exist within it."""),
					tag.table(
						tag.thead(
							tag.tr(
								tag.th('Name'),
								tag.th('Description', class_='nosort')
							)
						),
						tag.tbody((
							tag.tr(
								tag.td(self.site.link_to(tbspace)),
								tag.td(self.format_comment(tbspace.description, summary=True))
							) for tbspace in self.dbobject.tablespace_list
						)),
						id='tbspace-ts',
						summary='Database tablespaces'
					),
					class_='section',
					id='tbspaces'
				)
			)
		if self.site.index_docs:
			indexes = []
			ixdoc = self.site.first_index
			while ixdoc:
				indexes.append(ixdoc)
				ixdoc = ixdoc.next
			body.append(
				tag.div(
					tag.h3('Alphabetical Indexes'),
					tag.p("""These are alphabetical lists of objects in the
						database. Indexes are constructed by type (including
						generic types like Relation which encompasses Tables,
						Views, and Aliases), and entries are indexed by their
						unqualified name."""),
					tag.ul(
						tag.li(ixdoc.link())
						for ixdoc in indexes
					),
					class_='section',
					id='indexes'
				)
			)
		return body

