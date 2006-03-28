#!/bin/env python
# $Header$
# vim: set noet sw=4 ts=4:

import logging
from docbase import DocObjectBase
from doctable import DocTable
from docview import DocView
from docindex import DocIndex
from docdatatype import DocDatatype
from docfunction import DocFunction
from docutil import makeDateTime

__all__ = ['DocSchema']

class DocSchema(DocObjectBase):
	"""Class representing a schema in a DB2 database"""

	def __init__(self, database, cache, **row):
		"""Initializes an instance of the class from a cache row"""
		super(DocSchema, self).__init__(database, row['name'])
		logging.debug("Building schema %s" % (self.qualifiedName))
		self.__owner = row['owner']
		self.__definer = row['definer']
		self.__created = row['created']
		self.__description = row['description']
		self.__datatypes = {}
		self.__datatypeList = []
		self.__relations = {}
		self.__relationList = []
		self.__tables = {}
		self.__tableList = []
		self.__views = {}
		self.__viewList = []
		self.__aliases = {}
		self.__aliasList = []
		self.__indexes = {}
		self.__indexList = []
		self.__routines = {}
		self.__routineList = []
		self.__functions = {}
		self.__functionList = []
		self.__methods = {}
		self.__methodList = []
		self.__procedures = {}
		self.__procedureList = []
		self.__specificRoutines = {}
		self.__specificFunctions = {}
		self.__specificMethods = {}
		self.__specificProcedures = {}
		for datatype in [cache.datatypes[(schema, name)] for (schema, name) in cache.datatypes if schema == self.name]:
			self.__datatypes[datatype['name']] = DocDatatype(self, cache, **datatype)
		self.__datatypeList = [x for x in self.__datatypes.itervalues()]
		self.__datatypeList.sort(key=lambda datatype:datatype.name)
		for tableRec in [cache.tables[(schema, name)] for (schema, name) in cache.tables if schema == self.name]:
			table = DocTable(self, cache, **tableRec)
			self.__tables[tableRec['name']] = table
			self.__relations[tableRec['name']] = table
		self.__tableList = [x for x in self.__tables.itervalues()]
		self.__tableList.sort(key=lambda table:table.name)
		for viewRec in [cache.views[(schema, name)] for (schema, name) in cache.views if schema == self.name]:
			view = DocView(self, cache, **viewRec)
			self.__views[viewRec['name']] = view
			self.__relations[viewRec['name']] = view
		self.__viewList = [x for x in self.__views.itervalues()]
		self.__viewList.sort(key=lambda view:view.name)
		# XXX Add support for aliases
		self.__relationList = [x for x in self.__relations.itervalues()]
		self.__relationList.sort(key=lambda relation:relation.name)
		for indexRec in [cache.indexes[(schema, name)] for (schema, name) in cache.indexes if schema == self.name]:
			self.__indexes[indexRec['name']] = DocIndex(self, cache, **indexRec)
		self.__indexList = [x for x in self.__indexes.itervalues()]
		self.__indexList.sort(key=lambda index:index.name)
		for funcRec in [cache.functions[(schema, name)] for (schema, name) in cache.functions if schema == self.name]:
			func = DocFunction(self, cache, **funcRec)
			if not funcRec['name'] in self.__routines:
				self.__routines[funcRec['name']] = []
			self.__routines[funcRec['name']].append(func)
			if not funcRec['name'] in self.__functions:
				self.__functions[funcRec['name']] = []
			self.__functions[funcRec['name']].append(func)
			self.__specificRoutines[funcRec['specificName']] = func
			self.__specificFunctions[funcRec['specificName']] = func
		self.__functionList = [x for x in self.__functions.itervalues()]
		self.__functionList.sort(key=lambda function:function[0].name)
		# XXX Add support for methods
		# XXX Add support for stored procedures
		self.__routineList = [x for x in self.__routines.itervalues()]
		self.__routineList.sort(key=lambda routine:routine[0].name)
		# XXX Add support for sequences
		# XXX Add support for triggers

	def getTypeName(self):
		return "Schema"

	def getIdentifier(self):
		return "schema_%s" % (self.name)
	
	def getQualifiedName(self):
		return self.name
	
	def getDescription(self):
		if self.__description:
			return self.__description
		else:
			return super(DocSchema, self).getDescription()

	def getSystem(self):
		return self.name in [
			"NULLID",
			"SQLJ",
			"SYSCAT",
			"SYSFUN",
			"SYSIBM",
			"SYSPROC",
			"SYSSTAT",
			"SYSTOOLS"
		]

	def getDatabase(self):
		return self.parent

	def __getDatatypes(self):
		return self.__datatypes
	
	def __getDatatypeList(self):
		return self.__datatypeList

	def __getRelations(self):
		return self.__relations
	
	def __getRelationList(self):
		return self.__relationList
	
	def __getTables(self):
		return self.__tables
	
	def __getTableList(self):
		return self.__tableList
	
	def __getViews(self):
		return self.__views
	
	def __getViewList(self):
		return self.__viewList
	
	def __getAliases(self):
		return self.__aliases
	
	def __getAliasList(self):
		return self.__aliasList
	
	def __getIndexes(self):
		return self.__indexes
	
	def __getIndexList(self):
		return self.__indexList
	
	def __getRoutines(self):
		return self.__routines
	
	def __getRoutineList(self):
		return self.__routineList
	
	def __getFunctions(self):
		return self.__functions
	
	def __getFunctionList(self):
		return self.__functionList
	
	def __getMethods(self):
		return self.__methods
	
	def __getMethodList(self):
		return self.__methodList
	
	def __getProcedures(self):
		return self.__procedures
		
	def __getProcedureList(self):
		return self.__procedureList
	
	def __getSpecificRoutines(self):
		return self.__specificRoutines
	
	def __getSpecificFunctions(self):
		return self.__specificFunctions
	
	def __getSpecificMethods(self):
		return self.__specificMethods
	
	def __getSpecificProcedures(self):
		return self.__specificProcedures
	
	def __getSequences(self):
		return self.__sequences
	
	def __getTriggers(self):
		return self.__triggers

	def __getOwner(self):
		return self.__owner

	def __getDefiner(self):
		return self.__definer

	def __getCreated(self):
		return self.__created

	datatypes = property(__getDatatypes, doc="""The datatypes contained in the schema""")
	datatypeList = property(__getDatatypeList, doc="""The datatypes contained in the schema, sorted by name""")
	relations = property(__getRelations, doc="""The relations (tables, views, etc.) contained in the schema""")
	relationList = property(__getRelationList, doc="""The relations contained in the schema, sorted by name""")
	tables = property(__getTables, doc="""The tables contained in the schema""")
	tableList = property(__getTableList, doc="""The tables contained in the schema, sorted by name""")
	views = property(__getViews, doc="""The views contained in the schema""")
	viewList = property(__getViewList, doc="""The views contained in the schema, sorted by name""")
	aliases = property(__getAliases, doc="""The aliases contained in the schema""")
	aliasList = property(__getAliasList, doc="""The aliases contained in the schema, sorted by name""")
	indexes = property(__getIndexes, doc="""The indexes contained in the schema""")
	indexList = property(__getIndexList, doc="""The indexes contained in the schema, sorted by name""")
	routines = property(__getRoutines, doc="""The routines (methods, functions, etc.) contained in the schema""")
	routineList = property(__getRoutineList, doc="""The routines (methods, functions, etc.) contained in the schema, sorted by name""")
	functions = property(__getFunctions, doc="""The functions contained in the schema""")
	functionList = property(__getFunctionList, doc="""The functions contained in the schema, sorted by name""")
	methods = property(__getMethods, doc="""The methods contained in the schema""")
	methodList = property(__getMethodList, doc="""The methods contained in the schema, sorted by name""")
	procedures = property(__getProcedures, doc="""The procedures contained in the schema""")
	procedureList = property(__getProcedureList, doc="""The procedures contained in the schema, sorted by name""")
	specificRoutines = property(__getSpecificRoutines, doc="""The routines contained in the schema indexed by specific name""")
	specificFunctions = property(__getSpecificFunctions, doc="""The functions contained in the schema indexed by specific name""")
	specificMethods = property(__getSpecificMethods, doc="""The methods contained in the schema indexed by specific name""")
	specificProcedures = property(__getSpecificProcedures, doc="""The procedures contained in the schema indexed by specific name""")
	sequences = property(__getSequences, doc="""The sequences contained in the schema""")
	triggers = property(__getTriggers, doc="""The triggers contained in the schema""")
	owner = property(__getOwner, doc="""The authorization ID of the schema""")
	definer = property(__getDefiner, doc="""The user who created the schema""")
	created = property(__getCreated, doc="""Timestamp indicating when the schema was created""")

def main():
	pass

if __name__ == "__main__":
	main()
