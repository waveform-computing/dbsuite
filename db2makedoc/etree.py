# vim: set noet sw=4 ts=4:

# XXX This is an extremely dirty hack which works around problems with relative
# imports. This should no longer be necessary in Python 2.6 and above, when
# absolute imports become the default (see PEP328). However, until then, this
# fixes the problem of having a package named 'xml' in the standard library,
# and as a plugin name.
import sys
if 'xml' in sys.modules:
	del sys.modules['xml']

# Import the ElementTree API, favouring faster versions
#try:
#	from lxml.etree import *
#except ImportError:
try:
	from xml.etree.cElementTree import *
except ImportError:
	try:
		from cElementTree import *
	except ImportError:
		try:
			from xml.etree.ElementTree import *
		except ImportError:
			try:
				from elementtree.ElementTree import *
			except ImportError:
				raise ImportError('Unable to find an ElementTree implementation')


__all__ = ['fromstring', 'tostring', 'parse', 'iselement', 'Element',
		'SubElement', 'Comment', 'ProcessingInstruction', 'QName', 'indent',
		'flatten', 'flatten_html']


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
