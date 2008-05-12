#!/usr/bin/env python

import sys
import os
import re
import logging
import codecs
import optparse
import traceback
from urllib2 import urlopen
from urlparse import urljoin

# If we're running from an SVN checkout, tweak the path to find the main
# package from the checkout in preference to any that may be installed in the
# system's library
mypath = os.path.dirname(sys.argv[0])
if (os.path.exists(os.path.join(mypath, '.svn')) and
		os.path.exists(os.path.join(mypath, '..', '..', '..', 'db2makedoc'))):
	sys.path.insert(0, os.path.realpath(os.path.join(mypath, '..', '..', '..')))

from db2makedoc.etree import fromstring, tostring, iselement, Element, SubElement


# Create a simple UTF-8 encoder function. If you wish output to be in a
# different encoding, change the following getencoder() call
encoder = codecs.getencoder('utf-8')
encode = lambda s: encoder(s)[0]

def convert_name(elem):
	"""Extracts a name from an element.

	This routine is used to extract names from the InfoCenter documentation.
	The documentation often includes footnotes or modification indicators
	within the name column of a table, hence we need to be careful when
	extracting the name that we don't pick up this extraneous information.
	Specifically we extract only text which exists as a direct child of elem,
	not text owned by any child elements.
	"""
	result = elem.text or ''
	for child in elem:
		result += child.tail or ''
	return result

def convert_desc(elem):
	"""Given an HTML element, converts its content to text.
	
	This routine recursively extracts the text and tail attributes of the
	specified element. Special handling is provided for <ul> and <ol> lists
	which are commonly used in the InfoCenter's descriptions of columns. <ul>
	lists are simply converted to comma separated lists; <ol> lists are
	converted to numbered comma separated lists.
	
	All consecutive whitespace found within the HTML (newlines etc.) is
	converted and compressed to a single space character, and the final result
	is stripped of leading and trailing whitespace.

	The routine ignores anything within a <span id="changed"> element as these
	were (erroneously) used in the v8 InfoCenter for change marks.
	"""
	if elem.tag == 'ul':
		result = ', '.join([
			re.sub(r'\.$', '', convert_desc(li))
			for li in elem.findall('li')
		]) + '. '
	elif elem.tag == 'ol':
		result = ', '.join([
			'%d. %s' % (ix, re.sub(r'\.$', '', convert_desc(li)))
			for (ix, li) in enumerate(elem.findall('li'))
		]) + '. '
	elif elem.tag == 'span' and elem.attrib.get('id') == 'changed':
		result = ''
	else:
		result = elem.text or ''
		for e in elem:
			result += convert_desc(e) + (e.tail or '')
		result = re.sub(r'\s+', ' ', result)
	return result.strip()

def quote_str(s):
	"""Quotes a string for use in SQL.

	Quotes the string s with single quotes, doubling up single quotes within
	the string and replacing certain control characters with SQL hex-string
	equivalents (e.g. newlines).
	"""
	# Double up string quotes
	s = s.replace("'", "''")
	# Replace CR and LF with hex-strings
	s = s.replace('\r', "'||X'0D'||'")
	s = s.replace('\n', "'||X'0A'||'")
	# Enclose the result in quotes
	return "'%s'" % s

def quote_ident(s):
	"""Quotes an SQL identifier.

	If s is an identifier which would need quoting in order to avoid any
	transformation (e.g. lowercase characters), or contains characters not
	allowed in an unquoted identifier (symbols, spaces, etc.) then this routine
	returns s enclosed in double quotes (double quotes appearing within s are
	doubled).
	"""
	if re.match(r'^[A-Z#$@_][A-Z0-9#$@_]*$', s):
		# If it's a basic identifier, don't bother with quoting
		return s
	else:
		# Quote identifier, ensuring any embedded quotes are doubled
		return '"%s"' % s.replace('"', '""')

