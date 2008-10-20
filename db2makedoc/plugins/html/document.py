# vim: set noet sw=4 ts=4:

"""Provides a set of base classes for HTML based output plugins.

This package defines a set of utility classes which make it easier to construct
output plugins capable of producing HTML documents (or, more precisely, a
website containing HTML documents amongst other things).
"""

import os
import codecs
import re
import datetime
import logging
import urlparse
import threading
import time

from db2makedoc.highlighters import CommentHighlighter, SQLHighlighter
from db2makedoc.plugins.html.entities import HTML_ENTITIES
from db2makedoc.graph import Graph, Node, Edge, Cluster
from db2makedoc.db import (
	DatabaseObject, Relation, Routine, Constraint, Database, Tablespace,
	Schema, Table, View, Alias, Index, Trigger, Function, Procedure, Datatype,
	Field, UniqueKey, PrimaryKey, ForeignKey, Check, Param
)
from db2makedoc.etree import (
	fromstring, tostring, iselement, Element, Comment, flatten_html
)
from db2makedoc.sql.formatter import (
	ERROR, COMMENT, KEYWORD, IDENTIFIER, LABEL, DATATYPE, REGISTER,
	NUMBER, STRING, OPERATOR, PARAMETER, TERMINATOR, STATEMENT
)

# Import the CSSUtils API
# XXX Unneeded until we actually start work on the CSSDocument class
#try:
#	import cssutils
#except ImportError:
#	raise ImportError('Unable to find a CSS Utils implementation')

# Import the xapian bindings
try:
	import xapian
except ImportError:
	# Ignore any import errors - the main plugin takes care of warning the user
	# if xapian is required but not present
	pass

# Import the fastest StringIO implementation
try:
	from cStringIO import StringIO
except ImportError:
	try:
		from StringIO import StringIO
	except ImportError:
		raise ImportError('Unable to find a StringIO implementation')

# Determine the path containing this module (used for locating external source
# files like CSS and JavaScript below)
_my_path = os.path.dirname(os.path.abspath(__file__))


# Constants for HTML versions
(
	HTML4,   # HTML 4.01
	XHTML10, # XHTML 1.0
	XHTML11, # XHTML 1.1 (modular XHTML)
) = range(3)

# Constants for HTML style
(
	STRICT,       # Strict DTD
	TRANSITIONAL, # Transitional DTD
	FRAMESET,     # Frameset DTD
) = range(3)


class Attrs(dict):
	"""A dictionary with special behaviours for HTML attributes.

	Changes from the default dict type are as follows:

	The + operator can be used to combine an Attrs instance with another dict
	instance. The + operator is non-commutative with dictionaries in that, if a
	key exists in both dictionaries on either side of the operator, the value
	of the key in the dictionary on the right "wins". The augmented assignment
	operation += is also supported.

	In the operation a + b, the result (a new dictionary) contains the keys and
	values of a, updated with the keys and values of b. Neither a nor b is
	actually updated. If a is an instance of Attrs, the result of a + b is an
	instance of Attrs.  If a is an instance of dict, while b is an instance of
	Attrs, the result of a + b is an instance of dict.

	Certain values are treated specially. Setting a key to None removes the key
	from the dictionary. Setting a key to a boolean False value does likewise,
	while boolean True results in the key being associated with its name (as in
	checked='checked'). All values are converted to strings (for compatibility
	with ElementTree).

	Finally, underscore suffixes are automatically stripped from key names.
	This is to enable easy declaration of attribute names which conflict with
	Python keywords using the factory facilities of the HTMLDocument class
	below.
	"""

	def __init__(self, source=None, **kwargs):
		if source is not None and isinstance(source, dict):
			self.update(source)
		self.update(kwargs)

	def __add__(self, other):
		result = Attrs(self)
		result.update(other)
		return result

	def __radd__(self, other):
		result = dict(other)
		result.update(self)
		return result

	def __iadd__(self, other):
		self.update(other)

	def __setitem__(self, key, value):
		if value is None:
			if key in self:
				del self[key]
		elif isinstance(value, bool):
			if value:
				super(Attrs, self).__setitem__(key, key)
			elif key in self:
				del self[key]
		else:
			# Try to use ASCII encodings when possible (for performance)
			try:
				super(Attrs, self).__setitem__(key.rstrip('_'), str(value))
			except UnicodeEncodeError:
				super(Attrs, self).__setitem__(key.rstrip('_'), unicode(value))

	def update(self, source):
		for key, value in source.iteritems():
			self[key] = value


