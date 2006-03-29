#!/bin/env python
# $Header$
# vim: set noet sw=4 ts=4:

import logging
from string import Template
from schemabase import SchemaObject
from util import formatIdentifier

class IndexFieldsDict(object):
	"""Presents a dictionary of (field, indexOrder) tuples keyed by fieldName"""

	def __init__(self, database, schemaName, tableName, fields):
		"""Initializes the dict from a list of (fieldName, indexOrder) tuples"""
		assert type(fields) == type([])
		self.__database = database
		self.__schemaName = schemaName
		self.__tableName = tableName
		self.__keys = [fieldName for (fieldName, indexOrder) in fields]
		self.__items = {}
		for (fieldName, indexOrder) in fields:
			self.__items[fieldName] = indexOrder

	def keys(self):
		return self.__keys

	def has_key(self, key):
		return key in self.__keys

	def __len__(self):
		return len(self.__keys)

	def __getItem__(self, key):
		return (self.__database.schemas[self.__schemaName].tables[self.__tableName].fields[key], self.__items[key])

	def __iter__(self):
		for k in self.__keys:
			yield k

	def __contains__(self, key):
		return key in self.__keys

class IndexFieldsList(object):
	"""Presents a list of (field, indexOrder) tuples"""

	def __init__(self, database, schemaName, tableName, fields):
		"""Initializes the list from a list of (fieldName, indexOrder) tuples"""
		assert type(fields) == type([])
		self.__database = database
		self.__schemaName = schemaName
		self.__tableName = tableName
		self.__items = fields

	def __len__(self):
		return len(self.__items)

	def __getItem__(self, key):
		assert type(key) == int
		(fieldName, indexOrder) = self.__items[key]
		return (self.__database.schemas[self.__schemaName].tables[self.__tableName].fields[fieldName], indexOrder)

	def __iter__(self):
		for (fieldName, indexOrder) in self.__items:
			yield (self.__database.schemas[self.__schemaName].tables[self.__tableName].fields[fieldName], indexOrder)

	def __contains__(self, key):
		for i in self:
			if i == key:
				return True
		return False

