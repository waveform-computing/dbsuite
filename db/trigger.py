# $Header$
# vim: set noet sw=4 ts=4:

# Standard modules
import logging
from string import Template

# Application-specific modules
from db.schemabase import SchemaObject
from db.proxies import RelationsDict, RelationsList
from db.util import format_ident

class Trigger(SchemaObject):
	"""Class representing an index in a DB2 database"""

	def __init__(self, schema, cache, **row):
		"""Initializes an instance of the class from a cache row"""
		super(Trigger, self).__init__(schema, row['name'])
		logging.debug("Building trigger %s" % (self.qualified_name))
		self.type_name = 'Trigger'
		self.description = row.get('description', None) or self.description
		self.definer = row.get('definer', None)
		self.created = row.get('created', None)
		self.valid = row.get('valid', None)
		self.qualifier = row.get('qualifier', None)
		self.funcPath = row.get('funcPath', None)
		self.sql = row.get('sql', None)
		self.trigger_time = row['triggerTime']
		self.trigger_event = row['triggerEvent']
		self._relation_schema = row['tableSchema']
		self._relation_name = row['tableName']

	def _get_identifier(self):
		return "trigger_%s_%s" % (self.schema.name, self.name)

	def _get_parent_list(self):
		return self.schema.triggerList

	def _get_create_sql(self):
		if self.sql:
			return self.sql + '!'
		else:
			return ''

	def _get_drop_sql(self):
		sql = Template('DROP TRIGGER $schema.$trigger;')
		return sql.substitute({
			'schema': format_ident(self.schema.name),
			'trigger': format_ident(self.name),
		})

	def _get_relation(self):
		"""Returns the relation that the trigger applies to"""
		return self.database.schemas[self._relation_schema].relations[self._relation_name]

	relation = property(_get_relation)
