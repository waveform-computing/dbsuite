#!/usr/bin/env python
# $Header$
# vim: set noet sw=4 ts=4:

import os
import os.path
import datetime
import shutil
import xml.dom

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

DOM = xml.dom.getDOMImplementation()

def copytree(src, dst, dontcopy=['CVS']):
	"""Utility function based on copytree in shutil.
	
	Parameters:
	src -- The root of the directory tree to copy
	dst -- The destination directory to copy into
	dontcopy -- A list of file/directory names not to copy.
	"""
	names = list(set(os.listdir(src)) - set(dontcopy))
	errors = []
	if not os.path.isdir(dst):
		try:
			os.unlink(dst)
		except OSError:
			os.mkdir(dst)
	for name in names:
		srcname = os.path.join(src, name)
		dstname = os.path.join(dst, name)
		try:
			if os.path.isdir(srcname):
				copytree(srcname, dstname)
			else:
				shutil.copy(srcname, dstname)
		except (IOError, os.error), why:
			errors.append((srcname, dstname, why))
		except Error, err:
			errors.extend(err.args[0])
	if errors:
		raise Error, errors

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

class HTMLSite(object):
	"""Represents a collection of HTML documents (a website).

	This is the base class for a related collection of HTML documents,such as a
	website. It mainly exists to provide attributes which apply to all HTML
	documents in the collection (like author, site title, copyright, and such
	like).
	"""

	def __init__(self):
		"""Initializes an instance of the class."""
		super(HTMLSite, self).__init__()
		# Set various defaults
		self.htmlver = XHTML10
		self.htmlstyle = STRICT
		self.baseurl = ''
		self.basepath = '.'
		self.title = None
		self.description = None
		self.keywords = []
		self.author_name = None
		self.author_email = None
		self.date = datetime.datetime.today()
		self.lang = 'en'
		self.sublang = 'US'
		self.copyright = None
		self.documents = []