class ElementFactory(object):
	"""A class inspired by Genshi for easy creation of ElementTree Elements.

	The ElementFactory class should rarely be used directly. Instead, use the
	"tag" object which is an instance of ElementFactory. The ElementFactory
	class was inspired by the genshi builder unit in that it permits simple
	creation of Elements by calling methods on the tag object named after the
	element you wish to create. Positional arguments become content within the
	element, and keyword arguments become attributes.

	If you need an attribute or element tag that conflicts with a Python
	keyword, simply append an underscore to the name (which will be
	automatically stripped off).

	Content can be just about anything, including booleans, integers, longs,
	dates, times, etc. These types are all converted to strings in a manner
	suitable for use in generating human-readable documentation (though not
	necessarily machine-reading friendly), e.g. datetime values are
	automatically converted to an ISO8601 string representation, which integers
	are converted to strings containing thousand separators.

	For example:

	>>> tostring(tag.a('A link'))
	'<a>A link</a>'
	>>> tostring(tag.a('A link', class_='menuitem'))
	'<a class="menuitem">A link</a>'
	>>> tostring(tag.p('A ', tag.a('link', class_='menuitem')))
	'<p>A <a class="menuitem">link</a></p>'
	"""

	def _find(self, root, tagname, id=None):
		"""Returns the first element with the specified tagname and id"""
		if id is None:
			result = root.find('.//%s' % tagname)
			if result is None:
				raise Exception('Cannot find any %s elements' % tagname)
			else:
				return result
		else:
			result = [
				elem for elem in root.findall('.//%s' % tagname)
				if elem.attrib.get('id', '') == id
			]
			if len(result) == 0:
				raise Exception('Cannot find a %s element with id %s' % (tagname, id))
			elif len(result) > 1:
				raise Exception('Found multiple %s elements with id %s' % (tagname, id))
			else:
				return result[0]

	def _format(self, content):
		"""Reformats content into a human-readable string"""
		if content is None:
			# Format None as 'n/a'
			return 'n/a'
		elif isinstance(content, datetime.time):
			# Format times as ISO8601
			return content.strftime('%H:%M:%S')
		elif isinstance(content, datetime.date):
			# Format dates as ISO8601 (dates < 1970 can't be formatted, so treat them as None)
			if content.year < 1970:
				return self._format(None)
			else:
				return content.strftime('%Y-%m-%d')
		elif isinstance(content, datetime.datetime):
			# Format timestamps as ISO8601 (dates < 1970 can't be formatted, so treat them as None)
			if content.year < 1970:
				return self._format(None)
			else:
				return content.strftime('%Y-%m-%d %H:%M:%S')
		elif isinstance(content, bool):
			# Format booleans as Yes/No
			return ['No', 'Yes'][content]
		elif isinstance(content, (int, long)):
			# Format integer number with , as a thousand separator
			s = str(content)
			for i in xrange(len(s) - 3, 0, -3): s = '%s,%s' % (s[:i], s[i:])
			return s
		elif isinstance(content, basestring):
			# Strings are returned verbatim
			return content
		else:
			# Everything else is converted to an ASCII string
			return str(content)

	def _append(self, node, content):
		"""Adds content (string, node, node-list, etc.) to a node"""
		if isinstance(content, basestring):
			if content != '':
				if not isinstance(content, unicode):
					content = content.decode()
				if len(node) == 0:
					if node.text is None:
						node.text = content
					else:
						node.text += content
				else:
					if node[-1].tail is None:
						node[-1].tail = content
					else:
						node[-1].tail += content
		elif iselement(content):
			node.append(content)
		else:
			try:
				for n in iter(content):
					self._append(node, n)
			except TypeError:
				self._append(node, self._format(content))

	def _element(self, _name, *content, **attrs):
		if attrs:
			attrs = Attrs(attrs)
		e = Element(_name, attrs)
		self._append(e, content)
		return e

	def __getattr__(self, name):
		def generator(*content, **attrs):
			return self._element(name.rstrip('_'), *content, **attrs)
		return generator

	def script(self, *content, **attrs):
		# XXX Workaround: the script element cannot be "empty" (IE fucks up)
		if not content: content = (' ',)
		# If type isn't specified, default to 'text/javascript'
		attrs = Attrs(attrs)
		if not 'type' in attrs:
			attrs['type'] = 'text/javascript'
		return self._element('script', *content, **attrs)

	def style(self, *content, **attrs):
		# Default type is 'text/css', and media is 'screen'
		attrs = Attrs(attrs)
		if not 'type' in attrs:
			attrs['type'] = 'text/css'
		if not 'media' in attrs:
			attrs['media'] = 'screen'
		# If there's no content, and src is set, return a <link> element instead
		if not content and 'src' in attrs:
			attrs['rel'] = 'stylesheet'
			attrs['href'] = attrs['src']
			del attrs['src']
			return self._element('link', **attrs)
		else:
			return self._element('style', *content, **attrs)

tag = ElementFactory()


class HTMLCommentHighlighter(CommentHighlighter):
	"""Class which converts simple comment markup into HTML.

	This subclass of the generic comment highlighter class overrides the stub
	methods to convert the comment into HTML. The construction of the HTML
	elements is actually handled by the methods of the HTMLDocument object
	passed to the constructor as opposed to the methods in this class.
	"""

	def __init__(self, site):
		"""Initializes an instance of the class."""
		super(HTMLCommentHighlighter, self).__init__()
		assert isinstance(site, WebSite)
		self.site = site

	def handle_strong(self, text):
		"""Highlights strong text with HTML <strong> elements."""
		return tag.strong(text)

	def handle_emphasize(self, text):
		"""Highlights emphasized text with HTML <em> elements."""
		return tag.em(text)

	def handle_underline(self, text):
		"""Highlights underlined text with HTML <u> elements."""
		return tag.u(text)

	def start_para(self, summary):
		"""Emits an empty string for the start of a paragraph."""
		return ''

	def end_para(self, summary):
		"""Emits an HTML <br>eak element for the end of a paragraph."""
		return tag.br()

	def handle_link(self, target):
		"""Emits an HTML <a>nchor element linking to the object's documentation."""
		# If the target is something we don't generate a document for (like
		# a column), scan upwards in the hierarchy until we find a document
		# and return a link to that document with the in between objects added
		# as normal text suffixes
		return self.site.link_to(target, parent=True)

	def find_target(self, name):
		"""Searches the site's associated database for the named object."""
		return self.site.database.find(name)


class HTMLSQLHighlighter(SQLHighlighter):
	"""Class which marks up SQL with HTML.

	This subclass of the generic SQL highlighter class overrides the stub
	methods to markup the SQL with HTML <span> elements. The css_classes
	attribute determines the CSS classes which are attached to the <span>
	elements.

	When operating in line_split mode, the result is a sequence of <li>
	elements containing the <span> elements.

	The construction of the HTML elements is actually handled by the methods of
	the HTMLDocument object passed to the constructor.
	"""

	def __init__(self):
		"""Initializes an instance of the class."""
		super(HTMLSQLHighlighter, self).__init__()
		self.css_classes = {
			ERROR:      'sql-error',
			COMMENT:    'sql-comment',
			KEYWORD:    'sql-keyword',
			IDENTIFIER: 'sql-identifier',
			LABEL:      'sql-label',
			DATATYPE:   'sql-datatype',
			REGISTER:   'sql-register',
			NUMBER:     'sql-number',
			STRING:     'sql-string',
			OPERATOR:   'sql-operator',
			PARAMETER:  'sql-parameter',
			TERMINATOR: 'sql-terminator',
			STATEMENT:  'sql-terminator',
		}

	def format_token(self, token):
		(token_type, token_value, source, _, _) = token
		try:
			css_class = self.css_classes[(token_type, token_value)]
		except KeyError:
			css_class = self.css_classes.get(token_type, None)
		# XXX Disgusting hack because IE's too thick to handle pre-formatted
		# whitespace in anything except <pre>
		source = re.sub(' {2,}', lambda m: u'\u00A0' * len(m.group()), source)
		if css_class is not None:
			return tag.span(source, class_=css_class)
		else:
			return source

	def format_line(self, index, line):
		return tag.li(self.format_token(token) for token in line)


