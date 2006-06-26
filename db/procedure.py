#!/bin/env python
# $Header$
# vim: set noet sw=4 ts=4:

import logging
from string import Template
from schemabase import Routine
from param import Param
from util import formatSize, formatIdentifier

class Procedure(Routine):
	"""Class representing a procedure in a DB2 database"""
	
	def __init__(self, schema, cache, **row):
		"""Initializes an instance of the class from a cache row"""
		super(Procedure, self).__init__(schema, row['name'], row['specificName'])
		logging.debug("Building procedure %s" % (self.qualifiedName))
		self.__definer = row['definer']
		self.__origin = row['origin']
		self.__language = row['language']
		self.__deterministic = row['deterministic']
		self.__externalAction = row['externalAction']
		self.__nullCall = row['nullCall']
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
		myparams = [
			cache.proc_params[(schemaName, specificName, paramType, paramPos)]
			for (schemaName, specificName, paramType, paramPos) in cache.proc_params
			if schemaName == schema.name and specificName == self.specificName
		]
		for row in myparams:
			param = Param(self, cache, **row)
			self.__params[param.name] = param
		self.__paramList = sorted(self.__params.itervalues(), key=lambda param:param.position)

	def getTypeName(self):
		return "Procedure"
			
	def getDescription(self):
		if self.__description:
			return self.__description
		else:
			return super(Procedure, self).getDescription()
	
	def getParentList(self):
		return self.schema.procedureList

	def getParams(self):
		return self.__params
	
	def getParamList(self):
		return self.__paramList

	def getPrototype(self):
		prefix = {'Input': 'IN', 'Output': 'OUT', 'In/Out': 'INOUT'}
		
		def formatParams(params):
			return ', '.join([
				'%s %s %s' % (prefix[param.type], param.name, param.datatypeStr)
				for param in params
			])

		return "%s(%s)" % (
			self.qualifiedName,
			formatParams(self.paramList)
		)
	
	def getCreateSql(self):
		if self.language == 'SQL':
			return self.sql + '!'
		else:
			raise NotImplementedError
	
	def getDropSql(self):
		sql = Template('DROP SPECIFIC PROCEDURE $schema.$specific;')
		return sql.substitute({
			'schema': formatIdentifier(self.schema.name),
			'specific': formatIdentifier(self.specificName)
		})

	def __getDefiner(self):
		return self.__definer

	def __getOrigin(self):
		return self.__origin
	
	def __getLanguage(self):
		return self.__language
	
	def __getDeterministic(self):
		return self.__deterministic
	
	def __getExternalAction(self):
		return self.__externalAction
	
	def __getNullCall(self):
		return self.__nullCall
	
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
	origin = property(__getOrigin, doc="""The origin of the procedure (external, built-in, user-defined, etc.)""")
	language = property(__getLanguage, doc="""The language the procedure is implemented in""")
	deterministic = property(__getDeterministic, doc="""True if the procedure always performs the same actions given the same inputs""")
	externalAction = property(__getExternalAction, doc="""True if the procedure alters some external state (in which case the number of invocations matters)""")
	nullCall = property(__getNullCall, doc="""If False, the procedure is called when one or more parameters is NULL""")
	fenced = property(__getFenced, doc="""True if the procedure is run in the fenced execution environment""")
	sqlAccess = property(__getSqlAccess, doc="""Indicates whether the procedure executes any SQL statements and, if so, whether they are read-only or read-write""")
	threadSafe = property(__getThreadSafe, doc="""True if the external procedure can be run in the same process space as other procedure invocations""")
	valid = property(__getValid, doc="""True if the procedure is valid. Otherwise the procedure is invalid or inoperative and must be recreated""")
	created = property(__getCreated, doc="""Timestamp indicating when the procedure was created""")
	qualifier = property(__getQualifier, doc="""The current schema at the time the procedure was created""")
	funcPath = property(__getFuncPath, doc="""The function resolution path at the time the procedure was created""")
	sql = property(__getSql, doc="""The complete SQL statement that created the procedure, if language is SQL""")
	
def main():
	pass

if __name__ == "__main__":
	main()
