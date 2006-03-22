#!/bin/env python
# $Header$
# vim: set noet sw=4 ts=4:

import logging
from docrelationbase import DocRelationObject
from docutil import makeDateTime, makeBoolean, formatSize

__all__ = ['DocField']

class DocField(DocRelationObject):
	"""Class representing a field in a relation in a DB2 database"""

	def __init__(self, relation, cache, **row):
		"""Initializes an instance of the class from a cache row"""
		super(DocField, self).__init__(relation, row['name'])
		logging.info("Building field %s" % (self.qualifiedName))
		self.__datatypeSchema = row['datatypeSchema']
		self.__datatypeName = row['datatypeName']
		self.__size = row['size']
		self.__scale = row['scale']
		self.__default = row['default']
		self.__nullable = row['nullable']
		self.__codepage = row['codepage']
		self.__logged = row['logged']
		self.__compact = row['compact']
		self.__cardinality = row['cardinality']
		self.__averageSize = row['averageSize']
		self.__position = row['position']
		self.__keyIndex = row['keyIndex']
		self.__nullCardinality = row['nullCardinality']
		self.__identity = row['identity']
		self.__generated = row['generated']
		self.__compressDefault = row['compressDefault']
		self.__generateExpression = row['generateExpression']
		self.__description = row['description']

	def getTypeName(self):
		return "Field"

	def getIdentifier(self):
		return "field_%s_%s_%s" % (self.schema.name, self.relation.name, self.name)

	def getDescription(self):
		if self.__description:
			return self.__description
		else:
			return super(DocField, self).getDescription()

	def __getDatatype(self):
		return self.database.schemas[self.__datatypeSchema].datatypes[self.__datatypeName]

	def __getDatatypeStr(self):
		if self.datatype.isSystemObject:
			result = self.datatype.name
		else:
			result = self.datatype.qualifiedName
		if self.datatype.variableSize:
			result += '(%s' % (formatSize(self.__size))
			if self.datatype.variableScale:
				result += ',%d' % (self.__scale)
			result += ')'
		return result

	def __getByteSize(self):
		return self.__size

	def __getSize(self):
		if self.datatype.variableSize:
			return self.__size
		else:
			return None

	def __getScale(self):
		if self.datatype.variableScale:
			return self.__scale
		else:
			return None

	def __getDefault(self):
		return self.__default

	def __getNullable(self):
		return self.__nullable

	def __getCodepage(self):
		return self.__codepage

	def __getLogged(self):
		return self.__logged

	def __getCompact(self):
		return self.__compact

	def __getCardinality(self):
		return self.__cardinality

	def __getNullCardinality(self):
		return self.__nullCardinality

	def __getAverageSize(self):
		return self.__averageSize

	def __getPosition(self):
		return self.__position

	def __getKeyIndex(self):
		return self.__keyIndex

	def __getKey(self):
		if self.__keyIndex:
			return self.relation.primaryKey
		else:
			return None

	def __getIdentity(self):
		return self.__identity

	def __getGenerated(self):
		return self.__generated

	def __getGenerateExpression(self):
		return self.__generateExpression

	def __getCompressDefault(self):
		return self.__compressDefault

	datatype = property(__getDatatype, doc="""The datatype of the field""")
	datatypeStr = property(__getDatatypeStr, doc="""The datatype of the field formatted as a string for display""")
	byteSize = property(__getByteSize, doc="""The (maximum) number of bytes that the field occupies on disk""")
	size = property(__getSize, doc="""The maximum number of characters in a character-based field, or the maximum precision for numeric fields""")
	scale = property(__getScale, doc="""The number of places to the right of the decimal point in numeric fields""")
	default = property(__getDefault, doc="""The default value for the field""")
	nullable = property(__getNullable, doc="""True if the field can contain the NULL value""")
	codepage = property(__getCodepage, doc="""The codepage for character-based fields""")
	logged = property(__getLogged, doc="""Indicates whether LOB-based fields are transaction logged""")
	compact = property(__getCompact, doc="""Indicates whether LOB-based fields use compacted storage""")
	cardinality = property(__getCardinality, doc="""The number of distinct values in the field""")
	nullCardinality = property(__getNullCardinality, doc="""The number of NULL values in the field""")
	averageSize = property(__getAverageSize, doc="""The average number of characters in a character-based field""")
	position = property(__getPosition, doc="""The position of the field in the table (0-based)""")
	keyIndex = property(__getKeyIndex, doc="""The position of the field in the primary key of the table""")
	key = property(__getKey, doc="""The primary key in which the field exists (or None if it is not a key field)""")
	identity = property(__getIdentity, doc="""True if the field is defined as an IDENTITY field""")
	generated = property(__getGenerated, doc="""Indicates whether/when the field is generated""")
	generateExpression = property(__getGenerateExpression, doc="""If the field is generated, holds the expression used to generate the field's value""")
	compressDefault = property(__getCompressDefault, doc="""Indicates whether the field uses a compressed format for default values""")

def main():
	pass

if __name__ == "__main__":
	main()
