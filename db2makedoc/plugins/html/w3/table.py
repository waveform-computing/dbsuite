# vim: set noet sw=4 ts=4:

from itertools import chain
from db2makedoc.db import Alias, Table, View, ForeignKey, PrimaryKey, UniqueKey, Check
from db2makedoc.plugins.html.w3.document import W3ObjectDocument, W3GraphDocument, tag

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

class W3TableDocument(W3ObjectDocument):
	def __init__(self, site, table):
		assert isinstance(table, Table)
		super(W3TableDocument, self).__init__(site, table)

	def generate_sections(self):
		result = super(W3TableDocument, self).generate_sections()
		result.append((
			'description', 'Description',
			tag.p(self.format_comment(self.dbobject.description))
		))
		olstyle = 'list-style-type: none; padding: 0; margin: 0;'
		if self.dbobject.primary_key is None:
			key_count = 0
		else:
			key_count = len(self.dbobject.primary_key.fields)
		result.append((
			'attributes', 'Attributes',
			tag.table(
				tag.thead(
					tag.tr(
						tag.th('Attribute'),
						tag.th('Value'),
						tag.th('Attribute'),
						tag.th('Value')
					)
				),
				tag.tbody(
					tag.tr(
						tag.td(self.site.url_document('created.html').link()),
						tag.td(self.dbobject.created),
						tag.td(self.site.url_document('laststats.html').link()),
						tag.td(self.dbobject.last_stats)
					),
					tag.tr(
						tag.td(self.site.url_document('createdby.html').link()),
						tag.td(self.dbobject.owner),
						tag.td(self.site.url_document('cardinality.html').link()),
						tag.td(self.dbobject.cardinality)
					),
					tag.tr(
						tag.td(self.site.url_document('keycolcount.html').link()),
						tag.td(key_count),
						tag.td(self.site.url_document('colcount.html').link()),
						tag.td(len(self.dbobject.field_list))
					),
					tag.tr(
						tag.td(self.site.url_document('dependentrel.html').link()),
						tag.td(
							len(self.dbobject.dependents) +
							sum(len(k.dependent_list) for k in self.dbobject.unique_key_list)
						),
						tag.td(self.site.url_document('size.html').link()),
						tag.td(self.dbobject.size_str)
					)
					# XXX Include system?
				)
			)
		))
		if len(self.dbobject.field_list) > 0:
			result.append((
				'fields', 'Fields',
				tag.table(
					tag.thead(
						tag.tr(
							tag.th('#'),
							tag.th('Name'),
							tag.th('Type'),
							tag.th('Nulls'),
							tag.th('Key Pos'),
							tag.th('Cardinality'),
							tag.th('Description', class_='nosort')
						)
					),
					tag.tbody((
						tag.tr(
							tag.td(field.position + 1),
							tag.td(field.name, class_='nowrap'),
							tag.td(field.datatype_str, class_='nowrap'),
							tag.td(field.nullable),
							tag.td(_inc_index(field.key_index)), # XXX For Py2.5: field.key_index + 1 if field.key_index is not None else None,
							tag.td(field.cardinality),
							tag.td(self.format_comment(field.description, summary=True))
						) for field in self.dbobject.field_list
					)),
					id='field-ts'
				)
			))
		if len(self.dbobject.index_list) > 0:
			result.append((
				'indexes', 'Indexes',
				tag.table(
					tag.thead(
						tag.tr(
							tag.th('Name'),
							tag.th('Unique'),
							tag.th('Fields'),
							tag.th('Sort Order'),
							tag.th('Description', class_='nosort')
						)
					),
					tag.tbody((
						tag.tr(
							tag.td(self.site.link_to(index)),
							tag.td(index.unique),
							tag.td(tag.ol((tag.li(ixfield.name) for (ixfield, _) in index.field_list), style=olstyle)),
							tag.td(tag.ol((tag.li(orders[ixorder]) for (_, ixorder) in index.field_list), style=olstyle)),
							tag.td(self.format_comment(index.description, summary=True))
						) for index in self.dbobject.index_list
					)),
					id='index-ts'
				)
			))
		if len(self.dbobject.constraint_list) > 0:
			def fields(constraint):
				if isinstance(constraint, ForeignKey):
					return [
						'References ',
						self.site.link_to(constraint.ref_table),
						tag.ol((tag.li('%s -> %s' % (cfield.name, pfield.name)) for (cfield, pfield) in constraint.fields), style=olstyle)
					]
				elif isinstance(constraint, UniqueKey) or isinstance(constraint, Check):
					return tag.ol((tag.li(cfield.name) for cfield in constraint.fields), style=olstyle)
				else:
					return ''
			result.append((
				'constraints', 'Constraints',
				tag.table(
					tag.thead(
						tag.tr(
							tag.th('Name'),
							tag.th('Type'),
							tag.th('Fields', class_='nosort'),
							tag.th('Description', class_='nosort')
						)
					),
					tag.tbody((
						tag.tr(
							tag.td(self.site.link_to(constraint)),
							tag.td(self.site.type_names[constraint.__class__]),
							tag.td(fields(constraint)),
							tag.td(self.format_comment(constraint.description, summary=True))
						) for constraint in self.dbobject.constraint_list
					)),
					id='const-ts'
				)
			))
		if len(self.dbobject.trigger_list) > 0:
			result.append((
				'triggers', 'Triggers',
				tag.table(
					tag.thead(
						tag.tr(
							tag.th('Name'),
							tag.th('Timing'),
							tag.th('Event'),
							tag.th('Description', class_='nosort')
						)
					),
					tag.tbody((
						tag.tr(
							tag.td(self.site.link_to(trigger)),
							tag.td(times[trigger.trigger_time]),
							tag.td(events[trigger.trigger_event]),
							tag.td(self.format_comment(trigger.description, summary=True))
						) for trigger in self.dbobject.trigger_list
					)),
					id='trig-ts'
				)
			))
		if len(self.dbobject.dependents) + sum(len(k.dependent_list) for k in self.dbobject.unique_key_list) > 0:
			result.append((
				'dependents', 'Dependent Relations',
				tag.table(
					tag.thead(
						tag.tr(
							tag.th('Name'),
							tag.th('Type'),
							tag.th('Description', class_='nosort')
						)
					),
					tag.tbody((
						tag.tr(
							tag.td(self.site.link_to(dep)),
							tag.td(self.site.type_names[dep.__class__]),
							tag.td(self.format_comment(dep.description, summary=True))
						) for dep in chain(
							self.dbobject.dependent_list,
							(
								fkey.relation
								for ukey in self.dbobject.unique_key_list
								for fkey in ukey.dependent_list
							)
						)
					)),
					id='dep-ts'
				)
			))
		if self.site.object_graph(self.dbobject):
			result.append((
				'diagram', 'Diagram',
				self.site.img_of(self.dbobject)
			))
		if self.dbobject.create_sql:
			result.append((
				'sql', 'SQL Definition', [
					tag.p(tag.a('Line #s On/Off', href='#', onclick='javascript:return toggleLineNums("sqldef");')),
					self.format_sql(self.dbobject.create_sql, number_lines=True, id='sqldef')
				]
			))
		return result

