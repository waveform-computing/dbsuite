# $Header$
# vim: set noet sw=4 ts=4:

import logging
from string import Template
from db2makedoc.db.schemabase import SchemaObject
from db2makedoc.db.util import format_ident

class IndexFieldsDict(object):
	"""Presents a dictionary of (field, index_order) tuples keyed by field_name"""

	def __init__(self, database, schema_name, table_name, fields):
		"""Initializes the dict from a list of (field_name, index_order) tuples"""
		assert isinstance(fields, list)
		self._database = database
		self._schema_name = schema_name
		self._table_name = table_name
		self._keys = [field_name for (field_name, index_order) in fields]
		self._items = {}
		for (field_name, index_order) in fields:
			self._items[field_name] = index_order

	def keys(self):
		return self._keys

	def has_key(self, key):
		return key in self._keys

	def __len__(self):
		return len(self._keys)

	def __getItem__(self, key):
		return (self._database.schemas[self._schema_name].tables[self._table_name].fields[key], self._items[key])

	def __iter__(self):
		for k in self._keys:
			yield k

	def __contains__(self, key):
		return key in self._keys

class IndexFieldsList(object):
	"""Presents a list of (field, index_order) tuples"""

	def __init__(self, database, schema_name, table_name, fields):
		"""Initializes the list from a list of (field_name, index_order) tuples"""
		assert isinstance(fields, list)
		self._database = database
		self._schema_name = schema_name
		self._table_name = table_name
		self._items = fields

	def __len__(self):
		return len(self._items)

	def __getItem__(self, key):
		assert type(key) == int
		(field_name, index_order) = self._items[key]
		return (self._database.schemas[self._schema_name].tables[self._table_name].fields[field_name], index_order)

	def __iter__(self):
		for (field_name, index_order) in self._items:
			yield (self._database.schemas[self._schema_name].tables[self._table_name].fields[field_name], index_order)

	def __contains__(self, key):
		for i in self:
			if i == key:
				return True
		return False

class Index(SchemaObject):
	"""Class representing an index in a DB2 database"""

	def __init__(self, schema, input, **row):
		"""Initializes an instance of the class from a input row"""
		super(Index, self).__init__(schema, row['name'])
		logging.debug("Building index %s" % (self.qualified_name))
		self.type_name = 'Index'
		self.description = row.get('description', None) or self.description
		self.definer = row.get('definer', None)
		self.type = row.get('type', None)
		self.leaf_pages = row.get('leafPages', None)
		self.levels = row.get('levels', None)
		self.cluster_ratio = row.get('clusterRatio', None)
		self.cluster_factor = row.get('clusterFactor', None)
		self.sequential_pages = row.get('sequentialPages', None)
		self.density = row.get('density', None)
		self.user_defined = row.get('userDefined', None)
		self.required = row.get('required', None)
		self.created = row.get('created', None)
		self.stats_updated = row.get('statsUpdated', None)
		self.reverse_scans = row.get('reverseScans', None)
		self.unique = row['unique']
		self._table_schema = row['tableSchema']
		self._table_name = row['tableName']
		self._tablespace_name = row['tablespaceName']
		self.fields = IndexFieldsDict(self.database, self._table_schema, self._table_name, input.index_fields[(schema.name, self.name)])
		self.field_list = IndexFieldsList(self.database, self._table_schema, self._table_name, input.index_fields[(schema.name, self.name)])
		self.cardinality = (
			row.get('cardinality', None),
			[
				row.get('cardinality1', None),
				row.get('cardinality2', None),
				row.get('cardinality3', None),
				row.get('cardinality4', None),
			][:len(self.field_list)]
		)

	def _get_identifier(self):
		return "index_%s_%s" % (self.schema.name, self.name)

	def _get_parent_list(self):
		return self.schema.index_list

	def _get_create_sql(self):
		sql = """CREATE $type $schema.$index
ON $tbschema.$tbname ($fields)"""
		values = {
			'type': {False: 'INDEX', True: 'UNIQUE INDEX'}[self.unique],
			'schema': format_ident(self.schema.name),
			'index': format_ident(self.name),
			'tbschema': format_ident(self.table.schema.name),
			'tbname': format_ident(self.table.name),
			'fields': ', '.join(['%s%s' % (field.name, {
				'ASCENDING': '',
				'DESCENDING': ' DESC'
			}[order]) for (field, order) in self.field_list if order != 'INCLUDE'])
		}
		if self.unique:
			incfields = [field for (field, order) in self.field_list if order == 'INCLUDE']
			if len(incfields) > 0:
				sql += '\nINCLUDE ($incfields)'
				values['incfields'] = ', '.join([field.name for field in incfields])
		if self.reverse_scans:
			sql += '\nALLOW REVERSE SCANS'
		sql += ';'
		return Template(sql).substitute(values)

	def _get_drop_sql(self):
		sql = Template('DROP INDEX $schema.$index;')
		return sql.substitute({
			'schema': format_ident(self.schema.name),
			'index': format_ident(self.name)
		})

	def _get_table(self):
		"""Returns the table that index is defined against"""
		return self.database.schemas[self._table_schema].tables[self._table_name]

	def _get_tablespace(self):
		"""Returns the tablespace that contains the index's data"""
		return self.database.tablespaces[self._tablespace_name]

	table = property(_get_table)
	tablespace = property(_get_tablespace)
