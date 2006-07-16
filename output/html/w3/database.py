#!/bin/env python
# $Header$
# vim: set noet sw=4 ts=4:

import db.database
import output.html.w3

class W3DatabaseDocument(output.html.w3.W3Document):
	def __init__(self, dbobject, htmlver=XHTML10, htmlstyle=STRICT):
		assert isinstance(self.dbobject, db.database.Database):
		super(W3DatabaseDocument, self).__init__(dbobject, htmlver, htmlstyle)

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

