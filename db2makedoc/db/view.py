# $Header$
# vim: set noet sw=4 ts=4:

import logging
from string import Template
from db2makedoc.db.schemabase import Relation
from db2makedoc.db.proxies import RelationsDict, RelationsList, TriggersDict, TriggersList
from db2makedoc.db.field import Field
from db2makedoc.db.util import format_ident

class View(Relation):
	"""Class representing a view in a DB2 database"""
	
	def __init__(self, schema, input, *row):
		"""Initializes an instance of the class from a input row"""
		super(View, self).__init__(schema, row[1])
		logging.debug("Building view %s" % (self.qualified_name))
		(
			_,
			_,
			self.owner,
			self._system,
			self.created,
			self.read_only,
			self.sql,
			desc
		) = row
		self.type_name = 'View'
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
		self.dependencies = RelationsDict(
			self.database,
			input.relation_dependencies.[schema.name, self.name)]
		)
		self.dependency_list = RelationsList(
			self.database,
			input.relation_dependencies.[(schema.name, self.name)]
		)
		self.triggers = TriggersDict(
			self.database,
			input.relation_triggers[(schema.name, self.name)]
		)
		self.trigger_list = TriggersList(
			self.database,
			input.relation_triggers[(schema.name, self.name)]
		)

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
