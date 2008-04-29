# vim: set noet sw=4 ts=4:

from db2makedoc.db import Procedure
from db2makedoc.plugins.html.plain.document import PlainMainDocument

class PlainProcedureDocument(PlainMainDocument):
	def __init__(self, site, procedure):
		assert isinstance(procedure, Procedure)
		super(PlainProcedureDocument, self).__init__(site, procedure)
	
	def _create_sections(self):
		access = {
			None: 'No SQL',
			'N':  'No SQL',
			'C':  'Contains SQL',
			'R':  'Read-only SQL',
			'M':  'Modifies SQL',
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
					'Created',
					self.dbobject.created,
					'Owner',
					self.dbobject.owner,
				),
				(
					'SQL Access',
					access[self.dbobject.sql_access],
					'NULL Call',
					self.dbobject.null_call,
				),
				(
					'External Action',
					self.dbobject.external_action,
					'Deterministic',
					self.dbobject.deterministic,
				),
				(
					'Specific Name',
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
			self._add(self._pre(self._format_sql(self.dbobject.create_sql),
				attrs={'class': 'sql'}))

