#!/usr/bin/env python
# $Header$
# vim: set noet sw=4 ts=4:

import sys
import os.path
import datetime
import logging
from decimal import Decimal
from docdatabase import DocDatabase
from doctable import DocTable
from docview import DocView
from doccheck import DocCheck
from docforeignkey import DocForeignKey
from docuniquekey import DocUniqueKey, DocPrimaryKey
from docfunction import DocFunction
from string import Template
from xml.sax.saxutils import quoteattr, escape
from sqltokenizer import DB2UDBSQLTokenizer
from sqlhighlighter import SQLHTMLHighlighter
from sqlformatter import SQLFormatter

__all__ = ['DocOutput']

# Utility routines for generating XHTML tags and sequences

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

def makeTag(name, attrs={}, content="", optional=False):
	"""Generates a XHTML tag containing the specified attributes and content"""
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
		return makeTag(['td', 'th'][head], cellAttrs, content)
	else:
		return makeTag(['td', 'th'][head], cellAttrs, '&nbsp;')

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

# HTML construction methods

def filename(object):
	"""Returns a unique, but deterministic filename for the specified object"""
	return "%s.html" % (object.identifier)

def linkTo(object, attrs={}, qualifiedName=False):
	"""Generates an XHTML link to an object"""
	a = {'href': filename(object)}
	a.update(attrs)
	if qualifiedName:
		return makeTag('a', a, escape(object.qualifiedName))
	else:
		return makeTag('a', a, escape(object.name))

def popupLink(target, content, width=400, height=300):
	return makeTag('a', {'href': 'javascript:popup("%s","internal",%d,%d)' % (target, height, width)}, content)

def title(object):
	"""Returns a title string for the specified object"""
	if isinstance(object, DocDatabase):
		return "%s Documentation" % (object.name)
	else:
		return "%s Documentation - %s %s" % (object.database.name, object.typeName, object.qualifiedName)

def keywords(object):
	"""Returns a comma separated set of keywords for the specified object"""
	return "%s, %s, %s" % (object.typeName, object.name, object.qualifiedName)

def breadcrumbs(object):
	"""Returns a set of breadcrumb links for the specified object"""
	if object is None:
		return makeTag('a', {'href': 'index.html'}, 'Home')
	else:
		return breadcrumbs(object.parent) + " &raquo; " + makeTag('a', {'href': filename(object)}, '%s %s' % (object.typeName, object.name))

def menu(object):
	"""Returns a left-nav menu block for the specified object"""
	result = makeTag('a', {'href': 'index.html', 'id': 'site-home'}, 'Home') + '\n'
	if isinstance(object, DocDatabase):
		result += makeTag('a', {'href': filename(object), 'class': 'active'}, 'Documentation') + '\n'
	else:
		result += makeTag('a', {'href': filename(object.database)}, 'Documentation') + '\n'
	return makeTag('div', {'class': 'top-level'}, result)

class Document(object):
	def __init__(self, object):
		"""HTML document class.
		
		Represents the document to be produced for a given database object. The
		object parameter provides the database object that the document covers.
		"""
		super(Document, self).__init__()
		self._object = object
		self._sections = []
		self._updated = datetime.date.today()
		# XXX Figure out how to better search for the template
		self._template = Template(open("w3/template.html").read())

	def addSection(self, id, title):
		"""Starts a new section in the current document with the specified id and title"""
		self._sections.append({
			'id': id,
			'title': title,
			'content': ''
		})

	def addContent(self, content):
		"""Adds HTML content to the end of the current section"""
		self._sections[-1]['content'] += content + '\n'

	def addPara(self, para):
		"""Adds a paragraph of text to the end of the current section"""
		self.addContent(makeTag('p', {}, escape(para)))
	
	def write(self, filename):
		"""Writes the document to the specified file"""
		# Construct an index to place before the sections content
		index = '\n'.join([
			makeTag('li', {}, makeTag('a', {'href': '#' + section['id'], 'title': 'Jump to section'}, escape(section['title'])))
			for section in self._sections
		])
		# Concatenate all document sections together with headers before each
		content = '\n'.join([
			'\n'.join([
				makeTag('div', {'class': 'hrule-dots'}, '&nbsp;'),
				makeTag('h2', {'id': section['id']}, escape(section['title'])),
				section['content'],
				makeTag('p', {}, makeTag('a', {'href': '#masthead', 'title': 'Jump to top'}, 'Back to top'))
			])
			for section in self._sections
		])
		# Construct the body from a header, the index and the content from above
		body = '\n'.join([
			makeTag('h1', {}, escape(title(self._object))),
			makeTag('p', {}, escape(self._object.description)),
			makeTag('ul', {}, index),
			content
		])
		# Put the body and a number of other substitution values (mostly for
		# the metadata in the document HEAD) into a dictionary
		parameters = {
			'updated':      quoteattr(str(self._updated)),
			'updated_long': self._updated.strftime('%a, %d %b %Y'),
			'ownername':    quoteattr('Dave Hughes'),
			'owneremail':   quoteattr('dave_hughes@uk.ibm.com'),
			'description':  quoteattr(title(self._object)),
			'keywords':     quoteattr(keywords(self._object)),
			'sitetitle':    escape(title(self._object.database)),
			'doctitle':     escape(title(self._object)),
			'breadcrumbs':  breadcrumbs(self._object),
			'menu':         menu(self._object),
			'body':         body,
		}
		# Substitute all the values into the main template and write it to a file
		open(filename, "w").write(self._template.substitute(parameters))

