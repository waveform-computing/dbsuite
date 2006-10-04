# $Header$
# vim: set noet sw=4 ts=4:

"""Defines all abstract base classes"""

class DocBase(object):
	"""Base class for all documented database objects"""

	def __init__(self, parent, name):
		"""Initializes an instance of the class"""
		super(DocBase, self).__init__()
		assert not parent or isinstance(parent, DocBase)
		self.parent = parent
		self.name = name
		self.type_name = 'Object'
		self.description = 'No description in the system catalog'
		self._system = False

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
		if self.parent: result = self.parent.qualified_name + "." + result
		return result

	def _get_system(self):
		"""Returns a bool indicating whether the object is system-defined.

		This property indicates whether an object is system-defined (true) or
		user defined (false). Any object which is directly or indirectly owned
		by a system-defined object is considered system-defined itself.
		"""
		return self._system or self.parent.system

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
		not be the exact statement that created the object, or even valid for
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
	
	# Use the lambda trick to make property getter methods "virtual"
	database = property(lambda self: self._get_database())
	parent = property(lambda self: self.getParent())
	parent_list = property(lambda self: self._get_parent_list())
	parent_index = property(lambda self: self._get_parent_index())
	identifier = property(lambda self: self._get_identifier())
	qualified_name = property(lambda self: self._get_qualified_name())
	system = property(lambda self: self._get_system())
	next = property(lambda self: self._get_next())
	prior = property(lambda self: self._get_prior())
	first = property(lambda self: self._get_first())
	last = property(lambda self: self._get_last())
	create_sql = property(lambda self: self._get_create_sql())
	drop_sql = property(lambda self: self._get_drop_sql())
