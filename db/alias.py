#!/bin/env python
# $Header$
# vim: set noet sw=4 ts=4:

import logging
from string import Template
from schemabase import Relation
from util import formatIdentifier

class Alias(Relation):
	"""Class representing a alias in a DB2 database"""
	
	def __init__(self, schema, cache, **row):
		"""Initializes an instance of the class from a cache row"""
		super(Alias, self).__init__(schema, row['name'])
		logging.debug("Building alias %s" % (self.qualifiedName))
		self.__definer = row['definer']
		self.__created = row['created']
		self.__relationSchema = row['relationSchema']
		self.__relationName = row['relationName']
		self.__description = row['description']

	def getTypeName(self):
		return "Alias"

	def getDescription(self):
		if self.__description:
			return self.__description
		else:
			return super(Alias, self).getDescription()

	def getFields(self):
		return self.relation.fields

	def getFieldList(self):
		return self.relation.fieldList
	
	def getCreateSql(self):
		sql = Template('CREATE ALIAS $schema.$alias FOR $baseschema.$baserelation;')
		return sql.substitute({
			'schema': formatIdentifier(self.schema.name),
			'alias': formatIdentifier(self.name),
			'baseschema': formatIdentifier(self.relation.schema.name),
			'baserelation': formatIdentifier(self.relation.name)
		})
	
	def getDropSql(self):
		sql = Template('DROP ALIAS $schema.$alias;')
		return sql.substitute({
			'schema': formatIdentifier(self.schema.name),
			'alias': formatIdentifier(self.name)
		})
	
	def __getRelation(self):
		return self.database.schemas[self.__relationSchema].relations[self.__relationName]
	
	def __getDefiner(self):
		return self.__definer
	
	def __getCreated(self):
		return self.__created
	
	definer = property(__getDefiner, doc="""The user who created the view""")
	created = property(__getCreated, doc="""Timestamp indicating when the view was created""")
	relation = property(__getRelation, doc="""The relation that the alias is defined for""")
	
def main():
	pass

if __name__ == "__main__":
	main()
