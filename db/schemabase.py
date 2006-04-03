#!/bin/env python
# $Header$
# vim: set noet sw=4 ts=4:

from base import DocBase

class SchemaObject(DocBase):
	"""Base class for database objects that belong directly to a schema"""
	
	def getDatabase(self):
		return self.parent.parent
	
	def __getSchema(self):
		return self.parent
	
	schema = property(__getSchema, doc="""The schema that owns the object""")

class Relation(SchemaObject):
	"""Base class for relations that belong in a schema (e.g. tables, views, etc.)"""
	
	def getIdentifier(self):
		return "relation_%s_%s" % (self.schema.name, self.name)

	def getDependents(self):
		raise NotImplementedError

	def getDependentList(self):
		raise NotImplementedError

	def getFields(self):
		raise NotImplementedError

	def getFieldList(self):
		raise NotImplementedError

	def getParentList(self):
		return self.schema.relationList

	# Use the lambda trick to allow property getter methods to be overridden
	dependents = property(lambda self: self.getDependents(), doc="""A dictionary of the relations that depend on this relation (keyed by (schemaName, relationName) tuples)""")
	dependentList = property(lambda self: self.getDependentList(), doc="""A list of the relations that depend on this relation""")
	fields = property(lambda self: self.getFields(), doc="""The fields contained in the relation""")
	fieldList = property(lambda self: self.getFieldList(), doc="""The fields contained in the relation in an ordered list""")

class Routine(SchemaObject):
	"""Base class for routines that belong in a schema (functions, procedures, etc.)"""

	def __init__(self, parent, name, specificName):
		super(Routine, self).__init__(parent, name)
		self.__specificName = specificName
		
	def __getSpecificName(self):
		return self.__specificName

	def getIdentifier(self):
		return "routine_%s_%s" % (self.schema.name, self.specificName)

	def getParams(self):
		raise NotImplementedError

	def getParamList(self):
		raise NotImplementedError

	def getReturns(self):
		raise NotImplementedError

	def getReturnList(self):
		raise NotImplementedError

	def getPrototype(self):
		raise NotImplementedError
	
	# Use the lambda trick to allow property getter methods to be overridden
	params = property(lambda self: self.getParams(), doc="""The parameters of the routine""")
	paramList = property(lambda self: self.getParamList(), doc="""The parameters of the routine in an ordered list""")
	returns = property(lambda self: self.getReturns(), doc="""The return type (or types) of the routine""")
	returnList = property(lambda self: self.getReturnList(), doc="""The return type (or types) of the routine in an ordered list""")
	prototype = property(lambda self: self.getPrototype(), doc="""Returns the calling prototype of the routine, documenting its parameters and their types, and the return type(s) if any""")
	specificName = property(__getSpecificName, doc="""The specific name of the routine""")

def main():
	pass

if __name__ == "__main__":
	main()
