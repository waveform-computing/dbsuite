#!/bin/env python
# $Header$
# vim: set noet sw=4 ts=4:

from db.table import Table
from output.html.w3.document import W3Document

class W3TableDocument(W3Document):
	def __init__(self, site, table):
		assert isinstance(table, Table)
		super(W3TableDocument, self).__init__(site, table)

	def create_sections(self):
		fields = [obj for (name, obj) in sorted(self.dbobject.fields.items(), key=lambda (name, obj): name)]
		indexes = [obj for (name, obj) in sorted(self.dbobject.indexes.items(), key=lambda (name, obj): name)]
		constraints = [obj for (name, obj) in sorted(self.dbobject.constraints.items(), key=lambda (name, obj): name)]
		triggers = [obj for (name, obj) in sorted(self.dbobject.triggers.items(), key=lambda (name, obj): name)]
		dependents = [obj for (name, obj) in sorted(self.dbobject.dependents.items(), key=lambda (name, obj): name)]
		olstyle = {'style': 'list-style-type: none; padding: 0; margin: 0;'}
		self.section('description', 'Description')
		self.add(self.p(self.format_description(self.dbobject.description)))
		self.section('attributes', 'Attributes')
		self.add(self.p("""The following table notes various "vital statistics"
			of the table (such as cardinality -- the number of rows in the
			table). Note that many of these attributes are only valid as of the
			last time that statistics were gathered for the table (this date is
			recorded in the table)."""))
		if self.dbobject.primaryKey is None:
			key_count = 0
		else:
			key_count = len(self.dbobject.primaryKey.fields)
		self.add(self.table(
			head=[(
				"Attribute",
				"Value",
				"Attribute",
				"Value"
			)],
			data=[
				(
					'Data Tablespace',
					self.a_to(self.dbobject.dataTablespace),
					'Index Tablespace',
					self.a_to(self.dbobject.indexTablespace),
				),
				(
					'Long Tablespace',
					self.a_to(self.dbobject.longTablespace),
					self.a('clustered.html', 'MDC', popup=True),
					self.dbobject.clustered,
				),
				(
					self.a('created.html', 'Created', popup=True),
					self.dbobject.created,
					self.a('laststats.html', 'Last Statistics', popup=True),
					self.dbobject.statsUpdated,
				),
				(
					self.a('createdby.html', 'Created By', popup=True),
					self.dbobject.definer,
					self.a('cardinality.html', 'Cardinality', popup=True),
					self.dbobject.cardinality,
				),
				(
					self.a('keycolcount.html', '# Key Columns', popup=True),
					key_count,
					self.a('colcount.html', '# Columns', popup=True),
					len(self.dbobject.fields),
				),
				(
					self.a('rowpages.html', 'Row Pages', popup=True),
					self.dbobject.rowPages,
					self.a('totalpages.html', 'Total Pages', popup=True),
					self.dbobject.totalPages,
				),
				(
					self.a('dependentrel.html', 'Dependent Relations', popup=True),
					len(self.dbobject.dependentList),
					self.a('locksize.html', 'Lock Size', popup=True),
					self.dbobject.lockSize,
				),
				(
					self.a('append.html', 'Append', popup=True),
					self.dbobject.append,
					self.a('volatile.html', 'Volatile', popup=True),
					self.dbobject.volatile,
				),
			]
		))
		if len(fields) > 0:
			self.section('field_desc', 'Field Descriptions')
			self.add(self.p("""The following table contains the fields of the
				table (in alphabetical order) along with the description of
				each field.  For information on the structure and attributes of
				each field see the Field Schema section below."""))
			self.add(self.table(
				head=[(
					"Name",
					"Description"
				)],
				data=[(
					field.name,
					self.format_description(field.description, firstline=True)
				) for field in fields]
			))
			self.section('field_schema', 'Field Schema')
			self.add(self.p("""The following table contains the attributes of
				the fields of the table (again, fields are in alphabetical
				order, though the # column indicates the 1-based position of
				the field within the table)."""))
			self.add(self.table(
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
					field.name,
					field.datatypeStr,
					field.nullable,
					field.keyIndex,
					field.cardinality
				) for field in fields]
			))
		if len(indexes) > 0:
			self.section('indexes', 'Indexes')
			self.add(self.p("""The following table details the indexes defined
				against the table, including which fields each index targets.
				For more information about an individual index (e.g.
				statistics, directionality, etc.) click on the index name."""))
			self.add(self.table(
				head=[(
					"Name",
					"Unique",
					"Fields",
					"Sort Order",
					"Description"
				)],
				data=[(
					self.a_to(index, qualifiedname=True),
					index.unique,
					self.ol([ixfield.name for (ixfield, ixorder) in index.fieldList], attrs=olstyle),
					self.ol([ixorder for (ixfield, ixorder) in index.fieldList], attrs=olstyle),
					self.format_description(index.description, firstline=True)
				) for index in indexes]
			))
		if len(constraints) > 0:
			self.section('constraints', 'Constraints')
			self.add(self.p("""The following table details the constraints
				defined against the table, including which fields each
				constraint limits or tests. For more information about an
				individual constraint click on the constraint name."""))
			rows = []
			for constraint in constraints:
				if isinstance(constraint, ForeignKey):
					expression = [
						'References ',
						self.a_to(constraint.refTable),
						self.ol(['%s -> %s' % (cfield.name, pfield.name)
							for (cfield, pfield) in constraint.fields], attrs=olstyle)
					]
				elif isinstance(constraint, PrimaryKey) or isinstance(constraint, UniqueKey) or isinstance(constraint, Check):
					expression = self.ol([cfield.name for cfield in constraint.fields], attrs=olstyle)
				else:
					expression = ''
				rows.append((
					self.a_to(constraint),
					constraint.typeName,
					expression,
					self.format_description(constraint.description, firstline=True)
				))
			self.add(self.table(
				head=[(
					"Name",
					"Type",
					"Fields",
					"Description"
				)],
				data=rows
			))
		if len(triggers) > 0:
			self.section('triggers', 'Triggers')
			self.add(self.p("""The following table details the triggers defined
				against the table, including which actions fire the trigger and
				when. For more information about an individual trigger click on
				the trigger name."""))
			self.add(self.table(
				head=[(
					"Name",
					"Timing",
					"Event",
					"Description"
				)],
				data=[(
					self.a_to(trigger, qualifiedname=True),
					trigger.triggerTime,
					trigger.triggerEvent,
					self.format_description(trigger.description, firstline=True)
				) for trigger in triggers]
			))
		if len(dependents) > 0:
			self.section('dependents', 'Dependent Relations')
			self.add(self.p("""The following table lists all relations (views
				or materialized query tables) which reference this table in
				their associated SQL statement."""))
			self.add(self.table(
				head=[(
					"Name",
					"Type",
					"Description"
				)],
				data=[(
					self.a_to(dep, qualifiedname=True),
					dep.typeName,
					self.format_description(dep.description, firstline=True)
				) for dep in dependents]
			))
		self.section('sql', 'SQL Definition')
		self.add(self.p("""The SQL which created the table is given below.
			Note that this is not necessarily the same as the actual statement
			used to create the table (it has been reconstructed from the
			content of the system catalog tables and may differ in a number of
			areas)."""))
		selc.add(self.pre(self.format_sql(table.createSql), attrs={'class': 'sql'}))

