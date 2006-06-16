#!/bin/env python
# $Header$
# vim: set noet sw=4 ts=4:

"""Defines all abstract base classes"""

class DocBase(object):
	"""Base class for all documented database objects"""

	def __init__(self, parent, name):
		"""Initializes an instance of the class"""
		super(DocBase, self).__init__()
		assert not parent or isinstance(parent, DocBase)
		self.__parent = parent
		self.__name = name

	def getDatabase(self):
		raise NotImplementedError
	
	def getParent(self):
		return self.__parent
	
	def getParentList(self):
		return None

	def getParentIndex(self):
		if self.parentList is None:
			raise NotImplementedError
		else:
			return self.parentList.index(self)
	
	def getName(self):
		return self.__name
	
	def getTypeName(self):
		return "Object"
	
	def getDescription(self):
		return "No description in the system catalog"
	
	def getIdentifier(self):
		return id(self)

	def getQualifiedName(self):
		result = self.name
		if self.parent: result = self.parent.qualifiedName + "." + result
		return result

	def getSystem(self):
		if not self.parent is None:
			return self.parent.isSystemObject()
		else:
			return False

	def getNext(self):
		if self.parentList is None:
			return None
		try:
			return self.parentList[self.parentIndex + 1]
		except IndexError:
			return None

	def getPrior(self):
		if self.parentList is None:
			return None
		try:
			if self.parentIndex > 0:
				return self.parentList[self.parentIndex - 1]
			else:
				return None
		except IndexError:
			return None

	def getFirst(self):
		if self.parentList is None:
			return None
		try:
			return self.parentList[0]
		except IndexError:
			return None
	
	def getLast(self):
		if self.parentList is None:
			return None
		try:
			return self.parentList[-1]
		except IndexError:
			return None

	def getCreateSql(self):
		raise NotImplementedError

	def getDropSql(self):
		raise NotImplementedError

	def __str__(self):
		"""Return a string representation of the object"""
		return self.qualifiedName
	
	# Use the lambda trick to make property getter methods "virtual"
	database = property(lambda self: self.getDatabase(), doc="""The database that owns the object (the root of the hierarchy)""")
	parent = property(lambda self: self.getParent(), doc="""Returns the parent database object (e.g. the parent of a table is a schema)""")
	parentList = property(lambda self: self.getParentList(), doc="""Returns the list containing objects of the same type with the same parent, or None if the object is standalone""")
	parentIndex = property(lambda self: self.getParentIndex(), doc="""Returns the index of this object within the parentList""")
	identifier = property(lambda self: self.getIdentifier(), doc="""Returns a unique identifier for this object (suitable for use as the basis for a unique filename, for example)""")
	name = property(lambda self: self.getName(), doc="""Returns the unqualified name of the database object""")
	qualifiedName = property(lambda self: self.getQualifiedName(), doc="""Returns the fully qualified name of the database object""")
	typeName = property(lambda self: self.getTypeName(), doc="""Returns the human readable name of the object's type""")
	description = property(lambda self: self.getDescription(), doc="""Returns a brief description of the object""")
	system = property(lambda self: self.getSystem(), doc="""True if the object is a system-defined object""")
	next = property(lambda self: self.getNext(), doc="""Returns the next object of the same type with the same parent, or None if this is the last such object""")
	prior = property(lambda self: self.getPrior(), doc="""Returns the previous object of the same type with the same parent, or None if this is the first such object""")
	first = property(lambda self: self.getFirst(), doc="""Returns the first object of the same type with the same parent, or None""")
	last = property(lambda self: self.getLast(), doc="""Returns the last object of the same type with the same parent, or None""")
	createSql = property(lambda self: self.getCreateSql(), doc="""The SQL that can be used to create the object""")
	dropSql = property(lambda self: self.getDropSql(), doc="""The SQL that can be used to drop the object""")

def main():
	pass

if __name__ == "__main__":
	main()
