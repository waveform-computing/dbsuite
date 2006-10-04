# $Header$
# vim: set noet sw=4 ts=4:

# Standard modules
import logging
from string import Template

# Application-specific modules
from db.schemabase import Relation
from db.util import format_ident

class Alias(Relation):
	"""Class representing a alias in a DB2 database"""
	
	def __init__(self, schema, input, **row):
		"""Initializes an instance of the class from a input row"""
		super(Alias, self).__init__(schema, row['name'])
		logging.debug("Building alias %s" % (self.qualified_name))
		self.type_name = 'Alias'
		self.description = row.get('description', None) or self.description
		self.definer = row.get('definer', None)
		self.created = row.get('created', None)
		self._relation_schema = row['relationSchema']
		self._relation_name = row['relationName']

	def _get_fields(self):
		return self.relation.fields

	def _get_field_list(self):
		return self.relation.field_list
	
	def _get_create_sql(self):
		sql = Template('CREATE ALIAS $schema.$alias FOR $baseschema.$baserelation;')
		return sql.substitute({
			'schema': format_ident(self.schema.name),
			'alias': format_ident(self.name),
			'baseschema': format_ident(self.relation.schema.name),
			'baserelation': format_ident(self.relation.name)
		})
	
	def _get_drop_sql(self):
		sql = Template('DROP ALIAS $schema.$alias;')
		return sql.substitute({
			'schema': format_ident(self.schema.name),
			'alias': format_ident(self.name)
		})
	
	def _get_relation(self):
		"""Returns the relation the alias is for.

		This property returns the object representing the relation that
		is this alias is defined for.
		"""
		return self.database.schemas[self._relation_schema].relations[self._relation_name]
	
	relation = property(_get_relation)
