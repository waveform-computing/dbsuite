#!/bin/env python
# $Header$
# vim: set noet sw=4 ts=4:

from string import Template
from base import DocBase
from util import formatIdentifier

class RelationObject(DocBase):
	"""Base class for database objects that belong directly to a relation"""
	
	def getDatabase(self):
		return self.parent.parent.parent
	
	def __getRelation(self):
		return self.parent
	
	def __getSchema(self):
		return self.parent.parent
	
	relation = property(__getRelation, doc="""The relation that owns the object""")
	schema = property(__getSchema, doc="""The schema that contains the object""")

class Constraint(RelationObject):
	"""Base class for constraints that belong in a relation (e.g. primary keys, checks, etc.)"""
	
	def __getTable(self):
		return self.parent
	
	def getTypeName(self):
		return "Constraint"

	def getIdentifier(self):
		return "constraint_%s_%s_%s" % (self.relation.name, self.schema.name, self.name)

	def getFields(self):
		raise NotImplementedError
	
	def getPrototype(self):
		raise NotImplementedError
	
	def getCreateSql(self):
		sql = Template('ALTER TABLE $schema.$table ADD $constdef;')
		return sql.substitute({
			'schema': formatIdentifier(self.table.schema.name),
			'table': formatIdentifier(self.table.name),
			'constdef': self.prototype
		})
	
	def getDropSql(self):
		sql = Template('ALTER TABLE $schema.$table DROP CONSTRAINT $const;')
		return sql.substitute({
			'schema': formatIdentifier(self.table.schema.name),
			'table': formatIdentifier(self.table.name),
			'const': formatIdentifier(self.name)
		})
	
	def getParentList(self):
		return self.table.constraintList

	# Use the lambda trick to allow property getter methods to be overridden
	fields = property(lambda self: self.getFields(), doc="""The fields constrained by this constraint""")
	prototype = property(lambda self: self.getPrototype(), doc="""The attributes of the constraint formatted for use in an ALTER TABLE or CREATE TABLE statement""")
	table = property(__getTable, doc="""The table that owns the constraint""")

def main():
	pass

if __name__ == "__main__":
	main()
