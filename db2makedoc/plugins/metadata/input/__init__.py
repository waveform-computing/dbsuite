# vim: set noet sw=4 ts=4:

"""Input plugin for XML metadata storage."""

import logging
import re
import datetime
import db2makedoc.plugins
from db2makedoc.etree import parse, iselement


_timestamp_re = re.compile(r'^(\d{4})-(\d{2})-(\d{2})[T -]((\d{2})[:.](\d{2})[:.](\d{2})(\.(\d+))?)?$')
def timestamp(value):
	"""Utility routine for converting a value into a datetime object.

	This routine is used to transform values extracted from the XML document
	which contain ISO8601 formatted timestamps into internal Python datetime
	objects. If value is None, the result is None. Otherwise, the value is
	assumed to contain a value timestamp and conversion is attempted.
	"""
	if value is not None:
		try:
			m = _timestamp_re.match(value)
			if m:
				(yr, mth, day, _, hr, min, sec, _, msec) = m.groups()
				if not msec:
					msec = 0
				else:
					msec = msec[:6]
					msec += '0' * (6 - len(msec))
				if hr is not None:
					return datetime.datetime(int(yr), int(mth), int(day), int(hr), int(min), int(sec), int(msec))
				else:
					return datetime.datetime(int(yr), int(mth), int(day))
			else:
				raise ValueError()
		except ValueError, e:
			raise ValueError('Invalid timestamp representation: %s' % value)
	else:
		return None

def integer(value):
	"""Utility routine for converting a value into an integer/long object.

	This routine is used to transform values extracted from the XML document.
	If value is None, the result is None. Otherwise, the value is assumed to
	contain an integer value, and conversion is attempted into the smallest
	suitable type.
	"""
	if value is not None:
		assert isinstance(value, basestring)
		if len(value) < 10:
			return int(value)
		else:
			return long(value)
	else:
		return None

def text(value):
	"""Utility routine for extracting text from a potential element.

	This routine is used to extract text from within an element, if one
	is found. If value is None, the result is None. Otherwise, the value
	is the text property of the provided element.
	"""
	if iselement(value):
		return value.text
	else:
		return None

