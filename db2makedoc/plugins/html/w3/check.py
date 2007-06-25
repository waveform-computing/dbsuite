# $Header$
# vim: set noet sw=4 ts=4:

from db2makedoc.db import Check
from db2makedoc.plugins.html.w3.document import W3MainDocument

class W3CheckDocument(W3MainDocument):
	def __init__(self, site, check):
		assert isinstance(check, Check)
		super(W3CheckDocument, self).__init__(site, check)

	def _create_sections(self):
		fields = sorted(list(self.dbobject.fields), key=lambda field: field.name)
		self._section('description', 'Description')
		self._add(self._p(self._format_comment(self.dbobject.description)))
		self._section('attributes', 'Attributes')
		self._add(self._table(
			head=[(
				"Attribute",
				"Value",
				"Attribute",
				"Value"
			)],
			data=[
				(
					self._a(self.site.documents['created.html']),
					self.dbobject.created,
					self._a(self.site.documents['createdby.html']),
					self.dbobject.owner,
				),
			]
		))
		if len(fields) > 0:
			self._section('fields', 'Fields')
			self._add(self._table(
				head=[(
					"Field",
					"Description"
				)],
				data=[(
					field.name,
					self._format_comment(field.description, summary=True)
				) for field in fields]
			))
		self._section('sql', 'SQL Definition')
		self._add(self._pre(self._format_sql(self.dbobject.create_sql), attrs={'class': 'sql'}))

