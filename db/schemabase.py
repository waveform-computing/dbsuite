# $Header$
# vim: set noet sw=4 ts=4:

# Application-specific modules
from db.base import DocBase

class SchemaObject(DocBase):
	"""Base class for database objects that belong directly to a schema"""

	def __init__(self, parent, name):
		"""Initializes an instance of the class"""
		super(SchemaObject, self).__init__(parent, name)
		self.schema = parent
	
	def _get_database(self):
		return self.parent.parent
	
class Relation(SchemaObject):
	"""Base class for relations that belong in a schema (e.g. tables, views, etc.)"""

	def __init__(self, parent, name):
		"""Initializes an instance of the class"""
		super(Relation, self).__init__(parent, name)
		self.type_name = 'Relation'
	
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
		return self.schema.relationList

	# Use the lambda trick to allow property getter methods to be overridden
	dependents = property(lambda self: self._get_dependents())
	dependent_list = property(lambda self: self._get_dependent_list())
	fields = property(lambda self: self._get_fields())
	field_list = property(lambda self: self._get_field_list())

class Routine(SchemaObject):
	"""Base class for routines that belong in a schema (functions, procedures, etc.)"""

	def __init__(self, parent, name, specific_name):
		super(Routine, self).__init__(parent, name)
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
	
	# Use the lambda trick to allow property getter methods to be overridden
	params = property(lambda self: self._get_params())
	param_list = property(lambda self: self._get_param_list())
	returns = property(lambda self: self._get_returns())
	return_list = property(lambda self: self._get_return_list())
	prototype = property(lambda self: self._get_prototype())
