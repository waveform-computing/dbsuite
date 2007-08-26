# $Header$
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

from db2makedoc.db import DatabaseObject, Database
from db2makedoc.highlighters import CommentHighlighter, SQLHighlighter
from db2makedoc.plugins.html.entities import HTML_ENTITIES
from db2makedoc.sql.formatter import (
	ERROR,
	COMMENT,
	KEYWORD,
	IDENTIFIER,
	DATATYPE,
	REGISTER,
	NUMBER,
	STRING,
	OPERATOR,
	PARAMETER,
	TERMINATOR,
	STATEMENT
)

# Import the GraphViz API
from db2makedoc.graph import Graph, Node, Edge, Cluster

# Import the ElementTree API, favouring the faster cElementTree implementation
try:
	from xml.etree.cElementTree import fromstring, tostring, iselement, Element, Comment
except ImportError:
	try:
		from cElementTree import fromstring, tostring, iselement, Element, Comment
	except ImportError:
		try:
			from xml.etree.ElementTree import fromstring, tostring, iselement, Element, Comment
		except ImportError:
			try:
				from elementtree.ElementTree import fromstring, tostring, iselement, Element, Comment
			except ImportError:
				raise ImportError('Unable to find an ElementTree implementation')

# Import the CSSUtils API
try:
	import cssutils
except ImportError:
	raise ImportError('Unable to find a CSS Utils implementation')

# Import the fastest StringIO implementation
try:
	from cStringIO import StringIO
except ImportError:
	try:
		from StringIO import StringIO
	except ImportError:
		raise ImportError('Unable to find a StringIO implementation')


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


class AttrDict(dict):
	"""A dictionary which supports the + operator for combining two dictionaries.
	
	The + operator is non-commutative with dictionaries in that, if a key
	exists in both dictionaries on either side of the operator, the value of
	the key in the dictionary on the right "wins". The augmented assignment
	operation += is also supported.

	In the operation a + b, the result (a new dictionary) contains the keys and
	values of a, updated with the keys and values of b. Neither a nor b is
	actually updated.
	
	If a is an instance of AttrDict, the result of a + b is an instance of
	AttrDict.  If a is an instance of dict, while b is an instance of AttrDict,
	the result of a + b is an instance of dict.
	"""
	
	def __add__(self, other):
		result = AttrDict(self)
		result.update(other)
		return result

	def __radd__(self, other):
		result = dict(other)
		result.update(self)
		return result

	def __iadd__(self, other):
		self.update(other)


class HTMLCommentHighlighter(CommentHighlighter):
	"""Class which converts simple comment markup into HTML.

	This subclass of the generic comment highlighter class overrides the stub
	methods to convert the comment into HTML. The construction of the HTML
	elements is actually handled by the methods of the HTMLDocument object
	passed to the constructor as opposed to the methods in this class.
	"""

	def __init__(self, document):
		"""Initializes an instance of the class."""
		assert isinstance(document, HTMLDocument)
		super(HTMLCommentHighlighter, self).__init__()
		self.document = document

	def handle_strong(self, text):
		"""Highlights strong text with HTML <strong> elements."""
		return self.document._strong(text)

	def handle_emphasize(self, text):
		"""Highlights emphasized text with HTML <em> elements."""
		return self.document._em(text)

	def handle_underline(self, text):
		"""Highlights underlined text with HTML <u> elements."""
		return self.document._u(text)

	def start_para(self, summary):
		"""Emits an empty string for the start of a paragraph."""
		return ''

	def end_para(self, summary):
		"""Emits an HTML <br>eak element for the end of a paragraph."""
		return self.document._br()

	def handle_link(self, target):
		"""Emits an HTML <a>nchor element linking to the object's documentation."""
		# If the target is something we don't generate a document for (like
		# a column), scan upwards in the hierarchy until we find a document
		# and return a link to that document with the in between objects added
		# as normal text suffixes
		suffixes = []
		while self.document.site.object_document(target) is None:
			suffixes.insert(0, target.name)
			target = target.parent
			if isinstance(target, Database):
				return '.'.join(suffixes)
		return [
			self.document._a_to(target, qualifiedname=True),
			''.join(['.' + s for s in suffixes]),
		]

	def find_target(self, name):
		"""Searches the site's associated database for the named object."""
		return self.document.site.database.find(name)


