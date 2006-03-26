#!/bin/env python
# $Header$
# vim: set noet sw=4 ts=4:

import logging
from docbase import DocObjectBase
from docschema import DocSchema
from doctablespace import DocTablespace
from docutil import makeDateTime, makeBoolean

__all__ = ['DocDatabase']

class DocDatabase(DocObjectBase):
	"""Class representing a DB2 database"""
	
	def __init__(self, cache, name):
		"""Initializes an instance of the class"""
		super(DocDatabase, self).__init__(None, name)
		logging.debug("Building database")
		self.__tablespaces = {}
		for row in cache.tablespaces.itervalues():
			self.__tablespaces[row['name']] = DocTablespace(self, cache, **row)
		self.__schemas = {}
		for row in cache.schemas.itervalues():
			self.__schemas[row['name']] = DocSchema(self, cache, **row)

	def find(self, qualifiedName):
		"""Find an object in the hierarchy by its qualified name.
		
		Because there are several namespaces in DB2, the results of such a
		search can only be unambiguous if an order of precedence for object
		types is established. The order of precedence used by this method is
		as follows:
		
		Schemas
		Tablespaces
			Tables/Views (one namespace)
				Fields
				Constraints
			Indexes
			Functions/Methods/Procedures (one namespace)
		
		Hence, if a schema shares a name with a tablespace, the schema will
		be returned in preference to the tablespace. Likewise, if an index
		shares a name with a table, the table will be returned in preference
		to the index.
		"""
		parts = qualifiedName.split(".")
		if len(parts) == 1:
			return self.schemas.get(parts[0],
				self.tablespaces.get(parts[0],
				None))
		elif len(parts) == 2:
			schema = self.schemas[parts[0]]
			return schema.relations.get(parts[1],
				schema.indexes.get(parts[1],
				schema.routines.get(parts[1],
				None)))
		elif len(parts) == 3:
			relation = self.schemas[parts[0]].relations[parts[1]]
			return relation.fields.get(parts[2],
				relation.constraints.get(parts[2],
				None))
		else:
			return None

	def getTypeName(self):
		return "Database"
	
	def getIdentifier(self):
		return "db"
	
	def getDatabase(self):
		return self

	def __getTablespaces(self):
		return self.__tablespaces
	
	def __getSchemas(self):
		return self.__schemas

	schemas = property(__getSchemas, doc="""The schemas contained in the database""")
	tablespaces = property(__getTablespaces, doc="""The tablespaces contained in the database""")

def main():
	pass

if __name__ == "__main__":
	main()