class Index(SchemaObject):
	"""Class representing an index in a DB2 database"""

	def __init__(self, schema, cache, **row):
		"""Initializes an instance of the class from a cache row"""
		super(Index, self).__init__(schema, row['name'])
		logging.debug("Building index %s" % (self.qualifiedName))
		self.__definer = row['definer']
		self.__tableSchema = row['tableSchema']
		self.__tableName = row['tableName']
		self.__unique = row['unique']
		self.__type = row['type']
		self.__leafPages = row['leafPages']
		self.__levels = row['levels']
		self.__cardinality1 = row['cardinality1']
		self.__cardinality2 = row['cardinality2']
		self.__cardinality3 = row['cardinality3']
		self.__cardinality4 = row['cardinality4']
		self.__cardinality = row['cardinality']
		self.__clusterRatio = row['clusterRatio']
		self.__clusterFactor = row['clusterFactor']
		self.__sequentialPages = row['sequentialPages']
		self.__density = row['density']
		self.__userDefined = row['userDefined']
		self.__required = row['required']
		self.__created = row['created']
		self.__statsUpdated = row['statsUpdated']
		self.__reverseScans = row['reverseScans']
		self.__description = row['description']
		self.__tablespaceName = row['tablespaceName']
		self.__fields = IndexFieldsDict(self.database, row['tableSchema'], row['tableName'], cache.indexFields[(schema.name, self.name)])
		self.__fieldList = IndexFieldsList(self.database, row['tableSchema'], row['tableName'], cache.indexFields[(schema.name, self.name)])

	def getTypeName(self):
		return "Index"

	def getIdentifier(self):
		return "index_%s_%s" % (self.schema.name, self.name)

	def getDescription(self):
		if self.__description:
			return self.__description
		else:
			return super(Index, self).getDescription()

	def __getFields(self):
		return self.__fields

	def __getFieldList(self):
		return self.__fieldList

	def __getTable(self):
		return self.database.schemas[self.__tableSchema].tables[self.__tableName]

	def __getTablespace(self):
		return self.database.tablespaces[self.__tablespaceName]

	def __getDefiner(self):
		return self.__definer

	def __getCreated(self):
		return self.__created

	def __getStatsUpdated(self):
		return self.__statsUpdated

	def __getUnique(self):
		return self.__unique

	def __getType(self):
		return self.__type

	def __getLeafPages(self):
		return self.__leafPages

	def __getLevels(self):
		return self.__levels

	def __getCardinality(self):
		return (self.__cardinality, [
			self.__cardinality1,
			self.__cardinality2,
			self.__cardinality3,
			self.__cardinality4
			][:len(self.__fieldList)])

	def __getClusterRatio(self):
		return self.__clusterRatio

	def __getClusterFactor(self):
		return self.__clusterFactor

	def __getSequentialPages(self):
		return self.__sequentialPages

	def __getDensity(self):
		return self.__density

	def __getUserDefined(self):
		return self.__userDefined

	def __getRequired(self):
		return self.__required

	def __getReverseScans(self):
		return self.__reverseScans

	def __getCreateSql(self):
		sql = """CREATE $type $schema.$index
ON $tbschema.$tbname ($fields)"""
		values = {
			'type': {False: 'INDEX', True: 'UNIQUE INDEX'}[self.unique],
			'schema': formatIdentifier(self.schema.name),
			'index': formatIdentifier(self.name),
			'tbschema': formatIdentifier(self.table.schema.name),
			'tbname': formatIdentifier(self.table.name),
			'fields': ', '.join(['%s%s' % (field.name, {
				'Ascending': '',
				'Descending': ' DESC'
			}[order]) for (field, order) in self.fieldList if order != 'Include'])
		}
		if self.unique:
			incfields = [field for (field, order) in self.fieldList if order == 'Include']
			if len(incfields) > 0:
				sql += '\nINCLUDE ($incfields)'
				values['incfields'] = ', '.join([field.name for field in incfields])
		if self.reverseScans:
			sql += '\nALLOW REVERSE SCANS'
		sql += ';'
		return Template(sql).substitute(values)

	def __getDropSql(self):
		sql = Template('DROP INDEX $schema.$index;')
		return sql.substitute({
			'schema': formatIdentifier(self.schema.name),
			'index': formatIdentifier(self.name)
		})

	fields = property(__getFields, doc="""The fields that the index references, each entry is a tuple (field, order)""")
	fieldList = property(__getFieldList, doc="""The fields that the index references in an ordered list, each entry is a tuple (field, order)""")
	table = property(__getTable, doc="""The table that the index is defined for""")
	tablespace = property(__getTablespace, doc="""The tablespace that the index exists within""")
	definer = property(__getDefiner, doc="""The user who created the index""")
	created = property(__getCreated, doc="""Timestamp indicating when the index was created""")
	statsUpdated = property(__getStatsUpdated, doc="""Timestamp indicating when the statistics were last updated""")
	unique = property(__getUnique, doc="""True if the index only permits unique combinations of values""")
	type = property(__getType, doc="""Indicates the type of index (clustering, regular, etc)""")
	leafPages = property(__getLeafPages, doc="""The number of pages used by leaf nodes in the index""")
	levels = property(__getLevels, doc="""The number of levels in the index tree""")
	cardinality = property(__getCardinality, doc="""A tuple containing (index cardinality, [list of partial key cardinalities])""")
	clusterRatio = property(__getClusterRatio, doc="""A crude measure of clustering, used with basic index statistics""")
	clusterFactor = property(__getClusterFactor, doc="""A precise measure of clustering, used with detailed index statistics""")
	sequentialPages = property(__getSequentialPages, doc="""The number of approximately contiguous leaf pages which are in index order""")
	density = property(__getDensity, doc="""The ratio of sequential pages to total pages used by the index""")
	userDefined = property(__getUserDefined, doc="""True if the index is user defined, False if system defined""")
	required = property(__getRequired, doc="""True if the index is required to enforce another object like a primary key or unique constraint""")
	reverseScans = property(__getReverseScans, doc="""True if the index supports bidirectional scans""")
	createSql = property(__getCreateSql, doc="""The SQL that can be used to create the index""")
	dropSql = property(__getDropSql, doc="""The SQL that can be used to drop the index""")

def main():
	pass

if __name__ == "__main__":
	main()
