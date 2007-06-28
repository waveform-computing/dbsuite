# $Header$
# vim: set noet sw=4 ts=4:

"""Defines the base classes for input and output plugins.

This module defines the base classes for input and output plugins. Input
plugins are expected to retrieve certain details from a database structured in
the manner dictated by the docstrings in this module. Output plugins are
expected to generate documentation (in whatever specific format they target)
from the hierarchy of database objects provided to them by the main
application.
"""

import sys
import logging
from fnmatch import fnmatchcase as fnmatch

if sys.hexversion < 0x02050000:
	# Define the any() and all() functions for backward compatibility with
	# Python 2.4
	def all(iterable):
		for element in iterable:
			if not element:
				return False
		return True

	def any(iterable):
		for element in iterable:
			if element:
				return True
		return False

# Constants
EXCLUDE_OPTION = 'exclude'
INCLUDE_OPTION = 'include'

# Localizable strings
EXCLUDE_DESC = """A comma-separated list of schema name patterns to
	exclude from the documentation. If nothing is specified, no
	objects are excluded. See the "%(include)s" definition for more
	information""" % {
		'include': INCLUDE_OPTION,
	}
INCLUDE_DESC = """A comma-separated list of schema name patterns to
	include in the documentation. If nothing is specified, all
	objects are included. Patterns may include * and ? as traditional
	wildcard characters. If both "%(include)s" and "%(exclude)s"
	are specified, include filtering occurs first. Note that the
	filtering does not apply to schemas themselves, just to objects
	with schemas excluding datatypes.  This ensures that, if system
	schemas are excluded, all objects with built-in datatypes do not
	also disappear""" % {
		'include': INCLUDE_OPTION,
		'exclude': EXCLUDE_OPTION,
	}


class Plugin(object):
	"""Abstract base class for plugins.
	
	Do not derive plugins directly from this class. Use either the InputPlugin
	or OutputPlugin classes defined below. This class contains methods common
	to both InputPlugin and OutputPlugin (some of which developers may wish to
	override in plugin implementations).
	"""

	def __init__(self):
		"""Initializes an instance of the class.

		Plugins derived from this class are expected to set up the options
		that the plugin can accept by calling the add_option() method during
		construction. This allows the main application to present the user with
		a list of possible configuration options when requested.

		Other than setting up the options, the derived constructor is expected
		to do nothing else (other than call the inherited constructor of
		course).

		"""
		super(Plugin, self).__init__()
		self.options = {}

	def add_option(self, name, default=None, doc=None):
		"""Adds a new option to the configuration directory.

		Derived classes should NOT override this method.

		Derived classes are expected to call this method during construction to
		define the configuraiton options expect to receive. Currently, this is
		a very basic mechanism. In future it may be expanded to include some
		rudimentary type checking and validation (currently derived classes
		must perform any validation themselves during the execute() call).

		As such future expansions may result in an extended prototype for this
		function it is strongly recommended that keyword arguments are used
		when calling it.
		"""
		self.options[name] = (default, doc)
	
	def configure(self, config):
		"""Loads the plugin configuration.

		This method is called by the main application to load configuration
		information from the file specified by the user. If derived classes
		override this method they should call the inherited method and then
		test that the configuration is valid.
		"""
		for (name, (default, doc)) in self.options.iteritems():
			if name in config:
				self.options[name] = config[name]
			else:
				self.options[name] = default


class OutputPlugin(Plugin):
	"""Abstract base class for output plugins.

	Derived classes must include a description of the plugin in the class'
	docstring (this is used by the main application with the --help-plugin and
	--help-plugins switches).
	"""

	def execute(self, database):
		"""Invokes the plugin to produce documentation.

		This method is called by the main application with the database for
		which the plugin should produce documentation. Derived classes must
		override this method to implement this action, using the configuration
		supplied in the self.options dictionary (which by this point will
		simply map names to values with any documentation stripped out).

		This base class provides no "help" for implementing this method as the
		number of different types of documentation that could be produced (and
		the ways in which to produce them) are infinite. Output plugin
		developers should explore the output plugins distributed with the
		application to determine whether one of them could be subclassed as a
		more convenient implementation base.
		"""
		pass


