# vim: set noet sw=4 ts=4:

"""Input plugin for IBM DB2 for Linux/UNIX/Windows."""

import logging
import re
import db2makedoc.plugins
from db2makedoc.plugins.db2 import (
	connect, make_datetime, make_bool, make_int, make_str
)
from db2makedoc.tuples import (
	Schema, Datatype, Table, View, Alias, RelationDep, Index, IndexCol,
	RelationCol, UniqueKey, UniqueKeyCol, ForeignKey, ForeignKeyCol, Check,
	CheckCol, Function, Procedure, RoutineParam, Trigger, TriggerDep,
	Tablespace
)


def connect(database=None, username=None, password=None, host=None, port=None, unix_socket=None, ssl=False):
	"""Create a connection to the specified database.

	This utility method attempts to connect to the specified database using the
	username and password provided. The method attempts to use a variety of
	connection frameworks (current pg8000 or Psycopg2 PyDB2) depending on the
	underlying platform.
	"""
	logging.info('Connecting to database "%s"' % database)
	# Try the pg8000 driver
	try:
		from pg8000 import dbapi
	except ImportError:
		pass
	else:
		logging.info('Using pg8000 driver')
		if unix_socket:
			return dbapi.connect(database=database, user=username, password=password, unix_sock=unix_socket, ssl=ssl)
		else:
			return dbapi.connect(database=database, user=username, password=password, host=host, port=port, ssl=ssl)
	# Try the Psycopg2 driver
	try:
		import psycopg2
		import psycopg2.extensions
	except ImportError:
		pass
	else:
		logging.info('Using Psycopg2 driver')
		# Dirty hack for using UNIX sockets: Psycopg2 doesn't allow us to
		# specify which UNIX socket to connect to, just uses the client
		# library's compiled in default. Meanwhile, pg8000 requires
		# specification of the exact socket if UNIX socket connectivity is
		# wanted. If one looks at the client library's PQconnect function UNIX
		# socket connectivity is actually specified at the C level by passing a
		# pathname as the host parameter so in order to make Psycopg2 act a bit
		# like pg8000 that's what we do here as Psycopg2 doesn't actually do
		# anything with the parameters beyond pass them onto the client lib
		if unix_socket:
			host = os.path.dirname(unix_socket)
			port = None
		ssl = {
			False: 'prefer',
			True:  'require',
		}[ssl]
		# Ensure strings are returned as unicode objects
		conn = psycopg2.connect(database=database, user=username, password=password, host=host, port=port, ssl=ssl)
		psycopg2.extensions.register_type(psycopg2.extensions.UNICODE, conn)
		return conn
	# Try the pyodbc driver
	try:
		import pyodbc
	except ImportError:
		pass
	else:
		logging.info('Using pyodbc driver')
		# XXX Check whether escaping/quoting is required
		# XXX Need a way to specify the driver name. Given that on unixODBC the
		# driver alias is specified in odbcinst.ini
		if username is not None:
			return pyodbc.connect('driver=???;dsn=%s;uid=%s;pwd=%s' % (dsn, username, password))
		else:
			return pyodbc.connect('driver=???;dsn=%s' % dsn)
	raise ImportError('Unable to find a suitable connection framework; please install pg8000, Psycopg2, or pyodbc')


