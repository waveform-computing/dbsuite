# $Header$
# vim: set noet sw=4 ts=4:

# Standard modules
import logging
from string import Template

# Application-specific modules
from db.schemabase import Relation
from db.proxies import IndexesDict, IndexesList, RelationsDict, RelationsList, TriggersDict, TriggersList
from db.field import Field
from db.uniquekey import UniqueKey, PrimaryKey
from db.foreignkey import ForeignKey
from db.check import Check
from db.util import format_ident

class Table(Relation):
	"""Class representing a table in a DB2 database"""

	def __init__(self, schema, input, **row):
		"""Initializes an instance of the class from a input row"""
		super(Table, self).__init__(schema, row['name'])
		logging.debug("Building table %s" % (self.qualified_name))
		self.type_name = 'Table'
		self.description = row.get('description', None) or self.description
		self.definer = row.get('definer', None)
		self.check_pending = row.get('checkPending', None)
		self.created = row.get('created', None)
		self.stats_updated = row.get('statsUpdated', None)
		self.cardinality = row.get('cardinality', None)
		self.row_pages = row.get('rowPages', None)
		self.total_pages = row.get('totalPages', None)
		self.overflow = row.get('overflow', None)
		self.append = row.get('append', None)
		self.lock_size = row.get('lockSize', None)
		self.volatile = row.get('volatile', None)
		self.compression = row.get('compression', None)
		self.access_mode = row.get('accessMode', None)
		self.clustered = row.get('clustered', None)
		self.active_blocks = row.get('activeBlocks', None)
		self._fields = {}
		for field in [input.fields[(schema_name, table_name, field_name)]
			for (schema_name, table_name, field_name) in input.fields
			if schema_name == schema.name and table_name == self.name]:
			self._fields[field['name']] = Field(self, input, **field)
		self._field_list = sorted(self._fields.itervalues(), key=lambda field:field.position)
		self._dependents = RelationsDict(self.database, input.relation_dependents.get((schema.name, self.name)))
		self._dependent_list = RelationsList(self.database, input.relation_dependents.get((schema.name, self.name)))
		self.indexes = IndexesDict(self.database, input.table_indexes.get((schema.name, self.name)))
		self.index_list = IndexesList(self.database, input.table_indexes.get((schema.name, self.name)))
		self.triggers = TriggersDict(self.database, input.relation_triggers.get((schema.name, self.name)))
		self.trigger_list = TriggersList(self.database, input.relation_triggers.get((schema.name, self.name)))
		self.constraints = {}
		self.unique_keys = {}
		self.primary_key = None
		for key in [input.unique_keys[(schema_name, table_name, const_name)]
			for (schema_name, table_name, const_name) in input.unique_keys
			if schema_name == schema.name and table_name == self.name]:
			if key['type'] == 'P':
				constraint = PrimaryKey(self, input, **key)
				self.primary_key = constraint
			else:
				constraint = UniqueKey(self, input, **key)
			self.constraints[key['name']] = constraint
			self.unique_keys[key['name']] = constraint
		self.unique_key_list = sorted(self.unique_keys.itervalues(), key=lambda key:key.name)
		self.foreign_keys = {}
		for key in [input.foreign_keys[(schema_name, table_name, const_name)]
			for (schema_name, table_name, const_name) in input.foreign_keys
			if schema_name == schema.name and table_name == self.name]:
			constraint = ForeignKey(self, input, **key)
			self.constraints[key['name']] = constraint
			self.foreign_keys[key['name']] = constraint
		self.foreign_key_list = sorted(self.foreign_keys.itervalues(), key=lambda key:key.name)
		self.checks = {}
		for check in [input.checks[(schema_name, table_name, const_name)]
			for (schema_name, table_name, const_name) in input.checks
			if schema_name == schema.name and table_name == self.name]:
			constraint = Check(self, input, **check)
			self.constraints[check['name']] = constraint
			self.checks[check['name']] = constraint
		self.check_list = sorted(self.checks.itervalues(), key=lambda check:check.name)
		self.constraint_list = sorted(self.constraints.itervalues(), key=lambda constraint:constraint.name)
		self._data_tablespace = row['dataTbspace']
		self._index_tablespace = row.get('indexTbspace', None)
		self._long_tablespace = row.get('longTbspace', None)

	def _get_fields(self):
		return self._fields

	def _get_field_list(self):
		return self._field_list

	def _get_dependents(self):
		return self.__dependents

	def _get_dependent_list(self):
		return self.__dependent_list

	def _get_create_sql(self):
		sql = Template("""\
CREATE TABLE $schema.$table (
$elements
) $tbspaces;$indexes""")
		values = {
			'schema': format_ident(self.schema.name),
			'table': format_ident(self.name),	
			'elements': ',\n'.join(
				[field.prototype for field in self.field_list] + 
				[
					constraint.prototype
					for constraint in self.constraints.itervalues()
					if not isinstance(constraint, Check) or constraint.type != 'System Generated'
				]
			),
			'tbspaces': 'IN ' + format_ident(self.data_tablespace.name),
			'indexes': ''.join(['\n' + index.create_sql for index in self.index_list])
		}
		if self.index_tablespace != self.data_tablespace:
			values['tbspaces'] += ' INDEX IN ' + format_ident(self.index_tablespace.name)
		if self.long_tablespace != self.data_tablespace:
			values['tbspaces'] += ' LONG IN ' + format_ident(self.long_tablespace.name)
		return sql.substitute(values)
	
	def _get_drop_sql(self):
		sql = Template('DROP TABLE $schema.$table;')
		return sql.substitute({
			'schema': format_ident(self.schema.name),
			'table': format_ident(self.name)
		})
	
	def _get_data_tablespace(self):
		"""Returns the tablespace in which the table's data is stored"""
		return self.database.tablespaces[self._data_tablespace]

	def _get_index_tablespace(self):
		"""Returns the tablespace in which the table's indexes are stored"""
		if self._index_tablespace:
			return self.database.tablespaces[self._index_tablespace]
		else:
			return self.data_tablespace

	def _get_long_tablespace(self):
		"""Returns the tablespace in which the table's LOB values are stored"""
		if self._long_tablespace:
			return self.database.tablespaces[self._long_tablespace]
		else:
			return self.data_tablespace

	data_tablespace = property(_get_data_tablespace)
	index_tablespace = property(_get_index_tablespace)
	long_tablespace = property(_get_long_tablespace)