class WebSite(object):
	"""Represents a collection of HTML documents (a website).

	This is the base class for a related collection of HTML documents,such as a
	website. It mainly exists to provide attributes which apply to all HTML
	documents in the collection (like author, site title, copyright, and such
	like).
	"""

	def __init__(self, database, options):
		"""Initializes an instance of the class."""
		assert isinstance(database, Database)
		super(WebSite, self).__init__()
		self.database = database
		self.htmlver = XHTML10
		self.htmlstyle = STRICT
		self.base_url = ''
		self.base_path = options['path']
		self.home_url = options['home_url']
		self.home_title = options['home_title']
		self.icon_url = options['icon_url']
		self.icon_type = options['icon_type']
		self.keywords = [self.database.name]
		self.author_name = options['author_name']
		self.author_email = options['author_email']
		self.top = options['top']
		self.date = datetime.datetime.today()
		self.lang, self.sublang = options['lang']
		self.copyright = options['copyright']
		self.encoding = options['encoding']
		self.search = options['search']
		self.threads = options['threads']
		self.title = options['site_title']
		self.diagrams = bool(options['diagrams'])
		if self.title is None:
			self.title = '%s Documentation' % self.database.name
		self.type_names = {
			Alias:          'Alias',
			Check:          'Check Constraint',
			Constraint:     'Constraint',
			Database:       'Database',
			DatabaseObject: 'Object',
			Datatype:       'Data Type',
			Field:          'Field',
			ForeignKey:     'Foreign Key',
			Function:       'Function',
			Index:          'Index',
			Param:          'Parameter',
			PrimaryKey:     'Primary Key',
			Procedure:      'Procedure',
			Relation:       'Relation',
			Routine:        'Routine',
			Schema:         'Schema',
			Tablespace:     'Tablespace',
			Table:          'Table',
			Trigger:        'Trigger',
			UniqueKey:      'Unique Key',
			View:           'View',
		}
		self.default_desc = 'No description in the system catalog'
		self.urls = {}
		self.stylesheets = []
		self.scripts = []
		self.object_docs = {}
		self.object_graphs = {}
		self.tbspace_list = options['tbspace_list']
		# If indexes are requested, build the sorted object lists now (and set
		# up the first level of the index_docs mapping)
		self.first_index = None
		self.index_maps = {}
		self.index_docs = {}
		if options['indexes']:
			for cls in options['indexes']:
				self.index_maps[cls] = {}
				self.index_docs[cls] = {}
			self.database.touch(self.index_object, options['indexes'])

	def index_object(self, dbobject, dbclasses):
		"""Adds a database object to the relevant index lists.

		This is a utility method called for each object in the database
		hierarchy. If the object is an instance of any class in dbclasses, it
		is added to an index list (index lists are keyed by database class and
		initial letter). Note that the lists are not sorted here (or even in
		the caller) - it is up to index documents to sort these lists (which
		allows for multiple index documents to reference the same index list
		and sort it in different ways).
		"""
		for cls in dbclasses:
			if isinstance(dbobject, cls):
				letter = dbobject.name[:1]
				if letter in self.index_maps[cls]:
					self.index_maps[cls][letter].append(dbobject)
				else:
					self.index_maps[cls][letter] = [dbobject]

	def add_document(self, document):
		"""Adds a document to the website.

		This method adds a document to the website, and updates several data
		structures which track the associations between database objects and
		documents / graphs. The base implementation here permits a database
		object to be associated with a single document and a single graph.
		Descendents may override this method (and the object_document() and
		object_graph() methods) if more complex associations are desired (e.g.
		framed and non-framed versions of documents).
		"""
		assert isinstance(document, WebSiteDocument)
		self.urls[document.url] = document
		self.urls[document.absolute_url] = document
		if isinstance(document, HTMLObjectDocument):
			self.object_docs[document.dbobject] = document
		elif isinstance(document, GraphObjectDocument):
			self.object_graphs[document.dbobject] = document
		elif isinstance(document, HTMLIndexDocument):
			self.index_docs[document.dbclass][document.letter] = document
		elif isinstance(document, CSSDocument):
			self.stylesheets.append(document)
		elif isinstance(document, JavaScriptDocument):
			self.scripts.append(document)

	def url_document(self, url):
		"""Returns the WebSiteDocument associated with a given URL.

		This method returns the document with the specified URL (or None if no
		such URL exists in the site).
		"""
		return self.urls.get(url)

	def index_document(self, dbclass, letter=None, *args, **kwargs):
		"""Returns the HTMLDocument which indexes a particular database class.

		This methods returns a single HTMLDocument which contains an index for
		the specified database class (e.g. tables), if one exists (if one does
		not exist, the result is None).

		If the optional letter parameter is provided, and an index for the
		specific letter of the database class can be found, it will be
		returned. Otherwise, the first index (in alphabetical terms) for the
		class will be returned.

		The args and kwargs parameters capture any extra criteria that should
		be used to select between documents in the case that an index is
		represented by multiple documents (e.g. framed and unframed versions).
		"""
		assert issubclass(dbclass, DatabaseObject)
		if letter:
			try:
				return self.index_docs[dbclass][letter]
			except KeyError:
				return None
		else:
			docs = self.index_docs.get(dbclass)
			if docs:
				return docs[sorted(docs.keys())[0]]
			else:
				return None

	def object_document(self, dbobject, *args, **kwargs):
		"""Returns the HTMLDocument associated with a database object.

		This method returns a single HTMLDocument which is associated with the
		specified database object (dbobject). If the specified object has no
		associated HTMLDocument object, the method returns None.

		Descendents may override this method to alter the way database objects
		are associated with GraphDocuments.

		The args and kwargs parameters capture any extra criteria that should
		be used to select between documents in the case that a database object
		is represented by multiple documents (e.g. framed and unframed
		versions).  They correspond to the args and kwargs parameters of the
		link_to() method.
		"""
		assert isinstance(dbobject, DatabaseObject)
		return self.object_docs.get(dbobject)

	def object_graph(self, dbobject, *args, **kwargs):
		"""Returns the GraphDocument associated with a database object.

		This method returns a single GraphDocument which is associated with the
		specified database object (dbobject). If the specified objcet has no
		associated GraphDocument object, the method returns None.

		Descendents may override this method to alter the way database objects
		are associated with GraphDocuments.

		The args and kwargs parameters capture any extra criteria that should
		be used to select between graphs in the case that a database object is
		represented by multiple graphs (e.g. relational integrity versus
		functional dependencies).  They correspond to the args and kwargs
		parameters of the img_of() method.
		"""
		assert isinstance(dbobject, DatabaseObject)
		return self.object_graphs.get(dbobject)

	def link_to(self, dbobject, parent=False, *args, **kwargs):
		"""Returns a link to a document representing the specified database object.

		Given a database object, this method returns the Element(s) required to
		link to an HTMLDocument representing that object. The link will include
		the object's fully qualified name.

		If the specified object is not associated with any HTMLDocument, the
		parent parameter determines the result. If parent is False (the
		default), the method returns the text that the link would have
		contained (according to the typename and qualifiedname parameters).
		Otherwise, the method searches the object's parents for an associated
		document, returning a link to the first documented parent found.

		The args and kwargs parameters permit additional arguments to be
		relayed to the object_document() method in case the site implements
		multiple documents per object (e.g. framed and non-framed versions).
		"""
		assert isinstance(dbobject, DatabaseObject)
		doc = self.object_document(dbobject, *args, **kwargs)
		if doc:
			assert isinstance(doc, HTMLDocument)
			return tag.a(dbobject.qualified_name, href=doc.url, title=doc.title)
		elif parent:
			suffixes = []
			target = dbobject
			while doc is None:
				suffixes.insert(0, target.name)
				target = target.parent
				doc = self.object_document(target, *args, **kwargs)
				if isinstance(target, Database):
					target = None
					break
			return [
				self.link_to(target, False, *args, **kwargs),
				''.join(['.' + s for s in suffixes]),
			]
		else:
			return dbobject.qualified_name

	def img_of(self, dbobject, *args, **kwargs):
		"""Returns a link to a graph representing the specified database object.

		Given a database object, this method returns the Element(s) required to
		link to a GraphDocument representing that object.

		The args and kwargs parameters permit additional arguments to be
		relayed to the object_document() method in case the site implements
		multiple graphs per object.

		If the specified object is not associated with any GraphDocument, the
		method returns some text indicating that no graph is available.
		"""
		assert isinstance(dbobject, DatabaseObject)
		graph = self.object_graph(dbobject, *args, **kwargs)
		if graph is None:
			return tag.p('Graph for %s is not available' % dbobject.qualified_name)
		else:
			assert isinstance(graph, GraphDocument)
			return graph.link()

	def index_of(self, dbclass, letter=None, *args, **kwargs):
		"""Returns a link to an index of objects of the specified class.

		Given a database class (Table, Relation, etc.), this method returns
		the Element(s) required to link to the alphabetical index of objects
		of that class.

		If the letter parameter is ommitted, the link will be to the first
		letter of the index. The args and kwargs parameters permit additional
		arguments to be relayed to the index_document() method in case the site
		implements multiple indexes per class.

		If the specified class does not have an associated index, the method
		returns some text indicating that no index is available.
		"""
		assert issubclass(dbclass, DatabaseObject)
		doc = self.index_document(dbclass, letter, *args, **kwargs)
		if doc is None:
			return tag.p('%s index is not available' % self.type_names[dbclass])
		elif letter is None:
			return doc.link()
		else:
			return tag.a(letter, href=doc.url, title=doc.title)

	def link_indexes(self):
		"""Utility method for linking letters of indexes together.

		This method is called during write() to generate the first, prior,
		next, last, and parent links of the index documents. Normally, this
		sort of thing would be done in the generate() method of the document in
		question. However, it's much more efficient to do this at the site
		level for the index documents as we can sort the list of documents by
		letter once, and apply the links from the result.

		In this method, we also generate a bunch of "fake" documents
		representing each index. The HTMLExternalDocument class is used for
		this, and each "fake" document actually points to the document for the
		first letter of the index. These documents are used to provide another
		level of structure to the document hierarchy, which groups together
		each index letter document, e.g.:

		Database Document
		+- Table Index (fake)
		|  +- A
		|  +- B
		|  +- C
		|  +- D
		|  +- ...
		+- View Index (fake)
		   +- A
		   +- B
		   +- ...

		Override this in descendents if the index_docs structure is changed or
		enhanced.
		"""
		# Sort the list of database classes by name and filter out those which have
		# no index content
		dbclasses = [
			dbclass for dbclass in sorted(self.index_docs.iterkeys(),
				key=lambda dbclass: self.type_names[dbclass])
			if self.index_docs[dbclass]
		]
		# Create "fake" documents to represent each index. Note that the URL
		# constructed here is ultimately discarded, but must still be unique
		# (see below)
		dbclass_docs = [
			HTMLExternalDocument(self,
				'indexof_%s.html' % dbclass.config_names[0],
				'%s Index' % self.type_names[dbclass]
			)
			for dbclass in dbclasses
		]
		self.first_index = dbclass_docs[0]
		dbclass_parent = self.object_document(self.database)
		dbclass_prior = None
		for (dbclass, dbclass_doc) in zip(dbclasses, dbclass_docs):
			letter_docs = sorted(self.index_docs[dbclass].itervalues(), key=lambda doc: doc.letter)
			if letter_docs:
				# Replace the URL of the class document with the URL of the
				# first letter of the index. We can't do this at construction
				# time or the fake document will supplant the real document
				# (for the first letter) in the site's structures.
				dbclass_doc.url = letter_docs[0].url
				dbclass_doc.first = dbclass_docs[0]
				dbclass_doc.last = dbclass_docs[-1]
				dbclass_doc.parent = dbclass_parent
				dbclass_doc.prior = dbclass_prior
				dbclass_prior = dbclass_doc
				letter_prior = None
				for letter_doc in letter_docs:
					letter_doc.first = letter_docs[0]
					letter_doc.last = letter_docs[-1]
					letter_doc.parent = dbclass_doc
					letter_doc.prior = letter_prior
					letter_prior = letter_doc

	def write(self):
		"""Writes all documents in the site to disk."""
		if self.index_docs:
			self.link_indexes()
		if self.threads == 1:
			if self.diagrams:
				logging.info('Writing documents and graphs')
			else:
				logging.info('Writing documents')
			self.write_single(self.urls.itervalues())
		else:
			# Writing documents with multiple threads is split into two phases:
			# writing graphs, and writing non-graphs. This avoids a race
			# condition; in plugins which automatically resize large diagrams,
			# writing an HTMLDocument that references a GraphDocument can cause
			# the GraphDocument to be written in order to determine its size.
			# If another thread starts writing the same GraphDocument
			# simultaneously two threads wind up trying to write to the same
			# file
			if self.diagrams:
				logging.info('Writing graphs')
				self.write_multi(
					doc for doc in self.urls.itervalues()
					if isinstance(doc, GraphDocument)
				)
			logging.info('Writing documents')
			self.write_multi(
				doc for doc in self.urls.itervalues()
				if not isinstance(doc, GraphDocument)
			)
		if self.search:
			# Write all full-text-search documents to a new xapian database
			# in a single transaction
			logging.info('Writing search database')
			db = xapian.WritableDatabase(os.path.join(self.base_path, 'search'),
				xapian.DB_CREATE_OR_OVERWRITE)
			db.begin_transaction()
			try:
				for doc in self.urls.itervalues():
					if isinstance(doc, HTMLDocument) and doc.ftsdoc:
						db.add_document(doc.ftsdoc)
				db.commit_transaction()
			except:
				db.cancel_transaction()
				raise

	def reset_progress(self, total):
		self.start_progress = datetime.datetime.now()
		self.total_remaining = total
		self.last_progress = self.start_progress
		logging.info('%d documents remaining' % total)

	def write_progress(self, remaining):
		interval = 60
		if (datetime.datetime.now() - self.last_progress).seconds >= interval:
			elapsed = (datetime.datetime.now() - self.start_progress).seconds
			rate = (self.total_remaining - remaining) / float(elapsed)
			eta = datetime.timedelta(seconds=int(remaining / rate))
			logging.info('%d documents remaining, ETA %s @ %.2f docs/sec' % (remaining, eta, rate))
			self.last_progress = datetime.datetime.now()

	def write_single(self, docs):
		"""Single-threaded document writer method."""
		logging.debug('Single-threaded writer')
		docs = set(docs)
		self.reset_progress(len(docs))
		while docs:
			self.write_progress(len(docs))
			docs.pop().write()

	def write_multi(self, docs):
		"""Multi-threaded document writer method.

		This method sets up several parallel threads to handle writing
		documents. The documents to be written are stored in a set (to ensure
		that if documents are registered multiple times they are still only
		written once). The method terminates when all documents have been
		written. The number of parallel threads is controlled by the "threads"
		configuration value.
		"""
		logging.debug('Multi-threaded writer with %d threads' % self.threads)
		self._documents_set = set(docs)
		self.reset_progress(len(self._documents_set))
		# Create and start all the writing threads
		threads = [
			(i, threading.Thread(target=self.__thread_write, args=()))
			for i in range(self.threads)
		]
		for (i, thread) in threads:
			logging.debug('Starting writer thread #%d' % i)
			thread.start()
		# Join (wait on termination of) all writing threads
		while threads:
			(i, thread) = threads.pop()
			while thread.is_alive():
				self.write_progress(len(self._documents_set))
				thread.join(10.0)
			logging.debug('Writer thread #%d finished' % i)

	def __thread_write(self):
		"""Sub-routine for writing documents.

		This method runs in a separate thread and simply pops a document to
		be written from the internal stack and writes it. The thread terminates
		when no more documents remain in the stack.
		"""
		while self._documents_set:
			self._documents_set.pop().write()


