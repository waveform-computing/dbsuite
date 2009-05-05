# vim: set noet sw=4 ts=4:

# XXX This is an extremely dirty hack which works around problems with relative
# imports. This should no longer be necessary in Python 2.6 and above, when
# absolute imports become the default (see PEP328). However, until then, this
# fixes the problem of having a package named 'xml' in the standard library,
# and as a plugin name.
import sys
if 'xml' in sys.modules:
	del sys.modules['xml']

import datetime

try:
	import xml.etree.ElementTree as etree
except ImportError:
	try:
		import elementtree.ElementTree as etree
	except ImportError:
		raise ImportError('Unable to find an ElementTree implementation')


__all__ = ['fromstring', 'tostring', 'parse', 'iselement', 'Element',
		'SubElement', 'Comment', 'ProcessingInstruction', 'QName', 'indent',
		'flatten', 'flatten_html', 'html4_display', '_namespace_map',
		'ElementFactory']


# Monkey patch ElementTree to permit production and parsing of CDATA sections.
# Original code from http://code.activestate.com/recipes/576536/
def CDATA(text=None):
	element = Element(CDATA)
	element.text = text
	return element

old_ElementTree = etree.ElementTree
class ElementTree_CDATA(old_ElementTree):
	def _write(self, file, node, encoding, namespaces):
		if node.tag is CDATA:
			text = node.text.encode(encoding)
			file.write('<![CDATA[%s]]>' % text)
		else:
			old_ElementTree._write(self, file, node, encoding, namespaces)
etree.ElementTree = ElementTree_CDATA

old_XMLTreeBuilder = etree.XMLTreeBuilder
class XMLTreeBuilder_CDATA(old_XMLTreeBuilder):
	def __init__(self, html=0, target=None):
		old_XMLTreeBuilder.__init__(self, html, target)
		self._parser.StartCdataSectionHandler = self._start_cdata
		self._parser.EndCdataSectionHandler = self._end_cdata
		self._cdataSection = False
		self._cdataBuffer = None

	def _start_cdata(self):
		self._cdataSection = True
		self._cdataBuffer = []

	def _end_cdata(self):
		self._cdataSection = False
		text = self._fixtext(''.join(self._cdataBuffer))
		self._target.start(CDATA, {})
		self._target.data(text)
		self._target.end(CDATA)

	def _data(self, text):
		if self._cdataSection:
			self._cdataBuffer.append(text)
		else:
			old_XMLTreeBuilder._data(self, text)
etree.XMLTreeBuilder = XMLTreeBuilder_CDATA

try:
	from xml.etree.ElementTree import *
	from xml.etree.ElementTree import _namespace_map
	from xml.parsers import expat
except ImportError:
	from elementtree.ElementTree import *
	from elementtree.ElementTree import _namespace_map


def indent(elem, level=0, indent_str='\t'):
	"""Pretty prints XML with indentation.

	This is a small utility routine adapted from the ElementTree website which
	indents XML (in-place) to enable easier reading by humans.
	"""
	i = '\n' + indent_str * level
	if len(elem):
		if not elem.text or not elem.text.strip():
			elem.text = i + indent_str
		for child in elem:
			indent(child, level + 1)
		if not child.tail or not child.tail.strip():
			child.tail = i
		if not elem.tail or not elem.tail.strip():
			elem.tail = i
	else:
		if level and (not elem.tail or not elem.tail.strip()):
			elem.tail = i

def flatten(elem, include_tail=False):
	"""Extracts text from XML.

	This is a small utility routine taken from the ElementTree website which
	extracts text from an XML tree (text and tail attributes). Note that this
	may not be sufficient for extracting text from mixed-type XML documents
	like HTML, especially when extraneous whitespace is ommitted. For example:

		<ul><li>Item 1</li><li>Item 2</li><li>Item 3</li></ul>

	This will flatten to:

		"Item 1Item 2Item 3"
	
	Which is probably not what is wanted. See the flatten_html function below
	for dealing with this.
	"""
	text = elem.text or ''
	for e in elem:
		text += flatten(e, True)
	if include_tail and elem.tail:
		text += elem.tail
	return text

# The following dictionary lists the default display properties for elements in
# HTML 4 (taken from Appendix D of the CSS 2.1 specification) Note that the
# inline display property is ommitted as this is the default (i.e. any element
# encountered which is not explicitly mentioned in this list is assumed to have
# display set to inline).
html4_display = {
	'block': [
		'html', 'address', 'blockquote', 'body', 'dd', 'div', 'dl', 'dt',
		'fieldset', 'form', 'frame', 'frameset', 'h1', 'h2', 'h3', 'h4', 'h5',
		'h6', 'noframes', 'ol', 'p', 'ul', 'center', 'dir', 'hr', 'menu',
		'pre'
	],
	'list-item':          ['li'],
	'inline-block':       ['button', 'textarea', 'input', 'select'],
	'table':              ['table'],
	'table-row-group':    ['tbody'],
	'table-header-group': ['thead'],
	'table-footer-group': ['tfoot'],
	'table-row':          ['tr'],
	'table-column-group': ['colgroup'],
	'table-column':       ['col'],
	'table-cell':         ['td', 'th'],
	'table-caption':      ['caption'],
	'none':               ['head'],
}

# Restructure the dictionary above into a format more suitable for looking up
# display types by tag.
html4_display = dict(
	(tag, display)
	for (display, tags) in html4_display.iteritems()
	for tag in tags
)

# These dictionaries specify the prefixes and suffixes added to element content
# for particular display types. Any display type not mentioned in the
# dictionaries default to ''.
flatten_prefixes = {
	'list-item': ' * ',
}
flatten_suffixes = {
	'block': '\n',
	'table': '\n',
	'table-caption': '\n',
	'table-row': '\n',
	'table-cell': ' ',
	'list-item': '\n',
}

