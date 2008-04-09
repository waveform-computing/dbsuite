# vim: set noet sw=4 ts=4:

"""Defines all classes that represent the hierarchy of objects in a database.

This module defines all the classes that are used by the application to
represent a database. Instances of the classes are built from the information
returned by an input plugin. The top of the hierarchy is an instance of the
Database class. From this object, all other objects in the hierarchy can be
reached.

The top-level object (the instance of the Database class) is passed to output
plugins (along with the configuration information for the plugin).
"""

import re
import logging
from string import (Template,)
from UserDict import (DictMixin,)
from db2makedoc.sql.formatter import (format_size, format_ident)


__all__ = [
	'Alias',
	'Check',
	'Constraint',
	'Database',
	'DatabaseObject',
	'Datatype',
	'Field',
	'ForeignKey',
	'Function',
	'Index',
	'Param',
	'PrimaryKey',
	'Procedure',
	'Relation',
	'RelationObject',
	'Routine',
	'Schema',
	'SchemaObject',
	'Table',
	'Tablespace',
	'Trigger',
	'UniqueKey',
	'View',
]


# PRIVATE PROXY CLASSES #######################################################


class RelationsDict(object, DictMixin):
	"""Presents a dictionary of relations"""
	
	def __init__(self, database, relations):
		"""Initializes the dict from a list of (schema_name, relation_name) tuples"""
		assert isinstance(database, Database)
		assert isinstance(relations, list)
		self._database = database
		self._keys = relations
		
	def keys(self):
		return self._keys
	
	def has_key(self, key):
		return key in self._keys
	
	def __len__(self):
		return len(self._keys)
	
	def __getitem__(self, key):
		assert isinstance(key, tuple)
		(schema_name, relation_name) = key
		return self._database.schemas[schema_name].relations[relation_name]
	
	def __iter__(self):
		for k in self._keys:
			yield k
			
	def __contains__(self, key):
		return key in self._keys


class RelationsList(object):
	"""Presents a list of relations"""
	
	def __init__(self, database, relations):
		"""Initializes the list from a list of (schema_name, relation_name) tuples"""
		assert isinstance(database, Database)
		assert isinstance(relations, list)
		self._database = database
		self._items = relations
		
	def __len__(self):
		return len(self._items)
	
	def __getitem__(self, key):
		assert isinstance(key, int)
		(schema_name, relation_name) = self._items[key]
		return self._database.schemas[schema_name].relations[relation_name]
	
	def __iter__(self):
		for (schema_name, relation_name) in self._items:
			yield self._database.schemas[schema_name].relations[relation_name]

	def __contains__(self, key):
		for i in self:
			if i == key:
				return True
		return False


class IndexesDict(object, DictMixin):
	"""Presents a dictionary of indexes"""
	
	def __init__(self, database, indexes):
		"""Initializes the dict from a list of (schema_name, index_name) tuples"""
		assert isinstance(database, Database)
		assert isinstance(indexes, list)
		self._database = database
		self._keys = indexes

	def keys(self):
		return self._keys
	
	def has_key(self, key):
		return key in self._keys
	
	def __len__(self):
		return len(self._keys)
	
	def __getitem__(self, key):
		assert isinstance(key, tuple)
		(schema_name, index_name) = key
		return self._database.schemas[schema_name].indexes[index_name]
	
	def __iter__(self):
		for k in self._keys:
			yield k
			
	def __contains__(self, key):
		return key in self._keys


class IndexesList(object):
	"""Presents a list of indexes"""
	
	def __init__(self, database, indexes):
		"""Initializes the list from a list of (schema_name, index_name) tuples"""
		assert isinstance(database, Database)
		assert isinstance(indexes, list)
		self._database = database
		self._items = indexes
	
	def __len__(self):
		return len(self._items)
	
	def __getitem__(self, key):
		assert isinstance(key, int)
		(schema_name, index_name) = self._items[key]
		return self._database.schemas[schema_name].indexes[index_name]
	
	def __iter__(self):
		for (schema_name, index_name) in self._items:
			yield self._database.schemas[schema_name].indexes[index_name]
			
	def __contains__(self, key):
		for i in self:
			if i == key:
				return True
		return False


class ConstraintsDict(object, DictMixin):
	"""Presents a dictionary of constraints"""
	
	def __init__(self, database, constraints):
		"""Initializes the dict from a list of (schema_name, table_name, constraint_name) tuples"""
		assert isinstance(database, Database)
		assert isinstance(constraints, list)
		self._database = database
		self._keys = constraints
		
	def keys(self):
		return self._keys
	
	def has_key(self, key):
		return key in self._keys
	
	def __len__(self):
		return len(self._keys)
	
	def __getitem__(self, key):
		assert isinstance(key, tuple)
		(schema_name, table_name, constraint_name) = key
		return self._database.schemas[schema_name].tables[table_name].constraints[constraint_name]
	
	def __iter__(self):
		for k in self._keys:
			yield k
			
	def __contains__(self, key):
		return key in self._keys


class ConstraintsList(object):
	"""Presents a list of constraints"""
	
	def __init__(self, database, constraints):
		"""Initializes the list from a list of (schema_name, table_name, constraint_name) tuples"""
		assert isinstance(database, Database)
		assert isinstance(constraints, list)
		self._database = database
		self._items = constraints
		
	def __len__(self):
		return len(self._items)
	
	def __getitem__(self, key):
		assert isinstance(key, int)
		(schema_name, table_name, constraint_name) = self._items[key]
		return self._database.schemas[schema_name].tables[table_name].constraints[constraint_name]
	
	def __iter__(self):
		for (schema_name, table_name, constraint_name) in self._items:
			yield self._database.schemas[schema_name].tables[table_name].constraints[constraint_name]

	def __contains__(self, key):
		for i in self:
			if i == key:
				return True
		return False


class TriggersDict(object, DictMixin):
	"""Presents a dictionary of triggers"""
	
	def __init__(self, database, triggers):
		"""Initializes the dict from a list of (schema_name, trigger_name) tuples"""
		assert isinstance(database, Database)
		assert isinstance(triggers, list)
		self._database = database
		self._keys = triggers

	def keys(self):
		return self._keys
	
	def has_key(self, key):
		return key in self._keys
	
	def __len__(self):
		return len(self._keys)
	
	def __getitem__(self, key):
		assert isinstance(key, tuple)
		(schema_name, trigger_name) = key
		return self._database.schemas[schema_name].triggers[trigger_name]
	
	def __iter__(self):
		for k in self._keys:
			yield k
			
	def __contains__(self, key):
		return key in self._keys


