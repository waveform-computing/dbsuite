# $Header$
# vim: set noet sw=4 ts=4:

import logging
from db2makedoc.db.base import DocBase
from db2makedoc.db.schema import Schema
from db2makedoc.db.tablespace import Tablespace

class Database(DocBase):
	"""Class representing a DB2 database"""
	
	def __init__(self, input):
		"""Initializes an instance of the class"""
		super(Database, self).__init__(None, input.name)
		logging.debug("Building database")
		self.type_name = 'Database'
		self.tablespace_list = sorted([
			Tablespace(self, input, *item)
			for item in input.tablespaces
		], key=lambda item:item.name)
		self.tablespaces = dict([
			(tbspace.name, tbspace)
			for tbspace in self.tablespace_list
		])
		self.schema_list = sorted([
			Schema(self, input, *item)
			for item in input.schemas
		], key=lambda item:item.name)
		self.schemas = dict([
			(schema.name, schema)
			for schema in self.schema_list
		])

	def find(self, qualified_name):
		"""Find an object in the hierarchy by its qualified name.
		
		Because there are several namespaces in DB2, the results of such a
		search can only be unambiguous if an order of precedence for object
		types is established. The order of precedence used by this method is
		as follows:
		
		Schemas
		Tablespaces
			Tables,Views (one namespace)
				Fields
				Constraints
			Indexes
			Functions,Methods,Procedures (one namespace)
		
		Hence, if a schema shares a name with a tablespace, the schema will
		be returned in preference to the tablespace. Likewise, if an index
		shares a name with a table, the table will be returned in preference
		to the index.
		"""
		parts = qualified_name.split(".")
		if len(parts) == 1:
			return self.schemas.get(parts[0],
				self.tablespaces.get(parts[0],
				None))
		elif len(parts) == 2:
			schema = self.schemas[parts[0]]
			return schema.relations.get(parts[1],
				schema.indexes.get(parts[1],
				schema.routines.get(parts[1],
				None)))
		elif len(parts) == 3:
			relation = self.schemas[parts[0]].relations[parts[1]]
			return relation.fields.get(parts[2],
				relation.constraints.get(parts[2],
				None))
		else:
			return None

	def _get_identifier(self):
		return "db"
	
	def _get_database(self):
		return self
