# $Header$
# vim: set noet sw=4 ts=4:

import re
import logging
from db2makedoc.db.relationbase import Constraint
from db2makedoc.db.util import format_ident

class ForeignKeyFieldsList(object):
	"""Presents a list of (field, parentField) tuples in a foreign key"""

	def __init__(self, table, ref_schema_name, ref_table_name, fields):
		"""Initializes the list from a list of (field, parent_field) name tuples"""
		assert type(fields) == type([])
		self._table = table
		self._database = table.database
		self._ref_schema_name = ref_schema_name
		self._ref_table_name = ref_table_name
		self._items = fields

	def __len__(self):
		return len(self._items)

	def __getItem__(self, key):
		assert type(key) == int
		(field_name, parent_name) = self._items[key]
		parent_table = self._database.schemas[self._ref_schema_name].tables[self._ref_table_name]
		return (self._table.fields[field_name], parent_table.fields[parent_name])

	def __iter__(self):
		parent_table = self._database.schemas[self._ref_schema_name].tables[self._ref_table_name]
		for (field_name, parent_name) in self._items:
			yield (self._table.fields[field_name], parent_table.fields[parent_name])

	def __contains__(self, key):
		for i in self:
			if i == key:
				return True
		return False

class ForeignKey(Constraint):
	"""Class representing a foreign key in a table in a DB2 database"""

	def __init__(self, table, input, **row):
		"""Initializes an instance of the class from a input row"""
		super(ForeignKey, self).__init__(table, row['name'])
		logging.debug("Building foreign key %s" % (self.qualified_name))
		self.type_name = 'Foreign Key'
		self.description = row.get('description', None) or self.description
		self.created = row.get('created', None)
		self.definer = row.get('definer', None)
		self.enforced = row.get('enforced', None)
		self.check_existing = row.get('checkExisting', None)
		self.query_optimize = row.get('queryOptimize', None)
		self.delete_rule = row.get('deleteRule', None)
		self.update_rule = row.get('updateRule', None)
		self._ref_table_schema = row['refTableSchema']
		self._ref_table_name = row['refTableName']
		self._ref_key_name = row['refKeyName']
		self._fields = ForeignKeyFieldsList(table, self._ref_table_schema, self._ref_table_name, input.foreign_key_fields[(table.schema.name, table.name, self.name)])
		# XXX DB2 specific
		self._anonymous = re.match('^SQL\d{15}$', self.name)

	def _get_fields(self):
		return self._fields

	def _get_prototype(self):
		sql = 'FOREIGN KEY (%s) REFERENCES %s.%s(%s)' % (
			', '.join([format_ident(myfield.name) for (myfield, reffield) in self.fields]),
			format_ident(self.ref_table.schema.name),
			format_ident(self.ref_table.name),
			', '.join([format_ident(reffield.name) for (myfield, reffield) in self.fields])
		)
		if self.delete_rule:
			sql += ' ON DELETE ' + self.delete_rule
		if self.update_rule:
			sql += ' ON UPDATE ' + self.update_rule
		if not self._anonymous:
			sql = 'CONSTRAINT %s %s' % (self.name, sql)
		return sql

	def _get_ref_table(self):
		"""Returns the table that this foreign key references"""
		return self.database.schemas[self._ref_table_schema].tables[self._ref_table_name]

	def _get_ref_key(self):
		"""Returns the corresponding unique key in the referenced table"""
		return self.ref_table.unique_keys[self._ref_key_name]

	ref_table = property(_get_ref_table)
	ref_key = property(_get_ref_key)