def flatten_html(elem, elem_display=html4_display, xmlns='', include_tail=False):
	"""Extracts text from HTML.

	This is a variant of the flatten() function above which is designed to cope
	with the problems of flattening mixed-type XML like HTML documents, in
	which whitespace must be introduced in order for the flattened text to make
	sense.
	
	The elem_display property specifies a mapping of tags to CSS display types
	which determines how whitespace is added to the result. By default this is
	the html4_display dictionary defined above. Override this if you want to
	apply different display types for certain elements (e.g. anchor elements
	rendering in block style).

	The xmlns property specifies the XML namespace applied to the HTML elements
	(for dealing with XHTML elements which wouldn't otherwise match the entries
	in the standard html4_display dictionary).
	"""
	tag = elem.tag
	if xmlns and tag.startswith('{%s}' % xmlns):
		tag = tag[len(xmlns) + 2:]
	display = elem_display.get(tag, 'inline')
	# Don't render elements with certain display types (or their children)
	if display in ['none', 'table-column-group', 'table-column']:
		return ''
	else:
		text = ''
		# Make a vague effort to avoid too many extraneous newlines
		if elem.text:
			text += flatten_prefixes.get(display, '')
			text += elem.text
		for e in elem:
			text += flatten_html(e, elem_display, xmlns, True)
		if include_tail:
			text += flatten_suffixes.get(display, '')
			if elem.tail:
				text += elem.tail
		return text


class ElementFactory(object):
	"""A class inspired by Genshi for easy creation of ElementTree Elements.

	The ElementFactory class was inspired by the Genshi builder unit in that it
	permits simple creation of Elements by calling methods on the tag object
	named after the element you wish to create. Positional arguments become
	content within the element, and keyword arguments become attributes.

	If you need an attribute or element tag that conflicts with a Python
	keyword, simply append an underscore to the name (which will be
	automatically stripped off).

	Content can be just about anything, including booleans, integers, longs,
	dates, times, etc. This class simply applies their default string
	conversion to them (except basestring derived types like string and unicode
	which are simply used verbatim).

	For example:

	>>> tostring(tag.a('A link'))
	'<a>A link</a>'
	>>> tostring(tag.a('A link', class_='menuitem'))
	'<a class="menuitem">A link</a>'
	>>> tostring(tag.p('A ', tag.a('link', class_='menuitem')))
	'<p>A <a class="menuitem">link</a></p>'
	"""

	def __init__(self, namespace=None):
		"""Intializes an instance of the factory.

		The optional namespace parameter can be used to specify the namespace
		used to qualify all elements generated by an instance of the class.
		Rather than specifying this explicitly when constructing the class it
		is recommended that developers sub-class this class, and specify the
		namespace as part of an overridden __init__ method. In other words,
		make dialect specific sub-classes of this generic class (an
		HTMLElementFactory class for instance).
		"""
		self._namespace = namespace

	def _find(self, root, tagname, id=None):
		"""Returns the first element with the specified tagname and id"""
		if id is None:
			result = root.find('.//%s' % tagname)
			if result is None:
				raise LookupError('Cannot find any %s elements' % tagname)
			else:
				return result
		else:
			result = [
				elem for elem in root.findall('.//%s' % tagname)
				if elem.attrib.get('id', '') == id
			]
			if len(result) == 0:
				raise LookupError('Cannot find a %s element with id %s' % (tagname, id))
			elif len(result) > 1:
				raise LookupError('Found multiple %s elements with id %s' % (tagname, id))
			else:
				return result[0]

	def _format(self, content):
		"""Reformats content into a human-readable string"""
		if isinstance(content, basestring):
			# Strings (including unicode) are returned verbatim
			return content
		else:
			# Everything else is converted to an ASCII string
			return str(content)

	def _append(self, node, contents):
		"""Adds content (string, node, node-list, etc.) to a node"""
		if isinstance(contents, basestring):
			if contents != '':
				if len(node) == 0:
					if node.text is None:
						node.text = contents
					else:
						node.text += contents
				else:
					last = node[-1]
					if last.tail is None:
						last.tail = contents
					else:
						last.tail += contents
		elif isinstance(contents, (int, long, bool, datetime.datetime, datetime.date, datetime.time)):
			# XXX This branch exists for optimization purposes only (the except
			# branch below is moderately expensive)
			self._append(node, self._format(contents))
		elif iselement(contents):
			contents.tail = ''
			node.append(contents)
		else:
			try:
				for content in contents:
					self._append(node, content)
			except TypeError:
				self._append(node, self._format(contents))

	def _element(self, _name, *contents, **attrs):
		if self._namespace:
			_name = '{%s}%s' % (self._namespace, _name)
			attrs = dict(
				('{%s}%s' % (self._namespace, key), value)
				for (key, value) in attr.iteritems()
			)
		def conv(key, value):
			# This little utility routine is used to clean up attributes:
			# boolean True is represented as the key (as in checked="checked"),
			# all values are converted to strings, and trailing underscores are
			# removed from key names (convenience for names which are python
			# keywords)
			if not isinstance(key, basestring):
				key = str(key)
			else:
				key = key.rstrip('_')
			if value is True:
				value = key
			elif not isinstance(value, basestring):
				value = str(value)
			return key, value
		e = Element(_name, dict(
			conv(key, value)
			for key, value in attrs.iteritems()
			if value is not None and value is not False
		))
		for content in contents:
			self._append(e, content)
		return e

	def __getattr__(self, name):
		elem_name = name.rstrip('_')
		def generator(*content, **attrs):
			return self._element(elem_name, *content, **attrs)
		setattr(self, name, generator)
		return generator

