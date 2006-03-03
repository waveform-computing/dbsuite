#!/bin/env python
# $Header$
# vim: set noet sw=4 ts=4:

import logging
from docbase import DocObjectBase
from docutil import makeBoolean

__all__ = ['DocParam']

class DocParam(DocObjectBase):
	"""Class representing a parameter in a routine in a DB2 database"""

	def __init__(self, routine, cache, **row):
		"""Initializes an instance of the class from a cache row"""
		super(DocParam, self).__init__(routine, row['name'])
		self.__position = row['position']
		logging.info("Building parameter %s" % (self.qualifiedName))
		self.__type = row['type']
		self.__datatypeSchema = row['datatypeSchema']
		self.__datatypeName = row['datatypeName']
		self.__locator = row['locator']
		self.__size = row['size']
		self.__scale = row['scale']
		self.__codepage = row['codepage']
		self.__description = row['description']

	def getName(self):
		result = super(DocParam, self).getName()
		if not result: result = str(self.__position)
		return result

	def getTypeName(self):
		return "Parameter"

	def getIdentifier(self):
		return "param_%s_%s_%d" % (self.schema.name, self.routine.specificName, self.position)

	def getDescription(self):
		if self.__description:
			return self.__description
		else:
			return super(self.__class__, self).getDescription()

	def __getPosition(self):
		return self.__position

	def __getRoutine(self):
		return self.parent

	def __getSchema(self):
		return self.parent.parent

	def __getDatabase(self):
		return self.parent.parent.parent

	def __getType(self):
		return self.__type

	def __getDatatype(self):
		return self.database.schemas[self.__datatypeSchema].datatypes[self.__datatypeName]

	def __getLocator(self):
		return self.__locator

	def __getSize(self):
		return self.__size

	def __getScale(self):
		return self.__scale

	def __getCodepage(self):
		return self.__codepage

	position = property(__getPosition, doc="""The 0-based position of the parameter in the function's prototype""")
	routine = property(__getRoutine, doc="""The routine that owns the parameter""")
	schema = property(__getSchema, doc="""The schema that contains the parameter""")
	database = property(__getDatabase, doc="""The database that contains the parameter""")
	type = property(__getType, doc="""The type of the parameter (input, output, inout, etc.)""")
	datatype = property(__getDatatype, doc="""The datatype of the parameter""")
	locator = property(__getLocator, doc="""True if the parameter or result is passed in the form of a locator""")
	size = property(__getSize, doc="""Maximum number of characters (for a character-based parameter) or maximum precision (for a numeric parameter)""")
	scale = property(__getScale, doc="""Maximum number of decimal places (for a numeric parameter)""")
	codepage = property(__getCodepage, doc="""Codepage of a character-based parameter""")

def main():
	pass

if __name__ == "__main__":
	main()
