#!/bin/env python
# $Header$
# vim: set noet sw=4 ts=4:

from docbase import DocObjectBase

__all__ = ['DocRelationObject', 'DocConstraint']

class DocRelationObject(DocObjectBase):
	"""Base class for database objects that belong directly to a relation"""
	
	def __getRelation(self):
		return self.parent
	
	def __getSchema(self):
		return self.parent.parent
	
	def __getDatabase(self):
		return self.parent.parent.parent
	
	relation = property(__getRelation, doc="""The relation that owns the object""")
	schema = property(__getSchema, doc="""The schema that contains the object""")
	database = property(__getDatabase, doc="""The database that contains the object""")

class DocConstraint(DocRelationObject):
	"""Base class for constraints that belong in a relation (e.g. primary keys, checks, etc.)"""
	
	def getTypeName(self):
		return "Constraint"

	def getIdentifier(self):
		return "constraint_%s_%s" % (self.relation.name, self.schema.name, self.name)

	def getFields(self):
		raise NotImplementedError
	
	# Use the lambda trick to allow property getter methods to be overridden
	fields = property(lambda self: self.getFields(), doc="""The fields constrained by this constraint""")

def main():
	pass

if __name__ == "__main__":
	main()
