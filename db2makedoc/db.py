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
from itertools import chain, groupby
from UserDict import DictMixin
from db2makedoc.sql.formatter import format_size, format_ident
from db2makedoc.util import *


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

# XXX Many of these could be made direct subclasses of list, tuple, etc.
# XXX These should be replaced with the new ABCs in Python 2.6's collections package

class DictProxy(object, DictMixin):
	"""Presents a dictionary of objects from a list of identifiers.

	This abstract class acts like a read-only dictionary of objects from the
	database hierarchy. It is initialized from a list of identifiers which are
	used to lookup the actual objects from the hierarchy. This class is
	overridden below to implement dictionaries of relations, indexes, etc.
	"""

	def __init__(self, items, key=None):
		"""Initializes the dict from a list of tuples.
		
		If key is not specified, items must be a list of tuples which uniquely
		identify an object in the database hierarchy (e.g. if the dictionary
		represents relations then the tuples must be of the form (schema,
		name)). Otherwise, key is a function which must convert an element of
		items to the necessary form.
		"""
		super(DictProxy, self).__init__()
		if key is None:
			key = lambda x: x
		self._keys = set((key(i) for i in items))
		
	def _convert(self, item):
		"""Converts the tuple into a "real" database object.

		Override this method in descendents to convert the tuple of identifers
		stored in the object into a "real" object from the database object
		hierarchy. The default implementation raises an exception.
		"""
		raise NotImplementedError
		
	def keys(self):
		return self._keys
	
	def has_key(self, key):
		return key in self._keys
	
	def __len__(self):
		return len(self._keys)
	
	def __getitem__(self, key):
		if not key in self._keys:
			raise KeyError(key)
		return self._convert(key)
	
	def __iter__(self):
		for k in self._keys:
			yield k
			
	def __contains__(self, key):
		return key in self._keys


class ListProxy(object):
	"""Presents a list of objects from a list of identifiers.

	This abstract class acts like a read-only list of objects from the database
	hierarchy. It is initialized from a list of identifiers which are used to
	lookup the actual objects from the hierarchy. This class is overridden
	below to implement lists of relations, indexes, etc.  """
	
	def __init__(self, items, key=None):
		"""Initializes the list from a list of tuples.
		
		If key is not specified, items must be a list of tuples which uniquely
		identify an object in the database hierarchy (e.g. if the list proxy
		represents relations then the tuples must be of the form (schema,
		name)). Otherwise, key is a function which must convert an element of
		items to the necessary form.
		"""
		super(ListProxy, self).__init__()
		if key is None:
			key = lambda x: x
		self._items = [key(i) for i in items]

	def _convert(self, item):
		"""Converts the tuple into a "real" database object.

		Override this method in descendents to convert the tuple of identifers
		stored in the object into a "real" object from the database object
		hierarchy. The default implementation raises an exception.
		"""
		raise NotImplementedError
		
	def __len__(self):
		return len(self._items)
	
	def __getitem__(self, key):
		return self._convert(self._items[key])
	
	def __iter__(self):
		for i in self._items:
			yield self._convert(i)

	def __contains__(self, key):
		return any(i == key for i in self)

	def index(self, x, i=0, j=None):
		if j is None:
			j = len(self)
		for result in xrange(i, j):
			if self[result] is x:
				return result
		raise ValueError("%s not found in list" % repr(x))


class RelationsDict(DictProxy):
	def __init__(self, database, items, key=None):
		super(RelationsDict, self).__init__(items, key)
		assert isinstance(database, Database)
		self._database = database

	def _convert(self, item):
		(schema, relation) = item
		return self._database.schemas[schema].relations[relation]


class RelationsList(ListProxy):
	def __init__(self, database, items, key=None):
		super(RelationsList, self).__init__(items, key)
		assert isinstance(database, Database)
		self._database = database

	def _convert(self, item):
		(schema, relation) = item
		return self._database.schemas[schema].relations[relation]


class IndexesDict(DictProxy):
	def __init__(self, database, items, key=None):
		super(IndexesDict, self).__init__(items, key)
		assert isinstance(database, Database)
		self._database = database

	def _convert(self, item):
		(schema, index) = item
		return self._database.schemas[schema].indexes[index]


class IndexesList(ListProxy):
	def __init__(self, database, items, key=None):
		super(IndexesList, self).__init__(items, key)
		assert isinstance(database, Database)
		self._database = database

	def _convert(self, item):
		(schema, index) = item
		return self._database.schemas[schema].indexes[index]