class DocOutput(object):
	"""HTML documentation writer class -- IBM w3 Intranet v8 standard"""

	def __init__(self, database, path="."):
		"""Initializes an instance of the class.

		DocOutput is a "one-shot" class in that initializing and instance also
		causes the documentation to be written by the instance (which is then
		usually discarded).
		"""
		super(DocOutput, self).__init__()
		self.path = path
		self.tokenizer = DB2UDBSQLTokenizer()
		self.highlighter = SQLHTMLHighlighter(self.tokenizer)
		self.formatter = SQLFormatter(self.tokenizer)
		# Write the documentation files
		self.writeDatabase(database)
		for schema in database.schemas.itervalues():
			self.writeSchema(schema)
			for relation in schema.relations.itervalues():
				self.writeRelation(relation)
				if isinstance(relation, DocTable):
					for constraint in relation.constraints.itervalues():
						self.writeConstraint(constraint)
			for index in schema.indexes.itervalues():
				self.writeIndex(index)
		#	for routine in schema.routines.itervalues():
		#		self.writeRoutine(routine)
		for tablespace in database.tablespaces.itervalues():
			self.writeTablespace(tablespace)

	def writeDatabase(self, database):
		logging.debug("Writing documentation for database to %s" % (filename(database)))
		schemas = [obj for (name, obj) in sorted(database.schemas.items(), key=lambda (name, obj):name)]
		tbspaces = [obj for (name, obj) in sorted(database.tablespaces.items(), key=lambda (name, obj):name)]
		doc = Document(database)
		if len(schemas) > 0:
			doc.addSection(id='schemas', title='Schemas')
			doc.addPara("""The following table contains all schemas (logical
				object containers) in the database. Click on a schema name to
				view the documentation for that schema, including a list of all
				objects that exist within it.""")
			doc.addContent(makeTable(
				head=[(
					"Name",
					"Description"
				)],
				data=[(
					linkTo(schema),
					escape(schema.description)
				) for schema in schemas]
			))
		if len(tbspaces) > 0:
			doc.addSection(id='tbspaces', title='Tablespaces')
			doc.addPara("""The following table contains all tablespaces
				(physical object containers) in the database. Click on a
				tablespace name to view the documentation for that schema,
				including a list of all tables and/or indexes that exist within
				it.""")
			doc.addContent(makeTable(
				head=[(
					"Name",
					"Description"
				)],
				data=[(
					linkTo(tbspace),
					escape(tbspace.description)
				) for tbspace in tbspaces]
			))
		doc.write(os.path.join(self.path, filename(database)))

	def writeSchema(self, schema):
		logging.debug("Writing documentation for schema %s to %s" % (schema.name, filename(schema)))
		relations = [obj for (name, obj) in sorted(schema.relations.items(), key=lambda (name, obj): name)]
		routines = [obj for (name, obj) in sorted(schema.specificRoutines.items(), key=lambda (name, obj): name)]
		indexes = [obj for (name, obj) in sorted(schema.indexes.items(), key=lambda (name, obj): name)]
		doc = Document(schema)
		if len(relations) > 0:
			doc.addSection(id='relations', title='Relations')
			doc.addPara("""The following table contains all the relations
				(tables and views) that the schema contains. Click on a
				relation name to view the documentation for that relation,
				including a list of all objects that exist within it, and that
				the relation references.""")
			doc.addContent(makeTable(
				head=[(
					"Name",
					"Type",
					"Description"
				)],
				data=[(
					linkTo(relation),
					escape(relation.typeName),
					escape(relation.description)
				) for relation in relations]
			))
		if len(routines) > 0:
			doc.addSection(id='routines', title='Routines')
			doc.addPara("""The following table contains all the routines
				(functions, stored procedures, and methods) that the schema
				contains. Click on a routine name to view the documentation for
				that routine.""")
			doc.addContent(makeTable(
				head=[(
					"Name",
					"Type",
					"Description"
				)],
				data=[(
					linkTo(routine),
					escape(routine.typeName),
					escape(routine.description)
				) for routine in routines]
			))
		if len(indexes) > 0:
			doc.addSection(id='indexes', title='Indexes')
			doc.addPara("""The following table contains all the indexes that
				the schema contains. Click on an index name to view the
				documentation for that index.""")
			doc.addContent(makeTable(
				head=[(
					"Name",
					"Applies To",
					"Description")],
				data=[(
					linkTo(index),
					linkTo(index.table, qualifiedName=True),
					escape(index.description)
				) for index in indexes]
			))
		doc.write(os.path.join(self.path, filename(schema)))

	def writeTablespace(self, tbspace):
		logging.debug("Writing documentation for tablespace %s to %s" % (tbspace.name, filename(tbspace)))
		tables = [obj for (name, obj) in sorted(tbspace.tables.items(), key=lambda (name, obj): name)]
		indexes = [obj for (name, obj) in sorted(tbspace.indexes.items(), key=lambda (name, obj): name)]
		doc = Document(tbspace)
		if len(tables) > 0:
			doc.addSection(id='tables', title='Tables')
			doc.addPara("""The following table contains all the tables that
				the tablespace contains. Click on a table name to view the
				documentation for that table.""")
			doc.addContent(makeTable(
				head=[(
					"Name",
					"Description"
				)],
				data=[(
					linkTo(table, qualifiedName=True),
					escape(table.description)
				) for table in tables]
			))
		if len(indexes) > 0:
			doc.addSection(id='indexes', title='Indexes')
			doc.addPara("""The following table contains all the indexes that
				the tablespace contains. Click on an index name to view the
				documentation for that index.""")
			doc.addContent(makeTable(
				head=[(
					"Name",
					"Applies To",
					"Description"
				)],
				data=[(
					linkTo(index, qualifiedName=True),
					linkTo(index.table, qualifiedName=True),
					escape(index.description)
				) for index in indexes]
			))
		doc.write(os.path.join(self.path, filename(tbspace)))

	def writeTable(self, table):
		logging.debug("Writing documentation for table %s to %s" % (table.name, filename(table)))
		fields = [obj for (name, obj) in sorted(table.fields.items(), key=lambda (name, obj): name)]
		indexes = [obj for (name, obj) in sorted(table.indexes.items(), key=lambda (name, obj): name)]
		constraints = [obj for (name, obj) in sorted(table.constraints.items(), key=lambda (name, obj): name)]
		dependents = [obj for (name, obj) in sorted(table.dependents.items(), key=lambda (name, obj): name)]
		doc = Document(table)
		doc.addSection(id='attributes', title='Attributes')
		doc.addPara("""The following table notes various "vital statistics"
			of the table (such as cardinality -- the number of rows in the
			table). Note that many of these attributes are only valid as of
			the last time that statistics were gathered for the table (this
			date is recorded in the table).""")
		if table.primaryKey is None:
			keyCount = 0
		else:
			keyCount = len(table.primaryKey.fields)
		doc.addContent(makeTable(
			head=[(
				"Attribute",
				"Value",
				"Attribute",
				"Value"
			)],
			data=[
				(
					'Data Tablespace',
					linkTo(table.dataTablespace),
					'Index Tablespace',
					linkTo(table.indexTablespace),
				),
				(
					'Long Tablespace',
					linkTo(table.longTablespace),
					popupLink("clustered.html", makeTag('acronym', {'title': 'Multi-Dimensional Clustering'}, 'MDC')),
					table.clustered,
				),
				(
					popupLink("created.html", "Created"),
					table.created,
					popupLink("laststats.html", "Last Statistics"),
					table.statsUpdated,
				),
				(
					popupLink("createdby.html", "Created By"),
					escape(table.definer),
					popupLink("cardinality.html", "Cardinality"),
					table.cardinality,
				),
				(
					popupLink("keycolcount.html", "# Key Columns"),
					keyCount,
					popupLink("colcount.html", "# Columns"),
					len(table.fields),
				),
				(
					popupLink("rowpages.html", "Row Pages"),
					table.rowPages,
					popupLink("totalpages.html", "Total Pages"),
					table.totalPages,
				),
				(
					popupLink("dependentrel.html", "Dependent Relations"),
					len(table.dependentList),
					popupLink("locksize.html", "Lock Size"),
					escape(table.lockSize),
				),
				(
					popupLink("append.html", "Append"),
					table.append,
					popupLink("volatile.html", "Volatile"),
					table.volatile,
				),
			]))
		if len(fields) > 0:
			doc.addSection(id='fields', title='Field Descriptions')
			doc.addPara("""The following table contains the fields of the table
				(in alphabetical order) along with the description of each field.
				For information on the structure and attributes of each field see
				the Field Schema section below.""")
			doc.addContent(makeTable(
				head=[(
					"Name",
					"Description"
				)],
				data=[(
					escape(field.name),
					escape(field.description)
				) for field in fields]
			))
			doc.addSection(id='field_schema', title='Field Schema')
			doc.addPara("""The following table contains the attributes of the
				fields of the table (again, fields are in alphabetical order,
				though the # column indicates the 1-based position of the field
				within the table).""")
			doc.addContent(makeTable(
				head=[(
					"#",
					"Name",
					"Type",
					"Nulls",
					"Key Pos",
					"Cardinality"
				)],
				data=[(
					field.position + 1,
					escape(field.name),
					escape(field.datatypeStr),
					field.nullable,
					field.keyIndex,
					field.cardinality
				) for field in fields]
			))
		if len(indexes) > 0:
			doc.addSection('indexes', 'Index Descriptions')
			doc.addPara("""The following table details the indexes defined
				against the table, including which fields each index targets.
				For more information about an individual index (e.g. statistics,
				directionality, etc.) click on the index name.""")
			doc.addContent(makeTable(
				head=[(
					"Name",
					"Unique",
					"Fields",
					"Sort Order",
					"Description"
				)],
				data=[(
					linkTo(index, qualifiedName=True),
					index.unique,
					'<br />'.join([escape(ixfield.name) for (ixfield, ixorder) in index.fieldList]),
					'<br />'.join([escape(ixorder) for (ixfield, ixorder) in index.fieldList]),
					escape(index.description)
				) for index in indexes]
			))
		if len(constraints) > 0:
			doc.addSection('constraints', 'Constraints')
			doc.addPara("""The following table details the constraints defined
				against the table, including which fields each constraint
				limits or tests. For more information about an individual
				constraint click on the constraint name.""")
			rows = []
			for constraint in constraints:
				if isinstance(constraint, DocForeignKey):
					expression = '<br />'.join([escape("%s -> %s" % (cfield.name, pfield.name)) for (cfield, pfield) in constraint.fields])
				elif isinstance(constraint, DocPrimaryKey) or isinstance(constraint, DocUniqueKey) or isinstance(constraint, DocCheck):
					expression = '<br />'.join([escape(cfield.name) for cfield in constraint.fields])
				else:
					expression = '&nbsp;'
				rows.append((linkTo(constraint), constraint.typeName, expression, constraint.description))
			doc.addContent(makeTable(
				head=[(
					"Name",
					"Type",
					"Fields",
					"Description"
				)],
				data=rows
			))
		if len(dependents) > 0:
			doc.addSection('dependents', 'Dependent Relations')
			doc.addPara("""The following table lists all relations (views or
				materialized query tables) which reference this table in their
				associated SQL statement.""")
			doc.addContent(makeTable(
			    head=[(
					"Name",
					"Type",
					"Description"
				)],
			    data=[(
					linkTo(dep, qualifiedName=True),
					escape(dep.typeName),
					escape(dep.description)
				) for dep in dependents]
			))
		doc.addSection('sql', 'SQL Definition')
		doc.addPara("""The SQL which created the table is given below.
			Note that this is not necessarily the same as the actual statement
			used to create the table (it has been reconstructed from the
			content of the system catalog tables and may differ in a number of
			areas).""")
		doc.addContent(makeTag('pre', {'class': 'sql'}, self.highlighter.highlight(self.formatter.parse(table.createSql))))
		doc.write(os.path.join(self.path, filename(table)))

	def writeView(self, view):
		logging.debug("Writing documentation for view %s to %s" % (view.name, filename(view)))
		fields = [obj for (name, obj) in sorted(view.fields.items(), key=lambda (name, obj): name)]
		dependencies = [obj for (name, obj) in sorted(view.dependencies.items(), key=lambda (name, obj): name)]
		dependents = [obj for (name, obj) in sorted(view.dependents.items(), key=lambda (name, obj): name)]
		doc = Document(view)
		doc.addSection(id='attributes', title='Attributes')
		doc.addPara("""The following table notes various "vital statistics"
			of the view.""")
		doc.addContent(makeTable(
			head=[(
				"Attribute",
				"Value",
				"Attribute",
				"Value"
			)],
			data=[
				(
					popupLink("created.html", "Created"),
					view.created,
					popupLink("createdby.html", "Created By"),
					escape(view.definer),
				),
				(
					popupLink("colcount.html", "# Columns"),
					len(view.fields),
					popupLink("valid.html", "Valid"),
					view.valid,
				),
				(
					popupLink("readonly.html", "Read Only"),
					view.readOnly,
					popupLink("checkoption.html", "Check Option"),
					escape(view.check),
				),
				(
					popupLink("dependentrel.html", "Dependent Relations"),
					len(view.dependentList),
					popupLink("dependenciesrel.html", "Dependencies"),
					len(view.dependencyList),
				)
			]))
		if len(fields) > 0:
			doc.addSection(id='fields', title='Field Descriptions')
			doc.addPara("""The following table contains the fields of the view
				(in alphabetical order) along with the description of each field.
				For information on the structure and attributes of each field see
				the Field Schema section below.""")
			doc.addContent(makeTable(
				head=[(
					"Name",
					"Description"
				)],
				data=[(
					escape(field.name),
					escape(field.description)
				) for field in fields]
			))
			doc.addSection(id='field_schema', title='Field Schema')
			doc.addPara("""The following table contains the attributes of the
				fields of the view (again, fields are in alphabetical order,
				though the # column indicates the 1-based position of the field
				within the view).""")
			doc.addContent(makeTable(
				head=[(
					"#",
					"Name",
					"Type",
					"Nulls"
				)],
				data=[(
					field.position + 1,
					escape(field.name),
					escape(field.datatypeStr),
					field.nullable
				) for field in fields]
			))
		if len(dependents) > 0:
			doc.addSection('dependents', 'Dependent Relations')
			doc.addPara("""The following table lists all relations (views or
				materialized query tables) which reference this view in their
				associated SQL statement.""")
			doc.addContent(makeTable(
			    head=[(
					"Name",
					"Type",
					"Description"
				)],
			    data=[(
					linkTo(dep, qualifiedName=True),
					escape(dep.typeName),
					escape(dep.description)
				) for dep in dependents]
			))
		if len(dependencies) > 0:
			doc.addSection('dependencies', 'Dependencies')
			doc.addPara("""The following table lists all relations (tables,
				views, materialized query tables, etc.) which this view
				references in it's SQL statement.""")
			doc.addContent(makeTable(
				head=[(
					"Name",
					"Type",
					"Description"
				)],
				data=[(
					linkTo(dep, qualifiedName=True),
					escape(dep.typeName),
					escape(dep.description)
				) for dep in dependencies]
			))
		doc.addSection('sql', 'SQL Definition')
		doc.addPara("""The SQL which created the view is given below.
			Note that, in the process of storing the definition of a view, DB2
			removes much of the formatting, hence the formatting in the 
			statement below (which this system attempts to reconstruct) is
			not necessarily the formatting of the original statement.""")
		doc.addContent(makeTag('pre', {'class': 'sql'}, self.highlighter.highlight(self.formatter.parse(view.createSql))))
		doc.write(os.path.join(self.path, filename(view)))

	def writeRelation(self, relation):
		if isinstance(relation, DocTable):
			self.writeTable(relation)
		elif isinstance(relation, DocView):
			self.writeView(relation)

	def writeIndex(self, index):
		logging.debug("Writing documentation for index %s to %s" % (index.name, filename(index)))
		position = 0
		fields = []
		for (field, ordering) in index.fieldList:
			fields.append((field, ordering, position))
			position += 1
		fields = sorted(fields, key=lambda(field, ordering, position): field.name)
		doc = Document(index)
		doc.addSection(id='attributes', title='Attributes')
		doc.addPara("""The following table notes various "vital statistics"
			of the index.""")
		if not index.clusterFactor is None:
			clusterRatio = index.clusterFactor # XXX Convert as necessary
		else:
			clusterRatio = index.clusterRatio
		doc.addContent(makeTable(
			head=[(
				"Attribute",
				"Value",
				"Attribute",
				"Value"
			)],
			data=[
				(
					'Table',
					linkTo(index.table),
					'Tablespace',
					linkTo(index.tablespace),
				),
				(
					popupLink("created.html", "Created"),
					index.created,
					popupLink("laststats.html", "Last Statistics"),
					index.statsUpdated,
				),
				(
					popupLink("createdby.html", "Created By"),
					escape(index.definer),
					popupLink("colcount.html", "# Columns"),
					len(fields),
				),
				(
					popupLink("unique.html", "Unique"),
					index.unique,
					popupLink("reversescans.html", "Reverse Scans"),
					index.reverseScans,
				),
				(
					popupLink("cardinality.html", "Cardinality"),
					'<br />'.join(
						[formatContent(index.cardinality[0])] + 
						['1..%s: %s' % (keynum + 1, formatContent(card)) for (keynum, card) in enumerate(index.cardinality[1])]
					),
					popupLink("levels.html", "Levels"),
					index.levels,
				),
				(
					popupLink("leafpages.html", "Leaf Pages"),
					index.leafPages,
					popupLink("sequentialpages.html", "Sequential Pages"),
					index.sequentialPages,
				),
				(
					popupLink("clusterratio.html", "Cluster Ratio"),
					clusterRatio, # see above
					popupLink("density.html", "Density"),
					index.density,
				),
			]))
		if len(fields) > 0:
			doc.addSection(id='fields', title='Fields')
			doc.addPara("""The following table contains the fields of the index
				(in alphabetical order) along with the position of the field in
				the index, the ordering of the field (Ascending or Descending)
				and the description of the field.""")
			doc.addContent(makeTable(
				head=[(
					"#",
					"Name",
					"Order",
					"Description"
				)],
				data=[(
					position + 1,
					escape(field.name),
					ordering,
					escape(field.description)
				) for (field, ordering, position) in fields]
			))
		doc.addSection('sql', 'SQL Definition')
		doc.addPara("""The SQL which created the index is given below.
			Note that this is not necessarily the same as the actual statement
			used to create the index (it has been reconstructed from the
			content of the system catalog tables and may differ in a number of
			areas).""")
		doc.addContent(makeTag('pre', {'class': 'sql'}, self.highlighter.highlight(self.formatter.parse(index.createSql))))
		doc.write(os.path.join(self.path, filename(index)))
	
	def writeUniqueKey(self, key):
		logging.debug("Writing documentation for unique key %s to %s" % (key.name, filename(key)))
		position = 0
		fields = []
		for field in key.fields:
			fields.append((field, position))
			position += 1
		fields = sorted(fields, key=lambda(field, position): field.name)
		doc = Document(key)
		doc.addSection(id='attributes', title='Attributes')
		doc.addPara("""The following table notes various "vital statistics"
			of the unique key.""")
		doc.addContent(makeTable(
			head=[(
				"Attribute",
				"Value",
				"Attribute",
				"Value"
			)],
			data=[
				(
					popupLink("createdby.html", "Created By"),
					escape(key.definer),
					popupLink("colcount.html", "# Columns"),
					len(fields),
				),
			]))
		if len(fields) > 0:
			doc.addSection(id='fields', title='Fields')
			doc.addPara("""The following table contains the fields of the key
				(in alphabetical order) along with the position of the field in
				the key, and the description of the field in the key's table.""")
			doc.addContent(makeTable(
				head=[(
					"#",
					"Field",
					"Description"
				)],
				data=[(
					position + 1,
					escape(field.name),
					escape(field.description)
				) for (field, position) in fields]
			))
		doc.addSection('sql', 'SQL Definition')
		doc.addPara("""The SQL which can be used to create the key is given
			below. Note that this is not necessarily the same as the actual
			statement used to create the key (it has been reconstructed from
			the content of the system catalog tables and may differ in a number
			of areas).""")
		doc.addContent(makeTag('pre', {'class': 'sql'}, self.highlighter.highlight(self.formatter.parse(key.createSql))))
		doc.write(os.path.join(self.path, filename(key)))

	def writeForeignKey(self, key):
		logging.debug("Writing documentation for foreign key %s to %s" % (key.name, filename(key)))
		position = 0
		fields = []
		for (field1, field2) in key.fields:
			fields.append((field1, field2, position))
			position += 1
		fields = sorted(fields, key=lambda(field1, field2, position): field1.name)
		doc = Document(key)
		doc.addSection(id='attributes', title='Attributes')
		doc.addPara("""The following table notes various "vital statistics"
			of the foreign key.""")
		doc.addContent(makeTable(
			head=[(
				"Attribute",
				"Value",
				"Attribute",
				"Value"
			)],
			data=[
				(
					'Referenced Table',
					linkTo(key.refTable),
					'Referenced Key',
					linkTo(key.refKey),
				),
				(
					popupLink("created.html", "Created"),
					key.created,
					popupLink("createdby.html", "Created By"),
					escape(key.definer),
				),
				(
					popupLink("enforced.html", "Enforced"),
					key.enforced,
					popupLink("queryoptimize.html", "Query Optimizing"),
					key.queryOptimize,
				),
				(
					popupLink("deleterule.html", "Delete Rule"),
					key.deleteRule,
					popupLink("updaterule.html", "Update Rule"),
					key.updateRule,
				),
			]))
		if len(fields) > 0:
			doc.addSection(id='fields', title='Fields')
			doc.addPara("""The following table contains the fields of the key
				(in alphabetical order) along with the position of the field in
				the key, the field in the parent table that is referenced by
				the key, and the description of the field in the key's table.""")
			doc.addContent(makeTable(
				head=[(
					"#",
					"Field",
					"Parent",
					"Description"
				)],
				data=[(
					position + 1,
					escape(field1.name),
					escape(field2.name),
					escape(field1.description)
				) for (field1, field2, position) in fields]
			))
		doc.addSection('sql', 'SQL Definition')
		doc.addPara("""The SQL which can be used to create the key is given
			below. Note that this is not necessarily the same as the actual
			statement used to create the key (it has been reconstructed from
			the content of the system catalog tables and may differ in a number
			of areas).""")
		doc.addContent(makeTag('pre', {'class': 'sql'}, self.highlighter.highlight(self.formatter.parse(key.createSql))))
		doc.write(os.path.join(self.path, filename(key)))


	def writeCheck(self, check):
		logging.debug("Writing documentation for check constraint %s to %s" % (check.name, filename(check)))
		fields = sorted(list(check.fields), key=lambda(field): field.name)
		doc = Document(check)
		doc.addSection(id='attributes', title='Attributes')
		doc.addPara("""The following table notes various "vital statistics"
			of the check.""")
		doc.addContent(makeTable(
			head=[(
				"Attribute",
				"Value",
				"Attribute",
				"Value"
			)],
			data=[
				(
					popupLink("created.html", "Created"),
					check.created,
					popupLink("createdby.html", "Created By"),
					escape(check.definer),
				),
				(
					popupLink("enforced.html", "Enforced"),
					check.enforced,
					popupLink("queryoptimize.html", "Query Optimizing"),
					check.queryOptimize,
				),
			]))
		if len(fields) > 0:
			doc.addSection(id='fields', title='Fields')
			doc.addPara("""The following table contains the fields that the
				check references in it's SQL expression, and the description of
				the field in the check's table.""")
			doc.addContent(makeTable(
				head=[(
					"Field",
					"Description"
				)],
				data=[(
					escape(field.name),
					escape(field.description)
				) for field in fields]
			))
		doc.addSection('sql', 'SQL Definition')
		doc.addPara("""The SQL which can be used to create the check is given
			below. Note that this is not necessarily the same as the actual
			statement used to create the check (it has been reconstructed from
			the content of the system catalog tables and may differ in a number
			of areas).""")
		doc.addContent(makeTag('pre', {'class': 'sql'}, self.highlighter.highlight(self.formatter.parse(check.createSql))))
		doc.write(os.path.join(self.path, filename(check)))

	def writeConstraint(self, constraint):
		if isinstance(constraint, DocUniqueKey):
			self.writeUniqueKey(constraint)
		elif isinstance(constraint, DocForeignKey):
			self.writeForeignKey(constraint)
		elif isinstance(constraint, DocCheck):
			self.writeCheck(constraint)

def main():
	pass

if __name__ == "__main__":
	main()