class TriggersList(object):
	"""Presents a list of triggers"""
	
	def __init__(self, database, triggers):
		"""Initializes the list from a list of (schema_name, trigger_name) tuples"""
		assert isinstance(database, Database)
		assert isinstance(triggers, list)
		self._database = database
		self._items = triggers
	
	def __len__(self):
		return len(self._items)
	
	def __getitem__(self, key):
		assert isinstance(key, int)
		(schema_name, trigger_name) = self._items[key]
		return self._database.schemas[schema_name].triggers[trigger_name]
	
	def __iter__(self):
		for (schema_name, trigger_name) in self._items:
			yield self._database.schemas[schema_name].triggers[trigger_name]
			
	def __contains__(self, key):
		for i in self:
			if i == key:
				return True
		return False


class IndexFieldsDict(object):
	"""Presents a dictionary of (field, index_order) tuples keyed by field_name"""

	def __init__(self, database, schema_name, table_name, fields):
		"""Initializes the dict from a list of (field_name, index_order) tuples"""
		assert isinstance(database, Database)
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

	def __getitem__(self, key):
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
		assert isinstance(database, Database)
		assert isinstance(fields, list)
		self._database = database
		self._schema_name = schema_name
		self._table_name = table_name
		self._items = fields

	def __len__(self):
		return len(self._items)

	def __getitem__(self, key):
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


class ConstraintFieldsList(object):
	"""Presents a list of fields referenced by a constraint"""

	def __init__(self, table, fields):
		"""Initializes the list from a list of field names"""
		assert isinstance(table, Table)
		assert isinstance(fields, list)
		self._table = table
		self._items = fields

	def __len__(self):
		return len(self._items)

	def __getitem__(self, key):
		assert type(key) == int
		return self._table.fields[self._items[key]]

	def __iter__(self):
		for i in self._items:
			yield self._table.fields[i]

	def __contains__(self, key):
		for i in self:
			if i is key:
				return True
		return False

	def index(self, x, i=0, j=None):
		result = i
		for k in self._items[i:j]:
			if self._table.fields[k] is x:
				return result
			result += 1
		raise ValueError("%s not found in list" % repr(x))


class ForeignKeyFieldsList(object):
	"""Presents a list of (field, parent_field) tuples in a foreign key"""

	def __init__(self, table, ref_schema_name, ref_table_name, fields):
		"""Initializes the list from a list of (field, parent_field) name tuples"""
		assert isinstance(table, Table)
		assert isinstance(fields, list)
		self._table = table
		self._database = table.database
		self._ref_schema_name = ref_schema_name
		self._ref_table_name = ref_table_name
		self._items = fields

	def __len__(self):
		return len(self._items)

	def __getitem__(self, key):
		assert type(key) == int
		(field_name, parent_name) = self._items[key]
		parent_table = self._database.schemas[self._ref_schema_name].tables[self._ref_table_name]
		return (self._table.fields[field_name], parent_table.fields[parent_name])

	def __iter__(self):
		parent_table = self._database.schemas[self._ref_schema_name].tables[self._ref_table_name]
		for (field_name, parent_name) in self._items:
			yield (self._table.fields[field_name], parent_table.fields[parent_name])

	def __contains__(self, key):
		for i in self:
			if i == key:
				return True
		return False


# ABSTRACT BASE CLASSES #######################################################

class DatabaseObject(object):
	"""Base class for all documented database objects"""

	type_name = 'Object'

	def __init__(self, parent, name, system=False, description=None):
		"""Initializes an instance of the class.
		
		The parent parameter specifies the parent object that "owns" this
		object. For example, in the case of a table this would be the table's
		schema. The name parameter specifies the local (unqualified) name of
		the object, for example "MYTABLE". The system parameter specifies
		whether or not the object is system-maintained. Examples of
		system-maintained database objects are the system catalog tables
		created with the database or check constraints added to a table
		automatically to support a generated column.

		Finally, the description parameter provides the human readable
		descriptive text associated with the object (which should be output
		into the documentation).
		"""
		super(DatabaseObject, self).__init__()
		assert not parent or isinstance(parent, DatabaseObject)
		self.parent = parent
		self.name = name
		if description:
			self.description = description
		else:
			self.description = 'No description in the system catalog'
		self._system = system
		logging.debug("Building %s %s" % (self.type_name, self.qualified_name))

	def _get_database(self):
		"""Returns the database which owns the object.

		The database property returns the database at the top of the object
		hierarchy which owns this object. Descendents must override this method
		(the default implemented raises an exception).
		"""
		raise NotImplementedError
	
	def _get_parent_list(self):
		"""Returns the list to which this object belongs in its parent.

		If this object belongs in a list within its parent object (e.g. a field
		object belongs in the fields_list property of its parent Table object),
		this property will return that list. Otherwise, it returns None.
		"""
		return None

	def _get_parent_index(self):
		"""Returns the index of this object within the parent_list.

		If this object belongs in a list within its parent object (e.g. a field
		object belongs in the fields_list property of its parent Table object),
		this property will return the position of this object in that list.
		Typically this is analogous to the position property of the object. If
		this object does not have a parent_list, querying this property raises
		an exception.
		"""
		if self.parent_list is None:
			raise NotImplementedError
		else:
			return self.parent_list.index(self)
	
	def _get_identifier(self):
		"""Returns a unique identifier for the object.

		The default implementation relies on the built-in id() function.
		Descendents should override this to provide a more descriptive /
		meaningful (but still unique) value. This is used by certain output
		plugins to determine output filename.
		"""
		return id(self)

	def _get_qualified_name(self):
		"""Returns the fully qualified name of the object.

		This property recurses up the hierarchy to construct the fully
		qualified name of the object (the result should be valid as an SQL
		name).
		"""
		result = self.name
		if self.parent:
			result = self.parent.qualified_name + '.' + result
		return result

	def _get_system(self):
		"""Returns a bool indicating whether the object is system-defined.

		This property indicates whether an object is system-defined (true) or
		user defined (false). Any object which is directly or indirectly owned
		by a system-defined object is considered system-defined itself.
		"""
		if self.parent:
			return self._system or self.parent.system
		else:
			return self._system

	def _get_next(self):
		"""Returns the next sibling of this object.

		If this object is a member of a list in its parent (e.g. a field in a
		Table object), this property returns its next sibling. If it is the
		last object in the list, or if it is not a member of a list, the result
		is None.
		"""
		if self.parent_list is None:
			return None
		try:
			return self.parent_list[self.parent_index + 1]
		except IndexError:
			return None

	def _get_prior(self):
		"""Returns the prior sibling of this object.

		If this object is a member of a list in its parent (e.g. a field in a
		Table object), this property returns its prior sibling. If it is the
		first object in the list, or if it is not a member of a list, the
		result is None.
		"""
		if self.parent_list is None:
			return None
		try:
			if self.parent_index > 0:
				return self.parent_list[self.parent_index - 1]
			else:
				return None
		except IndexError:
			return None

	def _get_first(self):
		"""Returns the first sibling of this object.

		If this object is a member of a list in its parent (e.g. a field in a
		Table object), this property returns its first sibling (the first
		object in the parent_list). If it is not a member of a list, the result
		is None.
		"""
		if self.parent_list is None:
			return None
		return self.parent_list[0]
	
	def _get_last(self):
		"""Returns the last sibling of this object.

		If this object is a member of a list in its parent (e.g. a field in a
		Table object), this property returns its last sibling (the last object
		in the parent_list). If it is not a member of a list, the result is
		None.
		"""
		if self.parent_list is None:
			return None
		return self.parent_list[-1]

	def _get_create_sql(self):
		"""Returns the SQL required to create the object.

		This property returns the SQL required to create the object. It need
		not be the exact statement that created the object, or even valid for a
		specific platform. It is simply intended to provide a useful complement
		to the documentation for those well-versed enough in SQL that they
		prefer reading raw SQL to a bunch of text.
		"""
		raise NotImplementedError

	def _get_drop_sql(self):
		"""Returns the SQL required to drop the object.

		This property returns the SQL required to drop the object. Like the
		create_sql property, it need not be valid SQL for a specific platform,
		simply a useful complement to the documentation.
		"""
		raise NotImplementedError

	def __str__(self):
		"""Return a string representation of the object"""
		return self.qualified_name
	
	database = property(lambda self: self._get_database(), doc=_get_database.__doc__)
	parent_list = property(lambda self: self._get_parent_list(), doc=_get_parent_list.__doc__)
	parent_index = property(lambda self: self._get_parent_index(), doc=_get_parent_index.__doc__)
	identifier = property(lambda self: self._get_identifier(), doc=_get_identifier.__doc__)
	qualified_name = property(lambda self: self._get_qualified_name(), doc=_get_qualified_name.__doc__)
	system = property(lambda self: self._get_system(), doc=_get_system.__doc__)
	next = property(lambda self: self._get_next(), doc=_get_next.__doc__)
	prior = property(lambda self: self._get_prior(), doc=_get_prior.__doc__)
	first = property(lambda self: self._get_first(), doc=_get_first.__doc__)
	last = property(lambda self: self._get_last(), doc=_get_last.__doc__)
	create_sql = property(lambda self: self._get_create_sql(), doc=_get_create_sql.__doc__)
	drop_sql = property(lambda self: self._get_drop_sql(), doc=_get_drop_sql.__doc__)


