#!/bin/env python
# $Header$
# vim: set noet sw=4 ts=4:

import re
import logging
from relationbase import Constraint
from util import formatIdentifier

class CheckFieldsList(object):
	"""Presents a list of fields in a check constraint"""

	def __init__(self, table, fields):
		"""Initializes the list from a list of field names"""
		super(CheckFieldsList, self).__init__()
		assert type(fields) == type([])
		self.__table = table
		self.__items = fields

	def __len__(self):
		return len(self.__items)

	def __getItem__(self, key):
		assert type(key) == int
		return self.__table.fields[self.__items[key]]

	def __iter__(self):
		for fieldName in self.__items:
			yield self.__table.fields[fieldName]

	def __contains__(self, key):
		for i in self:
			if i == key:
				return True
		return False

class Check(Constraint):
	"""Class representing a check constraint in a table in a DB2 database"""

	def __init__(self, table, cache, **row):
		"""Initializes an instance of the class from a cache row"""
		super(Check, self).__init__(table, row['name'])
		logging.debug("Building check %s" % (self.qualifiedName))
		self.__created = row['created']
		self.__definer = row['definer']
		self.__enforced = row['enforced']
		self.__checkExisting = row['checkExisting']
		self.__queryOptimize = row['queryOptimize']
		self.__type = row['type']
		self.__qualifier = row['qualifier']
		self.__funcPath = row['funcPath']
		self.__expression = row['expression']
		self.__description = row['description']
		self.__fields = CheckFieldsList(table, cache.checkFields[(table.schema.name, table.name, self.name)])

	def getTypeName(self):
		return "Check Constraint"

	def getFields(self):
		return self.__fields

	def getDescription(self):
		if self.__description:
			return self.__description
		else:
			return super(Check, self).getDescription()

	def getPrototype(self):
		sql = 'CHECK (%s)' % self.expression
		if not re.match('^SQL\d{15}$', self.name):
			sql = 'CONSTRAINT %s %s' % (self.name, sql)
		return sql

	def __getCreated(self):
		return self.__created

	def __getDefiner(self):
		return self.__definer

	def __getEnforced(self):
		return self.__enforced

	def __getCheckExisting(self):
		return self.__checkExisting

	def __getQueryOptimize(self):
		return self.__queryOptimize

	def __getType(self):
		return self.__type

	def __getQualifier(self):
		return self.__qualifier

	def __getFuncPath(self):
		return self.__funcPath

	def __getExpression(self):
		return self.__expression

	created = property(__getCreated, doc="""Timestamp indicating when the check constraint was created""")
	definer = property(__getDefiner, doc="""The user who created the constraint""")
	enforced = property(__getEnforced, doc="""True if the check constraint is enforced during updates""")
	checkExisting = property(__getCheckExisting, doc="""Indicates when existing data is to be checked (if at all)""")
	queryOptimize = property(__getQueryOptimize, doc="""True if the check constraint is used to optimize queries""")
	type = property(__getType, doc="""Whether the constraint is a system-generated constraint (for generated columns) or a user-defined check""")
	qualifier = property(__getQualifier, doc="""The current schema at the time the check constraint was created""")
	funcPath = property(__getFuncPath, doc="""The function resolution path at the time the check constraint was created""")
	expression = property(__getExpression, doc="""The SQL expression that the check constraint tests""")

def main():
	pass

if __name__ == "__main__":
	main()
