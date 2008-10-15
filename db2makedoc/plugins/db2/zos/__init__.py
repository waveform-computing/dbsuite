# vim: set noet sw=4 ts=4:

"""Input plugin for IBM DB2 for z/OS."""

import logging
import re
import db2makedoc.plugins
from itertools import groupby
from db2makedoc.util import *
from db2makedoc.plugins.db2 import connect, make_datetime, make_bool
from db2makedoc.tuples import (
	Schema, Datatype, Table, View, Alias, RelationDep, Index, IndexCol,
	RelationCol, UniqueKey, UniqueKeyCol, ForeignKey, ForeignKeyCol, Check,
	CheckCol, Function, Procedure, RoutineParam, Trigger, TriggerDep,
	Tablespace
)


class InputPlugin(db2makedoc.plugins.InputPlugin):
	"""Input plugin for IBM DB2 for z/OS.

	This input plugin supports extracting documentation information from IBM
	DB2 for z/OS version 8 or above.
	"""

	def __init__(self):
		super(InputPlugin, self).__init__()
		self.add_option('database', default='',
			doc="""The locally cataloged name of the database to connect to """)
		self.add_option('username', default=None,
			doc="""The username to connect with (if ommitted, an implicit
			connection will be made as the current user)""")
		self.add_option('password', default=None,
			doc="""The password associated with the user given by the username
			option (mandatory if username is supplied)""")

	def configure(self, config):
		"""Loads the plugin configuration."""
		super(InputPlugin, self).configure(config)
		# Check for missing stuff
		if not self.options['database']:
			raise db2makedoc.plugins.PluginConfigurationError('The database option must be specified')
		if self.options['username'] is not None and self.options['password'] is None:
			raise db2makedoc.plugins.PluginConfigurationError('If the username option is specified, the password option must also be specified')

	def open(self):
		"""Opens the database connection for data retrieval."""
		super(InputPlugin, self).open()
		self.connection = connect(
			self.options['database'],
			self.options['username'],
			self.options['password']
		)
		self.name = self.options['database']
		# Test which version of the system catalog is installed. The following
		# progression is used to determine version:
		#
		# Base level (70)
		# SYSIBM.SYSSEQUENCEAUTH introduced in v8 (80)
		# SYSIBM.SYSROLES introduced in v9 (90)
		cursor = self.connection.cursor()
		schemaver = 70
		cursor.execute("""
			SELECT COUNT(*)
			FROM SYSIBM.SYSTABLES
			WHERE CREATOR = 'SYSIBM'
			AND NAME = 'SYSSEQUENCEAUTH'
			WITH UR""")
		if bool(cursor.fetchall()[0][0]):
			schemaver = 80
			cursor.execute("""
				SELECT COUNT(*)
				FROM SYSIBM.SYSTABLES
				WHERE CREATOR = 'SYSIBM'
				AND NAME = 'SYSROLES'
				WITH UR""")
			if bool(cursor.fetchall()[0][0]):
				schemaver = 90
		logging.info({
			70: 'Detected v7 (or below) catalog layout',
			80: 'Detected v8 catalog layout',
			90: 'Detected v9.1 catalog layout',
		}[schemaver])
		if schemaver < 80:
			raise db2makedoc.plugins.PluginError('DB2 server must be v8 or above')

	def close(self):
		"""Closes the database connection and cleans up any resources."""
		super(InputPlugin, self).close()
		self.connection.close()
		del self.connection

	def get_schemas(self):
		"""Retrieves the details of schemas stored in the database.

		Override this function to return a list of Schema tuples containing
		details of the schemas defined in the database. Schema tuples have the
		following named fields:

		name         -- The name of the schema
		owner*       -- The name of the user who owns the schema
		system       -- True if the schema is system maintained (bool)
		created*     -- When the schema was created (datetime)
		description* -- Descriptive text

		* Optional (can be None)
		"""
		for row in super(InputPlugin, self).get_schemas():
			yield row
		cursor = self.connection.cursor()
		# There is no catalog table detailing schemas in DB2 for z/OS so
		# instead we fake it by querying all schema information from the union
		# of the table, trigger, routine and sequence catalogs (which should
		# account for all schemas in the database, I think). The first person
		# to create an object in a schema is considered the "creator" of the
		# schema (this won't be accurate - consider what happens if the first
		# object is dropped - but it's good enough).
		cursor.execute("""
			WITH OBJECTS AS (
				SELECT CREATOR AS SCHEMA, CREATEDBY, CREATEDTS
				FROM SYSIBM.SYSTABLES
				UNION
				SELECT SCHEMA, CREATEDBY, CREATEDTS
				FROM SYSIBM.SYSROUTINES
				UNION
				SELECT SCHEMA, CREATEDBY, CREATEDTS
				FROM SYSIBM.SYSTRIGGERS
				UNION
				SELECT SCHEMA, CREATEDBY, CREATEDTS
				FROM SYSIBM.SYSSEQUENCES
			),
			SCHEMAS AS (
				SELECT SCHEMA, MIN(CREATEDTS) AS CREATEDTS
				FROM OBJECTS
				GROUP BY SCHEMA
			)
			SELECT
				RTRIM(S.SCHEMA)          AS NAME,
				MIN(O.CREATEDBY)         AS OWNER,
				CASE
					WHEN S.SCHEMA LIKE 'SYS%' THEN 'Y'
					ELSE 'N'
				END                      AS SYSTEM,
				CHAR(S.CREATEDTS)        AS CREATED,
				CAST('' AS VARCHAR(762)) AS DESCRIPTION
			FROM
				SCHEMAS S
				INNER JOIN OBJECTS O
					ON S.SCHEMA = O.SCHEMA
					AND S.CREATEDTS = O.CREATEDTS
			GROUP BY
				S.SCHEMA,
				S.CREATEDTS
			WITH UR
		""")
		for (
				name,
				owner,
				system,
				created,
				desc
			) in self.fetch_some(cursor):
			yield Schema(
				name,
				owner,
				make_bool(system),
				make_datetime(created),
				desc
			)

	def get_datatypes(self):
		"""Retrieves the details of datatypes stored in the database.

		Override this function to return a list of Datatype tuples containing
		details of the datatypes defined in the database (including system
		types). Datatype tuples have the following named fields:

		schema         -- The schema of the datatype
		name           -- The name of the datatype
		owner*         -- The name of the user who owns the datatype
		system         -- True if the type is system maintained (bool)
		created*       -- When the type was created (datetime)
		description*   -- Descriptive text
		variable_size  -- True if the type has a variable length (e.g. VARCHAR)
		variable_scale -- True if the type has a variable scale (e.g. DECIMAL)
		source_schema* -- The schema of the base system type of the datatype
		source_name*   -- The name of the base system type of the datatype
		size*          -- The length of the type for character based types or
		                  the maximum precision for decimal types
		scale*         -- The maximum scale for decimal types

		* Optional (can be None)
		"""
		for row in super(InputPlugin, self).get_datatypes():
			yield row
		cursor = self.connection.cursor()
		cursor.execute("""
			SELECT DISTINCT
				CAST('SYSIBM' AS VARCHAR(128))    AS TYPESCHEMA,
				CASE COLTYPE
					WHEN 'LONGVAR'  THEN 'LONG VARCHAR'
					WHEN 'CHAR'     THEN 'CHARACTER'
					WHEN 'VARG'     THEN 'VARGRAPHIC'
					WHEN 'LONGVARG' THEN 'LONG VARGRAPHIC'
					WHEN 'TIMESTMP' THEN 'TIMESTAMP'
					WHEN 'FLOAT'    THEN
						CASE LENGTH
							WHEN 4 THEN 'REAL'
							WHEN 8 THEN 'DOUBLE'
						END
					ELSE RTRIM(COLTYPE)
				END                               AS TYPENAME,
				'SYSIBM'                          AS OWNER,
				CHAR('Y')                         AS SYSTEM,
				CHAR(TIMESTAMP('19850401000000')) AS CREATED,
				CAST(NULL AS VARCHAR(762))        AS DESCRIPTION,
				CAST(NULL AS VARCHAR(128))        AS SOURCESCHEMA,
				CAST(NULL AS VARCHAR(128))        AS SOURCENAME,
				CAST(CASE COLTYPE
					WHEN 'CHAR'     THEN 0
					WHEN 'VARCHAR'  THEN 0
					WHEN 'LONGVAR'  THEN 0
					WHEN 'DECIMAL'  THEN 0
					WHEN 'GRAPHIC'  THEN 0
					WHEN 'VARG'     THEN 0
					WHEN 'LONGVARG' THEN 0
					WHEN 'BLOB'     THEN 0
					WHEN 'CLOB'     THEN 0
					WHEN 'DBCLOB'   THEN 0
					ELSE LENGTH
				END AS SMALLINT)                  AS SIZE,
				CAST(0 AS SMALLINT)               AS SCALE
			FROM
				SYSIBM.SYSCOLUMNS
			WHERE
				RTRIM(TYPESCHEMA) = 'SYSIBM'

			UNION ALL

			SELECT
				RTRIM(SCHEMA)       AS TYPESCHEMA,
				RTRIM(NAME)         AS TYPENAME,
				OWNER               AS OWNER,
				CHAR('N')           AS SYSTEM,
				CHAR(CREATEDTS)     AS CREATED,
				REMARKS             AS DESCRIPTION,
				RTRIM(SOURCESCHEMA) AS SOURCESCHEMA,
				RTRIM(SOURCETYPE)   AS SOURCENAME,
				LENGTH              AS SIZE,
				SCALE               AS SCALE
			FROM
				SYSIBM.SYSDATATYPES
			WITH UR
		""")
		for (
				schema,
				name,
				owner,
				system,
				created,
				desc,
				source_schema,
				source_name,
				size,
				scale,
			) in self.fetch_some(cursor):
			system = make_bool(system)
			yield Datatype(
				schema,
				name,
				owner,
				system,
				make_datetime(created),
				desc,
				system and not size and (name not in ('XML', 'REFERENCE')),
				system and (name == 'DECIMAL'),
				source_schema,
				source_name,
				size or None,
				scale or None # XXX Not necessarily unknown (0 is a valid scale)
			)

	def get_tables(self):
		"""Retrieves the details of tables stored in the database.

		Override this function to return a list of Table tuples containing
		details of the tables (NOT views) defined in the database (including
		system tables). Table tuples contain the following named fields:

		schema        -- The schema of the table
		name          -- The name of the table
		owner*        -- The name of the user who owns the table
		system        -- True if the table is system maintained (bool)
		created*      -- When the table was created (datetime)
		description*  -- Descriptive text
		tbspace       -- The name of the primary tablespace containing the table
		last_stats*   -- When the table's statistics were last calculated (datetime)
		cardinality*  -- The approximate number of rows in the table
		size*         -- The approximate size in bytes of the table

		* Optional (can be None)
		"""
		for row in super(InputPlugin, self).get_tables():
			yield row
		cursor = self.connection.cursor()
		cursor.execute("""
			SELECT
				RTRIM(CREATOR)                     AS TABSCHEMA,
				RTRIM(NAME)                        AS TABNAME,
				CREATEDBY                          AS OWNER,
				CASE
					WHEN CREATOR LIKE 'SYS%' THEN 'Y'
					ELSE 'N'
				END                                AS SYSTEM,
				CHAR(CREATEDTS)                    AS CREATED,
				REMARKS                            AS DESCRIPTION,
				RTRIM(TSNAME)                      AS TBSPACE,
				CHAR(STATSTIME)                    AS LASTSTATS,
				NULLIF(DECIMAL(CARDF), -1)         AS CARDINALITY,
				NULLIF(DECIMAL(SPACEF), -1) * 1024 AS SIZE
			FROM
				SYSIBM.SYSTABLES
			WHERE
				TYPE IN ('T', 'X')
				AND STATUS IN ('X', ' ')
			WITH UR
		""")
		for (
				schema,
				name,
				owner,
				system,
				created,
				desc,
				tbspace,
				laststats,
				cardinality,
				size,
			) in self.fetch_some(cursor):
			yield Table(
				schema,
				name,
				owner,
				make_bool(system),
				make_datetime(created),
				desc,
				tbspace,
				make_datetime(laststats),
				cardinality,
				size
			)

	def get_views(self):
		"""Retrieves the details of views stored in the database.

		Override this function to return a list of View tuples containing
		details of the views defined in the database (including system views).
		View tuples contain the following named fields:

		schema        -- The schema of the view
		name          -- The name of the view
		owner*        -- The name of the user who owns the view
		system        -- True if the view is system maintained (bool)
		created*      -- When the view was created (datetime)
		description*  -- Descriptive text
		read_only*    -- True if the view is not updateable (bool)
		sql*          -- The SQL statement that defined the view

		* Optional (can be None)
		"""
		for row in super(InputPlugin, self).get_views():
			yield row
		cursor = self.connection.cursor()
		cursor.execute("""
			SELECT
				RTRIM(V.CREATOR)      AS VIEWSCHEMA,
				RTRIM(V.NAME)         AS VIEWNAME,
				T.CREATEDBY           AS OWNER,
				CASE
					WHEN V.CREATOR LIKE 'SYS%' THEN 'Y'
					ELSE 'N'
				END                   AS SYSTEM,
				CHAR(T.CREATEDTS)     AS CREATED,
				T.REMARKS             AS DESCRIPTION,
				CAST(NULL AS CHAR(1)) AS READONLY,
				V.TEXT                AS SQL
			FROM
				SYSIBM.SYSTABLES T
				INNER JOIN SYSIBM.SYSVIEWS V
					ON T.CREATOR = V.CREATOR
					AND T.NAME = V.NAME
					AND T.TYPE IN ('M', 'V')
			ORDER BY
				V.CREATOR,
				V.NAME,
				V.SEQNO
			WITH UR
		""")
		for (k, v) in groupby(self.fetch_some(cursor), key=itemgetter(0, 1)):
			v = list(v)
			(
				schema,
				name,
				owner,
				system,
				created,
				desc,
				readonly,
				sql,
			) = v[0]
			sql = ''.join(i[-1] for i in v)
			yield View(
				schema,
				name,
				owner,
				make_bool(system),
				make_datetime(created),
				desc,
				make_bool(readonly),
				str(sql),
			)

	def get_aliases(self):
		"""Retrieves the details of aliases stored in the database.

		Override this function to return a list of Alias tuples containing
		details of the aliases (also known as synonyms in some systems) defined
		in the database (including system aliases). Alias tuples contain the
		following named fields:

		schema        -- The schema of the alias
		name          -- The name of the alias
		owner*        -- The name of the user who owns the alias
		system        -- True if the alias is system maintained (bool)
		created*      -- When the alias was created (datetime)
		description*  -- Descriptive text
		base_schema   -- The schema of the target relation
		base_table    -- The name of the target relation

		* Optional (can be None)
		"""
		for row in super(InputPlugin, self).get_aliases():
			yield row
		cursor = self.connection.cursor()
		cursor.execute("""
			SELECT
				RTRIM(CREATOR)   AS ALIASSCHEMA,
				RTRIM(NAME)      AS ALIASNAME,
				CREATEDBY        AS OWNER,
				CASE
					WHEN CREATOR LIKE 'SYS%' THEN 'Y'
					ELSE 'N'
				END              AS SYSTEM,
				CHAR(CREATEDTS)  AS CREATED,
				REMARKS          AS DESCRIPTION,
				RTRIM(TBCREATOR) AS BASESCHEMA,
				RTRIM(TBNAME)    AS BASETABLE
			FROM
				SYSIBM.SYSTABLES
			WHERE
				TYPE = 'A'

			UNION ALL

			SELECT
				RTRIM(CREATOR)   AS ALIASSCHEMA,
				RTRIM(NAME)      AS ALIASNAME,
				CREATEDBY        AS OWNER,
				CASE
					WHEN CREATOR LIKE 'SYS%' THEN 'Y'
					ELSE 'N'
				END              AS SYSTEM,
				CHAR(CREATEDTS)  AS CREATED,
				CAST(NULL AS VARCHAR(762)) AS DESCRIPTION,
				RTRIM(TBCREATOR) AS BASESCHEMA,
				RTRIM(TBNAME)    AS BASETABLE
			FROM
				SYSIBM.SYSSYNONYMS
			WITH UR
		""")
		for (
				schema,
				name,
				owner,
				system,
				created,
				desc,
				base_schema,
				base_table,
			) in self.fetch_some(cursor):
			yield Alias(
				schema,
				name,
				owner,
				make_bool(system),
				make_datetime(created),
				desc,
				base_schema,
				base_table
			)

	def get_view_dependencies(self):
		"""Retrieves the details of view dependencies.

		Override this function to return a list of RelationDep tuples
		containing details of the relations upon which views depend (the tables
		and views that a view references in its query). RelationDep tuples
		contain the following named fields:

		schema       -- The schema of the view
		name         -- The name of the view
		dep_schema   -- The schema of the relation upon which the view depends
		dep_name     -- The name of the relation upon which the view depends
		"""
		for row in super(InputPlugin, self).get_view_dependencies():
			yield row
		cursor = self.connection.cursor()
		cursor.execute("""
			SELECT
				RTRIM(DCREATOR) AS VIEWSCHEMA,
				RTRIM(DNAME)    AS VIEWNAME,
				RTRIM(BCREATOR) AS DEPSCHEMA,
				RTRIM(BNAME)    AS DEPNAME
			FROM
				SYSIBM.SYSVIEWDEP
			WHERE
				DTYPE IN ('M', 'V')
				AND BTYPE IN ('M', 'T', 'V')
			WITH UR""")
		for (
				schema,
				name,
				depschema,
				depname
			) in self.fetch_some(cursor):
			yield RelationDep(
				schema,
				name,
				depschema,
				depname
			)

	def get_indexes(self):
		"""Retrieves the details of indexes stored in the database.

		Override this function to return a list of Index tuples containing
		details of the indexes defined in the database (including system
		indexes). Index tuples contain the following named fields:

		schema        -- The schema of the index
		name          -- The name of the index
		owner*        -- The name of the user who owns the index
		system        -- True if the index is system maintained (bool)
		created*      -- When the index was created (datetime)
		description*  -- Descriptive text
		table_schema  -- The schema of the table the index belongs to
		table_name    -- The name of the table the index belongs to
		tbspace       -- The name of the tablespace which contains the index
		last_stats*   -- When the index statistics were last updated (datetime)
		cardinality*  -- The approximate number of values in the index
		size*         -- The approximate size in bytes of the index
		unique        -- True if the index contains only unique values (bool)

		* Optional (can be None)
		"""
		for row in super(InputPlugin, self).get_indexes():
			yield row
		cursor = self.connection.cursor()
		cursor.execute("""
			SELECT
				RTRIM(I.CREATOR)                     AS INDSCHEMA,
				RTRIM(I.NAME)                        AS INDNAME,
				I.CREATEDBY                          AS OWNER,
				CASE
					WHEN I.CREATOR LIKE 'SYS%' THEN 'Y'
					ELSE 'N'
				END                                  AS SYSTEM,
				CHAR(I.CREATEDTS)                    AS CREATED,
				I.REMARKS                            AS DESCRIPTION,
				RTRIM(I.TBCREATOR)                   AS TABSCHEMA,
				RTRIM(I.TBNAME)                      AS TABNAME,
				RTRIM(T.TSNAME)                      AS TBSPACE,
				CHAR(I.STATSTIME)                    AS LASTSTATS,
				NULLIF(DECIMAL(I.FULLKEYCARDF), -1)  AS CARD,
				NULLIF(DECIMAL(I.SPACEF), -1) * 1024 AS SIZE,
				CASE I.UNIQUERULE
					WHEN 'D' THEN 'N'
					ELSE 'Y'
				END                                  AS UNIQUE
			FROM
				SYSIBM.SYSINDEXES I
				INNER JOIN SYSIBM.SYSTABLES T
					ON I.TBCREATOR = T.CREATOR
					AND I.TBNAME = T.NAME
			WHERE
				T.STATUS IN ('X', ' ')
			WITH UR
		""")
		for (
				schema,
				name,
				owner,
				system,
				created,
				desc,
				tabschema,
				tabname,
				tbspace,
				laststats,
				card,
				size,
				unique,
			) in self.fetch_some(cursor):
			yield Index(
				schema,
				name,
				owner,
				make_bool(system),
				make_datetime(created),
				desc,
				tabschema,
				tabname,
				tbspace,
				make_datetime(laststats),
				card,
				size,
				make_bool(unique)
			)

	def get_index_cols(self):
		"""Retrieves the list of columns belonging to indexes.

		Override this function to return a list of IndexCol tuples detailing
		the columns that belong to each index in the database (including system
		indexes).  IndexCol tuples contain the following named fields:

		index_schema -- The schema of the index
		index_name   -- The name of the index
		name         -- The name of the column
		order        -- The ordering of the column in the index:
		                'A' = Ascending
		                'D' = Descending
		                'I' = Include (not an index key)

		Note that the each tuple details one column belonging to an index. It
		is important that the list of tuples is in the order that each column
		is declared in an index.
		"""
		for row in super(InputPlugin, self).get_index_cols():
			yield row
		cursor = self.connection.cursor()
		cursor.execute("""
			SELECT
				RTRIM(K.IXCREATOR) AS INDSCHEMA,
				RTRIM(K.IXNAME)    AS INDNAME,
				K.COLNAME          AS COLNAME,
				K.ORDERING         AS COLORDER
			FROM
				SYSIBM.SYSKEYS K
				INNER JOIN SYSIBM.SYSINDEXES I
					ON K.IXCREATOR = I.CREATOR
					AND K.IXNAME = I.NAME
				INNER JOIN SYSIBM.SYSTABLES T
					ON I.TBCREATOR = T.CREATOR
					AND I.TBNAME = T.NAME
			WHERE
				T.STATUS IN ('X', ' ')
			ORDER BY
				K.IXCREATOR,
				K.IXNAME,
				K.COLSEQ
			WITH UR
		""")
		for (
				schema,
				name,
				colname,
				colorder
			) in self.fetch_some(cursor):
			yield IndexCol(
				schema,
				name,
				colname,
				colorder
			)

	def get_relation_cols(self):
		"""Retrieves the list of columns belonging to relations.

		Override this function to return a list of RelationCol tuples detailing
		the columns that belong to each relation (table, view, etc.) in the
		database (including system relations). RelationCol tuples contain the
		following named fields:

		relation_schema  -- The schema of the table
		relation_name    -- The name of the table
		name             -- The name of the column
		type_schema      -- The schema of the column's datatype
		type_name        -- The name of the column's datatype
		size*            -- The length of the column for character types, or the
		                    numeric precision for decimal types (None if not a
		                    character or decimal type)
		scale*           -- The maximum scale for decimal types (None if not a
		                    decimal type)
		codepage*        -- The codepage of the column for character types (None
		                    if not a character type)
		identity*        -- True if the column is an identity column (bool)
		nullable*        -- True if the column can store NULL (bool)
		cardinality*     -- The approximate number of unique values in the column
		null_card*       -- The approximate number of NULLs in the column
		generated        -- 'A' = Column is always generated
		                    'D' = Column is generated by default
		                    'N' = Column is not generated
		default*         -- If generated is 'N', the default value of the column
		                    (expressed as SQL). Otherwise, the SQL expression that
		                    generates the column's value (or default value). None
		                    if the column has no default
		description*     -- Descriptive text

		Note that each tuple details one column belonging to a relation. It is
		important that the list of tuples is in the order that each column is
		declared in a relation.

		* Optional (can be None)
		"""
		for row in super(InputPlugin, self).get_relation_cols():
			yield row
		cursor = self.connection.cursor()
		cursor.execute("""
			SELECT
				RTRIM(C.TBCREATOR)                             AS TABSCHEMA,
				RTRIM(C.TBNAME)                                AS TABNAME,
				C.NAME                                         AS COLNAME,
				RTRIM(C.TYPESCHEMA)                            AS TYPESCHEMA,
				CASE RTRIM(C.TYPESCHEMA)
					WHEN 'SYSIBM' THEN
						CASE C.COLTYPE
							WHEN 'LONGVAR'  THEN 'LONG VARCHAR'
							WHEN 'CHAR'     THEN 'CHARACTER'
							WHEN 'VARG'     THEN 'VARGRAPHIC'
							WHEN 'LONGVARG' THEN 'LONG VARGRAPHIC'
							WHEN 'TIMESTMP' THEN 'TIMESTAMP'
							WHEN 'FLOAT'    THEN
								CASE C.LENGTH
									WHEN 4 THEN 'REAL'
									WHEN 8 THEN 'DOUBLE'
								END
							ELSE RTRIM(C.COLTYPE)
						END
					ELSE RTRIM(C.TYPENAME)
				END                                            AS TYPENAME,
				C.LENGTH                                       AS SIZE,
				C.SCALE                                        AS SCALE,
				C.CCSID                                        AS CODEPAGE,
				CASE C.DEFAULT
					WHEN 'A' THEN 'Y'
					WHEN 'D' THEN 'Y'
					WHEN 'I' THEN 'Y'
					WHEN 'J' THEN 'Y'
					ELSE 'N'
				END                                            AS IDENTITY,
				C.NULLS                                        AS NULLABLE,
				NULLIF(NULLIF(DECIMAL(C.COLCARD, 20), -1), -2) AS CARDINALITY,
				CAST(NULL AS DECIMAL(20))                      AS NULLCARD,
				CASE C.DEFAULT
					WHEN 'A' THEN 'A'
					WHEN 'D' THEN 'D'
					WHEN 'I' THEN 'A'
					WHEN 'J' THEN 'D'
					WHEN 'S' THEN 'D'
					WHEN 'U' THEN 'D'
					ELSE 'N'
				END                                            AS GENERATED,
				CASE C.DEFAULT
					WHEN '1' THEN '''' ||
						CASE C.DEFAULTVALUE
							WHEN '' THEN ''
							ELSE REPLACE(C.DEFAULTVALUE, '''', '''''')
						END || ''''
					WHEN '7' THEN '''' ||
						CASE C.DEFAULTVALUE
							WHEN '' THEN ''
							ELSE REPLACE(C.DEFAULTVALUE, '''', '''''')
						END || ''''
					WHEN '8' THEN 'G''' ||
						CASE C.DEFAULTVALUE
							WHEN '' THEN ''
							ELSE REPLACE(C.DEFAULTVALUE, '''', '''''')
						END || ''''
					WHEN '5' THEN 'X'''  || C.DEFAULTVALUE || ''''
					WHEN '6' THEN 'UX''' || C.DEFAULTVALUE || ''''
					WHEN 'B' THEN
						CASE C.COLTYPE
							WHEN 'INTEGER'  THEN '0'
							WHEN 'SMALLINT' THEN '0'
							WHEN 'FLOAT'    THEN '0.0'
							WHEN 'DECIMAL'  THEN '0.'
							WHEN 'CHAR'     THEN ''''''
							WHEN 'VARCHAR'  THEN ''''''
							WHEN 'LONGVAR'  THEN ''''''
							WHEN 'GRAPHIC'  THEN 'G'''''
							WHEN 'VARG'     THEN 'G'''''
							WHEN 'LONGVARG' THEN 'G'''''
							WHEN 'DATE'     THEN 'CURRENT DATE'
							WHEN 'TIME'     THEN 'CURRENT TIME'
							WHEN 'TIMESTMP' THEN 'CURRENT TIMESTAMP'
						END
					WHEN 'S' THEN 'CURRENT SQLID'
					WHEN 'U' THEN 'USER'
					WHEN 'Y' THEN
						CASE C.NULLS
							WHEN 'Y' THEN 'NULL'
							WHEN 'N' THEN
								CASE C.COLTYPE
									WHEN 'INTEGER'  THEN '0'
									WHEN 'SMALLINT' THEN '0'
									WHEN 'FLOAT'    THEN '0.0'
									WHEN 'DECIMAL'  THEN '0.'
									WHEN 'CHAR'     THEN ''''''
									WHEN 'VARCHAR'  THEN ''''''
									WHEN 'LONGVAR'  THEN ''''''
									WHEN 'GRAPHIC'  THEN 'G'''''
									WHEN 'VARG'     THEN 'G'''''
									WHEN 'LONGVARG' THEN 'G'''''
									WHEN 'DATE'     THEN 'CURRENT DATE'
									WHEN 'TIME'     THEN 'CURRENT TIME'
									WHEN 'TIMESTMP' THEN 'CURRENT TIMESTAMP'
								END
						END
					ELSE C.DEFAULTVALUE
				END                                            AS DEFAULT,
				C.REMARKS                                      AS DESCRIPTION
			FROM
				SYSIBM.SYSCOLUMNS C
				INNER JOIN SYSIBM.SYSTABLES T
					ON C.TBCREATOR = T.CREATOR
					AND C.TBNAME = T.NAME
			WHERE
				T.TYPE IN ('T', 'X', 'M', 'V')
				AND T.STATUS IN ('X', ' ')
			ORDER BY
				C.TBCREATOR,
				C.TBNAME,
				C.COLNO
			WITH UR
		""")
		for (
				schema,
				name,
				colname,
				typeschema,
				typename,
				size,
				scale,
				codepage,
				identity,
				nullable,
				cardinality,
				nullcard,
				generated,
				default,
				desc
			) in self.fetch_some(cursor):
			if generated != 'N':
				default = re.sub(r'^\s*AS\s*', '', str(default))
			yield RelationCol(
				schema,
				name,
				colname,
				typeschema,
				typename,
				size,
				scale,
				codepage or None,
				make_bool(identity),
				make_bool(nullable),
				cardinality,
				nullcard,
				generated,
				default,
				desc
			)

	def get_unique_keys(self):
		"""Retrieves the details of unique keys stored in the database.

		Override this function to return a list of UniqueKey tuples containing
		details of the unique keys defined in the database. UniqueKey tuples
		contain the following named fields:

		table_schema  -- The schema of the table containing the key
		table_name    -- The name of the table containing the key
		name          -- The name of the key
		owner*        -- The name of the user who owns the key
		system        -- True if the key is system maintained (bool)
		created*      -- When the key was created (datetime)
		description*  -- Descriptive text
		primary       -- True if the unique key is also a primary key (bool)

		* Optional (can be None)
		"""
		for row in super(InputPlugin, self).get_unique_keys():
			yield row
		cursor = self.connection.cursor()
		cursor.execute("""
			SELECT
				RTRIM(C.TBCREATOR)           AS TABSCHEMA,
				RTRIM(C.TBNAME)              AS TABNAME,
				RTRIM(C.CONSTNAME)           AS KEYNAME,
				C.CREATOR                    AS OWNER,
				CASE
					WHEN C.TBCREATOR LIKE 'SYS%' THEN 'Y'
					ELSE 'N'
				END                          AS SYSTEM,
				CHAR(C.CREATEDTS)            AS CREATED,
				CAST(NULL AS VARCHAR(762))   AS DESCRIPTION,
				CASE C.TYPE
					WHEN 'P' THEN 'Y'
					ELSE 'N'
				END                          AS PRIMARY
			FROM
				SYSIBM.SYSTABCONST C
				INNER JOIN SYSIBM.SYSTABLES T
					ON C.TBCREATOR = T.CREATOR
					AND C.TBNAME = T.NAME
			WHERE
				T.STATUS IN ('X', ' ')

			UNION ALL

			SELECT
				RTRIM(I.TBCREATOR)           AS TABSCHEMA,
				RTRIM(I.TBNAME)              AS TABNAME,
				RTRIM('IX:' || I.NAME)       AS KEYNAME,
				I.CREATEDBY                  AS OWNER,
				CASE
					WHEN I.TBCREATOR LIKE 'SYS%' THEN 'Y'
					ELSE 'N'
				END                          AS SYSTEM,
				CHAR(I.CREATEDTS)            AS CREATED,
				I.REMARKS                    AS DESCRIPTION,
				CHAR('Y')                    AS PRIMARY
			FROM
				SYSIBM.SYSINDEXES I
				INNER JOIN SYSIBM.SYSTABLES T
					ON I.TBCREATOR = T.CREATOR
					AND I.TBNAME = T.NAME
			WHERE
				I.UNIQUERULE = 'P'
				AND T.STATUS IN ('X', ' ')
				AND (I.TBCREATOR, I.TBNAME) NOT IN (SELECT TBCREATOR, TBNAME FROM SYSIBM.SYSTABCONST)
			WITH UR
		""")
		for (
				schema,
				name,
				keyname,
				owner,
				system,
				created,
				desc,
				primary,
			) in self.fetch_some(cursor):
			yield UniqueKey(
				schema,
				name,
				keyname,
				owner,
				make_bool(system),
				make_datetime(created),
				desc,
				make_bool(primary)
			)

	def get_unique_key_cols(self):
		"""Retrieves the list of columns belonging to unique keys.

		Override this function to return a list of UniqueKeyCol tuples
		detailing the columns that belong to each unique key in the database.
		The tuples contain the following named fields:

		const_schema -- The schema of the table containing the key
		const_table  -- The name of the table containing the key
		const_name   -- The name of the key
		name         -- The name of the column
		"""
		for row in super(InputPlugin, self).get_unique_key_cols():
			yield row
		cursor = self.connection.cursor()
		cursor.execute("""
			WITH COLS AS (
				SELECT
					TBCREATOR AS TABSCHEMA,
					TBNAME    AS TABNAME,
					CONSTNAME AS KEYNAME,
					COLNAME   AS COLNAME,
					COLSEQ    AS COLSEQ
				FROM
					SYSIBM.SYSKEYCOLUSE

				UNION ALL

				SELECT
					I.TBCREATOR     AS TABSCHEMA,
					I.TBNAME        AS TABNAME,
					'IX:' || I.NAME AS KEYNAME,
					K.COLNAME       AS COLNAME,
					K.COLSEQ        AS COLSEQ
				FROM
					SYSIBM.SYSINDEXES I
					INNER JOIN SYSIBM.SYSKEYS K
						ON I.CREATOR = K.IXCREATOR
						AND I.NAME = K.IXNAME
				WHERE
					(I.TBCREATOR, I.TBNAME) NOT IN (SELECT TBCREATOR, TBNAME FROM SYSIBM.SYSTABCONST)
			)
			SELECT
				RTRIM(TABSCHEMA) AS TABSCHEMA,
				RTRIM(TABNAME)   AS TABNAME,
				RTRIM(KEYNAME)   AS KEYNAME,
				COLNAME          AS COLNAME
			FROM
				COLS
			ORDER BY
				TABSCHEMA,
				TABNAME,
				KEYNAME,
				COLSEQ
			WITH UR
		""")
		for (
				schema,
				name,
				keyname,
				colname
			) in self.fetch_some(cursor):
			yield UniqueKeyCol(
				schema,
				name,
				keyname,
				colname
			)

	def get_foreign_keys(self):
		"""Retrieves the details of foreign keys stored in the database.

		Override this function to return a list of ForeignKey tuples containing
		details of the foreign keys defined in the database. ForeignKey tuples
		contain the following named fields:

		table_schema      -- The schema of the table containing the key
		table_name        -- The name of the table containing the key
		name              -- The name of the key
		owner*            -- The name of the user who owns the key
		system            -- True if the key is system maintained (bool)
		created*          -- When the key was created (datetime)
		description*      -- Descriptive text
		const_schema      -- The schema of the table the key references
		const_table       -- The name of the table the key references
		const_name        -- The name of the unique key that the key references
		delete_rule       -- The action to take on deletion of a parent key:
		                     'A' = No action
		                     'C' = Cascade
		                     'N' = Set NULL
		                     'R' = Restrict
		update_rule       -- The action to take on update of a parent key:
		                     'A' = No action
		                     'C' = Cascade
		                     'N' = Set NULL
		                     'R' = Restrict

		* Optional (can be None)
		"""
		for row in super(InputPlugin, self).get_foreign_keys():
			yield row
		cursor = self.connection.cursor()
		cursor.execute("""
			SELECT
				RTRIM(R.CREATOR)           AS TABSCHEMA,
				RTRIM(R.TBNAME)            AS TABNAME,
				RTRIM(R.RELNAME)           AS KEYNAME,
				T.CREATEDBY                AS OWNER,
				CASE
					WHEN R.CREATOR LIKE 'SYS%' THEN 'Y'
					ELSE 'N'
				END                        AS SYSTEM,
				CHAR(R.TIMESTAMP)          AS CREATED,
				CAST(NULL AS VARCHAR(762)) AS DESCRIPTION,
				RTRIM(R.REFTBCREATOR)      AS REFTABSCHEMA,
				RTRIM(R.REFTBNAME)         AS REFTABNAME,
				RTRIM(C.CONSTNAME)         AS REFKEYNAME,
				R.DELETERULE               AS DELETERULE,
				CAST('A' AS CHAR(1))       AS UPDATERULE
			FROM
				SYSIBM.SYSRELS R
				INNER JOIN SYSIBM.SYSTABLES T
					ON R.CREATOR = T.CREATOR
					AND R.TBNAME = T.NAME
				INNER JOIN SYSIBM.SYSTABCONST C
					ON R.IXOWNER = C.IXOWNER
					AND R.IXNAME = C.IXNAME
					AND NOT (R.IXOWNER = '99999999' AND R.IXNAME = '99999999')
					AND NOT (R.IXOWNER = '' AND R.IXNAME = '')
					AND NOT (C.IXOWNER = '' AND C.IXNAME = '')
			WHERE
				T.STATUS IN ('X', ' ')

			UNION ALL

			SELECT
				RTRIM(R.CREATOR)           AS TABSCHEMA,
				RTRIM(R.TBNAME)            AS TABNAME,
				RTRIM(R.RELNAME)           AS KEYNAME,
				T.CREATEDBY                AS OWNER,
				CASE
					WHEN R.CREATOR LIKE 'SYS%' THEN 'Y'
					ELSE 'N'
				END                        AS SYSTEM,
				CHAR(R.TIMESTAMP)          AS CREATED,
				CAST(NULL AS VARCHAR(762)) AS DESCRIPTION,
				RTRIM(R.REFTBCREATOR)      AS REFTABSCHEMA,
				RTRIM(R.REFTBNAME)         AS REFTABNAME,
				RTRIM(COALESCE(C.CONSTNAME, 'IX:' || I.NAME)) AS REFKEYNAME,
				R.DELETERULE               AS DELETERULE,
				CAST('A' AS CHAR(1))       AS UPDATERULE
			FROM
				SYSIBM.SYSRELS R
				INNER JOIN SYSIBM.SYSTABLES T
					ON R.CREATOR = T.CREATOR
					AND R.TBNAME = T.NAME
				INNER JOIN SYSIBM.SYSINDEXES I
					ON R.REFTBCREATOR = I.TBCREATOR
					AND R.REFTBNAME = I.TBNAME
					AND R.IXOWNER = ''
					AND R.IXNAME = ''
					AND I.UNIQUERULE = 'P'
				LEFT OUTER JOIN SYSIBM.SYSTABCONST C
					ON I.CREATOR = C.IXOWNER
					AND I.NAME = C.IXNAME
					AND NOT (C.IXOWNER = '' AND C.IXNAME = '')
			WHERE
				T.STATUS IN ('X', ' ')
			WITH UR
		""")
		for (
				schema,
				name,
				keyname,
				owner,
				system,
				created,
				desc,
				refschema,
				refname,
				refkeyname,
				deleterule,
				updaterule,
			) in self.fetch_some(cursor):
			yield ForeignKey(
				schema,
				name,
				keyname,
				owner,
				make_bool(system),
				make_datetime(created),
				desc,
				refschema,
				refname,
				refkeyname,
				deleterule,
				updaterule
			)

	def get_foreign_key_cols(self):
		"""Retrieves the list of columns belonging to foreign keys.

		Override this function to return a list of ForeignKeyCol tuples
		detailing the columns that belong to each foreign key in the database.
		ForeignKeyCol tuples contain the following named fields:

		const_schema -- The schema of the table containing the key
		const_table  -- The name of the table containing the key
		const_name   -- The name of the key
		name         -- The name of the column in the key
		ref_name     -- The name of the column that this column references in
		                the referenced key
		"""
		for row in super(InputPlugin, self).get_foreign_key_cols():
			yield row
		cursor = self.connection.cursor()
		cursor.execute("""
			WITH COLS AS (
				SELECT
					F.CREATOR          AS TABSCHEMA,
					F.TBNAME           AS TABNAME,
					F.RELNAME          AS KEYNAME,
					F.COLNAME          AS COLNAME,
					K.COLNAME          AS REFCOLNAME,
					F.COLSEQ           AS COLSEQ
				FROM
					SYSIBM.SYSFOREIGNKEYS F
					INNER JOIN SYSIBM.SYSTABLES T
						ON F.CREATOR = T.CREATOR
						AND F.TBNAME = T.NAME
					INNER JOIN SYSIBM.SYSRELS R
						ON F.CREATOR = R.CREATOR
						AND F.TBNAME = R.TBNAME
						AND F.RELNAME = R.RELNAME
					INNER JOIN SYSIBM.SYSTABCONST C
						ON R.IXOWNER = C.IXOWNER
						AND R.IXNAME = C.IXNAME
						AND NOT (R.IXOWNER = '99999999' AND R.IXNAME = '99999999')
						AND NOT (R.IXOWNER = '' AND R.IXNAME = '')
						AND NOT (C.IXOWNER = '' AND C.IXNAME = '')
					INNER JOIN SYSIBM.SYSKEYCOLUSE K
						ON C.TBCREATOR = K.TBCREATOR
						AND C.TBNAME = K.TBNAME
						AND C.CONSTNAME = K.CONSTNAME
						AND F.COLSEQ = K.COLSEQ
				WHERE
					T.STATUS IN ('X', ' ')

				UNION ALL

				SELECT
					F.CREATOR          AS TABSCHEMA,
					F.TBNAME           AS TABNAME,
					F.RELNAME          AS KEYNAME,
					F.COLNAME          AS COLNAME,
					K.COLNAME          AS REFCOLNAME,
					F.COLSEQ           AS COLSEQ
				FROM
					SYSIBM.SYSFOREIGNKEYS F
					INNER JOIN SYSIBM.SYSTABLES T
						ON F.CREATOR = T.CREATOR
						AND F.TBNAME = T.NAME
					INNER JOIN SYSIBM.SYSRELS R
						ON F.CREATOR = R.CREATOR
						AND F.TBNAME = R.TBNAME
						AND F.RELNAME = R.RELNAME
					INNER JOIN SYSIBM.SYSINDEXES I
						ON R.REFTBCREATOR = I.TBCREATOR
						AND R.REFTBNAME = I.TBNAME
						AND R.IXOWNER = ''
						AND R.IXNAME = ''
						AND I.UNIQUERULE = 'P'
					INNER JOIN SYSIBM.SYSKEYS K
						ON I.CREATOR = K.IXCREATOR
						AND I.NAME = K.IXNAME
						AND F.COLSEQ = K.COLSEQ
				WHERE
					T.STATUS IN ('X', ' ')
			)
			SELECT
				RTRIM(TABSCHEMA) AS TABSCHEMA,
				RTRIM(TABNAME)   AS TABNAME,
				RTRIM(KEYNAME)   AS KEYNAME,
				COLNAME          AS COLNAME,
				REFCOLNAME       AS REFCOLNAME
			FROM
				COLS
			ORDER BY
				TABSCHEMA,
				TABNAME,
				KEYNAME,
				COLSEQ
			WITH UR
		""")
		for (
				schema,
				name,
				keyname,
				colname,
				refcolname
			) in self.fetch_some(cursor):
			yield ForeignKeyCol(
				schema,
				name,
				keyname,
				colname,
				refcolname
			)

	def get_checks(self):
		"""Retrieves the details of checks stored in the database.

		Override this function to return a list of Check tuples containing
		details of the checks defined in the database. Check tuples contain the
		following named fields:

		table_schema  -- The schema of the table containing the check
		table_name    -- The name of the table containing the check
		name          -- The name of the check
		owner*        -- The name of the user who owns the check
		system        -- True if the check is system maintained (bool)
		created*      -- When the check was created (datetime)
		description*  -- Descriptive text
		sql*          -- The SQL expression that the check enforces

		* Optional (can be None)
		"""
		for row in super(InputPlugin, self).get_checks():
			yield row
		cursor = self.connection.cursor()
		cursor.execute("""
			SELECT
				RTRIM(C.TBOWNER)           AS TABSCHEMA,
				RTRIM(C.TBNAME)            AS TABNAME,
				RTRIM(C.CHECKNAME)         AS CHECKNAME,
				C.CREATOR                  AS OWNER,
				CASE
					WHEN C.TBOWNER LIKE 'SYS%' THEN 'Y'
					ELSE 'N'
				END                        AS SYSTEM,
				CHAR(C.TIMESTAMP)          AS CREATED,
				CAST(NULL AS VARCHAR(762)) AS DESCRIPTION,
				C.CHECKCONDITION           AS SQL
			FROM
				SYSIBM.SYSCHECKS C
				INNER JOIN SYSIBM.SYSTABLES T
					ON C.TBOWNER = T.CREATOR
					AND C.TBNAME = T.NAME
			WHERE
				T.STATUS IN ('X', ' ')
			WITH UR
		""")
		for (
				schema,
				name,
				checkname,
				owner,
				system,
				created,
				desc,
				sql,
			) in self.fetch_some(cursor):
			yield Check(
				schema,
				name,
				checkname,
				owner,
				make_bool(system),
				make_datetime(created),
				desc,
				str(sql)
			)

	def get_check_cols(self):
		"""Retrieves the list of columns belonging to checks.

		Override this function to return a list of CheckCol tuples detailing
		the columns that are referenced by each check in the database. CheckCol
		tuples contain the following named fields:

		const_schema -- The schema of the table containing the check
		const_table  -- The name of the table containing the check
		const_name   -- The name of the check
		name         -- The name of the column
		"""
		for row in super(InputPlugin, self).get_check_cols():
			yield row

	def get_functions(self):
		"""Retrieves the details of functions stored in the database.

		Override this function to return a list of Function tuples containing
		details of the functions defined in the database (including system
		functions). Function tuples contain the following named fields:

		schema         -- The schema of the function
		specific       -- The unique name of the function in the schema
		name           -- The (potentially overloaded) name of the function
		owner*         -- The name of the user who owns the function
		system         -- True if the function is system maintained (bool)
		created*       -- When the function was created (datetime)
		description*   -- Descriptive text
		deterministic* -- True if the function is deterministic (bool)
		ext_action*    -- True if the function has an external action (affects
		                  things outside the database) (bool)
		null_call*     -- True if the function is called on NULL input (bool)
		access*        -- 'N' if the function contains no SQL
		                  'C' if the function contains database independent SQL
		                  'R' if the function contains SQL that reads the db
		                  'M' if the function contains SQL that modifies the db
		sql*           -- The SQL statement that defined the function
		func_type      -- The type of the function:
		                  'C' = Column/aggregate function
		                  'R' = Row function
		                  'T' = Table function
		                  'S' = Scalar function

		* Optional (can be None)
		"""
		for row in super(InputPlugin, self).get_functions():
			yield row
		cursor = self.connection.cursor()
		cursor.execute("""
			SELECT
				RTRIM(SCHEMA)                AS FUNCSCHEMA,
				RTRIM(SPECIFICNAME)          AS FUNCSPECNAME,
				RTRIM(NAME)                  AS FUNCNAME,
				OWNER                        AS OWNER,
				CASE
					WHEN SCHEMA LIKE 'SYS%' THEN 'Y'
					WHEN ORIGIN = 'S' THEN 'Y'
					ELSE 'N'
				END                          AS SYSTEM,
				CHAR(CREATEDTS)              AS CREATED,
				REMARKS                      AS DESCRIPTION,
				DETERMINISTIC                AS DETERMINISTIC,
				EXTERNAL_ACTION              AS EXTACTION,
				CASE ORIGIN
					WHEN 'Q' THEN 'Y'
					ELSE NULL_CALL
				END                          AS NULLCALL,
				NULLIF(SQL_DATA_ACCESS, ' ') AS ACCESS,
				CAST(NULL AS VARCHAR(10))    AS SQL,
				FUNCTION_TYPE                AS FUNCTYPE
			FROM
				SYSIBM.SYSROUTINES
			WHERE
				ROUTINETYPE = 'F'
			WITH UR
		""")
		for (
				schema,
				specname,
				name,
				owner,
				system,
				created,
				desc,
				deterministic,
				extaction,
				nullcall,
				access,
				sql,
				functype,
			) in self.fetch_some(cursor):
			yield Function(
				schema,
				specname,
				name,
				owner,
				make_bool(system),
				make_datetime(created),
				desc,
				make_bool(deterministic),
				make_bool(extaction, true_value='E'),
				make_bool(nullcall),
				access,
				str(sql),
				functype
			)

	def get_procedures(self):
		"""Retrieves the details of stored procedures in the database.

		Override this function to return a list of Procedure tuples containing
		details of the procedures defined in the database (including system
		procedures). Procedure tuples contain the following named fields:

		schema         -- The schema of the procedure
		specific       -- The unique name of the procedure in the schema
		name           -- The (potentially overloaded) name of the procedure
		owner*         -- The name of the user who owns the procedure
		system         -- True if the procedure is system maintained (bool)
		created*       -- When the procedure was created (datetime)
		description*   -- Descriptive text
		deterministic* -- True if the procedure is deterministic (bool)
		ext_action*    -- True if the procedure has an external action (affects
		                  things outside the database) (bool)
		null_call*     -- True if the procedure is called on NULL input
		access*        -- 'N' if the procedure contains no SQL
		                  'C' if the procedure contains database independent SQL
		                  'R' if the procedure contains SQL that reads the db
		                  'M' if the procedure contains SQL that modifies the db
		sql*           -- The SQL statement that defined the procedure

		* Optional (can be None)
		"""
		for row in super(InputPlugin, self).get_procedures():
			yield row
		cursor = self.connection.cursor()
		cursor.execute("""
			SELECT
				RTRIM(SCHEMA)                AS PROCSCHEMA,
				RTRIM(SPECIFICNAME)          AS PROCSPECNAME,
				RTRIM(NAME)                  AS PROCNAME,
				OWNER                        AS OWNER,
				CASE
					WHEN SCHEMA LIKE 'SYS%' THEN 'Y'
					WHEN ORIGIN = 'S' THEN 'Y'
					ELSE 'N'
				END                          AS SYSTEM,
				CHAR(CREATEDTS)              AS CREATED,
				REMARKS                      AS DESCRIPTION,
				DETERMINISTIC                AS DETERMINISTIC,
				EXTERNAL_ACTION              AS EXTACTION,
				CASE ORIGIN
					WHEN 'Q' THEN 'Y'
					ELSE NULL_CALL
				END                          AS NULLCALL,
				NULLIF(SQL_DATA_ACCESS, ' ') AS ACCESS,
				CAST(NULL AS VARCHAR(10))    AS SQL
			FROM
				SYSIBM.SYSROUTINES
			WHERE
				ROUTINETYPE = 'P'
			WITH UR
		""")
		for (
				schema,
				specname,
				name,
				owner,
				system,
				created,
				desc,
				deterministic,
				extaction,
				nullcall,
				access,
				sql,
			) in self.fetch_some(cursor):
			yield Procedure(
				schema,
				specname,
				name,
				owner,
				make_bool(system),
				make_datetime(created),
				desc,
				make_bool(deterministic),
				make_bool(extaction, true_value='E'),
				make_bool(nullcall),
				access,
				str(sql),
			)

	def get_routine_params(self):
		"""Retrieves the list of parameters belonging to routines.

		Override this function to return a list of RoutineParam tuples
		detailing the parameters that are associated with each routine in the
		database. RoutineParam tuples contain the following named fields:

		routine_schema   -- The schema of the routine
		routine_specific -- The unique name of the routine in the schema
		param_name       -- The name of the parameter
		type_schema      -- The schema of the parameter's datatype
		type_name        -- The name of the parameter's datatype
		size*            -- The length of the parameter for character types, or
		                    the numeric precision for decimal types (None if not
		                    a character or decimal type)
		scale*           -- The maximum scale for decimal types (None if not a
		                    decimal type)
		codepage*        -- The codepage of the parameter for character types
		                    (None if not a character type)
		direction        -- 'I' = Input parameter
		                    'O' = Output parameter
		                    'B' = Input & output parameter
		                    'R' = Return value/column
		description*     -- Descriptive text

		Note that the each tuple details one parameter belonging to a routine.
		It is important that the list of tuples is in the order that each
		parameter is declared in the routine.

		This is slightly complicated by the fact that the return column(s) of a
		routine are also considered parameters (see the direction field above).
		It does not matter if parameters and return columns are interspersed in
		the result provided that, taken separately, each set of parameters or
		columns is in the correct order.

		* Optional (can be None)
		"""
		for row in super(InputPlugin, self).get_routine_params():
			yield row
		cursor = self.connection.cursor()
		cursor.execute("""
			SELECT
				RTRIM(SCHEMA)                   AS ROUTINESCHEMA,
				RTRIM(SPECIFICNAME)             AS ROUTINESPECNAME,
				PARMNAME                        AS PARMNAME,
				RTRIM(TYPESCHEMA)               AS TYPESCHEMA,
				CASE RTRIM(TYPESCHEMA)
					WHEN 'SYSIBM' THEN
						CASE TYPENAME
							WHEN 'LONGVAR'  THEN 'LONG VARCHAR'
							WHEN 'CHAR'     THEN 'CHARACTER'
							WHEN 'VARG'     THEN 'VARGRAPHIC'
							WHEN 'LONGVARG' THEN 'LONG VARGRAPHIC'
							WHEN 'TIMESTMP' THEN 'TIMESTAMP'
							WHEN 'FLOAT'    THEN
								CASE LENGTH
									WHEN 4 THEN 'REAL'
									WHEN 8 THEN 'DOUBLE'
								END
							ELSE RTRIM(TYPENAME)
						END
					ELSE RTRIM(TYPENAME)
				END                             AS TYPENAME,
				LENGTH                          AS SIZE,
				SCALE                           AS SCALE,
				CCSID                           AS CODEPAGE,
				CASE ROWTYPE
					WHEN 'S' THEN 'I'
					WHEN 'P' THEN 'I'
					WHEN 'C' THEN 'R'
					ELSE ROWTYPE
				END                             AS DIRECTION,
				CAST(NULL AS VARCHAR(762))      AS DESCRIPTION
			FROM
				SYSIBM.SYSPARMS
			WHERE
				ROUTINETYPE IN ('F', 'P')
				AND ROWTYPE <> 'X'
			ORDER BY
				SCHEMA,
				SPECIFICNAME,
				ORDINAL
			WITH UR
		""")
		for (
				schema,
				specname,
				parmname,
				typeschema,
				typename,
				size,
				scale,
				codepage,
				direction,
				desc
			) in self.fetch_some(cursor):
			yield RoutineParam(
				schema,
				specname,
				parmname,
				typeschema,
				typename,
				size or None,
				scale or None, # XXX Not necessarily unknown (0 is a valid scale)
				codepage or None,
				direction,
				desc
			)

	def get_triggers(self):
		"""Retrieves the details of table triggers in the database.

		Override this function to return a list of Trigger tuples containing
		details of the triggers defined in the database (including system
		triggers). Trigger tuples contain the following named fields:

		schema          -- The schema of the trigger
		name            -- The unique name of the trigger in the schema
		owner*          -- The name of the user who owns the trigger
		system          -- True if the trigger is system maintained (bool)
		created*        -- When the trigger was created (datetime)
		description*    -- Descriptive text
		relation_schema -- The schema of the relation that activates the trigger
		relation_name   -- The name of the relation that activates the trigger
		when            -- When the trigger is fired:
		                   'A' = After the event
		                   'B' = Before the event
		                   'I' = Instead of the event
		event           -- What statement fires the trigger:
		                   'I' = The trigger fires on INSERT
		                   'U' = The trigger fires on UPDATE
		                   'D' = The trigger fires on DELETE
		granularity     -- The granularity of trigger executions:
		                   'R' = The trigger fires for each row affected
		                   'S' = The trigger fires once per activating statement
		sql*            -- The SQL statement that defined the trigger

		* Optional (can be None)
		"""
		for row in super(InputPlugin, self).get_triggers():
			yield row
		cursor = self.connection.cursor()
		cursor.execute("""
			SELECT
				RTRIM(SCHEMA)      AS TRIGSCHEMA,
				RTRIM(NAME)        AS TRIGNAME,
				OWNER              AS OWNER,
				CASE
					WHEN SCHEMA LIKE 'SYS%%' THEN 'Y'
					ELSE 'N'
				END                AS SYSTEM,
				CHAR(CREATEDTS)    AS CREATED,
				REMARKS            AS DESCRIPTION,
				RTRIM(TBOWNER)     AS TABSCHEMA,
				RTRIM(TBNAME)      AS TABNAME,
				TRIGTIME           AS TRIGTIME,
				TRIGEVENT          AS TRIGEVENT,
				GRANULARITY        AS GRANULARITY,
				TEXT               AS SQL
			FROM
				SYSIBM.SYSTRIGGERS
			ORDER BY
				SCHEMA,
				NAME,
				SEQNO
			WITH UR
		""")
		for (k, v) in groupby(self.fetch_some(cursor), key=itemgetter(0, 1)):
			v = list(v)
			(
				schema,
				name,
				owner,
				system,
				created,
				desc,
				tabschema,
				tabname,
				trigtime,
				trigevent,
				granularity,
				sql,
			) = v[0]
			sql = ''.join(i[-1] for i in v)
			yield Trigger(
				schema,
				name,
				owner,
				make_bool(system),
				make_datetime(created),
				desc,
				tabschema,
				tabname,
				trigtime,
				trigevent,
				granularity,
				str(sql)
			)

	def get_trigger_dependencies(self):
		"""Retrieves the details of trigger dependencies.

		Override this function to return a list of TriggerDep tuples containing
		details of the relations upon which triggers depend (the tables that a
		trigger references in its body). TriggerDep tuples contain the
		following named fields:

		trig_schema  -- The schema of the trigger
		trig_name    -- The name of the trigger
		dep_schema   -- The schema of the relation upon which the trigger depends
		dep_name     -- The name of the relation upon which the trigger depends
		"""
		for row in super(InputPlugin, self).get_trigger_dependencies():
			yield row
		cursor = self.connection.cursor()
		cursor.execute("""
			SELECT
				RTRIM(T.SCHEMA)     AS TRIGSCHEMA,
				RTRIM(T.NAME)       AS TRIGNAME,
				RTRIM(D.BQUALIFIER) AS DEPSCHEMA,
				RTRIM(D.BNAME)      AS DEPNAME
			FROM
				SYSIBM.SYSTRIGGERS T
				INNER JOIN SYSIBM.SYSPACKDEP D
					ON T.SCHEMA = D.DCOLLID
					AND T.NAME = D.DNAME
					AND T.SEQNO = 1
					AND D.DTYPE = 'T'
			WHERE
				D.BTYPE IN ('A', 'M', 'S', 'T', 'V')
				AND NOT (D.BQUALIFIER = T.TBOWNER AND D.BNAME = T.TBNAME)
			WITH UR
		""")
		for (
				schema,
				name,
				depschema,
				depname
			) in self.fetch_some(cursor):
			yield TriggerDep(
				schema,
				name,
				depschema,
				depname
			)

	def get_tablespaces(self):
		"""Retrieves the details of the tablespaces in the database.

		Override this function to return a list of Tablespace tuples containing
		details of the tablespaces defined in the database (including system
		tablespaces). Tablespace tuples contain the following named fields:

		tbspace       -- The tablespace name
		owner*        -- The name of the user who owns the tablespace
		system        -- True if the tablespace is system maintained (bool)
		created*      -- When the tablespace was created (datetime)
		description*  -- Descriptive text
		type*         -- The type of the tablespace as free text

		* Optional (can be None)
		"""
		for row in super(InputPlugin, self).get_tablespaces():
			yield row
		cursor = self.connection.cursor()
		cursor.execute("""
			SELECT
				RTRIM(NAME)                AS TBSPACE,
				CREATOR                    AS OWNER,
				CASE
					WHEN NAME LIKE 'SYS%' THEN 'Y'
					ELSE 'N'
				END                        AS SYSTEM,
				CHAR(CREATEDTS)            AS CREATED,
				CAST(NULL AS VARCHAR(762)) AS DESCRIPTION,
				CASE
					WHEN PARTITIONS = 0 THEN 'Non-partitioned'
					ELSE 'Partitioned'
				END ||
				' ' ||
				CASE TYPE
					WHEN ' ' THEN 'regular'
					WHEN 'L' THEN 'large'
					WHEN 'O' THEN 'LOB'
					WHEN 'I' THEN 'member cluster'
					WHEN 'K' THEN 'member cluster'
				END ||
				' ' ||
				CASE ENCODING_SCHEME
					WHEN ' ' THEN 'temporary/work-file'
					WHEN 'A' THEN 'ASCII'
					WHEN 'E' THEN 'EBCDIC'
					WHEN 'U' THEN 'Unicode'
				END ||
				' tablespace with ' ||
				RTRIM(CHAR(PGSIZE)) ||
				'k page size and ' ||
				CASE LOCKRULE
					WHEN 'A' THEN 'any size'
					WHEN 'L' THEN 'LOB'
					WHEN 'P' THEN 'page'
					WHEN 'R' THEN 'row'
					WHEN 'S' THEN 'tablespace'
					WHEN 'T' THEN 'table'
				END ||
				' locks'                   AS TYPE
			FROM
				SYSIBM.SYSTABLESPACE
			WITH UR
		""")
		for (
				tbspace,
				owner,
				system,
				created,
				desc,
				tstype,
			) in self.fetch_some(cursor):
			yield Tablespace(
				tbspace,
				owner,
				make_bool(system),
				make_datetime(created),
				desc,
				tstype
			)

