# vim: set noet sw=4 ts=4:

"""Defines the base classes for input and output plugins.

This module defines the base classes for input and output plugins. Input
plugins are expected to retrieve certain details from a database structured in
the manner dictated by the docstrings in this module. Output plugins are
expected to generate documentation (in whatever specific format they target)
from the hierarchy of database objects provided to them by the main
application.
"""

import os
import sys
import logging
import datetime
import re
import db2makedoc.db
from fnmatch import fnmatchcase as fnmatch
from itertools import chain, groupby, ifilter
from db2makedoc.util import *
from db2makedoc.tuples import (
	ConstraintRef, IndexRef, RelationDep, RelationRef, RoutineRef, TableRef,
	TablespaceRef, TriggerDep, TriggerRef
)


class PluginError(Exception):
	"""Base exception class for plugin related errors."""
	pass


class PluginLoadError(PluginError):
	"""Exception class for plugin loading errors.

	The main program converts any ImportError exceptions raised by a plugin
	into this exception. Generally, plugins should not use this error directly
	(unless they have a non-import related loading error, which is likely to be
	rare).
	"""
	pass


class PluginConfigurationError(PluginError):
	"""Exception class for plugin configuration errors.

	This exception should only be raised during the configure() method of a
	plugin."""
	pass


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
		# Construct some utility mappings for the database class conversions
		classes = [
			cls for cls in db2makedoc.db.__dict__.itervalues()
			if type(cls) == type(object)
			and issubclass(cls, db2makedoc.db.DatabaseObject)
			and hasattr(cls, 'config_names')
		]
		# Generate a mapping of configuration names to classes
		self.__names = dict(
			(config_name, cls)
			for cls in classes
			for config_name in cls.config_names
		)
		# Generate a mapping of classes to their children. Note that we "tweak"
		# the UniqueKey entry afterward otherwise it'll wind up being treated
		# as an abstract base class for PrimaryKey (which it isn't)
		self.__abstracts = dict(
			(parent, [
				child
				for child in classes
				if child != parent
				and issubclass(child, parent)
			])
			for parent in classes
		)
		self.__abstracts[db2makedoc.db.UniqueKey] = []
		# Remove concrete classes (those with no children)
		self.__abstracts = dict(
			(base, classes)
			for (base, classes) in self.__abstracts.iteritems()
			if classes
		)

	def add_option(self, name, default=None, doc=None, convert=None):
		"""Adds a new option to the configuration directory.

		Derived classes should NOT override this method.

		Derived classes are expected to call this method during construction to
		define the configuraiton options expect to receive. As future
		expansions may result in an extended prototype for this function it is
		strongly recommended that keyword arguments are used when calling it.

		Parameters:
		name    -- The name of the option
		default -- The default value for the option if it is not found in the
		           configuration
		doc     -- A description of the option and its possible values
		convert -- A function to call which should convert the option value
		           from a string into its intended type. See the utility
		           convert_X methods below
		"""
		self.options[name] = (default, doc, convert)

	def convert_path(self, value):
		"""Conversion handler for configuration values containing paths."""
		return os.path.expanduser(value)

	def convert_file(self, value, mode='rU'):
		"""Conversion handler for configuration values containing filenames.

		Note: This handler returns a file-object with the specified filename. If
		you do not want the filename opened, use convert_path() instead. If you
		wish to specify a different value for the optional mode parameter, specify
		this function in a lambda function like so:

			lambda self, value: self.convert_file(value, mode='w')

		Ths default is to opening the file for reading in univeral line-break mode.
		"""
		return open(self.convert_path(value), mode)

	def convert_int(self, value, minvalue=None, maxvalue=None):
		"""Conversion handler for configuration values containing an integer."""
		result = int(value)
		if minvalue is not None and result < minvalue:
			raise PluginConfigurationError('%d is less than the minimum (%d)' % (result, minvalue))
		if maxvalue is not None and result > maxvalue:
			raise PluginConfigurationError('%d is greater than the maximum (%d)' % (result, maxvalue))
		return result

	def convert_float(self, value, minvalue=None, maxvalue=None):
		"""Conversion handler for configuration values containing a float."""
		result = float(value)
		if minvalue is not None and result < minvalue:
			raise PluginConfigurationError('%f is less than the minimum (%f)' % (result, minvalue))
		if maxvalue is not None and result > maxvalue:
			raise PluginConfigurationError('%f is greater than the maximum (%f)' % (result, maxvalue))
		return result

	def convert_bool(self, value,
		false_values=['false', 'no', 'off', '0'],
		true_values=['true', 'yes', 'on', '1']):
		"""Conversion handler for configuration values containing a boolean."""
		try:
			return dict(
				[(key, False) for key in false_values] +
				[(key, True) for key in true_values]
			)[value.lower()]
		except KeyError:
			raise PluginConfigurationError('Invalid boolean value "%s" (use one of %s instead)' % (value, ', '.join(false_values + true_values)))

	convert_date_re = re.compile(r'(\d{4})[-/.](\d{2})[-/.](\d{2})([T -.](\d{2})[:.](\d{2})([:.](\d{2})(\.(\d{6})\d*)?)?)?')
	def convert_date(self, value):
		"""Conversion handler for configuration values containing a date/time.

		The value must contain a string containing a date and optionally time
		in ISO8601 format (although some variation in field separators is
		permitted.
		"""
		result = convert_date_re.match(value).groups()
		if result is None:
			raise PluginConfigurationError('Invalid date value "%s" (use ISO8601 format, YYYY-MM-DD HH:MM:SS)' % value)
		(yr, mon, day, _, hr, min, _, sec, _, msec) = result
		return datetime.datetime(*(int(i or '0') for i in (yr, mon, day, hr, min, sec, msec)))

	def convert_list_sub(self, value, separator=',', subconvert=None):
		"""Conversion subroutine for convert_list and other methods."""
		if value.strip() == '':
			return []
		elif subconvert is None:
			return [item.strip() for item in value.split(separator)]
		else:
			return [subconvert(item.strip()) for item in value.split(separator)]

	def convert_list(self, value, separator=',', subconvert=None, minvalues=0,
		maxvalues=None):
		"""Conversion handler for configuration values containing a list.

		Use this method within a lambda function if you wish to specify values
		for the optional separator or subconverter parameters. For example, if
		you want to convert a comma separated list of integers:

			lambda value: self.convert_list(value,
		        subconvert=self.convert_int)

		The defaults for separator and subconverter handle converting a comma
		separated list of strings. Note that no escaping mechanism is provided
		for handling commas within elements of the list.
		"""
		result = self.convert_list_sub(value, separator, subconvert)
		if len(result) < minvalues:
			raise PluginConfigurationError('"%s" must contain at least %d elements' % (value, minvalues))
		if maxvalues is not None and len(result) > maxvalues:
			raise PluginConfigurationError('"%s" must contain less than %d elements' % (value, maxvalues))
		return result

	def convert_set(self, value, separator=",", subconvert=None, minvalues=0,
		maxvalues=None):
		"""Conversion handler for configuration values containing a set.

		Use this method in the same way as convert_list() above.
		"""
		result = set(self.convert_list_sub(value, separator, subconvert))
		if len(result) < minvalues:
			raise PluginConfigurationError('"%s" must contain at least %d unique elements' % (value, minvalues))
		if maxvalues is not None and len(result) > maxvalues:
			raise PluginConfigurationError('"%s" must contain less than %d unique elements' % (value, maxvalues))
		return result

	def convert_dict(self, value, listsep=',', mapsep='=', subconvert=None,
		minvalues=0, maxvalues=None):
		"""Conversion handler for configuration values containing a set of mappings.

		This method expects a comma-separated list of key=value items. Note
		that no escaping mechanism is provided for handling elements containing
		commas or equals characters, and that the subconvert function is
		applied to the values only, not the keys.

		Use this method in the same way as convert_list() above.
		"""
		return dict(self.convert_odict(value, listsep, mapsep, subconvert, minvalues, maxvalues))

	def convert_odict(self, value, listsep=',', mapsep='=', subconvert=None,
		minvalues=0, maxvalues=None):
		"""Conversion handler for configuration values containing a set of mappings.

		This method is equivalent to convert_dict(), except it returns a list
		of two-element tuples instead of a dictionary. This is useful when the
		ordering of the mappings must be preserved (and can be easily converted
		into a dictionary, if required).

		Use this method in the same way as convert_dict() above.
		"""
		result = [
			tuple(item.split(mapsep, 1))
			for item in self.convert_list_sub(value, listsep)
		]
		if subconvert is not None:
			result = [
				(key, subconvert(value))
				for (key, value) in result
			]
		return result

	def convert_dbclass(self, value, abstract=False):
		"""Conversion handler for configuration values containing a database class.

		This conversion method handles a value which refers to a database
		class. For example, "type=table". Alternate versions (e.g. plurals) of
		the class names are accepted (see the "config_names" attribute of the
		classes in the db2makedoc.db module), and values are case insensitive.

		If the optional abstract parameter is True, abstract base classes like
		Relation, Constraint, and Routine will be permitted as the result.  If
		it is False (the default), only concrete classes will be permitted
		(anything else will raise an error).
		"""
		try:
			result = self.__names[value]
		except KeyError:
			raise PluginConfigurationError('Unknown database object type "%s"' % value)
		if not abstract and result in self.__abstracts:
			raise PluginConfigurationError('Abstract object type "%s" not permitted' % value)
		return value

	def convert_dbclasses(self, value, separator=',', abstract=False):
		"""Conversion handler for configuration values containing a set of database classes.

		This conversion method handles lists of database classes, for example
		"diagrams=alias,table,view". Alternate versions (e.g. plurals) of the
		class names are accepted (see the "config_names" attribute of the
		classes in the db2makedoc.db module), and values are case insensitive.

		If the optional abstract parameter is True, abstract base classes like
		Relation, Constraint, and Routine will be permitted in the result. If
		it is False (the default), abstract classes will be converted to the
		concrete classes descended from them (e.g. Relation becomes Alias,
		Table, View).  The result is a set (rather than a list) of classes.
		"""
		try:
			value = set(
				self.__names[name] for name in
				self.convert_set(value, separator, subconvert=lambda x: x.lower())
			)
		except KeyError, e:
			raise PluginConfigurationError('Unknown database object type "%s"' % str(e))
		if abstract:
			return value
		else:
			return set(
				child
				for parent in value
				for child in self.__abstracts.get(parent, [parent])
			)

	def configure(self, config):
		"""Loads the plugin configuration.

		This method is called by the main application to load configuration
		information from the file specified by the user. If derived classes
		override this method they should call the inherited method and then
		test that the configuration is valid.
		"""
		for (name, (default, doc, convert)) in self.options.iteritems():
			value = config.get(name, default)
			# Note: Conversion is applied to defaults as well as explicitly
			# specified values (unless the default is None, which is passed
			# thru verbatim)
			if convert is not None and value is not None:
				try:
					value = convert(value)
				except Exception, e:
					raise PluginConfigurationError('Error reading value for "%s": %s' % (name, str(e)))
			self.options[name] = value


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
		self.add_option('exclude', default=None, convert=self.convert_list,
			doc="""A comma-separated list of schema name patterns to exclude
			from the documentation. If ommitted, no objects are excluded. See
			the "include" definition for more information""")
		self.add_option('include', default=None, convert=self.convert_list,
			doc="""A comma-separated list of schema name patterns to include in
			the documentation. If ommitted, all objects are included.  Patterns
			may include * and ? as traditional wildcard characters.  If both
			"include" and "exclude" are specified, include filtering occurs
			first. Note that the filtering does not apply to schemas
			themselves, just to objects within schemas excluding datatypes.
			This ensures that, if system schemas are excluded, all objects with
			built-in datatypes do not also disappear""")

	def configure(self, config):
		"""Loads the plugin configuration."""
		super(InputPlugin, self).configure(config)
		self.include = self.options['include'] or []
		self.exclude = self.options['exclude'] or []

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
		logging.debug('Retrieving schemas')
		return []

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
		logging.debug('Retrieving datatypes')
		return []

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
		logging.debug('Retrieving tables')
		return []

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
		logging.debug('Retrieving views')
		return []

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
		logging.debug('Retrieving aliases')
		return []

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
		logging.debug('Retrieving view dependencies')
		return []

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
		logging.debug('Retrieving indexes')
		return []

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
		logging.debug('Retrieving index columns')
		return []

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
		logging.debug('Retrieving relation columns')
		return []

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
		logging.debug('Retrieving unique keys')
		return []

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
		logging.debug('Retrieving unique key columns')
		return []

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
		logging.debug('Retrieving foreign keys')
		return []

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
		logging.debug('Retrieving foreign key columns')
		return []

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
		logging.debug('Retrieving check constraints')
		return []

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
		logging.debug('Retrieving check constraint columns')
		return []

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
		logging.debug('Retrieving functions')
		return []

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
		logging.debug('Retrieving procedures')
		return []

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
		logging.debug('Retrieving routine parameters')
		return []

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
		logging.debug('Retrieving triggers')
		return []

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
		logging.debug('Retrieving trigger dependencies')
		return []

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
		logging.debug('Retrieving tablespaces')
		return []

	def filter(self, items, key=None):
		"""Filters the iterable on the specified key.

		This method filters the iterable items against this instance's
		"include" and "exclude" lists of wildcards. The key parameter, if
		specified, provides a function used to extract the string which will be
		matched against the lists. Only elements (or the key of elements) which
		match one or more filters in the "include" list (or all elements if the
		"include" list is empty), and which do not match any of the filters in
		the "exclude" list will be present in the output.

		The method returns a generator.
		"""
		if key is None:
			key = lambda x: x
		result = items
		if self.include:
			def include_predicate(item):
				return any(fnmatch(key(item), pattern) for pattern in self.include)
			result = ifilter(include_predicate, result)
		if self.exclude:
			def exclude_predicate(item):
				return not any(fnmatch(key(item), pattern) for pattern in self.exclude)
			result = ifilter(exclude_predicate, result)
		return result

	def fetch_some(self, cursor, count=10):
		"""Efficient and flexible retrieval from a database cursor.

		This generator method retrieves rows from the specified cursor in a
		flexible but efficient manner by utilizing the fetchmany() method where
		possible, or fetchall() otherwise. As a generator method, individual
		rows are yielded.
		"""
		# XXX The following can be activated when a) PyDB2 supports fetchmany
		# without crashing or b) ibm_db starts to fetch in a vaguely reasonable
		# time
		#
		#if hasattr(cursor, 'fetchmany'):
		#	while True:
		#		rows = cursor.fetchmany(count)
		#		if not rows:
		#			break
		#		for row in rows:
		#			yield row
		#else:
		#	# Some interfaces don't implement fetchmany (although they should -
		#	# it's not optional). In this case, favour speed of retrieval over
		#	# memory usage (memory is cheap - bandwidth ain't)
		for row in cursor.fetchall():
			yield row


	@cached
	def schemas(self):
		# Note: schemas themselves are not filtered because datatypes are not
		# filtered (if a system schema got excluded, system datatypes would be
		# excluded and the object hierarchy would break horribly)
		return sorted(self.get_schemas(), key=attrgetter('name'))

	@cached
	def datatypes(self):
		return sorted(self.get_datatypes(), key=attrgetter('schema', 'name'))

	@cached
	def tables(self):
		result = self.filter(self.get_tables(), key=attrgetter('schema'))
		return sorted(result, key=attrgetter('schema', 'name'))

	@cached
	def views(self):
		result = self.filter(self.get_views(), key=attrgetter('schema'))
		return sorted(result, key=attrgetter('schema', 'name'))

	@cached
	def aliases(self):
		result = self.filter(self.get_aliases(), key=attrgetter('schema'))
		result = self.filter(result, key=attrgetter('base_schema'))
		return sorted(result, key=attrgetter('schema', 'name'))

	@cached
	def relations(self):
		result = (
			namedslice(Relation, relation)
			for relation in chain(self.tables, self.views, self.aliases)
		)
		return sorted(result, key=attrgetter('schema', 'name'))

	@cached
	def relation_dependencies(self):
		result = self.filter(self.get_view_dependencies(), key=attrgetter('view_schema'))
		result = self.filter(result, key=attrgetter('dep_schema'))
		result = sorted(result, key=attrgetter('schema', 'name', 'dep_schema', 'dep_name'))
		result = groupby(result, key=attrgetter('schema', 'name'))
		return dict(
			(RelationRef(*view), [RelationRef(d.dep_schema, d.dep_name) for d in deps])
			for (view, deps) in result
		)

	@cached
	def relation_dependents(self):
		result = chain(
			(
				RelationDep(*(relation + dep))
				for (relation, deps) in self.relation_dependencies.iteritems()
				for dep in deps
			),
			(
				RelationDep(a.schema, a.name, a.base_schema, a.base_name)
				for a in self.aliases
			)
		)
		result = sorted(result, key=attrgetter('dep_schema', 'dep_name', 'schema', 'name'))
		result = groupby(result, key=attrgetter('dep_schema', 'dep_name'))
		return dict(
			(RelationRef(*relation), [RelationRef(d.schema, d.name) for d in deps])
			for (relation, deps) in result
		)

	@cached
	def indexes(self):
		result = self.filter(self.get_indexes(), key=attrgetter('schema'))
		result = self.filter(result, key=attrgetter('table_schema'))
		return sorted(result, key=attrgetter('schema', 'name'))

	@cached
	def index_cols(self):
		result = self.filter(self.get_index_cols(), key=attrgetter('index_schema'))
		result = groupby(result, key=attrgetter('index_schema', 'index_name'))
		return dict((IndexRef(*index), list(cols)) for (index, cols) in result)

	@cached
	def table_indexes(self):
		result = sorted(self.indexes, key=attrgetter('table_schema', 'table_name', 'schema', 'name'))
		result = groupby(result, key=attrgetter('table_schema', 'table_name'))
		return dict((TableRef(*table), list(indexes)) for (table, indexes) in result)

	@cached
	def relation_cols(self):
		result = self.filter(self.get_relation_cols(), key=attrgetter('relation_schema'))
		result = sorted(result, key=attrgetter('relation_schema', 'relation_name'))
		result = groupby(result, key=attrgetter('relation_schema', 'relation_name'))
		return dict((RelationRef(*relation), list(cols)) for (relation, cols) in result)

	@cached
	def unique_keys(self):
		result = self.filter(self.get_unique_keys(), key=attrgetter('table_schema'))
		result = sorted(result, key=attrgetter('table_schema', 'table_name', 'name'))
		result = groupby(result, key=attrgetter('table_schema', 'table_name'))
		return dict((TableRef(*table), list(keys)) for (table, keys) in result)

	@cached
	def unique_key_cols(self):
		result = self.filter(self.get_unique_key_cols(), key=attrgetter('const_schema'))
		result = sorted(result, key=attrgetter('const_schema', 'const_table', 'const_name'))
		result = groupby(result, key=attrgetter('const_schema', 'const_table', 'const_name'))
		return dict((ConstraintRef(*key), list(cols)) for (key, cols) in result)

	@cached
	def foreign_keys(self):
		result = self.filter(self.get_foreign_keys(), key=attrgetter('table_schema'))
		result = self.filter(result, key=attrgetter('const_schema'))
		result = sorted(result, key=attrgetter('table_schema', 'table_name', 'name'))
		result = groupby(result, key=attrgetter('table_schema', 'table_name'))
		return dict((TableRef(*table), list(keys)) for (table, keys) in result)

	@cached
	def foreign_key_cols(self):
		result = self.filter(self.get_foreign_key_cols(), key=attrgetter('const_schema'))
		result = sorted(result, key=attrgetter('const_schema', 'const_table', 'const_name'))
		result = groupby(result, key=attrgetter('const_schema', 'const_table', 'const_name'))
		return dict((ConstraintRef(*key), list(cols)) for (key, cols) in result)

	@cached
	def parent_keys(self):
		result = (key for (table, keys) in self.foreign_keys.iteritems() for key in keys)
		result = sorted(result, key=attrgetter('const_schema', 'const_table', 'const_name'))
		result = groupby(result, key=attrgetter('const_schema', 'const_table', 'const_name'))
		return dict((ConstraintRef(*ukey), list(fkeys)) for (ukey, fkeys) in result)

	@cached
	def checks(self):
		result = self.filter(self.get_checks(), key=attrgetter('table_schema'))
		result = sorted(result, key=attrgetter('table_schema', 'table_name', 'name'))
		result = groupby(result, key=attrgetter('table_schema', 'table_name'))
		return dict((TableRef(*table), list(checks)) for (table, checks) in result)

	@cached
	def check_cols(self):
		result = self.filter(self.get_check_cols(), key=attrgetter('const_schema'))
		result = sorted(result, key=attrgetter('const_schema', 'const_table', 'const_name'))
		result = groupby(result, key=attrgetter('const_schema', 'const_table', 'const_name'))
		return dict((ConstraintRef(*key), list(cols)) for (key, cols) in result)

	@cached
	def functions(self):
		result = self.filter(self.get_functions(), key=attrgetter('schema'))
		return sorted(result, key=attrgetter('schema', 'specific'))

	@cached
	def procedures(self):
		result = self.filter(self.get_procedures(), key=attrgetter('schema'))
		return sorted(result, key=attrgetter('schema', 'specific'))

	@cached
	def routine_params(self):
		result = self.filter(self.get_routine_params(), key=attrgetter('routine_schema'))
		result = sorted(result, key=attrgetter('routine_schema', 'routine_specific'))
		result = groupby(result, key=attrgetter('routine_schema', 'routine_specific'))
		return dict((RoutineRef(*routine), list(params)) for (routine, params) in result)

	@cached
	def triggers(self):
		result = self.filter(self.get_triggers(), key=attrgetter('schema'))
		return sorted(result, key=attrgetter('schema', 'name'))

	@cached
	def trigger_dependencies(self):
		result = self.filter(self.get_trigger_dependencies(), key=attrgetter('schema'))
		result = self.filter(result, key=attrgetter('table_schema'))
		result = sorted(result, key=attrgetter('trig_schema', 'trig_name', 'dep_schema', 'dep_name'))
		result = groupby(result, key=attrgetter('trig_schema', 'trig_name'))
		return dict(
			(TriggerRef(*trigger), [RelationRef(d.dep_schema, d.dep_name) for d in deps])
			for (trigger, deps) in result
		)

	@cached
	def trigger_dependents(self):
		result = (
			TriggerDep(*(trigger + dep))
			for (trigger, deps) in self.trigger_dependencies.iteritems()
			for dep in deps
		)
		result = sorted(result, key=attrgetter('dep_schema', 'dep_name', 'trig_schema', 'trig_name'))
		result = groupby(result, key=attrgetter('dep_schema', 'dep_name'))
		return dict(
			(RelationRef(*relation), [TriggerRef(d.trig_schema, d.trig_name) for d in deps])
			for (relation, deps) in result
		)

	@cached
	def relation_triggers(self):
		result = sorted(self.triggers, key=attrgetter('relation_schema', 'relation_name', 'schema', 'name'))
		result = groupby(result, key=attrgetter('relation_schema', 'relation_name'))
		return dict((RelationRef(*relation), list(triggers)) for (relation, triggers) in result)

	@cached
	def tablespaces(self):
		return sorted(self.get_tablespaces(), key=attrgetter('name'))

	@cached
	def tablespace_tables(self):
		result = sorted(self.tables, key=attrgetter('tbspace', 'schema', 'name'))
		result = groupby(result, key=attrgetter('tbspace'))
		return dict((TablespaceRef(tbspace), list(tables)) for (tbspace, tables) in result)

	@cached
	def tablespace_indexes(self):
		result = sorted(self.indexes, key=attrgetter('tbspace', 'schema', 'name'))
		result = groupby(result, key=attrgetter('tbspace'))
		return dict((TablespaceRef(tbspace), list(indexes)) for (tbspace, indexes) in result)

