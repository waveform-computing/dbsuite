# $Header$
# vim: set noet sw=4 ts=4:

import os
import os.path
import codecs
import re
import datetime
from db2makedoc.dot.graph import (Graph, Node, Edge, Cluster)
from db2makedoc.highlighters.comments import (CommentHighlighter,)
from db2makedoc.highlighters.sql import (
	SQLHighlighter,
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

# Try and import the ElementTree API, favouring the faster cElementTree
# implementation if it's available
try:
	import xml.etree.cElementTree as et
except ImportError:
	try:
		import cElementTree as et
	except ImportError:
		try:
			import xml.etree.ElementTree as et
		except ImportError:
			try:
				import elementTree.ElementTree as et
			except ImportError:
				raise ImportError('Unable to find an ElementTree implementation')

# Import the fastest StringIO implementation we can find
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

class HTMLCommentHighlighter(CommentHighlighter):
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

class HTMLSQLHighlighter(SQLHighlighter):
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
		self.doc = self._html()
		self.comment_highlighter = self._init_comment_highlighter()
		assert isinstance(self.comment_highlighter, CommentHighlighter)
		self.sql_highlighter = self._init_sql_highlighter()
		assert isinstance(self.sql_highlighter, SQLHighlighter)
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
	
	def _init_comment_highlighter(self):
		"""Instantiates an object for highlighting comment markup."""
		return HTMLCommentHighlighter(self)

	def _init_sql_highlighter(self):
		"""Instantiates an object for highlighting SQL."""
		return HTMLSQLHighlighter(self)
	
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

	def write(self):
		"""Writes this document to a file in the site's path"""
		self._create_content()
		# "Pure" XML won't handle HTML character entities. So we do it
		# manually. First, get the XML as a Unicode string (without any XML
		# PI or DOCTYPE)
		if self.site.htmlver >= XHTML10:
			self.doc.attrib['xmlns'] = 'http://www.w3.org/1999/xhtml'
		s = unicode(et.tostring(self.doc))
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
  PUBLIC %(publicid)s
  %(systemid)s>
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
		elif et.iselement(content):
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
		e = et.Element(name, attrs)
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
			return self._element('style', AttrDict(type='text/css', media=media), et.Comment(content))
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
		# PNGs and GIFs use a client-side image-map to define link locations
		self._usemap = os.path.splitext(self.filename)[1].lower() in ('.png', '.gif')
		# _content_done is simply used to ensure that we don't generate the
		# graph content more than once when dealing with image maps (which have
		# to run through graphviz twice, once for the image, once for the map)
		self._content_done = False

	def write(self):
		"""Writes this document to a file in the site's path"""
		# The following lookup tables are used to decide on the method used to
		# write output based on the extension of the image filename
		method_lookup = {
			'.png': self.graph.to_png,
			'.gif': self.graph.to_gif,
			'.svg': self.graph.to_svg,
			'.ps': self.graph.to_ps,
			'.eps': self.graph.to_ps,
		}
		# If our filename is a compound (tuple) value, assume the first element
		# refers to the image filename, and the second refers to the
		# client-side image map
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
			return et.fromstring(f.getvalue())
		finally:
			f.close()

	def _create_content(self):
		"""Constructs the content of the graph."""
		# Child classes can override this to build the graph before writing
		self._content_done = True