class SchemaObject(DatabaseObject):
	"""Base class for database objects that belong directly to a schema"""

	def __init__(self, parent, name, system=False, description=None):
		"""Initializes an instance of the class"""
		assert isinstance(parent, Schema)
		super(SchemaObject, self).__init__(parent, name, system, description)
		self.schema = parent
	
	def _get_database(self):
		return self.parent.parent


class RelationObject(DatabaseObject):
	"""Base class for database objects that belong directly to a relation"""

	def __init__(self, parent, name, system=False, description=None):
		"""Initializes an instance of the class"""
		assert isinstance(parent, Relation)
		super(RelationObject, self).__init__(parent, name, system, description)
		self.relation = self.parent
		self.schema = self.parent.parent
	
	def _get_database(self):
		return self.parent.parent.parent


class RoutineObject(DatabaseObject):
	"""Base class for database objects that belong directly to a routine"""

	def __init__(self, parent, name, system=False, description=None):
		"""Initializes an instance of the class"""
		assert isinstance(parent, Routine)
		super(RoutineObject, self).__init__(parent, name, system, description)
		self.routine = self.parent
		self.schema = self.parent.parent
	
	def _get_database(self):
		return self.parent.parent.parent


class Relation(SchemaObject):
	"""Base class for relations that belong in a schema (e.g. tables, views, etc.)"""

	type_name = 'Relation'

	def _get_identifier(self):
		return "relation_%s_%s" % (self.schema.name, self.name)

	def _get_dependents(self):
		"""Returns a dictionary of the dependent relations.

		This property provides a dictionary (keyed on a 2-tuple of (schema,
		name)) of the relations which depend on this relation in some manner
		(e.g. a table which is depended on by a view).
		"""
		raise NotImplementedError

	def _get_dependent_list(self):
		"""Returns a list of the dependent relations.

		This property provides a list of the relations which depend on this
		relation in some manner (e.g. a table which is depended on by a view).
		"""
		raise NotImplementedError

	def _get_fields(self):
		"""Returns a dictionary of fields.

		This property provides a dictionary (keyed by name) of the fields
		contained by this relation.
		"""
		raise NotImplementedError

	def _get_field_list(self):
		"""Returns an ordered list of fields.

		This property provides an ordered list of the fields contained by this
		relation (the contents are ordered by their position in the relation).
		"""
		raise NotImplementedError

	def _get_parent_list(self):
		return self.schema.relation_list

	dependents = property(lambda self: self._get_dependents(), doc=_get_dependents.__doc__)
	dependent_list = property(lambda self: self._get_dependent_list(), doc=_get_dependent_list.__doc__)
	fields = property(lambda self: self._get_fields(), doc=_get_fields.__doc__)
	field_list = property(lambda self: self._get_field_list(), doc=_get_field_list.__doc__)


class Routine(SchemaObject):
	"""Base class for routines that belong in a schema (functions, procedures, etc.)"""

	type_name = 'Routine'

	def __init__(self, parent, name, specific_name, system=False, description=None):
		"""Initializes an instance of the class.
		
		The extra specific_name parameter in this constructor refers to the
		unique name that identifies the routine. In this context, multiple
		overloaded routines may have the same name, but each must have a unique
		specific_name by which a routine can be identified without specifying
		its prototype (parameter list).
		"""
		super(Routine, self).__init__(parent, name, system, description)
		self.specific_name = specific_name
		
	def _get_identifier(self):
		return "routine_%s_%s" % (self.schema.name, self.specific_name)

	def _get_params(self):
		"""Returns a dictionary of parameters.

		This property provides a dictionary (keyed by name) of the parameters
		that must be provided to this routine.
		"""
		raise NotImplementedError

	def _get_param_list(self):
		"""Returns an ordered list of parameters.

		This property provides an ordered list of the parameters that must be
		provided to this routine (the contents are ordered by their position in
		the routine prototype).
		"""
		raise NotImplementedError

	def _get_returns(self):
		"""Returns a dictionary of return fields.

		This property provides a dictionary (keyed by name) of the fields
		returned by the routine (assuming it is a row or table function).  If
		the routine is a scalar function this will contain a single object. If
		the routine is a procedure, this will be empty.
		"""
		raise NotImplementedError

	def _get_return_list(self):
		"""Returns an ordered list of return fields.

		This property provides an ordered list of the fields returned by the
		routine (assuming it is a row or table function).  If the routine is a
		scalar function this will contain a single object. If the routine is a
		procedure, this will be empty.
		"""
		raise NotImplementedError

	def _get_prototype(self):
		"""Returns the SQL prototype of the function.

		This property returns the SQL prototype of the routine. This isn't
		intended to be valid SQL, rather a representation of the routine as
		might appear in a manual, e.g. FUNC(PARAM1 TYPE, PARAM2 TYPE, ...)
		"""
		raise NotImplementedError
	
	params = property(lambda self: self._get_params(), doc=_get_params.__doc__)
	param_list = property(lambda self: self._get_param_list(), doc=_get_param_list.__doc__)
	returns = property(lambda self: self._get_returns(), doc=_get_returns.__doc__)
	return_list = property(lambda self: self._get_return_list(), doc=_get_return_list.__doc__)
	prototype = property(lambda self: self._get_prototype(), doc=_get_prototype.__doc__)


