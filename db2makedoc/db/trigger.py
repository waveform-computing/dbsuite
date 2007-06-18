# $Header$
# vim: set noet sw=4 ts=4:

import logging
from string import Template
from db2makedoc.db.schemabase import SchemaObject
from db2makedoc.db.proxies import RelationsDict, RelationsList
from db2makedoc.db.util import format_ident

class Trigger(SchemaObject):
	"""Class representing an index in a DB2 database"""

	def __init__(self, schema, input, *row):
		"""Initializes an instance of the class from a input row"""
		super(Trigger, self).__init__(schema, row[1])
		logging.debug("Building trigger %s" % (self.qualified_name))
		(
			_,
			_,
			self.owner,
			self._system,
			self.created,
			self._relation_schema,
			self._relation_name,
			self.trigger_time,
			self.trigger_event,
			self.granularity,
			self.sql,
			desc
		) = row
		self.type_name = 'Trigger'
		self.description = desc or self.description
		self.dependencies = RelationsDict(
			self.database,
			input.trigger_dependencies[(schema.name, self.name)]
		)
		self.dependency_list = RelationsList(
			self.database,
			input.trigger_dependencies[(schema.name, self.name)]
		)

	def _get_identifier(self):
		return "trigger_%s_%s" % (self.schema.name, self.name)

	def _get_parent_list(self):
		return self.schema.trigger_list

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
