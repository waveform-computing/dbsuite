#!/bin/env python
# $Header$
# vim: set noet sw=4 ts=4:

import logging
from docschemabase import DocRoutine
from docparam import DocParam
from docutil import makeDateTime, makeBoolean

__all__ = ['DocFunction']

class DocFunction(DocRoutine):
	"""Class representing a function in a DB2 database"""
	
	def __init__(self, schema, cache, **row):
		"""Initializes an instance of the class from a cache row"""
		super(DocFunction, self).__init__(schema, row['name'], row['specificName'])
		logging.debug("Building function %s" % (self.qualifiedName))
		self.__definer = row['definer']
		self.__rtypeSchema = row['rtypeSchema']
		self.__rtypeName = row['rtypeName']
		self.__origin = row['origin']
		self.__type = row['type']
		self.__language = row['language']
		self.__deterministic = row['deterministic']
		self.__externalAction = row['externalAction']
		self.__nullCall = row['nullCall']
		self.__castFunction = row['castFunction']
		self.__assignFunction = row['assignFunction']
		self.__parallel = row['parallel']
		self.__fenced = row['fenced']
		self.__sqlAccess = row['sqlAccess']
		self.__threadSafe = row['threadSafe']
		self.__valid = row['valid']
		self.__created = row['created']
		self.__qualifier = row['qualifier']
		self.__funcPath = row['funcPath']
		self.__sql = row['sql']
		self.__description = row['description']
		self.__params = {}
		for param in [cache.parameters[(schemaName, specificName, paramPos)] for (schemaName, specificName, paramPos) in cache.parameters if schemaName == schema.name and specificName == self.specificName]:
			self.__params[param['name']] = DocParam(self, cache, **param)
		self.__paramList = [x for x in self.__params.itervalues()]
		self.__paramList.sort(key=lambda param:param.position)

	def getTypeName(self):
		return "Function"
			
	def getIdentifier(self):
		return "func_%s_%s" % (self.schema.name, self.specificName)

	def getDescription(self):
		if self.__description:
			return self.__description
		else:
			return super(DocFunction, self).getDescription()

	def getParams(self):
		return self.__params
	
	def getParamList(self):
		return self.__paramList
	
	def __getDefiner(self):
		return self.__definer

	def __getReturnType(self):
		return self.database.schemas[self.__rtypeSchema].datatypes[self.__rtypeName]
	
	def __getOrigin(self):
		return self.__origin
	
	def __getType(self):
		return self.__type
	
	def __getLanguage(self):
		return self.__language
	
	def __getDeterministic(self):
		return self.__deterministic
	
	def __getExternalAction(self):
		return self.__externalAction
	
	def __getNullCall(self):
		return self.__nullCall
	
	def __getCastFunction(self):
		return self.__castFunction
	
	def __getAssignFunction(self):
		return self.__assignFunction
	
	def __getParallel(self):
		return self.__parallel
	
	def __getFenced(self):
		return self.__fenced
	
	def __getSqlAccess(self):
		return self.__sqlAccess
	
	def __getThreadSafe(self):
		return self.__threadSafe
	
	def __getValid(self):
		return self.__valid

	def __getCreated(self):
		return self.__created

	def __getQualifier(self):
		return self.__qualifier
	
	def __getFuncPath(self):
		return self.__funcPath
	
	def __getSql(self):
		return self.__sql
	
	definer = property(__getDefiner, doc="""The user who created the index""")
	returnType = property(__getReturnType, doc="""The return type of the function""")
	origin = property(__getOrigin, doc="""The origin of the function (external, built-in, user-defined, etc.)""")
	type = property(__getType, doc="""The sort of structure the function returns (row, table, scalar, etc.)""")
	language = property(__getLanguage, doc="""The language the function is implemented in""")
	deterministic = property(__getDeterministic, doc="""True if the function always returns the same result given the same inputs""")
	externalAction = property(__getExternalAction, doc="""True if the function alters some external state (in which case the number of invocations matters)""")
	nullCall = property(__getNullCall, doc="""If False, the function is assumed to return NULL with any NULL parameters""")
	castFunction = property(__getCastFunction, doc="""True if the function is a CAST() function""")
	assignFunction = property(__getAssignFunction, doc="""True if the function is an implicit assignment function""")
	parallel = property(__getParallel, doc="""True if the external function can be executed in multiple parallel invocations""")
	fenced = property(__getFenced, doc="""True if the function is run in the fenced function environment""")
	sqlAccess = property(__getSqlAccess, doc="""Indicates whether the function executes any SQL statements and, if so, whether they are read-only or read-write""")
	threadSafe = property(__getThreadSafe, doc="""True if the external function can be run in the same process space as other function invocations""")
	valid = property(__getValid, doc="""True if the function is valid. Otherwise the function is invalid or inoperative and must be recreated""")
	created = property(__getCreated, doc="""Timestamp indicating when the index was created""")
	qualifier = property(__getQualifier, doc="""The current schema at the time the function was created""")
	funcPath = property(__getFuncPath, doc="""The function resolution path at the time the function was created""")
	sql = property(__getSql, doc="""The complete SQL statement that created the function""")
	
def main():
	pass

if __name__ == "__main__":
	main()