class Constraint(RelationObject):
	"""Base class for constraints that belong in a relation (e.g. primary keys, checks, etc.)"""

	type_name = 'Constraint'

	def __init__(self, parent, name, system=False, description=None):
		"""Initializes an instance of the class"""
		super(Constraint, self).__init__(parent, name, system, description)
		self.table = self.parent
	
	def _get_identifier(self):
		return "constraint_%s_%s_%s" % (self.schema.name, self.relation.name, self.name)

	def _get_fields(self):
		"""Returns a list of the fields constrained by this constraint"""
		raise NotImplementedError
	
	def _get_prototype(self):
		"""Returns the prototype SQL of the constraint.
		
		Returns the attributes of the constraint formatted for use in an ALTER
		TABLE or CREATE TABLE statement.
		"""
		raise NotImplementedError
	
	def _get_create_sql(self):
		sql = Template('ALTER TABLE $schema.$table ADD $constdef;')
		return sql.substitute({
			'schema': format_ident(self.table.schema.name),
			'table': format_ident(self.table.name),
			'constdef': self.prototype
		})
	
	def _get_drop_sql(self):
		sql = Template('ALTER TABLE $schema.$table DROP CONSTRAINT $const;')
		return sql.substitute({
			'schema': format_ident(self.table.schema.name),
			'table': format_ident(self.table.name),
			'const': format_ident(self.name)
		})
	
	def _get_parent_list(self):
		return self.table.constraint_list

	fields = property(lambda self: self._get_fields(), doc=_get_fields.__doc__)
	prototype = property(lambda self: self._get_prototype(), doc=_get_prototype.__doc__)


# CONCRETE CLASSES ############################################################


class Database(DatabaseObject):
	"""Class representing a DB2 database"""

	type_name = 'Database'
	
	def __init__(self, input):
		"""Initializes an instance of the class"""
		super(Database, self).__init__(None, input.name)
		self.tablespace_list = sorted([
			Tablespace(self, input, *item)
			for item in input.tablespaces
		], key=lambda item:item.name)
		self.tablespaces = dict([
			(tbspace.name, tbspace)
			for tbspace in self.tablespace_list
		])
		self.schema_list = sorted([
			Schema(self, input, *item)
			for item in input.schemas
		], key=lambda item:item.name)
		# Prune completely empty schemas
		self.schema_list = [
			schema for schema in self.schema_list
			if sum([
				len(schema.relation_list),
				len(schema.routine_list),
				len(schema.trigger_list),
				len(schema.index_list),
				len(schema.datatype_list)
			]) > 0
		]
		self.schemas = dict([
			(schema.name, schema)
			for schema in self.schema_list
		])

	def find(self, qualified_name):
		"""Find an object in the hierarchy by its qualified name.
		
		Because there are several namespaces in DB2, the results of such a
		search can only be unambiguous if an order of precedence for object
		types is established. The order of precedence used by this method is
		as follows:
		
		Schemas
		Tablespaces
			Tables,Views (one namespace)
				Fields
				Constraints
			Indexes
			Functions,Methods,Procedures (one namespace)
		
		Hence, if a schema shares a name with a tablespace, the schema will
		be returned in preference to the tablespace. Likewise, if an index
		shares a name with a table, the table will be returned in preference
		to the index.
		"""
		parts = qualified_name.split(".")
		if len(parts) == 1:
			return self.schemas.get(parts[0],
				self.tablespaces.get(parts[0],
				None))
		elif len(parts) == 2:
			schema = self.schemas[parts[0]]
			return schema.relations.get(parts[1],
				schema.indexes.get(parts[1],
				schema.routines.get(parts[1],
				None)))
		elif len(parts) == 3:
			relation = self.schemas[parts[0]].relations[parts[1]]
			return relation.fields.get(parts[2],
				relation.constraints.get(parts[2],
				None))
		else:
			return None
	
	def touch(self, method, *args, **kwargs):
		"""Calls the specified method for each object within the database.

		The touch() method can be used to perform an operation on all objects
		or a sub-set of all objects in the database. It iterates over all
		objects of the database, recursing into schemas, tables, etc. The
		specified method is called for each object with a single parameter
		(namely, the object).

		Additional parameters can be passed which will be captured by args and
		kwargs and passed verbatim to method on each invocation.

		The return value of the method is ignored.
		"""
		method(self, *args, **kwargs)
		for schema in self.schemas.itervalues():
			method(schema, *args, **kwargs)
			for table in schema.tables.itervalues():
				method(table, *args, **kwargs)
				for ukey in table.unique_keys.itervalues():
					method(ukey, *args, **kwargs)
				for fkey in table.foreign_keys.itervalues():
					method(fkey, *args, **kwargs)
				for check in table.checks.itervalues():
					method(check, *args, **kwargs)
				for field in table.fields.itervalues():
					method(field, *args, **kwargs)
			for view in schema.views.itervalues():
				method(view, *args, **kwargs)
				for field in view.fields.itervalues():
					method(field, *args, **kwargs)
			for alias in schema.aliases.itervalues():
				method(alias, *args, **kwargs)
				for field in alias.fields.itervalues():
					method(field, *args, **kwargs)
			for index in schema.indexes.itervalues():
				method(index, *args, **kwargs)
			for function in schema.specific_functions.itervalues():
				method(function, *args, **kwargs)
			for procedure in schema.specific_procedures.itervalues():
				method(procedure, *args, **kwargs)
			for trigger in schema.triggers.itervalues():
				method(trigger, *args, **kwargs)
		for tbspace in self.tablespaces.itervalues():
			method(tbspace, *args, **kwargs)

	def _get_identifier(self):
		return "db"
	
	def _get_database(self):
		return self


class Tablespace(DatabaseObject):
	"""Class representing a tablespace"""

	type_name = 'Tablespace'

	def __init__(self, database, input, *row):
		"""Initializes an instance of the class from a input row"""
		(
			name,
			self.owner,
			system,
			self.created,
			self.type,
			desc
		) = row
		super(Tablespace, self).__init__(database, name, system, desc)
		self.table_list = RelationsList(
			self.database,
			sorted(input.tablespace_tables[self.name])
		)
		self.tables = RelationsDict(
			self.database,
			input.tablespace_tables[self.name]
		)
		self.index_list = IndexesList(
			self.database,
			sorted(input.tablespace_indexes[self.name])
		)
		self.indexes = IndexesDict(
			self.database,
			input.tablespace_indexes[self.name]
		)

	def _get_identifier(self):
		return "tbspace_%s" % (self.name)

	def _get_qualified_name(self):
		return self.name

	def _get_database(self):
		return self.parent

	def _get_parent_list(self):
		return self.database.tablespace_list


