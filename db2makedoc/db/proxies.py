# $Header$
# vim: set noet sw=4 ts=4:

from UserDict import DictMixin

class RelationsDict(object, DictMixin):
	"""Presents a dictionary of relations"""
	
	def __init__(self, database, relations):
		"""Initializes the dict from a list of (schema_name, relation_name) tuples"""
		if relations is None:
			relations = []
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
		if relations is None:
			relations = []
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
		if indexes is None:
			indexes = []
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
		if indexes is None:
			indexes = []
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

class TriggersDict(object, DictMixin):
	"""Presents a dictionary of triggers"""
	
	def __init__(self, database, triggers):
		"""Initializes the dict from a list of (schema_name, trigger_name) tuples"""
		if triggers is None:
			triggers = []
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
		if triggers is None:
			triggers = []
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
