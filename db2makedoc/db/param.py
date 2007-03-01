# $Header$
# vim: set noet sw=4 ts=4:

# Standard modules
import logging

# Application-specific modules
from db.base import DocBase
from db.util import format_size, format_ident

class Param(DocBase):
	"""Class representing a parameter in a routine in a DB2 database"""

	def __init__(self, routine, input, **row):
		"""Initializes an instance of the class from a input row"""
		# If the parameter is unnamed, make up a name based on the parameter's
		# position
		if row.get('name', None):
			super(Param, self).__init__(routine, row['name'])
		else:
			super(Param, self).__init__(routine, 'P%d' % row['position'])
		logging.debug("Building parameter %s" % (self.qualified_name))
		self.type_name = 'Parameter'
		self.routine = self.parent
		self.schema = self.parent.parent
		self.description = row.get('description', None) or self.description
		self.locator = row.get('locator', False)
		self.codepage = row.get('codepage', None)
		self.size = row['size']
		self.scale = row['scale']
		self.position = row['position']
		self.type = row['type']
		self._datatype_schema = row['datatypeSchema']
		self._datatype_name = row['datatypeName']

	def _get_identifier(self):
		return "param_%s_%s_%d" % (self.schema.name, self.routine.specific_name, self.position)

	def _get_database(self):
		return self.parent.parent.parent

	def _get_datatype(self):
		"""Returns the object representing the parameter's datatype"""
		return self.database.schemas[self._datatype_schema].datatypes[self._datatype_name]

	def _get_datatype_str(self):
		"""Returns a string representation of the datatype of the parameter.

		This is a convenience property which returns the datatype of the
		parameter with all necessary arguments in parentheses. It is used in
		constructing the prototype of the field.
		"""
		if self.datatype.system:
			result = format_ident(self.datatype.name)
		else:
			result = '%s.%s' % (
				format_ident(self.datatype.schema.name),
				format_ident(self.datatype.name)
			)
		if self.datatype.variable_size and not self.size is None:
			result += '(%s' % (format_size(self.size))
			if self.datatype.variable_scale and not self.scale is None:
				result += ',%d' % (self.scale)
			result += ')'
		return result

	datatype = property(_get_datatype)
	datatype_str = property(_get_datatype_str)