class Schema(DatabaseObject):
	"""Class representing a schema"""

	type_name = 'Schema'

	def __init__(self, database, input, *row):
		"""Initializes an instance of the class from a input row"""
		assert isinstance(database, Database)
		(
			name,
			self.owner,
			system,
			self.created,
			desc
		) = row
		super(Schema, self).__init__(database, name, system, desc)
		self.datatype_list = sorted([
			Datatype(self, input, *item)
			for item in input.datatypes
			if item[0] == self.name
		], key=lambda item:item.name)
		self.datatypes = dict([
			(datatype.name, datatype)
			for datatype in self.datatype_list
		])
		self.table_list = sorted([
			Table(self, input, *item)
			for item in input.tables
			if item[0] == self.name
		], key=lambda item:item.name)
		self.tables = dict([
			(table.name, table)
			for table in self.table_list
		])
		self.view_list = sorted([
			View(self, input, *item)
			for item in input.views
			if item[0] == self.name
		], key=lambda item:item.name)
		self.views = dict([
			(view.name, view)
			for view in self.view_list
		])
		self.alias_list = sorted([
			Alias(self, input, *item)
			for item in input.aliases
			if item[0] == self.name
		], key=lambda item:item.name)
		self.aliases = dict([
			(alias.name, alias)
			for alias in self.alias_list
		])
		self.relation_list = sorted(
			self.table_list + self.view_list + self.alias_list,
			key=lambda item:item.name
		)
		self.relations = dict([
			(relation.name, relation)
			for relation in self.relation_list
		])
		self.index_list = sorted([
			Index(self, input, *item)
			for item in input.indexes
			if item[0] == self.name
		])
		self.indexes = dict([
			(index.name, index)
			for index in self.index_list
		])
		self.function_list = sorted([
			Function(self, input, *item)
			for item in input.functions
			if item[0] == self.name
		], key=lambda item:item.name)
		self.functions = {}
		for function in self.function_list:
			if function.name in self.functions:
				self.functions[function.name].append(function)
			else:
				self.functions[function.name] = [function]
		self.specific_functions = dict([
			(function.specific_name, function)
			for function in self.function_list
		])
		self.procedure_list = sorted([
			Procedure(self, input, *item)
			for item in input.procedures
			if item[0] == self.name
		], key=lambda item:item.name)
		self.procedures = {}
		for procedure in self.procedure_list:
			if procedure.name in self.procedures:
				self.procedures[procedure.name].append(procedure)
			else:
				self.procedures[procedure.name] = [procedure]
		self.specific_procedures = dict([
			(procedure.specific_name, procedure)
			for procedure in self.procedure_list
		])
		self.routine_list = sorted(
			self.function_list + self.procedure_list,
			key=lambda item:item.name
		)
		self.routines = dict([
			(routine.name, routine)
			for routine in self.routine_list
		])
		self.specific_routines = dict([
			(routine.specific_name, routine)
			for routine in self.routine_list
		])
		# XXX Add support for methods
		# XXX Add support for sequences
		self.trigger_list = sorted([
			Trigger(self, input, *item)
			for item in input.triggers
			if item[0] == self.name
		], key=lambda item:item.name)
		self.triggers = dict([
			(trigger.name, trigger)
			for trigger in self.trigger_list
		])

	def _get_identifier(self):
		return "schema_%s" % (self.name)
	
	def _get_qualified_name(self):
		# Schemas form the top of the naming hierarchy
		return self.name
	
	def _get_database(self):
		return self.parent

	def _get_parent_list(self):
		return self.database.schema_list


class Table(Relation):
	"""Class representing a table"""

	type_name = 'Table'

	def __init__(self, schema, input, *row):
		"""Initializes an instance of the class from a input row"""
		(
			_, # schema_name
			name,
			self.owner,
			system,
			self.created,
			self.last_stats,
			self.cardinality,
			self.size,
			self._tablespace,
			desc
		) = row
		super(Table, self).__init__(schema, name, system, desc)
		self._field_list = [
			Field(self, input, position, *item)
			for (position, item) in enumerate(input.relation_cols[(schema.name, self.name)])
		]
		self._fields = dict([
			(field.name, field)
			for field in self._field_list
		])
		self._dependents = RelationsDict(
			self.database,
			input.relation_dependents[(schema.name, self.name)]
		)
		self._dependent_list = RelationsList(
			self.database,
			input.relation_dependents[(schema.name, self.name)]
		)
		self.indexes = IndexesDict(
			self.database,
			input.table_indexes[(schema.name, self.name)]
		)
		self.index_list = IndexesList(
			self.database,
			input.table_indexes[(schema.name, self.name)]
		)
		self.triggers = TriggersDict(
			self.database,
			input.relation_triggers[(schema.name, self.name)]
		)
		self.trigger_list = TriggersList(
			self.database,
			input.relation_triggers[(schema.name, self.name)]
		)
		self.trigger_dependents = TriggersDict(
			self.database,
			input.trigger_dependents[(schema.name, self.name)]
		)
		self.trigger_dependent_list = TriggersList(
			self.database,
			input.trigger_dependents[(schema.name, self.name)]
		)
		self.unique_key_list = [
			UniqueKey(self, input, *item)
			for item in input.unique_keys[(schema.name, self.name)]
			if not item[-2]
		]
		pitem = [
			PrimaryKey(self, input, *item)
			for item in input.unique_keys[(schema.name, self.name)]
			if item[-2]
		]
		if len(pitem) == 0:
			self.primary_key = None
		elif len(pitem) == 1:
			self.primary_key = pitem[0]
			self.unique_key_list.append(self.primary_key)
		else:
			# Something's gone horribly wrong in the input plugin - got more
			# than one primary key for the table!
			assert False
		self.unique_key_list = sorted(
			self.unique_key_list,
			key=lambda item:item.name
		)
		self.unique_keys = dict([
			(unique_key.name, unique_key)
			for unique_key in self.unique_key_list
		])
		self.foreign_key_list = sorted([
			ForeignKey(self, input, *item)
			for item in input.foreign_keys[(schema.name, self.name)]
		], key=lambda item:item.name)
		self.foreign_keys = dict([
			(foreign_key.name, foreign_key)
			for foreign_key in self.foreign_key_list
		])
		self.check_list = sorted([
			Check(self, input, *item)
			for item in input.checks[(schema.name, self.name)]
		], key=lambda item:item.name)
		self.checks = dict([
			(check.name, check)
			for check in self.check_list
		])
		self.constraint_list = sorted(
			self.unique_key_list + self.foreign_key_list + self.check_list,
			key=lambda item:item.name
		)
		self.constraints = dict([
			(constraint.name, constraint)
			for constraint in self.constraint_list
		])
	
	def _get_size_str(self):
		"""Returns the size of the table in a human-readable form"""
		return format_size(self.size, for_sql=False)

	def _get_fields(self):
		return self._fields

	def _get_field_list(self):
		return self._field_list

	def _get_dependents(self):
		return self._dependents

	def _get_dependent_list(self):
		return self._dependent_list

	def _get_create_sql(self):
		sql = Template('CREATE TABLE $schema.$table ($elements) IN $tbspace;')
		return sql.substitute({
			'schema': format_ident(self.schema.name),
			'table': format_ident(self.name),	
			'elements': ',\n'.join([
					field.prototype
					for field in self.field_list
				] + [
					constraint.prototype
					for constraint in self.constraints.itervalues()
					if not isinstance(constraint, Check) or not constraint.system
				]),
			'tbspace': format_ident(self.tablespace.name),
		})
	
	def _get_drop_sql(self):
		sql = Template('DROP TABLE $schema.$table;')
		return sql.substitute({
			'schema': format_ident(self.schema.name),
			'table': format_ident(self.name)
		})
	
	def _get_tablespace(self):
		"""Returns the tablespace in which the table's data is stored"""
		return self.database.tablespaces[self._tablespace]

	size_str = property(_get_size_str)
	tablespace = property(_get_tablespace)


