#!/bin/env python
# $Header$
# vim: set noet sw=4 ts=4:

import datetime
import HTMLParser
from xml.sax.saxutils import quoteattr, escape

class StripHTML(HTMLParser.HTMLParser):
	def strip(self, data):
		self._output = []
		self.feed(data)
		self.close()
		return ''.join(self._output)
	
	def handle_data(self, data):
		self._output.append(data)
	
	def handle_charref(self, ref):
		self._output.append(chr(int(ref)))
	
	def handle_entityref(self, ref):
		self._output.append({
			'amp': '&',
			'lt': '<',
			'gt': '>',
			'apos': "'",
			'quot': '"',
		}[ref])

def stripTags(content):
	return StripHTML().strip(content)

def startTag(name, attrs={}, empty=False):
	"""Generates an XHTML start tag containing the specified attributes"""
	subst = {
		'name': name,
		'attrs': ''.join([" %s=%s" % (str(key), quoteattr(str(attrs[key]))) for key in attrs]),
	}
	if empty:
		return "<%(name)s%(attrs)s />" % subst
	else:
		return "<%(name)s%(attrs)s>" % subst

def endTag(name):
	"""Generates an XHTML end tag"""
	return "</%s>" % (name)

def formatContent(content):
	if content is None:
		# Format None as 'n/a'
		return 'n/a'
	elif isinstance(content, datetime.datetime):
		# Format timestamps as ISO8601-ish (without the T separator)
		return content.strftime('%Y-%m-%d %H:%M:%S')
	elif type(content) in [int, long]:
		# Format integer numbers with , as a thousand separator
		s = str(content)
		for i in xrange(len(s) - 3, 0, -3): s = "%s,%s" % (s[:i], s[i:])
		return s
	else:
		return str(content)

def makeTag(name, attrs={}, content="", optional=False):
	"""Generates a XHTML element containing the specified attributes and content"""
	# Convert the content into a string, using custom conversions as necessary
	contentStr = formatContent(content)
	if contentStr != "":
		return "%s%s%s" % (startTag(name, attrs), contentStr, endTag(name))
	elif not optional:
		return startTag(name, attrs, True)
	else:
		return ""

def makeTableCell(content, head=False, cellAttrs={}):
	"""Returns a table cell containing the specified content"""
	if str(content) != "":
		return makeTag(['td', 'th'][bool(head)], cellAttrs, content)
	else:
		return makeTag(['td', 'th'][bool(head)], cellAttrs, '&nbsp;')

def makeTableRow(cells, head=False, rowAttrs={}):
	"""Returns a table row containing the specified cells"""
	return makeTag('tr', rowAttrs, ''.join([makeTableCell(content, head) for content in cells]))

def makeTable(data, head=[], foot=[], tableAttrs={}):
	"""Returns a table containing the specified head and data cells"""
	defaultAttrs = {'class': 'basic-table', 'cellspacing': 1, 'cellpadding': 0}
	defaultAttrs.update(tableAttrs)
	return makeTag('table', defaultAttrs, ''.join([
			makeTag('thead', {}, ''.join([makeTableRow(row, head=True, rowAttrs={'class': 'blue-med-dark'}) for row in head]), optional=True),
			makeTag('tfoot', {}, ''.join([makeTableRow(row, head=True, rowAttrs={'class': 'blue-med-dark'}) for row in foot]), optional=True),
			makeTag('tbody', {}, ''.join([makeTableRow(row, head=False, rowAttrs={'class': color}) for (row, color) in zip(data, ['white', 'gray'] * len(data))]), optional=False),
		])
	)

def makeListItem(content):
	"""Returns a list item containing the specified content"""
	return makeTag('li', {}, content)

def makeOrderedList(items):
	"""Returns an ordered list containing the specified items"""
	return makeTag('ol', {}, ''.join([makeListItem(item) for item in items]))

def makeUnorderedList(items):
	"""Returns an unordered list containing the specified items"""
	return makeTag('ul', {}, ''.join([makeListItem(item) for item in items]))

def makeDefinitionList(items):
	"""Returns a definition list containing the specified items"""
	return makeTag('dl', {}, ''.join([
		''.join([
			makeTag('dt', {}, term),
			makeTag('dd', {}, definition)
		])
		for term, definition in items
	]))

def main():
	# XXX Test cases
	pass

if __name__ == "__main__":
	main()
