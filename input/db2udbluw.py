#!/bin/env python
# $Header$
# vim: set noet sw=4 ts=4:

"""Input class for IBM DB2 UDB for Linux/UNIX/Windows.

This input class supports extracting documentation information from IBM DB2
UDB for Linux/UNIX/Windows version 8 or above. If the DOCCAT schema (see the
doccat_create.sql script in the contrib/db2udbluw directory) is present, it
will be used to source documentation data instead of SYSCAT.
"""

import logging
from util import makeDateTime, makeBoolean

def _fetch_dict(cursor):
	"""Returns rows from a cursor as a list of dictionaries.

	Specifically, the result set is returned as a list of dictionaries, where
	each dictionary represents one row of the result set, and is keyed by the
	field names of the result set converted to lower case.
	"""
	return [dict(zip([d[0] for d in cursor.description], row)) for row in cursor.fetchall()]

class Cache(object):
	def __init__(self, connection):
		super(Cache, self).__init__()
		logging.info("Initializing DB2 UDB for LUW input module")
		# Get a cursor to run the queries
		cursor = connection.cursor()
		try:
			# Test whether the DOCCAT extension is installed
			cursor.execute("""SELECT COUNT(*)
				FROM SYSCAT.SCHEMATA
				WHERE SCHEMANAME = 'DOCCAT'
				WITH UR""")
			doccat = bool(cursor.fetchall()[0][0])
			if doccat:
				logging.info("DOCCAT schema found, using DOCCAT instead of SYSCAT")
			else:
				logging.info("DOCCAT schema not found, using SYSCAT instead")
		finally:
			del cursor
		# Run all the queries, using DOCCAT extensions if available
		self._get_schemas(connection, doccat)
		self._get_datatypes(connection, doccat)
		self._get_tables(connection, doccat)
		self._get_views(connection, doccat)
		self._get_aliases(connection, doccat)
		self._get_dependencies(connection, doccat)
		self._get_indexes(connection, doccat)
		self._get_index_fields(connection, doccat)
		self._get_table_indexes(connection, doccat)
		self._get_fields(connection, doccat)
		self._get_unique_keys(connection, doccat)
		self._get_unique_key_fields(connection, doccat)
		self._get_foreign_keys(connection, doccat)
		self._get_foreign_key_fields(connection, doccat)
		self._get_checks(connection, doccat)
		self._get_check_fields(connection, doccat)
		self._get_functions(connection, doccat)
		self._get_function_params(connection, doccat)
		self._get_tablespaces(connection, doccat)
		self._get_tablespace_tables(connection, doccat)
		self._get_tablespace_indexes(connection, doccat)

	def _get_schemas(self, connection, doccat):
		logging.debug("Retrieving schemas")
		cursor = connection.cursor()
		try:
			cursor.execute("""
				SELECT
					RTRIM(SCHEMANAME) AS "name",
					RTRIM(OWNER)      AS "owner",
					RTRIM(DEFINER)    AS "definer",
					CHAR(CREATE_TIME) AS "created",
					REMARKS           AS "description"
				FROM %(schema)s.SCHEMATA
				WITH UR""" % {'schema': ['SYSCAT', 'DOCCAT'][doccat]})
			self.schemas = dict([(row['name'], row) for row in _fetch_dict(cursor)])
		finally:
			del cursor
		for row in self.schemas.itervalues():
			row['created'] = makeDateTime(row['created'])

	def _get_datatypes(self, connection, doccat):
		logging.debug("Retrieving datatypes")
		cursor = connection.cursor()
		try:
			cursor.execute("""
				SELECT
					RTRIM(TYPESCHEMA)   AS "schemaName",
					RTRIM(TYPENAME)     AS "name",
					RTRIM(DEFINER)      AS "definer",
					RTRIM(SOURCESCHEMA) AS "sourceSchema",
					RTRIM(SOURCENAME)   AS "sourceName",
					METATYPE            AS "type",
					LENGTH              AS "size",
					SCALE               AS "scale",
					CODEPAGE            AS "codepage",
					CHAR(CREATE_TIME)   AS "created",
					FINAL               AS "final",
					REMARKS             AS "description"
				FROM %(schema)s.DATATYPES
				WHERE INSTANTIABLE = 'Y'
				WITH UR""" % {'schema': ['SYSCAT', 'DOCCAT'][doccat]})
			self.datatypes = dict([((row['schemaName'], row['name']), row) for row in _fetch_dict(cursor)])
		finally:
			del cursor
		for row in self.datatypes.itervalues():
			row['created'] = makeDateTime(row['created'])
			row['final'] = makeBoolean(row['final'])
			row['systemType'] = makeBoolean(row['type'], 'S')
			if not row['size']: row['size'] = None
			if not row['scale']: row['scale'] = None # XXX Not necessarily unknown (0 is a valid scale)
			if not row['codepage']: row['codepage'] = None
			row['type'] = {
				'S': 'System',
				'T': 'Distinct',
				'R': 'Structured'
			}[row['type']]

	def _get_tables(self, connection, doccat):
		logging.debug("Retrieving tables")
		cursor = connection.cursor()
		try:
			cursor.execute("""
				SELECT
					RTRIM(TABSCHEMA)     AS "schemaName",
					RTRIM(TABNAME)       AS "name",
					RTRIM(DEFINER)       AS "definer",
					STATUS               AS "checkPending",
					CHAR(CREATE_TIME)    AS "created",
					CHAR(STATS_TIME)     AS "statsUpdated",
					NULLIF(CARD, -1)     AS "cardinality",
					NULLIF(NPAGES, -1)   AS "rowPages",
					NULLIF(FPAGES, -1)   AS "totalPages",
					NULLIF(OVERFLOW, -1) AS "overflow",
					RTRIM(TBSPACE)       AS "dataTbspace",
					RTRIM(INDEX_TBSPACE) AS "indexTbspace",
					RTRIM(LONG_TBSPACE)  AS "longTbspace",
					APPEND_MODE          AS "append",
					LOCKSIZE             AS "lockSize",
					VOLATILE             AS "volatile",
					COMPRESSION          AS "compression",
					ACCESS_MODE          AS "accessMode",
					CLUSTERED            AS "clustered",
					ACTIVE_BLOCKS        AS "activeBlocks",
					REMARKS              AS "description"
				FROM %(schema)s.TABLES
				WHERE TYPE = 'T'
				WITH UR""" % {'schema': ['SYSCAT', 'DOCCAT'][doccat]})
			self.tables = dict([((row['schemaName'], row['name']), row) for row in _fetch_dict(cursor)])
		finally:
			del cursor
		for row in self.tables.itervalues():
			row['created'] = makeDateTime(row['created'])
			row['statsUpdated'] = makeDateTime(row['statsUpdated'])
			row['checkPending'] = makeBoolean(row['checkPending'], 'C')
			row['append'] = makeBoolean(row['append'])
			row['volatile'] = makeBoolean(row['volatile'], 'C', ' ', None)
			row['compression'] = makeBoolean(row['compression'], 'V')
			row['clustered'] = makeBoolean(row['clustered'])
			row['lockSize'] = {
				'T': 'Table',
				'R': 'Row'
			}[row['lockSize']]
			row['accessMode'] = {
				'N': 'No Access',
				'R': 'Read Only',
				'D': 'No Data Movement',
				'F': 'Full Access'
			}[row['accessMode']]

	def _get_views(self, connection, doccat):
		logging.debug("Retrieving views")
		cursor = connection.cursor()
		try:
			cursor.execute("""
				SELECT
					RTRIM(T.TABSCHEMA)    AS "schemaName",
					RTRIM(T.TABNAME)      AS "name",
					RTRIM(V.DEFINER)      AS "definer",
					CHAR(T.CREATE_TIME)   AS "created",
					V.VIEWCHECK           AS "check",
					V.READONLY            AS "readOnly",
					V.VALID               AS "valid",
					RTRIM(V.QUALIFIER)    AS "qualifier",
					RTRIM(V.FUNC_PATH)    AS "funcPath",
					V.TEXT                AS "sql",
					T.REMARKS             AS "description"
				FROM
					%(schema)s.TABLES T
					INNER JOIN %(schema)s.VIEWS V
					ON T.TABSCHEMA = V.VIEWSCHEMA
					AND T.TABNAME = V.VIEWNAME
					AND T.TYPE = 'V'
				WITH UR""" % {'schema': ['SYSCAT', 'DOCCAT'][doccat]})
			self.views = dict([((row['schemaName'], row['name']), row) for row in _fetch_dict(cursor)])
		finally:
			del cursor
		for row in self.views.itervalues():
			row['created'] = makeDateTime(row['created'])
			row['readOnly'] = makeBoolean(row['readOnly'])
			row['valid'] = makeBoolean(row['valid'])
			row['check'] = {
				'N': 'No Check',
				'L': 'Local Check',
				'C': 'Cascaded Check'
			}[row['check']]
			row['sql'] = str(row['sql'])

	def _get_aliases(self, connection, doccat):
		# XXX Query aliases
		logging.debug("Retrieving aliases")
		#cursor = connection.cursor()
		self.aliases = {}

	def _get_dependencies(self, connection, doccat):
		logging.debug("Retrieving relation dependencies")
		cursor = connection.cursor()
		try:
			cursor.execute("""
				SELECT
					RTRIM(BSCHEMA)    AS "relationSchema",
					RTRIM(BNAME)      AS "relationName",
					RTRIM(TABSCHEMA)  AS "depSchema",
					RTRIM(TABNAME)    AS "depName"
				FROM %(schema)s.TABDEP
				WHERE BTYPE IN ('A', 'S', 'T', 'U', 'V', 'W')
				WITH UR""" % {'schema': ['SYSCAT', 'DOCCAT'][doccat]})
			self.dependents = {}
			self.dependencies = {}
			for (relationSchema, relationName, depSchema, depName) in cursor.fetchall():
				if not (relationSchema, relationName) in self.dependents:
					self.dependents[(relationSchema, relationName)] = []
				self.dependents[(relationSchema, relationName)].append((depSchema, depName))
				if not (depSchema, depName) in self.dependencies:
					self.dependencies[(depSchema, depName)] = []
				self.dependencies[(depSchema, depName)].append((relationSchema, relationName))
		finally:
			del cursor

	def _get_indexes(self, connection, doccat):
		logging.debug("Retrieving indexes")
		cursor = connection.cursor()
		try:
			cursor.execute("""
				SELECT
					RTRIM(I.INDSCHEMA)             AS "schemaName",
					RTRIM(I.INDNAME)               AS "name",
					RTRIM(I.DEFINER)               AS "definer",
					RTRIM(I.TABSCHEMA)             AS "tableSchema",
					RTRIM(I.TABNAME)               AS "tableName",
					I.UNIQUERULE                   AS "unique",
					RTRIM(I.INDEXTYPE)             AS "type",
					NULLIF(I.NLEAF, -1)            AS "leafPages",
					NULLIF(I.NLEVELS, -1)          AS "levels",
					NULLIF(I.FIRSTKEYCARD, -1)     AS "cardinality1",
					NULLIF(I.FIRST2KEYCARD, -1)    AS "cardinality2",
					NULLIF(I.FIRST3KEYCARD, -1)    AS "cardinality3",
					NULLIF(I.FIRST4KEYCARD, -1)    AS "cardinality4",
					NULLIF(I.FULLKEYCARD, -1)      AS "cardinality",
					NULLIF(I.CLUSTERRATIO, -1)     AS "clusterRatio",
					NULLIF(I.CLUSTERFACTOR, -1.0)  AS "clusterFactor",
					NULLIF(I.SEQUENTIAL_PAGES, -1) AS "sequentialPages",
					NULLIF(I.DENSITY, -1)          AS "density",
					I.USER_DEFINED                 AS "userDefined",
					I.SYSTEM_REQUIRED              AS "required",
					CHAR(I.CREATE_TIME)            AS "created",
					CHAR(I.STATS_TIME)             AS "statsUpdated",
					I.REVERSE_SCANS                AS "reverseScans",
					I.REMARKS                      AS "description",
					RTRIM(T.TBSPACE)               AS "tablespaceName"
				FROM
					%(schema)s.INDEXES I
					INNER JOIN %(schema)s.TABLESPACES T
					ON I.TBSPACEID = T.TBSPACEID
				WITH UR""" % {'schema': ['SYSCAT', 'DOCCAT'][doccat]})
			self.indexes = dict([((row['schemaName'], row['name']), row) for row in _fetch_dict(cursor)])
		finally:
			del cursor
		for row in self.indexes.itervalues():
			row['created'] = makeDateTime(row['created'])
			row['statsUpdated'] = makeDateTime(row['statsUpdated'])
			row['reverseScans'] = makeBoolean(row['reverseScans'])
			row['unique'] = row['unique'] != 'D'
			row['userDefined'] = row['userDefined'] != 0
			row['required'] = row['required'] != 0
			row['type'] = {
				'CLUS': 'Clustering',
				'REG': 'Regular',
				'DIM': 'Dimension Block',
				'BLOK': 'Block'
			}[row['type']]

	def _get_index_fields(self, connection, doccat):
		logging.debug("Retrieving index fields")
		cursor = connection.cursor()
		try:
			cursor.execute("""
				SELECT
					RTRIM(INDSCHEMA) AS "indexSchema",
					RTRIM(INDNAME)   AS "indexName",
					RTRIM(COLNAME)   AS "fieldName",
					COLORDER         AS "order"
				FROM %(schema)s.INDEXCOLUSE
				ORDER BY
					INDSCHEMA,
					INDNAME,
					COLSEQ
				WITH UR""" % {'schema': ['SYSCAT', 'DOCCAT'][doccat]})
			self.indexFields = {}
			for (indexSchema, indexName, fieldName, order) in cursor.fetchall():
				if not (indexSchema, indexName) in self.indexFields:
					self.indexFields[(indexSchema, indexName)] = []
				order = {'A': 'Ascending', 'D': 'Descending', 'I': 'Include'}[order]
				self.indexFields[(indexSchema, indexName)].append((fieldName, order))
		finally:
			del cursor

	def _get_table_indexes(self, connection, doccat):
		logging.debug("Retrieving table indexes")
		cursor = connection.cursor()
		try:
			cursor.execute("""
				SELECT
					RTRIM(TABSCHEMA) AS "tableSchema",
					RTRIM(TABNAME)   AS "tableName",
					RTRIM(INDSCHEMA) AS "indexSchema",
					RTRIM(INDNAME)   AS "indexName"
				FROM
					%(schema)s.INDEXES
				WITH UR""" % {'schema': ['SYSCAT', 'DOCCAT'][doccat]})
			self.tableIndexes = {}
			for (tableSchema, tableName, indexSchema, indexName) in cursor.fetchall():
				if not (tableSchema, tableName) in self.tableIndexes:
					self.tableIndexes[(tableSchema, tableName)] = []
				self.tableIndexes[(tableSchema, tableName)].append((indexSchema, indexName))
		finally:
			del cursor

	def _get_fields(self, connection, doccat):
		logging.debug("Retrieving fields")
		cursor = connection.cursor()
		try:
			cursor.execute("""
				SELECT
					RTRIM(TABSCHEMA)  AS "schemaName",
					RTRIM(TABNAME)    AS "tableName",
					RTRIM(COLNAME)    AS "name",
					RTRIM(TYPESCHEMA) AS "datatypeSchema",
					RTRIM(TYPENAME)   AS "datatypeName",
					LENGTH            AS "size",
					SCALE             AS "scale",
					RTRIM(DEFAULT)    AS "default",
					NULLS             AS "nullable",
					CODEPAGE          AS "codepage",
					LOGGED            AS "logged",
					COMPACT           AS "compact",
					COLCARD           AS "cardinality",
					AVGCOLLEN         AS "averageSize",
					COLNO             AS "position",
					KEYSEQ            AS "keyIndex",
					NUMNULLS          AS "nullCardinality",
					IDENTITY          AS "identity",
					GENERATED         AS "generated",
					COMPRESS          AS "compressDefault",
					RTRIM(TEXT)       AS "generateExpression",
					REMARKS           AS "description"
				FROM %(schema)s.COLUMNS
				WHERE HIDDEN <> 'S'
				WITH UR""" % {'schema': ['SYSCAT', 'DOCCAT'][doccat]})
			self.fields = dict([((row['schemaName'], row['tableName'], row['name']), row) for row in _fetch_dict(cursor)])
		finally:
			del cursor
		for row in self.fields.itervalues():
			if row['cardinality'] < 0: row['cardinality'] = None
			if row['averageSize'] < 0: row['averageSize'] = None
			if row['nullCardinality'] < 0: row['nullCardinality'] = None
			if not row['codepage']: row['codepage'] = None
			row['logged'] = makeBoolean(row['logged'])
			row['compact'] = makeBoolean(row['compact'])
			row['nullable'] = makeBoolean(row['nullable'])
			row['identity'] = makeBoolean(row['identity'])
			row['compressDefault'] = makeBoolean(row['compressDefault'], 'S')
			row['generated'] = {
				'D': 'By Default',
				'A': 'Always',
				' ': 'Never'
			}[row['generated']]
			row['generateExpression'] = str(row['generateExpression'])

	def _get_unique_keys(self, connection, doccat):
		logging.debug("Retrieving unique keys")
		cursor = connection.cursor()
		try:
			cursor.execute("""
				SELECT
					RTRIM(TABSCHEMA)  AS "schemaName",
					RTRIM(TABNAME)    AS "tableName",
					RTRIM(CONSTNAME)  AS "name",
					TYPE              AS "type",
					RTRIM(DEFINER)    AS "definer",
					CHECKEXISTINGDATA AS "checkExisting",
					REMARKS           AS "description"
				FROM %(schema)s.TABCONST
				WHERE TYPE IN ('U', 'P')
				WITH UR""" % {'schema': ['SYSCAT', 'DOCCAT'][doccat]})
			self.uniqueKeys = dict([((row['schemaName'], row['tableName'], row['name']), row) for row in _fetch_dict(cursor)])
		finally:
			del cursor
		for row in self.uniqueKeys.itervalues():
			row['checkExisting'] = {
				'D': 'Defer',
				'I': 'Immediate',
				'N': 'No check'
			}[row['checkExisting']]

	def _get_unique_key_fields(self, connection, doccat):
		logging.debug("Retrieving unique key fields")
		cursor = connection.cursor()
		try:
			cursor.execute("""
				SELECT
					RTRIM(TABSCHEMA) AS "keySchema",
					RTRIM(TABNAME)   AS "keyTable",
					RTRIM(CONSTNAME) AS "keyName",
					RTRIM(COLNAME)   AS "fieldName"
				FROM %(schema)s.KEYCOLUSE
				ORDER BY
					TABSCHEMA,
					TABNAME,
					CONSTNAME,
					COLSEQ
				WITH UR""" % {'schema': ['SYSCAT', 'DOCCAT'][doccat]})
			self.uniqueKeyFields = {}
			for (keySchema, keyTable, keyName, fieldName) in cursor.fetchall():
				if not (keySchema, keyTable, keyName) in self.uniqueKeyFields:
					self.uniqueKeyFields[(keySchema, keyTable, keyName)] = []
				self.uniqueKeyFields[(keySchema, keyTable, keyName)].append(fieldName)
		finally:
			del cursor

	def _get_foreign_keys(self, connection, doccat):
		logging.debug("Retrieving foreign keys")
		cursor = connection.cursor()
		try:
			cursor.execute("""
				SELECT
					RTRIM(T.TABSCHEMA)    AS "schemaName",
					RTRIM(T.TABNAME)      AS "tableName",
					RTRIM(T.CONSTNAME)    AS "name",
					RTRIM(R.REFTABSCHEMA) AS "refTableSchema",
					RTRIM(R.REFTABNAME)   AS "refTableName",
					RTRIM(R.REFKEYNAME)   AS "refKeyName",
					R.CREATE_TIME         AS "created",
					RTRIM(T.DEFINER)      AS "definer",
					T.ENFORCED            AS "enforced",
					T.CHECKEXISTINGDATA   AS "checkExisting",
					T.ENABLEQUERYOPT      AS "queryOptimize",
					R.DELETERULE          AS "deleteRule",
					R.UPDATERULE          AS "updateRule",
					T.REMARKS             AS "description"
				FROM
					%(schema)s.TABCONST T
					INNER JOIN %(schema)s.REFERENCES R
					ON T.TABSCHEMA = R.TABSCHEMA
					AND T.TABNAME = R.TABNAME
					AND T.CONSTNAME = R.CONSTNAME
					AND T.TYPE = 'F'
				WITH UR""" % {'schema': ['SYSCAT', 'DOCCAT'][doccat]})
			self.foreignKeys = dict([((row['schemaName'], row['tableName'], row['name']), row) for row in _fetch_dict(cursor)])
		finally:
			del cursor
		for row in self.foreignKeys.itervalues():
			row['created'] = makeDateTime(row['created'])
			row['enforced'] = makeBoolean(row['enforced'])
			row['queryOptimize'] = makeBoolean(row['queryOptimize'])
			row['checkExisting'] = {
				'D': 'Defer',
				'I': 'Immediate',
				'N': 'No check'
			}[row['checkExisting']]
			row['deleteRule'] = {
				'A': 'No Action',
				'R': 'Restrict',
				'C': 'Cascade',
				'N': 'Set NULL'
			}[row['deleteRule']]
			row['updateRule'] = {
				'A': 'No Action',
				'R': 'Restrict'
			}[row['updateRule']]

	def _get_foreign_key_fields(self, connection, doccat):
		logging.debug("Retrieving foreign key fields")
		cursor = connection.cursor()
		try:
			cursor.execute("""
				SELECT
					RTRIM(R.TABSCHEMA) AS "keySchema",
					RTRIM(R.TABNAME)   AS "keyTable",
					RTRIM(R.CONSTNAME) AS "keyName",
					RTRIM(KF.COLNAME)  AS "foreignFieldName",
					RTRIM(KP.COLNAME)  AS "parentFieldName"
				FROM
					%(schema)s.REFERENCES R
					INNER JOIN %(schema)s.KEYCOLUSE KF
						ON R.TABSCHEMA = KF.TABSCHEMA
						AND R.TABNAME = KF.TABNAME
						AND R.CONSTNAME = KF.CONSTNAME
					INNER JOIN %(schema)s.KEYCOLUSE KP
						ON R.REFTABSCHEMA = KP.TABSCHEMA
						AND R.REFTABNAME = KP.TABNAME
						AND R.REFKEYNAME = KP.CONSTNAME
				WHERE KF.COLSEQ = KP.COLSEQ
				ORDER BY
					R.TABSCHEMA,
					R.TABNAME,
					R.CONSTNAME,
					KF.COLSEQ
				WITH UR""" % {'schema': ['SYSCAT', 'DOCCAT'][doccat]})
			self.foreignKeyFields = {}
			for (keySchema, keyTable, keyName, foreignFieldName, parentFieldName) in cursor.fetchall():
				if not (keySchema, keyTable, keyName) in self.foreignKeyFields:
					self.foreignKeyFields[(keySchema, keyTable, keyName)] = []
				self.foreignKeyFields[(keySchema, keyTable, keyName)].append((foreignFieldName, parentFieldName))
		finally:
			del cursor

	def _get_checks(self, connection, doccat):
		logging.debug("Retrieving check constraints")
		cursor = connection.cursor()
		try:
			cursor.execute("""
				SELECT
					RTRIM(T.TABSCHEMA)    AS "schemaName",
					RTRIM(T.TABNAME)      AS "tableName",
					RTRIM(T.CONSTNAME)    AS "name",
					C.CREATE_TIME         AS "created",
					RTRIM(T.DEFINER)      AS "definer",
					T.ENFORCED            AS "enforced",
					T.CHECKEXISTINGDATA   AS "checkExisting",
					T.ENABLEQUERYOPT      AS "queryOptimize",
					C.TYPE                AS "type",
					RTRIM(C.QUALIFIER)    AS "qualifier",
					RTRIM(C.FUNC_PATH)    AS "funcPath",
					C.TEXT                AS "expression",
					T.REMARKS             AS "description"
				FROM
					%(schema)s.TABCONST T
					INNER JOIN %(schema)s.CHECKS C
					ON T.TABSCHEMA = C.TABSCHEMA
					AND T.TABNAME = C.TABNAME
					AND T.CONSTNAME = C.CONSTNAME
					AND T.TYPE = 'K'
				WITH UR""" % {'schema': ['SYSCAT', 'DOCCAT'][doccat]})
			self.checks = dict([((row['schemaName'], row['tableName'], row['name']), row) for row in _fetch_dict(cursor)])
		finally:
			del cursor
		for row in self.checks.itervalues():
			row['created'] = makeDateTime(row['created'])
			row['enforced'] = makeBoolean(row['enforced'])
			row['queryOptimize'] = makeBoolean(row['queryOptimize'])
			row['checkExisting'] = {
				'D': 'Defer',
				'I': 'Immediate',
				'N': 'No check'
			}[row['checkExisting']]
			row['type'] = {
				'A': 'System Generated', # InfoCenter reckons it's 'A'
				'S': 'System Generated', # However, it appears to be 'S'
				'C': 'Check',
				'F': 'Functional Dependency',
				'O': 'Object Property'
			}[row['type']]
			row['expression'] = str(row['expression'])

	def _get_check_fields(self, connection, doccat):
		logging.debug("Retrieving check fields")
		cursor = connection.cursor()
		try:
			cursor.execute("""
				SELECT
					RTRIM(TABSCHEMA) AS "keySchema",
					RTRIM(TABNAME)   AS "keyTable",
					RTRIM(CONSTNAME) AS "keyName",
					RTRIM(COLNAME)   AS "fieldName"
				FROM %(schema)s.COLCHECKS
				WITH UR""" % {'schema': ['SYSCAT', 'DOCCAT'][doccat]})
			self.checkFields = {}
			for (keySchema, keyTable, keyName, fieldName) in cursor.fetchall():
				if not (keySchema, keyTable, keyName) in self.checkFields:
					self.checkFields[(keySchema, keyTable, keyName)] = []
				self.checkFields[(keySchema, keyTable, keyName)].append(fieldName)
		finally:
			del cursor

	def _get_functions(self, connection, doccat):
		logging.debug("Retrieving functions")
		cursor = connection.cursor()
		try:
			cursor.execute("""
				SELECT
					RTRIM(ROUTINESCHEMA)     AS "schemaName",
					RTRIM(SPECIFICNAME)      AS "specificName",
					RTRIM(ROUTINENAME)       AS "name",
					RTRIM(DEFINER)           AS "definer",
					RTRIM(RETURN_TYPESCHEMA) AS "rtypeSchema",
					RTRIM(RETURN_TYPENAME)   AS "rtypeName",
					ORIGIN                   AS "origin",
					FUNCTIONTYPE             AS "type",
					RTRIM(LANGUAGE)          AS "language",
					DETERMINISTIC            AS "deterministic",
					EXTERNAL_ACTION          AS "externalAction",
					NULLCALL                 AS "nullCall",
					CAST_FUNCTION            AS "castFunction",
					ASSIGN_FUNCTION          AS "assignFunction",
					PARALLEL                 AS "parallel",
					FENCED                   AS "fenced",
					SQL_DATA_ACCESS          AS "sqlAccess",
					THREADSAFE               AS "threadSafe",
					VALID                    AS "valid",
					CHAR(CREATE_TIME)        AS "created",
					RTRIM(QUALIFIER)         AS "qualifier",
					RTRIM(FUNC_PATH)         AS "funcPath",
					TEXT                     AS "sql",
					REMARKS                  AS "description"
				FROM %(schema)s.ROUTINES
				WHERE ROUTINETYPE = 'F'
				WITH UR""" % {'schema': ['SYSCAT', 'DOCCAT'][doccat]})
			self.functions = dict([((row['schemaName'], row['specificName']), row) for row in _fetch_dict(cursor)])
		finally:
			del cursor
		for row in self.functions.itervalues():
			row['created'] = makeDateTime(row['created'])
			row['deterministic'] = makeBoolean(row['deterministic'])
			row['externalAction'] = makeBoolean(row['externalAction'], 'E')
			row['nullCall'] = makeBoolean(row['nullCall'])
			row['castFunction'] = makeBoolean(row['castFunction'])
			row['assignFunction'] = makeBoolean(row['assignFunction'])
			row['parallel'] = makeBoolean(row['parallel'])
			row['fenced'] = makeBoolean(row['fenced'])
			row['threadSafe'] = makeBoolean(row['threadSafe'])
			row['valid'] = makeBoolean(row['valid'])
			row['origin'] = {
				'B': 'Built-in',
				'E': 'User-defined external',
				'M': 'Template',
				'Q': 'SQL body',
				'U': 'User-defined source',
				'S': 'System generated',
				'T': 'System generated transform'
			}[row['origin']]
			row['type'] = {
				'C': 'Column',
				'R': 'Row',
				'S': 'Scalar',
				'T': 'Table'
			}[row['type']]
			row['sqlAccess'] = {
				'C': 'Contains SQL',
				'M': 'Modifies SQL',
				'N': 'No SQL',
				'R': 'Reads SQL',
				' ': None
			}[row['sqlAccess']]
			row['sql'] = str(row['sql'])

	def _get_function_params(self, connection, doccat):
		logging.debug("Retrieving parameters")
		cursor = connection.cursor()
		try:
			cursor.execute("""
				SELECT
					RTRIM(ROUTINESCHEMA)          AS "schemaName",
					RTRIM(ROUTINENAME)            AS "routineName",
					RTRIM(SPECIFICNAME)           AS "specificName",
					RTRIM(COALESCE(PARMNAME, '')) AS "name",
					ORDINAL                       AS "position",
					ROWTYPE                       AS "type",
					RTRIM(TYPESCHEMA)             AS "datatypeSchema",
					RTRIM(TYPENAME)               AS "datatypeName",
					LOCATOR                       AS "locator",
					LENGTH                        AS "size",
					SCALE                         AS "scale",
					CODEPAGE                      AS "codepage",
					REMARKS                       AS "description"
				FROM %(schema)s.ROUTINEPARMS
				WITH UR""" % {'schema': ['SYSCAT', 'DOCCAT'][doccat]})
			self.parameters = dict([((row['schemaName'], row['specificName'], row['type'], row['position']), row) for row in _fetch_dict(cursor)])
		finally:
			del cursor
		for row in self.parameters.itervalues():
			row['locator'] = makeBoolean(row['locator'])
			if row['size'] == 0: row['size'] = None
			if row['scale'] == -1: row['scale'] = None
			if not row['codepage']: row['codepage'] = None
			row['type'] = {
				'B': 'In/Out',
				'O': 'Output',
				'P': 'Input',
				'C': 'Result',
				'R': 'Result'
			}[row['type']]

	def _get_tablespaces(self, connection, doccat):
		logging.debug("Retrieving tablespaces")
		cursor = connection.cursor()
		try:
			cursor.execute("""
				SELECT
					RTRIM(TBSPACE)    AS "name",
					RTRIM(DEFINER)    AS "definer",
					CHAR(CREATE_TIME) AS "created",
					TBSPACETYPE       AS "managedBy",
					DATATYPE          AS "dataType",
					EXTENTSIZE        AS "extentSize",
					PREFETCHSIZE      AS "prefetchSize",
					OVERHEAD          AS "overhead",
					TRANSFERRATE      AS "transferRate",
					PAGESIZE          AS "pageSize",
					DROP_RECOVERY     AS "dropRecovery",
					REMARKS           AS "description"
				FROM %(schema)s.TABLESPACES
				WITH UR""" % {'schema': ['SYSCAT', 'DOCCAT'][doccat]})
			self.tablespaces = dict([(row['name'], row) for row in _fetch_dict(cursor)])
		finally:
			del cursor
		for row in self.tablespaces.itervalues():
			row['created'] = makeDateTime(row['created'])
			row['dropRecovery'] = makeBoolean(row['dropRecovery'])
			if row['prefetchSize'] < 0: row['prefetchSize'] = 'Auto'
			row['managedBy'] = {
				'S': 'System',
				'D': 'Database'
			}[row['managedBy']]
			row['dataType'] = {
				'A': 'Any',
				'L': 'Long/Index',
				'T': 'System Temporary',
				'U': 'User Temporary'
			}[row['dataType']]

	def _get_tablespace_tables(self, connection, doccat):
		# Note: MUST be run after _get_tables and _get_tablespaces
		self.tablespaceTables = dict([(tbspace, [(row['schemaName'], row['name'])
			for row in self.tables.itervalues()
			if row['dataTbspace'] == tbspace
			or row['indexTbspace'] == tbspace
			or row['longTbspace'] == tbspace])
			for tbspace in self.tablespaces])

	def _get_tablespace_indexes(self, connection, doccat):
		# Note: MUST be run after _get_indexes and _get_tablespaces
		self.tablespaceIndexes = dict([(tbspace, [(row['schemaName'], row['name'])
			for row in self.indexes.itervalues() if row['tablespaceName'] == tbspace])
			for tbspace in self.tablespaces])

def main():
	# XXX Test cases
	pass

if __name__ == "__main__":
	main()