def indent(elem, level=0):
	"""Pretty prints XML with indentation.

	This is a small utility routine adapted from the ElementTree website which
	indents XML (in-place) to enable easier reading by humans.
	"""
	i = '\n' + ' ' * 4 * level
	if len(elem):
		if not elem.text or not elem.text.strip():
			elem.text = i + ' ' * 4
		for child in elem:
			indent(child, level + 1)
		if not child.tail or not child.tail.strip():
			child.tail = i
		if not elem.tail or not elem.tail.strip():
			elem.tail = i
	else:
		if level and (not elem.tail or not elem.tail.strip()):
			elem.tail = i


class InfoCenterRetriever(object):
	"""Retrieves object descriptions from the IBM InfoCenter."""

	def __init__(self, version):
		super(InfoCenterRetriever, self).__init__()
		self.version = version
		self.url = {
			'8':  'http://publib.boulder.ibm.com/infocenter/db2luw/v8/topic/com.ibm.db2.udb.doc/admin/r0011297.htm',
			'9':  'http://publib.boulder.ibm.com/infocenter/db2luw/v9/topic/com.ibm.db2.udb.admin.doc/doc/r0011297.htm',
			'95': 'http://publib.boulder.ibm.com/infocenter/db2luw/v9r5/topic/com.ibm.db2.luw.sql.ref.doc/doc/r0011297.html',
		}[self.version]
		self.urls = {}

	def __iter__(self):
		for (schema, obj, url) in self._get_object_urls():
			logging.info('Retrieving descriptions for object %s.%s' % (schema, obj))
			f = self._get_xml(url)
			# The only reliable way to find the object description is to look
			# for a <div class="section"> element (for 9.5) and, if that fails
			# look for the first <p>aragraph (for 9 and 8).
			divs = [
				d for d in f.findall('.//div')
				if d.attrib.get('class') == 'section'
			]
			if len(divs) == 1:
				obj_desc = divs[0]
			else:
				obj_desc = f.find('.//p')
			if iselement(obj_desc):
				obj_desc = convert_desc(obj_desc)
			else:
				logging.error('Failed to find description for object %s.%s' % (schema, obj))
				obj_desc = ''
			table = f.find('.//table')
			part_count = 0
			part = 0
			columns = {}
			for row in table.find('tbody'):
				cells = row.findall('td')
				# Test for 4 or 5 data cells exactly. Anything else is either a
				# header or footnotes row and should be ignored (the SYSCAT
				# documentation uses 4 columns, SYSSTAT uses 5).
				# Workaround: The v8 InfoCenter has a bug in the PROCOPTIONS
				# documentation - the table rows erroneously contain 3 columns
				# although the table is 4 columns wide
				if 3 <= len(cells) <= 5:
					column = cells[0]
					# If a description spans multiple rows reuse the initial
					# cell
					if part == part_count:
						col_desc = cells[-1]
						part_count = int(col_desc.attrib.get('rowspan', '1'))
						part = 1
					else:
						part += 1
					# Strip all whitespace (newlines, space, etc.) - sometimes
					# the docs include essentially erroneous whitespace to
					# allow wrapping for really long column names
					column = re.sub(r'\s', '', convert_name(column))
					# Workaround: DB2 9.5 catalog spelling error: the
					# documentation lists SYSCAT.INDEXES.COLLECTSTATISTICS but
					# the column in the actual view in the database is called
					# SYSCAT.INDEXES.COLLECTSTATISTCS
					if (self.version == '95' and schema == 'SYSCAT' and
						obj == 'INDEXES' and column == 'COLLECTSTATISTICS'):
						column = 'COLLECTSTATISTCS'
					# Workaround: DB2 9.5 catalog spelling error: the
					# documentation lists SYSCAT.THRESHOLDS.QUEUEING, but the
					# column in the database is SYSCAT.THRESHOLDS.QUEUING
					if (self.version == '95' and schema == 'SYSCAT' and
						obj == 'THRESHOLDS' and column == 'QUEUEING'):
						column = 'QUEUING'
					# Workaround: DB2 9.5 catalog error: the documentation
					# lists SYSCAT.SECURITYPOLICIES.USERAUTHS but the column
					# doesn't exist in the database
					if (self.version == '95' and schema == 'SYSCAT' and
						obj == 'SECURITYPOLICIES' and column == 'USERAUTHS'):
						continue
					logging.debug('Retrieving description for column %s' % column)
					# For _really_ long descriptions, the docs sometimes use
					# separate consecutive "COLUMN_NAME (cont'd)" entries, so
					# we need to append to an existing description instead of
					# creating a new one
					if column[-8:] == "(cont'd)":
						column = column[:-8]
						columns[column] += convert_desc(col_desc)
					elif part_count > 1:
						columns[column] = '(%d/%d) %s' % (part, part_count, convert_desc(col_desc))
					else:
						columns[column] = convert_desc(col_desc)
			yield (schema, obj, obj_desc, columns)

	def _get_object_urls(self):
		logging.info('Retrieving table of all catalog views')
		d = {}
		f = self._get_xml(self.url)
		for anchor in f.findall('.//a'):
			if ('href' in anchor.attrib) and anchor.text and anchor.text.endswith(' catalog view'):
				url = urljoin(self.url, anchor.attrib['href'])
				obj = re.sub(' catalog view$', '', anchor.text)
				schema, obj = obj.split('.')
				d[(schema, obj)] = url
		for ((schema, obj), url) in sorted(d.iteritems()):
			yield (schema, obj, url)

	def _get_xml(self, url):
		logging.debug('Retrieving URL %s' % url)
		html = urlopen(url).read()
		# Workaround: ElementTree doesn't know about non-XML entities like
		# &nbsp; which occurs frequently in HTML, so we use a dirty hack here
		# to change them into numeric entities.
		html = html.replace('&nbsp;', '&#160;')
		# Workaround: Some of the InfoCenter HTML is buggy and causes
		# ElementTree's Expat-based parser to barf. Specifically, rel="search"
		# is erroneously repeated in the v9 catalog index, and v9.5 omits the
		# mandatory xml namespace from its root html element. We work around
		# these with a couple of extremely dirty hacks :-)
		html = html.replace('rel="search" ', '')
		html = html.replace('xmlns="http://www.w3.org/1999/xhtml"', '')
		return fromstring(html)


