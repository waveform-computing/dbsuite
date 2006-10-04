# $Header$
# vim: set noet sw=4 ts=4:

# Standard modules
import logging

# Application-specific modules
from db.base import DocBase
from db.proxies import IndexesDict, IndexesList, RelationsDict, RelationsList

class Tablespace(DocBase):
	"""Class representing a tablespace in a DB2 database"""

	def __init__(self, database, input, **row):
		"""Initializes an instance of the class from a input row"""
		super(Tablespace, self).__init__(database, row['name'])
		logging.debug("Building tablespace %s" % (self.qualified_name))
		self.type_name = 'Tablespace'
		self.description = row.get('description', None) or self.description
		self.definer = row['definer']
		self.created = row['created']
		self.managedBy = row['managedBy']
		self.dataType = row['dataType']
		self.extentSize = row['extentSize']
		self.prefetchSize = row['prefetchSize']
		self.overhead = row['overhead']
		self.transferRate = row['transferRate']
		self.pageSize = row['pageSize']
		self.dropRecovery = row['dropRecovery']
		self.table_list = RelationsList(self.database, sorted(input.tablespace_tables[self.name]))
		self.tables = RelationsDict(self.database, input.tablespace_tables[self.name])
		self.index_list = IndexesList(self.database, sorted(input.tablespace_indexes[self.name]))
		self.indexes = IndexesDict(self.database, input.tablespace_indexes[self.name])

	def _get_identifier(self):
		return "tbspace_%s" % (self.name)

	def _get_qualified_name(self):
		return self.name

	def _get_database(self):
		return self.parent

	def _get_parent_list(self):
		return self.database.tablespace_list
