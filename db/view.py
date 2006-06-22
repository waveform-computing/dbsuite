#!/bin/env python
# $Header$
# vim: set noet sw=4 ts=4:

import logging
from string import Template
from schemabase import Relation
from proxies import RelationsDict, RelationsList, TriggersDict, TriggersList
from field import Field
from util import formatIdentifier

class View(Relation):
	"""Class representing a view in a DB2 database"""
	
	def __init__(self, schema, cache, **row):
		"""Initializes an instance of the class from a cache row"""
		super(View, self).__init__(schema, row['name'])
		logging.debug("Building view %s" % (self.qualifiedName))
		self.__definer = row['definer']
		self.__created = row['created']
		self.__check = row['check']
		self.__readOnly = row['readOnly']
		self.__valid = row['valid']
		self.__qualifier = row['qualifier']
		self.__funcPath = row['funcPath']
		self.__sql = row['sql']
		self.__description = row['description']
		self.__fields = {}
		for field in [cache.fields[(schemaName, viewName, fieldName)] for (schemaName, viewName, fieldName) in cache.fields if schemaName == schema.name and viewName == self.name]:
			self.__fields[field['name']] = Field(self, cache, **field)
		self.__fieldList = sorted(self.__fields.itervalues(), key=lambda field:field.position)
		self.__dependents = RelationsDict(self.database, cache.relation_dependents.get((schema.name, self.name)))
		self.__dependentList = RelationsList(self.database, cache.relation_dependents.get((schema.name, self.name)))
		self.__dependencies = RelationsDict(self.database, cache.relation_dependencies.get((schema.name, self.name)))
		self.__dependencyList = RelationsList(self.database, cache.relation_dependencies.get((schema.name, self.name)))
		self.__triggers = TriggersDict(self.database, cache.relation_triggers.get((schema.name, self.name)))
		self.__triggerList = TriggersList(self.database, cache.relation_triggers.get((schema.name, self.name)))

	def getTypeName(self):
		return "View"

	def getDescription(self):
		if self.__description:
			return self.__description
		else:
			return super(View, self).getDescription()

	def getDependents(self):
		return self.__dependents
	
	def getDependentList(self):
		return self.__dependentList
	
	def getFields(self):
		return self.__fields
	
	def getFieldList(self):
		return self.__fieldList

	def getCreateSql(self):
		return self.__sql + ';'
	
	def getDropSql(self):
		sql = Template('DROP VIEW $schema.$view;')
		return sql.substitute({
			'schema': formatIdentifier(self.schema.name),
			'view': formatIdentifier(self.name)
		})
	
	def __getTriggers(self):
		return self.__triggers

	def __getTriggerList(self):
		return self.__triggerList

	def __getDependencies(self):
		return self.__dependencies
	
	def __getDependencyList(self):
		return self.__dependencyList

	def __getDefiner(self):
		return self.__definer
	
	def __getCreated(self):
		return self.__created
	
	def __getCheck(self):
		return self.__check
	
	def __getReadOnly(self):
		return self.__readOnly
	
	def __getValid(self):
		return self.__valid
	
	def __getQualifier(self):
		return self.__qualifier
	
	def __getFuncPath(self):
		return self.__funcPath
	
	def __getSql(self):
		return self.__sql

	triggers = property(__getTriggers, doc="""The triggers defined against this view in a dictionary""")
	triggerList = property(__getTriggerList, doc="""The triggers defined against this view in a list""")
	dependencies = property(__getDependencies, doc="""A dictionary of the relations (e.g. views) that this view depends upon (keyed by (schemaName, relationName) tuples)""")
	dependencyList = property(__getDependencyList, doc="""A list of the relations (e.g. views) that this view depends upon""")
	definer = property(__getDefiner, doc="""The user who created the view""")
	created = property(__getCreated, doc="""Timestamp indicating when the view was created""")
	check = property(__getCheck, doc="""How rows written to the view are checked""")
	readOnly = property(__getReadOnly, doc="""Specifies whether the view is updateable""")
	valid = property(__getValid, doc="""Specifies whether the view is accessible or inoperative""")
	qualifier = property(__getQualifier, doc="""Specifies the current schema at the time the view was created""")
	funcPath = property(__getFuncPath, doc="""Specifies the function resolution path at the time the view was created""")
	sql = property(__getSql, doc="""The complete SQL statement that created the view""")
	
def main():
	pass

if __name__ == "__main__":
	main()
