#!/bin/env python
# $Header$
# vim: set noet sw=4 ts=4:

from db.foreignkey import ForeignKey
from output.html.w3.document import W3Document

class W3ForeignKeyDocument(W3Document):
	def __init__(self, site, foreignkey):
		assert isinstance(foreignkey, ForeignKey)
		super(W3ForeignKeyDocument, self).__init__(site, foreignkey)
	
	def create_sections(self):
		self.section('description', 'Description')
		self.add(self.p(self.format_description(self.dbobject.description)))
		self.section('attributes', 'Attributes')
		self.add(self.p("""The following table notes various "vital statistics"
			of the foreign key."""))
		self.add(self.table(
			head=[(
				"Attribute",
				"Value",
				"Attribute",
				"Value"
			)],
			data=[
				(
					'Referenced Table',
					self.a_to(self.dbobject.refTable),
					'Referenced Key',
					self.a_to(self.dbobject.refKey),
				),
				(
					self.a("created.html", "Created", popup=True),
					self.dbobject.created,
					self.a("createdby.html", "Created By", popup=True),
					escape(self.dbobject.definer),
				),
				(
					self.a("enforced.html", "Enforced", popup=True),
					self.dbobject.enforced,
					self.a("queryoptimize.html", "Query Optimizing", popup=True),
					self.dbobject.queryOptimize,
				),
				(
					self.a("deleterule.html", "Delete Rule", popup=True),
					self.dbobject.deleteRule,
					self.a("updaterule.html", "Update Rule", popup=True),
					self.dbobject.updateRule,
				),
			]
		))
		fields = [(field1, field2, index) for (index, (field1, field2)) in enumerate(self.dbobject.fields)]
		fields = sorted(fields, key=lambda(field1, field2, position): field1.name)
		if len(fields) > 0:
			self.section('fields', 'Fields')
			self.add(self.p("""The following table contains the fields of the
				key (in alphabetical order) along with the position of the
				field in the key, the field in the parent table that is
				referenced by the key, and the description of the field in the
				key's table."""))
			self.add(self.table(
				head=[(
					"#",
					"Field",
					"Parent",
					"Description"
				)],
				data=[(
					index + 1,
					field1.name,
					field2.name,
					self.format_description(field1.description, firstline=True)
				) for (field1, field2, index) in fields]
			))
		self.section('sql', 'SQL Definition')
		self.add(self.p("""The SQL which can be used to create the key is given
			below. Note that this is not necessarily the same as the actual
			statement used to create the key (it has been reconstructed from
			the content of the system catalog tables and may differ in a number
			of areas)."""))
		self.add(self.pre(self.format_sql(self.dbobject.createSql), attrs={'class': 'sql'}))

