# vim: set noet sw=4 ts=4:

# Import the ElementTree API, favouring the faster cElementTree implementation
try:
	from xml.etree.cElementTree import fromstring, tostring, iselement, Element, SubElement, Comment
except ImportError:
	try:
		from cElementTree import fromstring, tostring, iselement, Element, SubElement, Comment
	except ImportError:
		try:
			from xml.etree.ElementTree import fromstring, tostring, iselement, Element, SubElement, Comment
		except ImportError:
			try:
				from elementtree.ElementTree import fromstring, tostring, iselement, Element, SubElement, Comment
			except ImportError:
				raise ImportError('Unable to find an ElementTree implementation')


__all__ = ['fromstring', 'tostring', 'iselement', 'Element', 'SubElement',
	'Comment', 'indent', 'flatten']


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
	extracts text from an XML tree (text and tail attributes).
	"""
	text = elem.text or ''
	for e in elem:
		text += flatten(e, True)
	if include_tail and elem.tail:
		text += elem.tail
	return text
