#!/bin/env python
# $Header$
# vim: set noet sw=4 ts=4:

import sys
import os.path
import logging
from htmlutils import *
from db.foreignkey import ForeignKey
from db.uniquekey import UniqueKey, PrimaryKey
from db.check import Check

def write(self, table):
	"""Outputs the documentation for a table object.

	Note that this function becomes the writeTable method of the
	Output class in the output.w3 module.
	"""
	logging.debug("Writing documentation for table %s to %s" % (table.name, filename(table)))
	fields = [obj for (name, obj) in sorted(table.fields.items(), key=lambda (name, obj): name)]
	indexes = [obj for (name, obj) in sorted(table.indexes.items(), key=lambda (name, obj): name)]
	constraints = [obj for (name, obj) in sorted(table.constraints.items(), key=lambda (name, obj): name)]
	dependents = [obj for (name, obj) in sorted(table.dependents.items(), key=lambda (name, obj): name)]
	doc = self.newDocument(table)
	doc.addSection(id='description', title='Description')
	doc.addContent('<p>%s</p>' % (self.formatDescription(table.description)))
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
				self.formatDescription(field.description)
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
				self.formatDescription(index.description)
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
			if isinstance(constraint, ForeignKey):
				expression = '<br />'.join([escape("%s -> %s" % (cfield.name, pfield.name)) for (cfield, pfield) in constraint.fields])
			elif isinstance(constraint, PrimaryKey) or isinstance(constraint, UniqueKey) or isinstance(constraint, Check):
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
				self.formatDescription(dep.description)
			) for dep in dependents]
		))
	doc.addSection('sql', 'SQL Definition')
	doc.addPara("""The SQL which created the table is given below.
		Note that this is not necessarily the same as the actual statement
		used to create the table (it has been reconstructed from the
		content of the system catalog tables and may differ in a number of
		areas).""")
	doc.addContent(makeTag('pre', {'class': 'sql'}, self.formatSql(table.createSql)))
	doc.write(os.path.join(self._path, filename(table)))

