#!/bin/env python
# $Header$
# vim: set noet sw=4 ts=4:

import db.uniquekey
import output.html.w3

class W3UniqueKeyDocument(output.html.w3.W3Document):
	def __init__(self, dbobject, htmlver=XHTML10, htmlstyle=STRICT):
		assert isinstance(self.dbobject, db.uniquekey.UniqueKey)
		super(W3UniqueKeyDocument, self).__init__(dbobject, htmlver, htmlstyle)

	def create_sections(self):
		fields = [(field, position) for (position, field) in enumerate(self.dbobject.fields)]
		fields = sorted(fields, key=lambda(field, position): field.name)
		self.section('description', 'Description')
		self.add(self.p(self.format_description(self.dbobject.description)))
		self.section('attributes', 'Attributes')
		self.add(self.p("""The following table notes various "vital statistics"
			of the unique key."""))
		self.add(self.table(
			head=[(
				'Attribute',
				'Value',
				'Attribute',
				'Value'
			)],
			data=[
				(
					self.a('createdby.html', 'Created By', popup=True),
					self.dbobject.definer,
					self.a('colcount.html', '# Columns', popup=True),
					len(fields),
				),
			]))
		if len(fields) > 0:
			self.section('fields', 'Fields')
			self.add(self.p("""The following table contains the fields of the
				key (in alphabetical order) along with the position of the
				field in the key, and the description of the field in the key's
				table."""))
			self.add(self.table(
				head=[(
					'#',
					'Field',
					'Description'
				)],
				data=[(
					position + 1,
					field.name,
					self.format_description(field.description, firstline=True)
				) for (field, position) in fields]
			))
		self.section('sql', 'SQL Definition')
		self.add(self.p("""The SQL which can be used to create the key is given
			below. Note that this is not necessarily the same as the actual
			statement used to create the key (it has been reconstructed from
			the content of the system catalog tables and may differ in a number
			of areas)."""))
		self.add(self.pre(self.format_sql(self.dbobject.createSql), attrs={'class': 'sql'}))