class ConstraintsDict(DictProxy):
	def __init__(self, database, items, key=None):
		super(ConstraintsDict, self).__init__(items, key)
		assert isinstance(database, Database)
		self._database = database

	def _convert(self, item):
		(schema, table, constraint) = item
		return self._database.schemas[schema].tables[table].constraints[constraint]


class ConstraintsList(ListProxy):
	def __init__(self, database, items, key=None):
		super(ConstraintsList, self).__init__(items, key)
		assert isinstance(database, Database)
		self._database = database

	def _convert(self, item):
		(schema, table, constraint) = item
		return self._database.schemas[schema].tables[table].constraints[constraint]


class TriggersDict(DictProxy):
	def __init__(self, database, items, key=None):
		super(TriggersDict, self).__init__(items, key)
		assert isinstance(database, Database)
		self._database = database

	def _convert(self, item):
		(schema, trigger) = item
		return self._database.schemas[schema].triggers[trigger]


class TriggersList(ListProxy):
	def __init__(self, database, items, key=None):
		super(TriggersList, self).__init__(items, key)
		assert isinstance(database, Database)
		self._database = database

	def _convert(self, item):
		(schema, trigger) = item
		return self._database.schemas[schema].triggers[trigger]


class IndexFieldsDict(DictProxy):
	def __init__(self, database, schema, table, fields):
		super(IndexFieldsDict, self).__init__(fields, key=attrgetter('name'))
		assert isinstance(database, Database)
		self._database = database
		self._schema = schema
		self._table = table
		self._order = dict((f.name, f.order) for f in fields)

	def _convert(self, item):
		return (self._database.schemas[self._schema].tables[self._table].fields[item], self._order[item])


class IndexFieldsList(ListProxy):
	def __init__(self, database, schema, table, fields):
		super(IndexFieldsList, self).__init__(fields, key=attrgetter('name', 'order'))
		assert isinstance(database, Database)
		self._database = database
		self._schema = schema
		self._table = table

	def _convert(self, item):
		(name, order) = item
		return (self._database.schemas[self._schema].tables[self._table].fields[name], order)


class ConstraintFieldsList(ListProxy):
	def __init__(self, table, fields):
		super(ConstraintFieldsList, self).__init__(fields, key=attrgetter('name'))
		assert isinstance(table, Table)
		self._table = table

	def _convert(self, item):
		return self._table.fields[item]


class ForeignKeyFieldsList(ListProxy):
	def __init__(self, table, ref_schema, ref_table, fields):
		super(ForeignKeyFieldsList, self).__init__(fields, key=attrgetter('name', 'ref_name'))
		assert isinstance(table, Table)
		self._table = table
		self._database = table.database
		self._ref_schema = ref_schema
		self._ref_table = ref_table

	def _convert(self, item):
		(field, parent) = item
		parent_table = self._database.schemas[self._ref_schema].tables[self._ref_table]
		return (self._table.fields[field], parent_table.fields[parent])


# ABSTRACT BASE CLASSES #######################################################

class DatabaseObject(object):
	"""Base class for all documented database objects"""

	config_names = ['all']

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
		self.description = description
		self._system = system
		self._parent_index = None
		logging.debug("Building %s %s" % (self.__class__.__name__, self.qualified_name))

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
		elif self._parent_index is None:
			# Cache the result as this is a potentially expensive lookup and
			# parent_list is not permitted to change after construction
			self._parent_index = self.parent_list.index(self)
		return self._parent_index
	
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

	config_names = []

	def __init__(self, parent, name, system=False, description=None):
		"""Initializes an instance of the class"""
		assert isinstance(parent, Schema)
		super(SchemaObject, self).__init__(parent, name, system, description)
		self.schema = parent
	
	def _get_database(self):
		return self.parent.parent


class RelationObject(DatabaseObject):
	"""Base class for database objects that belong directly to a relation"""

	config_names = []

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

	config_names = []

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

	config_names = ['relation', 'relations']

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

	config_names = ['routine', 'routines']

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

	def _get_qualified_specific_name(self):
		"""Returns the fully qualified specific name of the routine.

		This property recurses up the hierarchy to construct the fully
		qualified specific name of the object (the result should be valid as an
		SQL routine name, although not for invocation).
		"""
		result = self.specific_name
		if self.parent:
			result = self.parent.qualified_name + '.' + result
		return result

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
	
	qualified_specific_name = property(lambda self: self._get_qualified_specific_name(), doc=_get_qualified_specific_name.__doc__)
	params = property(lambda self: self._get_params(), doc=_get_params.__doc__)
	param_list = property(lambda self: self._get_param_list(), doc=_get_param_list.__doc__)
	returns = property(lambda self: self._get_returns(), doc=_get_returns.__doc__)
	return_list = property(lambda self: self._get_return_list(), doc=_get_return_list.__doc__)
	prototype = property(lambda self: self._get_prototype(), doc=_get_prototype.__doc__)