class HTMLDocument(object):
	"""Represents a simple HTML document.

	This is the base class for HTML documents. It provides several utility
	methods for constructing HTML elements, formatting content, and writing out
	the final HTML document.
	"""

	def __init__(self, site, url="index.html"):
		"""Initializes an instance of the class."""
		assert isinstance(site, HTMLSite)
		super(HTMLDocument, self).__init__()
		self.site = site
		self.site.documents.append(self)
		if self.site.htmlver >= XHTML10:
			namespace = 'http://www.w3.org/1999/xhtml'
		else:
			namespace = None
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
		self.doc = DOM.createDocument(namespace, 'html', DOM.createDocumentType('html', public_id, system_id))
		self.written = False
		# XXX Do we need to do something with self.site.baseurl here?
		self.url = url
		self.link_first = None
		self.link_prior = None
		self.link_next = None
		self.link_last = None
		self.link_up = None
		self.robots_index = True
		self.robots_follow = True
		# The following attributes mirror those in the HTMLSite class. If any
		# are set to something other than None, their value will override the
		# corresponding value in the owning HTMLSite instance (see the
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
	
	def __getattribute__(self, name):
		if name in [
			'title',
			'description',
			'author_name',
			'author_email',
			'date',
			'lang',
			'sublang',
			'copyright'
		]:
			return super(HTMLDocument, self).__getattribute__(name) or self.site.__getattribute__(name)
		else:
			return super(HTMLDocument, self).__getattribute__(name)

	def write(self, pretty=True):
		"""Writes this document to a file in the site's path"""
		f = open(os.path.join(self.site.basepath, self.url), 'w')
		try:
			if not self.written:
				self.create_content()
				written = True
			if pretty:
				f.write(self.doc.toprettyxml(encoding='UTF-8'))
			else:
				f.write(self.doc.toxml(encoding='UTF-8'))
		finally:
			f.close()

	def create_content(self):
		"""Constructs the content of the document."""
		# Add some standard <meta> elements (encoding, keywords, author, robots
		# info, Dublin Core stuff, etc.)
		content = [
			self.element('meta', {'http-equiv': 'text/html; charset=UTF-8'}),
			self.meta('Robots', ','.join([
				'%sindex'  % ['no', ''][bool(self.robots_index)],
				'%sfollow' % ['no', ''][bool(self.robots_follow)]
			])),
			self.meta('DC.Date', self.date.strftime('%Y-%m-%d'), 'iso8601'),
			self.meta('DC.Language', '%s-%s' % (self.lang, self.sublang), 'rfc1766'),
		]
		if self.copyright is not None:
			content.append(self.meta('DC.Rights', self.copyright))
		if self.description is not None:
			content.append(self.meta('Description', self.description))
		if len(self.keywords) > 0:
			content.append(self.meta('Keywords', ', '.join(self.keywords), 'iso8601'))
		if self.author_email is not None:
			content.append(self.meta('Owner', self.author_email))
			content.append(self.meta('Feedback', self.author_email))
			content.append(self.link('author', 'mailto:%s' % self.author_email, self.author_name))
		# Add some navigation <link> elements
		content.append(self.link('home', 'index.html'))
		if self.link_first is not None:
			content.append(self.link('first', self.link_first))
		if self.link_prior is not None:
			content.append(self.link('prev', self.link_prior))
		if self.link_next is not None:
			content.append(self.link('next', self.link_next))
		if self.link_last is not None:
			content.append(self.link('last', self.link_last))
		if self.link_up is not None:
			content.append(self.link('up', self.link_up))
		# Add the title
		if self.title is not None:
			titlenode = self.doc.createElement('title')
			self.append_content(titlenode, self.title)
			content.append(titlenode)
		# Create the <head> element with the above content, and an empty <body>
		# element
		self.doc.documentElement.appendChild(self.head(content))
		self.doc.documentElement.appendChild(self.body(''))
		# Override this in descendent classes to include additional content
	
	def format_content(self, content):
		if content is None:
			# Format None as 'n/a'
			return 'n/a'
		elif isinstance(content, datetime.datetime):
			# Format timestamps as ISO8601
			return content.strftime('%Y-%m-%d %H:%M:%S')
		elif type(content) in [int, long]:
			# Format integer number with , as a thousand separator
			s = str(content)
			for i in xrange(len(s) - 3, 0, -3): s = '%s,%s' % (s[:i], s[i:])
			return s
		else:
			return str(content)
	
	def append_content(self, node, content):
		"""Adds content (string, node, node-list, etc.) to a node"""
		if content == '':
			pass
		elif isinstance(content, xml.dom.Node):
			node.appendChild(content)
		elif isinstance(content, (xml.dom.NodeList, list, tuple)):
			# We use recursion here to allow for mixed lists of strings and
			# nodes
			for n in content:
				self.append_content(node, n)
		else:
			node.appendChild(self.doc.createTextNode(self.format_content(content)))
	
	def find_element(self, tagname, id=None):
		"""Returns the first element with the specified tagname and id"""
		if tagname is None:
			try:
				return self.doc.getElementsByTagName(tagname)[0]
			except IndexError:
				raise Exception('Cannot find any %s elements' % tagname)
		else:
			try:
				return [
					elem for elem in self.doc.getElementsByTagName(tagname)
					if elem.hasAttribute('id') and elem.getAttribute('id') == id
				][0]
			except IndexError:
				raise Exception('Cannot find a %s element with id %s' % (tagname, id))
	
	def element(self, name, attrs={}, content=''):
		"""Returns an element with the specified name, attributes and content."""
		node = self.doc.createElement(name)
		for name, value in attrs.iteritems():
			if value is not None:
				node.setAttribute(name, value)
		self.append_content(node, content)
		return node

	# HTML CONSTRUCTION METHODS
	# These methods are named after the HTML element they return. The
	# implementation is not intended to be comprehensive, only to cover those
	# elements likely to be used by descendent classes. That said, it is
	# reasonably generic and would likely fit most applications that need to
	# generate HTML.

	def a(self, href, content, title=None, attrs={}):
		return self.element('a', AttrDict(href=href, title=title) + attrs, content)

	def abbr(self, content, title, attrs={}):
		return self.element('abbr', AttrDict(title=title) + attrs, content)

	def acronym(self, content, title, attrs={}):
		return self.element('acronym', AttrDict(title=title) + attrs, content)

	def b(self, content, attrs={}):
		return self.element('b', attrs, content)

	def big(self, content, attrs={}):
		return self.element('big', attrs, content)

	def blockquote(self, content, attrs={}):
		return self.element('blockquote', attrs, content)

	def body(self, content, attrs={}):
		return self.element('body', attrs, content)

	def br(self):
		return self.element('br')

	def caption(self, content, attrs={}):
		return self.element('caption', attrs, content)

	def cite(self, content, attrs={}):
		return self.element('cite', attrs, content)

	def code(self, content, attrs={}):
		return self.element('code', attrs, content)

	def dd(self, content, attrs={}):
		return self.element('dd', attrs, content)

	def del(self, content, attrs={}):
		return self.element('del', attrs, content)

	def dfn(self, content, attrs={}):
		return self.element('dfn', attrs, content)

	def div(self, content, attrs={}):
		return self.element('div', attrs, content)

	def dl(self, items, attrs={}):
		return self.element('dl', attrs, [(self.dt(term), self.dd(defn)) for (term, defn) in items])

	def dt(self, content, attrs={}):
		return self.element('dt', attrs, content)

	def em(self, content, attrs={}):
		return self.element('em', attrs, content)

	def h(self, content, level=1, attrs={}):
		return self.element('h%d' % level, attrs, content)

	def head(self, content, attrs={}):
		return self.element('head', attrs, content)
	
	def hr(self, attrs={}):
		return self.element('hr', attrs)

	def i(self, content, attrs={}):
		return self.element('i', attrs, content)

	def img(self, src, alt=None, width=None, height=None, attrs={}):
		return self.element('img', AttrDict(src=src, alt=alt, width=width, height=height) + attrs)

	def ins(self, content, attrs={}):
		return self.element('ins', attrs, content)

	def kbd(self, content, attrs={}):
		return self.element('kbd', attrs, content)

	def li(self, content, attrs={}):
		return self.element('li', attrs, contentn)

	def link(self, rel, href, title=None, attrs={}):
		return self.element('link', AttrDict(rel=rel, href=href, title=title) + attrs)

	def meta(self, name, content, scheme=None, attrs={}):
		return self.element('meta', AttrDict(name=name, content=content, scheme=scheme) + attrs)

	def ol(self, items, attrs={}):
		return self.element('ol', attrs, [self.li(item) for item in items])

	def pre(self, content, attrs={}):
		return self.element('pre', attrs, content)

	def p(self, content, attrs={}):
		return self.element('p', attrs, content)

	def q(self, content, attrs={}):
		return self.element('q', attrs, content)

	def samp(self, content, attrs={}):
		return self.element('samp', attrs, content)

	def script(self, content='', src=None):
		# Either content or src must be specified, but not both
		assert content or src
		# The script element cannot be "empty" (MSIE doesn't like it)
		n = self.element('script', AttrDict(type='text/javascript', src=src), content)
		if not content:
			n.appendChild(self.doc.createTextNode(''))
		return n

	def small(self, content, attrs={}):
		return self.element('small', attrs, content)

	def span(self, content, attrs={}):
		return self.element('span', attrs, content)

	def strong(self, content, attrs={}):
		return self.element('strong', attrs, content)

	def style(self, content='', src=None, media='screen'):
		# Either content or src must be specified, but not both
		assert content or src
		# If content is specified, output a <style> element, otherwise output a
		# <link> element
		if content:
			return self.element('style', AttrDict(type='text/css', media=media), content)
		else:
			return self.element('link', AttrDict(type='text/css', media=media, rel='stylesheet', href=src))

	def sub(self, content, attrs={}):
		return self.element('sub', attrs, content)

	def sup(self, content, attrs={}):
		return self.element('sup', attrs, content)

	def table(self, data, head=[], foot=[], caption='', attrs={}):
		tablenode = self.element('table', attrs)
		tablenode.appendChild(self.caption(caption))
		if len(head) > 0:
			theadnode = self.doc.createElement('thead')
			for row in head:
				if isinstance(row, dict):
					# If the row is a dictionary, the row content is in the
					# value keyed by the empty string, and all other keys are
					# to be attributes of the cell
					attrs = dict(row)
					row = attrs['']
					del attrs['']
					theadnode.appendChild(self.tr(row, head=True, attrs))
				else:
					theadnode.appendChild(self.tr(row, head=True))
			tablenode.appendChild(theadnode)
		if len(foot) > 0:
			tfootnode = self.doc.createElement('tfoot')
			for row in foot:
				if isinstance(row, dict):
					# See comments above
					attrs = dict(row)
					row = attrs['']
					del attrs['']
					tfootnode.appendChild(self.tr(row, head=True, attrs))
				else:
					tfootnode.appendChild(self.tr(row, head=True))
			tablenode.appendChild(tfootnode)
		# The <tbody> element is mandatory, even if no rows are present
		tbodynode = self.doc.createElement('tbody')
		for row in data:
			if isinstance(row, dict):
				# See comments above
				attrs = dict(row)
				row = attrs['']
				del attrs['']
				tbodynode.appendChild(self.tr(row, head=False, attrs))
			else:
				tbodynode.appendChild(self.tr(row, head=False))
		tablenode.appendChild(tbodynode)
		return tablenode
	
	def td(self, content, head=False, attrs={}):
		if content == '':
			content = u'\u00A0' # \u00A0 = &nbsp;
		if head:
			return self.element('th', attrs, content)
		else:
			return self.element('td', attrs, content)
	
	def tr(self, cells, head=False, attrs={}):
		rownode = self.element('tr', attrs)
		for cell in cells:
			if isinstance(cell, dict):
				# If the cell is a dictionary, the cell content is in the value
				# keyed by the empty string, and all other keys are to be
				# attributes of the cell
				attrs = dict(cell)
				cell = attrs['']
				del attrs['']
				rownode.appendChild(self.td(cell, head, attrs))
			else:
				rownode.appendChild(self.td(cell, head))
		return rownode
	
	def tt(self, content, attrs={}):
		return self.element('tt', attrs, content)

	def u(self, content, attrs={}):
		return self.element('u', attrs, content)

	def ul(self, items, attrs={}):
		return self.element('ul', attrs, [self.li(item) for item in items])

	def var(self, content, attrs={}):
		return self.element('var', attrs, content)
	
