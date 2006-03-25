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
		self.__relations = {}
		self.__tables = {}
		self.__views = {}
		self.__aliases = {}
		self.__indexes = {}
		self.__routines = {}
		self.__functions = {}
		self.__methods = {}
		self.__procedures = {}
		self.__specificRoutines = {}
		self.__specificFunctions = {}
		self.__specificMethods = {}
		self.__specificProcedures = {}
		for datatype in [cache.datatypes[(schema, name)] for (schema, name) in cache.datatypes if schema == self.name]:
			self.__datatypes[datatype['name']] = DocDatatype(self, cache, **datatype)
		for tableRec in [cache.tables[(schema, name)] for (schema, name) in cache.tables if schema == self.name]:
			table = DocTable(self, cache, **tableRec)
			self.__tables[tableRec['name']] = table
			self.__relations[tableRec['name']] = table
		for viewRec in [cache.views[(schema, name)] for (schema, name) in cache.views if schema == self.name]:
			view = DocView(self, cache, **viewRec)
			self.__views[viewRec['name']] = view
			self.__relations[viewRec['name']] = view
		for indexRec in [cache.indexes[(schema, name)] for (schema, name) in cache.indexes if schema == self.name]:
			self.__indexes[indexRec['name']] = DocIndex(self, cache, **indexRec)
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
		# XXX Add support for aliases
		# XXX Add support for methods
		# XXX Add support for stored procedures
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

	def __getDatabase(self):
		return self.parent

	def __getDatatypes(self):
		return self.__datatypes

	def __getRelations(self):
		return self.__relations
	
	def __getTables(self):
		return self.__tables
	
	def __getViews(self):
		return self.__views
	
	def __getAliases(self):
		return self.__aliases
	
	def __getIndexes(self):
		return self.__indexes
	
	def __getRoutines(self):
		return self.__routines
	
	def __getFunctions(self):
		return self.__functions
	
	def __getMethods(self):
		return self.__methods
	
	def __getProcedures(self):
		return self.__procedures
	
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

	database = property(__getDatabase, doc="""The database that owns the schema""")
	datatypes = property(__getDatatypes, doc="""The datatypes contained in the schema""")
	relations = property(__getRelations, doc="""The relations (tables, views, etc.) contained in the schema""")
	tables = property(__getTables, doc="""The tables contained in the schema""")
	views = property(__getViews, doc="""The views contained in the schema""")
	aliases = property(__getAliases, doc="""The aliases contained in the schema""")
	indexes = property(__getIndexes, doc="""The indexes contained in the schema""")
	routines = property(__getRoutines, doc="""The routines (methods, functions, etc.) contained in the schema""")
	functions = property(__getFunctions, doc="""The functions contained in the schema""")
	methods = property(__getMethods, doc="""The methods contained in the schema""")
	procedures = property(__getProcedures, doc="""The procedures contained in the schema""")
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