class View(Relation):
	"""Class representing a view"""

	type_name = 'View'
	
	def __init__(self, schema, input, *row):
		"""Initializes an instance of the class from a input row"""
		(
			_, # schema_name
			name,
			self.owner,
			system,
			self.created,
			self.read_only,
			self.sql,
			desc
		) = row
		super(View, self).__init__(schema, name, system, desc)
		self._field_list = [
			Field(self, input, position, *item)
			for (position, item) in enumerate(input.relation_cols[(schema.name, self.name)])
		]
		self._fields = dict([
			(field.name, field)
			for field in self._field_list
		])
		self._dependents = RelationsDict(
			self.database,
			input.relation_dependents[(schema.name, self.name)]
		)
		self._dependent_list = RelationsList(
			self.database,
			input.relation_dependents[(schema.name, self.name)]
		)
		self.dependencies = RelationsDict(
			self.database,
			input.relation_dependencies[(schema.name, self.name)]
		)
		self.dependency_list = RelationsList(
			self.database,
			input.relation_dependencies[(schema.name, self.name)]
		)
		self.triggers = TriggersDict(
			self.database,
			input.relation_triggers[(schema.name, self.name)]
		)
		self.trigger_list = TriggersList(
			self.database,
			input.relation_triggers[(schema.name, self.name)]
		)

	def _get_dependents(self):
		return self._dependents
	
	def _get_dependent_list(self):
		return self._dependent_list
	
	def _get_fields(self):
		return self._fields
	
	def _get_field_list(self):
		return self._field_list

	def _get_create_sql(self):
		return self.sql + ';'
	
	def _get_drop_sql(self):
		sql = Template('DROP VIEW $schema.$view;')
		return sql.substitute({
			'schema': format_ident(self.schema.name),
			'view': format_ident(self.name),
		})


class Alias(Relation):
	"""Class representing a alias"""

	type_name = 'Alias'
	
	def __init__(self, schema, input, *row):
		"""Initializes an instance of the class from a input row"""
		(
			_, # schema_name
			name,
			self.owner,
			system,
			self.created,
			self._relation_schema,
			self._relation_name,
			desc
		) = row
		super(Alias, self).__init__(schema, name, system, desc)
		# XXX An alias should have its own Field objects
		self._dependents = RelationsDict(
			self.database,
			input.relation_dependents[(schema.name, self.name)]
		)
		self._dependent_list = RelationsList(
			self.database,
			input.relation_dependents[(schema.name, self.name)]
		)

	def _get_fields(self):
		return self.relation.fields

	def _get_field_list(self):
		return self.relation.field_list
	
	def _get_dependents(self):
		return self._dependents

	def _get_dependent_list(self):
		return self._dependent_list

	def _get_create_sql(self):
		sql = Template('CREATE ALIAS $schema.$alias FOR $baseschema.$baserelation;')
		return sql.substitute({
			'schema': format_ident(self.schema.name),
			'alias': format_ident(self.name),
			'baseschema': format_ident(self.relation.schema.name),
			'baserelation': format_ident(self.relation.name)
		})
	
	def _get_drop_sql(self):
		sql = Template('DROP ALIAS $schema.$alias;')
		return sql.substitute({
			'schema': format_ident(self.schema.name),
			'alias': format_ident(self.name)
		})
	
	def _get_relation(self):
		"""Returns the relation the alias is for.

		This property returns the object representing the relation that
		is this alias is defined for.
		"""
		return self.database.schemas[self._relation_schema].relations[self._relation_name]

	def _get_final_relation(self):
		"""Returns the final non-alias relation in a chain of aliases.

		This property returns the view or table that the alias ultimately
		points to by resolving any aliases in between.
		"""
		result = self
		while isinstance(result, Alias):
			result = result.relation
		return result
	
	relation = property(_get_relation)
	final_relation = property(_get_final_relation)


class Index(SchemaObject):
	"""Class representing an index"""

	type_name = 'Index'

	def __init__(self, schema, input, *row):
		"""Initializes an instance of the class from a input row"""
		(
			_, # schema_name
			name,
			self._table_schema,
			self._table_name,
			self.owner,
			system,
			self.created,
			self.last_stats,
			self.cardinality,
			self.size,
			self.unique,
			self._tablespace,
			desc
		) = row
		super(Index, self).__init__(schema, name, system, desc)
		self.fields = IndexFieldsDict(
			self.database,
			self._table_schema,
			self._table_name,
			input.index_cols[(schema.name, self.name)]
		)
		self.field_list = IndexFieldsList(
			self.database,
			self._table_schema,
			self._table_name,
			input.index_cols[(schema.name, self.name)]
		)

	def _get_identifier(self):
		return "index_%s_%s" % (self.schema.name, self.name)

	def _get_parent_list(self):
		return self.schema.index_list

	def _get_create_sql(self):
		sql = 'CREATE $type $schema.$index ON $tbschema.$tbname ($fields)'
		values = {
			'type': {False: 'INDEX', True: 'UNIQUE INDEX'}[self.unique],
			'schema': format_ident(self.schema.name),
			'index': format_ident(self.name),
			'tbschema': format_ident(self.table.schema.name),
			'tbname': format_ident(self.table.name),
			'fields': ', '.join(['%s%s' % (format_ident(field.name), {
				'A': '',
				'D': ' DESC'
			}[order]) for (field, order) in self.field_list if order != 'I'])
		}
		if self.unique:
			incfields = [
				field
				for (field, order) in self.field_list
				if order == 'I'
			]
			if len(incfields) > 0:
				sql += '\nINCLUDE ($incfields)'
				values['incfields'] = ', '.join([format_ident(field.name) for field in incfields])
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
		return self.database.tablespaces[self._tablespace]

	table = property(_get_table)
	tablespace = property(_get_tablespace)