class InputPlugin(Plugin):
	"""Abstract base class for input plugins.

	Derived classes must include a description of the plugin in the class'
	docstring (this is used by the main application with the --help-plugin and
	--help-plugins switches).
	"""

	def __init__(self):
		"""Initializes an instance of the class."""
		super(InputPlugin, self).__init__()
		self.add_option(EXCLUDE_OPTION, default=None, doc=EXCLUDE_DESC)
		self.add_option(INCLUDE_OPTION, default=None, doc=INCLUDE_DESC)
		self.__schemas = None
		self.__datatypes = None
		self.__tables = None
		self.__views = None
		self.__aliases = None
		self.__view_dependencies = None
		self.__relation_dependencies = None
		self.__relation_dependents = None
		self.__indexes = None
		self.__index_cols = None
		self.__table_indexes = None
		self.__relation_cols = None
		self.__unique_keys = None
		self.__unique_keys_list = None
		self.__unique_key_cols = None
		self.__foreign_keys = None
		self.__foreign_keys_list = None
		self.__foreign_key_cols = None
		self.__parent_keys = None
		self.__checks = None
		self.__checks_list = None
		self.__check_cols = None
		self.__functions = None
		self.__function_params = None
		self.__procedures = None
		self.__procedure_params = None
		self.__triggers = None
		self.__trigger_dependencies = None
		self.__relation_triggers = None
		self.__tablespaces = None
		self.__tablespace_tables = None
		self.__tablespace_indexes = None

	def configure(self, config):
		"""Loads the plugin configuration."""
		super(InputPlugin, self).configure(config)
		if self.options[INCLUDE_OPTION]:
			self.include = [s.strip() for s in self.options[INCLUDE_OPTION].split(',')]
		else:
			self.include = []
		if self.options[EXCLUDE_OPTION]:
			self.exclude = [s.strip() for s in self.options[EXCLUDE_OPTION].split(',')]
		else:
			self.exclude = []

	def open(self):
		"""Opens the database connection for data retrieval.

		This method is called by the main application to "start" the plugin.
		Derived classes should override this method to open the database
		connection, using the configuration specified in the self.options
		dictionary (which by this point will simply map names to values, with
		any documentation stripped out).

		This method is NOT expected to actually retrieve any data from the
		database (although it can do if the developer wishes) - the private
		property getters will handle calling the other derived methods to do
		this.
		"""
		pass
	
	def close(self):
		"""Closes the database connection and cleans up any resources.

		This method is called by the main application to "stop" the plugin
		once it has retrieved all the necessary data. Given Python's garbage
		collection it is not usually necessary to do anything here. However,
		if a plugin author has obtained any explicit locks on the source
		database or wishes to ensure the connection closes as rapidly as
		possible, this is the place to do it.
		"""
		pass

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
		logging.debug('Retrieving schemas')
		return []

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
		logging.debug('Retrieving datatypes')
		return []

	def get_tables(self):
		"""Retrieves the details of tables stored in the database.

		Override this function to return a list of tuples containing details of
		the tables (NOT views) defined in the database (including system
		tables). The tuples contain the following details in the order
		specified:

		schema        -- The schema of the table
		name          -- The name of the table
		owner*        -- The name of the user who owns the table
		system        -- True if the table is system maintained (boolean)
		created*      -- When the table was created (datetime)
		laststats*    -- When the table's statistics were last calculated (datetime)
		cardinality*  -- The approximate number of rows in the table
		size*         -- The approximate size in bytes of the table
		tbspace       -- The name of the primary tablespace containing the table
		description*  -- Descriptive text

		* Optional (can be None)
		"""
		logging.debug('Retrieving tables')
		return []

	def get_views(self):
		"""Retrieves the details of views stored in the database.

		Override this function to return a list of tuples containing details of
		the views defined in the database (including system views). The tuples
		contain the following details in the order specified:

		schema        -- The schema of the view
		name          -- The name of the view
		owner*        -- The name of the user who owns the view
		system        -- True if the view is system maintained (boolean)
		created*      -- When the view was created (datetime)
		readonly*     -- True if the view is not updateable (boolean)
		sql*          -- The SQL statement/query that defined the view
		description*  -- Descriptive text

		* Optional (can be None)
		"""
		logging.debug('Retrieving views')
		return []

	def get_aliases(self):
		"""Retrieves the details of aliases stored in the database.

		Override this function to return a list of tuples containing details of
		the aliases (also known as synonyms in some systems) defined in the
		database (including system aliases). The tuples contain the following
		details in the order specified:

		schema        -- The schema of the alias
		name          -- The name of the alias
		owner*        -- The name of the user who owns the alias
		system        -- True if the alias is system maintained (boolean)
		created*      -- When the alias was created (datetime)
		base_schema   -- The schema of the target relation
		base_table    -- The name of the target relation
		description*  -- Descriptive text

		* Optional (can be None)
		"""
		logging.debug('Retrieving aliases')
		return []

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
		logging.debug('Retrieving view dependencies')
		return []

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
		system        -- True if the index is system maintained (boolean)
		created*      -- When the index was created (datetime)
		laststats*    -- When the index statistics were last updated (datetime)
		cardinality*  -- The approximate number of values in the index
		size*         -- The approximate size in bytes of the index
		unique        -- True if the index contains only unique values (boolean)
		tbspace       -- The name of the tablespace which contains the index
		description*  -- Descriptive text

		* Optional (can be None)
		"""
		logging.debug('Retrieving indexes')
		return []

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

		Note that the each tuple details one column belonging to an index. It
		is important that the list of tuples is in the order that each column
		is declared in an index.
		"""
		logging.debug('Retrieving index columns')
		return []

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

		Note that each tuple details one column belonging to a relation. It is
		important that the list of tuples is in the order that each column is
		declared in a relation.

		* Optional (can be None)
		"""
		logging.debug('Retrieving relation columns')
		return []

	def get_unique_keys(self):
		"""Retrieves the details of unique keys stored in the database.

		Override this function to return a list of tuples containing details of
		the unique keys defined in the database. The tuples contain the
		following details in the order specified:

		schema        -- The schema of the table containing the key
		name          -- The name of the table containing the key
		keyname       -- The name of the key
		owner*        -- The name of the user who owns the key
		system        -- True if the key is system maintained (boolean)
		created*      -- When the key was created (datetime)
		primary       -- True if the unique key is also a primary key
		description*  -- Descriptive text

		* Optional (can be None)
		"""
		logging.debug('Retrieving unique keys')
		return []

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
		logging.debug('Retrieving unique key columns')
		return []

	def get_foreign_keys(self):
		"""Retrieves the details of foreign keys stored in the database.

		Override this function to return a list of tuples containing details of
		the foreign keys defined in the database. The tuples contain the
		following details in the order specified:

		schema        -- The schema of the table containing the key
		name          -- The name of the table containing the key
		keyname       -- The name of the key
		owner*        -- The name of the user who owns the key
		system        -- True if the key is system maintained (boolean)
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
		logging.debug('Retrieving foreign keys')
		return []

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
		logging.debug('Retrieving foreign key columns')
		return []

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
		logging.debug('Retrieving check constraints')
		return []

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
		logging.debug('Retrieving check constraint columns')
		return []

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
		logging.debug('Retrieving functions')
		return []

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
		logging.debug('Retrieving function parameters')
		return []

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
		logging.debug('Retrieving procedures')
		return []

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
		logging.debug('Retrieving procedure parameters')
		return []

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
		logging.debug('Retrieving triggers')
		return []

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
		logging.debug('Retrieving trigger dependencies')
		return []

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
		logging.debug('Retrieving tablespaces')
		return []

	def _filter(self, items, *elements):
		"""Filters the items list of tuples  on the specified elements.

		This method returns the list of tuples from elements which match one or
		more filters in the "include" list specified in the configuration (or
		all tuples if the "include" list is empty), and which do not match any
		of the filters in the "exclude" list. The elements iterable specifies
		the numeric indices of the element(s) in each tuple that should be
		compared to the filter lists.
		"""
		assert len(elements) > 0
		for element in elements:
			items = [
				item for item in items
				if (len(self.include) == 0 or any([
					fnmatch(item[element], pattern)
					for pattern in self.include
				]))
				and not any([
					fnmatch(item[element], pattern)
					for pattern in self.exclude
				])
			]
		return items

	def _get_schemas(self):
		if self.__schemas is None:
			# Note: schemas themselves are not filtered
			self.__schemas = self.get_schemas()
		return self.__schemas

	def _get_datatypes(self):
		if self.__datatypes is None:
			self.__datatypes = self.get_datatypes()
		return self.__datatypes

	def _get_tables(self):
		if self.__tables is None:
			self.__tables = self._filter(self.get_tables(), 0)
		return self.__tables

	def _get_views(self):
		if self.__views is None:
			self.__views = self._filter(self.get_views(), 0)
		return self.__views

	def _get_aliases(self):
		if self.__aliases is None:
			self.__aliases = self._filter(self.get_aliases(), 0, 5)
		return self.__aliases

	def _get_relations(self):
		for i in self.tables:
			yield i[:5]
		for i in self.views:
			yield i[:5]
		for i in self.aliases:
			yield i[:5]

	def _get_relation_dependencies(self):
		if self.__relation_dependencies is None:
			if self.__view_dependencies is None:
				self.__view_dependencies = self._filter(self.get_view_dependencies(), 0, 2)
			self.__relation_dependencies = dict([
				(relation[:2], [dep[2:4]
					for dep in self.__view_dependencies
					if relation[:2] == dep[:2]
				])
				for relation in self.relations
			])
		return self.__relation_dependencies

	def _get_relation_dependents(self):
		if self.__relation_dependents is None:
			if self.__view_dependencies is None:
				self.__view_dependencies = self._filter(self.get_view_dependencies(), 0, 2)
			self.__relation_dependents = dict([
				(relation[:2], [dep[:2]
					for dep in self.__view_dependencies
					if relation[:2] == dep[2:4]
				])
				for relation in self.relations
			])
		return self.__relation_dependents

	def _get_indexes(self):
		if self.__indexes is None:
			self.__indexes = self._filter(self.get_indexes(), 0, 2)
		return self.__indexes

	def _get_index_cols(self):
		if self.__index_cols is None:
			indexcols = self._filter(self.get_index_cols(), 0)
			self.__index_cols = dict([
				(index[:2], [indexcol[2:]
					for indexcol in indexcols
					if index[:2] == indexcol[:2]
				])
				for index in self.indexes
			])
		return self.__index_cols

	def _get_table_indexes(self):
		if self.__table_indexes is None:
			self.__table_indexes = dict([
				(table[:2], [index[:2]
					for index in self.indexes
					if table[:2] == index[2:4]
				])
				for table in self.tables
			])
		return self.__table_indexes

	def _get_relation_cols(self):
		if self.__relation_cols is None:
			relationcols = self._filter(self.get_relation_cols(), 0)
			self.__relation_cols = dict([
				(relation[:2], [relationcol[2:]
					for relationcol in relationcols
					if relation[:2] == relationcol[:2]
				])
				for relation in self.tables + self.views + self.aliases
			])
		return self.__relation_cols

	def _get_unique_keys(self):
		if self.__unique_keys is None:
			ukeys = self._filter(self.get_unique_keys(), 0)
			self.__unique_keys = dict([
				(table[:2], [ukey[2:]
					for ukey in ukeys
					if table[:2] == ukey[:2]
				])
				for table in self.tables
			])
		return self.__unique_keys

	def _get_unique_keys_list(self):
		if self.__unique_keys_list is None:
			self.__unique_keys_list = reduce(lambda a,b: a+b,
				[
					[(schema, name) + key for key in keys]
					for ((schema, name), keys) in self.unique_keys.iteritems()
					if len(keys) > 0
				], []
			)
		return self.__unique_keys_list

	def _get_unique_key_cols(self):
		if self.__unique_key_cols is None:
			ukeycols = self._filter(self.get_unique_key_cols(), 0)
			self.__unique_key_cols = dict([
				(ukey[:3], [ukeycol[3]
					for ukeycol in ukeycols
					if ukey[:3] == ukeycol[:3]
				])
				for ukey in self.unique_keys_list
			])
		return self.__unique_key_cols

	def _get_foreign_keys(self):
		if self.__foreign_keys is None:
			fkeys = self._filter(self.get_foreign_keys(), 0, 6)
			self.__foreign_keys = dict([
				(table[:2], [fkey[2:]
					for fkey in fkeys
					if table[:2] == fkey[:2]
				])
				for table in self.tables
			])
		return self.__foreign_keys

	def _get_foreign_keys_list(self):
		if self.__foreign_keys_list is None:
			self.__foreign_keys_list = reduce(lambda a,b: a+b,
				[
					[(schema, name) + key for key in keys]
					for ((schema, name), keys) in self.foreign_keys.iteritems()
					if len(keys) > 0
				], []
			)
		return self.__foreign_keys_list

	def _get_foreign_key_cols(self):
		if self.__foreign_key_cols is None:
			fkeycols = self._filter(self.get_foreign_key_cols(), 0)
			self.__foreign_key_cols = dict([
				(fkey[:3], [fkeycol[3:]
					for fkeycol in fkeycols
					if fkey[:3] == fkeycol[:3]
				])
				for fkey in self.foreign_keys_list
			])
		return self.__foreign_key_cols

	def _get_parent_keys(self):
		if self.__parent_keys is None:
			self.__parent_keys = dict([
				(ukey[:3], [fkey[:3]
					for fkey in self.foreign_keys_list
					if ukey[:3] == fkey[6:9]
				])
				for ukey in self.unique_keys_list
			])
		return self.__parent_keys

	def _get_checks(self):
		if self.__checks is None:
			checks = self._filter(self.get_checks(), 0)
			self.__checks = dict([
				(table[:2], [check[2:]
					for check in checks
					if table[:2] == check[:2]
				])
				for table in self.tables
			])
		return self.__checks

	def _get_checks_list(self):
		if self.__checks_list is None:
			self.__checks_list = reduce(lambda a,b: a+b,
				[
					[(schema, name) + check for check in checks]
					for ((schema, name), checks) in self.checks.iteritems()
					if len(checks) > 0
				], []
			)
		return self.__checks_list

	def _get_check_cols(self):
		if self.__check_cols is None:
			checkcols = self._filter(self.get_check_cols(), 0)
			self.__check_cols = dict([
				(check[:3], [checkcol[3]
					for checkcol in checkcols
					if check[:3] == checkcol[:3]
				])
				for check in self.checks_list
			])
		return self.__check_cols

	def _get_functions(self):
		if self.__functions is None:
			self.__functions = self._filter(self.get_functions(), 0)
		return self.__functions

	def _get_function_params(self):
		if self.__function_params is None:
			params = self._filter(self.get_function_params(), 0)
			self.__function_params = dict([
				(function[:2], [param[2:]
					for param in params
					if function[:2] == param[:2]
				])
				for function in self.functions
			])
		return self.__function_params

	def _get_procedures(self):
		if self.__procedures is None:
			self.__procedures = self._filter(self.get_procedures(), 0)
		return self.__procedures

	def _get_procedure_params(self):
		if self.__procedure_params is None:
			params = self._filter(self.get_procedure_params(), 0)
			self.__procedure_params = dict([
				(procedure[:2], [param[2:]
					for param in params
					if procedure[:2] == param[:2]
				])
				for procedure in self.procedures
			])
		return self.__procedure_params

	def _get_triggers(self):
		if self.__triggers is None:
			self.__triggers = self._filter(self.get_triggers(), 0, 5)
		return self.__triggers

	def _get_trigger_dependencies(self):
		if self.__trigger_dependencies is None:
			trigdeps = self._filter(self.get_trigger_dependencies(), 0, 2)
			self.__trigger_dependencies = dict([
				(trigger[:2], [trigdep[2:4]
					for trigdep in trigdeps
					if trigger[:2] == trigdep[:2]
				])
				for trigger in self.triggers
			])
		return self.__trigger_dependencies

	def _get_relation_triggers(self):
		if self.__relation_triggers is None:
			self.__relation_triggers = dict([
				(relation[:2], [trigger[:2]
					for trigger in self.triggers
					if relation[:2] == trigger[5:7]
				])
				for relation in self.relations
			])
		return self.__relation_triggers

	def _get_tablespaces(self):
		if self.__tablespaces is None:
			self.__tablespaces = self.get_tablespaces()
		return self.__tablespaces

	def _get_tablespace_tables(self):
		if self.__tablespace_tables is None:
			self.__tablespace_tables = dict([
				(tbspace[0], [table[:2]
					for table in self.tables
					if tbspace[0] == table[8]
				])
				for tbspace in self.tablespaces
			])
		return self.__tablespace_tables

	def _get_tablespace_indexes(self):
		if self.__tablespace_indexes is None:
			self.__tablespace_indexes = dict([
				(tbspace[0], [index[:2]
					for index in self.indexes
					if tbspace[0] == index[11]
				])
				for tbspace in self.tablespaces
			])
		return self.__tablespace_indexes

	schemas = property(lambda self: self._get_schemas())
	datatypes = property(lambda self: self._get_datatypes())
	tables = property(lambda self: self._get_tables())
	table_indexes = property(lambda self: self._get_table_indexes())
	views = property(lambda self: self._get_views())
	aliases = property(lambda self: self._get_aliases())
	relations = property(lambda self: self._get_relations())
	relation_dependencies = property(lambda self: self._get_relation_dependencies())
	relation_dependents = property(lambda self: self._get_relation_dependents())
	indexes = property(lambda self: self._get_indexes())
	index_cols = property(lambda self: self._get_index_cols())
	relation_cols = property(lambda self: self._get_relation_cols())
	unique_keys = property(lambda self: self._get_unique_keys())
	unique_keys_list = property(lambda self: self._get_unique_keys_list())
	unique_key_cols = property(lambda self: self._get_unique_key_cols())
	foreign_keys = property(lambda self: self._get_foreign_keys())
	foreign_keys_list = property(lambda self: self._get_foreign_keys_list())
	foreign_key_cols = property(lambda self: self._get_foreign_key_cols())
	parent_keys = property(lambda self: self._get_parent_keys())
	checks = property(lambda self: self._get_checks())
	checks_list = property(lambda self: self._get_checks_list())
	check_cols = property(lambda self: self._get_check_cols())
	functions = property(lambda self: self._get_functions())
	function_params = property(lambda self: self._get_function_params())
	procedures = property(lambda self: self._get_procedures())
	procedure_params = property(lambda self: self._get_procedure_params())
	triggers = property(lambda self: self._get_triggers())
	trigger_dependencies = property(lambda self: self._get_trigger_dependencies())
	relation_triggers = property(lambda self: self._get_relation_triggers())
	tablespaces = property(lambda self: self._get_tablespaces())
	tablespace_tables = property(lambda self: self._get_tablespace_tables())
	tablespace_indexes = property(lambda self: self._get_tablespace_indexes())

