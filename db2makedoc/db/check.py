# $Header$
# vim: set noet sw=4 ts=4:

import re
import logging
from db2makedoc.db.relationbase import Constraint
from db2makedoc.db.util import format_ident

class CheckFieldsList(object):
	"""Presents a list of fields in a check constraint"""

	def __init__(self, table, fields):
		"""Initializes the list from a list of field names"""
		super(CheckFieldsList, self).__init__()
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

class Check(Constraint):
	"""Class representing a check constraint in a table in a DB2 database"""

	def __init__(self, table, input, **row):
		"""Initializes an instance of the class from a input row"""
		super(Check, self).__init__(table, row['name'])
		logging.debug("Building check %s" % (self.qualified_name))
		self.type_name = 'Check Constraint'
		self.description = row.get('description', None) or self.description
		self.created = row.get('created', None)
		self.definer = row.get('definer', None)
		self.enforced = row.get('enforced', None)
		self.query_optimize = row.get('queryOptimize', None)
		self.check_existing = row.get('checkExisting', None)
		self.type = row.get('type', None)
		self.qualifier = row.get('qualifier', None)
		self.func_path = row.get('funcPath', None)
		self.expression = row.get('expression', None)
		self._fields = CheckFieldsList(table, input.check_fields[(table.schema.name, table.name, self.name)])
		self._system = self.type == 'SYSTEM'
		# XXX DB2 specific
		self._anonymous = re.match('^SQL\d{15}$', self.name)

	def _get_fields(self):
		return self._fields

	def _get_prototype(self):
		sql = 'CHECK (%s)' % self.expression
		if not self._anonymous:
			sql = 'CONSTRAINT %s %s' % (self.name, sql)
		return sql