class Trigger(SchemaObject):
	"""Class representing an index"""

	type_name = 'Trigger'

	def __init__(self, schema, input, *row):
		"""Initializes an instance of the class from a input row"""
		(
			_, # schema_name
			name,
			self.owner,
			system,
			self.created,
			self._relation_schema,
			self._relation_name,
			self.trigger_time,
			self.trigger_event,
			self.granularity,
			self.sql,
			desc
		) = row
		super(Trigger, self).__init__(schema, name, system, desc)
		self.dependencies = RelationsDict(
			self.database,
			input.trigger_dependencies[(schema.name, self.name)]
		)
		self.dependency_list = RelationsList(
			self.database,
			input.trigger_dependencies[(schema.name, self.name)]
		)

	def _get_identifier(self):
		return "trigger_%s_%s" % (self.schema.name, self.name)

	def _get_parent_list(self):
		return self.schema.trigger_list

	def _get_create_sql(self):
		if self.sql:
			return self.sql + '!'
		else:
			return ''

	def _get_drop_sql(self):
		sql = Template('DROP TRIGGER $schema.$trigger;')
		return sql.substitute({
			'schema': format_ident(self.schema.name),
			'trigger': format_ident(self.name),
		})

	def _get_relation(self):
		"""Returns the relation that the trigger applies to"""
		return self.database.schemas[self._relation_schema].relations[self._relation_name]

	relation = property(_get_relation)


class Function(Routine):
	"""Class representing a function"""

	type_name = 'Function'
	
	def __init__(self, schema, input, *row):
		"""Initializes an instance of the class from a input row"""
		(
			_, # schema_name
			specific_name,
			name,
			self.owner,
			system,
			self.created,
			self.type,
			self.deterministic,
			self.external_action,
			self.null_call,
			self.sql_access,
			self.sql,
			desc
		) = row
		super(Function, self).__init__(schema, name, specific_name, system, desc)
		self._param_list = [
			Param(self, input, position, *item)
			for (position, item) in enumerate(input.function_params[(schema.name, self.specific_name)])
			if item[1] != 'R'
		]
		self._params = dict([
			(param.name, param)
			for param in self._param_list
		])
		self._return_list = [
			Param(self, input, position, *item)
			for (position, item) in enumerate(input.function_params[(schema.name, self.specific_name)])
			if item[1] == 'R'
		]
		self._returns = dict([
			(param.name, param)
			for param in self._return_list
		])
		self._params = {}
		self._returns = {}

	def _get_parent_list(self):
		return self.schema.function_list

	def _get_params(self):
		return self._params
	
	def _get_param_list(self):
		return self._param_list

	def _get_returns(self):
		return self._returns

	def _get_return_list(self):
		return self._return_list
	
	def _get_prototype(self):
		
		def format_params(params):
			return ', '.join(['%s %s' % (format_ident(param.name), param.datatype_str) for param in params])

		def format_returns():
			if len(self.return_list) == 0:
				return ''
			elif self.type == 'R':
				return ' RETURNS ROW(%s)' % (format_params(self.return_list))
			elif self.type == 'T':
				return ' RETURNS TABLE(%s)' % (format_params(self.return_list))
			else:
				return ' RETURNS %s' % (self.return_list[0].datatype_str)

		sql = Template('$schema.$function($params)$returns')
		return sql.substitute({
			'schema': format_ident(self.schema.name),
			'function': format_ident(self.name),
			'params': format_params(self.param_list),
			'returns': format_returns()
		})
	
	def _get_create_sql(self):
		if self.sql:
			return self.sql + '!'
		else:
			return ''
	
	def _get_drop_sql(self):
		sql = Template('DROP SPECIFIC FUNCTION $schema.$specific;')
		return sql.substitute({
			'schema': format_ident(self.schema.name),
			'specific': format_ident(self.specific_name)
		})


class Procedure(Routine):
	"""Class representing a procedure"""

	type_name = 'Procedure'
	
	def __init__(self, schema, input, *row):
		"""Initializes an instance of the class from a input row"""
		(
			_, # schema_name
			specific_name,
			name,
			self.owner,
			system,
			self.created,
			self.deterministic,
			self.external_action,
			self.null_call,
			self.sql_access,
			self.sql,
			desc
		) = row
		super(Procedure, self).__init__(schema, name, specific_name, system, desc)
		self._param_list = [
			Param(self, input, position, *item)
			for (position, item) in enumerate(input.procedure_params[(schema.name, self.specific_name)])
			if item[1] != 'R'
		]
		self._params = dict([
			(param.name, param)
			for param in self._param_list
		])

	def _get_parent_list(self):
		return self.schema.procedure_list

	def _get_params(self):
		return self._params

	def _get_param_list(self):
		return self._param_list

	def _get_prototype(self):
		
		def format_params(params):
			parmtype = {
				'I': 'IN',
				'O': 'OUT',
				'B': 'INOUT',
			}
			return ', '.join([
				'%s %s %s' % (parmtype[param.type], param.name, param.datatype_str)
				for param in params
			])

		sql = Template('$schema.$proc($params)')
		return sql.substitute({
			'schema': format_ident(self.schema.name),
			'proc': format_ident(self.name),
			'params': format_params(self.param_list)
		})
	
	def _get_create_sql(self):
		if self.sql:
			return self.sql + '!'
		else:
			return ''
	
	def _get_drop_sql(self):
		sql = Template('DROP SPECIFIC PROCEDURE $schema.$specific;')
		return sql.substitute({
			'schema': format_ident(self.schema.name),
			'specific': format_ident(self.specific_name)
		})


class Datatype(SchemaObject):
	"""Class representing a datatype"""

	type_name = 'Data Type'
	
	def __init__(self, schema, input, *row):
		"""Initializes an instance of the class from a input row"""
		(
			_,
			name,
			self.owner,
			system,
			self.created,
			self._source_schema,
			self._source_name,
			self.size,
			self.scale,
			self.codepage,
			self.final,
			desc
		) = row
		super(Datatype, self).__init__(schema, name, system, desc)
		# XXX DB2 specific
		self.variable_size = self._system and (self.size is None) and (self.name not in ("XML", "REFERENCE"))
		self.variable_scale = self._system and (self.name == "DECIMAL")

	def _get_identifier(self):
		return "datatype_%s_%s" % (self.schema.name, self.name)
	
	def _get_source(self):
		"""Returns the datatype on which this type is based.

		If this datatype is based on another type this property returns the
		object representing the base datatype.
		"""
		if self._source_name:
			return self.database.schemas[self._source_schema].datatypes[self._source_name]
		else:
			return None
	
	source = property(_get_source)


