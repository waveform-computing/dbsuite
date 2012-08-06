# vim: set et sw=4 sts=4:

# Copyright 2012 Dave Hughes.
#
# This file is part of dbsuite.
#
# dbsuite is free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# dbsuite is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# dbsuite.  If not, see <http://www.gnu.org/licenses/>.

"""Implements a set of classes for converting table and column comments.

This module provides a set of utility classes which can be used to extract
basic table and column comments from a variety of sources, and convert them
into a variety of output formats. They are used to form the basis of the
db2convdoc utility.
"""

from __future__ import (
    unicode_literals,
    print_function,
    absolute_import,
    division,
    )

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
            re.sub(ur'\.$', '', convert_desc(li))
            for li in elem.findall('li')
        ]) + '. '
    elif elem.tag == 'ol':
        result = ', '.join([
            '%d. %s' % (ix, re.sub(ur'\.$', '', convert_desc(li)))
            for (ix, li) in enumerate(elem.findall('li'))
        ]) + '. '
    elif elem.tag == 'span' and elem.attrib.get('id') == 'changed':
        result = ''
    else:
        result = elem.text or ''
        for e in elem:
            result += convert_desc(e) + (e.tail or '')
        result = re.sub(ur'\s+', ' ', result)
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
            '81': 'http://publib.boulder.ibm.com/infocenter/db2luw/v8/topic/com.ibm.db2.udb.doc/admin/r0011297.htm',
            '82': 'http://publib.boulder.ibm.com/infocenter/db2luw/v8/topic/com.ibm.db2.udb.doc/admin/r0011297.htm',
            '91': 'http://publib.boulder.ibm.com/infocenter/db2luw/v9/topic/com.ibm.db2.udb.admin.doc/doc/r0011297.htm',
            '95': 'http://publib.boulder.ibm.com/infocenter/db2luw/v9r5/topic/com.ibm.db2.luw.sql.ref.doc/doc/r0011297.html',
            '97': 'http://publib.boulder.ibm.com/infocenter/db2luw/v9r7/topic/com.ibm.db2.luw.sql.ref.doc/doc/r0011297.html',
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
                    column = re.sub(ur'\s', '', convert_name(column))
                    # Workaround: DB2 9.5 and 9.7 catalog spelling error: the
                    # documentation lists SYSCAT.INDEXES.COLLECTSTATISTICS but
                    # the column in the actual view in the database is called
                    # SYSCAT.INDEXES.COLLECTSTATISTCS
                    if (self.version in ('95', '97') and schema == 'SYSCAT' and
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
        f = urlopen(url)
        html = f.read().decode(f.info().getparam('charset') or 'UTF-8')
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
        return fromstring(html.encode('UTF-8'))


class InfoCenterSource81(InfoCenterSource):
    """Retrieves object descriptions from the DB2 v8.1 for LUW InfoCenter."""
    def __init__(self):
        super(InfoCenterSource81, self).__init__(version='81')

class InfoCenterSource82(InfoCenterSource):
    """Retrieves object descriptions from the DB2 v8.2 for LUW InfoCenter."""
    def __init__(self):
        super(InfoCenterSource82, self).__init__(version='82')

class InfoCenterSource91(InfoCenterSource):
    """Retrieves object descriptions from the DB2 v9.1 for LUW InfoCenter."""
    def __init__(self):
        super(InfoCenterSource91, self).__init__(version='91')

class InfoCenterSource95(InfoCenterSource):
    """Retrieves object descriptions from the DB2 v9.5 for LUW InfoCenter."""
    def __init__(self):
        super(InfoCenterSource95, self).__init__(version='95')

class InfoCenterSource97(InfoCenterSource):
    """Retrieves object descriptions from the DB2 v9.7 for LUW InfoCenter."""
    def __init__(self):
        super(InfoCenterSource97, self).__init__(version='97')


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
            logging.info('Generating SQL for object %s.%s' % (schema, obj))
            if len(desc) > self.maxlen:
                logging.warning('Description for object %s.%s has been truncated' % (schema, obj))
                desc = desc[:self.maxlen - 3] + '...'
            yield 'COMMENT ON TABLE %s.%s IS %s%s\n' % (
                format_ident(schema),
                format_ident(obj),
                quote_str(desc),
                self.terminator,
            )
            yield 'COMMENT ON %s.%s (\n' % (
                format_ident(schema),
                format_ident(obj),
            )
            prefix = ''
            maxlen = max(
                len(format_ident(column))
                for column in columns.iterkeys()
            )
            for (column, desc) in sorted(columns.iteritems()):
                logging.debug('Generating SQL for column %s' % column)
                if len(desc) > self.maxlen:
                    logging.warning('Description for column %s.%s.%s has been truncated' % (schema, obj, column))
                    desc = desc[:self.maxlen - 3] + '...'
                yield '%s\t%-*s IS %s\n' % (
                    prefix,
                    maxlen,
                    format_ident(column),
                    quote_str(desc)
                )
                prefix = ','
            yield ')%s\n' % self.terminator
            yield '\n'


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

    def __init__(self, retriever, terminator=';', schema='DOCDATA'):
        super(InsertConverter, self).__init__()
        self.retriever = retriever
        self.terminator = terminator
        self.schema = schema

    def __iter__(self):
        for (schema, obj, desc, columns) in self.retriever:
            logging.info('Generating SQL for object %s.%s' % (schema, obj))
            yield 'INSERT INTO %s.TABLES (TABSCHEMA, TABNAME, REMARKS)\n' % format_ident(self.schema)
            yield '\tVALUES (%s, %s, CLOB(%s))%s\n' % (
                quote_str(schema),
                quote_str(obj),
                quote_str(desc),
                self.terminator,
            )
            yield 'INSERT INTO %s.COLUMNS (TABSCHEMA, TABNAME, COLNAME, REMARKS)\n' % format_ident(self.schema)
            yield '\tSELECT %s, %s, COLNAME, REMARKS FROM (VALUES\n' % (
                quote_str(schema),
                quote_str(obj),
            )
            prefix = ''
            maxlen = max(
                len(quote_str(column)) + 1
                for column in columns.iterkeys()
            )
            for (column, desc) in sorted(columns.iteritems()):
                logging.debug('Generating SQL for column %s' % column)
                yield '%s\t\t(%-*s CLOB(%s))\n' % (
                    prefix,
                    maxlen,
                    quote_str(column) + ',',
                    quote_str(desc)
                )
                prefix = ','
            yield '\t) AS T(COLNAME, REMARKS)%s\n' % self.terminator
            yield '\n'


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

    def __init__(self, retriever, terminator=';', schema='DOCCAT'):
        super(UpdateConverter, self).__init__()
        self.retriever = retriever
        self.terminator = terminator
        self.schema = schema

    def __iter__(self):
        for (schema, obj, desc, columns) in self.retriever:
            logging.info('Generating SQL for object %s.%s' % (schema, obj))
            yield 'UPDATE %s.TABLES\n' % format_ident(self.schema)
            yield 'SET\n'
            yield '\tREMARKS = CLOB(%s)\n' % quote_str(desc)
            yield 'WHERE\n'
            yield '\tTABSCHEMA = %s\n' % quote_str(schema)
            yield '\tAND TABNAME = %s%s\n' % (quote_str(obj), self.terminator)
            yield 'UPDATE %s.COLUMNS\n' % format_ident(self.schema)
            yield 'SET\n'
            yield '\tREMARKS = CASE COLNAME\n'
            maxlen = max(
                len(quote_str(column)) + 1
                for column in columns.iterkeys()
            )
            for (column, desc) in sorted(columns.iteritems()):
                logging.debug('Generating SQL for column %s' % column)
                yield '\t\tWHEN %-*s THEN CLOB(%s)\n' % (
                    maxlen,
                    quote_str(column),
                    quote_str(desc)
                )
            yield '\tEND\n'
            yield 'WHERE\n'
            yield '\tTABSCHEMA = %s\n' % quote_str(schema)
            yield '\tAND TABNAME = %s%s\n' % (quote_str(obj), self.terminator)
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

    def __init__(self, retriever, terminator=';', schema='DOCDATA'):
        super(MergeConverter, self).__init__()
        self.retriever = retriever
        self.terminator = terminator
        self.schema = schema

    def __iter__(self):
        for (schema, obj, desc, columns) in self.retriever:
            logging.info('Generating SQL for object %s.%s' % (schema, obj))
            yield 'MERGE INTO %s.TABLES AS T\n' % format_ident(self.schema)
            yield 'USING TABLE(VALUES\n'
            yield '\t(%s, %s, CLOB(%s))\n' % (quote_str(schema), quote_str(obj), quote_str(desc))
            yield ') AS S(TABSCHEMA, TABNAME, REMARKS)\n'
            yield 'ON T.TABSCHEMA = S.TABSCHEMA\n'
            yield 'AND T.TABNAME = S.TABNAME\n'
            yield 'WHEN MATCHED THEN\n'
            yield '\tUPDATE REMARKS = S.REMARKS\n'
            yield 'WHEN NOT MATCHED THEN\n'
            yield '\tINSERT (TABSCHEMA, TABNAME, REMARKS)\n'
            yield '\tVALUES (S.TABSCHEMA, S.TABNAME, S.REMARKS)%s\n' % self.terminator
            yield 'MERGE INTO %s.COLUMNS AS T\n' % format_ident(self.schema)
            yield 'USING TABLE(VALUES\n'
            prefix = ''
            maxlen = max(
                len(quote_str(column)) + 1
                for column in columns.iterkeys()
            )
            for (column, desc) in sorted(columns.iteritems()):
                logging.debug('Generating SQL for column %s' % column)
                yield '%s\t(%s, %s, %-*s CLOB(%s))\n' % (
                    prefix,
                    quote_str(schema),
                    quote_str(obj),
                    maxlen,
                    quote_str(column) + ',',
                    quote_str(desc)
                )
                prefix = ','
            yield ') AS S(TABSCHEMA, TABNAME, COLNAME, REMARKS)\n'
            yield 'ON T.TABSCHEMA = S.TABSCHEMA\n'
            yield 'AND T.TABNAME = S.TABNAME\n'
            yield 'AND T.COLNAME = S.COLNAME\n'
            yield 'WHEN MATCHED THEN\n'
            yield '\tUPDATE REMARKS = S.REMARKS\n'
            yield 'WHEN NOT MATCHED THEN\n'
            yield '\tINSERT (TABSCHEMA, TABNAME, COLNAME, REMARKS)\n'
            yield '\tVALUES (S.TABSCHEMA, S.TABNAME, S.COLNAME, S.REMARKS)%s\n' % self.terminator
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
        yield '<?xml version="1.0" encoding="UTF-8" ?>\n'
        # Ensure the output is in UTF-8 encoding
        s = tostring(root)
        if isinstance(s, unicode):
            s = s.encode('UTF-8')
        yield s


