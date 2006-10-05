# $Header$
# vim: set noet sw=4 ts=4:

from db.alias import Alias
from output.html.w3.document import W3MainDocument

class W3AliasDocument(W3MainDocument):
	def __init__(self, site, alias):
		assert isinstance(alias, Alias)
		super(W3AliasDocument, self).__init__(site, alias)

	def create_sections(self):
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
					self.a(self.site.documents['created.html']),
					self.dbobject.created,
					self.a(self.site.documents['createdby.html']),
					self.dbobject.definer,
				),
				(
					'Alias For',
					{'colspan': '3', '': self.a_to(self.dbobject.relation, qualifiedname=True)},
				),
			]
		))
		self.section('sql', 'SQL Definition')
		self.add(self.pre(self.format_sql(self.dbobject.create_sql), attrs={'class': 'sql'}))

