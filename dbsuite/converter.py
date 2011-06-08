# vim: set noet sw=4 ts=4:

"""Implements a set of classes for converting table and column comments.

This module provides a set of utility classes which can be used to extract
basic table and column comments from a variety of sources, and convert them
into a variety of output formats. They are used to form the basis of the
db2convdoc utility.
"""

import re
import locale
import logging
from urllib2 import urlopen
from urlparse import urljoin
from dbsuite.parser import quote_str, format_ident
from dbsuite.etree import fromstring, tostring, iselement, Element, SubElement, indent


__all__ = [
	'InfoCenterSource',
	'XMLSource',
	'CommentConverter',
	'InsertConverter',
	'UpdateConverter',
	'MergeConverter',
	'XMLConverter',
]


def convert_name(elem):
	"""Extracts a name from an element.

	This routine is used to extract names from the InfoCenter documentation.
	The documentation often includes footnotes or modification indicators
	within the name column of a table, hence we need to be careful when
	extracting the name that we don't pick up this extraneous information.
	Specifically we extract only text which exists as a direct child of elem,
	not text owned by any child elements.
	"""
	result = elem.text or u''
	for child in elem:
		result += child.tail or u''
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
	if elem.tag == u'ul':
		result = u', '.join([
			re.sub(ur'\.$', u'', convert_desc(li))
			for li in elem.findall(u'li')
		]) + u'. '
	elif elem.tag == u'ol':
		result = u', '.join([
			u'%d. %s' % (ix, re.sub(ur'\.$', u'', convert_desc(li)))
			for (ix, li) in enumerate(elem.findall(u'li'))
		]) + u'. '
	elif elem.tag == u'span' and elem.attrib.get(u'id') == u'changed':
		result = u''
	else:
		result = elem.text or u''
		for e in elem:
			result += convert_desc(e) + (e.tail or u'')
		result = re.sub(ur'\s+', u' ', result)
	return result.strip()


