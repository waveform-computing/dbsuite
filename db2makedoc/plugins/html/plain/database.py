# vim: set noet sw=4 ts=4:

from db2makedoc.db import Database
from db2makedoc.plugins.html.plain.document import PlainObjectDocument

class PlainDatabaseDocument(PlainObjectDocument):
	def __init__(self, site, database):
		assert isinstance(database, Database)
		super(PlainDatabaseDocument, self).__init__(site, database)

	def generate_sections(self):
		tag = self.tag
		result = super(PlainDatabaseDocument, self).generate_sections()
		result.append((
			'description', 'Description',
			tag.p(self.format_comment(self.dbobject.description))
		))
		if len(self.dbobject.schema_list) > 0:
			result.append((
				'schemas', 'Schemas', [
					tag.p("""The following table contains all schemas (logical
					object containers) in the database. Click on a schema name
					to view the documentation for that schema, including a list
					of all objects that exist within it."""),
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
					)
				]
			))
		if self.site.tbspace_list and len(self.dbobject.tablespace_list) > 0:
			result.append((
				'tbspaces', 'Tablespaces', [
					tag.p("""The following table contains all tablespaces
					(physical object containers) in the database. Click on a
					tablespace name to view the documentation for that
					tablespace, including a list of all tables and/or indexes
					that exist within it."""),
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
					)
				]
			))
		if self.site.index_docs:
			indexes = []
			doc = self.site.first_index
			while doc:
				indexes.append(doc)
				doc = doc.next
			result.append((
				'indexes', 'Alphabetical Indexes', [
					tag.p("""These are alphabetical lists of objects in the
					database. Indexes are constructed by type (including
					generic types like Relation which encompasses Tables,
					Views, and Aliases), and entries are indexed by their
					unqualified name."""),
					tag.ul(
						tag.li(doc.link())
						for doc in indexes
					)
				]
			))
		return result

