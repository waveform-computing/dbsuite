# $Header$
# vim: set noet sw=4 ts=4:

import logging
from string import Template
from db2makedoc.db.relationbase import RelationObject
from db2makedoc.db.util import format_size, format_ident

class Field(RelationObject):
	"""Class representing a field in a relation in a DB2 database"""

	def __init__(self, relation, input, position, *row):
		"""Initializes an instance of the class from a input row"""
		super(Field, self).__init__(relation, row[0])
		logging.debug("Building field %s" % (self.qualified_name))
		(
			_,
			self._datatype_schema,
			self._datatype_name,
			self.identity,
			self._size,
			self._scale,
			self.codepage,
			self.nullable,
			self.cardinality,
			self.null_cardinality,
			self.generated,
			self.default,
			desc
		) = row
		self.type_name = 'Field'
		self.description = desc or self.description
		self.position = position

	def _get_identifier(self):
		return "field_%s_%s_%s" % (self.schema.name, self.relation.name, self.name)

	def _get_parent_list(self):
		return self.relation.field_list

	def _get_create_sql(self):
		from doctable import Table
		if isinstance(self.relation, Table):
			sql = Template('ALTER TABLE $schema.$table ADD COLUMN $fielddef;')
			return sql.substitute({
				'schema': format_ident(self.relation.schema.name),
				'table': format_ident(self.relation.name),
				'fielddef': self.prototype
			})
		else:
			return ''
	
	def _get_drop_sql(self):
		from doctable import Table
		if isinstance(self.relation, Table):
			sql = Template('ALTER TABLE $schema.$table DROP COLUMN $field;')
			return sql.substitute({
				'schema': format_ident(self.relation.schema.name),
				'table': format_ident(self.relation.name),
				'field': format_ident(self.name)
			})
		else:
			return ''
	
	def _get_prototype(self):
		"""Returns the SQL prototype of the field.

		This property returns the "prototype" of the field. That is, the chunk
		of SQL that would define this particular field in an ALTER TABLE ADD
		COLUMN or CREATE TABLE statement. This value is used by the create_sql
		property of the field and of its owning table.
		"""
		items = [format_ident(self.name), self.datatype_str]
		if not self.nullable:
			items.append('NOT NULL')
		if self.default:
			if self.generated == 'N':
				items.append('WITH DEFAULT %s' % (self.default))
			else:
				items.append('GENERATED %s AS (%s)' % (
					{'A': 'ALWAYS', 'D': 'BY DEFAULT'}[self.generated],
					self.default
				))
		return ' '.join(items)
		
	def _get_datatype(self):
		"""Returns the object representing the field's datatype"""
		return self.database.schemas[self._datatype_schema].datatypes[self._datatype_name]

	def _get_datatype_str(self):
		"""Returns a string representation of the datatype of the field.

		This is a convenience property which returns the datatype of the field
		with all necessary parameters in parentheses. It is used in
		constructing the prototype of the field.
		"""
		if self.datatype.system:
			result = format_ident(self.datatype.name)
		else:
			result = '%s.%s' % (
				format_ident(self.datatype.schema.name),
				format_ident(self.datatype.name)
			)
		if self.datatype.variable_size:
			result += '(%s' % (format_size(self._size))
			if self.datatype.variable_scale:
				result += ',%d' % (self._scale)
			result += ')'
		return result

	def _get_size(self):
		"""Returns the size of the field"""
		if self.datatype.variable_size:
			return self._size
		else:
			return None

	def _get_scale(self):
		"""Returns the scale of the field"""
		if self.datatype.variable_scale:
			return self._scale
		else:
			return None

	def _get_key_index(self):
		"""Returns the position of this field in the table's primary key"""
		if self.key:
			return self.key.fields.index(self)
		else:
			return None

	def _get_key(self):
		"""Returns the primary key that this field is a member of (if any)"""
		if self.relation.primary_key and (self in self.relation.primary_key.fields):
			return self.relation.primary_key
		else:
			return None

	datatype = property(_get_datatype)
	datatype_str = property(_get_datatype_str)
	size = property(_get_size)
	scale = property(_get_scale)
	key_index = property(_get_key_index)
	key = property(_get_key)
	prototype = property(_get_prototype)
