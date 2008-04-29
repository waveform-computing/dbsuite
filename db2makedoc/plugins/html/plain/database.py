# vim: set noet sw=4 ts=4:

from db2makedoc.db import Database
from db2makedoc.plugins.html.plain.document import PlainMainDocument

class PlainDatabaseDocument(PlainMainDocument):
	def __init__(self, site, database):
		assert isinstance(database, Database)
		super(PlainDatabaseDocument, self).__init__(site, database)

	def _create_sections(self):
		schemas = [obj for (name, obj) in sorted(self.dbobject.schemas.items(), key=lambda (name, obj):name)]
		tbspaces = [obj for (name, obj) in sorted(self.dbobject.tablespaces.items(), key=lambda (name, obj):name)]
		self._section('description', 'Description')
		self._add(self._p(self._format_comment(self.dbobject.description)))
		if len(schemas) > 0:
			self._section('schemas', 'Schemas')
			self._add(self._p("""The following table contains all schemas
				(logical object containers) in the database. Click on a schema
				name to view the documentation for that schema, including a
				list of all objects that exist within it."""))
			self._add(self._table(
				head=[(
					"Name",
					"Description"
				)],
				data=[(
					self._a_to(schema),
					self._format_comment(schema.description, summary=True)
				) for schema in schemas]
			))
		if len(tbspaces) > 0:
			self._section('tbspaces', 'Tablespaces')
			self._add(self._p("""The following table contains all tablespaces
				(physical object containers) in the database. Click on a
				tablespace name to view the documentation for that tablespace,
				including a list of all tables and/or indexes that exist within
				it."""))
			self._add(self._table(
				head=[(
					"Name",
					"Description"
				)],
				data=[(
					self._a_to(tbspace),
					self._format_comment(tbspace.description, summary=True)
				) for tbspace in tbspaces]
			))

