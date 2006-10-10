# $Header$
# vim: set noet sw=4 ts=4:

from db.table import Table
from db.foreignkey import ForeignKey
from db.uniquekey import PrimaryKey, UniqueKey
from db.check import Check
from output.html.w3.document import W3MainDocument, W3GraphDocument

class W3TableDocument(W3MainDocument):
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
		if self.dbobject.primary_key is None:
			key_count = 0
		else:
			key_count = len(self.dbobject.primary_key.fields)
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
					self.a_to(self.dbobject.data_tablespace),
					'Index Tablespace',
					self.a_to(self.dbobject.index_tablespace),
				),
				(
					'Long Tablespace',
					self.a_to(self.dbobject.long_tablespace),
					self.a(self.site.documents['clustered.html']),
					self.dbobject.clustered,
				),
				(
					self.a(self.site.documents['created.html']),
					self.dbobject.created,
					self.a(self.site.documents['laststats.html']),
					self.dbobject.stats_updated,
				),
				(
					self.a(self.site.documents['createdby.html']),
					self.dbobject.definer,
					self.a(self.site.documents['cardinality.html']),
					self.dbobject.cardinality,
				),
				(
					self.a(self.site.documents['keycolcount.html']),
					key_count,
					self.a(self.site.documents['colcount.html']),
					len(self.dbobject.fields),
				),
				(
					self.a(self.site.documents['rowpages.html']),
					self.dbobject.row_pages,
					self.a(self.site.documents['totalpages.html']),
					self.dbobject.total_pages,
				),
				(
					self.a(self.site.documents['dependentrel.html']),
					len(self.dbobject.dependent_list),
					self.a(self.site.documents['locksize.html']),
					self.dbobject.lock_size,
				),
				(
					self.a(self.site.documents['append.html']),
					self.dbobject.append,
					self.a(self.site.documents['volatile.html']),
					self.dbobject.volatile,
				),
			]
		))
		if len(fields) > 0:
			self.section('field_desc', 'Field Descriptions')
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
					field.datatype_str,
					field.nullable,
					field.key_index,
					field.cardinality
				) for field in fields]
			))
		if len(indexes) > 0:
			self.section('indexes', 'Indexes')
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
					self.ol([ixfield.name for (ixfield, ixorder) in index.field_list], attrs=olstyle),
					self.ol([ixorder for (ixfield, ixorder) in index.field_list], attrs=olstyle),
					self.format_description(index.description, firstline=True)
				) for index in indexes]
			))
		if len(constraints) > 0:
			self.section('constraints', 'Constraints')
			rows = []
			for constraint in constraints:
				if isinstance(constraint, ForeignKey):
					expression = [
						'References ',
						self.a_to(constraint.ref_table),
						self.ol(['%s -> %s' % (cfield.name, pfield.name)
							for (cfield, pfield) in constraint.fields], attrs=olstyle)
					]
				elif isinstance(constraint, PrimaryKey) or isinstance(constraint, UniqueKey) or isinstance(constraint, Check):
					expression = self.ol([cfield.name for cfield in constraint.fields], attrs=olstyle)
				else:
					expression = ''
				rows.append((
					self.a_to(constraint),
					constraint.type_name,
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
			self.add(self.table(
				head=[(
					"Name",
					"Timing",
					"Event",
					"Description"
				)],
				data=[(
					self.a_to(trigger, qualifiedname=True),
					trigger.trigger_time,
					trigger.trigger_event,
					self.format_description(trigger.description, firstline=True)
				) for trigger in triggers]
			))
		if len(dependents) > 0:
			self.section('dependents', 'Dependent Relations')
			self.add(self.table(
				head=[(
					"Name",
					"Type",
					"Description"
				)],
				data=[(
					self.a_to(dep, qualifiedname=True),
					dep.type_name,
					self.format_description(dep.description, firstline=True)
				) for dep in dependents]
			))
		self.section('diagram', 'Diagram')
		self.add(self.img_of(self.dbobject))
		self.section('sql', 'SQL Definition')
		self.add(self.pre(self.format_sql(self.dbobject.create_sql), attrs={'class': 'sql'}))

class W3TableGraph(W3GraphDocument):
	def __init__(self, site, table):
		assert isinstance(table, Table)
		super(W3TableGraph, self).__init__(site, table)
	
	def create_graph(self):
		super(W3TableGraph, self).create_graph()
		table = self.dbobject
		table_node = self.add_dbobject(table, selected=True)
		for dependent in table.dependent_list:
			dep_node = self.add_dbobject(dependent)
			dep_edge = dep_node.connect_to(table_node)
			dep_edge.label = '<uses>'
			dep_edge.arrowhead = 'onormal'
		for key in table.foreign_key_list:
			key_node = self.add_dbobject(key.ref_table)
			key_edge = table_node.connect_to(key_node)
			key_edge.dbobject = key
			key_edge.label = key.name
			key_edge.arrowhead = 'normal'
		for trigger in table.trigger_list:
			trig_node = self.add_dbobject(trigger)
			trig_edge = table_node.connect_to(trig_node)
			trig_edge.label = ('<%s %s>' % (trigger.trigger_time, trigger.trigger_event)).lower()
			trig_edge.arrowhead = 'vee'
			for dependency in trigger.dependency_list:
				dep_node = self.add_dbobject(dependency)
				dep_edge = trig_node.connect_to(dep_node)
				dep_edge.label = '<uses>'
				dep_edge.arrowhead = 'onormal'