class HTMLSQLHighlighter(SQLHighlighter):
	"""Class which marks up SQL with HTML.

	This subclass of the generic SQL highlighter class overrides the stub
	methods to markup the SQL with HTML <span> elements. The css_classes
	attribute determines the CSS classes which are attached to the <span>
	elements.

	If the number_lines attribute is True (it is False by default) then lines
	will be output as <tr> elements with two columns - the left containing the
	line number. In this case the number_class attribute specifies the class of
	the left column, and the sql_class attribute specifies the class of the
	right column.

	The construction of the HTML elements is actually handled by the methods of
	the HTMLDocument object passed to the constructor.
	"""

	def __init__(self, document):
		"""Initializes an instance of the class."""
		assert isinstance(document, HTMLDocument)
		super(HTMLSQLHighlighter, self).__init__()
		self.document = document
		self.css_classes = {
			ERROR:      'sql_error',
			COMMENT:    'sql_comment',
			KEYWORD:    'sql_keyword',
			IDENTIFIER: 'sql_identifier',
			DATATYPE:   'sql_datatype',
			REGISTER:   'sql_register',
			NUMBER:     'sql_number',
			STRING:     'sql_string',
			OPERATOR:   'sql_operator',
			PARAMETER:  'sql_parameter',
			TERMINATOR: 'sql_terminator',
			STATEMENT:  'sql_terminator',
		}
		self.number_lines = False
		self.number_class = 'num_cell'
		self.sql_class = 'sql_cell'

	def format_token(self, token):
		(token_type, token_value, source, _, _) = token
		try:
			css_class = self.css_classes[(token_type, token_value)]
		except KeyError:
			css_class = self.css_classes.get(token_type, None)
		if css_class is not None:
			return self.document._span(source, {'class': css_class})
		else:
			return source

	def format_line(self, index, line):
		if self.number_lines:
			return self.document._tr([
				(index, {'class': self.number_class}),
				([self.format_token(token) for token in line], {'class': self.sql_class})
			])
		else:
			return [self.format_token(token) for token in line]


class WebSite(object):
	"""Represents a collection of HTML documents (a website).

	This is the base class for a related collection of HTML documents,such as a
	website. It mainly exists to provide attributes which apply to all HTML
	documents in the collection (like author, site title, copyright, and such
	like).
	"""

	def __init__(self, database):
		"""Initializes an instance of the class."""
		assert isinstance(database, Database)
		super(WebSite, self).__init__()
		self.database = database
		# Set various defaults
		self.htmlver = XHTML10
		self.htmlstyle = STRICT
		self.base_url = ''
		self.base_path = '.'
		self.home_url = '/'
		self.home_title = 'Home'
		self.title = '%s Documentation' % self.database.name
		self.description = None
		self.keywords = [self.database.name]
		self.author_name = None
		self.author_email = None
		self.date = datetime.datetime.today()
		self.lang = 'en'
		self.sublang = 'US'
		self.copyright = None
		self.encoding = 'ISO-8859-1'
		self._documents = {}
	
	def add_document(self, document):
		"""Adds a document to the website.
		
		This is a stub method to be overridden in descendent classes. It has a
		very basic implementation that suffices for the url_document() method
		below but should be overridden in descendents to provide for efficient
		implementations of object_document() and object_graph() (which cannot
		be provided in this class as their implementation implies knowledge of
		the layout of documents in the site).

		See the concrete output plugins for example implementations.
		"""
		assert isinstance(document, WebSiteDocument)
		self._documents[document.url] = document
		self._documents[document.absolute_url] = document
	
	def url_document(self, url):
		"""Returns the WebSiteDocument associated with a given URL.

		This is a stub method to be overridden in descendent classes. It is
		used to allow weak references between documents by URL (as opposed to
		an object reference), or to obtain references for documents with
		static URLs that do not represent objects.

		If the specified URL cannot be found, the method must return None.
		"""
		return self._documents.get(url)

	def object_document(self, dbobject, *args, **kwargs):
		"""Returns the HTMLDocument associated with a database object.
		
		This is a stub method to be overridden in descendent classes. It is
		used by the _a_to() method of the HTMLDocument class to generate a URL
		for an <a> element pointing to the documentation for a database object.

		If the specified object has no associated HTMLDocument object, the
		method must return None.

		The args and kwargs parameters capture any extra criteria that should
		be used to select between documents in the case that a database object
		is represented by multiple documents (e.g. framed and unframed
		versions).  They correspond to the args and kwargs parameters of the
		_a_to() method.
		"""
		assert isinstance(dbobject, DatabaseObject)
		return None

	def object_graph(self, dbobject, *args, **kwargs):
		"""Returns the GraphDocument associated with a database object.
		
		This is a stub method to be overridden in descendent classes. It is
		used by the _img_of() method of the HTMLDocument class to generate an
		<img> element (and possibly an associated <map> element) in a document
		for a database object.

		If the specified has no associated GraphDocument object, the method
		must return None.

		The args and kwargs parameters capture any extra criteria that should
		be used to select between graphs in the case that a database object is
		represented by multiple graphs (e.g. relational integrity versus
		functional dependencies).  They correspond to the args and kwargs
		parameters of the _img_of() method.
		"""
		assert isinstance(dbobject, DatabaseObject)
		return None

	def write(self):
		"""Writes all documents in the site to disk."""
		for doc in set(self._documents.itervalues()):
			doc.write()
	

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


