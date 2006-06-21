#!/bin/env python
# $Header$
# vim: set noet sw=4 ts=4:

from UserDict import DictMixin

class RelationsDict(object, DictMixin):
	"""Presents a dictionary of relations"""
	
	def __init__(self, database, relations):
		"""Initializes the dict from a list of (schemaName, relationName) tuples"""
		if relations is None:
			relations = []
		self.__database = database
		self.__keys = relations
		
	def keys(self):
		return self.__keys
	
	def has_key(self, key):
		return key in self.__keys
	
	def __len__(self):
		return len(self.__keys)
	
	def __getitem__(self, key):
		assert isinstance(key, tuple)
		(schemaName, relationName) = key
		return self.__database.schemas[schemaName].relations[relationName]
	
	def __iter__(self):
		for k in self.__keys:
			yield k
			
	def __contains__(self, key):
		return key in self.__keys

class RelationsList(object):
	"""Presents a list of relations"""
	
	def __init__(self, database, relations):
		"""Initializes the list from a list of (schemaName, relationName) tuples"""
		if relations is None:
			relations = []
		self.__database = database
		self.__items = relations
		
	def __len__(self):
		return len(self.__items)
	
	def __getitem__(self, key):
		assert isinstance(key, int)
		(schemaName, relationName) = self.__items[key]
		return self.__database.schemas[schemaName].relations[relationName]
	
	def __iter__(self):
		for (schemaName, relationName) in self.__items:
			yield self.__database.schemas[schemaName].relations[relationName]

	def __contains__(self, key):
		for i in self:
			if i == key:
				return True
		return False

class IndexesDict(object, DictMixin):
	"""Presents a dictionary of indexes"""
	
	def __init__(self, database, indexes):
		"""Initializes the dict from a list of (schemaName, indexName) tuples"""
		if indexes is None:
			indexes = []
		self.__database = database
		self.__keys = indexes

	def keys(self):
		return self.__keys
	
	def has_key(self, key):
		return key in self.__keys
	
	def __len__(self):
		return len(self.__keys)
	
	def __getitem__(self, key):
		assert isinstance(key, tuple)
		(schemaName, indexName) = key
		return self.__database.schemas[schemaName].indexes[indexName]
	
	def __iter__(self):
		for k in self.__keys:
			yield k
			
	def __contains__(self, key):
		return key in self.__keys

class IndexesList(object):
	"""Presents a list of indexes"""
	
	def __init__(self, database, indexes):
		"""Initializes the list from a list of (schemaName, indexName) tuples"""
		if indexes is None:
			indexes = []
		self.__database = database
		self.__items = indexes
	
	def __len__(self):
		return len(self.__items)
	
	def __getitem__(self, key):
		assert isinstance(key, int)
		(schemaName, indexName) = self.__items[key]
		return self.__database.schemas[schemaName].indexes[indexName]
	
	def __iter__(self):
		for (schemaName, indexName) in self.__items:
			yield self.__database.schemas[schemaName].indexes[indexName]
			
	def __contains__(self, key):
		for i in self:
			if i == key:
				return True
		return False

class TriggersDict(object, DictMixin):
	"""Presents a dictionary of triggers"""
	
	def __init__(self, database, triggers):
		"""Initializes the dict from a list of (schemaName, triggerName) tuples"""
		if triggers is None:
			triggers = []
		self.__database = database
		self.__keys = triggers

	def keys(self):
		return self.__keys
	
	def has_key(self, key):
		return key in self.__keys
	
	def __len__(self):
		return len(self.__keys)
	
	def __getitem__(self, key):
		assert isinstance(key, tuple)
		(schemaName, triggerName) = key
		return self.__database.schemas[schemaName].triggers[triggerName]
	
	def __iter__(self):
		for k in self.__keys:
			yield k
			
	def __contains__(self, key):
		return key in self.__keys

class TriggersList(object):
	"""Presents a list of triggers"""
	
	def __init__(self, database, triggers):
		"""Initializes the list from a list of (schemaName, triggerName) tuples"""
		if triggers is None:
			triggers = []
		self.__database = database
		self.__items = triggers
	
	def __len__(self):
		return len(self.__items)
	
	def __getitem__(self, key):
		assert isinstance(key, int)
		(schemaName, triggerName) = self.__items[key]
		return self.__database.schemas[schemaName].triggers[triggerName]
	
	def __iter__(self):
		for (schemaName, triggerName) in self.__items:
			yield self.__database.schemas[schemaName].triggers[triggerName]
			
	def __contains__(self, key):
		for i in self:
			if i == key:
				return True
		return False

def main():
	pass

if __name__ == "__main__":
	main()
