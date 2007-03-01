# $Header$
# vim: set noet sw=4 ts=4:

from db.check import Check
from output.html.w3.document import W3MainDocument

class W3CheckDocument(W3MainDocument):
	def __init__(self, site, check):
		assert isinstance(check, Check)
		super(W3CheckDocument, self).__init__(site, check)

	def create_sections(self):
		fields = sorted(list(self.dbobject.fields), key=lambda field: field.name)
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
			]
		))
		if len(fields) > 0:
			self.section('fields', 'Fields')
			self.add(self.table(
				head=[(
					"Field",
					"Description"
				)],
				data=[(
					field.name,
					self.format_comment(field.description, summary=True)
				) for field in fields]
			))
		self.section('sql', 'SQL Definition')
		self.add(self.pre(self.format_sql(self.dbobject.create_sql), attrs={'class': 'sql'}))

