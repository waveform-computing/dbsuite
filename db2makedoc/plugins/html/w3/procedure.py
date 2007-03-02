# $Header$
# vim: set noet sw=4 ts=4:

from db2makedoc.db.procedure import Procedure
from db2makedoc.plugins.html.w3.document import W3MainDocument

class W3ProcedureDocument(W3MainDocument):
	def __init__(self, site, procedure):
		assert isinstance(procedure, Procedure)
		super(W3ProcedureDocument, self).__init__(site, procedure)
	
	def create_sections(self):
		overloads = self.dbobject.schema.procedures[self.dbobject.name]
		self.section('description', 'Description')
		self.add(self.p(self.format_prototype(self.dbobject.prototype)))
		self.add(self.p(self.format_comment(self.dbobject.description)))
		# XXX What about the IN/OUT/INOUT state of procedure parameters?
		self.add(self.dl([
			(param.name, self.format_comment(param.description))
			for param in self.dbobject.param_list
		]))
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
					self.a(self.site.documents['funcorigin.html']),
					self.dbobject.origin,
				),
				(
					self.a(self.site.documents['createdby.html']),
					self.dbobject.definer,
					self.a(self.site.documents['funclanguage.html']),
					self.dbobject.language,
				),
				(
					self.a(self.site.documents['sqlaccess.html']),
					self.dbobject.sql_access,
					self.a(self.site.documents['nullcall.html']),
					self.dbobject.null_call,
				),
				(
					self.a(self.site.documents['externalaction.html']),
					self.dbobject.external_action,
					self.a(self.site.documents['deterministic.html']),
					self.dbobject.deterministic,
				),
				(
					self.a(self.site.documents['fenced.html']),
					self.dbobject.fenced,
					self.a(self.site.documents['threadsafe.html']),
					self.dbobject.thread_safe,
				),
				(
					self.a(self.site.documents['specificname.html']),
					(self.dbobject.specific_name, {'colspan': 3}),
				),
			]
		))
		if len(overloads) > 1:
			self.section('overloads', 'Overloaded Versions')
			self.add(self.table(
				head=[(
					'Prototype',
					'Specific Name',
				)],
				data=[(
					self.format_prototype(overload.prototype),
					self.a(self.site.document_map[overload].url, overload.specific_name)
				) for overload in overloads if overload != self.dbobject]
			))
		if self.dbobject.language == 'SQL':
			self.section('sql', 'SQL Definition')
			self.add(self.pre(self.format_sql(self.dbobject.create_sql,
				terminator='!'), attrs={'class': 'sql'}))

