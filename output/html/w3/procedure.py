#!/bin/env python
# $Header$
# vim: set noet sw=4 ts=4:

from db.procedure import Procedure
from output.html.w3.document import W3MainDocument

class W3ProcedureDocument(W3MainDocument):
	def __init__(self, site, procedure):
		assert isinstance(procedure, Procedure)
		super(W3ProcedureDocument, self).__init__(site, procedure)
	
	def create_sections(self):
		overloads = self.dbobject.schema.procedures[self.dbobject.name]
		self.section('description', 'Description')
		self.add(self.p(self.format_prototype(self.dbobject.prototype)))
		self.add(self.p(self.format_description(self.dbobject.description)))
		# XXX What about the IN/OUT/INOUT state of procedure parameters?
		self.add(self.dl([
			(param.name, self.format_description(param.description))
			for param in self.dbobject.paramList
		]))
		self.section('attributes', 'Attributes')
		self.add(self.p("""The following table notes the various attributes and
			properties of the procedure."""))
		self.add(self.table(
			head=[(
				"Attribute",
				"Value",
				"Attribute",
				"Value"
			)],
			data=[
				(
					self.a("created.html", "Created", popup=True),
					self.dbobject.created,
					self.a("funcorigin.html", "Origin", popup=True),
					self.dbobject.origin,
				),
				(
					self.a("createdby.html", "Created By", popup=True),
					self.dbobject.definer,
					self.a("funclanguage.html", "Language", popup=True),
					self.dbobject.language,
				),
				(
					self.a("sqlaccess.html", "SQL Access", popup=True),
					self.dbobject.sqlAccess,
					self.a("nullcall.html", "Call on NULL", popup=True),
					self.dbobject.nullCall,
				),
				(
					self.a("externalaction.html", "External Action", popup=True),
					self.dbobject.externalAction,
					self.a("deterministic.html", "Deterministic", popup=True),
					self.dbobject.deterministic,
				),
				(
					self.a("fenced.html", "Fenced", popup=True),
					self.dbobject.fenced,
					self.a("threadsafe.html", "Thread Safe", popup=True),
					self.dbobject.threadSafe,
				),
				(
					self.a("specificname.html", "Specific Name", popup=True),
					{'colspan': '3', '': self.dbobject.specificName},
				),
			]
		))
		if len(overloads) > 1:
			self.section('overloads', 'Overloaded Versions')
			self.add(self.p("""Listed below are the prototypes of overloaded
				versions of this procedure (i.e. procedures with the same
				qualified name, but different parameter lists). Click on a
				specific name to view the entry for the overloaded
				procedure."""))
			self.add(self.table(
				head=[(
					'Prototype',
					'Specific Name',
				)],
				data=[(
					self.format_prototype(overload.prototype),
					self.a(self.site.document_map[overload].url, overload.specificName)
				) for overload in overloads if overload != self.dbobject]
			))
		if self.dbobject.language == 'SQL':
			self.section('sql', 'SQL Definition')
			self.add(self.p("""The SQL which can be used to create the
				procedure is given below. Note that, in the process of storing
				the definition of a procedure, DB2 removes much of the
				formatting, hence the formatting in the statement below (which
				this system attempts to reconstruct) is not necessarily the
				formatting of the original statement. The statement terminator
				used in the SQL below is bang (!)"""))
			self.add(self.pre(self.format_sql(self.dbobject.createSql, terminator='!'), attrs={'class': 'sql'}))