class XMLRetriever(object):
	"""Retrieves object descriptions from an XML file."""

	def __init__(self, xml):
		super(XMLRetriever, self).__init__()
		self.xml = xml

	def __iter__(self):
		if isinstance(self.xml, basestring):
			root = fromstring(xml)
		elif hasattr(self.xml, 'read'):
			# Assume self.xml is a file-like object
			root = fromstring(self.xml.read())
		if root.tag != 'database':
			raise Exception('Expected root element to be "database", but found "%s"' % root.tag)
		for schema in root.findall('schema'):
			if not 'name' in schema.attrib:
				raise Exception('Mandatory "name" attribute missing')
			for relation in schema.findall('relation'):
				if not 'name' in relation.attrib:
					raise Exception('Mandatory "name" attribute missing from relation in schema %s' % schema.attrib['name'])
				description = relation.find('description')
				if iselement(description):
					description = description.text or ''
				else:
					description = ''
				columns = dict(
					(column.attrib['name'], column.text or '')
					for column in relation.findall('column')
				)
				yield (schema.attrib['name'], relation.attrib['name'], description, columns)


class CommentGenerator(object):
	"""Generates COMMENT statements for applying descriptions to objects.
	
	This generator is used when you wish to store object descriptions in the
	standard system catalog. Note that this has an extremely limited length
	(254 characters on DB2 for LUW), and lacks facilities for storing certain
	descriptions (e.g. routine parameters).
	"""

	def __init__(self, retriever, terminator=';', maxlen=253):
		super(CommentGenerator, self).__init__()
		self.retriever = retriever
		self.terminator = terminator
		self.maxlen = maxlen

	def __iter__(self):
		for (schema, obj, desc, columns) in self.retriever:
			logging.info('Generating SQL for object %s.%s' % (schema, obj))
			if len(desc) > self.maxlen:
				logging.warning('Description for object %s.%s has been truncated' % (schema, obj))
				desc = desc[:self.maxlen - 3] + '...'
			yield encode('COMMENT ON TABLE %s.%s IS %s%s\n' % (
				quote_ident(schema),
				quote_ident(obj),
				quote_str(desc),
				self.terminator,
			))
			yield encode('COMMENT ON %s.%s (\n' % (
				quote_ident(schema),
				quote_ident(obj),
			))
			prefix = ''
			maxlen = max(
				len(quote_ident(column))
				for column in columns.iterkeys()
			)
			for (column, desc) in sorted(columns.iteritems()):
				logging.debug('Generating SQL for column %s' % column)
				if len(desc) > self.maxlen:
					logging.warning('Description for column %s.%s.%s has been truncated' % (schema, obj, column))
					desc = desc[:self.maxlen - 3] + '...'
				yield encode('%s\t%-*s IS %s\n' % (
					prefix,
					maxlen,
					quote_ident(column),
					quote_str(desc)
				))
				prefix = ','
			yield encode(')%s\n' % self.terminator)
			yield encode('\n')


