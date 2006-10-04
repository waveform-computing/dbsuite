# $Header$
# vim: set noet sw=4 ts=4:

# Standard modules
import logging

# Application-specific modules
from db.base import DocBase
from db.table import Table
from db.view import View
from db.alias import Alias
from db.index import Index
from db.trigger import Trigger
from db.datatype import Datatype
from db.function import Function
from db.procedure import Procedure

class Schema(DocBase):
	"""Class representing a schema in a DB2 database"""

	def __init__(self, database, input, **row):
		"""Initializes an instance of the class from a input row"""
		super(Schema, self).__init__(database, row['name'])
		logging.debug("Building schema %s" % (self.qualified_name))
		self.type_name = 'Schema'
		self.description = row.get('description', None) or self.description
		self.owner = row.get('owner', None)
		self.definer = row.get('definer', None)
		self.created = row.get('created', None)
		self.datatypes = {}
		self.relations = {}
		self.tables = {}
		self.views = {}
		self.aliases = {}
		self.indexes = {}
		self.routines = {}
		self.functions = {}
		self.methods = {}
		self.procedures = {}
		self.triggers = {}
		self.specific_routines = {}
		self.specific_functions = {}
		self.specific_methods = {}
		self.specific_procedures = {}
		# XXX Could all this be done entirely with list comprehensions instead?
		for datatype in [input.datatypes[(schema, name)] for (schema, name) in input.datatypes if schema == self.name]:
			self.datatypes[datatype['name']] = Datatype(self, input, **datatype)
		self.datatype_list = sorted(self.datatypes.itervalues(), key=lambda datatype: datatype.name)
		for table_rec in [input.tables[(schema, name)] for (schema, name) in input.tables if schema == self.name]:
			table = Table(self, input, **table_rec)
			self.tables[table_rec['name']] = table
			self.relations[table_rec['name']] = table
		self.table_list = sorted(self.tables.itervalues(), key=lambda table:table.name)
		for view_rec in [input.views[(schema, name)] for (schema, name) in input.views if schema == self.name]:
			view = View(self, input, **view_rec)
			self.views[view_rec['name']] = view
			self.relations[view_rec['name']] = view
		self.view_list = sorted(self.views.itervalues(), key=lambda view:view.name)
		for alias_rec in [input.aliases[(schema, name)] for (schema, name) in input.aliases if schema == self.name]:
			alias = Alias(self, input, **alias_rec)
			self.aliases[alias_rec['name']] = alias
			self.relations[alias_rec['name']] = alias
		self.alias_list = sorted(self.aliases.itervalues(), key=lambda alias:alias.name)
		self.relation_list = sorted(self.relations.itervalues(), key=lambda relation:relation.name)
		for index_rec in [input.indexes[(schema, name)] for (schema, name) in input.indexes if schema == self.name]:
			self.indexes[index_rec['name']] = Index(self, input, **index_rec)
		self.index_list = sorted(self.indexes.itervalues(), key=lambda index:index.name)
		for func_rec in [input.functions[(schema, name)] for (schema, name) in input.functions if schema == self.name]:
			func = Function(self, input, **func_rec)
			if not func_rec['name'] in self.routines:
				self.routines[func_rec['name']] = []
			self.routines[func_rec['name']].append(func)
			if not func_rec['name'] in self.functions:
				self.functions[func_rec['name']] = []
			self.functions[func_rec['name']].append(func)
			self.specificRoutines[func_rec['specific_name']] = func
			self.specificFunctions[func_rec['specific_name']] = func
		self.function_list = sorted(self.specificFunctions.itervalues(), key=lambda function:function.name)
		for proc_rec in [input.procedures[(schema, name)] for (schema, name) in input.procedures if schema == self.name]:
			proc = Procedure(self, input, **proc_rec)
			if not proc_rec['name'] in self.routines:
				self.routines[proc_rec['name']] = []
			self.routines[proc_rec['name']].append(proc)
			if not proc_rec['name'] in self.procedures:
				self.procedures[proc_rec['name']] = []
			self.procedures[proc_rec['name']].append(proc)
			self.specificRoutines[proc_rec['specific_name']] = proc
			self.specificProcedures[proc_rec['specific_name']] = proc
		self.procedure_list = sorted(self.specificProcedures.itervalues(), key=lambda procedure:procedure.name)
		# XXX Add support for methods
		self.routine_list = sorted(self.specificRoutines.itervalues(), key=lambda routine:routine.name)
		# XXX Add support for sequences
		for trig_rec in [input.triggers[(schema, name)] for (schema, name) in input.triggers if schema == self.name]:
			self.triggers[trig_rec['name']] = Trigger(self, input, **trig_rec)
		self.trigger_list = sorted(self.triggers.itervalues(), key=lambda trigger:trigger.name)

	def _get_identifier(self):
		return "schema_%s" % (self.name)
	
	def _get_qualified_name(self):
		# Schemas form the top of the naming hierarchy
		return self.name
	
	def _get_system(self):
		# XXX DB2 specific
		return self.name in [
			"NULLID",
			"SQLJ",
			"SYSCAT",
			"SYSFUN",
			"SYSIBM",
			"SYSPROC",
			"SYSSTAT",
			"SYSTOOLS"
		]

	def _get_database(self):
		return self.parent

	def _get_parent_list(self):
		return self.database.schema_list
