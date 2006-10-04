# $Header$
# vim: set noet sw=4 ts=4:

# Standard modules
import re
import logging

# Application-specific modules
from db.relationbase import Constraint
from db.util import format_ident

class UniqueKeyFieldsList(object):
	"""Presents a list of fields in a unique key"""

	def __init__(self, table, fields):
		"""Initializes the list from a list of field names"""
		assert type(fields) == type([])
		self._table = table
		self._items = fields

	def __len__(self):
		return len(self._items)

	def __getItem__(self, key):
		assert type(key) == int
		return self._table.fields[self._items[key]]

	def __iter__(self):
		for i in self._items:
			yield self._table.fields[i]

	def __contains__(self, key):
		for i in self:
			if i == key:
				return True
		return False

class UniqueKey(Constraint):
	"""Class representing a unique key in a table in a DB2 database"""

	def __init__(self, table, input, **row):
		"""Initializes an instance of the class from a input row"""
		super(UniqueKey, self).__init__(table, row['name'])
		logging.debug("Building unique key %s" % (self.qualified_name))
		self.type_name = 'Unique Key'
		self.description = row.get('description', None) or self.description
		self.definer = row.get('definer', None)
		self.check_existing = row.get('checkExisting', None)
		self._fields = UniqueKeyFieldsList(table, input.unique_key_fields[(table.schema.name, table.name, self.name)])
		# XXX DB2 specific
		self._anonymous = re.match('^SQL\d{15}$', self.name)

	def _get_fields(self):
		return self._fields

	def _get_prototype(self):
		sql = 'UNIQUE (%s)' % ', '.join([format_ident(field.name) for field in self.fields])
		if not self._anonymous:
			sql = 'CONSTRAINT %s %s' % (self.name, sql)
		return sql

class PrimaryKey(UniqueKey):
	"""Class representing a primary key in a table in a DB2 database"""

	def __init__(self, table, input, **row):
		"""Initializes an instance of the class from a input row"""
		super(PrimaryKey, self).__init__(table, input, row)
		self.type_name = 'Primary Key'

	def _get_prototype(self):
		sql = 'PRIMARY KEY (%s)' % ', '.join([format_ident(field.name) for field in self.fields])
		if not self._anonymous:
			sql = 'CONSTRAINT %s %s' % (self.name, sql)
		return sql
