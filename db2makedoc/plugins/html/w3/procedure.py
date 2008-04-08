# vim: set noet sw=4 ts=4:

from db2makedoc.db import Procedure
from db2makedoc.plugins.html.w3.document import W3MainDocument

class W3ProcedureDocument(W3MainDocument):
	def __init__(self, site, procedure):
		assert isinstance(procedure, Procedure)
		super(W3ProcedureDocument, self).__init__(site, procedure)
	
	def _create_sections(self):
		access = {
			'N': 'No SQL',
			'C': 'Contains SQL',
			'R': 'Read-only SQL',
			'M': 'Modifies SQL',
		}
		overloads = self.dbobject.schema.procedures[self.dbobject.name]
		self._section('description', 'Description')
		self._add(self._p(self._format_prototype(self.dbobject.prototype)))
		self._add(self._p(self._format_comment(self.dbobject.description)))
		# XXX What about the IN/OUT/INOUT state of procedure parameters?
		self._add(self._dl([
			(param.name, self._format_comment(param.description))
			for param in self.dbobject.param_list
		]))
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
					self._a(self.site.url_document('created.html')),
					self.dbobject.created,
					self._a(self.site.url_document('createdby.html')),
					self.dbobject.owner,
				),
				(
					self._a(self.site.url_document('sqlaccess.html')),
					access[self.dbobject.sql_access],
					self._a(self.site.url_document('nullcall.html')),
					self.dbobject.null_call,
				),
				(
					self._a(self.site.url_document('externalaction.html')),
					self.dbobject.external_action,
					self._a(self.site.url_document('deterministic.html')),
					self.dbobject.deterministic,
				),
				(
					self._a(self.site.url_document('specificname.html')),
					(self.dbobject.specific_name, {'colspan': 3}),
				),
			]
		))
		if len(overloads) > 1:
			self._section('overloads', 'Overloaded Versions')
			self._add(self._table(
				head=[(
					'Prototype',
					'Specific Name',
				)],
				data=[(
					self._format_prototype(overload.prototype),
					self._a(self.site.object_document(overload), overload.specific_name)
				) for overload in overloads if overload != self.dbobject]
			))
		if self.dbobject.create_sql:
			self._section('sql', 'SQL Definition')
			self._add(self._pre(self._format_sql(self.dbobject.create_sql,
				terminator='!'), attrs={'class': 'sql'}))