class HTMLDocument(WebSiteDocument):
	"""Represents a simple HTML document.

	This is the base class for HTML documents. It provides several utility
	methods for constructing HTML elements, formatting content, and writing out
	the final HTML document. Construction of HTML elements is handled by the
	ElementTree API.
	"""

	def __init__(self, site, url, filename=None):
		"""Initializes an instance of the class."""
		self._site_attributes = []
		super(HTMLDocument, self).__init__(site, url, filename)
		self.doc = self._html()
		self.comment_highlighter = self._init_comment_highlighter()
		assert isinstance(self.comment_highlighter, HTMLCommentHighlighter)
		self.sql_highlighter = self._init_sql_highlighter()
		assert isinstance(self.sql_highlighter, HTMLSQLHighlighter)
		self.link_first = None
		self.link_prior = None
		self.link_next = None
		self.link_last = None
		self.link_up = None
		self.robots_index = True
		self.robots_follow = True
		# The following attributes mirror those in the WebSite class. If any
		# are set to something other than None, their value will override the
		# corresponding value in the owning WebSite instance (see the
		# overridden __getattribute__ implementation for more details).
		self.title = None
		self.description = None
		self.keywords = None
		self.author_name = None
		self.author_email = None
		self.date = None
		self.lang = None
		self.sublang = None
		self.copyright = None
		self._site_attributes += [
			'title',
			'description',
			'keywords',
			'author_name',
			'author_email',
			'date',
			'lang',
			'sublang',
			'copyright',
		]
	
	def _init_comment_highlighter(self):
		"""Instantiates an object for highlighting comment markup."""
		return HTMLCommentHighlighter(self)

	def _init_sql_highlighter(self):
		"""Instantiates an object for highlighting SQL."""
		return HTMLSQLHighlighter(self)

	def __getattribute__(self, name):
		if name in super(HTMLDocument, self).__getattribute__('_site_attributes'):
			return super(HTMLDocument, self).__getattribute__(name) or self.site.__getattribute__(name)
		else:
			return super(HTMLDocument, self).__getattribute__(name)

	# Regex which finds characters within the range of characters capable of
	# being encoded as HTML entities
	entitiesre = re.compile(u'[%s-%s]' % (
		unichr(min(HTML_ENTITIES.iterkeys())),
		unichr(max(HTML_ENTITIES.iterkeys()))
	))

	def write(self):
		"""Writes this document to a file in the site's path"""
		super(HTMLDocument, self).write()
		self._create_content()
		# "Pure" XML won't handle HTML character entities. So we do it
		# manually. First, get the XML as a Unicode string (without any XML
		# PI or DOCTYPE)
		if self.site.htmlver >= XHTML10:
			self.doc.attrib['xmlns'] = 'http://www.w3.org/1999/xhtml'
		s = unicode(tostring(self.doc))
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
		s = u'''\
<?xml version="1.0" encoding="%(encoding)s"?>
<!DOCTYPE html
  PUBLIC "%(publicid)s"
  "%(systemid)s">
%(content)s''' % {
			'encoding': self.site.encoding,
			'publicid': public_id,
			'systemid': system_id,
			'content': s,
		}
		# Transcode the document into the target encoding
		s = codecs.getencoder(self.site.encoding)(s)[0]
		# Finally, write the output to the destination file
		f = open(self.filename, 'w')
		try:
			f.write(s)
		finally:
			f.close()

	def _create_content(self):
		"""Constructs the content of the document."""
		# Add some standard <meta> elements (encoding, keywords, author, robots
		# info, Dublin Core stuff, etc.)
		content = [
			self._meta('Robots', ','.join([
				'%sindex'  % ['no', ''][bool(self.robots_index)],
				'%sfollow' % ['no', ''][bool(self.robots_follow)]
			])),
			self._meta('DC.Date', self.date.strftime('%Y-%m-%d'), 'iso8601'),
			self._meta('DC.Language', '%s-%s' % (self.lang, self.sublang), 'rfc1766'),
		]
		if self.copyright is not None:
			content.append(self._meta('DC.Rights', self.copyright))
		if self.description is not None:
			content.append(self._meta('Description', self.description))
		if len(self.keywords) > 0:
			content.append(self._meta('Keywords', ', '.join(self.keywords), 'iso8601'))
		if self.author_email is not None:
			content.append(self._meta('Owner', self.author_email))
			content.append(self._meta('Feedback', self.author_email))
			content.append(self._link('author', 'mailto:%s' % self.author_email, self.author_name))
		# Add some navigation <link> elements
		content.append(self._link('home', 'index.html'))
		if isinstance(self.link_first, HTMLDocument):
			content.append(self._link('first', self.link_first.url))
		if isinstance(self.link_prior, HTMLDocument):
			content.append(self._link('prev', self.link_prior.url))
		if isinstance(self.link_next, HTMLDocument):
			content.append(self._link('next', self.link_next.url))
		if isinstance(self.link_last, HTMLDocument):
			content.append(self._link('last', self.link_last.url))
		if isinstance(self.link_up, HTMLDocument):
			content.append(self._link('up', self.link_up.url))
		# Add the title
		if self.title is not None:
			content.append(self._title(self.title))
		# Create the <head> element with the above content, and an empty <body>
		# element
		self.doc.append(self._head(content))
		self.doc.append(self._body(''))
		# Override this in descendent classes to include additional content

	def _format_comment(self, comment, summary=False):
		return self.comment_highlighter.parse(comment, summary)

	def _format_sql(self, sql, terminator=';', splitlines=False):
		return self.sql_highlighter.parse(sql, terminator, splitlines)

	def _format_prototype(self, sql):
		return self.sql_highlighter.parse_prototype(sql)
	
	def _format_content(self, content):
		if content is None:
			# Format None as 'n/a'
			return 'n/a'
		elif isinstance(content, datetime.datetime):
			# Format timestamps as ISO8601
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
	
	def _append_content(self, node, content):
		"""Adds content (string, node, node-list, etc.) to a node"""
		if isinstance(content, basestring):
			if content != '':
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
					self._append_content(node, n)
			except TypeError:
				self._append_content(node, self._format_content(content))
	
	def _find_element(self, tagname, id=None):
		"""Returns the first element with the specified tagname and id"""
		if id is None:
			result = self.doc.find('.//%s' % tagname)
			if result is None:
				raise Exception('Cannot find any %s elements' % tagname)
			else:
				return result
		else:
			result = [
				elem for elem in self.doc.findall('.//%s' % tagname)
				if elem.attrib.get('id', '') == id
			]
			if len(result) == 0:
				raise Exception('Cannot find a %s element with id %s' % (tagname, id))
			elif len(result) > 1:
				raise Exception('Found multiple %s elements with id %s' % (tagname, id))
			else:
				return result[0]
	
	def _element(self, name, attrs={}, content=''):
		"""Returns an element with the specified name, attributes and content."""
		attrs = dict([
			(n, str(v)) for (n, v) in attrs.iteritems() if v is not None
		])
		e = Element(name, attrs)
		self._append_content(e, content)
		return e

	# HTML CONSTRUCTION METHODS
	# These methods are named after the HTML element they return. The
	# implementation is not intended to be comprehensive, only to cover those
	# elements likely to be used by descendent classes. That said, it is
	# reasonably generic and would likely fit most applications that need to
	# generate HTML.

	def _a(self, href, content=None, title=None, attrs={}):
		if isinstance(href, HTMLDocument):
			if content is None:
				content = href.title
			if title is None:
				title = href.title
			href = href.url
		return self._element('a', AttrDict(href=href, title=title) + attrs, content)

	def _a_to(self, dbobject, typename=False, qualifiedname=False, *args, **kwargs):
		# Special version of "_a" to create a link to a database object. The
		# args and kwargs parameters capture extra information to be used to
		# distinguish between multiple documents
		assert isinstance(dbobject, DatabaseObject)
		if qualifiedname:
			content = dbobject.qualified_name
		else:
			content = dbobject.name
		if typename:
			content = '%s %s' % (dbobject.type_name, content)
		doc = self.site.object_document(dbobject, *args, **kwargs)
		if doc is None:
			return content
		else:
			assert isinstance(doc, HTMLDocument)
			return self._a(doc.url, content)

	def _abbr(self, content, title, attrs={}):
		return self._element('abbr', AttrDict(title=title) + attrs, content)

	def _acronym(self, content, title, attrs={}):
		return self._element('acronym', AttrDict(title=title) + attrs, content)

	def _b(self, content, attrs={}):
		return self._element('b', attrs, content)

	def _big(self, content, attrs={}):
		return self._element('big', attrs, content)

	def _blockquote(self, content, attrs={}):
		return self._element('blockquote', attrs, content)

	def _body(self, content, attrs={}):
		return self._element('body', attrs, content)

	def _br(self):
		return self._element('br')

	def _caption(self, content, attrs={}):
		return self._element('caption', attrs, content)

	def _cite(self, content, attrs={}):
		return self._element('cite', attrs, content)

	def _code(self, content, attrs={}):
		return self._element('code', attrs, content)

	def _dd(self, content, attrs={}):
		return self._element('dd', attrs, content)

	def _del(self, content, attrs={}):
		return self._element('del', attrs, content)

	def _dfn(self, content, attrs={}):
		return self._element('dfn', attrs, content)

	def _div(self, content, attrs={}):
		return self._element('div', attrs, content)

	def _dl(self, items, attrs={}):
		return self._element('dl', attrs, [
			(self._dt(term), self._dd(defn))
			for (term, defn) in items
		])

	def _dt(self, content, attrs={}):
		return self._element('dt', attrs, content)

	def _em(self, content, attrs={}):
		return self._element('em', attrs, content)

	def _h(self, content, level=1, attrs={}):
		return self._element('h%d' % level, attrs, content)

	def _head(self, content, attrs={}):
		return self._element('head', attrs, content)
	
	def _hr(self, attrs={}):
		return self._element('hr', attrs)

	def _html(self, head=None, body=None, attrs={}):
		elem = self._element('html', attrs)
		if head is not None:
			elem.append(head)
		if body is not None:
			elem.append(body)
		return elem

	def _i(self, content, attrs={}):
		return self._element('i', attrs, content)

	def _img(self, src, alt=None, width=None, height=None, attrs={}):
		if isinstance(src, GraphDocument):
			src = src.url
		return self._element('img', AttrDict(src=src, alt=alt, width=width, height=height) + attrs)

	def _img_of(self, dbobject, *args, **kwargs):
		# Special version of "img" to create diagrams of a database object. The
		# args and kwargs parameters capture extra information to be used to
		# distinguish between multiple documents
		assert isinstance(dbobject, DatabaseObject)
		graph = self.site.object_graph(dbobject, *args, **kwargs)
		if graph is None:
			return self._p('Graph for %s is not available' % dbobject.qualified_name)
		else:
			assert isinstance(graph, GraphDocument)
			if graph._usemap:
				# If the graph uses a client side image map for links a bit
				# more work is required. We need to get the graph to generate
				# the <map> document, then import all elements from that
				# document into the document this instance contains...
				image = self._img(graph.url, attrs={'usemap': '#' + graph.url})
				map = graph._map()
				map.attrib['id'] = graph.url
				map.attrib['name'] = graph.url
				return [image, map]
			else:
				return self._img(graph.url)

	def _ins(self, content, attrs={}):
		return self._element('ins', attrs, content)

	def _kbd(self, content, attrs={}):
		return self._element('kbd', attrs, content)

	def _li(self, content, attrs={}):
		return self._element('li', attrs, content)

	def _link(self, rel, href, title=None, attrs={}):
		return self._element('link', AttrDict(rel=rel, href=href, title=title) + attrs)

	def _meta(self, name, content, scheme=None, attrs={}):
		return self._element('meta', AttrDict(name=name, content=content, scheme=scheme) + attrs)

	def _ol(self, items, attrs={}):
		return self._element('ol', attrs, [
			self._li(item)
			for item in items
		])

	def _pre(self, content, attrs={}):
		return self._element('pre', attrs, content)

	def _p(self, content, attrs={}):
		return self._element('p', attrs, content)

	def _q(self, content, attrs={}):
		return self._element('q', attrs, content)

	def _samp(self, content, attrs={}):
		return self._element('samp', attrs, content)

	def _script(self, content='', src=None):
		# Either content or src must be specified, but not both
		assert content or src
		# XXX Workaround: the script element cannot be "empty" (IE fucks up)
		if not content: content = ' '
		n = self._element('script', AttrDict(type='text/javascript', src=src), content)
		return n

	def _small(self, content, attrs={}):
		return self._element('small', attrs, content)

	def _span(self, content, attrs={}):
		return self._element('span', attrs, content)

	def _strong(self, content, attrs={}):
		return self._element('strong', attrs, content)

	def _style(self, content='', src=None, media='screen'):
		# Either content or src must be specified, but not both
		assert content or src
		# If content is specified, output a <style> element, otherwise output a
		# <link> element
		if content:
			return self._element('style', AttrDict(type='text/css', media=media), Comment(content))
		else:
			return self._element('link', AttrDict(type='text/css', media=media, rel='stylesheet', href=src))

	def _sub(self, content, attrs={}):
		return self._element('sub', attrs, content)

	def _sup(self, content, attrs={}):
		return self._element('sup', attrs, content)

	def _table(self, data, head=[], foot=[], caption='', attrs={}):
		tablenode = self._element('table', attrs)
		tablenode.append(self._caption(caption))
		if len(head) > 0:
			theadnode = self._element('thead')
			for row in head:
				if isinstance(row, tuple) and len(row) == 2 and isinstance(row[1], dict):
					# If the row is a two-element tuple, where the second
					# element is a dictionary then the first element contains
					# the content of the row and the second the attributes of
					# the row.
					theadnode.append(self._tr(row[0], head=True, attrs=row[1]))
				else:
					theadnode.append(self._tr(row, head=True))
			tablenode.append(theadnode)
		if len(foot) > 0:
			tfootnode = self._element('tfoot')
			for row in foot:
				if isinstance(row, tuple) and len(row) == 2 and isinstance(row[1], dict):
					# See comments above
					tfootnode.append(self._tr(row[0], head=True, attrs=row[1]))
				else:
					tfootnode.append(self._tr(row, head=True))
			tablenode.append(tfootnode)
		# The <tbody> element is mandatory, even if no rows are present
		tbodynode = self._element('tbody')
		for row in data:
			if isinstance(row, tuple) and len(row) == 2 and isinstance(row[1], dict):
				# See comments above
				tbodynode.append(self._tr(row[0], head=False, attrs=row[1]))
			else:
				tbodynode.append(self._tr(row, head=False))
		tablenode.append(tbodynode)
		return tablenode
	
	def _td(self, content, head=False, attrs={}):
		if content == '':
			content = u'\u00A0' # \u00A0 = &nbsp;
		if head:
			return self._element('th', attrs, content)
		else:
			return self._element('td', attrs, content)
	
	def _title(self, content, attrs={}):
		return self._element('title', attrs, content)
	
	def _tr(self, cells, head=False, attrs={}):
		rownode = self._element('tr', attrs)
		for cell in cells:
			if isinstance(cell, tuple) and len(cell) == 2 and isinstance(cell[1], dict):
				# If the cell is a two-element tuple, where the second cell is
				# a dictionary, then the first element contains the cell's
				# content and the second the cell's attributes.
				rownode.append(self._td(cell[0], head, cell[1]))
			else:
				rownode.append(self._td(cell, head))
		return rownode
	
	def _tt(self, content, attrs={}):
		return self._element('tt', attrs, content)

	def _u(self, content, attrs={}):
		return self._element('u', attrs, content)

	def _ul(self, items, attrs={}):
		return self._element('ul', attrs, [
			self._li(item)
			for item in items
		])

	def _var(self, content, attrs={}):
		return self._element('var', attrs, content)