class InfoCenterSource(object):
	"""Retrieves object descriptions from a DB2 for LUW InfoCenter.

	This source retrieves pages from the system catalog documentation in the
	DB2 for LUW InfoCenter (the version is specified as part of the source
	name). This can be used to generate documentation for the SYSCAT and
	SYSSTAT schemas in a DB2 for LUW database.
	"""

	def __init__(self, version):
		super(InfoCenterSource, self).__init__()
		self.version = version
		self.url = {
			u'81': u'http://publib.boulder.ibm.com/infocenter/db2luw/v8/topic/com.ibm.db2.udb.doc/admin/r0011297.htm',
			u'82': u'http://publib.boulder.ibm.com/infocenter/db2luw/v8/topic/com.ibm.db2.udb.doc/admin/r0011297.htm',
			u'91': u'http://publib.boulder.ibm.com/infocenter/db2luw/v9/topic/com.ibm.db2.udb.admin.doc/doc/r0011297.htm',
			u'95': u'http://publib.boulder.ibm.com/infocenter/db2luw/v9r5/topic/com.ibm.db2.luw.sql.ref.doc/doc/r0011297.html',
			u'97': u'http://publib.boulder.ibm.com/infocenter/db2luw/v9r7/topic/com.ibm.db2.luw.sql.ref.doc/doc/r0011297.html',
		}[self.version]
		self.urls = {}

	def __iter__(self):
		for (schema, obj, url) in self._get_object_urls():
			logging.info(u'Retrieving descriptions for object %s.%s' % (schema, obj))
			f = self._get_xml(url)
			# The only reliable way to find the object description is to look
			# for a <div class="section"> element (for 9.5) and, if that fails
			# look for the first <p>aragraph (for 9 and 8).
			divs = [
				d for d in f.findall(u'.//div')
				if d.attrib.get(u'class') == u'section'
			]
			if len(divs) == 1:
				obj_desc = divs[0]
			else:
				obj_desc = f.find(u'.//p')
			if iselement(obj_desc):
				obj_desc = convert_desc(obj_desc)
			else:
				logging.error(u'Failed to find description for object %s.%s' % (schema, obj))
				obj_desc = u''
			table = f.find(u'.//table')
			part_count = 0
			part = 0
			columns = {}
			for row in table.find(u'tbody'):
				cells = row.findall(u'td')
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
						part_count = int(col_desc.attrib.get(u'rowspan', u'1'))
						part = 1
					else:
						part += 1
					# Strip all whitespace (newlines, space, etc.) - sometimes
					# the docs include essentially erroneous whitespace to
					# allow wrapping for really long column names
					column = re.sub(ur'\s', '', convert_name(column))
					# Workaround: DB2 9.5 and 9.7 catalog spelling error: the
					# documentation lists SYSCAT.INDEXES.COLLECTSTATISTICS but
					# the column in the actual view in the database is called
					# SYSCAT.INDEXES.COLLECTSTATISTCS
					if (self.version in (u'95', u'97') and schema == u'SYSCAT' and
						obj == u'INDEXES' and column == u'COLLECTSTATISTICS'):
						column = u'COLLECTSTATISTCS'
					# Workaround: DB2 9.5 catalog spelling error: the
					# documentation lists SYSCAT.THRESHOLDS.QUEUEING, but the
					# column in the database is SYSCAT.THRESHOLDS.QUEUING
					if (self.version == u'95' and schema == u'SYSCAT' and
						obj == u'THRESHOLDS' and column == u'QUEUEING'):
						column = u'QUEUING'
					# Workaround: DB2 9.5 catalog error: the documentation
					# lists SYSCAT.SECURITYPOLICIES.USERAUTHS but the column
					# doesn't exist in the database
					if (self.version == u'95' and schema == u'SYSCAT' and
						obj == u'SECURITYPOLICIES' and column == u'USERAUTHS'):
						continue
					logging.debug(u'Retrieving description for column %s' % column)
					# For _really_ long descriptions, the docs sometimes use
					# separate consecutive "COLUMN_NAME (cont'd)" entries, so
					# we need to append to an existing description instead of
					# creating a new one
					if column[-8:] == u"(cont'd)":
						column = column[:-8]
						columns[column] += convert_desc(col_desc)
					elif part_count > 1:
						columns[column] = u'(%d/%d) %s' % (part, part_count, convert_desc(col_desc))
					else:
						columns[column] = convert_desc(col_desc)
			yield (schema, obj, obj_desc, columns)

	def _get_object_urls(self):
		logging.info(u'Retrieving table of all catalog views')
		d = {}
		f = self._get_xml(self.url)
		for anchor in f.findall(u'.//a'):
			if (u'href' in anchor.attrib) and anchor.text and anchor.text.endswith(u' catalog view'):
				url = urljoin(self.url, anchor.attrib[u'href'])
				obj = re.sub(u' catalog view$', '', anchor.text)
				schema, obj = obj.split('.')
				d[(schema, obj)] = url
		for ((schema, obj), url) in sorted(d.iteritems()):
			yield (schema, obj, url)

	def _get_xml(self, url):
		logging.debug(u'Retrieving URL %s' % url)
		f = urlopen(url)
		html = f.read().decode(f.info().getparam('charset') or 'UTF-8')
		# Workaround: ElementTree doesn't know about non-XML entities like
		# &nbsp; which occurs frequently in HTML, so we use a dirty hack here
		# to change them into numeric entities.
		html = html.replace(u'&nbsp;', u'&#160;')
		# Workaround: Some of the InfoCenter HTML is buggy and causes
		# ElementTree's Expat-based parser to barf. Specifically, rel="search"
		# is erroneously repeated in the v9 catalog index, and v9.5 omits the
		# mandatory xml namespace from its root html element. We work around
		# these with a couple of extremely dirty hacks :-)
		html = html.replace(u'rel="search" ', u'')
		html = html.replace(u'xmlns="http://www.w3.org/1999/xhtml"', u'')
		return fromstring(html.encode('UTF-8'))


class InfoCenterSource81(InfoCenterSource):
	"""Retrieves object descriptions from the DB2 v8.1 for LUW InfoCenter."""
	def __init__(self):
		super(InfoCenterSource81, self).__init__(version=u'81')

class InfoCenterSource82(InfoCenterSource):
	"""Retrieves object descriptions from the DB2 v8.2 for LUW InfoCenter."""
	def __init__(self):
		super(InfoCenterSource82, self).__init__(version=u'82')

class InfoCenterSource91(InfoCenterSource):
	"""Retrieves object descriptions from the DB2 v9.1 for LUW InfoCenter."""
	def __init__(self):
		super(InfoCenterSource91, self).__init__(version=u'91')

