# $Header$
# vim: set noet sw=4 ts=4:

# Standard modules
import os
import os.path
import codecs
import re
import datetime
import shutil
import xml.dom

# Application-specific modules
from dot.graph import Graph, Node, Edge, Cluster

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

# Global DOM implementation

DOM = xml.dom.getDOMImplementation()

# HTML character entities from the HTML4.01 spec
# <http://www.w3.org/TR/REC-html40/sgml/entities.html> (see
# HTMLDocument.write() for usage)

HTML_ENTITIES = {
# Section 24.2 (ISO-8859-1 characters)
	160: 'nbsp',
	161: 'iexcl',
	162: 'cent',
	163: 'pound',
	164: 'curren',
	165: 'yen',
	166: 'brvbar',
	167: 'sect',
	168: 'uml',
	169: 'copy',
	170: 'ordf',
	171: 'laquo',
	172: 'not',
	173: 'shy',
	174: 'reg',
	175: 'macr',
	176: 'deg',
	177: 'plusmn',
	178: 'sup2',
	179: 'sup3',
	180: 'acute',
	181: 'micro',
	182: 'para',
	183: 'middot',
	184: 'cedil',
	185: 'sup1',
	186: 'ordm',
	187: 'raquo',
	188: 'frac14',
	189: 'frac12',
	190: 'frac34',
	191: 'iquest',
	192: 'Agrave',
	193: 'Aacute',
	194: 'Acirc',
	195: 'Atilde',
	196: 'Auml',
	197: 'Aring',
	198: 'AElig',
	199: 'Ccedil',
	200: 'Egrave',
	201: 'Eacute',
	202: 'Ecirc',
	203: 'Euml',
	204: 'Igrave',
	205: 'Iacute',
	206: 'Icirc',
	207: 'Iuml',
	208: 'ETH',
	209: 'Ntilde',
	210: 'Ograve',
	211: 'Oacute',
	212: 'Ocirc',
	213: 'Otilde',
	214: 'Ouml',
	215: 'times',
	216: 'Oslash',
	217: 'Ugrave',
	218: 'Uacute',
	219: 'Ucirc',
	220: 'Uuml',
	221: 'Yacute',
	222: 'THORN',
	223: 'szlig',
	224: 'agrave',
	225: 'aacute',
	226: 'acirc',
	227: 'atilde',
	228: 'auml',
	229: 'aring',
	230: 'aelig',
	231: 'ccedil',
	232: 'egrave',
	233: 'eacute',
	234: 'ecirc',
	235: 'euml',
	236: 'igrave',
	237: 'iacute',
	238: 'icirc',
	239: 'iuml',
	240: 'eth',
	241: 'ntilde',
	242: 'ograve',
	243: 'oacute',
	244: 'ocirc',
	245: 'otilde',
	246: 'ouml',
	247: 'divide',
	248: 'oslash',
	249: 'ugrave',
	250: 'uacute',
	251: 'ucirc',
	252: 'uuml',
	253: 'yacute',
	254: 'thorn',
	255: 'yuml',
# Section 24.3 (symbols, mathematical symbols, and greek letters)
	402: 'fnof',
	913: 'Alpha',
	914: 'Beta',
	915: 'Gamma',
	916: 'Delta',
	917: 'Epsilon',
	918: 'Zeta',
	919: 'Eta',
	920: 'Theta',
	921: 'Iota',
	922: 'Kappa',
	923: 'Lambda',
	924: 'Mu',
	925: 'Nu',
	926: 'Xi',
	927: 'Omicron',
	928: 'Pi',
	929: 'Rho',
	931: 'Sigma',
	932: 'Tau',
	933: 'Upsilon',
	934: 'Phi',
	935: 'Chi',
	936: 'Psi',
	937: 'Omega',
	945: 'alpha',
	946: 'beta',
	947: 'gamma',
	948: 'delta',
	949: 'epsilon',
	950: 'zeta',
	951: 'eta',
	952: 'theta',
	953: 'iota',
	954: 'kappa',
	955: 'lambda',
	956: 'mu',
	957: 'nu',
	958: 'xi',
	959: 'omicron',
	960: 'pi',
	961: 'rho',
	962: 'sigmaf',
	963: 'sigma',
	964: 'tau',
	965: 'upsilon',
	966: 'phi',
	967: 'chi',
	968: 'psi',
	969: 'omega',
	977: 'thetasym',
	978: 'upsih',
	982: 'piv',
	8226: 'bull',
	8230: 'hellip',
	8242: 'prime',
	8243: 'Prime',
	8254: 'oline',
	8250: 'frasl',
	8472: 'weierp',
	8465: 'image',
	8476: 'real',
	8482: 'trade',
	8501: 'alefsym',
	8592: 'larr',
	8593: 'uarr',
	8594: 'rarr',
	8595: 'darr',
	8596: 'harr',
	8629: 'crarr',
	8656: 'lArr',
	8657: 'uArr',
	8658: 'rArr',
	8659: 'dArr',
	8660: 'hArr',
	8704: 'forall',
	8706: 'part',
	8707: 'exist',
	8709: 'empty',
	8711: 'nabla',
	8712: 'isin',
	8713: 'notin',
	8715: 'ni',
	8719: 'prod',
	8721: 'sum',
	8722: 'minus',
	8727: 'lowast',
	8730: 'radic',
	8733: 'prop',
	8734: 'infin',
	8736: 'ang',
	8743: 'and',
	8744: 'or',
	8745: 'cap',
	8746: 'cup',
	8747: 'int',
	8756: 'there4',
	8764: 'sim',
	8773: 'cong',
	8776: 'asymp',
	8800: 'ne',
	8801: 'equiv',
	8804: 'le',
	8805: 'ge',
	8834: 'sub',
	8835: 'sup',
	8836: 'nsub',
	8838: 'sube',
	8839: 'supe',
	8853: 'oplus',
	8855: 'otimes',
	8869: 'perp',
	8901: 'sdot',
	8968: 'lceil',
	8969: 'rceil',
	8970: 'lfloor',
	8971: 'rfloor',
	9001: 'lang',
	9002: 'rang',
	9674: 'loz',
	9824: 'spades',
	9827: 'clubs',
	9829: 'hearts',
	9830: 'diams',
# Section 24.4 (markup-significant and I18N characters)
	338: 'OElig',
	339: 'oelig',
	352: 'Scaron',
	353: 'scaron',
	376: 'Yuml',
	710: 'circ',
	732: 'tidle',
	8194: 'ensp',
	8195: 'emsp',
	8201: 'thinsp',
	8204: 'zwnj',
	8205: 'zwj',
	8206: 'lrm',
	8207: 'rlm',
	8211: 'ndash',
	8212: 'mdash',
	8216: 'lsquo',
	8217: 'rsquo',
	8218: 'sbquo',
	8220: 'ldquo',
	8221: 'rdquo',
	8222: 'bdquo',
	8224: 'dagger',
	8225: 'Dagger',
	8240: 'permil',
	8249: 'lsaquo',
	8250: 'rsaquo',
	8364: 'euro',
}

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