class W3TableGraph(W3GraphDocument):
	def __init__(self, site, table):
		assert isinstance(table, Table)
		super(W3TableGraph, self).__init__(site, table)
	
	def generate(self):
		super(W3TableGraph, self).generate()
		table = self.dbobject
		table_node = self.add(table, selected=True)
		for dependent in table.dependent_list:
			dep_node = self.add(dependent)
			dep_edge = dep_node.connect_to(table_node)
			if isinstance(dependent, View):
				dep_edge.label = '<uses>'
			elif isinstance(dependent, Alias):
				dep_edge.label = '<for>'
			dep_edge.arrowhead = 'onormal'
		for key in table.foreign_key_list:
			key_node = self.add(key.ref_table)
			key_edge = table_node.connect_to(key_node)
			key_edge.dbobject = key
			key_edge.label = key.name
			key_edge.arrowhead = 'normal'
		for key in table.unique_key_list:
			for dependent in key.dependent_list:
				dep_node = self.add(dependent.relation)
				dep_edge = dep_node.connect_to(table_node)
				dep_edge.dbobject = dependent
				dep_edge.label = dependent.name
				dep_edge.arrowhead = 'normal'
		for trigger in table.trigger_list:
			trig_node = self.add(trigger)
			trig_edge = table_node.connect_to(trig_node)
			trig_edge.label = ('<%s %s>' % (times[trigger.trigger_time], events[trigger.trigger_event])).lower()
			trig_edge.arrowhead = 'vee'
			for dependency in trigger.dependency_list:
				dep_node = self.add(dependency)
				dep_edge = trig_node.connect_to(dep_node)
				dep_edge.label = '<uses>'
				dep_edge.arrowhead = 'onormal'
		for trigger in table.trigger_dependent_list:
			trig_node = self.add(trigger)
			rel_node = self.add(trigger.relation)
			trig_edge = rel_node.connect_to(trig_node)
			trig_edge.label = ('<%s %s>' % (times[trigger.trigger_time], events[trigger.trigger_event])).lower()
			trig_edge.arrowhead = 'vee'
			dep_edge = trig_node.connect_to(table_node)
			dep_edge.label = '<uses>'
			dep_edge.arrowhead = 'onormal'
		return self.graph
