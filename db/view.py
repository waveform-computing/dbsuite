# $Header$
# vim: set noet sw=4 ts=4:

# Standard modules
import logging
from string import Template

# Application-specific modules
from db.schemabase import Relation
from db.proxies import RelationsDict, RelationsList, TriggersDict, TriggersList
from db.field import Field
from db.util import format_ident

class View(Relation):
	"""Class representing a view in a DB2 database"""
	
	def __init__(self, schema, cache, **row):
		"""Initializes an instance of the class from a cache row"""
		super(View, self).__init__(schema, row['name'])
		logging.debug("Building view %s" % (self.qualified_name))
		self.type_name = 'View'
		self.description = row.get('description', None) or self.description
		self.definer = row.get('definer', None)
		self.created = row.get('created', None)
		self.check = row.get('check', None)
		self.readOnly = row.get('readOnly', None)
		self.valid = row.get('valid', None)
		self.qualifier = row.get('qualifier', None)
		self.funcPath = row.get('funcPath', None)
		self.sql = row.get('sql', None)
		self._fields = {}
		for field in [cache.fields[(schema_name, view_name, field_name)] for (schema_name, view_name, field_name) in cache.fields if schema_name == schema.name and view_name == self.name]:
			self._fields[field['name']] = Field(self, cache, **field)
		self._field_list = sorted(self._fields.itervalues(), key=lambda field:field.position)
		self._dependents = RelationsDict(self.database, cache.relation_dependents.get((schema.name, self.name)))
		self._dependent_list = RelationsList(self.database, cache.relation_dependents.get((schema.name, self.name)))
		self.dependencies = RelationsDict(self.database, cache.relation_dependencies.get((schema.name, self.name)))
		self.dependency_list = RelationsList(self.database, cache.relation_dependencies.get((schema.name, self.name)))
		self.triggers = TriggersDict(self.database, cache.relation_triggers.get((schema.name, self.name)))
		self.trigger_list = TriggersList(self.database, cache.relation_triggers.get((schema.name, self.name)))

	def _get_dependents(self):
		return self._dependents
	
	def _get_dependent_list(self):
		return self._dependent_list
	
	def _get_fields(self):
		return self._fields
	
	def _get_field_list(self):
		return self._field_list

	def _get_create_sql(self):
		return self.sql + ';'
	
	def _get_drop_sql(self):
		sql = Template('DROP VIEW $schema.$view;')
		return sql.substitute({
			'schema': format_ident(self.schema.name),
			'view': format_ident(self.name),
		})