class InfoCenterSource95(InfoCenterSource):
	"""Retrieves object descriptions from the DB2 v9.5 for LUW InfoCenter."""
	def __init__(self):
		super(InfoCenterSource95, self).__init__(version=u'95')

class InfoCenterSource97(InfoCenterSource):
	"""Retrieves object descriptions from the DB2 v9.7 for LUW InfoCenter."""
	def __init__(self):
		super(InfoCenterSource97, self).__init__(version=u'97')


class XMLSource(object):
	"""Retrieves object descriptions from an XML file.

	This source reads stdin expecting to find XML containing table and column
	descriptions. The expected structure can be seen by using the XML converter
	with one of the other sources. This source is primarily intended as a
	debugging tool.
	"""

	def __init__(self, xml):
		super(XMLSource, self).__init__()
		self.xml = xml

	def __iter__(self):
		if isinstance(self.xml, basestring):
			root = fromstring(xml)
		elif hasattr(self.xml, u'read'):
			# Assume self.xml is a file-like object
			root = fromstring(self.xml.read())
		if root.tag != u'database':
			raise Exception(u'Expected root element to be "database", but found "%s"' % root.tag)
		for schema in root.findall(u'schema'):
			if not u'name' in schema.attrib:
				raise Exception(u'Mandatory "name" attribute missing')
			for relation in schema.findall(u'relation'):
				if not u'name' in relation.attrib:
					raise Exception(u'Mandatory "name" attribute missing from relation in schema %s' % schema.attrib[u'name'])
				description = relation.find(u'description')
				if iselement(description):
					description = description.text or u''
				else:
					description = u''
				columns = dict(
					(column.attrib[u'name'], column.text or u'')
					for column in relation.findall(u'column')
				)
				yield (schema.attrib[u'name'], relation.attrib[u'name'], description, columns)


class CommentConverter(object):
	"""Generates COMMENT statements for applying descriptions to objects.

	This converter is used when you wish to store object descriptions in the
	standard system catalog. Note that this has an extremely limited length
	(254 characters on DB2 for LUW), and lacks facilities for storing certain
	descriptions (e.g. routine parameters).
	"""

	def __init__(self, retriever, terminator=';', maxlen=253):
		super(CommentConverter, self).__init__()
		self.retriever = retriever
		self.terminator = terminator
		self.maxlen = maxlen

	def __iter__(self):
		for (schema, obj, desc, columns) in self.retriever:
			logging.info(u'Generating SQL for object %s.%s' % (schema, obj))
			if len(desc) > self.maxlen:
				logging.warning(u'Description for object %s.%s has been truncated' % (schema, obj))
				desc = desc[:self.maxlen - 3] + u'...'
			yield u'COMMENT ON TABLE %s.%s IS %s%s\n' % (
				format_ident(schema),
				format_ident(obj),
				quote_str(desc),
				self.terminator,
			)
			yield u'COMMENT ON %s.%s (\n' % (
				format_ident(schema),
				format_ident(obj),
			)
			prefix = ''
			maxlen = max(
				len(format_ident(column))
				for column in columns.iterkeys()
			)
			for (column, desc) in sorted(columns.iteritems()):
				logging.debug(u'Generating SQL for column %s' % column)
				if len(desc) > self.maxlen:
					logging.warning(u'Description for column %s.%s.%s has been truncated' % (schema, obj, column))
					desc = desc[:self.maxlen - 3] + u'...'
				yield u'%s\t%-*s IS %s\n' % (
					prefix,
					maxlen,
					format_ident(column),
					quote_str(desc)
				)
				prefix = u','
			yield u')%s\n' % self.terminator
			yield u'\n'


