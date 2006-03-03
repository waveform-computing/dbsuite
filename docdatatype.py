#!/bin/env python
# $Header$
# vim: set noet sw=4 ts=4:

import logging
from docschemabase import DocSchemaObject
from docutil import makeDateTime, makeBoolean

__all__ = ['DocDatatype']

class DocDatatype(DocSchemaObject):
	"""Class representing a datatype in a DB2 database"""
	
	def __init__(self, schema, cache, **row):
		"""Initializes an instance of the class from a cache row"""
		super(self.__class__, self).__init__(schema, row['name'])
		logging.info("Building datatype %s" % (self.qualifiedName))
		self.__definer = row['definer']
		self.__sourceSchema = row['sourceSchema']
		self.__sourceName = row['sourceName']
		self.__type = row['type']
		self.__systemType = row['systemType']
		self.__size = row['size']
		self.__scale = row['scale']
		self.__codepage = row['codepage']
		self.__created = row['created']
		self.__final = row['final']
		self.__description = row['description']

	def getTypeName(self):
		return "Data Type"
			
	def isSystemObject(self):
		return self.__systemType
	
	def getIdentifier(self):
		return "datatype_%s_%s" % (self.schema.name, self.name)
	
	def getDescription(self):
		if self.__description:
			return self.__description
		else:
			return super(self.__class__, self).getDescription()

	def __getDefiner(self):
		return self.__definer
	
	def __getSource(self):
		if self.__sourceName:
			return self.database.schemas[self.__sourceSchema].datatypes[self.__sourceName]
		else:
			return None
	
	def __getType(self):
		return self.__type
	
	def __getSize(self):
		return self.__size
	
	def __getScale(self):
		return self.__scale
	
	def __getCodepage(self):
		return self.__codepage
	
	def __getCreated(self):
		return self.__created
	
	def __getFinal(self):
		return self.__final
	
	def __getVariableSize(self):
		return self.__systemType and (self.__size is None) and (self.name != "REFERENCE")
	
	def __getVariableScale(self):
		return self.__systemType and (self.name == "DECIMAL")

	definer = property(__getDefiner, doc="""The user who created the index""")
	source = property(__getSource, doc="""The datatype upon which this type is based""")
	type = property(__getType, doc="""The type of this datatype (structured, distinct, or system)""")
	size = property(__getSize, doc="""The maximum size (or precision for numeric types) of the distinct type""")
	scale = property(__getScale, doc="""The maximum decimal scale of the distinct type""")
	codepage = property(__getCodepage, doc="""The codepage of the character-based distinct type""")
	created = property(__getCreated, doc="""Timestamp indicating when the index was created""")
	final = property(__getFinal, doc="""If True, then subtypes cannot be defined with this type as the ancestor""")
	variableSize = property(__getVariableSize, doc="""If True, then a size must/may be specified when using the datatype (e.g. CHAR, BLOB, DECIMAL)""")
	variableScale = property(__getVariableScale, doc="""If True, then a scale must/may be specified when using the datatype (e.g. DECIMAL, NUMERIC)""")
	
def main():
	pass

if __name__ == "__main__":
	main()
