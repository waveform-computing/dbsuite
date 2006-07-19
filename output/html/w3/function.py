#!/bin/env python
# $Header$
# vim: set noet sw=4 ts=4:

from db.function import Function
from output.html.w3.document import W3Document

class W3FunctionDocument(W3Document):
	def __init__(self, site, function):
		assert isinstance(function, Function)
		super(W3FunctionDocument, self).__init__(site, function)
	
	def create_sections(self):
		overloads = self.dbobject.schema.functions[self.dbobject.name]
		params = list(self.dbobject.paramList) # Take a copy of the parameter list
		if self.dbobject.type in ['Row', 'Table']:
			# Extend the list with return parameters if the function is a ROW
			# or TABLE function (and hence, returns multiple named parms)
			params.extend(self.dbobject.returnList)
		self.section('description', 'Description')
		self.add(self.p(self.format_prototype(self.dbobject.prototype)))
		self.add(self.p(self.format_description(self.dbobject.description)))
		self.add(self.dl([
			(param.name, self.format_description(param.description))
			for param in params
		]))
		self.section('attributes', 'Attributes')
		self.add(self.p("""The following table notes the various attributes and
			properties of the function."""))
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
					self.a("functype.html", "Type", popup=True),
					self.dbobject.type,
					self.a("sqlaccess.html", "SQL Access", popup=True),
					self.dbobject.sqlAccess,
				),
				(
					self.a("castfunc.html", "Cast Function", popup=True),
					self.dbobject.castFunction,
					self.a("assignfunc.html", "Assign Function", popup=True),
					self.dbobject.assignFunction,
				),
				(
					self.a("externalaction.html", "External Action", popup=True),
					self.dbobject.externalAction,
					self.a("deterministic.html", "Deterministic", popup=True),
					self.dbobject.deterministic,
				),
				(
					self.a("nullcall.html", "Call on NULL", popup=True),
					self.dbobject.nullCall,
					self.a("fenced.html", "Fenced", popup=True),
					self.dbobject.fenced,
				),
				(
					self.a("parallelcall.html", "Parallel", popup=True),
					self.dbobject.parallel,
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
				versions of this function (i.e. functions with the same
				qualified name, but different parameter lists). Click on a
				specific name to view the entry for the overloaded
				function."""))
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
			self.add(self.p("""The SQL which can be used to create the function
				is given below. Note that, in the process of storing the
				definition of a function, DB2 removes much of the formatting,
				hence the formatting in the statement below (which this system
				attempts to reconstruct) is not necessarily the formatting of
				the original statement. The statement terminator used in the
				SQL below is bang (!)"""))
			self.add(self.pre(self.format_sql(self.dbobject.createSql, terminator='!'), attrs={'class': 'sql'}))