class InputPlugin(db2makedoc.plugins.InputPlugin):
	"""Input plugin for metadata storage (in XML format).

	This input plugin extracts database metadata from an XML file. This is
	intended for use in conjunction with the metadata output plugin, if you
	want metadata extraction and document creation to be performed separately
	(on separate machines or at separate times), or if you wish to use
	db2makedoc to use metadata in a transportable format from some other
	application.  The DTD of th einput is not fully documented at the present
	time. The best way to learn it is to look at the output of the metadata.out
	plugin.
	"""

	def __init__(self):
		"""Initializes an instance of the class."""
		super(InputPlugin, self).__init__()
		self.add_option('filename', default=None, convert=self.convert_path,
			doc="""The filename for the XML output file (mandatory)""")
	
	def configure(self, config):
		"""Loads the plugin configuration."""
		super(InputPlugin, self).configure(config)
		# Ensure the filename was specified and that we can open it
		if not self.options['filename']:
			raise db2makedoc.plugins.PluginConfigurationError('The filename option must be specified')
		try:
			open(self.options['filename'], 'rb')
		except Exception, e:
			raise db2makedoc.plugins.PluginConfigurationError('Unable to open the specified file: %s' % str(e))

	def open(self):
		"""Opens and parses the source file."""
		super(InputPlugin, self).open()
		# Open and parse the document, and check its got the right root
		self.doc = parse(self.options['filename']).getroot()
		if self.doc.tag != 'database':
			raise db2makedoc.plugins.PluginError('Document root element must be "database"')
		self.name = self.doc.attrib['name']
		# Generate a parent map for the document (we'll need this later to
		# lookup the parents of nodes addressed by ID)
		self.parents = dict(
			(child, parent)
			for parent in self.doc.getiterator()
			for child in parent
		)
		# Generate an ID map (the structure uses a lot of IDREFS, so this
		# speeds things up considerably)
		self.ids = dict(
			(elem.attrib['id'], elem)
			for elem in self.doc.getiterator()
			if 'id' in elem.attrib
		)
	
	def close(self):
		"""Closes the source file and cleans up any resources."""
		super(InputPlugin, self).close()
		del self.parents
		del self.doc
	
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
		for schema in self.doc.findall('schema'):
			result.append((
				schema.attrib['name'],
				schema.attrib.get('owner'),
				bool(schema.attrib.get('system')),
				timestamp(schema.attrib.get('created')),
				text(schema.find('description')),
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
		for schema in self.doc.findall('schema'):
			for datatype in schema.findall('datatype'):
				source = self.ids.get(datatype.attrib.get('source'))
				result.append((
					schema.attrib['name'],
					datatype.attrib['name'],
					datatype.attrib.get('owner'),
					bool(datatype.attrib.get('system')),
					timestamp(datatype.attrib.get('created')),
					source and self.parents[source].attrib['name'],
					source and source.attrib['name'],
					source and datatype.attrib.get('size'),
					source and datatype.attrib.get('scale'),
					None, # XXX Not present in metadata.out
					False, # XXX Not present in metadata.out
					text(datatype.find('description')),
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
		for schema in self.doc.findall('schema'):
			for table in schema.findall('table'):
				tbspace = self.ids[table.attrib['tablespace']]
				result.append((
					schema.attrib['name'],
					table.attrib['name'],
					table.attrib.get('owner'),
					bool(table.attrib.get('system')),
					timestamp(table.attrib.get('created')),
					timestamp(table.attrib.get('laststats')),
					integer(table.attrib.get('cardinality')),
					integer(table.attrib.get('size')),
					tbspace.attrib['name'],
					text(table.find('description')),
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
		for schema in self.doc.findall('schema'):
			for view in schema.findall('view'):
				sql = view.find('sql')
				result.append((
					schema.attrib['name'],
					view.attrib['name'],
					view.attrib.get('owner'),
					bool(view.attrib.get('system')),
					timestamp(view.attrib.get('created')),
					bool(view.attrib.get('readonly')),
					sql and sql.text,
					text(view.find('description')),
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
		for schema in self.doc.findall('schema'):
			for alias in schema.findall('alias'):
				base = self.ids[alias.attrib['relation']]
				result.append((
					schema.attrib['name'],
					alias.attrib['name'],
					alias.attrib.get('owner'),
					bool(alias.attrib.get('system')),
					timestamp(alias.attrib.get('created')),
					self.parents[base].attrib['name'],
					base.attrib['name'],
					text(alias.find('description')),
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
		for schema in self.doc.findall('schema'):
			for view in schema.findall('view'):
				for dep in view.findall('viewdep'):
					ref = self.ids[dep.attrib['ref']]
					result.append((
						schema.attrib['name'],
						view.attrib['name'],
						self.parents[ref].attrib['name'],
						ref.attrib['name'],
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
		for schema in self.doc.findall('schema'):
			for index in schema.findall('index'):
				table = self.ids[index.attrib['table']]
				tbspace = self.ids[index.attrib['tbspace']]
				result.append((
					schema.attrib['name'],
					index.attrib['name'],
					self.parents[table].attrib['name'],
					table.attrib['name'],
					index.attrib.get('owner'),
					bool(index.attrib.get('system')),
					timestamp(index.attrib.get('created')),
					timestamp(index.attrib.get('laststats')),
					integer(index.attrib.get('cardinality')),
					integer(index.attrib.get('size')),
					bool(index.attrib.get('unique')),
					tbspace.attrib['name'],
					text(index.find('description')),
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
		lookup = {'asc': 'A', 'desc': 'D', 'include': 'I'}
		for schema in self.doc.findall('schema'):
			for index in schema.findall('index'):
				for field in index.findall('indexfield'):
					ref = self.ids[field.attrib['ref']]
					result.append((
						schema.attrib['name'],
						index.attrib['name'],
						ref.attrib['name'],
						lookup[field.attrib['order']],
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
		lookup = {'always': 'A', 'default': 'D'}
		for schema in self.doc.findall('schema'):
			for relation in schema.findall('table') + schema.findall('view') + schema.findall('alias'):
				for field in relation.findall('field'):
					datatype = self.ids[field.attrib['datatype']]
					result.append((
						schema.attrib['name'],
						relation.attrib['name'],
						field.attrib['name'],
						self.parents[datatype].attrib['name'],
						datatype.attrib['name'],
						bool(field.attrib.get('identity')),
						integer(field.attrib.get('size')),
						integer(field.attrib.get('scale')),
						field.attrib.get('codepage'),
						bool(field.attrib.get('nullable')),
						integer(field.attrib.get('cardinality')),
						integer(field.attrib.get('null_cardinality')),
						lookup.get(field.attrib.get('generated'), 'N'),
						field.attrib.get('expression', field.attrib.get('default')),
						text(field.find('description')),
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
		for schema in self.doc.findall('schema'):
			for table in schema.findall('table'):
				for key in table.findall('uniquekey') + table.findall('primarykey'):
					result.append((
						schema.attrib['name'],
						table.attrib['name'],
						key.attrib['name'],
						key.attrib.get('owner'),
						bool(key.attrib.get('system')),
						timestamp(key.attrib.get('created')),
						key.tag == 'primarykey',
						text(key.find('description')),
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
		for schema in self.doc.findall('schema'):
			for table in schema.findall('table'):
				for key in table.findall('uniquekey') + table.findall('primarykey'):
					for field in key.findall('keyfield'):
						ref = self.ids[field.attrib['ref']]
						result.append((
							schema.attrib['name'],
							table.attrib['name'],
							key.attrib['name'],
							ref.attrib['name'],
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
		lookup = {'noaction': 'A', 'cascade': 'C', 'setnull': 'N', 'restrict': 'R'}
		for schema in self.doc.findall('schema'):
			for table in schema.findall('table'):
				for key in table.findall('foreignkey'):
					ref = self.ids[key.attrib['references']]
					result.append((
						schema.attrib['name'],
						table.attrib['name'],
						key.attrib['name'],
						key.attrib.get('owner'),
						bool(key.attrib.get('system')),
						timestamp(key.attrib.get('created')),
						self.parents[self.parents[ref]].attrib['name'],
						self.parents[ref].attrib['name'],
						ref.attrib['name'],
						lookup[key.attrib['ondelete']],
						lookup[key.attrib['onupdate']],
						text(key.find('description')),
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
		for schema in self.doc.findall('schema'):
			for table in schema.findall('table'):
				for key in table.findall('foreignkey'):
					for field in key.findall('fkeyfield'):
						sourceref = self.ids[field.attrib['sourceref']]
						targetref = self.ids[field.attrib['targetref']]
						result.append((
							schema.attrib['name'],
							table.attrib['name'],
							key.attrib['name'],
							sourceref.attrib['name'],
							targetref.attrib['name'],
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
		for schema in self.doc.findall('schema'):
			for table in schema.findall('table'):
				for check in table.findall('check'):
					result.append((
						schema.attrib['name'],
						table.attrib['name'],
						check.attrib['name'],
						check.attrib.get('owner'),
						bool(check.attrib.get('system')),
						timestamp(check.attrib.get('created')),
						check.attrib.get('expression'), # XXX This should be a sub-element
						text(check.find('description')),
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
		for schema in self.doc.findall('schema'):
			for table in schema.findall('table'):
				for check in table.findall('check'):
					for field in check.findall('checkfield'):
						ref = self.ids[field.attrib['ref']]
						result.append((
							schema.attrib['name'],
							table.attrib['name'],
							check.attrib['name'],
							ref.attrib['name'],
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
		lookup_type = {'column': 'C', 'row': 'R', 'table': 'T', 'scalar': 'S'}
		lookup_access = {'none': 'N', 'contains': 'C', 'reads': 'R', 'modifies': 'M'}
		for schema in self.doc.findall('schema'):
			for function in schema.findall('function'):
				result.append((
					schema.attrib['name'],
					function.attrib['specificname'],
					function.attrib['name'],
					function.attrib.get('owner'),
					bool(function.attrib.get('system')),
					timestamp(function.attrib.get('created')),
					lookup_type[function.attrib['type']],
					bool(function.attrib.get('deterministic')), # XXX Optional
					bool(function.attrib.get('externalaction')), # XXX Optional
					bool(function.attrib.get('nullcall')), # XXX Optional
					lookup_access.get(function.attrib['access']),
					text(function.find('sql')),
					text(function.find('description')),
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
		lookup = {'in': 'I', 'out': 'O', 'inout': 'B', 'return': 'R'}
		for schema in self.doc.findall('schema'):
			for function in schema.findall('function'):
				for param in function.findall('parameter'):
					type = self.ids[param.attrib['datatype']]
					result.append((
						schema.attrib['name'],
						function.attrib['specificname'],
						param.attrib['name'],
						lookup[param.attrib['type']],
						self.parents[type].attrib['name'],
						type.attrib['name'],
						integer(param.attrib.get('size')),
						integer(param.attrib.get('scale')),
						param.attrib.get('codepage'),
						text(param.find('description')),
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
		lookup_access = {'none': 'N', 'contains': 'C', 'reads': 'R', 'modifies': 'M'}
		for schema in self.doc.findall('schema'):
			for procedure in schema.findall('procedure'):
				result.append((
					schema.attrib['name'],
					procedure.attrib['specificname'],
					procedure.attrib['name'],
					procedure.attrib.get('owner'),
					bool(procedure.attrib.get('system')),
					timestamp(procedure.attrib.get('created')),
					bool(procedure.attrib.get('deterministic')), # XXX Optional
					bool(procedure.attrib.get('externalaction')), # XXX Optional
					bool(procedure.attrib.get('nullcall')), # XXX Optional
					lookup_access.get(procedure.attrib['access']),
					text(procedure.find('sql')),
					text(procedure.find('description')),
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
		lookup = {'in': 'I', 'out': 'O', 'inout': 'B', 'return': 'R'}
		for schema in self.doc.findall('schema'):
			for procedure in schema.findall('procedure'):
				for param in procedure.findall('parameter'):
					type = self.ids[param.attrib['datatype']]
					result.append((
						schema.attrib['name'],
						procedure.attrib['specificname'],
						param.attrib['name'],
						lookup[param.attrib['type']],
						self.parents[type].attrib['name'],
						type.attrib['name'],
						integer(param.attrib.get('size')),
						integer(param.attrib.get('scale')),
						param.attrib.get('codepage'),
						text(param.find('description')),
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
		lookup_time = {'after': 'A', 'before': 'B', 'instead': 'I'}
		lookup_event = {'insert': 'I', 'update': 'U', 'delete': 'D'}
		lookup_granularity = {'row': 'R', 'statement': 'S'}
		for schema in self.doc.findall('schema'):
			for trigger in schema.findall('trigger'):
				relation = self.ids[trigger.attrib['relation']]
				result.append((
					schema.attrib['name'],
					trigger.attrib['name'],
					trigger.attrib.get('owner'),
					bool(trigger.attrib.get('system')),
					timestamp(trigger.attrib.get('created')),
					self.parents[relation].attrib['name'],
					relation.attrib['name'],
					lookup_time[trigger.attrib['time']],
					lookup_event[trigger.attrib['event']],
					lookup_granularity[trigger.attrib['granularity']],
					text(trigger.find('sql')),
					text(trigger.find('description')),
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
		for schema in self.doc.findall('schema'):
			for trigger in schema.findall('trigger'):
				for dep in trigger.findall('trigdep'):
					ref = self.ids[dep.attrib['ref']]
					result.append((
						schema.attrib['name'],
						trigger.attrib['name'],
						self.parents[ref].attrib['name'],
						ref.attrib['name'],
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
		for tbspace in self.doc.findall('tablespace'):
			result.append((
				tbspace.attrib['name'],
				tbspace.attrib.get('owner'),
				bool(tbspace.attrib.get('system')),
				timestamp(tbspace.attrib.get('created')),
				tbspace.attrib.get('type'),
				text(tbspace.find('description')),
			))
		return result

