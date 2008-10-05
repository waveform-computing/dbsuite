# vim: set noet sw=4 ts=4:

"""Input plugin for IBM DB2 for z/OS."""

import logging
import re
import db2makedoc.plugins
from db2makedoc.plugins.db2 import connect, make_datetime, make_bool


class InputPlugin(db2makedoc.plugins.InputPlugin):
	"""Input plugin for IBM DB2 for z/OS.

	This input plugin supports extracting documentation information from IBM
	DB2 for z/OS version 8 or above. If the DOCCAT schema (see the
	doccat_create.sql script in the contrib/db2/zos directory) is present, it
	will be used to source documentation data instead of SYSIBM.
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

		Override this function to return a list of tuples containing details of
		the schemas defined in the database. The tuples contain the following
		details in the order specified:

		name         -- The name of the schema
		owner*       -- The name of the user who owns the schema
		system       -- True if the schema is system maintained (boolean)
		created*     -- When the schema was created (datetime)
		description* -- Descriptive text

		* Optional (can be None)
		"""
		result = super(InputPlugin, self).get_schemas()
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
				S.SCHEMA                 AS NAME,
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
			) in cursor.fetchall():
			result.append((
				name,
				owner,
				make_bool(system),
				make_datetime(created),
				desc
			))
		return result

	def get_datatypes(self):
		"""Retrieves the details of datatypes stored in the database.

		Override this function to return a list of tuples containing details of
		the datatypes defined in the database (including system types). The
		tuples contain the following details in the order specified:

		schema         -- The schema of the datatype
		name           -- The name of the datatype
		owner*         -- The name of the user who owns the datatype
		system         -- True if the type is system maintained (boolean)
		created*       -- When the type was created (datetime)
		var_size       -- True if the type has a variable length (e.g. VARCHAR)
		var_scale      -- True if the type has a variable scale (e.g. DECIMAL)
		source_schema* -- The schema of the base system type of the datatype
		source_name*   -- The name of the base system type of the datatype
		size*          -- The length of the type for character based types or
		                  the maximum precision for decimal types
		scale*         -- The maximum scale for decimal types
		description*   -- Descriptive text

		* Optional (can be None)
		"""
		result = super(InputPlugin, self).get_datatypes()
		cursor = self.connection.cursor()
		cursor.execute("""
			WITH SYSTEM_TYPES AS (
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
						ELSE COLTYPE
					END                               AS TYPENAME,
					'SYSIBM'                          AS OWNER,
					CHAR('Y')                         AS SYSTEM,
					CHAR(TIMESTAMP('19850401000000')) AS CREATED,
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
					CAST(0 AS SMALLINT)               AS SCALE,
					CAST(NULL AS VARCHAR(762))        AS DESCRIPTION
				FROM
					SYSIBM.SYSCOLUMNS
				WHERE
					SOURCETYPEID = 0
			),
			USER_TYPES AS (
				SELECT
					SCHEMA          AS TYPESCHEMA,
					NAME            AS TYPENAME,
					OWNER           AS OWNER,
					CHAR('N')       AS SYSTEM,
					CHAR(CREATEDTS) AS CREATED,
					SOURCESCHEMA    AS SOURCESCHEMA,
					SOURCETYPE      AS SOURCENAME,
					LENGTH          AS SIZE,
					SCALE           AS SCALE,
					REMARKS         AS DESCRIPTION
				FROM
					SYSIBM.SYSDATATYPES
			)
			SELECT * FROM SYSTEM_TYPES
			UNION ALL
			SELECT * FROM USER_TYPES
			WITH UR
		""")
		for (
				schema,
				name,
				owner,
				system,
				created,
				source_schema,
				source_name,
				size,
				scale,
				desc
			) in cursor.fetchall():
			system = make_bool(system)
			result.append((
				schema,
				name,
				owner,
				system,
				make_datetime(created),
				system and not size and (name not in ('XML', 'REFERENCE')),
				system and (name == 'DECIMAL'),
				source_schema,
				source_name,
				size or None,
				scale or None, # XXX Not necessarily unknown (0 is a valid scale)
				desc
			))
		return result

	def get_tables(self):
		"""Retrieves the details of tables stored in the database.

		Override this function to return a list of tuples containing details of
		the tables (NOT views) defined in the database (including system
		tables). The tuples contain the following details in the order
		specified:

		schema        -- The schema of the table
		name          -- The name of the table
		owner*        -- The name of the user who owns the table
		system        -- True of the table is system maintained (boolean)
		created*      -- When the table was created (datetime)
		laststats*    -- When the table's statistics were last calculated (datetime)
		cardinality*  -- The approximate number of rows in the table
		size*         -- The approximate size in bytes of the table
		tbspace       -- The name of the primary tablespace containing the table
		description*  -- Descriptive text

		* Optional (can be None)
		"""
		result = super(InputPlugin, self).get_tables()
		cursor = self.connection.cursor()
		cursor.execute("""
			SELECT
				CREATOR                            AS TABSCHEMA,
				NAME                               AS TABNAME,
				CREATEDBY                          AS OWNER,
				CASE
					WHEN CREATOR LIKE 'SYS%' THEN 'Y'
					ELSE 'N'
				END                                AS SYSTEM,
				CHAR(CREATEDTS)                    AS CREATED,
				CHAR(STATSTIME)                    AS LASTSTATS,
				NULLIF(DECIMAL(CARDF), -1)         AS CARDINALITY,
				NULLIF(DECIMAL(SPACEF), -1) * 1024 AS SIZE,
				TSNAME                             AS TBSPACE,
				REMARKS                            AS DESCRIPTION
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
				laststats,
				cardinality,
				size,
				tbspace,
				desc
			) in cursor.fetchall():
			result.append((
				schema,
				name,
				owner,
				make_bool(system),
				make_datetime(created),
				make_datetime(laststats),
				cardinality,
				size,
				tbspace,
				desc
			))
		return result

	def get_views(self):
		"""Retrieves the details of views stored in the database.

		Override this function to return a list of tuples containing details of
		the views defined in the database (including system views). The tuples
		contain the following details in the order specified:

		schema        -- The schema of the view
		name          -- The name of the view
		owner*        -- The name of the user who owns the view
		system        -- True of the view is system maintained (boolean)
		created*      -- When the view was created (datetime)
		readonly*     -- True if the view is not updateable (boolean)
		sql*          -- The SQL statement/query that defined the view
		description*  -- Descriptive text

		* Optional (can be None)
		"""
		result = super(InputPlugin, self).get_views()
		cursor = self.connection.cursor()
		cursor.execute("""
			SELECT
				V.CREATOR             AS VIEWSCHEMA,
				V.NAME                AS VIEWNAME,
				T.CREATEDBY           AS OWNER,
				CASE
					WHEN V.CREATOR LIKE 'SYS%' THEN 'Y'
					ELSE 'N'
				END                   AS SYSTEM,
				CHAR(T.CREATEDTS)     AS CREATED,
				CAST(NULL AS CHAR(1)) AS READONLY,
				V.TEXT                AS SQL,
				T.REMARKS             AS DESCRIPTION
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
		last_view = ('', '')
		sql = ''
		for (
				schema,
				name,
				owner,
				system,
				created,
				readonly,
				sqlchunk,
				desc
			) in cursor.fetchall():
			if last_view != (schema, name):
				if last_view[0]:
					result.append((
						schema,
						name,
						owner,
						make_bool(system),
						make_datetime(created),
						make_bool(readonly),
						str(sql),
						desc
					))
				last_view = (schema, name)
				sql = sqlchunk
			else:
				sql += sqlchunk
		if last_view[0]:
			result.append((
				schema,
				name,
				owner,
				make_bool(system),
				make_datetime(created),
				make_bool(readonly),
				str(sql),
				desc
			))
		return result

	def get_aliases(self):
		"""Retrieves the details of aliases stored in the database.

		Override this function to return a list of tuples containing details of
		the aliases (also known as synonyms in some systems) defined in the
		database (including system aliases). The tuples contain the following
		details in the order specified:

		schema        -- The schema of the alias
		name          -- The name of the alias
		owner*        -- The name of the user who owns the alias
		system        -- True of the alias is system maintained (boolean)
		created*      -- When the alias was created (datetime)
		base_schema   -- The schema of the target relation
		base_table    -- The name of the target relation
		description*  -- Descriptive text

		* Optional (can be None)
		"""
		result = super(InputPlugin, self).get_aliases()
		cursor = self.connection.cursor()
		cursor.execute("""
			SELECT
				CREATOR          AS ALIASSCHEMA,
				NAME             AS ALIASNAME,
				CREATEDBY        AS OWNER,
				CASE
					WHEN CREATOR LIKE 'SYS%' THEN 'Y'
					ELSE 'N'
				END              AS SYSTEM,
				CHAR(CREATEDTS)  AS CREATED,
				TBCREATOR        AS BASESCHEMA,
				TBNAME           AS BASETABLE,
				REMARKS          AS DESCRIPTION
			FROM
				SYSIBM.SYSTABLES
			WHERE
				TYPE = 'A'

			UNION ALL

			SELECT
				CREATOR          AS ALIASSCHEMA,
				NAME             AS ALIASNAME,
				CREATEDBY        AS OWNER,
				CASE
					WHEN CREATOR LIKE 'SYS%' THEN 'Y'
					ELSE 'N'
				END              AS SYSTEM,
				CHAR(CREATEDTS)  AS CREATED,
				TBCREATOR        AS BASESCHEMA,
				TBNAME           AS BASETABLE,
				CAST(NULL AS VARCHAR(762)) AS DESCRIPTION
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
				base_schema,
				base_table,
				desc
			) in cursor.fetchall():
			result.append((
				schema,
				name,
				owner,
				make_bool(system),
				make_datetime(created),
				base_schema,
				base_table,
				desc
			))
		return result

	def get_view_dependencies(self):
		"""Retrieves the details of view dependencies.

		Override this function to return a list of tuples containing details of
		the relations upon which views depend (the tables and views that a view
		references in its query).  The tuples contain the following details in
		the order specified:

		schema       -- The schema of the view
		name         -- The name of the view
		dep_schema   -- The schema of the relation upon which the view depends
		dep_name     -- The name of the relation upon which the view depends
		"""
		result = super(InputPlugin, self).get_view_dependencies()
		cursor = self.connection.cursor()
		cursor.execute("""
			SELECT
				DCREATOR AS VIEWSCHEMA,
				DNAME    AS VIEWNAME,
				BCREATOR AS DEPSCHEMA,
				BNAME    AS DEPNAME
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
			) in cursor.fetchall():
			result.append((
				schema,
				name,
				depschema,
				depname
			))
		return result

	def get_indexes(self):
		"""Retrieves the details of indexes stored in the database.

		Override this function to return a list of tuples containing details of
		the indexes defined in the database (including system indexes). The
		tuples contain the following details in the order specified:

		schema        -- The schema of the index
		name          -- The name of the index
		tabschema     -- The schema of the table the index belongs to
		tabname       -- The name of the table the index belongs to
		owner*        -- The name of the user who owns the index
		system        -- True of the index is system maintained (boolean)
		created*      -- When the index was created (datetime)
		laststats*    -- When the index statistics were last updated (datetime)
		cardinality*  -- The approximate number of values in the index
		size*         -- The approximate size in bytes of the index
		unique        -- True if the index contains only unique values (boolean)
		tbspace       -- The name of the tablespace which contains the index
		description*  -- Descriptive text

		* Optional (can be None)
		"""
		result = super(InputPlugin, self).get_indexes()
		cursor = self.connection.cursor()
		cursor.execute("""
			SELECT
				I.CREATOR                            AS INDSCHEMA,
				I.NAME                               AS INDNAME,
				I.TBCREATOR                          AS TABSCHEMA,
				I.NAME                               AS TABNAME,
				I.CREATEDBY                          AS OWNER,
				CASE
					WHEN I.CREATOR LIKE 'SYS%' THEN 'Y'
					ELSE 'N'
				END                                  AS SYSTEM,
				CHAR(I.CREATEDTS)                    AS CREATED,
				CHAR(I.STATSTIME)                    AS LASTSTATS,
				NULLIF(DECIMAL(I.FULLKEYCARDF), -1)  AS CARD,
				NULLIF(DECIMAL(I.SPACEF), -1) * 1024 AS SIZE,
				CASE I.UNIQUERULE
					WHEN 'D' THEN 'N'
					ELSE 'Y'
				END                                  AS UNIQUE,
				I.INDEXSPACE                         AS TBSPACE,
				I.REMARKS                            AS DESCRIPTION
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
				tabschema,
				tabname,
				owner,
				system,
				created,
				laststats,
				card,
				size,
				unique,
				tbspace,
				desc
			) in cursor.fetchall():
			result.append((
				schema,
				name,
				tabschema,
				tabname,
				owner,
				make_bool(system),
				make_datetime(created),
				make_datetime(laststats),
				card,
				size,
				make_bool(unique),
				tbspace,
				desc
			))
		return result

	def get_index_cols(self):
		"""Retrieves the list of columns belonging to indexes.

		Override this function to return a list of tuples detailing the columns
		that belong to each index in the database (including system indexes).
		The tuples contain the following details in the order specified:

		schema       -- The schema of the index
		name         -- The name of the index
		colname      -- The name of the column
		colorder     -- The ordering of the column in the index:
		                'A'=Ascending
		                'D'=Descending
		                'I'=Include (not an index key)

		Note that the each tuple details one column belonging an index. It is
		important that the list of tuples is in the order that each column is
		declared in an index.
		"""
		result = super(InputPlugin, self).get_index_cols()
		cursor = self.connection.cursor()
		cursor.execute("""
			SELECT
				K.IXCREATOR AS INDSCHEMA,
				K.IXNAME    AS INDNAME,
				K.COLNAME   AS COLNAME,
				K.ORDERING  AS COLORDER
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
			) in cursor.fetchall():
			result.append((
				schema,
				name,
				colname,
				colorder
			))
		return result

	def get_relation_cols(self):
		"""Retrieves the list of columns belonging to relations.

		Override this function to return a list of tuples detailing the columns
		that belong to each relation (table, view, etc.) in the database
		(including system relations).  The tuples contain the following details
		in the order specified:

		schema        -- The schema of the table
		name          -- The name of the table
		colname       -- The name of the column
		typeschema    -- The schema of the column's datatype
		typename      -- The name of the column's datatype
		identity*     -- True if the column is an identity column (boolean)
		size*         -- The length of the column for character types, or the
		                 numeric precision for decimal types (None if not a
		                 character or decimal type)
		scale*        -- The maximum scale for decimal types (None if not a
		                 decimal type)
		codepage*     -- The codepage of the column for character types (None
		                 if not a character type)
		nullable*     -- True if the column can store NULL (boolean)
		cardinality*  -- The approximate number of unique values in the column
		nullcard*     -- The approximate number of NULLs in the column
		generated     -- 'A' if the column is always generated
		                 'D' if the column is generated by default
		                 'N' if the column is not generated
		default*      -- If generated is 'N', the default value of the column
		                 (expressed as SQL). Otherwise, the SQL expression that
		                 generates the column's value (or default value). None
		                 if the column has no default
		description*  -- Descriptive text

		Note that the each tuple details one column belonging to a relation. It
		is important that the list of tuples is in the order that each column
		is declared in a relation.

		* Optional (can be None)
		"""
		result = super(InputPlugin, self).get_relation_cols()
		cursor = self.connection.cursor()
		cursor.execute("""
			SELECT
				C.TBCREATOR                                    AS TABSCHEMA,
				C.TBNAME                                       AS TABNAME,
				C.NAME                                         AS COLNAME,
				CASE C.SOURCETYPEID
					WHEN 0 THEN 'SYSIBM'
					ELSE C.TYPESCHEMA
				END                                            AS TYPESCHEMA,
				CASE C.SOURCETYPEID
					WHEN 0 THEN
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
							ELSE C.COLTYPE
						END
					ELSE C.TYPENAME
				END                                            AS TYPENAME,
				CASE C.DEFAULT
					WHEN 'A' THEN 'Y'
					WHEN 'D' THEN 'Y'
					WHEN 'I' THEN 'Y'
					WHEN 'J' THEN 'Y'
					ELSE 'N'
				END                                            AS IDENTITY,
				C.LENGTH                                       AS SIZE,
				C.SCALE                                        AS SCALE,
				C.CCSID                                        AS CODEPAGE,
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
				identity,
				size,
				scale,
				codepage,
				nullable,
				cardinality,
				nullcard,
				generated,
				default,
				desc
			) in cursor.fetchall():
			if generated != 'N':
				default = re.sub(r'^\s*AS\s*', '', str(default))
			result.append((
				schema,
				name,
				colname,
				typeschema,
				typename,
				make_bool(identity),
				size,
				scale,
				codepage or None,
				make_bool(nullable),
				cardinality,
				nullcard,
				generated,
				default,
				desc
			))
		return result

	def get_unique_keys(self):
		"""Retrieves the details of unique keys stored in the database.

		Override this function to return a list of tuples containing details of
		the unique keys defined in the database. The tuples contain the
		following details in the order specified:

		schema        -- The schema of the table containing the key
		name          -- The name of the table containing the key
		keyname       -- The name of the key
		owner*        -- The name of the user who owns the key
		system        -- True of the key is system maintained (boolean)
		created*      -- When the key was created (datetime)
		primary       -- True if the unique key is also a primary key
		description*  -- Descriptive text

		* Optional (can be None)
		"""
		result = super(InputPlugin, self).get_unique_keys()
		cursor = self.connection.cursor()
		cursor.execute("""
			SELECT
				C.TBCREATOR                  AS TABSCHEMA,
				C.TBNAME                     AS TABNAME,
				C.CONSTNAME                  AS KEYNAME,
				C.CREATOR                    AS OWNER,
				CASE
					WHEN C.TBCREATOR LIKE 'SYS%' THEN 'Y'
					ELSE 'N'
				END                          AS SYSTEM,
				CHAR(C.CREATEDTS)            AS CREATED,
				CASE C.TYPE
					WHEN 'P' THEN 'Y'
					ELSE 'N'
				END                          AS PRIMARY,
				CAST(NULL AS VARCHAR(762))   AS DESCRIPTION
			FROM
				SYSIBM.SYSTABCONST C
				INNER JOIN SYSIBM.SYSTABLES T
					ON C.TBCREATOR = T.CREATOR
					AND C.TBNAME = T.NAME
			WHERE
				T.STATUS IN ('X', ' ')

			UNION ALL

			SELECT
				I.TBCREATOR                  AS TABSCHEMA,
				I.TBNAME                     AS TABNAME,
				'IX:' || I.NAME              AS KEYNAME,
				I.CREATEDBY                  AS OWNER,
				CASE
					WHEN I.TBCREATOR LIKE 'SYS%' THEN 'Y'
					ELSE 'N'
				END                          AS SYSTEM,
				CHAR(I.CREATEDTS)            AS CREATED,
				CHAR('Y')                    AS PRIMARY,
				I.REMARKS                    AS DESCRIPTION
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
				primary,
				desc
			) in cursor.fetchall():
			result.append((
				schema,
				name,
				keyname,
				owner,
				make_bool(system),
				make_datetime(created),
				make_bool(primary),
				desc
			))
		return result

	def get_unique_key_cols(self):
		"""Retrieves the list of columns belonging to unique keys.

		Override this function to return a list of tuples detailing the columns
		that belong to each unique key in the database.  The tuples contain the
		following details in the order specified:

		schema       -- The schema of the table containing the key
		name         -- The name of the table containing the key
		keyname      -- The name of the key
		colname      -- The name of the column
		"""
		result = super(InputPlugin, self).get_unique_key_cols()
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
				TABSCHEMA,
				TABNAME,
				KEYNAME,
				COLNAME
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
			) in cursor.fetchall():
			result.append((
				schema,
				name,
				keyname,
				colname
			))
		return result

	def get_foreign_keys(self):
		"""Retrieves the details of foreign keys stored in the database.

		Override this function to return a list of tuples containing details of
		the foreign keys defined in the database. The tuples contain the
		following details in the order specified:

		schema        -- The schema of the table containing the key
		name          -- The name of the table containing the key
		keyname       -- The name of the key
		owner*        -- The name of the user who owns the key
		system        -- True of the key is system maintained (boolean)
		created*      -- When the key was created (datetime)
		refschema     -- The schema of the table the key references
		refname       -- The name of the table the key references
		refkeyname    -- The name of the unique key that the key references
		deleterule    -- The action to take on deletion of a parent key
		                 'A' = No action
		                 'C' = Cascade
		                 'N' = Set NULL
		                 'R' = Restrict
		updaterule    -- The action to take on update of a parent key
		                 'A' = No action
		                 'C' = Cascade
		                 'N' = Set NULL
		                 'R' = Restrict
		description*  -- Descriptive text

		* Optional (can be None)
		"""
		result = super(InputPlugin, self).get_foreign_keys()
		cursor = self.connection.cursor()
		cursor.execute("""
			SELECT
				R.CREATOR                  AS TABSCHEMA,
				R.TBNAME                   AS TABNAME,
				R.RELNAME                  AS KEYNAME,
				T.CREATEDBY                AS OWNER,
				CASE
					WHEN R.CREATOR LIKE 'SYS%' THEN 'Y'
					ELSE 'N'
				END                        AS SYSTEM,
				CHAR(R.TIMESTAMP)          AS CREATED,
				R.REFTBCREATOR             AS REFTABSCHEMA,
				R.REFTBNAME                AS REFTABNAME,
				C.CONSTNAME                AS REFKEYNAME,
				R.DELETERULE               AS DELETERULE,
				CAST('A' AS CHAR(1))       AS UPDATERULE,
				CAST(NULL AS VARCHAR(762)) AS DESCRIPTION
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
				R.CREATOR                  AS TABSCHEMA,
				R.TBNAME                   AS TABNAME,
				R.RELNAME                  AS KEYNAME,
				T.CREATEDBY                AS OWNER,
				CASE
					WHEN R.CREATOR LIKE 'SYS%' THEN 'Y'
					ELSE 'N'
				END                        AS SYSTEM,
				CHAR(R.TIMESTAMP)          AS CREATED,
				R.REFTBCREATOR             AS REFTABSCHEMA,
				R.REFTBNAME                AS REFTABNAME,
				COALESCE(C.CONSTNAME, 'IX:' || I.NAME) AS REFKEYNAME,
				R.DELETERULE               AS DELETERULE,
				CAST('A' AS CHAR(1))       AS UPDATERULE,
				CAST(NULL AS VARCHAR(762)) AS DESCRIPTION
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
				refschema,
				refname,
				refkeyname,
				deleterule,
				updaterule,
				desc
			) in cursor.fetchall():
			result.append((
				schema,
				name,
				keyname,
				owner,
				make_bool(system),
				make_datetime(created),
				refschema,
				refname,
				refkeyname,
				deleterule,
				updaterule,
				desc
			))
		return result

	def get_foreign_key_cols(self):
		"""Retrieves the list of columns belonging to foreign keys.

		Override this function to return a list of tuples detailing the columns
		that belong to each foreign key in the database.  The tuples contain
		the following details in the order specified:

		schema       -- The schema of the table containing the key
		name         -- The name of the table containing the key
		keyname      -- The name of the key
		colname      -- The name of the column
		refcolname   -- The name of the column that this column references in
		                the referenced table
		"""
		result = super(InputPlugin, self).get_foreign_key_cols()
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
				TABSCHEMA,
				TABNAME,
				KEYNAME,
				COLNAME,
				REFCOLNAME
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
			) in cursor.fetchall():
			result.append((
				schema,
				name,
				keyname,
				colname,
				refcolname
			))
		return result

	def get_checks(self):
		"""Retrieves the details of checks stored in the database.

		Override this function to return a list of tuples containing details of
		the checks defined in the database. The tuples contain the following
		details in the order specified:

		schema        -- The schema of the table containing the check
		name          -- The name of the table containing the check
		checkname     -- The name of the check
		owner*        -- The name of the user who owns the check
		system        -- True if the check is system maintained (boolean)
		created*      -- When the check was created (datetime)
		sql*          -- The SQL statement/query that defined the check
		description*  -- Descriptive text

		* Optional (can be None)
		"""
		result = super(InputPlugin, self).get_checks()
		cursor = self.connection.cursor()
		cursor.execute("""
			SELECT
				C.TBOWNER                  AS TABSCHEMA,
				C.TBNAME                   AS TABNAME,
				C.CHECKNAME                AS CHECKNAME,
				C.CREATOR                  AS OWNER,
				CASE
					WHEN C.TBOWNER LIKE 'SYS%' THEN 'Y'
					ELSE 'N'
				END                        AS SYSTEM,
				CHAR(C.TIMESTAMP)          AS CREATED,
				C.CHECKCONDITION           AS SQL,
				CAST(NULL AS VARCHAR(762)) AS DESCRIPTION
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
				sql,
				desc
			) in cursor.fetchall():
			result.append((
				schema,
				name,
				checkname,
				owner,
				make_bool(system),
				make_datetime(created),
				str(sql),
				desc
			))
		return result

	def get_check_cols(self):
		"""Retrieves the list of columns belonging to checks.

		Override this function to return a list of tuples detailing the columns
		that are referenced by each check in the database.  The tuples contain
		the following details in the order specified:

		schema       -- The schema of the table containing the check
		name         -- The name of the table containing the check
		checkname    -- The name of the check
		colname      -- The name of the column
		"""
		return super(InputPlugin, self).get_check_cols()

	def get_functions(self):
		"""Retrieves the details of functions stored in the database.

		Override this function to return a list of tuples containing details of
		the functions defined in the database (including system functions). The
		tuples contain the following details in the order specified:

		schema         -- The schema of the function
		specname       -- The unique name of the function in the schema
		name           -- The (potentially overloaded) name of the function
		owner*         -- The name of the user who owns the function
		system         -- True if the function is system maintained (boolean)
		created*       -- When the function was created (datetime)
		functype       -- 'C' if the function is a column/aggregate function
		                  'R' if the function returns a row
		                  'T' if the function returns a table
		                  'S' if the function is scalar
		deterministic* -- True if the function is deterministic
		extaction*     -- True if the function has an external action (affects
		                  things outside the database)
		nullcall*      -- True if the function is called on NULL input
		access*        -- 'N' if the function contains no SQL
		                  'C' if the function contains database independent SQL
		                  'R' if the function contains SQL that reads the db
		                  'M' if the function contains SQL that modifies the db
		sql*           -- The SQL statement/query that defined the function
		description*   -- Descriptive text

		* Optional (can be None)
		"""
		result = super(InputPlugin, self).get_functions()
		cursor = self.connection.cursor()
		cursor.execute("""
			SELECT
				SCHEMA                       AS FUNCSCHEMA,
				SPECIFICNAME                 AS FUNCSPECNAME,
				NAME                         AS FUNCNAME,
				OWNER                        AS OWNER,
				CASE
					WHEN SCHEMA LIKE 'SYS%' THEN 'Y'
					WHEN ORIGIN = 'S' THEN 'Y'
					ELSE 'N'
				END                          AS SYSTEM,
				CHAR(CREATEDTS)              AS CREATED,
				FUNCTION_TYPE                AS FUNCTYPE,
				DETERMINISTIC                AS DETERMINISTIC,
				EXTERNAL_ACTION              AS EXTACTION,
				CASE ORIGIN
					WHEN 'Q' THEN 'Y'
					ELSE NULL_CALL
				END                          AS NULLCALL,
				NULLIF(SQL_DATA_ACCESS, ' ') AS ACCESS,
				CAST(NULL AS VARCHAR(10))    AS SQL,
				REMARKS                      AS DESCRIPTION
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
				functype,
				deterministic,
				extaction,
				nullcall,
				access,
				sql,
				desc
			) in cursor.fetchall():
			result.append((
				schema,
				specname,
				name,
				owner,
				make_bool(system),
				make_datetime(created),
				functype,
				make_bool(deterministic),
				make_bool(extaction, true_value='E'),
				make_bool(nullcall),
				access,
				str(sql),
				desc
			))
		return result

	def get_function_params(self):
		"""Retrieves the list of parameters belonging to functions.

		Override this function to return a list of tuples detailing the
		parameters that are associated with each function in the database.  The
		tuples contain the following details in the order specified:

		schema         -- The schema of the function
		specname       -- The unique name of the function in the schema
		parmname       -- The name of the parameter
		parmtype       -- 'I' = Input parameter
		                  'O' = Output parameter
		                  'B' = Input+Output parameter
		                  'R' = Return value/column
		typeschema     -- The schema of the parameter's datatype
		typename       -- The name of the parameter's datatype
		size*          -- The length of the parameter for character types, or
		                  the numeric precision for decimal types (None if not
		                  a character or decimal type)
		scale*         -- The maximum scale for decimal types (None if not a
		                  decimal type)
		codepage*      -- The codepage of the parameter for character types
		                  (None if not a character type)
		description*   -- Descriptive text

		Note that the each tuple details one parameter belonging to a function.
		It is important that the list of tuples is in the order that each
		parameter is declared in the function.

		This is slightly complicated by the fact that the return column(s) of a
		function are also considered parameters (see the parmtype field above).
		It does not matter if parameters and return columns are interspersed in
		the result provided that, taken separately, each set of parameters or
		columns is in the correct order.

		* Optional (can be None)
		"""
		result = super(InputPlugin, self).get_function_params()
		cursor = self.connection.cursor()
		cursor.execute("""
			SELECT
				SCHEMA                          AS FUNCSCHEMA,
				SPECIFICNAME                    AS FUNCSPECNAME,
				PARMNAME                        AS PARMNAME,
				CASE ROWTYPE
					WHEN 'S' THEN 'I'
					WHEN 'P' THEN 'I'
					WHEN 'C' THEN 'R'
					ELSE ROWTYPE
				END                             AS PARMTYPE,
				CASE SOURCETYPEID
					WHEN 0 THEN 'SYSIBM'
					ELSE TYPESCHEMA
				END                             AS TYPESCHEMA,
				CASE SOURCETYPEID
					WHEN 0 THEN
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
							ELSE TYPENAME
						END
					ELSE TYPENAME
				END                             AS TYPENAME,
				LENGTH                          AS SIZE,
				SCALE                           AS SCALE,
				CCSID                           AS CODEPAGE,
				CAST(NULL AS VARCHAR(762))      AS DESCRIPTION
			FROM
				SYSIBM.SYSPARMS
			WHERE
				ROUTINETYPE = 'F'
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
				parmtype,
				typeschema,
				typename,
				size,
				scale,
				codepage,
				desc
			) in cursor.fetchall():
			result.append((
				schema,
				specname,
				parmname,
				parmtype,
				typeschema,
				typename,
				size or None,
				scale or None, # XXX Not necessarily unknown (0 is a valid scale)
				codepage or None,
				desc
			))
		return result
	
