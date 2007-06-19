# $Header$
# vim: set noet sw=4 ts=4:

from db2makedoc.db.function import Function
from db2makedoc.plugins.html.w3.document import W3MainDocument

class W3FunctionDocument(W3MainDocument):
	def __init__(self, site, function):
		assert isinstance(function, Function)
		super(W3FunctionDocument, self).__init__(site, function)
	
	def _create_sections(self):
		functype = {
			'C': 'Column/Aggregate',
			'R': 'Row',
			'T': 'Table',
			'S': 'Scalar',
		}
		access = {
			' ': 'No SQL', # XXX Workaround for a bug in DB2 UDB LUW v8.2 (UCASE has SQL_DATA_ACCESS = ' ' when it should be 'N')
			'N': 'No SQL',
			'C': 'Contains SQL',
			'R': 'Read-only SQL',
			'M': 'Modifies SQL',
		}
		overloads = self.dbobject.schema.functions[self.dbobject.name]
		params = list(self.dbobject.param_list) # Take a copy of the parameter list
		if self.dbobject.type in ['R', 'T']:
			# Extend the list with return parameters if the function is a ROW
			# or TABLE function (and hence, returns multiple named parms)
			params.extend(self.dbobject.return_list)
		self._section('description', 'Description')
		self._add(self._p(self._format_prototype(self.dbobject.prototype)))
		self._add(self._p(self._format_comment(self.dbobject.description)))
		self._add(self._dl([
			(param.name, self._format_comment(param.description))
			for param in params
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
					self._a(self.site.documents['created.html']),
					self.dbobject.created,
					self._a(self.site.documents['createdby.html']),
					self.dbobject.owner,
				),
				(
					self._a(self.site.documents['functype.html']),
					functype[self.dbobject.type],
					self._a(self.site.documents['sqlaccess.html']),
					access[self.dbobject.sql_access],
				),
				(
					self._a(self.site.documents['externalaction.html']),
					self.dbobject.external_action,
					self._a(self.site.documents['deterministic.html']),
					self.dbobject.deterministic,
				),
				(
					self._a(self.site.documents['nullcall.html']),
					self.dbobject.null_call,
					self._a(self.site.documents['specificname.html']),
					self.dbobject.specific_name,
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
					self._a(self.site.document_map[overload].url, overload.specific_name)
				) for overload in overloads if overload != self.dbobject]
			))
		if self.dbobject.create_sql:
			self._section('sql', 'SQL Definition')
			self._add(self._pre(self._format_sql(self.dbobject.create_sql,
				terminator='!'), attrs={'class': 'sql'}))

