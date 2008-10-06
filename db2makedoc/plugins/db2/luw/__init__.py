# vim: set noet sw=4 ts=4:

"""Input plugin for IBM DB2 for Linux/UNIX/Windows."""

import logging
import re
import db2makedoc.plugins
from db2makedoc.plugins.db2 import connect, make_datetime, make_bool


class InputPlugin(db2makedoc.plugins.InputPlugin):
	"""Input plugin for IBM DB2 for Linux/UNIX/Windows.

	This input plugin supports extracting documentation information from IBM
	DB2 for Linux/UNIX/Windows version 8 or above. If the DOCCAT schema (see
	the doccat_create.sql script in the contrib/db2/luw directory) is present,
	it will be used to source documentation data instead of SYSCAT.
	"""

	def __init__(self):
		super(InputPlugin, self).__init__()
		self.add_option('database', default='',
			doc="""The locally cataloged name of the database to connect to""")
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
		# Test whether the DOCCAT extension is installed
		cursor = self.connection.cursor()
		cursor.execute("""
			SELECT COUNT(*)
			FROM SYSCAT.SCHEMATA
			WHERE SCHEMANAME = 'DOCCAT'
			WITH UR""")
		doccat = bool(cursor.fetchall()[0][0])
		logging.info([
			'DOCCAT extension schema not found, using SYSCAT',
			'DOCCAT extension schema found, using DOCCAT instead of SYSCAT'
		][doccat])
		# Test which version of the system catalog is installed. The following
		# progression is used to determine version:
		#
		# Base level (70)
		# SYSCAT.ROUTINES introduced in v8 (80)
		# SYSCAT.TABLES.OWNER introduced in v9 (90)
		# SYSCAT.VARIABLES introduced in v9.5 (95)
		cursor = self.connection.cursor()
		schemaver = 70
		cursor.execute("""
			SELECT COUNT(*)
			FROM SYSCAT.TABLES
			WHERE TABSCHEMA = 'SYSCAT'
			AND TABNAME = 'ROUTINES'
			WITH UR""")
		if bool(cursor.fetchall()[0][0]):
			schemaver = 80
			cursor.execute("""
				SELECT COUNT(*)
				FROM SYSCAT.COLUMNS
				WHERE TABSCHEMA = 'SYSCAT'
				AND TABNAME = 'TABLES'
				AND COLNAME = 'OWNER'
				WITH UR""")
			if bool(cursor.fetchall()[0][0]):
				schemaver = 90
				cursor.execute("""
					SELECT COUNT(*)
					FROM SYSCAT.TABLES
					WHERE TABSCHEMA = 'SYSCAT'
					AND TABNAME = 'VARIABLES'
					WITH UR""")
				if bool(cursor.fetchall()[0][0]):
					schemaver = 95
		logging.info({
			70: 'Detected v7 (or below) catalog layout',
			80: 'Detected v8.2 catalog layout',
			90: 'Detected v9.1 catalog layout',
			95: 'Detected v9.5 (or above) catalog layout',
		}[schemaver])
		if schemaver < 80:
			raise db2makedoc.plugins.PluginError('DB2 server must be v8.2 or above')
		# Set up a generic query substitution dictionary
		self.query_subst = {
			'schema': ['SYSCAT', 'DOCCAT'][doccat],
			'owner': ['DEFINER', 'OWNER'][schemaver >= 90],
		}

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
		cursor.execute("""
			SELECT
				RTRIM(SCHEMANAME) AS NAME,
				RTRIM(OWNER)      AS OWNER,
				CASE
					WHEN SCHEMANAME LIKE 'SYS%%' THEN 'Y'
					WHEN SCHEMANAME = 'SQLJ' THEN 'Y'
					WHEN SCHEMANAME = 'NULLID' THEN 'Y'
					ELSE 'N'
				END               AS SYSTEM,
				CHAR(CREATE_TIME) AS CREATED,
				REMARKS           AS DESCRIPTION
			FROM
				%(schema)s.SCHEMATA
			WITH UR""" % self.query_subst)
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
			SELECT
				RTRIM(TYPESCHEMA)   AS TYPESCHEMA,
				RTRIM(TYPENAME)     AS TYPENAME,
				RTRIM(%(owner)s)    AS OWNER,
				CASE METATYPE
					WHEN 'S' THEN 'Y'
					ELSE 'N'
				END                 AS SYSTEM,
				CHAR(CREATE_TIME)   AS CREATED,
				RTRIM(SOURCESCHEMA) AS SOURCESCHEMA,
				RTRIM(SOURCENAME)   AS SOURCENAME,
				LENGTH              AS SIZE,
				SCALE               AS SCALE,
				REMARKS             AS DESCRIPTION
			FROM
				%(schema)s.DATATYPES
			WHERE INSTANTIABLE = 'Y'
			WITH UR""" % self.query_subst)
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
				RTRIM(T.TABSCHEMA)     AS TABSCHEMA,
				RTRIM(T.TABNAME)       AS TABNAME,
				RTRIM(T.%(owner)s)     AS OWNER,
				CASE
					WHEN T.TABSCHEMA LIKE 'SYS%%' THEN 'Y'
					WHEN T.TABSCHEMA = 'SQLJ' THEN 'Y'
					WHEN T.TABSCHEMA = 'NULLID' THEN 'Y'
					ELSE 'N'
				END                    AS SYSTEM,
				CHAR(T.CREATE_TIME)    AS CREATED,
				CHAR(T.STATS_TIME)     AS LASTSTATS,
				NULLIF(T.CARD, -1)     AS CARDINALITY,
				BIGINT(NULLIF(T.FPAGES, -1)) * TS.PAGESIZE  AS SIZE,
				COALESCE(RTRIM(T.TBSPACE), 'NICKNAMESPACE') AS TBSPACE,
				T.REMARKS              AS DESCRIPTION
			FROM
				%(schema)s.TABLES T
				LEFT OUTER JOIN %(schema)s.TABLESPACES TS
					ON T.TBSPACEID = TS.TBSPACEID
			WHERE
				T.TYPE IN ('T', 'N')
				AND T.STATUS <> 'X'
			WITH UR""" % self.query_subst)
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
				RTRIM(V.VIEWSCHEMA)   AS VIEWSCHEMA,
				RTRIM(V.VIEWNAME)     AS VIEWNAME,
				RTRIM(V.%(owner)s)    AS OWNER,
				CASE
					WHEN V.VIEWSCHEMA LIKE 'SYS%%' THEN 'Y'
					WHEN V.VIEWSCHEMA = 'SQLJ' THEN 'Y'
					WHEN V.VIEWSCHEMA = 'NULLID' THEN 'Y'
					ELSE 'N'
				END                   AS SYSTEM,
				CHAR(T.CREATE_TIME)   AS CREATED,
				V.READONLY            AS READONLY,
				V.TEXT                AS SQL,
				T.REMARKS             AS DESCRIPTION
			FROM
				%(schema)s.TABLES T
				INNER JOIN %(schema)s.VIEWS V
					ON T.TABSCHEMA = V.VIEWSCHEMA
					AND T.TABNAME = V.VIEWNAME
					AND T.TYPE = 'V'
			WHERE
				V.VALID <> 'X'
			WITH UR""" % self.query_subst)
		for (
				schema,
				name,
				owner,
				system,
				created,
				readonly,
				sql,
				desc
			) in cursor.fetchall():
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
				RTRIM(TABSCHEMA)      AS ALIASSCHEMA,
				RTRIM(TABNAME)        AS ALIASNAME,
				RTRIM(%(owner)s)      AS OWNER,
				CASE
					WHEN TABSCHEMA LIKE 'SYS%%' THEN 'Y'
					WHEN TABSCHEMA = 'SQLJ' THEN 'Y'
					WHEN TABSCHEMA = 'NULLID' THEN 'Y'
					ELSE 'N'
				END                   AS SYSTEM,
				CHAR(CREATE_TIME)     AS CREATED,
				RTRIM(BASE_TABSCHEMA) AS BASESCHEMA,
				RTRIM(BASE_TABNAME)   AS BASETABLE,
				REMARKS               AS DESCRIPTION
			FROM
				%(schema)s.TABLES
			WHERE
				TYPE = 'A'
			WITH UR""" % self.query_subst)
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
				RTRIM(T.TABSCHEMA) AS VIEWSCHEMA,
				RTRIM(T.TABNAME)   AS VIEWNAME,
				RTRIM(T.BSCHEMA)   AS DEPSCHEMA,
				RTRIM(T.BNAME)     AS DEPNAME
			FROM
				%(schema)s.TABDEP T
				INNER JOIN %(schema)s.VIEWS V
					ON T.TABSCHEMA = V.VIEWSCHEMA
					AND T.TABNAME = V.VIEWNAME
			WHERE
				T.DTYPE = 'V'
				AND T.BTYPE IN ('A', 'N', 'T', 'V')
				AND V.VALID <> 'X'
			WITH UR""" % self.query_subst)
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
				RTRIM(I.INDSCHEMA)               AS INDSCHEMA,
				RTRIM(I.INDNAME)                 AS INDNAME,
				RTRIM(I.TABSCHEMA)               AS TABSCHEMA,
				RTRIM(I.TABNAME)                 AS TABNAME,
				RTRIM(I.%(owner)s)               AS OWNER,
				CASE
					WHEN I.INDSCHEMA LIKE 'SYS%%' THEN 'Y'
					WHEN I.INDSCHEMA = 'SQLJ' THEN 'Y'
					WHEN I.INDSCHEMA = 'NULLID' THEN 'Y'
					ELSE 'N'
				END                              AS SYSTEM,
				CHAR(I.CREATE_TIME)              AS CREATED,
				CHAR(I.STATS_TIME)               AS LASTSTATS,
				NULLIF(I.FULLKEYCARD, -1)        AS CARD,
				BIGINT(NULLIF(I.NLEAF, -1)) * TS.PAGESIZE    AS SIZE,
				CASE I.UNIQUERULE
					WHEN 'D' THEN 'N'
					ELSE 'Y'
				END                              AS UNIQUE,
				COALESCE(RTRIM(TS.TBSPACE), 'NICKNAMESPACE') AS TBSPACE,
				I.REMARKS                        AS DESCRIPTION
			FROM
				%(schema)s.INDEXES I
				INNER JOIN %(schema)s.TABLES T
					ON I.TABSCHEMA = T.TABSCHEMA
					AND I.TABNAME = T.TABNAME
				LEFT OUTER JOIN %(schema)s.TABLESPACES TS
					ON I.TBSPACEID = TS.TBSPACEID
			WHERE
				T.STATUS <> 'X'
			WITH UR""" % self.query_subst)
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
				RTRIM(IC.INDSCHEMA) AS INDSCHEMA,
				RTRIM(IC.INDNAME)   AS INDNAME,
				RTRIM(IC.COLNAME)   AS COLNAME,
				IC.COLORDER         AS COLORDER
			FROM
				%(schema)s.INDEXCOLUSE IC
				INNER JOIN %(schema)s.INDEXES I
					ON IC.INDSCHEMA = I.INDSCHEMA
					AND IC.INDNAME = I.INDNAME
				INNER JOIN %(schema)s.TABLES T
					ON I.TABSCHEMA = T.TABSCHEMA
					AND I.TABNAME = T.TABNAME
			WHERE
				T.STATUS <> 'X'
			ORDER BY
				IC.INDSCHEMA,
				IC.INDNAME,
				IC.COLSEQ
			WITH UR""" % self.query_subst)
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
				RTRIM(C.TABSCHEMA)                 AS TABSCHEMA,
				RTRIM(C.TABNAME)                   AS TABNAME,
				RTRIM(C.COLNAME)                   AS COLNAME,
				RTRIM(C.TYPESCHEMA)                AS TYPESCHEMA,
				RTRIM(C.TYPENAME)                  AS TYPENAME,
				CASE C.IDENTITY
					WHEN 'Y' THEN 'Y'
					ELSE 'N'
				END                                AS IDENTITY,
				C.LENGTH                           AS SIZE,
				C.SCALE                            AS SCALE,
				C.CODEPAGE                         AS CODEPAGE,
				C.NULLS                            AS NULLABLE,
				NULLIF(NULLIF(C.COLCARD, -1), -2)  AS CARDINALITY,
				NULLIF(C.NUMNULLS, -1)             AS NULLCARD,
				CASE C.GENERATED
					WHEN 'A' THEN 'A'
					WHEN 'D' THEN 'D'
					ELSE 'N'
				END                                AS GENERATED,
				COALESCE(CASE C.GENERATED
					WHEN '' THEN C.DEFAULT
					ELSE C.TEXT
				END, '')                           AS DEFAULT,
				C.REMARKS                          AS DESCRIPTION
			FROM
				%(schema)s.COLUMNS C
				INNER JOIN %(schema)s.TABLES T
					ON C.TABSCHEMA = T.TABSCHEMA
					AND C.TABNAME = T.TABNAME
			WHERE
				C.HIDDEN <> 'S'
				AND T.TYPE IN ('A', 'N', 'T', 'V')
				AND T.STATUS <> 'X'
			ORDER BY
				C.TABSCHEMA,
				C.TABNAME,
				C.COLNO
			WITH UR""" % self.query_subst)
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
				RTRIM(TABSCHEMA)        AS TABSCHEMA,
				RTRIM(TABNAME)          AS TABNAME,
				RTRIM(CONSTNAME)        AS KEYNAME,
				RTRIM(%(owner)s)        AS OWNER,
				CASE
					WHEN TABSCHEMA LIKE 'SYS%%' THEN 'Y'
					WHEN TABSCHEMA = 'SQLJ' THEN 'Y'
					WHEN TABSCHEMA = 'NULLID' THEN 'Y'
					ELSE 'N'
				END                     AS SYSTEM,
				CAST(NULL AS TIMESTAMP) AS CREATED,
				CASE TYPE
					WHEN 'P' THEN 'Y'
					ELSE 'N'
				END                     AS PRIMARY,
				REMARKS                 AS DESCRIPTION
			FROM
				%(schema)s.TABCONST
			WHERE
				TYPE IN ('U', 'P')
			WITH UR""" % self.query_subst)
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
			SELECT
				RTRIM(TABSCHEMA) AS TABSCHEMA,
				RTRIM(TABNAME)   AS TABNAME,
				RTRIM(CONSTNAME) AS KEYNAME,
				RTRIM(COLNAME)   AS COLNAME
			FROM
				%(schema)s.KEYCOLUSE
			ORDER BY
				TABSCHEMA,
				TABNAME,
				CONSTNAME,
				COLSEQ
			WITH UR""" % self.query_subst)
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
				RTRIM(T.TABSCHEMA)    AS TABSCHEMA,
				RTRIM(T.TABNAME)      AS TABNAME,
				RTRIM(T.CONSTNAME)    AS KEYNAME,
				RTRIM(T.%(owner)s)    AS OWNER,
				CASE
					WHEN T.TABSCHEMA LIKE 'SYS%%' THEN 'Y'
					WHEN T.TABSCHEMA = 'SQLJ' THEN 'Y'
					WHEN T.TABSCHEMA = 'NULLID' THEN 'Y'
					ELSE 'N'
				END                   AS SYSTEM,
				CHAR(R.CREATE_TIME)   AS CREATED,
				RTRIM(R.REFTABSCHEMA) AS REFTABSCHEMA,
				RTRIM(R.REFTABNAME)   AS REFTABNAME,
				RTRIM(R.REFKEYNAME)   AS REFKEYNAME,
				R.DELETERULE          AS DELETERULE,
				R.UPDATERULE          AS UPDATERULE,
				T.REMARKS             AS DESCRIPTION
			FROM
				%(schema)s.TABCONST T
				INNER JOIN %(schema)s.REFERENCES R
					ON T.TABSCHEMA = R.TABSCHEMA
					AND T.TABNAME = R.TABNAME
					AND T.CONSTNAME = R.CONSTNAME
					AND T.TYPE = 'F'
			WITH UR""" % self.query_subst)
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
			SELECT
				RTRIM(R.TABSCHEMA) AS TABSCHEMA,
				RTRIM(R.TABNAME)   AS TABNAME,
				RTRIM(R.CONSTNAME) AS KEYNAME,
				RTRIM(KF.COLNAME)  AS COLNAME,
				RTRIM(KP.COLNAME)  AS REFCOLNAME
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
			WITH UR""" % self.query_subst)
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
				RTRIM(T.TABSCHEMA)    AS TABSCHEMA,
				RTRIM(T.TABNAME)      AS TABNAME,
				RTRIM(T.CONSTNAME)    AS CHECKNAME,
				RTRIM(T.%(owner)s)    AS OWNER,
				CASE
					WHEN T.TABSCHEMA LIKE 'SYS%%' THEN 'Y'
					WHEN T.TABSCHEMA = 'SQLJ' THEN 'Y'
					WHEN T.TABSCHEMA = 'NULLID' THEN 'Y'
					WHEN C.TYPE IN ('A', 'S') THEN 'Y'
					ELSE 'N'
				END                   AS SYSTEM,
				CHAR(C.CREATE_TIME)   AS CREATED,
				C.TEXT                AS SQL,
				T.REMARKS             AS DESCRIPTION
			FROM
				%(schema)s.TABCONST T
				INNER JOIN %(schema)s.CHECKS C
					ON T.TABSCHEMA = C.TABSCHEMA
					AND T.TABNAME = C.TABNAME
					AND T.CONSTNAME = C.CONSTNAME
					AND T.TYPE = 'K'
			WITH UR""" % self.query_subst)
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
		result = super(InputPlugin, self).get_check_cols()
		cursor = self.connection.cursor()
		cursor.execute("""
			SELECT
				RTRIM(TABSCHEMA) AS TABSCHEMA,
				RTRIM(TABNAME)   AS TABNAME,
				RTRIM(CONSTNAME) AS CHECKNAME,
				RTRIM(COLNAME)   AS COLNAME
			FROM
				%(schema)s.COLCHECKS
			WITH UR""" % self.query_subst)
		for (
				schema,
				name,
				chkname,
				colname
			) in cursor.fetchall():
			result.append((
				schema,
				name,
				chkname,
				colname
			))
		return result

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
				RTRIM(ROUTINESCHEMA)         AS FUNCSCHEMA,
				RTRIM(SPECIFICNAME)          AS FUNCSPECNAME,
				RTRIM(ROUTINENAME)           AS FUNCNAME,
				RTRIM(%(owner)s)             AS OWNER,
				CASE
					WHEN ROUTINESCHEMA LIKE 'SYS%%' THEN 'Y'
					WHEN ROUTINESCHEMA = 'SQLJ' THEN 'Y'
					WHEN ROUTINESCHEMA = 'NULLID' THEN 'Y'
					WHEN ORIGIN IN ('B', 'S', 'T') THEN 'Y'
					ELSE 'N'
				END                          AS SYSTEM,
				CHAR(CREATE_TIME)            AS CREATED,
				FUNCTIONTYPE                 AS FUNCTYPE,
				DETERMINISTIC                AS DETERMINISTIC,
				EXTERNAL_ACTION              AS EXTACTION,
				NULLCALL                     AS NULLCALL,
				NULLIF(SQL_DATA_ACCESS, ' ') AS ACCESS,
				COALESCE(TEXT, '')           AS SQL,
				REMARKS                      AS DESCRIPTION
			FROM
				%(schema)s.ROUTINES
			WHERE
				ROUTINETYPE = 'F'
				AND VALID <> 'X'
			WITH UR""" % self.query_subst)
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
				RTRIM(P.ROUTINESCHEMA)          AS FUNCSCHEMA,
				RTRIM(P.SPECIFICNAME)           AS FUNCSPECNAME,
				RTRIM(COALESCE(P.PARMNAME, '')) AS PARMNAME,
				CASE P.ROWTYPE
					WHEN ' ' THEN 'I'
					WHEN 'P' THEN 'I'
					WHEN 'C' THEN 'R'
					ELSE P.ROWTYPE
				END                             AS PARMTYPE,
				RTRIM(P.TYPESCHEMA)             AS TYPESCHEMA,
				RTRIM(P.TYPENAME)               AS TYPENAME,
				P.LENGTH                        AS SIZE,
				P.SCALE                         AS SCALE,
				P.CODEPAGE                      AS CODEPAGE,
				P.REMARKS                       AS DESCRIPTION
			FROM
				%(schema)s.ROUTINEPARMS P
				INNER JOIN %(schema)s.ROUTINES R
					ON P.ROUTINESCHEMA = R.ROUTINESCHEMA
					AND P.SPECIFICNAME = R.SPECIFICNAME
			WHERE
				R.ROUTINETYPE = 'F'
				AND R.VALID <> 'X'
			ORDER BY
				P.ROUTINESCHEMA,
				P.SPECIFICNAME,
				P.ORDINAL
			WITH UR""" % self.query_subst)
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

	def get_procedures(self):
		"""Retrieves the details of stored procedures in the database.

		Override this function to return a list of tuples containing details of
		the procedures defined in the database (including system procedures).
		The tuples contain the following details in the order specified:

		schema         -- The schema of the procedure
		specname       -- The unique name of the procedure in the schema
		name           -- The (potentially overloaded) name of the procedure
		owner*         -- The name of the user who owns the procedure
		system         -- True if the procedure is system maintained (boolean)
		created*       -- When the procedure was created (datetime)
		deterministic* -- True if the procedure is deterministic
		extaction*     -- True if the procedure has an external action (affects
		                  things outside the database)
		nullcall*      -- True if the procedure is called on NULL input
		access*        -- 'N' if the procedure contains no SQL
		                  'C' if the procedure contains database independent SQL
		                  'R' if the procedure contains SQL that reads the db
		                  'M' if the procedure contains SQL that modifies the db
		sql*           -- The SQL statement/query that defined the procedure
		description*   -- Descriptive text

		* Optional (can be None)
		"""
		result = super(InputPlugin, self).get_procedures()
		cursor = self.connection.cursor()
		cursor.execute("""
			SELECT
				RTRIM(ROUTINESCHEMA)         AS PROCSCHEMA,
				RTRIM(SPECIFICNAME)          AS PROCSPECNAME,
				RTRIM(ROUTINENAME)           AS PROCNAME,
				RTRIM(%(owner)s)             AS OWNER,
				CASE
					WHEN ROUTINESCHEMA LIKE 'SYS%%' THEN 'Y'
					WHEN ROUTINESCHEMA = 'SQLJ' THEN 'Y'
					WHEN ROUTINESCHEMA = 'NULLID' THEN 'Y'
					WHEN ORIGIN IN ('B', 'S', 'T') THEN 'Y'
					ELSE 'N'
				END                          AS SYSTEM,
				CHAR(CREATE_TIME)            AS CREATED,
				DETERMINISTIC                AS DETERMINISTIC,
				EXTERNAL_ACTION              AS EXTACTION,
				NULLCALL                     AS NULLCALL,
				NULLIF(SQL_DATA_ACCESS, ' ') AS ACCESS,
				COALESCE(TEXT, '')           AS SQL,
				REMARKS                      AS DESCRIPTION
			FROM
				%(schema)s.ROUTINES
			WHERE
				ROUTINETYPE = 'P'
				AND VALID <> 'X'
			WITH UR""" % self.query_subst)
		for (
				schema,
				specname,
				name,
				owner,
				system,
				created,
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
				make_bool(deterministic),
				make_bool(extaction, true_value='E'),
				make_bool(nullcall),
				access,
				str(sql),
				desc
			))
		return result

	def get_procedure_params(self):
		"""Retrieves the list of parameters belonging to procedures.

		Override this function to return a list of tuples detailing the
		parameters that are associated with each procedure in the database.
		The tuples contain the following details in the order specified:

		schema         -- The schema of the procedure
		specname       -- The unique name of the procedure in the schema
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

		Note that the each tuple details one parameter belonging to a
		procedure.  It is important that the list of tuples is in the order
		that each parameter is declared in the procedure.

		This is slightly complicated by the fact that the return column(s) of a
		procedure are also considered parameters (see the parmtype field
		above).  It does not matter if parameters and return columns are
		interspersed in the result provided that, taken separately, each set of
		parameters or columns is in the correct order.

		* Optional (can be None)
		"""
		result = super(InputPlugin, self).get_procedure_params()
		cursor = self.connection.cursor()
		cursor.execute("""
			SELECT
				RTRIM(RP.ROUTINESCHEMA)          AS PROCSCHEMA,
				RTRIM(RP.SPECIFICNAME)           AS PROCSPECNAME,
				RTRIM(COALESCE(RP.PARMNAME, '')) AS PARMNAME,
				CASE RP.ROWTYPE
					WHEN 'P' THEN 'I'
					WHEN 'C' THEN 'R'
					ELSE RP.ROWTYPE
				END                              AS PARMTYPE,
				RTRIM(RP.TYPESCHEMA)             AS TYPESCHEMA,
				RTRIM(RP.TYPENAME)               AS TYPENAME,
				RP.LENGTH                        AS SIZE,
				RP.SCALE                         AS SCALE,
				RP.CODEPAGE                      AS CODEPAGE,
				RP.REMARKS                       AS DESCRIPTION
			FROM
				%(schema)s.ROUTINEPARMS RP
				INNER JOIN %(schema)s.ROUTINES R
					ON RP.ROUTINESCHEMA = R.ROUTINESCHEMA
					AND RP.SPECIFICNAME = R.SPECIFICNAME
			WHERE
				R.ROUTINETYPE = 'P'
				AND R.VALID <> 'X'
			ORDER BY
				RP.ROUTINESCHEMA,
				RP.SPECIFICNAME,
				RP.ORDINAL
			WITH UR""" % self.query_subst)
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

	def get_triggers(self):
		"""Retrieves the details of table triggers in the database.

		Override this function to return a list of tuples containing details of
		the triggers defined in the database (including system triggers).  The
		tuples contain the following details in the order specified:

		schema         -- The schema of the trigger
		name           -- The unique name of the trigger in the schema
		owner*         -- The name of the user who owns the trigger
		system         -- True if the trigger is system maintained (boolean)
		created*       -- When the trigger was created (datetime)
		tabschema      -- The schema of the table that activates the trigger
		tabname        -- The name of the table that activates the trigger
		trigtime       -- When the trigger is fired:
		                  'A' = The trigger fires after the statement
		                  'B' = The trigger fires before the statement
		                  'I' = The trigger fires instead of the statement
		trigevent      -- What statement fires the trigger:
		                  'I' = The trigger fires on INSERT
		                  'U' = The trigger fires on UPDATE
		                  'D' = The trigger fires on DELETE
		granularity    -- The granularity of trigger executions:
		                  'R' = The trigger fires for each row affected
		                  'S' = The trigger fires once per activating statement
		sql*           -- The SQL statement/query that defined the trigger
		description*   -- Descriptive text

		* Optional (can be None)
		"""
		result = super(InputPlugin, self).get_triggers()
		cursor = self.connection.cursor()
		cursor.execute("""
			SELECT
				RTRIM(TRIGSCHEMA)  AS TRIGSCHEMA,
				RTRIM(TRIGNAME)    AS TRIGNAME,
				RTRIM(%(owner)s)   AS OWNER,
				CASE
					WHEN TRIGSCHEMA LIKE 'SYS%%' THEN 'Y'
					WHEN TRIGSCHEMA = 'SQLJ' THEN 'Y'
					WHEN TRIGSCHEMA = 'NULLID' THEN 'Y'
					ELSE 'N'
				END                AS SYSTEM,
				CHAR(CREATE_TIME)  AS CREATED,
				RTRIM(TABSCHEMA)   AS TABSCHEMA,
				RTRIM(TABNAME)     AS TABNAME,
				TRIGTIME           AS TRIGTIME,
				TRIGEVENT          AS TRIGEVENT,
				GRANULARITY        AS GRANULARITY,
				TEXT               AS SQL,
				REMARKS            AS DESCRIPTION
			FROM
				%(schema)s.TRIGGERS
			WHERE
				VALID <> 'X'
			WITH UR""" % self.query_subst)
		for (
				schema,
				name,
				owner,
				system,
				created,
				tabschema,
				tabname,
				trigtime,
				trigevent,
				granularity,
				sql,
				desc
			) in cursor.fetchall():
			result.append((
				schema,
				name,
				owner,
				make_bool(system),
				make_datetime(created),
				tabschema,
				tabname,
				trigtime,
				trigevent,
				granularity,
				str(sql),
				desc
			))
		return result

	def get_trigger_dependencies(self):
		"""Retrieves the details of trigger dependencies.

		Override this function to return a list of tuples containing details of
		the relations upon which triggers depend (the tables that a trigger
		references in its body).  The tuples contain the following details in
		the order specified:

		schema       -- The schema of the trigger
		name         -- The name of the trigger
		dep_schema   -- The schema of the relation upon which the trigger depends
		dep_name     -- The name of the relation upon which the trigger depends
		"""
		result = super(InputPlugin, self).get_trigger_dependencies()
		cursor = self.connection.cursor()
		cursor.execute("""
			SELECT
				RTRIM(TD.TRIGSCHEMA) AS TRIGSCHEMA,
				RTRIM(TD.TRIGNAME)   AS TRIGNAME,
				RTRIM(TD.BSCHEMA)    AS DEPSCHEMA,
				RTRIM(TD.BNAME)      AS DEPNAME
			FROM
				%(schema)s.TRIGDEP TD
				INNER JOIN %(schema)s.TRIGGERS T
					ON TD.TRIGSCHEMA = T.TRIGSCHEMA
					AND TD.TRIGNAME = T.TRIGNAME
			WHERE
				TD.BTYPE IN ('A', 'N', 'T', 'V')
				AND T.VALID <> 'X'
				AND NOT (TD.BSCHEMA = T.TABSCHEMA AND TD.BNAME = T.TABNAME)
			WITH UR""" % self.query_subst)
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

	def get_tablespaces(self):
		"""Retrieves the details of the tablespaces in the database.

		Override this function to return a list of tuples containing details of
		the tablespaces defined in the database (including system tablespaces).
		The tuples contain the following details in the order specified:

		tbspace       -- The tablespace name
		owner*        -- The name of the user who owns the tablespace
		system        -- True if the tablespace is system maintained (boolean)
		created*      -- When the tablespace was created (datetime)
		type*         -- The type of the tablespace (regular, temporary, system
		              -- or database managed, etc) as free text
		description*  -- Descriptive text

		* Optional (can be None)
		"""
		result = super(InputPlugin, self).get_tablespaces()
		cursor = self.connection.cursor()
		cursor.execute("""
			SELECT
				RTRIM(TBSPACE)    AS TBSPACE,
				RTRIM(%(owner)s)  AS OWNER,
				CASE TBSPACE
					WHEN 'SYSCATSPACE' THEN 'Y'
					WHEN 'SYSTOOLSPACE' THEN 'Y'
					ELSE 'N'
				END               AS SYSTEM,
				CHAR(CREATE_TIME) AS CREATED,
				CASE DATATYPE
					WHEN 'A' THEN 'Regular'
					WHEN 'L' THEN 'Long'
					WHEN 'T' THEN 'System temporary'
					WHEN 'U' THEN 'User temporary'
					ELSE 'Unknown'
				END ||
				' ' ||
				CASE TBSPACETYPE
					WHEN 'D' THEN 'DMS'
					WHEN 'S' THEN 'SMS'
					ELSE 'unknown'
				END ||
				' tablespace with ' ||
				RTRIM(CHAR(PAGESIZE / 1024)) ||
				'k page size' ||
				CASE DROP_RECOVERY
					WHEN 'Y' THEN ' and drop recovery'
					ELSE ''
				END               AS TYPE,
				REMARKS           AS DESCRIPTION
			FROM
				%(schema)s.TABLESPACES

			UNION ALL

			SELECT
				'NICKNAMESPACE',
				'SYSIBM',
				'N',
				CHAR(CREATE_TIME),
				'Fake tablespace',
				'Fake tablespace which contains all nicknames in the database'
			FROM
				%(schema)s.TABLESPACES
			WHERE
				TBSPACE = 'SYSCATSPACE'
				AND EXISTS (
					SELECT 1
					FROM SYSCAT.TABLES
					WHERE TYPE = 'N'
					FETCH FIRST 1 ROW ONLY
				)
			WITH UR""" % self.query_subst)
		for (
				tbspace,
				owner,
				system,
				created,
				tstype,
				desc
			) in cursor.fetchall():
			result.append((
				tbspace,
				owner,
				make_bool(system),
				make_datetime(created),
				tstype,
				desc
			))
		return result

