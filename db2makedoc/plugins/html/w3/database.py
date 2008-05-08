# vim: set noet sw=4 ts=4:

from db2makedoc.db import Database
from db2makedoc.plugins.html.w3.document import W3MainDocument, tag

class W3DatabaseDocument(W3MainDocument):
	def __init__(self, site, database):
		assert isinstance(database, Database)
		super(W3DatabaseDocument, self).__init__(site, database)

	def generate_sections(self):
		result = super(W3DatabaseDocument, self).generate_sections()
		schemas = [obj for (name, obj) in sorted(self.dbobject.schemas.items(), key=lambda (name, obj):name)]
		tbspaces = [obj for (name, obj) in sorted(self.dbobject.tablespaces.items(), key=lambda (name, obj):name)]
		result.append((
			'description', 'Description',
			tag.p(self.format_comment(self.dbobject.description))
		))
		if len(schemas) > 0:
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
								tag.th('Description')
							)
						),
						tag.tbody((
							tag.tr(
								tag.td(self.site.link_to(schema)),
								tag.td(self.format_comment(schema.description, summary=True))
							) for schema in schemas
						))
					)
				]
			))
		if len(tbspaces) > 0:
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
								tag.th('Description')
							)
						),
						tag.tbody((
							tag.tr(
								tag.td(self.site.link_to(tbspace)),
								tag.td(self.format_comment(tbspace.description, summary=True))
							) for tbspace in tbspaces
						))
					)
				]
			))
		return result

