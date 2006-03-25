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

	def getTypeName(self):
		return "Database"
	
	def getIdentifier(self):
		return "db"
	
	def __getDatabase(self):
		return self

	def __getTablespaces(self):
		return self.__tablespaces
	
	def __getSchemas(self):
		return self.__schemas

	database = property(__getDatabase, doc="""The database object itself""")
	schemas = property(__getSchemas, doc="""The schemas contained in the database""")
	tablespaces = property(__getTablespaces, doc="""The tablespaces contained in the database""")

def main():
	pass

if __name__ == "__main__":
	main()