class InsertGenerator(object):
	"""Generates INSERT statements for applying descriptions to objects.
	
	This generator is used when you wish to store object descriptions in the
	DOCCAT extension schema (see doccat_create.sql). DOCCAT descriptions can be
	considerably longer than SYSCAT descriptions (up to 32k characters long),
	and DOCCAT provides facilities for commenting routine parameters. However,
	being non-standard, third-party applications will ignore DOCCAT comments.
	"""

	def __init__(self, retriever, terminator=';'):
		super(InsertGenerator, self).__init__()
		self.retriever = retriever
		self.terminator = terminator

	def __iter__(self):
		for (schema, obj, desc, columns) in self.retriever:
			logging.info('Generating SQL for object %s.%s' % (schema, obj))
			yield encode('INSERT INTO DOCDATA.TABLES (TABSCHEMA, TABNAME, REMARKS)\n')
			yield encode('\tVALUES (%s, %s, %s)%s\n' % (
				quote_str(schema),
				quote_str(obj),
				quote_str(desc),
				self.terminator,
			))
			yield encode('INSERT INTO DOCDATA.COLUMNS (TABSCHEMA, TABNAME, COLNAME, REMARKS)\n')
			yield encode('\tSELECT %s, %s, COLNAME, REMARKS FROM (VALUES\n' % (
				quote_str(schema),
				quote_str(obj),
			))
			prefix = ''
			maxlen = max(
				len(quote_str(column)) + 1
				for column in columns.iterkeys()
			)
			for (column, desc) in sorted(columns.iteritems()):
				logging.debug('Generating SQL for column %s' % column)
				yield encode('%s\t\t(%-*s CLOB(%s))\n' % (
					prefix,
					maxlen,
					quote_str(column) + ',',
					quote_str(desc)
				))
				prefix = ','
			yield encode('\t) AS T(COLNAME, REMARKS)%s\n') % self.terminator
			yield encode('\n')


class XMLGenerator(object):
	"""Generates an XML tree associating objects with their descriptions.
	
	This generator is mostly for debugging purposes. Instead of outputting SQL,
	it returns an XML tree containing the object names and their descriptions.
	"""

	def __init__(self, retriever):
		super(XMLGenerator, self).__init__()
		self.retriever = retriever

	def __iter__(self):
		root = Element('database')
		root.attrib['name'] = ''
		schemas = {}
		objects = {}
		for (schema, obj, desc, columns) in self.retriever:
			try:
				schema_elem = schemas[schema]
			except KeyError:
				schema_elem = SubElement(root, 'schema')
				schema_elem.attrib['name'] = schema
				schemas[schema] = schema_elem
			try:
				obj_elem = objects[(schema, obj)]
			except KeyError:
				obj_elem = SubElement(schema_elem, 'relation')
				obj_elem.attrib['name'] = obj
				objects[(schema, obj)] = obj_elem
			SubElement(obj_elem, 'description').text = desc
			for (column, desc) in sorted(columns.iteritems()):
				col_elem = SubElement(obj_elem, 'column')
				col_elem.attrib['name'] = column
				col_elem.text = desc
		indent(root)
		yield encode('<?xml version="1.0" encoding="UTF-8" ?>\n')
		yield encode(tostring(root))