class Constraint(RelationObject):
	"""Base class for constraints that belong in a relation (e.g. primary keys, checks, etc.)"""

	config_names = ['constraint', 'constraints']

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
		return 'ALTER TABLE %s.%s ADD %s' % (
			format_ident(self.table.schema.name),
			format_ident(self.table.name),
			self.prototype
		)

	def _get_drop_sql(self):
		return 'ALTER TABLE %s.%s DROP CONSTRAINT %s' % (
			format_ident(self.table.schema.name),
			format_ident(self.table.name),
			format_ident(self.name)
		)
	
	def _get_parent_list(self):
		return self.table.constraint_list

	fields = property(lambda self: self._get_fields(), doc=_get_fields.__doc__)
	prototype = property(lambda self: self._get_prototype(), doc=_get_prototype.__doc__)


# CONCRETE CLASSES ############################################################


class Database(DatabaseObject):
	"""Class representing a DB2 database"""

	config_names = ['database', 'databases', 'db', 'dbs']
	
	def __init__(self, input):
		"""Initializes an instance of the class"""
		super(Database, self).__init__(None, input.name)
		self.tablespace_list = [Tablespace(self, input, t) for t in input.tablespaces]
		self.tablespaces = dict((t.name, t) for t in self.tablespace_list)
		self.schema_list = [Schema(self, input, s) for s in input.schemas]
		# Prune completely empty schemas
		self.schema_list = [
			s for s in self.schema_list
			if sum([
				len(s.relation_list),
				len(s.routine_list),
				len(s.trigger_list),
				len(s.index_list),
				len(s.datatype_list),
			]) > 0
		]
		self.schemas = dict((s.name, s) for s in self.schema_list)
		# Prune completely empty tablespaces
		self.tablespace_list = [
			t for t in self.tablespace_list
			if sum([
				len(t.table_list),
				len(t.index_list),
			]) > 0
		]
		self.tablespaces = dict((t.name, t) for t in self.tablespace_list)

	def find(self, qualified_name):
		"""Find an object in the hierarchy by its qualified name.
		
		Because there are several namespaces in DB2, the results of such a
		search can only be unambiguous if an order of precedence for object
		types is established. The order of precedence used by this method is
		as follows:
		
		Schemas
		Tablespaces
			Tables, Views, Aliases (one namespace)
				Fields
				Constraints
			Indexes
			Functions, Methods, Procedures (one namespace)
		
		Hence, if a schema shares a name with a tablespace, the schema will
		be returned in preference to the tablespace. Likewise, if an index
		shares a name with a table, the table will be returned in preference
		to the index.
		"""
		# XXX This is wrong: delimited names can contain the . separator
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
		(namely, the object). Note that certain objects in the tree are
		excluded for not being "database objects". Specifically, function and
		procedure parameters are not included, nor are index fields, or
		constraint fields. This is because these are not "independent" objects,
		i.e. while you can add and remove fields to/from a table, you cannot
		add and remove parameters to/from a procedure (without redefining it).

		Additional parameters can be passed which will be captured by args and
		kwargs and passed verbatim to method on each invocation.

		The return value of the method is ignored.
		"""
		method(self, *args, **kwargs)
		for schema in self.schemas.itervalues():
			method(schema, *args, **kwargs)
			for datatype in schema.datatypes.itervalues():
				method(datatype, *args, **kwargs)
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

	config_names = ['tablespace', 'tablespaces']

	def __init__(self, database, input, row):
		"""Initializes an instance of the class from a input row"""
		super(Tablespace, self).__init__(database, row.name, row.system, row.description)
		self.owner = row.owner
		self.created = row.created
		self.type = row.type
		self.table_list = RelationsList(
			self.database, input.tablespace_tables.get((self.name,), []),
			key=attrgetter('schema', 'name')
		)
		self.tables = RelationsDict(
			self.database, input.tablespace_tables.get((self.name,), []),
			key=attrgetter('schema', 'name')
		)
		self.index_list = IndexesList(
			self.database, input.tablespace_indexes.get((self.name,), []),
			key=attrgetter('schema', 'name')
		)
		self.indexes = IndexesDict(
			self.database, input.tablespace_indexes.get((self.name,), []),
			key=attrgetter('schema', 'name')
		)

	def _get_identifier(self):
		return "tbspace_%s" % self.name

	def _get_qualified_name(self):
		return self.name

	def _get_database(self):
		return self.parent

	def _get_parent_list(self):
		return self.database.tablespace_list


class Schema(DatabaseObject):
	"""Class representing a schema"""

	config_names = ['schema', 'schemas']

	def __init__(self, database, input, row):
		"""Initializes an instance of the class from a input row"""
		super(Schema, self).__init__(database, row.name, row.system, row.description)
		self.owner = row.owner
		self.created = row.created
		self.datatype_list = [
			Datatype(self, input, i)
			for i in input.datatypes
			if i.schema == self.name
		]
		self.datatypes = dict((i.name, i) for i in self.datatype_list)
		self.table_list = [
			Table(self, input, i)
			for i in input.tables
			if i.schema == self.name
		]
		self.tables = dict((i.name, i) for i in self.table_list)
		self.view_list = [
			View(self, input, i)
			for i in input.views
			if i.schema == self.name
		]
		self.views = dict((i.name, i) for i in self.view_list)
		self.alias_list = [
			Alias(self, input, i)
			for i in input.aliases
			if i.schema == self.name
		]
		self.aliases = dict((i.name, i) for i in self.alias_list)
		self.relation_list = sorted(
			chain(self.table_list, self.view_list, self.alias_list),
			key=attrgetter('name')
		)
		self.relations = dict((i.name, i) for i in self.relation_list)
		self.index_list = [
			Index(self, input, i)
			for i in input.indexes
			if i.schema == self.name
		]
		self.indexes = dict((i.name, i) for i in self.index_list)
		self.function_list = [
			Function(self, input, i)
			for i in input.functions
			if i.schema == self.name
		]
		self.functions = sorted(self.function_list, key=attrgetter('name', 'specific_name'))
		self.functions = groupby(self.functions, key=attrgetter('name'))
		self.functions = dict((name, list(funcs)) for (name, funcs) in self.functions)
		self.specific_functions = dict((i.specific_name, i) for i in self.function_list)
		self.procedure_list = [
			Procedure(self, input, i)
			for i in input.procedures
			if i.schema == self.name
		]
		self.procedures = sorted(self.procedure_list, key=attrgetter('name', 'specific_name'))
		self.procedures = groupby(self.procedures, key=attrgetter('name'))
		self.procedures = dict((name, list(procs)) for (name, procs) in self.procedures)
		self.specific_procedures = dict((i.specific_name, i) for i in self.procedure_list)
		self.routine_list = sorted(
			chain(self.function_list, self.procedure_list),
			key=attrgetter('specific_name')
		)
		self.routines = sorted(self.routine_list, key=attrgetter('name', 'specific_name'))
		self.routines = groupby(self.routines, key=attrgetter('name'))
		self.routines = dict((name, list(routines)) for (name, routines) in self.routines)
		self.specific_routines = dict((i.specific_name, i) for i in self.routine_list)
		# XXX Add support for sequences
		self.trigger_list = [
			Trigger(self, input, i)
			for i in input.triggers
			if i.schema == self.name
		]
		self.triggers = dict((i.name, i) for i in self.trigger_list)

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

	config_names = ['table', 'tables']

	def __init__(self, schema, input, row):
		"""Initializes an instance of the class from a input row"""
		super(Table, self).__init__(schema, row.name, row.system, row.description)
		self.owner = row.owner
		self.created = row.created
		self.last_stats = row.last_stats
		self.cardinality = row.cardinality
		self.size = row.size
		self._tablespace = row.tbspace
		self._field_list = [
			Field(self, input, pos, i)
			for (pos, i) in enumerate(input.relation_cols.get((schema.name, self.name), []))
		]
		self._fields = dict((i.name, i) for i in self._field_list)
		self._dependents = RelationsDict(
			self.database,
			input.relation_dependents.get((schema.name, self.name), [])
		)
		self._dependent_list = RelationsList(
			self.database,
			input.relation_dependents.get((schema.name, self.name), [])
		)
		self.indexes = IndexesDict(
			self.database,
			input.table_indexes.get((schema.name, self.name), []),
			key=attrgetter('schema', 'name')
		)
		self.index_list = IndexesList(
			self.database,
			input.table_indexes.get((schema.name, self.name), []),
			key=attrgetter('schema', 'name')
		)
		self.triggers = TriggersDict(
			self.database,
			input.relation_triggers.get((schema.name, self.name), []),
			key=attrgetter('schema', 'name')
		)
		self.trigger_list = TriggersList(
			self.database,
			input.relation_triggers.get((schema.name, self.name), []),
			key=attrgetter('schema', 'name')
		)
		self.trigger_dependents = TriggersDict(
			self.database,
			input.trigger_dependents.get((schema.name, self.name), [])
		)
		self.trigger_dependent_list = TriggersList(
			self.database,
			input.trigger_dependents.get((schema.name, self.name), [])
		)
		self.unique_key_list = [
			UniqueKey(self, input, i)
			for i in input.unique_keys.get((schema.name, self.name), [])
			if not i.primary
		]
		primary_keys = [
			PrimaryKey(self, input, i)
			for i in input.unique_keys.get((schema.name, self.name), [])
			if i.primary
		]
		if len(primary_keys) == 0:
			self.primary_key = None
		elif len(primary_keys) == 1:
			self.primary_key = primary_keys[0]
			self.unique_key_list.append(self.primary_key)
		else:
			# Something's gone horribly wrong in the input plugin - got more
			# than one primary key for the table!
			assert False
		self.unique_keys = dict((i.name, i) for i in self.unique_key_list)
		self.foreign_key_list = [
			ForeignKey(self, input, i)
			for i in input.foreign_keys.get((schema.name, self.name), [])
		]
		self.foreign_keys = dict((i.name, i) for i in self.foreign_key_list)
		self.check_list = [
			Check(self, input, i)
			for i in input.checks.get((schema.name, self.name), [])
		]
		self.checks = dict((i.name, i) for i in self.check_list)
		self.constraint_list = sorted(
			chain(self.unique_key_list, self.foreign_key_list, self.check_list),
			key=attrgetter('name')
		)
		self.constraints = dict((i.name, i) for i in self.constraint_list)
	
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
		return 'CREATE TABLE %s.%s (%s) IN %s' % (
			format_ident(self.schema.name),
			format_ident(self.name),	
			',\n'.join(chain(
				(field.prototype for field in self.field_list),
				(const.prototype for const in self.constraints.itervalues()
					if not (isinstance(const, Check) and const.system))
			)),
			format_ident(self.tablespace.name),
		)
	
	def _get_drop_sql(self):
		return 'DROP TABLE %s.%s' % (
			format_ident(self.schema.name),
			format_ident(self.name)
		)
	
	def _get_tablespace(self):
		"""Returns the tablespace in which the table's data is stored"""
		return self.database.tablespaces[self._tablespace]

	size_str = property(_get_size_str)
	tablespace = property(_get_tablespace)


