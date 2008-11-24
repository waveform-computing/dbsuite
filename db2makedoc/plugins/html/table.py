# vim: set noet sw=4 ts=4:

from itertools import chain
from db2makedoc.db import Alias, View, ForeignKey, PrimaryKey, UniqueKey, Check
from db2makedoc.plugins.html.document import HTMLObjectDocument, GraphObjectDocument

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

class TableDocument(HTMLObjectDocument):
	def generate_body(self):
		body = super(TableDocument, self).generate_body()
		tag = self.tag
		body.append(
			tag.div(
				tag.h3('Description'),
				tag.p(self.format_comment(self.dbobject.description)),
				class_='section',
				id='description'
			)
		)
		olstyle = 'list-style-type: none; padding: 0; margin: 0;'
		if self.dbobject.primary_key is None:
			key_count = 0
		else:
			key_count = len(self.dbobject.primary_key.fields)
		body.append(
			tag.div(
				tag.h3('Attributes'),
				tag.p_attributes(self.dbobject),
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
					),
					summary='Table attributes'
				),
				class_='section',
				id='attributes'
			)
		)
		if len(self.dbobject.field_list) > 0:
			body.append(
				tag.div(
					tag.h3('Fields'),
					tag.p_relation_fields(self.dbobject),
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
								tag.td(field.position),
								tag.td(field.name),
								tag.td(field.datatype_str),
								tag.td(field.nullable),
								tag.td(field.key_index),
								tag.td(field.cardinality),
								tag.td(self.format_comment(field.description, summary=True))
							) for field in self.dbobject.field_list
						)),
						id='field-ts',
						summary='Table fields'
					),
					class_='section',
					id='fields'
				)
			)
		if len(self.dbobject.index_list) > 0:
			body.append(
				tag.div(
					tag.h3('Indexes'),
					tag.p("""The following table lists the indexes that apply
						to this table, whether or not the index enforces a
						unique rule, and the fields that the index covers.
						Click on an index name to view the full documentation
						for that index."""),
					tag.table(
						tag.thead(
							tag.tr(
								tag.th('Name'),
								tag.th('Unique'),
								tag.th('Fields', class_='nosort'),
								tag.th('Sort Order', class_='nosort'),
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
						id='index-ts',
						summary='Table indexes'
					),
					class_='section',
					id='indexes'
				)
			)
		if len(self.dbobject.constraint_list) > 0:
			def fields(constraint):
				if isinstance(constraint, ForeignKey):
					return [
						'References ',
						self.site.link_to(constraint.ref_table),
						tag.ol((tag.li('%s -> %s' % (cfield.name, pfield.name)) for (cfield, pfield) in constraint.fields), style=olstyle)
					]
				elif isinstance(constraint, PrimaryKey) or isinstance(constraint, UniqueKey) or isinstance(constraint, Check):
					return tag.ol((tag.li(cfield.name) for cfield in constraint.fields), style=olstyle)
				else:
					return ''
			body.append(
				tag.div(
					tag.h3('Constraints'),
					tag.p("""The following table lists all constraints that
						apply to this table, including the fields constrained
						in each case. Click on a constraint's name to view the
						full documentation for that constraint."""),
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
						id='const-ts',
						summary='Table constraints'
					),
					class_='section',
					id='constraints'
				)
			)
		if len(self.dbobject.trigger_list) > 0:
			body.append(
				tag.div(
					tag.h3('Triggers'),
					tag.p_triggers(self.dbobject),
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
						id='trig-ts',
						summary='Table triggers'
					),
					class_='section',
					id='triggers'
				)
			)
		if len(self.dbobject.dependents) + sum(len(k.dependent_list) for k in self.dbobject.unique_key_list) > 0:
			body.append(
				tag.div(
					tag.h3('Dependent Relations'),
					tag.p_dependent_relations(self.dbobject),
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
						id='dep-ts',
						summary='Table dependents'
					),
					class_='section',
					id='dependents'
				)
			)
		if self.site.object_graph(self.dbobject):
			body.append(
				tag.div(
					tag.h3('Diagram'),
					tag.p_diagram(self.dbobject),
					self.site.img_of(self.dbobject),
					class_='section',
					id='diagram'
				)
			)
		if self.dbobject.create_sql:
			body.append(
				tag.div(
					tag.h3('SQL Definition'),
					tag.p_sql_definition(self.dbobject),
					self.format_sql(self.dbobject.create_sql, number_lines=True, id='sql-def'),
					class_='section',
					id='sql'
				)
			)
		return body

class TableGraph(GraphObjectDocument):
	def generate(self):
		graph = super(TableGraph, self).generate()
		table = self.dbobject
		table_node = graph.add(table, selected=True)
		for dependent in table.dependent_list:
			dep_node = graph.add(dependent)
			dep_edge = dep_node.connect_to(table_node)
			if isinstance(dependent, View):
				dep_edge.label = '<uses>'
			elif isinstance(dependent, Alias):
				dep_edge.label = '<for>'
			dep_edge.arrowhead = 'onormal'
		for key in table.foreign_key_list:
			key_node = graph.add(key.ref_table)
			key_edge = table_node.connect_to(key_node)
			key_edge.dbobject = key
			key_edge.label = key.name
			key_edge.arrowhead = 'normal'
		for key in table.unique_key_list:
			for dependent in key.dependent_list:
				dep_node = graph.add(dependent.relation)
				dep_edge = dep_node.connect_to(table_node)
				dep_edge.dbobject = dependent
				dep_edge.label = dependent.name
				dep_edge.arrowhead = 'normal'
		for trigger in table.trigger_list:
			trig_node = graph.add(trigger)
			trig_edge = table_node.connect_to(trig_node)
			trig_edge.label = ('<%s %s>' % (times[trigger.trigger_time], events[trigger.trigger_event])).lower()
			trig_edge.arrowhead = 'vee'
			for dependency in trigger.dependency_list:
				dep_node = graph.add(dependency)
				dep_edge = trig_node.connect_to(dep_node)
				dep_edge.label = '<uses>'
				dep_edge.arrowhead = 'onormal'
		for trigger in table.trigger_dependent_list:
			trig_node = graph.add(trigger)
			rel_node = graph.add(trigger.relation)
			trig_edge = rel_node.connect_to(trig_node)
			trig_edge.label = ('<%s %s>' % (times[trigger.trigger_time], events[trigger.trigger_event])).lower()
			trig_edge.arrowhead = 'vee'
			dep_edge = trig_node.connect_to(table_node)
			dep_edge.label = '<uses>'
			dep_edge.arrowhead = 'onormal'
		return graph

