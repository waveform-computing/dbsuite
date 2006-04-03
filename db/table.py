#!/bin/env python
# $Header$
# vim: set noet sw=4 ts=4:

import logging
from string import Template
from schemabase import Relation
from proxies import IndexesDict, IndexesList, RelationsDict, RelationsList
from field import Field
from uniquekey import UniqueKey, PrimaryKey
from foreignkey import ForeignKey
from check import Check
from util import formatIdentifier

class Table(Relation):
	"""Class representing a table in a DB2 database"""

	def __init__(self, schema, cache, **row):
		"""Initializes an instance of the class from a cache row"""
		super(Table, self).__init__(schema, row['name'])
		logging.debug("Building table %s" % (self.qualifiedName))
		self.__definer = row['definer']
		self.__checkPending = row['checkPending']
		self.__created = row['created']
		self.__statsUpdated = row['statsUpdated']
		self.__cardinality = row['cardinality']
		self.__rowPages = row['rowPages']
		self.__totalPages = row['totalPages']
		self.__overflow = row['overflow']
		self.__dataTbspace = row['dataTbspace']
		self.__indexTbspace = row['indexTbspace']
		self.__longTbspace = row['longTbspace']
		self.__append = row['append']
		self.__lockSize = row['lockSize']
		self.__volatile = row['volatile']
		self.__compression = row['compression']
		self.__accessMode = row['accessMode']
		self.__clustered = row['clustered']
		self.__activeBlocks = row['activeBlocks']
		self.__description = row['description']
		self.__fields = {}
		for field in [cache.fields[(schemaName, tableName, fieldName)]
			for (schemaName, tableName, fieldName) in cache.fields
			if schemaName == schema.name and tableName == self.name]:
			self.__fields[field['name']] = Field(self, cache, **field)
		self.__fieldList = sorted(self.__fields.itervalues(), key=lambda field:field.position)
		self.__dependents = RelationsDict(self.database, cache.dependents.get((schema.name, self.name)))
		self.__dependentList = RelationsList(self.database, cache.dependents.get((schema.name, self.name)))
		self.__indexes = IndexesDict(self.database, cache.tableIndexes.get((schema.name, self.name)))
		self.__indexList = IndexesList(self.database, cache.tableIndexes.get((schema.name, self.name)))
		self.__constraints = {}
		self.__uniqueKeys = {}
		self.__primaryKey = None
		for key in [cache.uniqueKeys[(schemaName, tableName, constName)]
			for (schemaName, tableName, constName) in cache.uniqueKeys
			if schemaName == schema.name and tableName == self.name]:
			if key['type'] == 'P':
				constraint = PrimaryKey(self, cache, **key)
				self.__primaryKey = constraint
			else:
				constraint = UniqueKey(self, cache, **key)
			self.__constraints[key['name']] = constraint
			self.__uniqueKeys[key['name']] = constraint
		self.__uniqueKeyList = sorted(self.__uniqueKeys.itervalues(), key=lambda key:key.name)
		self.__foreignKeys = {}
		for key in [cache.foreignKeys[(schemaName, tableName, constName)]
			for (schemaName, tableName, constName) in cache.foreignKeys
			if schemaName == schema.name and tableName == self.name]:
			constraint = ForeignKey(self, cache, **key)
			self.__constraints[key['name']] = constraint
			self.__foreignKeys[key['name']] = constraint
		self.__foreignKeyList = sorted(self.__foreignKeys.itervalues(), key=lambda key:key.name)
		self.__checks = {}
		for check in [cache.checks[(schemaName, tableName, constName)]
			for (schemaName, tableName, constName) in cache.checks
			if schemaName == schema.name and tableName == self.name]:
			constraint = Check(self, cache, **check)
			self.__constraints[check['name']] = constraint
			self.__checks[check['name']] = constraint
		self.__checkList = sorted(self.__checks.itervalues(), key=lambda check:check.name)
		self.__constraintList = sorted(self.__constraints.itervalues(), key=lambda constraint:constraint.name)

	def getTypeName(self):
		return "Table"

	def getDescription(self):
		if self.__description:
			return self.__description
		else:
			return super(Table, self).getDescription()

	def getFields(self):
		return self.__fields

	def getFieldList(self):
		return self.__fieldList

	def getDependents(self):
		return self.__dependents

	def getDependentList(self):
		return self.__dependentList

	def getCreateSql(self):
		sql = Template("""CREATE TABLE $schema.$table (
$elements
) $tbspaces;$indexes""")
		values = {
			'schema': formatIdentifier(self.schema.name),
			'table': formatIdentifier(self.name),	
			'elements': ',\n'.join(
				[field.prototype for field in self.fieldList] + 
				[constraint.prototype for constraint in self.constraints.itervalues()]
			),
			'tbspaces': 'IN ' + formatIdentifier(self.dataTablespace.name),
			'indexes': ''.join(['\n' + index.createSql for index in self.indexList])
		}
		if self.indexTablespace != self.dataTablespace:
			values['tbspaces'] += ' INDEX IN ' + formatIdentifier(self.indexTablespace.name)
		if self.longTablespace != self.dataTablespace:
			values['tbspaces'] += ' LONG IN ' + formatIdentifier(self.longTablespace.name)
		return sql.substitute(values)
	
	def getDropSql(self):
		sql = Template('DROP TABLE $schema.$table;')
		return sql.substitute({
			'schema': formatIdentifier(self.schema.name),
			'table': formatIdentifier(self.name)
		})
	
	def __getIndexes(self):
		return self.__indexes

	def __getIndexList(self):
		return self.__indexList

	def __getConstraints(self):
		return self.__constraints

	def __getConstraintList(self):
		return self.__constraintList

	def __getPrimaryKey(self):
		return self.__primaryKey

	def __getUniqueKeys(self):
		return self.__uniqueKeys

	def __getUniqueKeyList(self):
		return self.__uniqueKeyList

	def __getForeignKeys(self):
		return self.__foreignKeys

	def __getForeignKeyList(self):
		return self.__foreignKeyList

	def __getChecks(self):
		return self.__checks

	def __getCheckList(self):
		return self.__checkList

	def __getDefiner(self):
		return self.__definer

	def __getCheckPending(self):
		return self.__checkPending

	def __getCreated(self):
		return self.__created

	def __getStatsUpdated(self):
		return self.__statsUpdated

	def __getCardinality(self):
		return self.__cardinality

	def __getRowPages(self):
		return self.__rowPages

	def __getTotalPages(self):
		return self.__totalPages

	def __getOverflow(self):
		return self.__overflow

	def __getDataTablespace(self):
		return self.database.tablespaces[self.__dataTbspace]

	def __getIndexTablespace(self):
		if self.__indexTbspace:
			return self.database.tablespaces[self.__indexTbspace]
		else:
			return self.dataTablespace

	def __getLongTablespace(self):
		if self.__longTbspace:
			return self.database.tablespaces[self.__longTbspace]
		else:
			return self.dataTablespace

	def __getAppend(self):
		return self.__append

	def __getLockSize(self):
		return self.__lockSize

	def __getVolatile(self):
		return self.__volatile

	def __getCompression(self):
		return self.__compression

	def __getAccessMode(self):
		return self.__accessMode

	def __getClustered(self):
		return self.__clustered

	def __getActiveBlocks(self):
		return self.__activeBlocks

	indexes = property(__getIndexes, doc="""The indexes used by this table in a dictionary""")
	indexList = property(__getIndexList, doc="""The indexes used by this table in a list""")
	constraints = property(__getConstraints, doc="""The constraints (keys, checks, etc.) contained in the table""")
	constraintList = property(__getConstraintList, doc="""The constraints (keys, checks, etc.) contained in the table, in a sorted list""")
	primaryKey = property(__getPrimaryKey, doc="""The primary key constraint of the table""")
	uniqueKeys = property(__getUniqueKeys, doc="""The unique key constraints (including the primary key, if any) contained in the table""")
	uniqueKeyList = property(__getUniqueKeyList, doc="""The unique key constraints (including the primary key, if any) contained in the table, in a sorted list""")
	foreignKeys = property(__getForeignKeys, doc="""The foreign key constraints contained in the table""")
	foreignKeyList = property(__getForeignKeyList, doc="""The foreign key constraints contained in the table, in a sorted list""")
	checks = property(__getChecks, doc="""The check constraints contained in the table""")
	checkList = property(__getCheckList, doc="""The check constraints contained in the table, in a sorted list""")
	definer = property(__getDefiner, doc="""The user who created the table""")
	checkPending = property(__getCheckPending, doc="""True if the table is in check-pending state""")
	created = property(__getCreated, doc="""Timestamp indicating when the table was created""")
	statsUpdated = property(__getStatsUpdated, doc="""Timestamp indicating when the statistics were last updated""")
	cardinality = property(__getCardinality, doc="""The number of rows in the table (when the statistics were last updated)""")
	rowPages = property(__getRowPages, doc="""The number of pages used for row data (when the statistics were last updated)""")
	totalPages = property(__getTotalPages, doc="""The number of pages used by the table overall (when the statistics were last updated)""")
	overflow = property(__getOverflow, doc="""The number of overflow records""")
	dataTablespace = property(__getDataTablespace, doc="""The tablespace containing the table's data""")
	indexTablespace = property(__getIndexTablespace, doc="""The tablespace containing the table's indexes""")
	longTablespace = property(__getLongTablespace, doc="""The tablespace containing the table's BLOB and LONG data""")
	append = property(__getAppend, doc="""True if the table always appends records instead of inserting them""")
	lockSize = property(__getLockSize, doc="""The preferred lock size for the table""")
	volatile = property(__getVolatile, doc="""True if the cardinality of the table varies greatly""")
	compression = property(__getCompression, doc="""True if the table is using the compressed field format""")
	accessMode = property(__getAccessMode, doc="""The current access mode for the table""")
	clustered = property(__getClustered, doc="""True if the table is a multi-dimensional clustering table""")
	activeBlocks = property(__getActiveBlocks, doc="""The number of active blocks for multi-dimensional clustering tables""")

def main():
	pass

if __name__ == "__main__":
	main()
