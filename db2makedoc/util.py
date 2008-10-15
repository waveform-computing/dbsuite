# vim: set noet sw=4 ts=4:

"""Defines general utility methods and functions.

This module backports some built-in functions from later Python versions, in
particular the any() and all() functions from Python 2.5 and namedtuple() from
Python 2.6, and defines some useful generic recipes.
"""

import sys
import types

__all__ = []


# all() and any() recipes
if sys.hexversion < 0x02050000:
	__all__.append('all')
	def all(iterable):
		for element in iterable:
			if not element:
				return False
		return True

	__all__.append('any')
	def any(iterable):
		for element in iterable:
			if element:
				return True
		return False


__all__.append('attrgetter')
__all__.append('itemgetter')
# multiple item extraction in itemgetter and attrgetter
if sys.hexversion < 0x02050000:
	def attrgetter(*attrs):
		if len(attrs) == 0:
			raise TypeError('attrgetter expected 1 arguments, got 0')
		elif len(attrs) == 1:
			attr = attrs[0]
			def getter(obj):
				return getattr(obj, attr)
		else:
			def getter(obj):
				return tuple(getattr(obj, attr) for attr in attrs)
		return getter

	def itemgetter(*items):
		if len(items) == 0:
			raise TypeError('itemgetter expected 1 arguments, got 0')
		elif len(items) == 1:
			item = items[0]
			def getter(obj):
				return obj[item]
		else:
			def getter(obj):
				return tuple(obj[item] for item in items)
		return getter
else:
	from operator import itemgetter, attrgetter


# Named tuple recipe (http://code.activestate.com/recipes/500261/)
__all__.append('namedtuple')
if sys.hexversion < 0x02060000:
	from operator import itemgetter as _itemgetter
	from keyword import iskeyword as _iskeyword
	import sys as _sys

	def namedtuple(typename, field_names, verbose=False):
		"""Returns a new subclass of tuple with named fields.

		>>> Point = namedtuple('Point', 'x y')
		>>> Point.__doc__                   # docstring for the new class
		'Point(x, y)'
		>>> p = Point(11, y=22)             # instantiate with positional args or keywords
		>>> p[0] + p[1]                     # indexable like a plain tuple
		33
		>>> x, y = p                        # unpack like a regular tuple
		>>> x, y
		(11, 22)
		>>> p.x + p.y                       # fields also accessable by name
		33
		>>> d = p._asdict()                 # convert to a dictionary
		>>> d['x']
		11
		>>> Point(**d)                      # convert from a dictionary
		Point(x=11, y=22)
		>>> p._replace(x=100)               # _replace() is like str.replace() but targets named fields
		Point(x=100, y=22)

		"""

		# Parse and validate the field names.  Validation serves two purposes,
		# generating informative error messages and preventing template injection attacks.
		if isinstance(field_names, basestring):
			field_names = field_names.replace(',', ' ').split() # names separated by whitespace and/or commas
		field_names = tuple(map(str, field_names))
		for name in (typename,) + field_names:
			if not min(c.isalnum() or c=='_' for c in name):
				raise ValueError('Type names and field names can only contain alphanumeric characters and underscores: %r' % name)
			if _iskeyword(name):
				raise ValueError('Type names and field names cannot be a keyword: %r' % name)
			if name[0].isdigit():
				raise ValueError('Type names and field names cannot start with a number: %r' % name)
		seen_names = set()
		for name in field_names:
			if name.startswith('_'):
				raise ValueError('Field names cannot start with an underscore: %r' % name)
			if name in seen_names:
				raise ValueError('Encountered duplicate field name: %r' % name)
			seen_names.add(name)

		# Create and fill-in the class template
		numfields = len(field_names)
		argtxt = repr(field_names).replace("'", "")[1:-1]   # tuple repr without parens or quotes
		reprtxt = ', '.join('%s=%%r' % name for name in field_names)
		dicttxt = ', '.join('%r: t[%d]' % (name, pos) for pos, name in enumerate(field_names))
		template = '''\
class %(typename)s(tuple):
	'%(typename)s(%(argtxt)s)' \n
	__slots__ = () \n
	_fields = %(field_names)r \n
	def __new__(cls, %(argtxt)s):
		return tuple.__new__(cls, (%(argtxt)s)) \n
	@classmethod
	def _make(cls, iterable, new=tuple.__new__, len=len):
		'Make a new %(typename)s object from a sequence or iterable'
		result = new(cls, iterable)
		if len(result) != %(numfields)d:
			raise TypeError('Expected %(numfields)d arguments, got %%d' %% len(result))
		return result \n
	def __repr__(self):
		return '%(typename)s(%(reprtxt)s)' %% self \n
	def _asdict(t):
		'Return a new dict which maps field names to their values'
		return {%(dicttxt)s} \n
	def _replace(self, **kwds):
		'Return a new %(typename)s object replacing specified fields with new values'
		result = self._make(map(kwds.pop, %(field_names)r, self))
		if kwds:
			raise ValueError('Got unexpected field names: %%r' %% kwds.keys())
		return result \n\n''' % locals()
		for i, name in enumerate(field_names):
			template += '	%s = property(itemgetter(%d))\n' % (name, i)
		if verbose:
			print template

		# Execute the template string in a temporary namespace
		namespace = dict(itemgetter=_itemgetter)
		try:
			exec template in namespace
		except SyntaxError, e:
			raise SyntaxError(e.message + ':\n' + template)
		result = namespace[typename]

		# For pickling to work, the __module__ variable needs to be set to the frame
		# where the named tuple is created.  Bypass this step in enviroments where
		# sys._getframe is not defined (Jython for example).
		if hasattr(_sys, '_getframe') and _sys.platform != 'cli':
			result.__module__ = _sys._getframe(1).f_globals['__name__']

		return result
else:
	from collections import namedtuple


def namedslice(cls, obj):
	"""Copies values from obj into the namedtuple class cls by field name.

	Given a namedtuple object in obj, and a namedtuple class in cls, this
	function returns a namedtuple of type cls with values taken from obj.  This
	is useful when dealing with namedtuple types which are based partly on
	other namedtuple types, for example:

		>>> nt1 = namedtuple('nt1', ('field1', 'field2'))
		>>> nt2 = namedtuple('nt2', ('field3', 'field4'))
		>>> nt3 = namedtuple('nt3', nt1._fields + nt2._fields)
		>>> nt3._fields
		('field1', 'field2', 'field3', 'field4')
		>>> obj = nt3(1, 2, 3, 4)
		>>> namedslice(nt1, obj)
		nt1(field1=1, field2=2)
		>>> obj = nt2(3, 4)
		>>> namedslice(nt3, obj)
		nt3(field1=None, field2=None, field3=3, field4=4)

	Note that it doesn't matter if the target type has a different number of
	fields to the source object. Fields which exist in the source object but
	not the target class will simply be ommitted in the result, while fields
	which exist in the target class but not the source object will be None in
	the result.
	"""
	assert isinstance(obj, tuple)
	assert issubclass(cls, tuple)
	assert hasattr(obj, '_fields')
	assert hasattr(cls, '_fields')
	return cls(*(getattr(obj, attr, None) for attr in cls._fields))


# Caching decorator
__all__.append('cached')
class cached(property):
	"""Convert a method into a cached property"""

	def __init__(self, method):
		private = '_' + method.__name__
		def fget(s):
			try:
				return getattr(s, private)
			except AttributeError:
				value = method(s)
				setattr(s, private, value)
				return value
		super(cached, self).__init__(fget)
