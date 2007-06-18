# $Header$
# vim: set noet sw=4 ts=4:

import logging
from db2makedoc.db.schemabase import SchemaObject

class Datatype(SchemaObject):
	"""Class representing a datatype in a DB2 database"""
	
	def __init__(self, schema, input, *row):
		"""Initializes an instance of the class from a input row"""
		super(Datatype, self).__init__(schema, row[1])
		logging.debug("Building datatype %s" % (self.qualified_name))
		(
			_,
			_,
			self.owner,
			self._system,
			self.created,
			self._source_schema,
			self._source_name,
			self.size,
			self.scale,
			self.codepage,
			self.final,
			desc
		) = row
		self.type_name = 'Data Type'
		self.description = desc or self.description
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
