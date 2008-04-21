# vim: set noet sw=4 ts=4:

from db2makedoc.db import UniqueKey
from db2makedoc.plugins.html.w3.document import W3MainDocument

class W3UniqueKeyDocument(W3MainDocument):
	def __init__(self, site, uniquekey):
		assert isinstance(uniquekey, UniqueKey)
		super(W3UniqueKeyDocument, self).__init__(site, uniquekey)

	def _create_sections(self):
		fields = [(field, position) for (position, field) in enumerate(self.dbobject.fields)]
		fields = sorted(fields, key=lambda(field, position): field.name)
		self._section('description', 'Description')
		self._add(self._p(self._format_comment(self.dbobject.description)))
		self._section('attributes', 'Attributes')
		self._add(self._table(
			head=[(
				'Attribute',
				'Value',
				'Attribute',
				'Value'
			)],
			data=[
				(
					self._a(self.site.url_document('createdby.html')),
					self.dbobject.owner,
					self._a(self.site.url_document('colcount.html')),
					len(fields),
				),
			]))
		if len(fields) > 0:
			self._section('fields', 'Fields')
			self._add(self._table(
				head=[(
					'#',
					'Field',
					'Description'
				)],
				data=[(
					position + 1,
					field.name,
					self._format_comment(field.description, summary=True)
				) for (field, position) in fields]
			))
		self._section('sql', 'SQL Definition')
		self._add(self._pre(self._format_sql(self.dbobject.create_sql),
			attrs={'class': 'sql'}))