class Field(RelationObject):
	"""Class representing a field in a relation"""

	type_name = 'Field'

	def __init__(self, relation, input, position, *row):
		"""Initializes an instance of the class from a input row"""
		# XXX DB2 specific assumption: some databases have system columns (e.g. OID)
		(
			name,
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
		super(Field, self).__init__(relation, name, False, desc)
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


class UniqueKey(Constraint):
	"""Class representing a unique key in a table"""

	type_name = 'Unique Key'

	def __init__(self, table, input, *row):
		"""Initializes an instance of the class from a input row"""
		(
			name,
			self.owner,
			system,
			self.created,
			_, # primary
			desc
		) = row
		super(UniqueKey, self).__init__(table, name, system, desc)
		# XXX DB2 specific: should be provided by input plugin
		self._anonymous = re.match('^SQL\d{15}$', self.name)
		self._fields = ConstraintFieldsList(
			table,
			input.unique_key_cols[(table.schema.name, table.name, self.name)]
		)
		self.dependents = ConstraintsDict(
			self.database,
			input.parent_keys[(table.schema.name, table.name, self.name)]
		)
		self.dependent_list = ConstraintsList(
			self.database,
			input.parent_keys[(table.schema.name, table.name, self.name)]
		)

	def _get_fields(self):
		return self._fields

	def _get_prototype(self):
		sql = 'UNIQUE (%s)' % ', '.join([format_ident(field.name) for field in self.fields])
		if not self._anonymous:
			sql = 'CONSTRAINT %s %s' % (self.name, sql)
		return sql


class PrimaryKey(UniqueKey):
	"""Class representing a primary key in a table"""

	type_name = 'Primary Key'

	def _get_prototype(self):
		sql = 'PRIMARY KEY (%s)' % ', '.join([format_ident(field.name) for field in self.fields])
		if not self._anonymous:
			sql = 'CONSTRAINT %s %s' % (self.name, sql)
		return sql


class ForeignKey(Constraint):
	"""Class representing a foreign key in a table"""

	type_name = 'Foreign Key'

	def __init__(self, table, input, *row):
		"""Initializes an instance of the class from a input row"""
		(
			name,
			self.owner,
			system,
			self.created,
			self._ref_table_schema,
			self._ref_table_name,
			self._ref_key_name,
			self.delete_rule,
			self.update_rule,
			desc
		) = row
		super(ForeignKey, self).__init__(table, name, system, desc)
		# XXX DB2 specific: should be provided by input plugin
		self._anonymous = re.match('^SQL\d{15}$', self.name)
		self._fields = ForeignKeyFieldsList(
			table, self._ref_table_schema, self._ref_table_name,
			input.foreign_key_cols[(table.schema.name, table.name, self.name)]
		)

	def _get_fields(self):
		return self._fields

	def _get_prototype(self):
		sql = 'FOREIGN KEY (%s) REFERENCES %s.%s(%s)' % (
			', '.join([format_ident(myfield.name) for (myfield, reffield) in self.fields]),
			format_ident(self.ref_table.schema.name),
			format_ident(self.ref_table.name),
			', '.join([format_ident(reffield.name) for (myfield, reffield) in self.fields])
		)
		rules = {
			'A': 'NO ACTION',
			'C': 'CASCADE',
			'N': 'SET NULL',
			'R': 'RESTRICT',
		}
		if self.delete_rule:
			sql += ' ON DELETE ' + rules[self.delete_rule]
		if self.update_rule:
			sql += ' ON UPDATE ' + rules[self.update_rule]
		if not self._anonymous:
			sql = 'CONSTRAINT %s %s' % (self.name, sql)
		return sql

	def _get_ref_table(self):
		"""Returns the table that this foreign key references"""
		return self.database.schemas[self._ref_table_schema].tables[self._ref_table_name]

	def _get_ref_key(self):
		"""Returns the corresponding unique key in the referenced table"""
		return self.ref_table.unique_keys[self._ref_key_name]

	ref_table = property(_get_ref_table)
	ref_key = property(_get_ref_key)


class Check(Constraint):
	"""Class representing a check constraint in a table"""

	type_name = 'Check Constraint'

	def __init__(self, table, input, *row):
		"""Initializes an instance of the class from a input row"""
		(
			name,
			self.owner,
			system,
			self.created,
			self.expression,
			desc
		) = row
		super(Check, self).__init__(table, name, system, desc)
		# XXX DB2 specific: should be provided by input plugin
		self._anonymous = re.match('^SQL\d{15}$', self.name)
		self._fields = ConstraintFieldsList(
			table,
			input.check_cols[(table.schema.name, table.name, self.name)]
		)

	def _get_fields(self):
		return self._fields

	def _get_prototype(self):
		sql = 'CHECK (%s)' % self.expression
		if not self._anonymous:
			sql = 'CONSTRAINT %s %s' % (self.name, sql)
		return sql


class Param(RoutineObject):
	"""Class representing a parameter in a routine in a DB2 database"""

	type_name = 'Parameter'

	def __init__(self, routine, input, position, *row):
		"""Initializes an instance of the class from a input row"""
		(
			name,
			self.type,
			self._datatype_schema,
			self._datatype_name,
			self.size,
			self.scale,
			self.codepage,
			desc
		) = row
		# If the parameter is unnamed, make up a name based on the parameter's
		# position
		if name:
			# XXX DB2 assumption? Is there such a thing as a "system-maintained
			# parameter" in any RDBMS?
			super(Param, self).__init__(routine, name, False, desc)
		else:
			super(Param, self).__init__(routine, 'P%d' % position, False, desc)

	def _get_identifier(self):
		return "param_%s_%s_%d" % (self.parent.parent.name, self.parent.specific_name, self.position)

	def _get_datatype(self):
		"""Returns the object representing the parameter's datatype"""
		return self.database.schemas[self._datatype_schema].datatypes[self._datatype_name]

	def _get_datatype_str(self):
		"""Returns a string representation of the datatype of the parameter.

		This is a convenience property which returns the datatype of the
		parameter with all necessary arguments in parentheses. It is used in
		constructing the prototype of the field.
		"""
		if self.datatype.system:
			result = format_ident(self.datatype.name)
		else:
			result = '%s.%s' % (
				format_ident(self.datatype.schema.name),
				format_ident(self.datatype.name)
			)
		if self.datatype.variable_size and not self.size is None:
			result += '(%s' % (format_size(self.size))
			if self.datatype.variable_scale and not self.scale is None:
				result += ',%d' % (self.scale)
			result += ')'
		return result

	datatype = property(_get_datatype)
	datatype_str = property(_get_datatype_str)
