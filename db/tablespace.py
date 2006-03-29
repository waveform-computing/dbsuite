#!/bin/env python
# $Header$
# vim: set noet sw=4 ts=4:

import logging
from base import DocBase
from proxies import IndexesDict, IndexesList, RelationsDict, RelationsList

class Tablespace(DocBase):
	"""Class representing a tablespace in a DB2 database"""

	def __init__(self, database, cache, **row):
		"""Initializes an instance of the class from a cache row"""
		super(Tablespace, self).__init__(database, row['name'])
		logging.debug("Building tablespace %s" % (self.qualifiedName))
		self.__definer = row['definer']
		self.__created = row['created']
		self.__managedBy = row['managedBy']
		self.__dataType = row['dataType']
		self.__extentSize = row['extentSize']
		self.__prefetchSize = row['prefetchSize']
		self.__overhead = row['overhead']
		self.__transferRate = row['transferRate']
		self.__pageSize = row['pageSize']
		self.__dropRecovery = row['dropRecovery']
		self.__description = row['description']
		self.__tableList = RelationsList(self.database, sorted(cache.tablespaceTables[self.name]))
		self.__tables = RelationsDict(self.database, cache.tablespaceTables[self.name])
		self.__indexList = IndexesList(self.database, sorted(cache.tablespaceIndexes[self.name]))
		self.__indexes = IndexesDict(self.database, cache.tablespaceIndexes[self.name])

	def getTypeName(self):
		return "Tablespace"

	def getIdentifier(self):
		return "tbspace_%s" % (self.name)

	def getQualifiedName(self):
		return self.name

	def getDescription(self):
		if self.__description:
			return self.__description
		else:
			return super(Tablespace, self).getDescription()

	def getDatabase(self):
		return self.parent

	def __getTables(self):
		return self.__tables

	def __getTableList(self):
		return self.__tableList

	def __getIndexes(self):
		return self.__indexes

	def __getIndexList(self):
		return self.__indexList

	def __getDefiner(self):
		return self.__definer

	def __getCreated(self):
		return self.__created

	def __getManagedBy(self):
		return self.__managedBy

	def __getDataType(self):
		return self.__dataType

	def __getExtentSize(self):
		return self.__extentSize

	def __getPrefetchSize(self):
		return self.__prefetchSize

	def __getOverhead(self):
		return self.__overhead

	def __getTransferRate(self):
		return self.__transferRate

	def __getPageSize(self):
		return self.__pageSize

	def __getDropRecovery(self):
		return self.__dropRecovery

	tables = property(__getTables, doc="""A dictionary of the tables contained in the tablespace (keyed by (schemaName, tableName) tuples)""")
	tableList = property(__getTableList, doc="""A list of the tables contained in the tablespace, sorted by qualified name""")
	indexes = property(__getIndexes, doc="""A dictionary of the indexes contained in the tablespace (keyed by (schemaName, indexName) tuples)""")
	indexList = property(__getIndexList, doc="""A list of the indexes contained in the tablespace, sorted by qualified name""")
	definer = property(__getDefiner, doc="""The user ID who created the tablespace""")
	created = property(__getCreated, doc="""Timestamp indicating when the tablespace was created""")
	managedBy = property(__getManagedBy, doc="""Indicates whether the tablespace is managed by the operating system or the database""")
	dataType = property(__getDataType, doc="""Indicates the types of table data that the tablespace can hold""")
	extentSize = property(__getExtentSize, doc="""Indicates the minimum number of pages allocated to objects in the tablespace""")
	prefetchSize = property(__getPrefetchSize, doc="""Indicates the minimum number of contiguous pages retrieved during a prefetch operation""")
	overhead = property(__getOverhead, doc="""Disk latency time in milliseconds""")
	transferRate = property(__getTransferRate, doc="""Time to read one page into the buffer""")
	pageSize = property(__getPageSize, doc="""The size (in bytes) of pages in the tablespace""")
	dropRecovery = property(__getDropRecovery, doc="""Whether dropped tables can be recovered in this tablespace""")

def main():
	pass

if __name__ == "__main__":
	main()
