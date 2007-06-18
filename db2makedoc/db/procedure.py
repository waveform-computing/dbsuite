# $Header$
# vim: set noet sw=4 ts=4:

import logging
from string import Template
from db2makedoc.db.schemabase import Routine
from db2makedoc.db.param import Param
from db2makedoc.db.util import format_size, format_ident

class Procedure(Routine):
	"""Class representing a procedure in a DB2 database"""
	
	def __init__(self, schema, input, *row):
		"""Initializes an instance of the class from a input row"""
		super(Procedure, self).__init__(schema, row[2], row[1])
		logging.debug("Building procedure %s" % (self.qualified_name))
		(
			_,
			_,
			_,
			self.owner,
			self._system,
			self.created,
			self.deterministic,
			self.external_action,
			self.null_call,
			self.sql_access,
			self.sql,
			desc
		) = row
		self.type_name = 'Procedure'
		self.description = desc or self.description
		self._param_list = [
			Param(self, input, position, *item)
			for (position, item) in enumerate(input.procedure_params[(schema.name, self.specific_name)])
			if item[1] != 'R'
		]
		self._params = dict([
			(param.name, param)
			for param in self._param_list
		])

	def _get_parent_list(self):
		return self.schema.procedure_list

	def _get_params(self):
		return self._params

	def _get_param_list(self):
		return self._param_list

	def _get_prototype(self):
		
		def format_params(params):
			parmtype = {
				'I': 'IN',
				'O': 'OUT',
				'B': 'INOUT',
			}
			return ', '.join([
				'%s %s %s' % (parmtype[param.type], param.name, param.datatype_str)
				for param in params
			])

		return "%s(%s)" % (self.qualified_name, format_params(self.param_list))
	
	def _get_create_sql(self):
		if self.sql:
			return self.sql + '!'
		else:
			return ''
	
	def _get_drop_sql(self):
		sql = Template('DROP SPECIFIC PROCEDURE $schema.$specific;')
		return sql.substitute({
			'schema': format_ident(self.schema.name),
			'specific': format_ident(self.specific_name)
		})