class InputPlugin(db2makedoc.plugins.InputPlugin):
	"""Input plugin for PostgreSQL.

	This input plugin supports extracting documentation information from
	PostgreSQL databases.
	"""

	def __init__(self):
		super(InputPlugin, self).__init__()
		self.add_option('host', default='localhost',
			doc="""The hostname of the machine hosting the PostgreSQL server""")
		self.add_option('port', default='5432',
			convert=lambda value: self.convert_int(value, minvalue=1, maxvalue=65535),
			doc="""The port on which the PostgreSQL server is listening""")
		self.add_option('unix_socket', default=None,
			doc="""The UNIX socket to connect to (if specified a TCP/IP
			connection will not be attempted)""")
		self.add_option('database', default='',
			doc="""The name of the database to connect to on the specified host/socket""")
		self.add_option('username', default=None,
			doc="""The username to connect with""")
		self.add_option('password', default=None,
			doc="""The password associated with the user given by the username
			option (optional; implicit authentication is attempted if not supplied)""")
		self.add_option('ssl', default='false', convert=self.convert_bool,
			doc="""If true, attempt SSL negotiation using PostgreSQL's "require"
			setting""")
		self.add_option('block_size', default='8192', convert=self.convert_int,
			doc="""The block size being used by the PostgreSQL server, used to
			calculate approximate sizes of objects on disk""")

	def configure(self, config):
		"""Loads the plugin configuration."""
		super(InputPlugin, self).configure(config)
		# Check for missing stuff
		if not self.options['username']:
			raise db2makedoc.plugins.PluginConfigurationError('The username option must be specified')
		if not self.options['host'] and not self.options['unix_socket']:
			raise db2makedoc.plugins.PluginConfigurationError('Either "host" or "unix_socket" must be specified')
		# If database is not specified it's equal to username
		if not self.options['database']:
			self.options['database'] = self.options['username']
		self.block_size = self.options['block_size']

	def open(self):
		"""Opens the database connection for data retrieval."""
		super(InputPlugin, self).open()
		self.connection = connect(
			self.options['database'],
			self.options['username'],
			self.options['password'],
			self.options['host'],
			self.options['port'],
			self.options['unix_socket'],
			self.options['ssl']
		)
		self.name = self.options['database']

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
		cursor.execute("""
			SELECT
				nsp.nspname                              AS name,
				own.rolname                              AS owner,
				CASE
					WHEN nsp.nspname LIKE 'pg_%' THEN true
					WHEN nsp.nspname = 'information_schema' THEN true
					ELSE false
				END                                      AS system,
				CAST(NULL AS TIMESTAMP)                  AS created,
				obj_description(nsp.oid, 'pg_namespace') AS description
			FROM
				pg_catalog.pg_namespace nsp
				INNER JOIN pg_catalog.pg_authid own
					ON nsp.nspowner = own.oid
		""")
		for row in self.fetch_some(cursor):
			yield Schema(*row)

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
			SELECT
				nst.nspname                         AS typeschema,
				typ.typname                         AS typename,
				own.rolname                         AS owner,
				CASE typ.typtype
					WHEN 'b' THEN true
					ELSE false
				END                                 AS system,
				CAST(NULL AS TIMESTAMP)             AS created,
				obj_description(typ.oid, 'pg_type') AS description,
				false                               AS variable_size,
				false                               AS variable_scale,
				CASE typ.typtype
					WHEN 'd' THEN nsb.nspname
				END                                 AS sourceschema,
				CASE typ.typtype
					WHEN 'd' THEN bas.typname
				END                                 AS sourcename,
				CAST(NULL AS INTEGER)               AS size,
				CAST(NULL AS INTEGER)               AS scale
			FROM
				pg_catalog.pg_type typ
				INNER JOIN pg_catalog.pg_namespace nst
					ON typ.typnamespace = nst.oid
				INNER JOIN pg_catalog.pg_authid own
					ON typ.typowner = own.oid
				LEFT OUTER JOIN pg_catalog.pg_type bas
					ON typ.typbasetype = bas.oid
				LEFT OUTER JOIN pg_catalog.pg_namespace nsb
					ON bas.typnamespace = nsb.oid
			WHERE
				typ.typtype IN ('b', 'd', 'e')
				AND typ.typelem = 0
				AND typ.typisdefined
		""")
		for row in self.fetch_some(cursor):
			yield Datatype(*row)

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
				nsp.nspname                                 AS tabschema,
				cls.relname                                 AS tabname,
				own.rolname                                 AS owner,
				CASE
					WHEN nsp.nspname LIKE 'pg_%' THEN true
					WHEN nsp.nspname = 'information_schema' THEN true
					ELSE false
				END                                         AS system,
				CAST(NULL AS TIMESTAMP)                     AS created,
				obj_description(cls.oid, 'pg_class')        AS description,
				CASE cls.reltablespace
					WHEN 0 THEN dbs.spcname
					ELSE tbs.spcname
				END                                         AS tbspace,
				CAST(NULL AS TIMESTAMP)                     AS laststats,
				CAST(cls.reltuples AS BIGINT)               AS cardinality,
				cls.relpages                                AS size
			FROM
				pg_catalog.pg_class cls
				INNER JOIN pg_catalog.pg_namespace nsp
					ON cls.relnamespace = nsp.oid
				INNER JOIN pg_catalog.pg_authid own
					ON cls.relowner = own.oid
				LEFT OUTER JOIN pg_catalog.pg_tablespace tbs
					ON cls.reltablespace = tbs.oid
					AND cls.reltablespace <> 0
				INNER JOIN pg_catalog.pg_database db
					ON db.datname = current_database()
				INNER JOIN pg_catalog.pg_tablespace dbs
					ON db.dattablespace = dbs.oid
			WHERE
				NOT cls.relistemp
				AND cls.relkind = 'r'
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
				system,
				created,
				desc,
				tbspace,
				laststats,
				cardinality,
				size * self.block_size,
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
				RTRIM(V.VIEWSCHEMA)   AS VIEWSCHEMA,
				RTRIM(V.VIEWNAME)     AS VIEWNAME,
				RTRIM(V.%(owner)s)    AS OWNER,
				CHAR('N')             AS SYSTEM,
				CHAR(T.CREATE_TIME)   AS CREATED,
				T.REMARKS             AS DESCRIPTION,
				V.READONLY            AS READONLY,
				V.TEXT                AS SQL
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
				desc,
				readonly,
				sql,
			) in self.fetch_some(cursor):
			yield View(
				make_str(schema),
				make_str(name),
				make_str(owner),
				make_bool(system),
				make_datetime(created),
				make_str(desc),
				make_bool(readonly),
				make_str(sql),
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
		for row in  super(InputPlugin, self).get_aliases():
			yield row
		cursor = self.connection.cursor()
		cursor.execute("""
			SELECT
				RTRIM(TABSCHEMA)      AS ALIASSCHEMA,
				RTRIM(TABNAME)        AS ALIASNAME,
				RTRIM(%(owner)s)      AS OWNER,
				CHAR('N')             AS SYSTEM,
				CHAR(CREATE_TIME)     AS CREATED,
				REMARKS               AS DESCRIPTION,
				RTRIM(BASE_TABSCHEMA) AS BASESCHEMA,
				RTRIM(BASE_TABNAME)   AS BASETABLE
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
				desc,
				base_schema,
				base_table,
			) in self.fetch_some(cursor):
			yield Alias(
				make_str(schema),
				make_str(name),
				make_str(owner),
				make_bool(system),
				make_datetime(created),
				make_str(desc),
				make_str(base_schema),
				make_str(base_table),
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
				depname,
			) in self.fetch_some(cursor):
			yield RelationDep(
				make_str(schema),
				make_str(name),
				make_str(depschema),
				make_str(depname),
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
				RTRIM(I.INDSCHEMA)                           AS INDSCHEMA,
				RTRIM(I.INDNAME)                             AS INDNAME,
				RTRIM(I.%(owner)s)                           AS OWNER,
				CASE USER_DEFINED
					WHEN 0 THEN 'Y'
					ELSE 'N'
				END                                          AS SYSTEM,
				CHAR(I.CREATE_TIME)                          AS CREATED,
				I.REMARKS                                    AS DESCRIPTION,
				RTRIM(I.TABSCHEMA)                           AS TABSCHEMA,
				RTRIM(I.TABNAME)                             AS TABNAME,
				COALESCE(RTRIM(TS.TBSPACE), 'NICKNAMESPACE') AS TBSPACE,
				CHAR(I.STATS_TIME)                           AS LASTSTATS,
				NULLIF(I.FULLKEYCARD, -1)                    AS CARD,
				BIGINT(NULLIF(I.NLEAF, -1)) * TS.PAGESIZE    AS SIZE,
				CASE I.UNIQUERULE
					WHEN 'D' THEN 'N'
					ELSE 'Y'
				END                                          AS UNIQUE
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
				make_str(schema),
				make_str(name),
				make_str(owner),
				make_bool(system),
				make_datetime(created),
				make_str(desc),
				make_str(tabschema),
				make_str(tabname),
				make_str(tbspace),
				make_datetime(laststats),
				make_int(card),
				make_int(size),
				make_bool(unique),
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
				colorder,
			) in self.fetch_some(cursor):
			yield IndexCol(
				make_str(schema),
				make_str(name),
				make_str(colname),
				make_str(colorder),
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
				RTRIM(C.TABSCHEMA)                 AS TABSCHEMA,
				RTRIM(C.TABNAME)                   AS TABNAME,
				RTRIM(C.COLNAME)                   AS COLNAME,
				RTRIM(C.TYPESCHEMA)                AS TYPESCHEMA,
				RTRIM(C.TYPENAME)                  AS TYPENAME,
				NULLIF(C.LENGTH, 0)                AS SIZE,
				C.SCALE                            AS SCALE,
				-- XXX 0 is a legitimate codepage (e.g. FOR BIT DATA columns)
				NULLIF(C.CODEPAGE, 0)              AS CODEPAGE,
				CASE C.IDENTITY
					WHEN 'Y' THEN 'Y'
					ELSE 'N'
				END                                AS IDENTITY,
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
				size,
				scale,
				codepage,
				identity,
				nullable,
				cardinality,
				nullcard,
				generated,
				default,
				desc,
			) in self.fetch_some(cursor):
			if generated != 'N':
				default = re.sub(r'^\s*AS\s*', '', str(default))
			yield RelationCol(
				make_str(schema),
				make_str(name),
				make_str(colname),
				make_str(typeschema),
				make_str(typename),
				make_int(size),
				make_int(scale),
				make_int(codepage),
				make_bool(identity),
				make_bool(nullable),
				make_int(cardinality),
				make_int(nullcard),
				make_str(generated),
				make_str(default),
				make_str(desc),
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
				RTRIM(TABSCHEMA)        AS TABSCHEMA,
				RTRIM(TABNAME)          AS TABNAME,
				RTRIM(CONSTNAME)        AS KEYNAME,
				RTRIM(%(owner)s)        AS OWNER,
				CHAR('N')               AS SYSTEM,
				CAST(NULL AS TIMESTAMP) AS CREATED,
				REMARKS                 AS DESCRIPTION,
				CASE TYPE
					WHEN 'P' THEN 'Y'
					ELSE 'N'
				END                     AS PRIMARY
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
				desc,
				primary,
			) in self.fetch_some(cursor):
			yield UniqueKey(
				make_str(schema),
				make_str(name),
				make_str(keyname),
				make_str(owner),
				make_bool(system),
				make_datetime(created),
				make_str(desc),
				make_bool(primary),
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
			) in self.fetch_some(cursor):
			yield UniqueKeyCol(
				make_str(schema),
				make_str(name),
				make_str(keyname),
				make_str(colname),
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
				RTRIM(T.TABSCHEMA)    AS TABSCHEMA,
				RTRIM(T.TABNAME)      AS TABNAME,
				RTRIM(T.CONSTNAME)    AS KEYNAME,
				RTRIM(T.%(owner)s)    AS OWNER,
				CHAR('N')             AS SYSTEM,
				CHAR(R.CREATE_TIME)   AS CREATED,
				T.REMARKS             AS DESCRIPTION,
				RTRIM(R.REFTABSCHEMA) AS REFTABSCHEMA,
				RTRIM(R.REFTABNAME)   AS REFTABNAME,
				RTRIM(R.REFKEYNAME)   AS REFKEYNAME,
				R.DELETERULE          AS DELETERULE,
				R.UPDATERULE          AS UPDATERULE
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
				desc,
				refschema,
				refname,
				refkeyname,
				deleterule,
				updaterule,
			) in self.fetch_some(cursor):
			yield ForeignKey(
				make_str(schema),
				make_str(name),
				make_str(keyname),
				make_str(owner),
				make_bool(system),
				make_datetime(created),
				make_str(desc),
				make_str(refschema),
				make_str(refname),
				make_str(refkeyname),
				make_str(deleterule),
				make_str(updaterule),
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
			) in self.fetch_some(cursor):
			yield ForeignKeyCol(
				make_str(schema),
				make_str(name),
				make_str(keyname),
				make_str(colname),
				make_str(refcolname),
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
				RTRIM(T.TABSCHEMA)    AS TABSCHEMA,
				RTRIM(T.TABNAME)      AS TABNAME,
				RTRIM(T.CONSTNAME)    AS CHECKNAME,
				RTRIM(T.%(owner)s)    AS OWNER,
				CASE
					WHEN C.TYPE IN ('A', 'S') THEN 'Y'
					ELSE 'N'
				END                   AS SYSTEM,
				CHAR(C.CREATE_TIME)   AS CREATED,
				T.REMARKS             AS DESCRIPTION,
				C.TEXT                AS SQL
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
				desc,
				sql,
			) in self.fetch_some(cursor):
			yield Check(
				make_str(schema),
				make_str(name),
				make_str(checkname),
				make_str(owner),
				make_bool(system),
				make_datetime(created),
				make_str(desc),
				make_str(sql),
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
			) in self.fetch_some(cursor):
			yield CheckCol(
				make_str(schema),
				make_str(name),
				make_str(chkname),
				make_str(colname),
			)

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
				RTRIM(ROUTINESCHEMA)         AS FUNCSCHEMA,
				RTRIM(SPECIFICNAME)          AS FUNCSPECNAME,
				RTRIM(ROUTINENAME)           AS FUNCNAME,
				RTRIM(%(owner)s)             AS OWNER,
				CASE
					WHEN ORIGIN IN ('B', 'S', 'T') THEN 'Y'
					ELSE 'N'
				END                          AS SYSTEM,
				CHAR(CREATE_TIME)            AS CREATED,
				REMARKS                      AS DESCRIPTION,
				DETERMINISTIC                AS DETERMINISTIC,
				EXTERNAL_ACTION              AS EXTACTION,
				NULLCALL                     AS NULLCALL,
				NULLIF(SQL_DATA_ACCESS, ' ') AS ACCESS,
				TEXT                         AS SQL,
				FUNCTIONTYPE                 AS FUNCTYPE
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
				desc,
				deterministic,
				extaction,
				nullcall,
				access,
				sql,
				functype,
			) in self.fetch_some(cursor):
			yield Function(
				make_str(schema),
				make_str(specname),
				make_str(name),
				make_str(owner),
				make_bool(system),
				make_datetime(created),
				make_str(desc),
				make_bool(deterministic),
				make_bool(extaction, true_value='E'),
				make_bool(nullcall),
				make_str(access),
				make_str(sql),
				make_str(functype),
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
				RTRIM(ROUTINESCHEMA)         AS PROCSCHEMA,
				RTRIM(SPECIFICNAME)          AS PROCSPECNAME,
				RTRIM(ROUTINENAME)           AS PROCNAME,
				RTRIM(%(owner)s)             AS OWNER,
				CASE
					WHEN ORIGIN IN ('B', 'S', 'T') THEN 'Y'
					ELSE 'N'
				END                          AS SYSTEM,
				CHAR(CREATE_TIME)            AS CREATED,
				REMARKS                      AS DESCRIPTION,
				DETERMINISTIC                AS DETERMINISTIC,
				EXTERNAL_ACTION              AS EXTACTION,
				NULLCALL                     AS NULLCALL,
				NULLIF(SQL_DATA_ACCESS, ' ') AS ACCESS,
				TEXT                         AS SQL
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
				desc,
				deterministic,
				extaction,
				nullcall,
				access,
				sql
			) in self.fetch_some(cursor):
			yield Procedure(
				make_str(schema),
				make_str(specname),
				make_str(name),
				make_str(owner),
				make_bool(system),
				make_datetime(created),
				make_str(desc),
				make_bool(deterministic),
				make_bool(extaction, true_value='E'),
				make_bool(nullcall),
				make_str(access),
				make_str(sql),
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
				RTRIM(P.ROUTINESCHEMA)          AS ROUTINESCHEMA,
				RTRIM(P.SPECIFICNAME)           AS ROUTINESPECNAME,
				RTRIM(COALESCE(P.PARMNAME, '')) AS PARMNAME,
				RTRIM(P.TYPESCHEMA)             AS TYPESCHEMA,
				RTRIM(P.TYPENAME)               AS TYPENAME,
				NULLIF(P.LENGTH, 0)             AS SIZE,
				P.SCALE                         AS SCALE,
				-- XXX 0 is a legitimate codepage (e.g. FOR BIT DATA types)
				NULLIF(P.CODEPAGE, 0)           AS CODEPAGE,
				CASE P.ROWTYPE
					WHEN ' ' THEN 'I'
					WHEN 'P' THEN 'I'
					WHEN 'C' THEN 'R'
					ELSE P.ROWTYPE
				END                             AS DIRECTION,
				P.REMARKS                       AS DESCRIPTION
			FROM
				%(schema)s.ROUTINEPARMS P
				INNER JOIN %(schema)s.ROUTINES R
					ON P.ROUTINESCHEMA = R.ROUTINESCHEMA
					AND P.SPECIFICNAME = R.SPECIFICNAME
			WHERE
				R.ROUTINETYPE IN ('F', 'P')
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
				typeschema,
				typename,
				size,
				scale,
				codepage,
				parmtype,
				desc
			) in self.fetch_some(cursor):
			yield RoutineParam(
				make_str(schema),
				make_str(specname),
				make_str(parmname),
				make_str(typeschema),
				make_str(typename),
				make_int(size),
				make_int(scale),
				make_int(codepage),
				make_str(parmtype),
				make_str(desc),
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
				RTRIM(TRIGSCHEMA)  AS TRIGSCHEMA,
				RTRIM(TRIGNAME)    AS TRIGNAME,
				RTRIM(%(owner)s)   AS OWNER,
				CHAR('N')          AS SYSTEM,
				CHAR(CREATE_TIME)  AS CREATED,
				REMARKS            AS DESCRIPTION,
				RTRIM(TABSCHEMA)   AS TABSCHEMA,
				RTRIM(TABNAME)     AS TABNAME,
				TRIGTIME           AS TRIGTIME,
				TRIGEVENT          AS TRIGEVENT,
				GRANULARITY        AS GRANULARITY,
				TEXT               AS SQL
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
				desc,
				tabschema,
				tabname,
				trigtime,
				trigevent,
				granularity,
				sql,
			) in self.fetch_some(cursor):
			yield Trigger(
				make_str(schema),
				make_str(name),
				make_str(owner),
				make_bool(system),
				make_datetime(created),
				make_str(desc),
				make_str(tabschema),
				make_str(tabname),
				make_str(trigtime),
				make_str(trigevent),
				make_str(granularity),
				make_str(sql),
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
			) in self.fetch_some(cursor):
			yield TriggerDep(
				make_str(schema),
				make_str(name),
				make_str(depschema),
				make_str(depname),
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
				RTRIM(TBSPACE)    AS TBSPACE,
				RTRIM(%(owner)s)  AS OWNER,
				CASE TBSPACE
					WHEN 'SYSCATSPACE' THEN 'Y'
					WHEN 'SYSTOOLSPACE' THEN 'Y'
					ELSE 'N'
				END               AS SYSTEM,
				CHAR(CREATE_TIME) AS CREATED,
				REMARKS           AS DESCRIPTION,
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
				END               AS TYPE
			FROM
				%(schema)s.TABLESPACES

			UNION ALL

			SELECT
				'NICKNAMESPACE',
				'SYSIBM',
				'N',
				CHAR(CREATE_TIME),
				'Fake tablespace which contains all nicknames in the database',
				'Fake tablespace'
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
				desc,
				tstype,
			) in self.fetch_some(cursor):
			yield Tablespace(
				make_str(tbspace),
				make_str(owner),
				make_bool(system),
				make_datetime(created),
				make_str(desc),
				make_str(tstype),
			)

