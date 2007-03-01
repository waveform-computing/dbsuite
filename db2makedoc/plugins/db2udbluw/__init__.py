# $Header$
# vim: set noet sw=4 ts=4:

"""Input plugin for IBM DB2 UDB for Linux/UNIX/Windows.

This input plugin supports extracting documentation information from IBM DB2
UDB for Linux/UNIX/Windows version 8 or above. If the DOCCAT schema (see the
doccat_create.sql script in the contrib/db2udbluw directory) is present, it
will be used to source documentation data instead of SYSCAT.
"""

# Standard modules
import sys
mswindows = sys.platform == 'win32'
import logging
import datetime
import re

# Constants
DATABASE_OPTION = 'database'
USERNAME_OPTION = 'username'
PASSWORD_OPTION = 'password'

# Localizable strings
DATABASE_DESC = 'The locally cataloged name of the database to connect to'
USERNAME_DESC = 'The username to connect with (optional: if ommitted an implicit connection will be made)'
PASSWORD_DESC = 'The password associated with the user given by the username option'
MISSING_OPTION = 'The "%s" option must be specified'
MISSING_DEPENDENT = 'If the "%s" option is given, the "%s" option must also be provided'

CONNECTING_MSG = 'Connecting to database %s'
USING_DOCCAT = 'DOCCAT extension schema found, using DOCCAT instead of SYSCAT'
USING_SYSCAT = 'DOCCAT extension schema not found, using SYSCAT'

# Plugin options dictionary
options = {
	DATABASE_OPTION: DATABASE_DESC,
	USERNAME_OPTION: USERNAME_DESC,
	PASSWORD_OPTION: PASSWORD_DESC,
}

def _make_datetime(value):
	"""Converts a date-time value from a database query to a datetime object.

	If value is None or a blank string, returns None. If value is a string
	containing an ISO8601 formatted date ("YYYY-MM-DD HH:MM:SS.NNNNNN") it is
	converted to a standard Python datetime value. If value is has a integer
	"value" attribute it is assumed to be a UNIX timestamp and is converted
	into a Python datetime value.

	Basically this routine exists to converts a database framework-specific
	representation of a datetime value into a standard Python datetime value.
	"""
	if (value is None) or (value == ""):
		return None
	elif isinstance(value, basestring):
		return datetime.datetime(*([int(x) for x in re.match(r"(\d{4})-(\d{2})-(\d{2})[T -](\d{2})[:.](\d{2})[:.](\d{2})\.(\d{6})\d*", value).groups()]))
	elif hasattr(value, 'value') and isinstance(value.value, int):
		return datetime.datetime.fromtimestamp(value.value)
	else:
		raise ValueError('Unable to convert date-time value "%s"' % str(value))

def _make_bool(value, true_value='Y', false_value='N', none_value=' ', unknown_error=False, unknown_result=None):
	"""Converts a character-based value into a boolean value.

	If value equals true_value, false_value, or none_value return true, false,
	or None respectively. If it matches none of them and unknown_error is false
	(the default), returns unknown_result (defaults to None).  Otherwise if
	unknown_error is true, the a KeyError is raised.
	"""
	try:
		return {true_value: True, false_value: False, none_value: None}[value]
	except KeyError:
		if unknown_error:
			raise
		else:
			return unknown_result

def _fetch_dict(cursor):
	"""Returns rows from a cursor as a list of dictionaries.

	Specifically, the result set is returned as a list of dictionaries, where
	each dictionary represents one row of the result set, and is keyed by the
	field names of the result set converted to lower case.

	Okay, horribly wasteful and un-Pythonic. But it's simple and it works.
	"""
	return [dict(zip([d[0] for d in cursor.description], row)) for row in cursor.fetchall()]