class WebSiteDocument(object):
	"""Represents a document in a website (e.g. HTML, CSS, image, etc.)"""

	def __init__(self, site, url, filename=None):
		"""Initializes an instance of the class."""
		assert isinstance(site, WebSite)
		super(WebSiteDocument, self).__init__()
		self.site = site
		self.url = url
		self.absolute_url = urlparse.urljoin(self.site.base_url, url)
		if filename is None:
			parts = [self.site.base_path]
			parts.extend(self.url.split('/'))
			self.filename = os.path.join(*parts)
		else:
			self.filename = filename
		self.site.add_document(self)

	def write(self):
		"""Writes this document to a file in the site's path.

		Derived classes should override this method to write the content of the
		document to the file specified by the instance's filename property.  If
		writing a text-based format, remember to encode the output with the
		encoding specified by the owning site object.
		"""
		logging.debug('Writing %s' % self.filename)

	def link(self, *args, **kwargs):
		"""Returns the Element(s) required to link to the document.

		Derived classes should override this method to produce the Element(s)
		required to link to this document. In the case of an HTML document,
		this is likely to be an <a>nchor, while a graphic might produce an
		<img> element, and a stylesheet a <link> element. The default
		implementation here simply returns the url as a link.

		The args and kwargs parameters capture additional information for the
		generation of the link. For example, in the case of a stylesheet a
		media parameter might be included.
		"""
		return tag.a(self.url, href=self.url)


