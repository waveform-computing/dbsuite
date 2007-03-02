# $Header$
# vim: set noet sw=4 ts=4:

import logging
from string import Template
from db2makedoc.db.schemabase import Routine
from db2makedoc.db.param import Param
from db2makedoc.db.util import format_size, format_ident

class Function(Routine):
	"""Class representing a function in a DB2 database"""
	
	def __init__(self, schema, input, **row):
		"""Initializes an instance of the class from a input row"""
		super(Function, self).__init__(schema, row['name'], row['specificName'])
		logging.debug("Building function %s" % (self.qualified_name))
		self.type_name = 'Function'
		self.description = row.get('description', None) or self.description
		self.definer = row.get('definer', None)
		self.origin = row.get('origin', None)
		self.type = row.get('type', None)
		self.deterministic = row.get('deterministic', None)
		self.external_action = row.get('externalAction', None)
		self.null_call = row.get('nullCall', None)
		self.cast_function = row.get('castFunction', None)
		self.assign_function = row.get('assignFunction', None)
		self.parallel = row.get('parallel', None)
		self.fenced = row.get('fenced', None)
		self.sql_access = row.get('sqlAccess', None)
		self.thread_safe = row.get('threadSafe', None)
		self.valid = row.get('valid', None)
		self.created = row.get('created', None)
		self.qualifier = row.get('qualifier', None)
		self.func_path = row.get('funcPath', None)
		self.sql = row.get('sql', None)
		self.language = row['language']
		self._params = {}
		self._returns = {}
		myparams = [
			input.func_params[(schema_name, specific_name, param_type, param_pos)]
			for (schema_name, specific_name, param_type, param_pos) in input.func_params
			if schema_name == schema.name and specific_name == self.specific_name
		]
		for row in myparams:
			param = Param(self, input, **row)
			if param.type == 'RESULT':
				self._returns[param.name] = param
			else:
				self._params[param.name] = param
		self._param_list = sorted(self._params.itervalues(), key=lambda param:param.position)
		self._return_list = sorted(self._returns.itervalues(), key=lambda param:param.position)

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
			elif self.type == 'ROW':
				return ' RETURNS ROW(%s)' % (format_params(self.return_list))
			elif self.type == 'TABLE':
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
