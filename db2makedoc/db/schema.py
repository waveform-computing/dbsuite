# $Header$
# vim: set noet sw=4 ts=4:

import logging
from db2makedoc.db.base import DocBase
from db2makedoc.db.table import Table
from db2makedoc.db.view import View
from db2makedoc.db.alias import Alias
from db2makedoc.db.index import Index
from db2makedoc.db.trigger import Trigger
from db2makedoc.db.datatype import Datatype
from db2makedoc.db.function import Function
from db2makedoc.db.procedure import Procedure

class Schema(DocBase):
	"""Class representing a schema in a DB2 database"""

	def __init__(self, database, input, *row):
		"""Initializes an instance of the class from a input row"""
		super(Schema, self).__init__(database, row[0])
		logging.debug("Building schema %s" % (self.qualified_name))
		(
			_,
			self.owner,
			self._system,
			self.created,
			desc
		) = row
		self.type_name = 'Schema'
		self.description = desc or self.description
		self.datatype_list = sorted([
			Datatype(self, input, *item)
			for item in input.datatypes
			if item[0] == self.name
		], key=lambda item:item.name)
		self.datatypes = dict([
			(datatype.name, datatype)
			for datatype in self.datatype_list
		])
		self.table_list = sorted([
			Table(self, input, *item)
			for item in input.tables
			if item[0] == self.name
		], key=lambda item:item.name)
		self.tables = dict([
			(table.name, table)
			for table in self.table_list
		])
		self.view_list = sorted([
			View(self, input, *item)
			for item in input.views
			if item[0] == self.name
		], key=lambda item:item.name)
		self.views = dict([
			(view.name, view)
			for view in self.view_list
		])
		self.alias_list = sorted([
			Alias(self, input, *item)
			for item in input.aliases
			if item[0] == self.name
		], key=lambda item:item.name)
		self.aliases = dict([
			(alias.name, alias)
			for alias in self.alias_list
		])
		self.relation_list = sorted(
			self.table_list + self.view_list + self.alias_list,
			key=lambda item:item.name
		)
		self.relations = dict([
			(relation.name, relation)
			for relation in self.relation_list
		])
		self.index_list = sorted([
			Index(self, input, *item)
			for item in input.indexes
			if item[0] == self.name
		])
		self.indexes = dict([
			(index.name, index)
			for index in self.index_list
		])
		self.function_list = sorted([
			Function(self, input, *item)
			for item in input.functions
			if item[0] == self.name
		], key=lambda item:item.name)
		self.functions = {}
		for function in self.function_list:
			if function.name in self.functions:
				self.functions[function.name].append(function)
			else:
				self.functions[function.name] = [function]
		self.specific_functions = dict([
			(function.specific_name, function)
			for function in self.function_list
		])
		self.procedure_list = sorted([
			Procedure(self, input, *item)
			for item in input.procedures
			if item[0] == self.name
		], key=lambda item:item.name)
		self.procedures = {}
		for procedure in self.procedure_list:
			if procedure.name in self.procedures:
				self.procedures[procedure.name].append(procedure)
			else:
				self.procedures[procedure.name] = [procedure]
		self.specific_procedures = dict([
			(procedure.specific_name, procedure)
			for procedure in self.procedure_list
		])
		self.routine_list = sorted(
			self.function_list + self.procedure_list,
			key=lambda item:item.name
		)
		self.routines = dict([
			(routine.name, routine)
			for routine in self.routine_list
		])
		self.specific_routines = dict([
			(routine.specific_name, routine)
			for routine in self.routine_list
		])
		# XXX Add support for methods
		# XXX Add support for sequences
		self.trigger_list = sorted([
			Trigger(self, input, *item)
			for item in input.triggers
			if item[0] == self.name
		], key=lambda item:item.name)
		self.triggers = dict([
			(trigger.name, trigger)
			for trigger in self.trigger_list
		])

	def _get_identifier(self):
		return "schema_%s" % (self.name)
	
	def _get_qualified_name(self):
		# Schemas form the top of the naming hierarchy
		return self.name
	
	def _get_database(self):
		return self.parent

	def _get_parent_list(self):
		return self.database.schema_list