class HTMLDocument(WebSiteDocument):
	"""Represents a simple HTML document.

	This is the base class for HTML documents. It provides several utility
	methods for constructing HTML elements, formatting content, and writing out
	the final HTML document. Construction of HTML elements is handled by the
	ElementTree API.
	"""

	def __init__(self, site, url, filename=None):
		super(HTMLDocument, self).__init__(site, url, filename)
		self.ftsdoc = None
		self.title = ''
		self.description = ''
		self.keywords = []
		self.author_name = site.author_name
		self.author_email = site.author_email
		self.icon_url = site.icon_url
		self.icon_type = site.icon_type
		self.date = site.date
		self.lang = site.lang
		self.sublang = site.sublang
		self.copyright = site.copyright
		self.search = site.search
		self.robots_index = True
		self.robots_follow = True
		self.comment_highlighter = HTMLCommentHighlighter(self.site)
		self.sql_highlighter = HTMLSQLHighlighter()
		self._first = None
		self._prior = None
		self._next = None
		self._last = None
		self._parent = None

	def _get_first(self):
		return self._first
	def _set_first(self, value):
		assert (value is None) or isinstance(value, HTMLDocument)
		self._first = value

	def _get_prior(self):
		return self._prior
	def _set_prior(self, value):
		assert (value is None) or isinstance(value, HTMLDocument)
		assert not value is self
		if self._prior:
			self._prior._next = None
		self._prior = value
		if value:
			value._next = self

	def _get_next(self):
		return self._next
	def _set_next(self, value):
		assert (value is None) or isinstance(value, HTMLDocument)
		assert not value is self
		if self._next:
			self._next._prior =None
		self._next = value
		if value:
			value._prior = self

	def _get_last(self):
		return self._last
	def _set_last(self, value):
		assert (value is None) or isinstance(value, HTMLDocument)
		self._last = value

	def _get_parent(self):
		return self._parent
	def _set_parent(self, value):
		assert (value is None) or isinstance(value, HTMLDocument)
		assert not value is self
		self._parent = value

	def _get_level(self):
		result = 0
		item = self
		while item.parent:
			result += 1
			item = item.parent
		return result

	first = property(lambda self: self._get_first(), lambda self, value: self._set_first(value))
	prior = property(lambda self: self._get_prior(), lambda self, value: self._set_prior(value))
	next = property(lambda self: self._get_next(), lambda self, value: self._set_next(value))
	last = property(lambda self: self._get_last(), lambda self, value: self._set_last(value))
	parent = property(lambda self: self._get_parent(), lambda self, value: self._set_parent(value))
	level = property(_get_level)

	def write(self):
		super(HTMLDocument, self).write()
		doc = self.generate()
		# If full-text-searching is enabled, set up a Xapian indexer and
		# stemmer and fill out the ftsdoc. The site class handles writing all
		# the ftsdoc's to the xapian database once all writing is finished
		if self.search:
			logging.debug('Indexing %s' % self.filename)
			indexer = xapian.TermGenerator()
			# XXX Seems to be a bug in xapian 1.0.2 which causes a segfault
			# with this enabled
			#indexer.set_flags(xapian.TermGenerator.FLAG_SPELLING)
			indexer.set_stemmer(xapian.Stem(self.lang))
			self.ftsdoc = xapian.Document()
			self.ftsdoc.set_data('\n'.join([
				self.url,
				self.title or self.url,
				self.description or self.title or self.url,
			]))
			indexer.set_document(self.ftsdoc)
			indexer.index_text(self.flatten(doc))
		# Finally, write the output to the destination file
		f = open(self.filename, 'w')
		try:
			f.write(self.serialize(doc))
		finally:
			f.close()

	# Regex which finds characters within the range of characters capable of
	# being encoded as HTML entities
	entitiesre = re.compile(u'[%s-%s]' % (
		unichr(min(HTML_ENTITIES.iterkeys())),
		unichr(max(HTML_ENTITIES.iterkeys()))
	))

	def serialize(self, content):
		"""Converts the document into a string for writing."""
		# "Pure" XML won't handle HTML character entities. So we do it
		# manually. First, get the XML as a Unicode string (without any XML
		# PI or DOCTYPE)
		if self.site.htmlver >= XHTML10:
			content.attrib['xmlns'] = 'http://www.w3.org/1999/xhtml'
		s = unicode(tostring(content))
		# Convert any characters into HTML entities that can be
		def subfunc(match):
			if ord(match.group()) in HTML_ENTITIES:
				return u'&%s;' % HTML_ENTITIES[ord(match.group())]
			else:
				return match.group()
		s = self.entitiesre.sub(subfunc, s)
		# Insert an XML PI at the start reflecting the target encoding (and
		# a DOCTYPE as ElementTree doesn't handle this for us directly)
		try:
			(public_id, system_id) = {
				(HTML4, STRICT):         ('-//W3C//DTD HTML 4.01//EN', 'http://www.w3.org/TR/html4/strict.dtd'),
				(HTML4, TRANSITIONAL):   ('-//W3C//DTD HTML 4.01 Transitional//EN', 'http://www.w3.org/TR/html4/loose.dtd'),
				(HTML4, FRAMESET):       ('-//W3C//DTD HTML 4.01 Frameset//EN', 'http://www.w3.org/TR/html4/frameset.dtd'),
				(XHTML10, STRICT):       ('-//W3C//DTD XHTML 1.0 Strict//EN', 'http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd'),
				(XHTML10, TRANSITIONAL): ('-//W3C//DTD XHTML 1.0 Transitional//EN', 'http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd'),
				(XHTML10, FRAMESET):     ('-//W3C//DTD XHTML 1.0 Frameset//EN', 'http://www.w3.org/TR/xhtml1/DTD/xhtml1-frameset.dtd'),
				(XHTML11, STRICT):       ('-//W3C//DTD XHTML 1.1//EN', 'xhtml11-flat.dtd'),
			}[(self.site.htmlver, self.site.htmlstyle)]
		except KeyError:
			raise KeyError('Invalid HTML version and style (XHTML11 only supports the STRICT style)')
		s = u"""\
<?xml version="1.0" encoding="%(encoding)s"?>
<!DOCTYPE html
  PUBLIC "%(publicid)s"
  "%(systemid)s">
%(content)s""" % {
			'encoding': self.site.encoding,
			'publicid': public_id,
			'systemid': system_id,
			'content': s,
		}
		# Transcode the document into the target encoding
		return s.encode(self.site.encoding)

	def flatten(self, content):
		"""Converts the document into pure text for full-text indexing."""
		# This base implementation simply flattens the content of the HTML body
		# node. Descendents may override this to refine the output (e.g. to exclude
		# common headings and other items essentially useless for searching)
		return flatten_html(content.find('body'))

	def generate(self):
		"""Called by write() to generate the document as an ElementTree."""
		# Override this in descendent classes to include additional content
		# Add some standard <meta> elements (encoding, keywords, author, robots
		# info, Dublin Core stuff, etc.)
		content = [
			tag.meta(name='Robots', content=','.join([
				'%sindex'  % ['no', ''][bool(self.robots_index)],
				'%sfollow' % ['no', ''][bool(self.robots_follow)],
			])),
			tag.meta(name='DC.Date', content=self.date, scheme='iso8601'),
			tag.meta(name='DC.Language', content='%s-%s' % (self.lang, self.sublang), scheme='rfc1766'),
		]
		if self.copyright is not None:
			content.append(tag.meta(name='DC.Rights', content=self.copyright))
		if self.description is not None:
			content.append(tag.meta(name='Description', content=self.description))
		if len(self.keywords) > 0:
			content.append(tag.meta(name='Keywords', content=', '.join(self.keywords)))
		if self.author_email is not None:
			content.append(tag.meta(name='Owner', content=self.author_email))
			content.append(tag.meta(name='Feedback', content=self.author_email))
			content.append(tag.link(rel='author', href='mailto:%s' % self.author_email, title=self.author_name))
		# Add some navigation <link> elements
		content.append(tag.link(rel='home', href=self.site.home_url))
		if self.first:
			content.append(tag.link(rel='first', href=self.first.url))
		if self.prior:
			content.append(tag.link(rel='prev', href=self.prior.url))
		if self.next:
			content.append(tag.link(rel='next', href=self.next.url))
		if self.last:
			content.append(tag.link(rel='last', href=self.last.url))
		if self.parent:
			content.append(tag.link(rel='up', href=self.parent.url))
		# Add <link> elements for the favicon
		if self.icon_url:
			content.append(tag.link(rel='icon', href=self.icon_url, type=self.icon_type))
			content.append(tag.link(rel='shortcut icon', href=self.icon_url, type=self.icon_type))
		# Add the title
		if self.title is not None:
			content.append(tag.title('%s - %s' % (self.site.title, self.title)))
		# Create the <head> element with the above content, and an empty <body>
		# element
		return tag.html(tag.head(content), tag.body())

	def format_comment(self, comment, summary=False):
		return self.comment_highlighter.parse(comment or self.site.default_desc, summary)

	def format_sql(self, sql, terminator=';', number_lines=False, id=None):
		tokens = self.sql_highlighter.parse(sql, terminator, line_split=number_lines)
		if number_lines:
			return tag.ol(tokens, class_='sql', id=id)
		else:
			return tag.pre(tokens, class_='sql', id=id)

	def format_prototype(self, sql):
		return tag.code(self.sql_highlighter.parse_prototype(sql), class_='sql')

	def link(self, *args, **kwargs):
		return tag.a(self.title, href=self.url, title=self.title)


