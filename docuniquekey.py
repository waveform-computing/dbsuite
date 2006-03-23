#!/bin/env python
# $Header$
# vim: set noet sw=4 ts=4:

import logging
from docrelationbase import DocConstraint
from docutil import formatIdentifier

__all__ = ['DocUniqueKey', 'DocPrimaryKey']

class UniqueKeyFieldsList(object):
	"""Presents a list of fields in a unique key"""

	def __init__(self, table, fields):
		"""Initializes the list from a list of field names"""
		assert type(fields) == type([])
		self.__table = table
		self.__items = fields

	def __len__(self):
		return len(self.__items)

	def __getItem__(self, key):
		assert type(key) == int
		return self.__table.fields[self.__items[key]]

	def __iter__(self):
		for fieldName in self.__items:
			yield self.__table.fields[fieldName]

	def __contains__(self, key):
		for i in self:
			if i == key:
				return True
		return False

class DocUniqueKey(DocConstraint):
	"""Class representing a unique key in a table in a DB2 database"""

	def __init__(self, table, cache, **row):
		"""Initializes an instance of the class from a cache row"""
		super(DocUniqueKey, self).__init__(table, row['name'])
		logging.info("Building unique key %s" % (self.qualifiedName))
		self.__definer = row['definer']
		self.__checkExisting = row['checkExisting']
		self.__description = row['description']
		self.__fields = UniqueKeyFieldsList(table, cache.uniqueKeyFields[(table.schema.name, table.name, self.name)])

	def getTypeName(self):
		return "Unique Key"

	def getFields(self):
		return self.__fields

	def getDescription(self):
		if self.__description:
			return self.__description
		else:
			return super(DocUniqueKey, self).getDescription()
	
	def getDefinitionStr(self):
		return 'CONSTRAINT %s UNIQUE (%s)' % (
			formatIdentifier(self.name),
			', '.join([formatIdentifier(field.name) for field in self.fields])
		)

	def __getDefiner(self):
		return self.__definer

	def __getCheckExisting(self):
		return self.__checkExisting

	definer = property(__getDefiner, doc="""The user who created the key""")
	checkExisting = property(__getCheckExisting, doc="""Indicates when existing data is to be checked (if at all)""")

class DocPrimaryKey(DocUniqueKey):
	"""Class representing a primary key in a table in a DB2 database"""

	def getTypeName(self):
		return "Primary Key"

	def getDefinitionStr(self):
		return "CONSTRAINT %s PRIMARY KEY (%s)" % (
			formatIdentifier(self.name),
			', '.join([formatIdentifier(field.name) for field in self.fields])
		)

def main():
	pass

if __name__ == "__main__":
	main()
