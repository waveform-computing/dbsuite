# $Header$
# vim: set noet sw=4 ts=4:

from db2makedoc.db import Table, ForeignKey, PrimaryKey, UniqueKey, Check
from db2makedoc.plugins.html.w3.document import W3MainDocument, W3GraphDocument

orders = {
	'A': 'Ascending',
	'D': 'Descending',
	'I': 'Include',
}
times = {
	'A': 'After',
	'B': 'Before',
	'I': 'Instead of',
}
events = {
	'I': 'Insert',
	'U': 'Update',
	'D': 'Delete',
}

def _inc_index(i):
	if i is None:
		return i
	else:
		return i + 1

class W3TableDocument(W3MainDocument):
	def __init__(self, site, table):
		assert isinstance(table, Table)
		super(W3TableDocument, self).__init__(site, table)

	def _create_sections(self):
		fields = [obj for (name, obj) in sorted(self.dbobject.fields.items(), key=lambda (name, obj): name)]
		indexes = [obj for (name, obj) in sorted(self.dbobject.indexes.items(), key=lambda (name, obj): name)]
		constraints = [obj for (name, obj) in sorted(self.dbobject.constraints.items(), key=lambda (name, obj): name)]
		triggers = [obj for (name, obj) in sorted(self.dbobject.triggers.items(), key=lambda (name, obj): name)]
		dependents = [obj for (name, obj) in sorted(self.dbobject.dependents.items(), key=lambda (name, obj): name)]
		dependents += reduce(lambda a,b: a+b, 
			[
				[fkey.relation for fkey in ukey.dependent_list]
				for ukey in self.dbobject.unique_key_list
				if len(ukey.dependent_list) > 0
			], []
		)
		olstyle = {'style': 'list-style-type: none; padding: 0; margin: 0;'}
		self._section('description', 'Description')
		self._add(self._p(self._format_comment(self.dbobject.description)))
		self._section('attributes', 'Attributes')
		if self.dbobject.primary_key is None:
			key_count = 0
		else:
			key_count = len(self.dbobject.primary_key.fields)
		self._add(self._table(
			head=[(
				"Attribute",
				"Value",
				"Attribute",
				"Value"
			)],
			data=[
				(
					self._a(self.site.url_document('created.html')),
					self.dbobject.created,
					self._a(self.site.url_document('laststats.html')),
					self.dbobject.last_stats,
				),
				(
					self._a(self.site.url_document('createdby.html')),
					self.dbobject.owner,
					self._a(self.site.url_document('cardinality.html')),
					self.dbobject.cardinality,
				),
				(
					self._a(self.site.url_document('keycolcount.html')),
					key_count,
					self._a(self.site.url_document('colcount.html')),
					len(self.dbobject.fields),
				),
				(
					self._a(self.site.url_document('dependentrel.html')),
					len(dependents),
					self._a(self.site.url_document('size.html')),
					self.dbobject.size_str,
				),
				# XXX Include system?
			]
		))
		if len(fields) > 0:
			self._section('field_desc', 'Field Descriptions')
			self._add(self._table(
				head=[(
					"Name",
					"Description"
				)],
				data=[(
					field.name,
					self._format_comment(field.description, summary=True)
				) for field in fields]
			))
			self._section('field_schema', 'Field Schema')
			self._add(self._table(
				head=[(
					"#",
					"Name",
					"Type",
					"Nulls",
					"Key Pos",
					"Cardinality"
				)],
				data=[(
					_inc_index(field.position),
					field.name,
					field.datatype_str,
					field.nullable,
					_inc_index(field.key_index),
					# XXX For Py2.5: field.key_index + 1 if field.key_index is not None else None,
					field.cardinality
				) for field in fields]
			))
		if len(indexes) > 0:
			self._section('indexes', 'Indexes')
			self._add(self._table(
				head=[(
					"Name",
					"Unique",
					"Fields",
					"Sort Order",
					"Description"
				)],
				data=[(
					self._a_to(index, qualifiedname=True),
					index.unique,
					self._ol([ixfield.name for (ixfield, _) in index.field_list], attrs=olstyle),
					self._ol([orders[ixorder] for (_, ixorder) in index.field_list], attrs=olstyle),
					self._format_comment(index.description, summary=True)
				) for index in indexes]
			))
		if len(constraints) > 0:
			self._section('constraints', 'Constraints')
			rows = []
			for constraint in constraints:
				if isinstance(constraint, ForeignKey):
					expression = [
						'References ',
						self._a_to(constraint.ref_table),
						self._ol(['%s -> %s' % (cfield.name, pfield.name)
							for (cfield, pfield) in constraint.fields], attrs=olstyle)
					]
				elif isinstance(constraint, PrimaryKey) or isinstance(constraint, UniqueKey) or isinstance(constraint, Check):
					expression = self._ol([cfield.name for cfield in constraint.fields], attrs=olstyle)
				else:
					expression = ''
				rows.append((
					self._a_to(constraint),
					constraint.type_name,
					expression,
					self._format_comment(constraint.description, summary=True)
				))
			self._add(self._table(
				head=[(
					"Name",
					"Type",
					"Fields",
					"Description"
				)],
				data=rows
			))
		if len(triggers) > 0:
			self._section('triggers', 'Triggers')
			self._add(self._table(
				head=[(
					"Name",
					"Timing",
					"Event",
					"Description"
				)],
				data=[(
					self._a_to(trigger, qualifiedname=True),
					times[trigger.trigger_time],
					events[trigger.trigger_event],
					self._format_comment(trigger.description, summary=True)
				) for trigger in triggers]
			))
		if len(dependents) > 0:
			self._section('dependents', 'Dependent Relations')
			self._add(self._table(
				head=[(
					"Name",
					"Type",
					"Description"
				)],
				data=[(
					self._a_to(dep, qualifiedname=True),
					dep.type_name,
					self._format_comment(dep.description, summary=True)
				) for dep in dependents]
			))
		self._section('diagram', 'Diagram')
		self._add(self._img_of(self.dbobject))
		self._section('sql', 'SQL Definition')
		self._add(self._pre(self._format_sql(self.dbobject.create_sql),
			attrs={'class': 'sql'}))

