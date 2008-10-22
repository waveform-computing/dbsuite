# vim: set noet sw=4 ts=4:

"""Input plugin for XML metadata storage."""

import logging
import re
import datetime
import db2makedoc.plugins
from itertools import chain
from db2makedoc.etree import parse, iselement
from db2makedoc.tuples import (
	Schema, Datatype, Table, View, Alias, RelationDep, Index, IndexCol,
	RelationCol, UniqueKey, UniqueKeyCol, ForeignKey, ForeignKeyCol, Check,
	CheckCol, Function, Procedure, RoutineParam, Trigger, TriggerDep,
	Tablespace
)


_timestamp_re = re.compile(r'^(\d{4})-(\d{2})-(\d{2})([T -](\d{2})[:.](\d{2})[:.](\d{2})(\.(\d+))?)?$')
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
		logging.info('Reading input from "%s"' % self.options['filename'])
		# Open and parse the document, and check its got the right root
		self.doc = parse(self.options['filename']).getroot()
		if self.doc.tag != 'database':
			raise db2makedoc.plugins.PluginError('Document root element must be "database"')
		self.name = self.doc.attrib['name']
		# Generate a parent map for the document (we'll need this later to
		# lookup the parents of nodes addressed by ID)
		logging.debug('Building parent map')
		self.parents = dict(
			(child, parent)
			for parent in self.doc.getiterator()
			for child in parent
		)
		# Generate an ID map (the structure uses a lot of IDREFS, so this
		# speeds things up considerably)
		logging.debug('Building IDREF map')
		self.ids = dict(
			(elem.attrib['id'], elem)
			for elem in self.doc.getiterator()
			if 'id' in elem.attrib
		)
	
	def close(self):
		"""Closes the source file and cleans up any resources."""
		super(InputPlugin, self).close()
		del self.ids
		del self.parents
		del self.doc
	
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
		for schema in self.doc.findall('schema'):
			yield Schema(
				schema.attrib['name'],
				schema.attrib.get('owner'),
				bool(schema.attrib.get('system')),
				timestamp(schema.attrib.get('created')),
				text(schema.find('description')),
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
		for schema in self.doc.findall('schema'):
			for datatype in schema.findall('datatype'):
				source = self.ids.get(datatype.attrib.get('source'))
				usertype = [None, True][iselement(source)]
				yield Datatype(
					schema.attrib['name'],
					datatype.attrib['name'],
					datatype.attrib.get('owner'),
					bool(datatype.attrib.get('system')),
					timestamp(datatype.attrib.get('created')),
					text(datatype.find('description')),
					datatype.attrib.get('variable') in ('size', 'scale'),
					datatype.attrib.get('variable') == 'scale',
					usertype and self.parents[source].attrib['name'],
					usertype and source.attrib['name'],
					usertype and datatype.attrib.get('size'),
					usertype and datatype.attrib.get('scale'),
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
		for schema in self.doc.findall('schema'):
			for table in schema.findall('table'):
				tbspace = self.ids[table.attrib['tablespace']]
				yield Table(
					schema.attrib['name'],
					table.attrib['name'],
					table.attrib.get('owner'),
					bool(table.attrib.get('system')),
					timestamp(table.attrib.get('created')),
					text(table.find('description')),
					tbspace.attrib['name'],
					timestamp(table.attrib.get('laststats')),
					integer(table.attrib.get('cardinality')),
					integer(table.attrib.get('size')),
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
		for schema in self.doc.findall('schema'):
			for view in schema.findall('view'):
				yield View(
					schema.attrib['name'],
					view.attrib['name'],
					view.attrib.get('owner'),
					bool(view.attrib.get('system')),
					timestamp(view.attrib.get('created')),
					text(view.find('description')),
					bool(view.attrib.get('readonly')),
					text(view.find('sql')),
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
		for schema in self.doc.findall('schema'):
			for alias in schema.findall('alias'):
				base = self.ids[alias.attrib['relation']]
				yield Alias(
					schema.attrib['name'],
					alias.attrib['name'],
					alias.attrib.get('owner'),
					bool(alias.attrib.get('system')),
					timestamp(alias.attrib.get('created')),
					text(alias.find('description')),
					self.parents[base].attrib['name'],
					base.attrib['name'],
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
		for schema in self.doc.findall('schema'):
			for view in schema.findall('view'):
				for dep in view.findall('viewdep'):
					ref = self.ids[dep.attrib['ref']]
					yield RelationDep(
						schema.attrib['name'],
						view.attrib['name'],
						self.parents[ref].attrib['name'],
						ref.attrib['name'],
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
		for schema in self.doc.findall('schema'):
			for index in schema.findall('index'):
				table = self.ids[index.attrib['table']]
				tbspace = self.ids[index.attrib['tablespace']]
				yield Index(
					schema.attrib['name'],
					index.attrib['name'],
					index.attrib.get('owner'),
					bool(index.attrib.get('system')),
					timestamp(index.attrib.get('created')),
					text(index.find('description')),
					self.parents[table].attrib['name'],
					table.attrib['name'],
					tbspace.attrib['name'],
					timestamp(index.attrib.get('laststats')),
					integer(index.attrib.get('cardinality')),
					integer(index.attrib.get('size')),
					bool(index.attrib.get('unique')),
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
		lookup = {'asc': 'A', 'desc': 'D', 'include': 'I'}
		for schema in self.doc.findall('schema'):
			for index in schema.findall('index'):
				for field in index.findall('indexfield'):
					ref = self.ids[field.attrib['ref']]
					yield IndexCol(
						schema.attrib['name'],
						index.attrib['name'],
						ref.attrib['name'],
						lookup[field.attrib['order']],
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
		lookup = {'always': 'A', 'default': 'D'}
		for schema in self.doc.findall('schema'):
			for relation in chain(schema.findall('table'), schema.findall('view'),schema.findall('alias')):
				for field in sorted(relation.findall('field'), key=lambda elem: int(elem.attrib['position'])):
					datatype = self.ids[field.attrib['datatype']]
					yield RelationCol(
						schema.attrib['name'],
						relation.attrib['name'],
						field.attrib['name'],
						self.parents[datatype].attrib['name'],
						datatype.attrib['name'],
						integer(field.attrib.get('size')),
						integer(field.attrib.get('scale')),
						field.attrib.get('codepage'),
						bool(field.attrib.get('identity')),
						bool(field.attrib.get('nullable')),
						integer(field.attrib.get('cardinality')),
						integer(field.attrib.get('null_cardinality')),
						lookup.get(field.attrib.get('generated'), 'N'),
						field.attrib.get('expression', field.attrib.get('default')),
						text(field.find('description')),
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
		for schema in self.doc.findall('schema'):
			for table in schema.findall('table'):
				for key in chain(table.findall('uniquekey'), table.findall('primarykey')):
					yield UniqueKey(
						schema.attrib['name'],
						table.attrib['name'],
						key.attrib['name'],
						key.attrib.get('owner'),
						bool(key.attrib.get('system')),
						timestamp(key.attrib.get('created')),
						text(key.find('description')),
						key.tag == 'primarykey',
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
		for schema in self.doc.findall('schema'):
			for table in schema.findall('table'):
				for key in chain(table.findall('uniquekey'), table.findall('primarykey')):
					for field in key.findall('keyfield'):
						ref = self.ids[field.attrib['ref']]
						yield UniqueKeyCol(
							schema.attrib['name'],
							table.attrib['name'],
							key.attrib['name'],
							ref.attrib['name'],
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
		lookup = {'noaction': 'A', 'cascade': 'C', 'setnull': 'N', 'restrict': 'R'}
		for schema in self.doc.findall('schema'):
			for table in schema.findall('table'):
				for key in table.findall('foreignkey'):
					ref = self.ids[key.attrib['references']]
					yield ForeignKey(
						schema.attrib['name'],
						table.attrib['name'],
						key.attrib['name'],
						key.attrib.get('owner'),
						bool(key.attrib.get('system')),
						timestamp(key.attrib.get('created')),
						text(key.find('description')),
						self.parents[self.parents[ref]].attrib['name'],
						self.parents[ref].attrib['name'],
						ref.attrib['name'],
						lookup[key.attrib['ondelete']],
						lookup[key.attrib['onupdate']],
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
		for schema in self.doc.findall('schema'):
			for table in schema.findall('table'):
				for key in table.findall('foreignkey'):
					for field in key.findall('fkeyfield'):
						sourceref = self.ids[field.attrib['sourceref']]
						targetref = self.ids[field.attrib['targetref']]
						yield ForeignKeyCol(
							schema.attrib['name'],
							table.attrib['name'],
							key.attrib['name'],
							sourceref.attrib['name'],
							targetref.attrib['name'],
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
		for schema in self.doc.findall('schema'):
			for table in schema.findall('table'):
				for check in table.findall('check'):
					yield Check(
						schema.attrib['name'],
						table.attrib['name'],
						check.attrib['name'],
						check.attrib.get('owner'),
						bool(check.attrib.get('system')),
						timestamp(check.attrib.get('created')),
						text(check.find('description')),
						text(check.find('expression')),
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
		for schema in self.doc.findall('schema'):
			for table in schema.findall('table'):
				for check in table.findall('check'):
					for field in check.findall('checkfield'):
						ref = self.ids[field.attrib['ref']]
						yield CheckCol(
							schema.attrib['name'],
							table.attrib['name'],
							check.attrib['name'],
							ref.attrib['name'],
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
		lookup_type = {'column': 'C', 'row': 'R', 'table': 'T', 'scalar': 'S'}
		lookup_access = {'none': 'N', 'contains': 'C', 'reads': 'R', 'modifies': 'M'}
		for schema in self.doc.findall('schema'):
			for function in schema.findall('function'):
				yield Function(
					schema.attrib['name'],
					function.attrib['specificname'],
					function.attrib['name'],
					function.attrib.get('owner'),
					bool(function.attrib.get('system')),
					timestamp(function.attrib.get('created')),
					text(function.find('description')),
					bool(function.attrib.get('deterministic')), # XXX Optional
					bool(function.attrib.get('externalaction')), # XXX Optional
					bool(function.attrib.get('nullcall')), # XXX Optional
					lookup_access.get(function.attrib['access']),
					text(function.find('sql')),
					lookup_type[function.attrib['type']],
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
		lookup_access = {'none': 'N', 'contains': 'C', 'reads': 'R', 'modifies': 'M'}
		for schema in self.doc.findall('schema'):
			for procedure in schema.findall('procedure'):
				yield Procedure(
					schema.attrib['name'],
					procedure.attrib['specificname'],
					procedure.attrib['name'],
					procedure.attrib.get('owner'),
					bool(procedure.attrib.get('system')),
					timestamp(procedure.attrib.get('created')),
					text(procedure.find('description')),
					bool(procedure.attrib.get('deterministic')), # XXX Optional
					bool(procedure.attrib.get('externalaction')), # XXX Optional
					bool(procedure.attrib.get('nullcall')), # XXX Optional
					lookup_access.get(procedure.attrib['access']),
					text(procedure.find('sql')),
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
		lookup = {'in': 'I', 'out': 'O', 'inout': 'B', 'return': 'R'}
		for schema in self.doc.findall('schema'):
			for routine in chain(schema.findall('function'), schema.findall('procedure')):
				for param in routine.findall('parameter'):
					type = self.ids[param.attrib['datatype']]
					yield RoutineParam(
						schema.attrib['name'],
						routine.attrib['specificname'],
						param.attrib['name'],
						self.parents[type].attrib['name'],
						type.attrib['name'],
						integer(param.attrib.get('size')),
						integer(param.attrib.get('scale')),
						param.attrib.get('codepage'),
						lookup[param.attrib['type']],
						text(param.find('description')),
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
		lookup_time = {'after': 'A', 'before': 'B', 'instead': 'I'}
		lookup_event = {'insert': 'I', 'update': 'U', 'delete': 'D'}
		lookup_granularity = {'row': 'R', 'statement': 'S'}
		for schema in self.doc.findall('schema'):
			for trigger in schema.findall('trigger'):
				relation = self.ids[trigger.attrib['relation']]
				yield Trigger(
					schema.attrib['name'],
					trigger.attrib['name'],
					trigger.attrib.get('owner'),
					bool(trigger.attrib.get('system')),
					timestamp(trigger.attrib.get('created')),
					text(trigger.find('description')),
					self.parents[relation].attrib['name'],
					relation.attrib['name'],
					lookup_time[trigger.attrib['time']],
					lookup_event[trigger.attrib['event']],
					lookup_granularity[trigger.attrib['granularity']],
					text(trigger.find('sql')),
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
		for schema in self.doc.findall('schema'):
			for trigger in schema.findall('trigger'):
				for dep in trigger.findall('trigdep'):
					ref = self.ids[dep.attrib['ref']]
					yield TriggerDep(
						schema.attrib['name'],
						trigger.attrib['name'],
						self.parents[ref].attrib['name'],
						ref.attrib['name'],
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
		for tbspace in self.doc.findall('tablespace'):
			yield Tablespace(
				tbspace.attrib['name'],
				tbspace.attrib.get('owner'),
				bool(tbspace.attrib.get('system')),
				timestamp(tbspace.attrib.get('created')),
				text(tbspace.find('description')),
				tbspace.attrib.get('type'),
			)

