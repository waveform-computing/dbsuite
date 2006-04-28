#!/bin/env python
# $Header$
# vim: set noet sw=4 ts=4:

"""Input classes package.

Each module in this package supports a different kind of database. Currently
the following modules are provided:

Database Engine                         Module
-------------------------------------------------
IBM DB2 UDB for Linux/UNIX/Windows v8   db2udbluw
IBM DB2 UDB for z/OS v8                 db2udbzos


Each module is expected to export a class called Cache which, when constructed
with a database connection (conforming to the Python DB API) builds an object
containing a cache of the metadata from the database. The cache basically
contains dictionaries of dictionaries.

The unique identifer of an object (e.g. a schema and name for a table) forms
the key of the "outer" dictionary for each cache, while the contained
dictionaries are keyed by result-set fieldnames. This rather goes against the
Python ethos of not using dictionaries for database result sets, but tuples
are immutable and we need to convert some of the values (like timestamps).
It's also useful as it enables us to use the inner dictionaries as keyword
args when constructing objects later.

There are some exceptions to this dictionary of dictionaries structure - in
particular where "proxy" list/dict objects are used in the eventual object
hierarchy (in particular, see the cache for table dependencies, and the
indexes that apply to a given table).
"""

__all__ = [
	'db2udbluw',
]
