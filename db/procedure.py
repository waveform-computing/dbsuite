# $Header$
# vim: set noet sw=4 ts=4:

# Standard modules
import logging
from string import Template

# Application-specific modules
from db.schemabase import Routine
from db.param import Param
from db.util import format_size, format_ident

class Procedure(Routine):
	"""Class representing a procedure in a DB2 database"""
	
	def __init__(self, schema, cache, **row):
		"""Initializes an instance of the class from a cache row"""
		super(Procedure, self).__init__(schema, row['name'], row['specific_name'])
		logging.debug("Building procedure %s" % (self.qualified_name))
		self.type_name = 'Procedure'
		self.description = row.get('description', None) or self.description
		self.definer = row.get('definer', None)
		self.origin = row.get('origin', None)
		self.deterministic = row.get('deterministic', None)
		self.external_action = row.get('externalAction', None)
		self.null_call = row.get('nullCall', None)
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
		myparams = [
			cache.proc_params[(schema_name, specific_name, param_type, param_pos)]
			for (schema_name, specific_name, param_type, param_pos) in cache.proc_params
			if schema_name == schema.name and specific_name == self.specific_name
		]
		for row in myparams:
			param = Param(self, cache, **row)
			self._params[param.name] = param
		self._param_list = sorted(self._params.itervalues(), key=lambda param:param.position)

	def _get_parent_list(self):
		return self.schema.procedure_list

	def _get_params(self):
		return self._params

	def _get_param_list(self):
		return self._param_list

	def _get_prototype(self):
		
		def format_params(params):
			return ', '.join([
				'%s %s %s' % (param.type, param.name, param.datatype_str)
				for param in params
			])

		return "%s(%s)" % (self.qualified_name, format_params(self.param_list))
	
	def _get_create_sql(self):
		if self.language == 'SQL':
			if self.sql:
				return self.sql + '!'
			else:
				return ''
		else:
			# XXX Add ability to generate CREATE PROCEDURE for externals
			raise NotImplementedError
	
	def _get_drop_sql(self):
		sql = Template('DROP SPECIFIC PROCEDURE $schema.$specific;')
		return sql.substitute({
			'schema': format_ident(self.schema.name),
			'specific': format_ident(self.specific_name)
		})