class HTMLExternalDocument(HTMLDocument):
	"""Document class representing an external document.

	This class is used to represent HTML documents which are not generated by
	db2makedoc (whether on the local web server or elsewhere). The write()
	method of this class is overridden to do nothing. Instances of this class
	primarily serve as the target of other document's links.

	Note that the filename parameter to the constructor is replaced by title
	(there's no point having a filename for a document we'll never write to
	after all!).
	"""

	def __init__(self, site, url, title):
		super(HTMLExternalDocument, self).__init__(site, url, '')
		self.title = title

	def write(self):
		# Overridden to do nothing
		pass


class HTMLIndexDocument(HTMLDocument):
	"""Document class representing an alphabetical index of objects."""

	def __init__(self, site, dbclass, letter):
		assert dbclass in site.index_maps
		assert letter in site.index_maps[dbclass]
		# Set dbclass and letter before calling the inherited method so that
		# site.add_document knows what to do with us
		self.dbclass = dbclass
		self.letter = letter
		# If the letter isn't a simple ASCII alphanumeric character, use the
		# hex value of the character in the URL (which becomes the filename),
		# in case the character is either illegal for the underlying FS (e.g.
		# backslash on Windows), or the FS doesn't support Unicode (e.g. some
		# older UNIX FSs)
		if letter == '':
			url = 'indexof_%s_empty.html' % dbclass.config_names[0]
		elif re.match('[a-zA-Z0-9]', letter):
			url = 'indexof_%s_%s.html' % (dbclass.config_names[0], letter)
		else:
			url = 'indexof_%s_%s.html' % (dbclass.config_names[0], hex(ord(letter)))
		super(HTMLIndexDocument, self).__init__(site, url)
		self.title = '%s Index' % self.site.type_names[dbclass]
		self.description = self.title
		self.search = False
		self.items = site.index_maps[dbclass][letter]