class Input(object):
	def __init__(self, config):
		super(Input, self).__init__()
		# Check the config dictionary for missing stuff
		if not DATABASE_OPTION in config:
			raise Exception(MISSING_OPTION % DATABASE_OPTION)
		if USERNAME_OPTION in config and not PASSWORD_OPTION in config:
			raise Exception(MISSING_DEPENDENT % (USERNAME_OPTION, PASSWORD_OPTION))
		logging.info(CONNECTING_MSG % config[DATABASE_OPTION])
		self.connection = self._connect(
			config[DATABASE_OPTION],
			config.get(USERNAME_OPTION, None),
			config.get(PASSWORD_OPTION, None)
		)
		try:
			self.name = config[DATABASE_OPTION]
			# Test whether the DOCCAT extension is installed
			cursor = self.connection.cursor()
			try:
				cursor.execute("""
					SELECT COUNT(*)
					FROM SYSCAT.SCHEMATA
					WHERE SCHEMANAME = 'DOCCAT'
					WITH UR""")
				self.doccat = bool(cursor.fetchall()[0][0])
				if self.doccat:
					logging.info(USING_DOCCAT)
				else:
					logging.info(USING_SYSCAT)
			finally:
				cursor.close()
				del cursor
			# Run all the queries, using DOCCAT extensions if available
			self._get_schemas()
			self._get_datatypes()
			self._get_tables()
			self._get_views()
			self._get_aliases()
			self._get_relation_dependencies()
			self._get_indexes()
			self._get_index_fields()
			self._get_table_indexes()
			self._get_fields()
			self._get_unique_keys()
			self._get_unique_key_fields()
			self._get_foreign_keys()
			self._get_foreign_key_fields()
			self._get_checks()
			self._get_check_fields()
			self._get_functions()
			self._get_function_params()
			self._get_procedures()
			self._get_procedure_params()
			self._get_triggers()
			self._get_trigger_dependencies()
			self._get_relation_triggers()
			self._get_tablespaces()
			self._get_tablespace_tables()
			self._get_tablespace_indexes()
		finally:
			self.connection.close()
			del self.connection
	
	def _connect(self, dsn, username=None, password=None):
		"""Create a connection to the specified database.

		This utility method attempts to connect to the database named by dsn
		using the (optional) username and password provided. The method
		attempts to use a variety of connection frameworks (PyDB2, PythonWin's
		ODBC stuff and mxODBC) depending on the underlying platform.

		Note that the queries in the methods below are written to be agnostic
		to the quirks of the various connection frameworks (e.g. PythonWin's
		ODBC module doesn't correctly handle certain dates hence why all DATE
		and TIMESTAMP fields are CAST to CHAR in the queries below).
		"""
		try:
			# Try the PyDB2 framework
			import DB2
		except ImportError:
			try:
				# Try the PythonWin ODBC framework
				if mswindows:
					import dbi
					import odbc
				else:
					raise ImportError('')
			except ImportError:
				try:
					# Try the mxODBC framework
					import mx.ODBC
				except ImportError:
					raise
				else:
					# XXX Fix connection string
					# Connect using mxODBC (different driver depending on
					# platform)
					if mswindows:
						import mx.ODBC.Windows
						return mx.ODBC.Windows.DriverConnect('DSN=%s;UID=%s;PWD=%s')
					else:
						import mx.ODBC.iODBC
						return mx.ODBC.iODBC.DriverConnect('DSN=%s;UID=%s;PWD=%s')
			else:
				# Connect using PythonWin ODBC
				if username:
					return odbc.odbc("%s/%s/%s" % (dsn, username, password))
				else:
					return odbc.odbc(dsn)
		else:
			# Connect using PyDB2
			if username:
				return DB2.Connection(dsn, username, password)
			else:
				return DB2.Connection(dsn)

	def _get_schemas(self):
		logging.debug("Retrieving schemas")
		cursor = self.connection.cursor()
		try:
			cursor.execute("""
				SELECT
					RTRIM(SCHEMANAME) AS "name",
					RTRIM(OWNER)      AS "owner",
					RTRIM(DEFINER)    AS "definer",
					CHAR(CREATE_TIME) AS "created",
					REMARKS           AS "description"
				FROM
					%(schema)s.SCHEMATA
				WITH UR""" % {'schema': ['SYSCAT', 'DOCCAT'][self.doccat]})
			self.schemas = dict([(row['name'], row) for row in _fetch_dict(cursor)])
		finally:
			cursor.close()
			del cursor
		for row in self.schemas.itervalues():
			row['created'] = _make_datetime(row['created'])

	def _get_datatypes(self):
		logging.debug("Retrieving datatypes")
		cursor = self.connection.cursor()
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
				FROM
					%(schema)s.DATATYPES
				WHERE INSTANTIABLE = 'Y'
				WITH UR""" % {'schema': ['SYSCAT', 'DOCCAT'][self.doccat]})
			self.datatypes = dict([((row['schemaName'], row['name']), row) for row in _fetch_dict(cursor)])
		finally:
			cursor.close()
			del cursor
		for row in self.datatypes.itervalues():
			row['created'] = _make_datetime(row['created'])
			row['final'] = _make_bool(row['final'])
			if not row['size']: row['size'] = None
			if not row['scale']: row['scale'] = None # XXX Not necessarily unknown (0 is a valid scale)
			if not row['codepage']: row['codepage'] = None
			row['type'] = {
				'S': 'SYSTEM',
				'T': 'DISTINCT',
				'R': 'STRUCTURED',
			}[row['type']]

	def _get_tables(self):
		logging.debug("Retrieving tables")
		cursor = self.connection.cursor()
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
				FROM
					%(schema)s.TABLES
				WHERE
					TYPE = 'T'
				WITH UR""" % {'schema': ['SYSCAT', 'DOCCAT'][self.doccat]})
			self.tables = dict([((row['schemaName'], row['name']), row) for row in _fetch_dict(cursor)])
		finally:
			cursor.close()
			del cursor
		for row in self.tables.itervalues():
			row['created'] = _make_datetime(row['created'])
			row['statsUpdated'] = _make_datetime(row['statsUpdated'])
			row['checkPending'] = _make_bool(row['checkPending'], 'C')
			row['append'] = _make_bool(row['append'])
			row['volatile'] = _make_bool(row['volatile'], 'C', ' ', None)
			row['compression'] = _make_bool(row['compression'], 'V')
			row['clustered'] = _make_bool(row['clustered'])
			row['lockSize'] = {
				'T': 'TABLE',
				'R': 'ROW',
			}[row['lockSize']]
			row['accessMode'] = {
				'N': 'NO ACCESS',
				'R': 'READ ONLY',
				'D': 'NO DATA MOVEMENT',
				'F': 'FULL ACCESS',
			}[row['accessMode']]

	def _get_views(self):
		logging.debug("Retrieving views")
		cursor = self.connection.cursor()
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
				WITH UR""" % {'schema': ['SYSCAT', 'DOCCAT'][self.doccat]})
			self.views = dict([((row['schemaName'], row['name']), row) for row in _fetch_dict(cursor)])
		finally:
			cursor.close()
			del cursor
		for row in self.views.itervalues():
			row['created'] = _make_datetime(row['created'])
			row['readOnly'] = _make_bool(row['readOnly'])
			row['valid'] = _make_bool(row['valid'], false_value='X')
			row['check'] = {
				'N': 'NO CHECK',
				'L': 'LOCAL CHECK',
				'C': 'CASCADED CHECK',
			}[row['check']]
			row['sql'] = str(row['sql'])

	def _get_aliases(self):
		logging.debug("Retrieving aliases")
		cursor = self.connection.cursor()
		try:
			cursor.execute("""
				SELECT
					RTRIM(TABSCHEMA)      AS "schemaName",
					RTRIM(TABNAME)        AS "name",
					RTRIM(DEFINER)        AS "definer",
					CHAR(CREATE_TIME)     AS "created",
					RTRIM(BASE_TABSCHEMA) AS "relationSchema",
					RTRIM(BASE_TABNAME)   AS "relationName",
					REMARKS               AS "description"
				FROM
					%(schema)s.TABLES
				WHERE
					TYPE = 'A'
				WITH UR""" % {'schema': ['SYSCAT', 'DOCCAT'][self.doccat]})
			self.aliases = dict([((row['schemaName'], row['name']), row) for row in _fetch_dict(cursor)])
		finally:
			cursor.close()
			del cursor
		for row in self.aliases.itervalues():
			row['created'] = _make_datetime(row['created'])

	def _get_relation_dependencies(self):
		logging.debug("Retrieving relation dependencies")
		cursor = self.connection.cursor()
		try:
			cursor.execute("""
				SELECT
					RTRIM(BSCHEMA)    AS "relationSchema",
					RTRIM(BNAME)      AS "relationName",
					RTRIM(TABSCHEMA)  AS "depSchema",
					RTRIM(TABNAME)    AS "depName"
				FROM
					%(schema)s.TABDEP
				WHERE
					BTYPE IN ('A', 'S', 'T', 'U', 'V', 'W')
				WITH UR""" % {'schema': ['SYSCAT', 'DOCCAT'][self.doccat]})
			self.relation_dependents = {}
			self.relation_dependencies = {}
			for (relation_schema, relation_name, dep_schema, dep_name) in cursor.fetchall():
				if not (relation_schema, relation_name) in self.relation_dependents:
					self.relation_dependents[(relation_schema, relation_name)] = []
				self.relation_dependents[(relation_schema, relation_name)].append((dep_schema, dep_name))
				if not (dep_schema, dep_name) in self.relation_dependencies:
					self.relation_dependencies[(dep_schema, dep_name)] = []
				self.relation_dependencies[(dep_schema, dep_name)].append((relation_schema, relation_name))
		finally:
			cursor.close()
			del cursor

	def _get_trigger_dependencies(self):
		logging.debug("Retrieving trigger dependencies")
		cursor = self.connection.cursor()
		try:
			cursor.execute("""
				SELECT
					RTRIM(D.BSCHEMA)    AS "relationSchema",
					RTRIM(D.BNAME)      AS "relationName",
					RTRIM(D.TRIGSCHEMA) AS "depSchema",
					RTRIM(D.TRIGNAME)   AS "depName"
				FROM
					%(schema)s.TRIGDEP D
					INNER JOIN %(schema)s.TRIGGERS T
						ON D.TRIGSCHEMA = T.TRIGSCHEMA
						AND D.TRIGNAME = T.TRIGNAME
				WHERE
					BTYPE IN ('A', 'S', 'T', 'U', 'V', 'W')
					AND NOT (D.BSCHEMA = T.TABSCHEMA AND D.BNAME = T.TABNAME)
				WITH UR""" % {'schema': ['SYSCAT', 'DOCCAT'][self.doccat]})
			self.trigger_dependents = {}
			self.trigger_dependencies = {}
			for (relation_schema, relation_name, dep_schema, dep_name) in cursor.fetchall():
				if not (relation_schema, relation_name) in self.trigger_dependents:
					self.trigger_dependents[(relation_schema, relation_name)] = []
				self.trigger_dependents[(relation_schema, relation_name)].append((dep_schema, dep_name))
				if not (dep_schema, dep_name) in self.trigger_dependencies:
					self.trigger_dependencies[(dep_schema, dep_name)] = []
				self.trigger_dependencies[(dep_schema, dep_name)].append((relation_schema, relation_name))
		finally:
			cursor.close()
			del cursor

	def _get_indexes(self):
		logging.debug("Retrieving indexes")
		cursor = self.connection.cursor()
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
				WITH UR""" % {'schema': ['SYSCAT', 'DOCCAT'][self.doccat]})
			self.indexes = dict([((row['schemaName'], row['name']), row) for row in _fetch_dict(cursor)])
		finally:
			cursor.close()
			del cursor
		for row in self.indexes.itervalues():
			row['created'] = _make_datetime(row['created'])
			row['statsUpdated'] = _make_datetime(row['statsUpdated'])
			row['reverseScans'] = _make_bool(row['reverseScans'])
			row['unique'] = row['unique'] != 'D'
			row['userDefined'] = row['userDefined'] != 0
			row['required'] = row['required'] != 0
			row['type'] = {
				'CLUS': 'CLUSTERING',
				'REG': 'REGULAR',
				'DIM': 'DIMENSION BLOCK',
				'BLOK': 'BLOCK',
			}[row['type']]

	def _get_index_fields(self):
		logging.debug("Retrieving index fields")
		cursor = self.connection.cursor()
		try:
			cursor.execute("""
				SELECT
					RTRIM(INDSCHEMA) AS "indexSchema",
					RTRIM(INDNAME)   AS "indexName",
					RTRIM(COLNAME)   AS "fieldName",
					COLORDER         AS "order"
				FROM
					%(schema)s.INDEXCOLUSE
				ORDER BY
					INDSCHEMA,
					INDNAME,
					COLSEQ
				WITH UR""" % {'schema': ['SYSCAT', 'DOCCAT'][self.doccat]})
			self.index_fields = {}
			for (index_schema, index_name, field_name, order) in cursor.fetchall():
				if not (index_schema, index_name) in self.index_fields:
					self.index_fields[(index_schema, index_name)] = []
				order = {
					'A': 'ASCENDING',
					'D': 'DESCENDING',
					'I': 'INCLUDE',
				}[order]
				self.index_fields[(index_schema, index_name)].append((field_name, order))
		finally:
			cursor.close()
			del cursor

	def _get_table_indexes(self):
		logging.debug("Retrieving table indexes")
		# Note: Must be run AFTER _get_indexes and _get_tables
		self.table_indexes = dict([
			((table_schema, table_name), [(row['schemaName'], row['name'])
				for row in self.indexes.itervalues()
				if row['tableSchema'] == table_schema
				and row['tableName'] == table_name
			])
			for (table_schema, table_name) in self.tables
		])

	def _get_fields(self):
		logging.debug("Retrieving fields")
		cursor = self.connection.cursor()
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
				FROM
					%(schema)s.COLUMNS
				WHERE
					HIDDEN <> 'S'
				WITH UR""" % {'schema': ['SYSCAT', 'DOCCAT'][self.doccat]})
			self.fields = dict([((row['schemaName'], row['tableName'], row['name']), row) for row in _fetch_dict(cursor)])
		finally:
			cursor.close()
			del cursor
		for row in self.fields.itervalues():
			if row['cardinality'] < 0: row['cardinality'] = None
			if row['averageSize'] < 0: row['averageSize'] = None
			if row['nullCardinality'] < 0: row['nullCardinality'] = None
			if not row['codepage']: row['codepage'] = None
			row['logged'] = _make_bool(row['logged'])
			row['compact'] = _make_bool(row['compact'])
			row['nullable'] = _make_bool(row['nullable'])
			row['identity'] = _make_bool(row['identity'])
			row['compressDefault'] = _make_bool(row['compressDefault'], 'S')
			row['generated'] = {
				'D': 'BY DEFAULT',
				'A': 'ALWAYS',
				' ': 'NEVER',
			}[row['generated']]
			row['generateExpression'] = str(row['generateExpression'])

	def _get_unique_keys(self):
		logging.debug("Retrieving unique keys")
		cursor = self.connection.cursor()
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
				FROM
					%(schema)s.TABCONST
				WHERE
					TYPE IN ('U', 'P')
				WITH UR""" % {'schema': ['SYSCAT', 'DOCCAT'][self.doccat]})
			self.unique_keys = dict([((row['schemaName'], row['tableName'], row['name']), row) for row in _fetch_dict(cursor)])
		finally:
			cursor.close()
			del cursor
		for row in self.unique_keys.itervalues():
			row['checkExisting'] = {
				'D': 'DEFER',
				'I': 'IMMEDIATE',
				'N': 'NO CHECK',
			}[row['checkExisting']]

	def _get_unique_key_fields(self):
		logging.debug("Retrieving unique key fields")
		cursor = self.connection.cursor()
		try:
			cursor.execute("""
				SELECT
					RTRIM(TABSCHEMA) AS "keySchema",
					RTRIM(TABNAME)   AS "keyTable",
					RTRIM(CONSTNAME) AS "keyName",
					RTRIM(COLNAME)   AS "fieldName"
				FROM
					%(schema)s.KEYCOLUSE
				ORDER BY
					TABSCHEMA,
					TABNAME,
					CONSTNAME,
					COLSEQ
				WITH UR""" % {'schema': ['SYSCAT', 'DOCCAT'][self.doccat]})
			self.unique_key_fields = {}
			for (key_schema, key_table, key_name, field_name) in cursor.fetchall():
				if not (key_schema, key_table, key_name) in self.unique_key_fields:
					self.unique_key_fields[(key_schema, key_table, key_name)] = []
				self.unique_key_fields[(key_schema, key_table, key_name)].append(field_name)
		finally:
			cursor.close()
			del cursor

	def _get_foreign_keys(self):
		logging.debug("Retrieving foreign keys")
		cursor = self.connection.cursor()
		try:
			cursor.execute("""
				SELECT
					RTRIM(T.TABSCHEMA)    AS "schemaName",
					RTRIM(T.TABNAME)      AS "tableName",
					RTRIM(T.CONSTNAME)    AS "name",
					RTRIM(R.REFTABSCHEMA) AS "refTableSchema",
					RTRIM(R.REFTABNAME)   AS "refTableName",
					RTRIM(R.REFKEYNAME)   AS "refKeyName",
					CHAR(R.CREATE_TIME)   AS "created",
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
				WITH UR""" % {'schema': ['SYSCAT', 'DOCCAT'][self.doccat]})
			self.foreign_keys = dict([((row['schemaName'], row['tableName'], row['name']), row) for row in _fetch_dict(cursor)])
		finally:
			cursor.close()
			del cursor
		for row in self.foreign_keys.itervalues():
			row['created'] = _make_datetime(row['created'])
			row['enforced'] = _make_bool(row['enforced'])
			row['queryOptimize'] = _make_bool(row['queryOptimize'])
			row['checkExisting'] = {
				'D': 'DEFER',
				'I': 'IMMEDIATE',
				'N': 'NO CHECK',
			}[row['checkExisting']]
			row['deleteRule'] = {
				'A': 'NO ACTION',
				'R': 'RESTRICT',
				'C': 'CASCADE',
				'N': 'SET NULL',
			}[row['deleteRule']]
			row['updateRule'] = {
				'A': 'NO ACTION',
				'R': 'RESTRICT',
				'C': 'CASCADE',
				'N': 'SET NULL',
			}[row['updateRule']]

	def _get_foreign_key_fields(self):
		logging.debug("Retrieving foreign key fields")
		cursor = self.connection.cursor()
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
				WHERE
					KF.COLSEQ = KP.COLSEQ
				ORDER BY
					R.TABSCHEMA,
					R.TABNAME,
					R.CONSTNAME,
					KF.COLSEQ
				WITH UR""" % {'schema': ['SYSCAT', 'DOCCAT'][self.doccat]})
			self.foreign_key_fields = {}
			for (key_schema, key_table, key_name, foreign_field_name, parent_field_name) in cursor.fetchall():
				if not (key_schema, key_table, key_name) in self.foreign_key_fields:
					self.foreign_key_fields[(key_schema, key_table, key_name)] = []
				self.foreign_key_fields[(key_schema, key_table, key_name)].append((foreign_field_name, parent_field_name))
		finally:
			cursor.close()
			del cursor

	def _get_checks(self):
		logging.debug("Retrieving check constraints")
		cursor = self.connection.cursor()
		try:
			cursor.execute("""
				SELECT
					RTRIM(T.TABSCHEMA)    AS "schemaName",
					RTRIM(T.TABNAME)      AS "tableName",
					RTRIM(T.CONSTNAME)    AS "name",
					CHAR(C.CREATE_TIME)   AS "created",
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
				WITH UR""" % {'schema': ['SYSCAT', 'DOCCAT'][self.doccat]})
			self.checks = dict([((row['schemaName'], row['tableName'], row['name']), row) for row in _fetch_dict(cursor)])
		finally:
			cursor.close()
			del cursor
		for row in self.checks.itervalues():
			row['created'] = _make_datetime(row['created'])
			row['enforced'] = _make_bool(row['enforced'])
			row['queryOptimize'] = _make_bool(row['queryOptimize'])
			row['checkExisting'] = {
				'D': 'DEFER',
				'I': 'IMMEDIATE',
				'N': 'NO CHECK',
			}[row['checkExisting']]
			row['type'] = {
				'A': 'SYSTEM', # InfoCenter reckons it's 'A'
				'S': 'SYSTEM', # However, it appears to be 'S'
				'C': 'CHECK',
				'F': 'FUNCTIONAL DEPENDENCY',
				'O': 'OBJECT PROPERTY',
			}[row['type']]
			row['expression'] = str(row['expression'])

	def _get_check_fields(self):
		logging.debug("Retrieving check fields")
		cursor = self.connection.cursor()
		try:
			cursor.execute("""
				SELECT
					RTRIM(TABSCHEMA) AS "keySchema",
					RTRIM(TABNAME)   AS "keyTable",
					RTRIM(CONSTNAME) AS "keyName",
					RTRIM(COLNAME)   AS "fieldName"
				FROM
					%(schema)s.COLCHECKS
				WITH UR""" % {'schema': ['SYSCAT', 'DOCCAT'][self.doccat]})
			self.check_fields = {}
			for (key_schema, key_table, key_name, field_name) in cursor.fetchall():
				if not (key_schema, key_table, key_name) in self.check_fields:
					self.check_fields[(key_schema, key_table, key_name)] = []
				self.check_fields[(key_schema, key_table, key_name)].append(field_name)
		finally:
			cursor.close()
			del cursor
	
	def _get_functions(self):
		logging.debug("Retrieving functions")
		cursor = self.connection.cursor()
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
				FROM
					%(schema)s.ROUTINES
				WHERE
					ROUTINETYPE = 'F'
				WITH UR""" % {'schema': ['SYSCAT', 'DOCCAT'][self.doccat]})
			self.functions = dict([((row['schemaName'], row['specificName']), row) for row in _fetch_dict(cursor)])
		finally:
			cursor.close()
			del cursor
		for row in self.functions.itervalues():
			row['created'] = _make_datetime(row['created'])
			row['deterministic'] = _make_bool(row['deterministic'])
			row['externalAction'] = _make_bool(row['externalAction'], 'E')
			row['nullCall'] = _make_bool(row['nullCall'])
			row['castFunction'] = _make_bool(row['castFunction'])
			row['assignFunction'] = _make_bool(row['assignFunction'])
			row['parallel'] = _make_bool(row['parallel'])
			row['fenced'] = _make_bool(row['fenced'])
			row['threadSafe'] = _make_bool(row['threadSafe'])
			row['valid'] = _make_bool(row['valid'])
			row['origin'] = {
				'B': 'BUILT-IN',
				'E': 'USER-DEFINED EXTERNAL',
				'M': 'TEMPLATE',
				'Q': 'SQL BODY',
				'U': 'USER-DEFINED SOURCE',
				'S': 'SYSTEM GENERATED',
				'T': 'SYSTEM GENERATED TRANSFORM',
			}[row['origin']]
			row['type'] = {
				'C': 'COLUMN',
				'R': 'ROW',
				'S': 'SCALAR',
				'T': 'TABLE',
			}[row['type']]
			row['sqlAccess'] = {
				'C': 'CONTAINS SQL',
				'M': 'MODIFIES SQL',
				'N': 'NO SQL',
				'R': 'READS SQL',
				' ': None,
			}[row['sqlAccess']]
			row['sql'] = str(row['sql'])

	def _get_function_params(self):
		logging.debug("Retrieving function parameters")
		cursor = self.connection.cursor()
		try:
			cursor.execute("""
				SELECT
					RTRIM(P.ROUTINESCHEMA)          AS "schemaName",
					RTRIM(P.ROUTINENAME)            AS "routineName",
					RTRIM(P.SPECIFICNAME)           AS "specificName",
					RTRIM(COALESCE(P.PARMNAME, '')) AS "name",
					P.ORDINAL                       AS "position",
					P.ROWTYPE                       AS "type",
					RTRIM(P.TYPESCHEMA)             AS "datatypeSchema",
					RTRIM(P.TYPENAME)               AS "datatypeName",
					P.LOCATOR                       AS "locator",
					P.LENGTH                        AS "size",
					P.SCALE                         AS "scale",
					P.CODEPAGE                      AS "codepage",
					P.REMARKS                       AS "description"
				FROM
					%(schema)s.ROUTINEPARMS P
					INNER JOIN %(schema)s.ROUTINES R
						ON P.ROUTINESCHEMA = R.ROUTINESCHEMA
						AND P.SPECIFICNAME = R.SPECIFICNAME
				WHERE
					R.ROUTINETYPE = 'F'
				WITH UR""" % {'schema': ['SYSCAT', 'DOCCAT'][self.doccat]})
			self.func_params = dict([((row['schemaName'], row['specificName'], row['type'], row['position']), row) for row in _fetch_dict(cursor)])
		finally:
			cursor.close()
			del cursor
		for row in self.func_params.itervalues():
			row['locator'] = _make_bool(row['locator'])
			if row['size'] == 0: row['size'] = None
			if row['scale'] == -1: row['scale'] = None
			if not row['codepage']: row['codepage'] = None
			row['type'] = {
				'B': 'INOUT',
				'O': 'OUT',
				'P': 'IN',
				'C': 'RESULT',
				'R': 'RESULT',
			}[row['type']]
	
	def _get_procedures(self):
		logging.debug("Retrieving procedures")
		cursor = self.connection.cursor()
		try:
			cursor.execute("""
				SELECT
					RTRIM(ROUTINESCHEMA)     AS "schemaName",
					RTRIM(SPECIFICNAME)      AS "specificName",
					RTRIM(ROUTINENAME)       AS "name",
					RTRIM(DEFINER)           AS "definer",
					ORIGIN                   AS "origin",
					RTRIM(LANGUAGE)          AS "language",
					DETERMINISTIC            AS "deterministic",
					EXTERNAL_ACTION          AS "externalAction",
					NULLCALL                 AS "nullCall",
					FENCED                   AS "fenced",
					SQL_DATA_ACCESS          AS "sqlAccess",
					THREADSAFE               AS "threadSafe",
					VALID                    AS "valid",
					CHAR(CREATE_TIME)        AS "created",
					RTRIM(QUALIFIER)         AS "qualifier",
					RTRIM(FUNC_PATH)         AS "funcPath",
					TEXT                     AS "sql",
					REMARKS                  AS "description"
				FROM
					%(schema)s.ROUTINES
				WHERE
					ROUTINETYPE = 'P'
				WITH UR""" % {'schema': ['SYSCAT', 'DOCCAT'][self.doccat]})
			self.procedures = dict([((row['schemaName'], row['specificName']), row) for row in _fetch_dict(cursor)])
		finally:
			cursor.close()
			del cursor
		for row in self.procedures.itervalues():
			row['created'] = _make_datetime(row['created'])
			row['deterministic'] = _make_bool(row['deterministic'])
			row['externalAction'] = _make_bool(row['externalAction'], 'E')
			row['nullCall'] = _make_bool(row['nullCall'])
			row['fenced'] = _make_bool(row['fenced'])
			row['threadSafe'] = _make_bool(row['threadSafe'])
			row['valid'] = _make_bool(row['valid'])
			row['origin'] = {
				'B': 'BUILT-IN',
				'E': 'USER-DEFINED EXTERNAL',
				'M': 'TEMPLATE',
				'Q': 'SQL BODY',
				'U': 'USER-DEFINED SOURCE',
				'S': 'SYSTEM GENERATED',
				'T': 'SYSTEM GENERATED TRANSFORM',
			}[row['origin']]
			row['sqlAccess'] = {
				'C': 'CONTAINS SQL',
				'M': 'MODIFIES SQL',
				'N': 'NO SQL',
				'R': 'READS SQL',
				' ': None,
			}[row['sqlAccess']]
			row['sql'] = str(row['sql'])
	
	def _get_procedure_params(self):
		logging.debug("Retrieving procedure parameters")
		cursor = self.connection.cursor()
		try:
			cursor.execute("""
				SELECT
					RTRIM(P.ROUTINESCHEMA)          AS "schemaName",
					RTRIM(P.ROUTINENAME)            AS "routineName",
					RTRIM(P.SPECIFICNAME)           AS "specificName",
					RTRIM(COALESCE(P.PARMNAME, '')) AS "name",
					P.ORDINAL                       AS "position",
					P.ROWTYPE                       AS "type",
					RTRIM(P.TYPESCHEMA)             AS "datatypeSchema",
					RTRIM(P.TYPENAME)               AS "datatypeName",
					P.LENGTH                        AS "size",
					P.SCALE                         AS "scale",
					P.CODEPAGE                      AS "codepage",
					P.REMARKS                       AS "description"
				FROM
					%(schema)s.ROUTINEPARMS P
					INNER JOIN %(schema)s.ROUTINES R
						ON P.ROUTINESCHEMA = R.ROUTINESCHEMA
						AND P.SPECIFICNAME = R.SPECIFICNAME
				WHERE
					R.ROUTINETYPE = 'P'
				WITH UR""" % {'schema': ['SYSCAT', 'DOCCAT'][self.doccat]})
			self.proc_params = dict([((row['schemaName'], row['specificName'], row['type'], row['position']), row) for row in _fetch_dict(cursor)])
		finally:
			cursor.close()
			del cursor
		for row in self.proc_params.itervalues():
			if row['size'] == 0: row['size'] = None
			if row['scale'] == -1: row['scale'] = None
			if not row['codepage']: row['codepage'] = None
			row['type'] = {
				'B': 'INOUT',
				'O': 'OUT',
				'P': 'IN',
				'C': 'RESULT',
				'R': 'RESULT',
			}[row['type']]
	
	def _get_triggers(self):
		logging.debug("Retrieving triggers")
		cursor = self.connection.cursor()
		try:
			cursor.execute("""
				SELECT
					RTRIM(TRIGSCHEMA) AS "schemaName",
					RTRIM(TRIGNAME)   AS "name",
					RTRIM(DEFINER)    AS "definer",
					RTRIM(TABSCHEMA)  AS "tableSchema",
					RTRIM(TABNAME)    AS "tableName",
					TRIGTIME          AS "triggerTime",
					TRIGEVENT         AS "triggerEvent",
					GRANULARITY       AS "granularity",
					VALID             AS "valid",
					CHAR(CREATE_TIME) AS "created",
					RTRIM(QUALIFIER)  AS "qualifier",
					RTRIM(FUNC_PATH)  AS "funcPath",
					TEXT              AS "sql",
					REMARKS           AS "description"
				FROM
					%(schema)s.TRIGGERS
				WITH UR""" % {'schema': ['SYSCAT', 'DOCCAT'][self.doccat]})
			self.triggers = dict([((row['schemaName'], row['name']), row) for row in _fetch_dict(cursor)])
		finally:
			cursor.close()
			del cursor
		for row in self.triggers.itervalues():
			row['created'] = _make_datetime(row['created'])
			row['valid'] = _make_bool(row['valid'], false_value='X')
			row['triggerTime'] = {
				'A': 'AFTER',
				'B': 'BEFORE',
				'I': 'INSTEAD OF',
			}[row['triggerTime']]
			row['triggerEvent'] = {
				'I': 'INSERT',
				'U': 'UPDATE',
				'D': 'DELETE',
			}[row['triggerEvent']]
			row['granularity'] = {
				'S': 'STATEMENT',
				'R': 'ROW',
			}[row['granularity']]
			row['sql'] = str(row['sql'])

	def _get_relation_triggers(self):
		logging.debug("Retrieving table triggers")
		cursor = self.connection.cursor()
		try:
			cursor.execute("""
				SELECT
					RTRIM(TABSCHEMA)  AS "tableSchema",
					RTRIM(TABNAME)    AS "tableName",
					RTRIM(TRIGSCHEMA) AS "triggerSchema",
					RTRIM(TRIGNAME)   AS "triggerName"
				FROM
					%(schema)s.TRIGGERS
				WITH UR""" % {'schema': ['SYSCAT', 'DOCCAT'][self.doccat]})
			self.relation_triggers = {}
			for (table_schema, table_name, trigger_schema, trigger_name) in cursor.fetchall():
				if not (table_schema, table_name) in self.relation_triggers:
					self.relation_triggers[(table_schema, table_name)] = []
				self.relation_triggers[(table_schema, table_name)].append((trigger_schema, trigger_name))
		finally:
			cursor.close()
			del cursor

	def _get_tablespaces(self):
		logging.debug("Retrieving tablespaces")
		cursor = self.connection.cursor()
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
				WITH UR""" % {'schema': ['SYSCAT', 'DOCCAT'][self.doccat]})
			self.tablespaces = dict([(row['name'], row) for row in _fetch_dict(cursor)])
		finally:
			cursor.close()
			del cursor
		for row in self.tablespaces.itervalues():
			row['created'] = _make_datetime(row['created'])
			row['dropRecovery'] = _make_bool(row['dropRecovery'])
			if row['prefetchSize'] < 0: row['prefetchSize'] = 'Auto'
			row['managedBy'] = {
				'S': 'SYSTEM',
				'D': 'DATABASE',
			}[row['managedBy']]
			row['dataType'] = {
				'A': 'ANY',
				'L': 'LONG/INDEX',
				'T': 'SYSTEM TEMPORARY',
				'U': 'USER TEMPORARY',
			}[row['dataType']]

	def _get_tablespace_tables(self):
		# Note: Must be run AFTER _get_tables and _get_tablespaces
		logging.debug("Retrieving tablespace tables")
		self.tablespace_tables = dict([
			(tbspace, [(row['schemaName'], row['name'])
				for row in self.tables.itervalues()
				if row['dataTbspace'] == tbspace
				or row['indexTbspace'] == tbspace
				or row['longTbspace'] == tbspace
			])
			for tbspace in self.tablespaces
		])

	def _get_tablespace_indexes(self):
		# Note: Must be run AFTER _get_indexes and _get_tablespaces
		logging.debug("Retrieving tablespace indexes")
		self.tablespace_indexes = dict([
			(tbspace, [
				(row['schemaName'], row['name'])
				for row in self.indexes.itervalues() if row['tablespaceName'] == tbspace
			])
			for tbspace in self.tablespaces
		])