class InsertConverter(object):
	"""Generates INSERT statements for applying descriptions to objects.

	This converter is used when you wish to store object descriptions in the
	DOCCAT extension schema (see doccat_create.sql). DOCCAT descriptions can be
	considerably longer than SYSCAT descriptions (up to 32k characters long),
	and DOCCAT provides facilities for commenting routine parameters. However,
	being non-standard, third-party applications will ignore DOCCAT comments.

	This converter outputs INSERT statements which target the DOCDATA tables
	which underly the DOCCAT views. This is intended for situations where no
	comments exist (in the DOCCAT views) for the source objects.
	"""

	def __init__(self, retriever, terminator=u';', schema=u'DOCDATA'):
		super(InsertConverter, self).__init__()
		self.retriever = retriever
		self.terminator = terminator
		self.schema = schema

	def __iter__(self):
		for (schema, obj, desc, columns) in self.retriever:
			logging.info(u'Generating SQL for object %s.%s' % (schema, obj))
			yield u'INSERT INTO %s.TABLES (TABSCHEMA, TABNAME, REMARKS)\n' % format_ident(self.schema)
			yield u'\tVALUES (%s, %s, CLOB(%s))%s\n' % (
				quote_str(schema),
				quote_str(obj),
				quote_str(desc),
				self.terminator,
			)
			yield u'INSERT INTO %s.COLUMNS (TABSCHEMA, TABNAME, COLNAME, REMARKS)\n' % format_ident(self.schema)
			yield u'\tSELECT %s, %s, COLNAME, REMARKS FROM (VALUES\n' % (
				quote_str(schema),
				quote_str(obj),
			)
			prefix = ''
			maxlen = max(
				len(quote_str(column)) + 1
				for column in columns.iterkeys()
			)
			for (column, desc) in sorted(columns.iteritems()):
				logging.debug(u'Generating SQL for column %s' % column)
				yield u'%s\t\t(%-*s CLOB(%s))\n' % (
					prefix,
					maxlen,
					quote_str(column) + u',',
					quote_str(desc)
				)
				prefix = u','
			yield u'\t) AS T(COLNAME, REMARKS)%s\n' % self.terminator
			yield u'\n'


class UpdateConverter(object):
	"""Generates UPDATE statements for applying descriptions to objects.

	This converter is used when you wish to store object descriptions in the
	DOCCAT extension schema (see doccat_create.sql). DOCCAT descriptions can be
	considerably longer than SYSCAT descriptions (up to 32k characters long),
	and DOCCAT provides facilities for commenting routine parameters. However,
	being non-standard, third-party applications will ignore DOCCAT comments.

	This converter outputs UPDATE statements which target DOCCAT's views
	directly. The INSTEAD OF triggers on these views will convert the UPDATEs
	into whatever operation is required on the underlying tables. Therefore
	this converter is safe to use whether or not you have any existing comments
	on the source objects, although the resulting SQL will be rather slower
	than the "insert" or "merge" converters.
	"""

	def __init__(self, retriever, terminator=u';', schema=u'DOCCAT'):
		super(UpdateConverter, self).__init__()
		self.retriever = retriever
		self.terminator = terminator
		self.schema = schema

	def __iter__(self):
		for (schema, obj, desc, columns) in self.retriever:
			logging.info(u'Generating SQL for object %s.%s' % (schema, obj))
			yield u'UPDATE %s.TABLES\n' % format_ident(self.schema)
			yield u'SET\n'
			yield u'\tREMARKS = CLOB(%s)\n' % quote_str(desc)
			yield u'WHERE\n'
			yield u'\tTABSCHEMA = %s\n' % quote_str(schema)
			yield u'\tAND TABNAME = %s%s\n' % (quote_str(obj), self.terminator)
			yield u'UPDATE %s.COLUMNS\n' % format_ident(self.schema)
			yield u'SET\n'
			yield u'\tREMARKS = CASE COLNAME\n'
			maxlen = max(
				len(quote_str(column)) + 1
				for column in columns.iterkeys()
			)
			for (column, desc) in sorted(columns.iteritems()):
				logging.debug('Generating SQL for column %s' % column)
				yield u'\t\tWHEN %-*s THEN CLOB(%s)\n' % (
					maxlen,
					quote_str(column),
					quote_str(desc)
				)
			yield u'\tEND\n'
			yield u'WHERE\n'
			yield u'\tTABSCHEMA = %s\n' % quote_str(schema)
			yield u'\tAND TABNAME = %s%s\n' % (quote_str(obj), self.terminator)
			yield '\n'