class HTMLObjectDocument(HTMLDocument):
	"""Document class representing a database object (schema, table, etc.)"""

	def __init__(self, site, dbobject):
		# Set dbobject before calling the inherited method to ensure that
		# site.add_document knows what object we represent
		self.dbobject = dbobject
		# Override the identifier for the top-level document
		if isinstance(dbobject, Database):
			ident = site.top or dbobject.identifier
		else:
			ident = dbobject.identifier
		super(HTMLObjectDocument, self).__init__(site, '%s.html' % ident)
		self.title = '%s %s' % (
			self.site.type_names[self.dbobject.__class__],
			self.dbobject.qualified_name
		)
		self.description = self.dbobject.description or self.title
		self.keywords = [
			self.site.database.name,
			self.site.type_names[self.dbobject.__class__],
			self.dbobject.name,
			self.dbobject.qualified_name
		]

	def _get_first(self):
		result = super(HTMLObjectDocument, self)._get_first()
		if not result and self.dbobject.first:
			return self.site.object_document(self.dbobject.first)
		else:
			return result

	def _get_prior(self):
		result = super(HTMLObjectDocument, self)._get_prior()
		if not result and self.dbobject.prior:
			return self.site.object_document(self.dbobject.prior)
		else:
			return result

	def _get_next(self):
		result = super(HTMLObjectDocument, self)._get_next()
		if not result and self.dbobject.next:
			return self.site.object_document(self.dbobject.next)
		else:
			return result

	def _get_last(self):
		result = super(HTMLObjectDocument, self)._get_last()
		if not result and self.dbobject.last:
			return self.site.object_document(self.dbobject.last)
		else:
			return result

	def _get_parent(self):
		result = super(HTMLObjectDocument, self)._get_parent()
		if not result and self.dbobject.parent:
			return self.site.object_document(self.dbobject.parent)
		else:
			return result


class CSSDocument(WebSiteDocument):
	"""Represents a simple CSS document.

	This is the base class for CSS stylesheets. It provides no methods for
	constructing or editing CSS; simply override the generate() method to
	return the CSS to write to the file.
	"""

	def __init__(self, site, url, filename=None, media='all'):
		super(CSSDocument, self).__init__(site, url, filename)
		self.media = media

	def write(self):
		super(CSSDocument, self).write()
		f = open(self.filename, 'w')
		try:
			f.write(self.serialize(self.generate()))
		finally:
			f.close()

	def serialize(self, content):
		"""Converts the document into a string for writing."""
		return content.encode(self.site.encoding)

	def generate(self):
		"""Constructs the content of the stylesheet."""
		# Child classes can override this to build the stylesheet
		return u''

	def link(self, *args, **kwargs):
		# Overridden to return a <link> to the stylesheet (the tag
		# ElementFactory takes care of converting <style> into <link> when
		# there's no content, and src is specified)
		return tag.style(src=self.url, media=self.media)


class SQLCSSDocument(CSSDocument):
	"""Stylesheet class for SQL syntax highlighting."""

	sql_css = codecs.open(os.path.join(_my_path, 'sql.css'), 'r', 'UTF-8').read()

	def __init__(self, site):
		super(SQLCSSDocument, self).__init__(site, 'sql.css')

	def generate(self):
		doc = super(SQLCSSDocument, self).generate()
		return doc + self.sql_css


class JavaScriptDocument(WebSiteDocument):
	"""Represents a simple JavaScript document.

	This is the base class for JavaScript libraries. It provides no methods for
	constructing or editing JavaScript; simply override the generate() method
	to return the JavaScript to write to the file.
	"""

	def write(self):
		super(JavaScriptDocument, self).write()
		f = open(self.filename, 'w')
		try:
			f.write(self.serialize(self.generate()))
		finally:
			f.close()

	def serialize(self, content):
		"""Converts the document into a string for writing."""
		return content.encode(self.site.encoding)

	def generate(self):
		"""Constructs the content of the JavaScript library."""
		# Child classes can override this to build the script
		return u''

	def link(self, *args, **kwargs):
		# Overridden to return a <script> element
		return tag.script(src=self.url)