class WebSite(object):
	"""Represents a collection of HTML documents (a website).

	This is the base class for a related collection of HTML documents,such as a
	website. It mainly exists to provide attributes which apply to all HTML
	documents in the collection (like author, site title, copyright, and such
	like).
	"""

	def __init__(self):
		"""Initializes an instance of the class."""
		super(WebSite, self).__init__()
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
		self.documents = {}
		self.encoding = 'ISO-8859-1'
	
	def add_document(self, document):
		assert isinstance(document, WebSiteDocument)
		self.documents[document.url] = document

class WebSiteDocument(object):
	"""Represents a document in a website (e.g. HTML, CSS, image, etc.)"""

	def __init__(self, site, url):
		"""Initializes an instance of the class."""
		assert isinstance(site, WebSite)
		super(WebSiteDocument, self).__init__()
		self.site = site
		self.url = url
		self.filename = os.path.join(self.site.basepath, self.url)
		self.site.add_document(self)
	
	def write(self):
		"""Writes this document to a file in the site's path"""
		# Stub method to be overridden in descendent classes
		pass

class HTMLDocument(WebSiteDocument):
	"""Represents a simple HTML document.

	This is the base class for HTML documents. It provides several utility
	methods for constructing HTML elements, formatting content, and writing out
	the final HTML document.
	"""

	def __init__(self, site, url):
		"""Initializes an instance of the class."""
		super(HTMLDocument, self).__init__(site, url)
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
	
	def __getattribute__(self, name):
		if name in [
			'title',
			'description',
			'keywords',
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

	# Regex which finds characters within the range of characters capable of
	# being encoded as HTML entities
	entitiesre = re.compile(u'[%s-%s]' % (
		unichr(min(HTML_ENTITIES.iterkeys())),
		unichr(max(HTML_ENTITIES.iterkeys()))
	))

	# Regex which finds the XML PI at the start of an XML document
	xmlpire = re.compile(ur'^<\?xml version="1\.0" \?>')

	def write(self):
		"""Writes this document to a file in the site's path"""

		def subfunc(match):
			if ord(match.group()) in HTML_ENTITIES:
				return u'&%s;' % HTML_ENTITIES[ord(match.group())]
			else:
				return match.group()

		f = open(self.filename, 'w')
		try:
			self.create_content()
			try:
				# "Pure XML" DOM won't handle HTML character entities. So we do
				# it manually... First, get the XML as a Unicode string
				s = self.doc.toxml()
				# Convert any characters into HTML entities that can be
				s = self.entitiesre.sub(subfunc, s)
				# Patch the XML PI at the start to reflect the target encoding
				s = self.xmlpire.sub(u'<?xml version="1.0" encoding="%s" ?>' % self.site.encoding, s)
				# Transcode the XML into the target encoding
				s = codecs.getencoder(self.site.encoding)(s)[0]
				f.write(s)
			finally:
				# XXX Because DOM takes up a truly stupid amount of memory, and
				# because this class is used in a one-shot manner, we unlink
				# (destroy) the document contents as soon as they're written.
				# Without this, in practice, db2makedoc can easily chew up 1Gb
				# of RAM (!) even with relatively small databases
				self.doc.unlink()
		finally:
			f.close()

	def create_content(self):
		"""Constructs the content of the document."""
		# Add some standard <meta> elements (encoding, keywords, author, robots
		# info, Dublin Core stuff, etc.)
		content = [
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
		if isinstance(self.link_first, HTMLDocument):
			content.append(self.link('first', self.link_first.url))
		if isinstance(self.link_prior, HTMLDocument):
			content.append(self.link('prev', self.link_prior.url))
		if isinstance(self.link_next, HTMLDocument):
			content.append(self.link('next', self.link_next.url))
		if isinstance(self.link_last, HTMLDocument):
			content.append(self.link('last', self.link_last.url))
		if isinstance(self.link_up, HTMLDocument):
			content.append(self.link('up', self.link_up.url))
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
	
	def append_content(self, node, content):
		"""Adds content (string, node, node-list, etc.) to a node"""
		if isinstance(content, basestring):
			if content != '':
				node.appendChild(self.doc.createTextNode(self.format_content(content)))
		elif isinstance(content, xml.dom.Node) or hasattr(content, 'nodeType'):
			node.appendChild(content)
		elif isinstance(content, (list, tuple)) or hasattr(content, '__iter__'):
			# We use recursion here to allow for mixed lists of strings and
			# nodes
			for n in content:
				self.append_content(node, n)
		elif content is None:
			# None gets re-written to not-applicable / not-available
			node.appendChild(self.doc.createTextNode('n/a'))
		else:
			# Attempt to convert anything else into a string
			node.appendChild(self.doc.createTextNode(self.format_content(str(content))))
	
	def find_element(self, tagname, id=None):
		"""Returns the first element with the specified tagname and id"""
		if id is None:
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
				assert isinstance(value, basestring)
				node.setAttribute(name, value)
		self.append_content(node, content)
		return node

	# HTML CONSTRUCTION METHODS
	# These methods are named after the HTML element they return. The
	# implementation is not intended to be comprehensive, only to cover those
	# elements likely to be used by descendent classes. That said, it is
	# reasonably generic and would likely fit most applications that need to
	# generate HTML.

	def a(self, href, content=None, title=None, attrs={}):
		if isinstance(href, HTMLDocument):
			if content is None:
				content = href.title
			if title is None:
				title = href.title
			href = href.url
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

	# Renamed from del as del is a Python keyword
	def _del(self, content, attrs={}):
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
		if isinstance(src, GraphDocument):
			src = src.url
		return self.element('img', AttrDict(src=src, alt=alt, width=width, height=height) + attrs)

	def ins(self, content, attrs={}):
		return self.element('ins', attrs, content)

	def kbd(self, content, attrs={}):
		return self.element('kbd', attrs, content)

	def li(self, content, attrs={}):
		return self.element('li', attrs, content)

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
			return self.element('style', AttrDict(type='text/css', media=media), self.doc.createComment(content))
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
					theadnode.appendChild(self.tr(row, head=True, attrs=attrs))
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
					tfootnode.appendChild(self.tr(row, head=True, attrs=attrs))
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
				tbodynode.appendChild(self.tr(row, head=False, attrs=attrs))
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
	
	def write(self):
		"""Writes this document to a file in the site's path"""
		f = open(self.filename, 'w')
		try:
			# Transcode the CSS into the target encoding and write to the file
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
		# XXX Rewrite URL to include 'orrible IE specific stuff for
		# PNG+image-maps instead of SVG
	
	def write(self):
		"""Writes this document to a file in the site's path"""
		# XXX Add some hackish trickery to produce additional PNG and
		# client-side image map files
		f = open(self.filename, 'w')
		try:
			self.create_graph()
			self.graph.to_svg(f)
		finally:
			f.close()

	def create_graph(self):
		"""Constructs the content of the graph."""
		# Child classes can override this to make last minute tweaks to the
		# graph before writing
		pass
