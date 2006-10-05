# $Header$
# vim: set noet sw=4 ts=4:

from db.uniquekey import UniqueKey
from output.html.w3.document import W3MainDocument

class W3UniqueKeyDocument(W3MainDocument):
	def __init__(self, site, uniquekey):
		assert isinstance(uniquekey, UniqueKey)
		super(W3UniqueKeyDocument, self).__init__(site, uniquekey)

	def create_sections(self):
		fields = [(field, position) for (position, field) in enumerate(self.dbobject.fields)]
		fields = sorted(fields, key=lambda(field, position): field.name)
		self.section('description', 'Description')
		self.add(self.p(self.format_description(self.dbobject.description)))
		self.section('attributes', 'Attributes')
		self.add(self.table(
			head=[(
				'Attribute',
				'Value',
				'Attribute',
				'Value'
			)],
			data=[
				(
					self.a(self.site.documents['createdby.html']),
					self.dbobject.definer,
					self.a(self.site.documents['colcount.html']),
					len(fields),
				),
			]))
		if len(fields) > 0:
			self.section('fields', 'Fields')
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
		self.add(self.pre(self.format_sql(self.dbobject.create_sql), attrs={'class': 'sql'}))