class ImageDocument(WebSiteDocument):
	"""Represents a static image.

	This is the base class for static images. It provides no methods for
	constructing or editing images; simply override the generate() method to
	return the image data to write to the file.
	"""

	def write(self):
		super(ImageDocument, self).write()
		f = open(self.filename, 'wb')
		try:
			f.write(self.generate())
		finally:
			f.close()

	def generate(self):
		"""Constructs the content of the image."""
		# Child class can override this to build the image (or simply read it from a source file)
		return ''

	def link(self, *args, **kwargs):
		# Overridden to return an <img> element
		return tag.img(src=self.url)


class GraphDocument(WebSiteDocument):
	"""Represents a graph in GraphViz dot language.

	This is the base class for dot graphs. It provides a doc attribute which is
	a Graph object from the dot.graph module included with the application.
	This (and the associated Node, Edge, Cluster and Subgraph classes) provide
	rudimentary editing facilities for constructor dot graphs.
	"""

	def __init__(self, site, url):
		super(GraphDocument, self).__init__(site, url)
		self.graph = Graph('G')
		self.graph.rankdir = 'LR'
		self.graph.dpi = '96'
		# PNGs and GIFs use a client-side image-map to define link locations
		# (SVGs just use embedded links)
		self.usemap = os.path.splitext(self.filename)[1].lower() in ('.png', '.gif')
		# generated is a latch to ensure generate() isn't performed
		# more than once when dealing with image maps (which have to run
		# through graphviz twice, once for the image, once for the map)
		self.generated = False

	def write(self):
		"""Writes this document to a file in the site's path"""
		super(GraphDocument, self).write()
		# Generate the graph if it hasn't been already
		if not self.generated:
			g = self.generate()
			g.touch(self.style)
		else:
			g = self.graph
		# The following lookup tables are used to decide on the method used to
		# write output based on the extension of the image filename
		method_lookup = {
			'.png': g.to_png,
			'.gif': g.to_gif,
			'.svg': g.to_svg,
			'.ps':  g.to_ps,
			'.eps': g.to_ps,
		}
		ext = os.path.splitext(self.filename)[1].lower()
		try:
			method = method_lookup[ext]
		except KeyError:
			raise Exception('Unknown image extension "%s"' % ext)
		f = open(self.filename, 'wb')
		try:
			method(f)
		finally:
			f.close()

	def generate(self):
		"""Constructs the content of the graph."""
		self.generated = True
		return self.graph

	def style(self, node):
		"""Applies common styles to graph objects."""
		# Override this in descendents to change common graph styles
		if isinstance(node, (Node, Edge)):
			node.fontname = 'Verdana'
			node.fontsize = 8.0
		elif isinstance(node, Cluster):
			node.fontname = 'Verdana'
			node.fontsize = 10.0

	def link(self, *args, **kwargs):
		if self.usemap:
			# If the graph uses a client side image map for links a bit
			# more work is required. We need to get the graph to generate
			# the <map> doc, then import all elements from that
			map = self.map()
			img = tag.img(src=self.url, usemap='#' + map.attrib['id'])
			return [img, map]
		else:
			return tag.img(src=self.url)

	def map(self):
		"""Returns an Element containing the client-side image map."""
		assert self.usemap
		if not self.generated:
			g = self.generate()
			g.touch(self.style)
		else:
			g = self.graph
		f = StringIO()
		try:
			g.to_map(f)
			result = fromstring(f.getvalue())
			result.attrib['id'] = self.url.rsplit('.', 1)[0] + '.map'
			result.attrib['name'] = result.attrib['id']
			return result
		finally:
			f.close()


class GraphObjectDocument(GraphDocument):
	"""Graph class representing a database object (schema, table, etc.)"""

	def __init__(self, site, dbobject):
		"""Initializes an instance of the class."""
		self.dbobject = dbobject # must be set before calling the inherited method
		super(GraphObjectDocument, self).__init__(site, '%s.png' % dbobject.identifier)
		self.dbobjects = {}

	def style(self, node):
		# Overridden to add URLs to graph items representing database objects,
		# and to apply common styles for database objects
		super(GraphObjectDocument, self).style(node)
		if hasattr(node, 'dbobject'):
			doc = self.site.object_document(node.dbobject)
			if isinstance(node, (Node, Edge, Cluster)) and doc:
				node.URL = doc.url
			if isinstance(node.dbobject, Schema):
				node.style = 'filled'
				node.fillcolor = '#ece6d7'
				node.color = '#ece6d7'
			elif isinstance(node.dbobject, Relation):
				node.shape = 'rectangle'
				node.style = 'filled'
				if isinstance(node.dbobject, Table):
					node.fillcolor = '#bbbbff'
				elif isinstance(node.dbobject, View):
					node.style = 'filled,rounded'
					node.fillcolor = '#bbffbb'
				elif isinstance(node.dbobject, Alias):
					if isinstance(node.dbobject.final_relation, View):
						node.style = 'filled,rounded'
					node.fillcolor = '#ffffbb'
				node.color = '#000000'
			elif isinstance(node.dbobject, Trigger):
				node.shape = 'hexagon'
				node.style = 'filled'
				node.fillcolor = '#ffbbbb'
		if hasattr(node, 'selected') and node.selected:
			styles = node.style.split(',')
			styles.append('setlinewidth(3)')
			node.style = ','.join(styles)

	def add(self, dbobject, selected=False):
		"""Utility method to add a database object to the graph.

		This utility method adds the specified database object along with
		standardized formatting depending on the type of the object.
		Descendents should override this method if they wish to tweak the
		styling or add support for additional object types.
		"""
		assert isinstance(dbobject, DatabaseObject)
		o = self.dbobjects.get(dbobject)
		if o is None:
			if isinstance(dbobject, Schema):
				o = Cluster(self.graph, dbobject.qualified_name)
				o.label = dbobject.name
			elif isinstance(dbobject, (Relation, Trigger)):
				cluster = self.add(dbobject.schema)
				o = Node(cluster, dbobject.qualified_name)
				o.label = dbobject.name
			o.selected = selected
			o.dbobject = dbobject
			self.dbobjects[dbobject] = o
		return o

