# $Header$
# vim: set noet sw=4 ts=4:

# Standard modules
import logging

# Application-specific modules
from db.schemabase import SchemaObject

class Datatype(SchemaObject):
	"""Class representing a datatype in a DB2 database"""
	
	def __init__(self, schema, input, **row):
		"""Initializes an instance of the class from a input row"""
		super(Datatype, self).__init__(schema, row['name'])
		logging.debug("Building datatype %s" % (self.qualified_name))
		self.type_name = 'Data Type'
		self.description = row.get('description', None) or self.description
		self.definer = row.get('definer', None)
		self.codepage = row.get('codepage', None)
		self.created = row.get('created', None)
		self.final = row.get('final', None)
		self.type = row['type']
		self.size = row['size']
		self.scale = row['scale']
		self._system = (self.type == 'SYSTEM')
		self._source_schema = row['sourceSchema']
		self._source_name = row['sourceName']
		# XXX DB2 specific
		self.variable_size = self._system and (self.size is None) and (self.name != "REFERENCE")
		self.variable_scale = self._system and (self.name == "DECIMAL")

	def _get_identifier(self):
		return "datatype_%s_%s" % (self.schema.name, self.name)
	
	def _get_source(self):
		"""Returns the datatype on which this type is based.

		If this datatype is based on another type this property returns the
		object representing the base datatype.
		"""
		if self._source_name:
			return self.database.schemas[self._source_schema].datatypes[self._source_name]
		else:
			return None
	
	source = property(_get_source)
