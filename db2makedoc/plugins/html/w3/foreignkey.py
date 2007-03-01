# $Header$
# vim: set noet sw=4 ts=4:

from db.foreignkey import ForeignKey
from output.html.w3.document import W3MainDocument

class W3ForeignKeyDocument(W3MainDocument):
	def __init__(self, site, foreignkey):
		assert isinstance(foreignkey, ForeignKey)
		super(W3ForeignKeyDocument, self).__init__(site, foreignkey)
	
	def create_sections(self):
		self.section('description', 'Description')
		self.add(self.p(self.format_comment(self.dbobject.description)))
		self.section('attributes', 'Attributes')
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
					self.a_to(self.dbobject.ref_table),
					'Referenced Key',
					self.a_to(self.dbobject.ref_key),
				),
				(
					self.a(self.site.documents['created.html']),
					self.dbobject.created,
					self.a(self.site.documents['createdby.html']),
					self.dbobject.definer,
				),
				(
					self.a(self.site.documents['enforced.html']),
					self.dbobject.enforced,
					self.a(self.site.documents['queryoptimize.html']),
					self.dbobject.query_optimize,
				),
				(
					self.a(self.site.documents['deleterule.html']),
					self.dbobject.delete_rule,
					self.a(self.site.documents['updaterule.html']),
					self.dbobject.update_rule,
				),
			]
		))
		fields = [(field1, field2, index) for (index, (field1, field2)) in enumerate(self.dbobject.fields)]
		fields = sorted(fields, key=lambda(field1, field2, position): field1.name)
		if len(fields) > 0:
			self.section('fields', 'Fields')
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
					self.format_comment(field1.description, summary=True)
				) for (field1, field2, index) in fields]
			))
		self.section('sql', 'SQL Definition')
		self.add(self.pre(self.format_sql(self.dbobject.create_sql),
			attrs={'class': 'sql'}))