class CSSDocument(WebSiteDocument):
	"""Represents a simple CSS document.

	This is the base class for CSS stylesheets. It provides no methods for
	constructing or editing CSS; it simply contains a "doc" property which
	stores the CSS to write to the file when write() is called.
	"""

	def __init__(self, site, url):
		"""Initializes an instance of the class."""
		super(CSSDocument, self).__init__(site, url)
		self.doc = ''

	def _create_content(self):
		"""Constructs the content of the stylesheet."""
		# Child classes can override this to build the stylesheet
		pass
	
	def write(self):
		"""Writes this document to a file in the site's path"""
		super(CSSDocument, self).write()
		self._create_content()
		f = open(self.filename, 'w')
		try:
			# Transcode the CSS into the target encoding and write to the file
			f.write(codecs.getencoder(self.site.encoding)(self.doc)[0])
		finally:
			f.close()


class JavaScriptDocument(WebSiteDocument):
	"""Represents a simple JavaScript document.

	This is the base class for JavaScript libraries. It provides no methods for
	constructing or editing JavaScript; it simply contains a "doc" property
	which stores the JavaScript to write to the file when write() is called.
	"""

	def __init__(self, site, url):
		"""Initializes an instance of the class."""
		super(JavaScriptDocument, self).__init__(site, url)
		self.doc = ''

	def _create_content(self):
		"""Constructs the content of the stylesheet."""
		# Child classes can override this to build the library
		pass
	
	def write(self):
		"""Writes this document to a file in the site's path"""
		super(JavaScriptDocument, self).write()
		self._create_content()
		f = open(self.filename, 'w')
		try:
			# Transcode the JavaScript into the target encoding and write to the file
			f.write(codecs.getencoder(self.site.encoding)(self.doc)[0])
		finally:
			f.close()


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
		# PNGs and GIFs use a client-side image-map to define link locations
		# (SVGs just use embedded links)
		self._usemap = os.path.splitext(self.filename)[1].lower() in ('.png', '.gif')
		# _content_done is simply used to ensure that we don't generate the
		# graph content more than once when dealing with image maps (which have
		# to run through graphviz twice, once for the image, once for the map)
		self._content_done = False

	def write(self):
		"""Writes this document to a file in the site's path"""
		super(GraphDocument, self).write()
		# The following lookup tables are used to decide on the method used to
		# write output based on the extension of the image filename
		method_lookup = {
			'.png': self.graph.to_png,
			'.gif': self.graph.to_gif,
			'.svg': self.graph.to_svg,
			'.ps': self.graph.to_ps,
			'.eps': self.graph.to_ps,
		}
		try:
			method = method_lookup[os.path.splitext(self.filename)[1].lower()]
		except KeyError:
			raise Exception('Unknown image extension "%s"' % ext)
		# Generate the graph and write it out to the specified file
		if not self._content_done:
			self._create_content()
		f = open(self.filename, 'wb')
		try:
			method(f)
		finally:
			f.close()

	def _map(self):
		"""Returns an Element containing the client-side image map."""
		assert self._usemap
		if not self._content_done:
			self._create_content()
		f = StringIO()
		try:
			self.graph.to_map(f)
			return fromstring(f.getvalue())
		finally:
			f.close()

	def _create_content(self):
		"""Constructs the content of the graph."""
		# Child classes can override this to build the graph before writing
		self._content_done = True