class W3TableGraph(W3GraphDocument):
	def __init__(self, site, table):
		assert isinstance(table, Table)
		super(W3TableGraph, self).__init__(site, table)
	
	def _create_graph(self):
		super(W3TableGraph, self)._create_graph()
		table = self.dbobject
		table_node = self._add_dbobject(table, selected=True)
		for dependent in table.dependent_list:
			dep_node = self._add_dbobject(dependent)
			dep_edge = dep_node.connect_to(table_node)
			dep_edge.label = '<uses>'
			dep_edge.arrowhead = 'onormal'
		for key in table.foreign_key_list:
			key_node = self._add_dbobject(key.ref_table)
			key_edge = table_node.connect_to(key_node)
			key_edge.dbobject = key
			key_edge.label = key.name
			key_edge.arrowhead = 'normal'
		for key in table.unique_key_list:
			for dependent in key.dependent_list:
				dep_node = self._add_dbobject(dependent.relation)
				dep_edge = dep_node.connect_to(table_node)
				dep_edge.dbobject = dependent
				dep_edge.label = dependent.name
				dep_edge.arrowhead = 'normal'
		for trigger in table.trigger_list:
			trig_node = self._add_dbobject(trigger)
			trig_edge = table_node.connect_to(trig_node)
			trig_edge.label = ('<%s %s>' % (times[trigger.trigger_time], events[trigger.trigger_event])).lower()
			trig_edge.arrowhead = 'vee'
			for dependency in trigger.dependency_list:
				dep_node = self._add_dbobject(dependency)
				dep_edge = trig_node.connect_to(dep_node)
				dep_edge.label = '<uses>'
				dep_edge.arrowhead = 'onormal'
		for trigger in table.trigger_dependent_list:
			trig_node = self._add_dbobject(trigger)
			rel_node = self._add_dbobject(trigger.relation)
			trig_edge = rel_node.connect_to(trig_node)
			trig_edge.label = ('<%s %s>' % (times[trigger.trigger_time], events[trigger.trigger_event])).lower()
			trig_edge.arrowhead = 'vee'
			dep_edge = trig_node.connect_to(table_node)
			dep_edge.label = '<uses>'
			dep_edge.arrowhead = 'onormal'
