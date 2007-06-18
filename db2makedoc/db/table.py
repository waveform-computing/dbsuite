# $Header$
# vim: set noet sw=4 ts=4:

import logging
from string import Template
from db2makedoc.db.schemabase import Relation
from db2makedoc.db.proxies import IndexesDict, IndexesList, RelationsDict, RelationsList, TriggersDict, TriggersList
from db2makedoc.db.field import Field
from db2makedoc.db.uniquekey import UniqueKey, PrimaryKey
from db2makedoc.db.foreignkey import ForeignKey
from db2makedoc.db.check import Check
from db2makedoc.db.util import format_ident

class Table(Relation):
	"""Class representing a table in a DB2 database"""

	def __init__(self, schema, input, *row):
		"""Initializes an instance of the class from a input row"""
		super(Table, self).__init__(schema, row[1])
		logging.debug("Building table %s" % (self.qualified_name))
		(
			_,
			_,
			self.owner,
			self._system,
			self.created,
			self.last_stats,
			self.cardinality,
			self.size,
			self._tablespace,
			desc
		) = row
		self.type_name = 'Table'
		self.description = desc or self.description
		self._field_list = [
			Field(self, input, position + 1, *item)
			for (position, item) in enumerate(input.relation_cols[(schema.name, self.name)])
		]
		self._fields = dict([
			(field.name, field)
			for field in self._field_list
		])
		self._dependents = RelationsDict(
			self.database,
			input.relation_dependents[(schema.name, self.name)]
		)
		self._dependent_list = RelationsList(
			self.database,
			input.relation_dependents[(schema.name, self.name)]
		)
		self.indexes = IndexesDict(
			self.database,
			input.table_indexes[(schema.name, self.name)]
		)
		self.index_list = IndexesList(
			self.database,
			input.table_indexes[(schema.name, self.name)]
		)
		self.triggers = TriggersDict(
			self.database,
			input.relation_triggers[(schema.name, self.name)]
		)
		self.trigger_list = TriggersList(
			self.database,
			input.relation_triggers[(schema.name, self.name)]
		)
		self.unique_key_list = [
			UniqueKey(self, input, *item)
			for item in input.unique_keys[(schema.name, self.name)]
			if not item[-2]
		]
		pitem = [
			PrimaryKey(self, input, *item)
			for item in input.unique_keys[(schema.name, self.name)]
			if item[-2]
		]
		if len(pitem) == 0:
			self.primary_key = None
		elif len(pitem) == 1:
			self.primary_key = pitem[0]
			self.unique_key_list.append(self.primary_key)
		else:
			# Something's gone horribly wrong in the input plugin - got more
			# than one primary key for the table!
			assert False
		self.unique_key_list = sorted(
			self.unique_key_list,
			key=lambda item:item.name
		)
		self.unique_keys = dict([
			(unique_key.name, unique_key)
			for unique_key in self.unique_key_list
		])
		self.foreign_key_list = sorted([
			ForeignKey(self, input, *item)
			for item in input.foreign_keys[(schema.name, self.name)]
		], key=lambda item:item.name)
		self.foreign_keys = dict([
			(foreign_key.name, foreign_key)
			for foreign_key in self.foreign_key_list
		])
		self.check_list = sorted([
			Check(self, input, *item)
			for item in input.checks[(schema.name, self.name)]
		], key=lambda item:item.name)
		self.checks = dict([
			(check.name, check)
			for check in self.check_list
		])
		self.constraint_list = sorted(
			self.unique_key_list + self.foreign_key_list + self.check_list,
			key=lambda item:item.name
		)
		self.constraints = dict([
			(constraint.name, constraint)
			for constraint in self.constraint_list
		])

	def _get_fields(self):
		return self._fields

	def _get_field_list(self):
		return self._field_list

	def _get_dependents(self):
		return self._dependents

	def _get_dependent_list(self):
		return self._dependent_list

	def _get_create_sql(self):
		sql = Template('CREATE TABLE $schema.$table ($elements) IN $tbspace;$indexes')
		return sql.substitute({
			'schema': format_ident(self.schema.name),
			'table': format_ident(self.name),	
			'elements': ',\n'.join([
					field.prototype
					for field in self.field_list
				] + [
					constraint.prototype
					for constraint in self.constraints.itervalues()
					if not isinstance(constraint, Check) or not constraint.system
				]),
			'tbspace': format_ident(self.tablespace.name),
			'indexes': ''.join([
					'\n' + index.create_sql
					for index in self.index_list
				]),
		}
	
	def _get_drop_sql(self):
		sql = Template('DROP TABLE $schema.$table;')
		return sql.substitute({
			'schema': format_ident(self.schema.name),
			'table': format_ident(self.name)
		})
	
	def _get_tablespace(self):
		"""Returns the tablespace in which the table's data is stored"""
		return self.database.tablespaces[self._tablespace]

	tablespace = property(_get_tablespace)
