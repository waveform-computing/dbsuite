#!/bin/env python
# $Header$
# vim: set noet sw=4 ts=4:

import logging
from docrelationbase import DocConstraint
from docutil import makeBoolean, makeDateTime, formatIdentifier

__all__ = ['DocForeignKey']

class ForeignKeyFieldsList(object):
	"""Presents a list of (field, parentField) tuples in a foreign key"""

	def __init__(self, table, refSchemaName, refTableName, fields):
		"""Initializes the list from a list of (field, parentField) name tuples"""
		assert type(fields) == type([])
		self.__table = table
		self.__database = table.database
		self.__refSchemaName = refSchemaName
		self.__refTableName = refTableName
		self.__items = fields

	def __len__(self):
		return len(self.__items)

	def __getItem__(self, key):
		assert type(key) == int
		(fieldName, parentName) = self.__items[key]
		parentTable = self.__database.schemas[self.__refSchemaName].tables[self.__refTableName]
		return (self.__table.fields[fieldName], parentTable.fields[parentName])

	def __iter__(self):
		parentTable = self.__database.schemas[self.__refSchemaName].tables[self.__refTableName]
		for (fieldName, parentName) in self.__items:
			yield (self.__table.fields[fieldName], parentTable.fields[parentName])

	def __contains__(self, key):
		for i in self:
			if i == key:
				return True
		return False

class DocForeignKey(DocConstraint):
	"""Class representing a foreign key in a table in a DB2 database"""

	def __init__(self, table, cache, **row):
		"""Initializes an instance of the class from a cache row"""
		super(DocForeignKey, self).__init__(table, row['name'])
		logging.info("Building foreign key %s" % (self.qualifiedName))
		self.__refTableSchema = row['refTableSchema']
		self.__refTableName = row['refTableName']
		self.__refKeyName = row['refKeyName']
		self.__created = row['created']
		self.__definer = row['definer']
		self.__enforced = row['enforced']
		self.__checkExisting = row['checkExisting']
		self.__queryOptimize = row['queryOptimize']
		self.__deleteRule = row['deleteRule']
		self.__updateRule = row['updateRule']
		self.__description = row['description']
		self.__fields = ForeignKeyFieldsList(table, row['refTableSchema'], row['refTableName'], cache.foreignKeyFields[(table.schema.name, table.name, self.name)])

	def getTypeName(self):
		return "Foreign Key"

	def getFields(self):
		return self.__fields

	def getDescription(self):
		if self.__description:
			return self.__description
		else:
			return super(DocForeignKey, self).getDescription()
	
	def getDefinitionStr(self):
		sql = 'CONSTRAINT %s FOREIGN KEY (%s) REFERENCES %s.%s(%s)' % (
			formatIdentifier(self.name),
			', '.join([formatIdentifier(myfield.name) for (myfield, reffield) in self.fields]),
			formatIdentifier(self.refTable.schema.name),
			formatIdentifier(self.refTable.name),
			', '.join([formatIdentifier(reffield.name) for (myfield, reffield) in self.fields])
		)
		if self.deleteRule != 'No Action':
			sql += ' ON DELETE %s' % ({
				'No Action': 'NO ACTION',
				'Restrict': 'RESTRICT',
				'Cascade': 'CASCADE',
				'Set NULL': 'SET NULL',
			}[self.deleteRule])
		if self.updateRule != 'No Action':
			sql += ' ON UPDATE %s' % ({
				'No Action': 'NO ACTION',
				'Restrict': 'RESTRICT',
			})
		return sql

	def __getRefTable(self):
		return self.database.schemas[self.__refTableSchema].tables[self.__refTableName]

	def __getRefKey(self):
		return self.refTable.uniqueKeys[self.__refKeyName]

	def __getCreated(self):
		return self.__created

	def __getDefiner(self):
		return self.__definer

	def __getEnforced(self):
		return self.__enforced

	def __getCheckExisting(self):
		return self.__checkExisting

	def __getQueryOptimize(self):
		return self.__queryOptimize

	def __getDeleteRule(self):
		return self.__deleteRule

	def __getUpdateRule(self):
		return self.__updateRule

	refTable = property(__getRefTable, doc="""The table that the foreign key references""")
	refKey = property(__getRefKey, doc="""The key in the parent table that the foreign key references""")
	created = property(__getCreated, doc="""Timestamp indicating when the foreign key was created""")
	definer = property(__getDefiner, doc="""The user who created the key""")
	enforced = property(__getEnforced, doc="""True if the foreign key is enforced during updates""")
	checkExisting = property(__getCheckExisting, doc="""Indicates when existing data is to be checked (if at all)""")
	queryOptimize = property(__getQueryOptimize, doc="""True if the foreign key is used to optimize queries""")
	deleteRule = property(__getDeleteRule, doc="""Indicates the action to take when a parent record is deleted""")
	updateRule = property(__getUpdateRule, doc="""Indicates the action to take when a parent record is updated""")

def main():
	pass

if __name__ == "__main__":
	main()
