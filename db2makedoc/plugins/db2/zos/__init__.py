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
				S.CREATEDTS              AS CREATED,
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
		codepage*      -- The codepage for character based types
		final*         -- True if the type cannot be derived from (boolean)
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
				CODEPAGE            AS CODEPAGE,
				FINAL               AS FINAL,
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
				codepage,
				final,
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
				codepage or None,
				final,
				desc
			))
		return result