class MergeConverter(object):
	"""Generates MERGE statements for applying descriptions to objects.

	This converter is used when you wish to store object descriptions in the
	DOCCAT extension schema (see doccat_create.sql). DOCCAT descriptions can be
	considerably longer than SYSCAT descriptions (up to 32k characters long),
	and DOCCAT provides facilities for commenting routine parameters. However,
	being non-standard, third-party applications will ignore DOCCAT comments.

	This converter outputs MERGE statements which target the DOCDATA tables
	which underly the DOCCAT views. Due to the flexible nature of the MERGE
	statement, the generated SQL should work regardless of whether comments
	already exist for the source objects. However, the generated SQL is quite
	complex and won't be quite as quick as output of the "insert" converter.
	"""

	def __init__(self, retriever, terminator=u';', schema=u'DOCDATA'):
		super(MergeConverter, self).__init__()
		self.retriever = retriever
		self.terminator = terminator
		self.schema = schema

	def __iter__(self):
		for (schema, obj, desc, columns) in self.retriever:
			logging.info(u'Generating SQL for object %s.%s' % (schema, obj))
			yield u'MERGE INTO %s.TABLES AS T\n' % format_ident(self.schema)
			yield u'USING TABLE(VALUES\n'
			yield u'\t(%s, %s, CLOB(%s))\n' % (quote_str(schema), quote_str(obj), quote_str(desc))
			yield u') AS S(TABSCHEMA, TABNAME, REMARKS)\n'
			yield u'ON T.TABSCHEMA = S.TABSCHEMA\n'
			yield u'AND T.TABNAME = S.TABNAME\n'
			yield u'WHEN MATCHED THEN\n'
			yield u'\tUPDATE REMARKS = S.REMARKS\n'
			yield u'WHEN NOT MATCHED THEN\n'
			yield u'\tINSERT (TABSCHEMA, TABNAME, REMARKS)\n'
			yield u'\tVALUES (S.TABSCHEMA, S.TABNAME, S.REMARKS)%s\n' % self.terminator
			yield u'MERGE INTO %s.COLUMNS AS T\n' % format_ident(self.schema)
			yield u'USING TABLE(VALUES\n'
			prefix = ''
			maxlen = max(
				len(quote_str(column)) + 1
				for column in columns.iterkeys()
			)
			for (column, desc) in sorted(columns.iteritems()):
				logging.debug('Generating SQL for column %s' % column)
				yield u'%s\t(%s, %s, %-*s CLOB(%s))\n' % (
					prefix,
					quote_str(schema),
					quote_str(obj),
					maxlen,
					quote_str(column) + ',',
					quote_str(desc)
				)
				prefix = ','
			yield u') AS S(TABSCHEMA, TABNAME, COLNAME, REMARKS)\n'
			yield u'ON T.TABSCHEMA = S.TABSCHEMA\n'
			yield u'AND T.TABNAME = S.TABNAME\n'
			yield u'AND T.COLNAME = S.COLNAME\n'
			yield u'WHEN MATCHED THEN\n'
			yield u'\tUPDATE REMARKS = S.REMARKS\n'
			yield u'WHEN NOT MATCHED THEN\n'
			yield u'\tINSERT (TABSCHEMA, TABNAME, COLNAME, REMARKS)\n'
			yield u'\tVALUES (S.TABSCHEMA, S.TABNAME, S.COLNAME, S.REMARKS)%s\n' % self.terminator
			yield '\n'


class XMLConverter(object):
	"""Generates an XML tree associating objects with their descriptions.

	This converter is mostly for debugging purposes. Instead of outputting SQL,
	it returns an XML document containing the object names and their
	descriptions.
	"""

	def __init__(self, retriever):
		super(XMLConverter, self).__init__()
		self.retriever = retriever

	def __iter__(self):
		root = Element(u'database')
		root.attrib[u'name'] = u''
		schemas = {}
		objects = {}
		for (schema, obj, desc, columns) in self.retriever:
			try:
				schema_elem = schemas[schema]
			except KeyError:
				schema_elem = SubElement(root, u'schema')
				schema_elem.attrib[u'name'] = schema
				schemas[schema] = schema_elem
			try:
				obj_elem = objects[(schema, obj)]
			except KeyError:
				obj_elem = SubElement(schema_elem, u'relation')
				obj_elem.attrib[u'name'] = obj
				objects[(schema, obj)] = obj_elem
			SubElement(obj_elem, u'description').text = desc
			for (column, desc) in sorted(columns.iteritems()):
				col_elem = SubElement(obj_elem, u'column')
				col_elem.attrib[u'name'] = column
				col_elem.text = desc
		indent(root)
		yield '<?xml version="1.0" encoding="UTF-8" ?>\n'
		# Ensure the output is in UTF-8 encoding
		s = tostring(root)
		if isinstance(s, unicode):
			s = s.encode('UTF-8')
		yield s


