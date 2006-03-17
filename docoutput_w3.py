#!/usr/bin/env python
# $Header$
# vim: set noet sw=4 ts=4:

import sys
import os.path
import datetime
import logging
from docdatabase import DocDatabase
from doctablespace import DocTablespace
from docschema import DocSchema
from doctable import DocTable
from docview import DocView
from docfield import DocField
from docdatatype import DocDatatype
from doccheck import DocCheck
from docforeignkey import DocForeignKey
from docuniquekey import DocUniqueKey, DocPrimaryKey
from docfunction import DocFunction
from docparam import DocParam
from string import Template
from xml.sax.saxutils import quoteattr, escape
from sqltokenizer import DB2UDBSQLTokenizer
from sqlhighlighter import SQLHTMLHighlighter

__all__ = ['DocOutput']

# Utility routines for generating XHTML tags and sequences

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
	if content is None:
		contentStr = 'n/a'
	elif isinstance(content, datetime.datetime):
		contentStr = content.strftime("%Y-%m-%d %H:%M:%S")
	else:
		contentStr = str(content)
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
	"""Returns a unique filename for the specified object"""
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
	return makeTag('a', {
		'class': 'help-link-dark',
		'href': 'javascript:popup("%s","internal",%d,%d)' % (target, height, width),
	}, content)

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

# Output class