class View(Relation):
	"""Class representing a view"""

	config_names = ['view', 'views']
	
	def __init__(self, schema, input, row):
		"""Initializes an instance of the class from a input row"""
		super(View, self).__init__(schema, row.name, row.system, row.description)
		self.owner = row.owner
		self.created = row.created
		self.read_only = row.read_only
		self.sql = row.sql
		self._field_list = [
			Field(self, input, pos, i)
			for (pos, i) in enumerate(input.relation_cols.get((schema.name, self.name), []))
		]
		self._fields = dict((i.name, i) for i in self._field_list)
		self._dependents = RelationsDict(
			self.database,
			input.relation_dependents.get((schema.name, self.name), [])
		)
		self._dependent_list = RelationsList(
			self.database,
			input.relation_dependents.get((schema.name, self.name), [])
		)
		self.dependencies = RelationsDict(
			self.database,
			input.relation_dependencies.get((schema.name, self.name), [])
		)
		self.dependency_list = RelationsList(
			self.database,
			input.relation_dependencies.get((schema.name, self.name), [])
		)
		self.triggers = TriggersDict(
			self.database,
			input.relation_triggers.get((schema.name, self.name), []),
			key=attrgetter('schema', 'name')
		)
		self.trigger_list = TriggersList(
			self.database,
			input.relation_triggers.get((schema.name, self.name), []),
			key=attrgetter('schema', 'name')
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
		return self.sql
	
	def _get_drop_sql(self):
		return 'DROP VIEW %s.%s' % (
			format_ident(self.schema.name),
			format_ident(self.name),
		)


class Alias(Relation):
	"""Class representing a alias"""

	config_names = ['alias', 'aliases']
	
	def __init__(self, schema, input, row):
		"""Initializes an instance of the class from a input row"""
		super(Alias, self).__init__(schema, row.name, row.system, row.description)
		self.owner = row.owner
		self.created = row.created
		self._relation_schema = row.base_schema
		self._relation_name = row.base_name
		# XXX An alias should have its own Field objects
		self._dependents = RelationsDict(
			self.database,
			input.relation_dependents.get((schema.name, self.name), [])
		)
		self._dependent_list = RelationsList(
			self.database,
			input.relation_dependents.get((schema.name, self.name), [])
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
		return 'CREATE ALIAS %s.%s FOR %s.%s' % (
			format_ident(self.schema.name),
			format_ident(self.name),
			format_ident(self.relation.schema.name),
			format_ident(self.relation.name)
		)
	
	def _get_drop_sql(self):
		return 'DROP ALIAS %s.%s' % (
			format_ident(self.schema.name),
			format_ident(self.name)
		)
	
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
		result = self.relation
		while isinstance(result, Alias):
			result = result.relation
		return result
	
	relation = property(_get_relation)
	final_relation = property(_get_final_relation)


class Index(SchemaObject):
	"""Class representing an index"""

	config_names = ['index', 'indexes', 'indices']

	def __init__(self, schema, input, row):
		"""Initializes an instance of the class from a input row"""
		super(Index, self).__init__(schema, row.name, row.system, row.description)
		self._table_schema = row.table_schema
		self._table_name = row.table_name
		self.owner = row.owner
		self.created = row.created
		self.last_stats = row.last_stats
		self.cardinality = row.cardinality
		self.size = row.size
		self.unique = row.unique
		self._tablespace = row.tbspace
		self.fields = IndexFieldsDict(
			self.database, self._table_schema, self._table_name,
			input.index_cols.get((schema.name, self.name), [])
		)
		self.field_list = IndexFieldsList(
			self.database, self._table_schema, self._table_name,
			input.index_cols.get((schema.name, self.name), [])
		)

	def _get_identifier(self):
		return "index_%s_%s" % (self.schema.name, self.name)

	def _get_parent_list(self):
		return self.schema.index_list

	def _get_create_sql(self):
		ordering = {
			'A': '',
			'D': ' DESC',
		}
		fields = ', '.join((
			'%s%s' % (format_ident(field.name), ordering[order])
			for (field, order) in self.field_list
			if order != 'I'
		))
		sql = [
			'CREATE',
			['INDEX', 'UNIQUE INDEX'][self.unique],
			'%s.%s' % (format_ident(self.schema.name), format_ident(self.name)),
			'ON',
			'%s.%s' % (format_ident(self.table.schema.name), format_ident(self.table.name)),
			'(%s)' % fields
		]
		if self.unique:
			incfields = ', '.join((
				format_ident(field.name)
				for (field, order) in self.field_list
				if order == 'I'
			))
			if incfields:
				sql.append('INCLUDE (%s)' % incfields)
		return ' '.join(sql)

	def _get_drop_sql(self):
		return 'DROP INDEX %s.%s' % (
			format_ident(self.schema.name),
			format_ident(self.name)
		)

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

	config_names = ['trigger', 'triggers']

	def __init__(self, schema, input, row):
		"""Initializes an instance of the class from a input row"""
		super(Trigger, self).__init__(schema, row.name, row.system, row.description)
		self.owner = row.owner
		self.created = row.created
		self._relation_schema = row.relation_schema
		self._relation_name = row.relation_name
		self.trigger_time = row.when
		self.trigger_event = row.event
		self.granularity = row.granularity
		self.sql = row.sql
		self.dependencies = RelationsDict(
			self.database,
			input.trigger_dependencies.get((schema.name, self.name), [])
		)
		self.dependency_list = RelationsList(
			self.database,
			input.trigger_dependencies.get((schema.name, self.name), [])
		)

	def _get_identifier(self):
		return "trigger_%s_%s" % (self.schema.name, self.name)

	def _get_parent_list(self):
		return self.schema.trigger_list

	def _get_create_sql(self):
		return self.sql or ''

	def _get_drop_sql(self):
		return 'DROP TRIGGER %s.%s' % (
			format_ident(self.schema.name),
			format_ident(self.name),
		)

	def _get_relation(self):
		"""Returns the relation that the trigger applies to"""
		return self.database.schemas[self._relation_schema].relations[self._relation_name]

	relation = property(_get_relation)


class Function(Routine):
	"""Class representing a function"""

	config_names = ['function', 'functions', 'func', 'funcs']
	
	def __init__(self, schema, input, row):
		"""Initializes an instance of the class from a input row"""
		super(Function, self).__init__(schema, row.name, row.specific, row.system, row.description)
		self.owner = row.owner
		self.created = row.created
		self.type = row.func_type
		self.deterministic = row.deterministic
		self.external_action = row.ext_action
		self.null_call = row.null_call
		self.sql_access = row.access
		self.sql = row.sql
		self._param_list = [
			Param(self, input, pos, i)
			for (pos, i) in enumerate(input.routine_params.get((schema.name, self.specific_name), []))
			if i.direction != 'R'
		]
		self._params = dict((i.name, i) for i in self._param_list)
		self._return_list = [
			Param(self, input, pos, i)
			for (pos, i) in enumerate(input.routine_params.get((schema.name, self.specific_name), []))
			if i.direction == 'R'
		]
		self._returns = dict((i.name, i) for i in self._return_list)

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
			return ', '.join(('%s %s' % (format_ident(param.name), param.datatype_str) for param in params))

		def format_returns():
			if len(self.return_list) == 0:
				return ''
			elif self.type == 'R':
				return ' RETURNS ROW(%s)' % format_params(self.return_list)
			elif self.type == 'T':
				return ' RETURNS TABLE(%s)' % format_params(self.return_list)
			else:
				return ' RETURNS %s' % self.return_list[0].datatype_str

		return '%s.%s(%s)%s' % (
			format_ident(self.schema.name),
			format_ident(self.name),
			format_params(self.param_list),
			format_returns()
		)
	
	def _get_create_sql(self):
		# XXX Something more sophisticated here?
		return self.sql or ''
	
	def _get_drop_sql(self):
		return 'DROP SPECIFIC FUNCTION %s.%s' % (
			format_ident(self.schema.name),
			format_ident(self.specific_name)
		)


class Procedure(Routine):
	"""Class representing a procedure"""

	config_names = ['procedure', 'procedures', 'proc', 'procs']
	
	def __init__(self, schema, input, row):
		"""Initializes an instance of the class from a input row"""
		super(Procedure, self).__init__(schema, row.name, row.specific, row.system, row.description)
		self.owner = row.owner
		self.created = row.created
		self.deterministic = row.deterministic
		self.external_action = row.ext_action
		self.null_call = row.null_call
		self.sql_access = row.access
		self.sql = row.sql
		self._param_list = [
			Param(self, input, pos, i)
			for (pos, i) in enumerate(input.routine_params.get((schema.name, self.specific_name), []))
			if i.direction != 'R'
		]
		self._params = dict((i.name, i) for i in self._param_list)

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
			return ', '.join((
				'%s %s %s' % (parmtype[param.type], param.name, param.datatype_str)
				for param in params
			))

		return '%s.%s(%s)' % (
			format_ident(self.schema.name),
			format_ident(self.name),
			format_params(self.param_list)
		)
	
	def _get_create_sql(self):
		# XXX Something more sophisticated here?
		return self.sql or ''
	
	def _get_drop_sql(self):
		return 'DROP SPECIFIC PROCEDURE %s.%s' % (
			format_ident(self.schema.name),
			format_ident(self.specific_name)
		)


class Datatype(SchemaObject):
	"""Class representing a datatype"""

	config_names = ['datatype', 'datatypes', 'type', 'types']
	
	def __init__(self, schema, input, row):
		"""Initializes an instance of the class from a input row"""
		super(Datatype, self).__init__(schema, row.name, row.system, row.description)
		self.owner = row.owner
		self.created = row.created
		self.variable_size = row.variable_size
		self.variable_scale = row.variable_scale
		self._source_schema = row.source_schema
		self._source_name = row.source_name
		self.size = row.size
		self.scale = row.scale

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

	config_names = ['field', 'fields', 'column', 'columns', 'col', 'cols']

	def __init__(self, relation, input, position, row):
		"""Initializes an instance of the class from a input row"""
		# XXX DB2 specific assumption: some databases have system columns (e.g. OID)
		super(Field, self).__init__(relation, row.name, False, row.description)
		self._datatype_schema = row.type_schema
		self._datatype_name = row.type_name
		self.identity = row.identity
		self._size = row.size
		self._scale = row.scale
		self.codepage = row.codepage
		self.nullable = row.nullable
		self.cardinality = row.cardinality
		self.null_cardinality = row.null_card
		self.generated = row.generated
		self.default = row.default
		self.position = position

	def _get_identifier(self):
		return "field_%s_%s_%s" % (self.schema.name, self.relation.name, self.name)

	def _get_parent_list(self):
		return self.relation.field_list

	def _get_create_sql(self):
		if isinstance(self.relation, Table):
			return 'ALTER TABLE %s.%s ADD COLUMN %s' % (
				format_ident(self.relation.schema.name),
				format_ident(self.relation.name),
				self.prototype
			)
		else:
			return ''
	
	def _get_drop_sql(self):
		if isinstance(self.relation, Table):
			return 'ALTER TABLE %s.%s DROP COLUMN %s' % (
				format_ident(self.relation.schema.name),
				format_ident(self.relation.name),
				format_ident(self.name)
			)
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
				items.append('DEFAULT %s' % (self.default))
			else:
				items.append('GENERATED %s AS %s' % (
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
		if isinstance(self.relation, Table) and self.relation.primary_key and (self in self.relation.primary_key.fields):
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

	config_names = ['unique_key', 'unique_keys', 'uniquekey', 'uniquekeys',
		'unique', 'uniques']

	def __init__(self, table, input, row):
		"""Initializes an instance of the class from a input row"""
		super(UniqueKey, self).__init__(table, row.name, row.system, row.description)
		self.owner = row.owner
		self.created = row.created
		# XXX DB2 specific: should be provided by input plugin
		self._anonymous = re.match('^SQL\d{15}$', self.name)
		self._fields = ConstraintFieldsList(
			table,
			input.unique_key_cols.get((table.schema.name, table.name, self.name), [])
		)
		self.dependents = ConstraintsDict(
			self.database,
			[
				(fk.table_schema, fk.table_name, fk.name)
				for fk in input.parent_keys.get((table.schema.name, table.name, self.name), [])
			]
		)
		self.dependent_list = ConstraintsList(
			self.database,
			[
				(fk.table_schema, fk.table_name, fk.name)
				for fk in input.parent_keys.get((table.schema.name, table.name, self.name), [])
			]
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

	config_names = ['primary_key', 'primary_keys', 'primarykey', 'primarykeys',
		'primary', 'primaries', 'key', 'keys', 'pk', 'pks']

	def _get_prototype(self):
		sql = 'PRIMARY KEY (%s)' % ', '.join([format_ident(field.name) for field in self.fields])
		if not self._anonymous:
			sql = 'CONSTRAINT %s %s' % (self.name, sql)
		return sql


class ForeignKey(Constraint):
	"""Class representing a foreign key in a table"""

	config_names = ['foreign_key', 'foreign_keys', 'foreignkey', 'foreignkeys',
		'reference', 'references', 'fk', 'fks']

	def __init__(self, table, input, row):
		"""Initializes an instance of the class from a input row"""
		super(ForeignKey, self).__init__(table, row.name, row.system, row.description)
		self.owner = row.owner
		self.created = row.created
		self._ref_table_schema = row.const_schema
		self._ref_table_name = row.const_table
		self._ref_key_name = row.const_name
		self.delete_rule = row.delete_rule
		self.update_rule = row.update_rule
		# XXX DB2 specific: should be provided by input plugin
		self._anonymous = re.match('^SQL\d{15}$', self.name)
		self._fields = ForeignKeyFieldsList(
			table, self._ref_table_schema, self._ref_table_name,
			input.foreign_key_cols.get((table.schema.name, table.name, self.name), [])
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

	config_names = ['check', 'checks', 'ck', 'cks']

	def __init__(self, table, input, row):
		"""Initializes an instance of the class from a input row"""
		super(Check, self).__init__(table, row.name, row.system, row.description)
		self.owner = row.owner
		self.created = row.created
		self.expression = row.sql
		# XXX DB2 specific: should be provided by input plugin
		self._anonymous = re.match('^SQL\d{15}$', self.name)
		self._fields = ConstraintFieldsList(
			table,
			input.check_cols.get((table.schema.name, table.name, self.name), [])
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

	config_names = ['parameter', 'parameters', 'param', 'parameters',
		'parm', 'parms']

	def __init__(self, routine, input, position, row):
		"""Initializes an instance of the class from a input row"""
		# If the parameter is unnamed, make up a name based on the parameter's
		# position
		# XXX DB2 assumption? Is there such a thing as a "system-maintained
		# parameter" in any RDBMS?
		super(Param, self).__init__(routine, row.name or ('P%d' % position), False, row.description)
		self.type = row.direction
		self._datatype_schema = row.type_schema
		self._datatype_name = row.type_name
		self.size = row.size
		self.scale = row.scale
		self.codepage = row.codepage
		self.position = position

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
