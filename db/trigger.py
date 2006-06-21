#!/bin/env python
# $Header$
# vim: set noet sw=4 ts=4:

import logging
from string import Template
from schemabase import SchemaObject
from proxies import RelationsDict, RelationsList
from util import formatIdentifier

class Trigger(SchemaObject):
	"""Class representing an index in a DB2 database"""

	def __init__(self, schema, cache, **row):
		"""Initializes an instance of the class from a cache row"""
		super(Trigger, self).__init__(schema, row['name'])
		logging.debug("Building trigger %s" % (self.qualifiedName))
		self.__definer = row['definer']
		self.__relationSchema = row['tableSchema']
		self.__relationName = row['tableName']
		self.__created = row['created']
		self.__triggerTime = row['triggerTime']
		self.__triggerEvent = row['triggerEvent']
		self.__valid = row['valid']
		self.__qualifier = row['qualifier']
		self.__funcPath = row['funcPath']
		self.__description = row['description']
		self.__sql = row['sql']

	def getTypeName(self):
		return "Trigger"

	def getIdentifier(self):
		return "trigger_%s_%s" % (self.schema.name, self.name)

	def getDescription(self):
		if self.__description:
			return self.__description
		else:
			return super(Trigger, self).getDescription()

	def getParentList(self):
		return self.schema.triggerList

	def getCreateSql(self):
		return self.sql

	def getDropSql(self):
		sql = Template('DROP TRIGGER $schema.$trigger;')
		return sql.substitute({
			'schema': formatIdentifier(self.schema.name),
			'trigger': formatIdentifier(self.name)
		})

	def __getRelation(self):
		return self.database.schemas[self.__relationSchema].relations[self.__relationName]

	def __getDefiner(self):
		return self.__definer

	def __getCreated(self):
		return self.__created

	def __getTriggerTime(self):
		return self.__triggerTime

	def __getTriggerEvent(self):
		return self.__triggerEvent

	def __getValid(self):
		return self.__valid
	
	def __getQualifier(self):
		return self.__qualifier
	
	def __getFuncPath(self):
		return self.__funcPath
	
	relation = property(__getRelation, doc="""The relation (table or view) that the trigger is defined for""")
	definer = property(__getDefiner, doc="""The user who created the trigger""")
	created = property(__getCreated, doc="""Timestamp indicating when the trigger was created""")
	triggerTime = property(__getTriggerTime, doc="""Specifies whether a trigger fires before, after, or instead of the action to be carried by the statement that fired the trigger""")
	triggerEvent = property(__getTriggerEvent, doc="""Specifies what sort of statements fire the trigger (INSERT, UPDATE, or DELETE)""")
	valid = property(__getValid, doc="""Specifies whether the trigger is active or inoperative""")
	qualifier = property(__getQualifier, doc="""Specifies the current schema at the time the trigger was created""")
	funcPath = property(__getFuncPath, doc="""Specifies the function resolution path at the time the trigger was created""")

def main():
	pass

if __name__ == "__main__":
	main()
