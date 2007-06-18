# $Header$
# vim: set noet sw=4 ts=4:

import logging
from string import Template
from db2makedoc.db.schemabase import Routine
from db2makedoc.db.param import Param
from db2makedoc.db.util import format_size, format_ident

class Function(Routine):
	"""Class representing a function in a DB2 database"""
	
	def __init__(self, schema, input, *row):
		"""Initializes an instance of the class from a input row"""
		super(Function, self).__init__(schema, row[2], row[1])
		logging.debug("Building function %s" % (self.qualified_name))
		(
			_,
			_,
			_,
			self.owner,
			self._system,
			self.created,
			self.type,
			self.deterministic,
			self.external_action,
			self.null_call,
			self.sql_access,
			self.sql,
			desc
		) = row
		self.type_name = 'Function'
		self.description = desc or self.description
		self._param_list = [
			Param(self, input, position + 1, *item)
			for (position, item) in enumerate(input.function_params[(schema.name, self.specific_name)])
			if item[1] != 'R'
		]
		self._params = dict([
			(param.name, param)
			for param in self._param_list
		])
		self._return_list = [
			Param(self, input, position + 1, *item)
			for (position, item) in enumerate(input.function_params[(schema.name, self.specific_name)])
			if item[1] == 'R'
		]
		self._returns = dict([
			(param.name, param)
			for param in self._return_list
		])
		self._params = {}
		self._returns = {}

	def _get_parent_list(self):
		return self.schema.function_list

	def _get_params(self):
		return self._params
	
	def _get_param_list(self):
		return self._param_list

	def _get_returns(self):
		return self._returns

	def _get_return_list(self):
		return self._return_list
	
	def _get_prototype(self):
		
		def format_params(params):
			return ', '.join(['%s %s' % (param.name, param.datatype_str) for param in params])

		def format_returns():
			if len(self.return_list) == 0:
				return ''
			elif self.type == 'R':
				return ' RETURNS ROW(%s)' % (format_params(self.return_list))
			elif self.type == 'T':
				return ' RETURNS TABLE(%s)' % (format_params(self.return_list))
			else:
				return ' RETURNS %s' % (self.return_list[0].datatype_str)

		return "%s(%s)%s" % (
			self.qualified_name,
			format_params(self.param_list),
			format_returns()
		)
	
	def _get_create_sql(self):
		if self.language == 'SQL':
			if self.sql:
				return self.sql + '!'
			else:
				return ''
		else:
			# XXX Add ability to generate CREATE FUNCTION for externals
			raise NotImplementedError
	
	def _get_drop_sql(self):
		sql = Template('DROP SPECIFIC FUNCTION $schema.$specific;')
		return sql.substitute({
			'schema': format_ident(self.schema.name),
			'specific': format_ident(self.specific_name)
		})