class DocOutput(object):
	"""HTML documentation writer class -- IBM w3 Intranet v8 standard"""

	def __init__(self, database, path="."):
		"""Initializes an instance of the class.

		DocOutput is a "one-shot" class in that initializing and instance also
		causes the documentation to be written by the instance (which is then
		usually discarded).
		"""
		self.path = path
		self.updated = datetime.date.today()
		self.template = Template(open("template_w3.html").read())
		self.tokenizer = DB2UDBSQLTokenizer()
		self.highlighter = SQLHTMLHighlighter(self.tokenizer)
		# Write the documentation files
		self.writeDatabase(database)
		for schema in database.schemas.itervalues():
			self.writeSchema(schema)
			for relation in schema.relations.itervalues():
				self.writeRelation(relation)
		#	for index in schema.indexes.itervalues():
		#		self.writeIndex(index)
		#	for routine in schema.routines.itervalues():
		#		self.writeRoutine(routine)
		for tablespace in database.tablespaces.itervalues():
			self.writeTablespace(tablespace)

	# Document construction methods

	def startDocument(self, object):
		"""Starts a new document for the specified object"""
		self.docobject = object
		self.docsections = []

	def addSection(self, id, title):
		"""Starts a new section in the current document with the specified id and title"""
		self.docsections.append({
			'id': id,
			'title': title,
			'content': ''
		})

	def addContent(self, content):
		"""Adds HTML content to the end of the current section"""
		self.docsections[-1]['content'] += content + '\n'

	def addPara(self, para):
		"""Adds a paragraph of text to the end of the current section"""
		self.addContent(makeTag('p', {}, escape(para)))

	def endDocument(self):
		"""Writes the current document to its destination file"""
		# Construct an index to place before the sections content
		index = '\n'.join([
			makeTag('li', {}, makeTag('a', {'href': '#' + section['id'], 'title': 'Jump to section'}, escape(section['title'])))
			for section in self.docsections
		])
		# Concatenate all document sections together with headers before each
		content = '\n'.join([
			'\n'.join([
				makeTag('div', {'class': 'hrule-dots'}, '&nbsp;'),
				makeTag('h2', {'id': section['id']}, escape(section['title'])),
				section['content'],
				makeTag('p', {}, makeTag('a', {'href': '#masthead', 'title': 'Jump to top'}, 'Back to top'))
			])
			for section in self.docsections
		])
		# Construct the body from a header, the index and the content from above
		body = '\n'.join([
			makeTag('h1', {}, escape(title(self.docobject))),
			makeTag('p', {}, escape(self.docobject.description)),
			makeTag('ul', {}, index),
			content
		])
		# Put the body and a number of other substitution values (mostly for
		# the metadata in the document HEAD) into a dictionary
		parameters = {
			'updated':      quoteattr(str(self.updated)),
			'updated_long': self.updated.strftime('%a, %d %b %Y'),
			'ownername':    quoteattr('Dave Hughes'),
			'owneremail':   quoteattr('dave_hughes@uk.ibm.com'),
			'description':  quoteattr(title(self.docobject)),
			'keywords':     quoteattr(keywords(self.docobject)),
			'sitetitle':    escape(title(self.docobject.database)),
			'doctitle':     escape(title(self.docobject)),
			'breadcrumbs':  breadcrumbs(self.docobject),
			'menu':         menu(self.docobject),
			'body':         body,
		}
		# Substitute all the values into the main template and write it to a file
		f = open(os.path.join(self.path, filename(self.docobject)), "w")
		try:
			f.write(self.template.substitute(parameters))
		finally:
			f.close()

	# Database object specific methods

	def writeDatabase(self, database):
		logging.info("Writing documentation for database to %s" % (filename(database)))
		schemas = [obj for (name, obj) in sorted(database.schemas.items(), key=lambda (name, obj):name)]
		tbspaces = [obj for (name, obj) in sorted(database.tablespaces.items(), key=lambda (name, obj):name)]
		self.startDocument(database)
		if len(schemas) > 0:
			self.addSection(id='schemas', title='Schemas')
			self.addPara("""The following table contains all schemas (logical
				object containers) in the database. Click on a schema name to
				view the documentation for that schema, including a list of all
				objects that exist within it.""")
			self.addContent(makeTable(
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
			self.addSection(id='tbspaces', title='Tablespaces')
			self.addPara("""The following table contains all tablespaces
				(physical object containers) in the database. Click on a
				tablespace name to view the documentation for that schema,
				including a list of all tables and/or indexes that exist within
				it.""")
			self.addContent(makeTable(
				head=[(
					"Name",
					"Description"
				)],
				data=[(
					linkTo(tbspace),
					escape(tbspace.description)
				) for tbspace in tbspaces]
			))
		self.endDocument()

	def writeSchema(self, schema):
		logging.info("Writing documentation for schema %s to %s" % (schema.name, filename(schema)))
		relations = [obj for (name, obj) in sorted(schema.relations.items(), key=lambda (name, obj): name)]
		routines = [obj for (name, obj) in sorted(schema.specificRoutines.items(), key=lambda (name, obj): name)]
		indexes = [obj for (name, obj) in sorted(schema.indexes.items(), key=lambda (name, obj): name)]
		self.startDocument(schema)
		if len(relations) > 0:
			self.addSection(id='relations', title='Relations')
			self.addPara("""The following table contains all the relations
				(tables and views) that the schema contains. Click on a
				relation name to view the documentation for that relation,
				including a list of all objects that exist within it, and that
				the relation references.""")
			self.addContent(makeTable(
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
			self.addSection(id='routines', title='Routines')
			self.addPara("""The following table contains all the routines
				(functions, stored procedures, and methods) that the schema
				contains. Click on a routine name to view the documentation for
				that routine.""")
			self.addContent(makeTable(
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
			self.addSection(id='indexes', title='Indexes')
			self.addPara("""The following table contains all the indexes that
				the schema contains. Click on an index name to view the
				documentation for that index.""")
			self.addContent(makeTable(
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
		self.endDocument()

	def writeTablespace(self, tbspace):
		logging.info("Writing documentation for tablespace %s to %s" % (tbspace.name, filename(tbspace)))
		tables = [obj for (name, obj) in sorted(tbspace.tables.items(), key=lambda (name, obj): name)]
		indexes = [obj for (name, obj) in sorted(tbspace.indexes.items(), key=lambda (name, obj): name)]
		self.startDocument(tbspace)
		if len(tables) > 0:
			self.addSection(id='tables', title='Tables')
			self.addPara("""The following table contains all the tables that
				the tablespace contains. Click on a table name to view the
				documentation for that table.""")
			self.addContent(makeTable(
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
			self.addSection(id='indexes', title='Indexes')
			self.addPara("""The following table contains all the indexes that
				the tablespace contains. Click on an index name to view the
				documentation for that index.""")
			self.addContent(makeTable(
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
		self.endDocument()

	def writeTable(self, table):
		logging.info("Writing documentation for table %s to %s" % (table.name, filename(table)))
		fields = [obj for (name, obj) in sorted(table.fields.items(), key=lambda (name, obj): name)]
		indexes = [obj for (name, obj) in sorted(table.indexes.items(), key=lambda (name, obj): name)]
		constraints = [obj for (name, obj) in sorted(table.constraints.items(), key=lambda (name, obj): name)]
		dependents = [obj for (name, obj) in sorted(table.dependents.items(), key=lambda (name, obj): name)]
		self.startDocument(table)
		self.addSection(id='attributes', title='Attributes')
		self.addPara("""The following table notes various "vital statistics"
			of the table (such as cardinality -- the number of rows in the
			table). Note that many of these attributes are only valid as of
			the last time that statistics were gathered for the table (this
			date is recorded in the table).""")
		if table.primaryKey is None:
			keyCount = 0
		else:
			keyCount = len(table.primaryKey.fields)
		self.addContent(makeTable(
			head=[(
				"Attribute",
				"Value",
				"Attribute",
				"Value"
			)],
			data=[
				(
					popupLink("created_w3.html", "Created"),
					table.created,
					popupLink("laststats_w3.html", "Last Statistics"),
					table.statsUpdated
				),
				(
					popupLink("cardinality_w3.html", "Cardinality"),
					table.cardinality,
					popupLink("createdby_w3.html", "Created By"),
					escape(table.definer)
				),
				(
					popupLink("colcount_w3.html", "# Columns"),
					len(table.fields),
					popupLink("keycolcount_w3.html", "# Key Columns"),
					keyCount
				),
				(
					popupLink("rowpages_w3.html", "Row Pages"),
					table.rowPages,
					popupLink("totalpages_w3.html", "Total Pages"),
					table.totalPages
				),
				(
					popupLink("dependentrel_w3.html", "Dependent Relations"),
					len(table.dependentList),
					popupLink("locksize_w3.html", "Lock Size"),
					escape(table.lockSize)
				),
				(
					popupLink("append_w3.html", "Append"),
					table.append,
					popupLink("volatile_w3.html", "Volatile"),
					table.volatile
				),
				(
					popupLink("compression_w3.html", "Value Compression"),
					table.compression,
					popupLink("clustered_w3.html", "Multi-dimensional Clustering"),
					table.clustered
				)
			]))
		if len(fields) > 0:
			self.addSection(id='fields', title='Field Descriptions')
			self.addPara("""The following table contains the fields of the table
				(in alphabetical order) along with the description of each field.
				For information on the structure and attributes of each field see
				the Field Schema section below.""")
			self.addContent(makeTable(
				head=[(
					"Name",
					"Description"
				)],
				data=[(
					escape(field.name),
					escape(field.description)
				) for field in fields]
			))
			self.addSection(id='field_schema', title='Field Schema')
			self.addPara("""The following table contains the attributes of the
				fields of the table (again, fields are in alphabetical order,
				though the # column indicates the 1-based position of the field
				within the table).""")
			self.addContent(makeTable(
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
			self.addSection('indexes', 'Index Descriptions')
			self.addPara("""The following table details the indexes defined
				against the table, including which fields each index targets.
				For more information about an individual index (e.g. statistics,
				directionality, etc.) click on the index name.""")
			self.addContent(makeTable(
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
			self.addSection('constraints', 'Constraints')
			self.addPara("""The following table details the constraints defined
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
			self.addContent(makeTable(
				head=[(
					"Name",
					"Type",
					"Fields",
					"Description"
				)],
				data=rows
			))
		if len(dependents) > 0:
			self.addSection('dependents', 'Dependent Relations')
			self.addPara("""The following table lists all relations (views or
				materialized query tables) which reference this table in their
				associated SQL statement.""")
			self.addContent(makeTable(
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
		self.addSection('tbspaces', 'Tablespaces')
		self.addPara("""This table uses the following tablespaces:""")
		self.addContent(makeTag(
			'ul', {}, '\n'.join([
				makeTag('li', {}, 'Data tablespace: ' + linkTo(table.dataTablespace)),
				makeTag('li', {}, 'Index tablespace: ' + linkTo(table.indexTablespace)),
				makeTag('li', {}, 'Long tablespace: ' + linkTo(table.longTablespace)),
			])
		))
		self.endDocument()

	def writeView(self, view):
		logging.info("Writing documentation for view %s to %s" % (view.name, filename(view)))
		fields = [obj for (name, obj) in sorted(view.fields.items(), key=lambda (name, obj): name)]
		dependencies = [obj for (name, obj) in sorted(view.dependencies.items(), key=lambda (name, obj): name)]
		dependents = [obj for (name, obj) in sorted(view.dependents.items(), key=lambda (name, obj): name)]
		self.startDocument(view)
		self.addSection(id='attributes', title='Attributes')
		self.addPara("""The following table notes various "vital statistics"
			of the view.""")
		self.addContent(makeTable(
			head=[(
				"Attribute",
				"Value",
				"Attribute",
				"Value"
			)],
			data=[
				(
					popupLink("created_w3.html", "Created"),
					view.created,
					popupLink("createdby_w3.html", "Created By"),
					escape(view.definer),
				),
				(
					popupLink("colcount_w3.html", "# Columns"),
					len(view.fields),
					popupLink("valid_w3.html", "Valid"),
					view.valid
				),
				(
					popupLink("readonly_w3.html", "Read Only"),
					view.readOnly,
					popupLink("checkoption_w3.html", "Check Option"),
					escape(view.check)
				),
				(
					popupLink("dependentrel_w3.html", "Dependent Relations"),
					len(view.dependentList),
					popupLink("dependenciesrel_w3.html", "Dependencies"),
					len(view.dependencyList)
				)
			]))
		if len(fields) > 0:
			self.addSection(id='fields', title='Field Descriptions')
			self.addPara("""The following table contains the fields of the view
				(in alphabetical order) along with the description of each field.
				For information on the structure and attributes of each field see
				the Field Schema section below.""")
			self.addContent(makeTable(
				head=[(
					"Name",
					"Description"
				)],
				data=[(
					escape(field.name),
					escape(field.description)
				) for field in fields]
			))
			self.addSection(id='field_schema', title='Field Schema')
			self.addPara("""The following table contains the attributes of the
				fields of the view (again, fields are in alphabetical order,
				though the # column indicates the 1-based position of the field
				within the view).""")
			self.addContent(makeTable(
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
		if len(dependents) > 0:
			self.addSection('dependents', 'Dependent Relations')
			self.addPara("""The following table lists all relations (views or
				materialized query tables) which reference this view in their
				associated SQL statement.""")
			self.addContent(makeTable(
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
			self.addSection('dependencies', 'Dependencies')
			self.addPara("""The following table lists all relations (tables,
				views, materialized query tables, etc.) which this view
				references in it's SQL statement.""")
			self.addContent(makeTable(
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
		self.addSection('sql', 'SQL Definition')
		self.addPara("""The SQL query which defines the view is given below.
			Note that, in the process of storing the definition of a view, DB2
			removes much of the formatting (e.g. link breaks). Hence the
			statement below may appear "messy".""")
		self.addContent(makeTag('div', {'class': 'sql'}, self.highlighter.highlight(view.sql)))
		self.endDocument()

	def writeRelation(self, relation):
		if isinstance(relation, DocTable):
			self.writeTable(relation)
		elif isinstance(relation, DocView):
			self.writeView(relation)
		self.endDocument()

def main():
	pass

if __name__ == "__main__":
	main()
