#!/bin/env python
# $Header$
# vim: set noet sw=4 ts=4:

import db.check
import output.html.w3

class W3CheckDocument(output.html.w3.W3Document):
	def __init__(self, dbobject, htmlver=XHTML10, htmlstyle=STRICT):
		assert isinstance(self.dbobject, db.check.Check)
		super(W3CheckDocument, self).__init__(dbobject, htmlver, htmlstyle)

	def create_sections(self):
		fields = sorted(list(self.dbobject.fields), key=lambda field: field.name)
		self.section('description', 'Description')
		self.add(self.p(self.format_description(self.dbobject.description)))
		self.section('attributes', 'Attributes')
		self.add(self.p("""The following table notes various "vital statistics" of the check constraint."""))
		self.add(self.table(
			head=[(
				"Attribute",
				"Value",
				"Attribute",
				"Value"
			)]
			data=[
				(
					self.a("created.html", "Created", popup=True),
					self.dbobject.created,
					self.a("createdby.html", "Created By", popup=True),
					self.dbobject.definer,
				),
				(
					self.a("enforced.html", "Enforced", popup=True),
					self.dbobject.enforced,
					self.a("queryoptimize.html", "Query Optimizing", popup=True),
					self.dbobject.queryOptimize,
				),
			]
		))
		if len(fields) > 0:
			self.section('fields', 'Fields')
			self.add(self.p("""The following table contains the fields that the
				check references in it's SQL expression, and the description of
				the field in the check's table."""))
			self.add(self.table(
				head=[(
					"Field",
					"Description"
				)]
				data=[(
					field.name,
					self.format_description(field.description, firstline=True)
				) for field in fields]
			))
		self.section('sql', 'SQL Definition')
		self.add(self.p("""The SQL which can be used to create the check is given
			below. Note that this is not necessarily the same as the actual
			statement used to create the check (it has been reconstructed from
			the content of the system catalog tables and may differ in a number
			of areas)."""))
		self.add(self.pre(self.format_sql(self.dbobject.createSql), attrs={'class': 'sql'}))

