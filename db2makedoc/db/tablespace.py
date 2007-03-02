# $Header$
# vim: set noet sw=4 ts=4:

import logging
from db2makedoc.db.base import DocBase
from db2makedoc.db.proxies import IndexesDict, IndexesList, RelationsDict, RelationsList

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
		self.managed_by = row['managedBy']
		self.data_type = row['dataType']
		self.extent_size = row['extentSize']
		self.prefetch_size = row['prefetchSize']
		self.overhead = row['overhead']
		self.transfer_rate = row['transferRate']
		self.page_size = row['pageSize']
		self.drop_recovery = row['dropRecovery']
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