def parse_cmdline(args=None):
	parser = optparse.OptionParser(
		usage='%prog [options] source converter',
		version='%prog 1.0',
		description="""\
This utility generates SYSCAT (or DOCCAT) compatible comments from a variety of
sources, primarily various versions of the DB2 for LUW InfoCenter. The
mandatory "source" parameter specifies the source, and can be LUW8, LUW9, LUW95
(indicating a version of the InfoCenter), or XML (indicating the source is XML
passed to stdin). The "converter" parameter specifies the output format for the
documentation, and can be SYSCAT (generates SQL "COMMENT" statements), DOCCAT
(generates SQL "INSERT" statements targetting the DOCCAT extension schema), or
XML (generates XML for use with the XML source). The output is written to
stdout. Error messages and warnings are written to stderr.
""")
	parser.set_defaults(
		debug=False,
		logfile='',
		loglevel=logging.WARNING
	)
	parser.add_option('-q', '--quiet', dest='loglevel', action='store_const', const=logging.ERROR,
		help="""product less console output""")
	parser.add_option('-v', '--verbose', dest='loglevel', action='store_const', const=logging.INFO,
		help="""produce more console output""")
	parser.add_option('-l', '--logfile', dest='logfile',
		help="""log messages to the specified file""")
	parser.add_option('-D', '--debug', dest='debug', action='store_true',
		help="""enables debug mode""")
	if args is None:
		args = sys.argv[1:]
	(options, args) = parser.parse_args(args)
	# Set up some logging stuff
	console = logging.StreamHandler(sys.stderr)
	console.setFormatter(logging.Formatter('%(message)s'))
	console.setLevel(options.loglevel)
	logging.getLogger().addHandler(console)
	if options.logfile:
		logfile = logging.FileHandler(options.logfile)
		logfile.setFormatter(logging.Formatter('%(asctime)s, %(levelname)s, %(message)s'))
		logfile.setLevel(logging.DEBUG)
		logging.getLogger().addHandler(logfile)
	# Set up the exceptions hook for uncaught exceptions and the logging
	# levels if --debug was given
	if options.debug:
		console.setLevel(logging.DEBUG)
		logging.getLogger().setLevel(logging.DEBUG)
	else:
		logging.getLogger().setLevel(logging.INFO)
		sys.excepthook = production_excepthook
	# Check the mandatory args were given
	if len(args) != 2:
		parser.error('you must specify a source and a converter')
	return args

def production_excepthook(type, value, tb):
	"""Exception hook for non-debug mode."""
	# I/O errors should be simple to solve - no need to bother the user with
	# a full stack trace, just the error message will suffice
	if issubclass(type, IOError):
		logging.critical(str(value))
	else:
		# Otherwise, log the stack trace and the exception into the log file
		# for debugging purposes
		for line in traceback.format_exception(type, value, tb):
			for s in line.rstrip().split('\n'):
				logging.critical(s)
	# Pass a failure exit code to the calling shell
	sys.exit(1)

def main(source, converter):
	if source.startswith('LUW'):
		source = InfoCenterRetriever(version=source[3:])
	elif source == 'XML':
		source = XMLRetriever(xml=sys.stdin)
	else:
		raise Exception('invalid source specified')
	converter = {
		'SYSCAT': CommentGenerator,
		'DOCCAT': InsertGenerator,
		'XML':    XMLGenerator,
	}[converter](source)
	for line in converter:
		sys.stdout.write(line)


if __name__ == '__main__':
	main(*parse_cmdline())
