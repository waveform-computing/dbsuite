#!/bin/env python
# $Header$
# vim: set noet sw=4 ts=4:

from db.database import Database
from output.html.w3.document import W3Document

class W3DatabaseDocument(W3Document):
	def __init__(self, site, database):
		assert isinstance(database, Database)
		super(W3DatabaseDocument, self).__init__(site, database)

	def create_sections(self):
		schemas = [obj for (name, obj) in sorted(self.dbobject.schemas.items(), key=lambda (name, obj):name)]
		tbspaces = [obj for (name, obj) in sorted(self.dbobject.tablespaces.items(), key=lambda (name, obj):name)]
		self.section('description', 'Description')
		self.add(self.p(self.format_description(self.dbobject.description)))
		if len(schemas) > 0:
			self.section('schemas', 'Schemas')
			self.add(self.p("""The following table contains all schemas
				(logical object containers) in the database. Click on a schema
				name to view the documentation for that schema, including a
				list of all objects that exist within it."""))
			self.add(self.table(
				head=[(
					"Name",
					"Description"
				)],
				data=[(
					self.a_to(schema),
					self.format_description(schema.description, firstline=True)
				) for schema in schemas]
			))
		if len(tbspaces) > 0:
			self.section('tbspaces', 'Tablespaces')
			self.add(self.p("""The following table contains all tablespaces
				(physical object containers) in the database. Click on a
				tablespace name to view the documentation for that tablespace,
				including a list of all tables and/or indexes that exist within
				it."""))
			self.add(self.table(
				head=[(
					"Name",
					"Description"
				)],
				data=[(
					self.a_to(tbspace),
					self.format_description(tbspace.description, firstline=True)
				) for tbspace in tbspaces]
			))

