# vim: set noet sw=4 ts=4:

from db2makedoc.db import Table, View, Alias
from db2makedoc.plugins.html.document import HTMLObjectDocument, GraphObjectDocument

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

class SchemaDocument(HTMLObjectDocument):
	def generate_body(self):
		body = super(SchemaDocument, self).generate_body()
		tag = self.tag
		body.append(
			tag.div(
				tag.h3('Description'),
				tag.p(self.format_comment(self.dbobject.description)),
				class_='section',
				id='description'
			)
		)
		if len(self.dbobject.relation_list) > 0:
			body.append(
				tag.div(
					tag.h3('Relations'),
					tag.p("""The following table lists the relations (tables,
						views, and aliases) that belong to the schema. Click on
						a relation's name to view the documentation for that
						relation."""),
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
								tag.td(self.site.link_to(relation)),
								tag.td(self.site.type_names[relation.__class__]),
								tag.td(self.format_comment(relation.description, summary=True))
							) for relation in self.dbobject.relation_list
						)),
						id='relation-ts',
						summary='Schema relations'
					),
					class_='section',
					id='relations'
				)
			)
		if len(self.dbobject.index_list) > 0:
			body.append(
				tag.div(
					tag.h3('Indexes'),
					tag.p("""The following table lists the indexes that belong
						to the schema. Note that an index can apply to a table
						in a different schema. Click on an index name to view
						the documentation for that index."""),
					tag.table(
						tag.thead(
							tag.tr(
								tag.th('Name'),
								tag.th('Unique'),
								tag.th('Applies To'),
								tag.th('Description', class_='nosort')
							)
						),
						tag.tbody((
							tag.tr(
								tag.td(self.site.link_to(index)),
								tag.td(index.unique),
								tag.td(self.site.link_to(index.table)),
								tag.td(self.format_comment(index.description, summary=True))
							) for index in self.dbobject.index_list
						)),
						id='index-ts',
						summary='Schema indexes'
					),
					class_='section',
					id='indexes'
				)
			)
		if len(self.dbobject.trigger_list) > 0:
			body.append(
				tag.div(
					tag.h3('Triggers'),
					tag.p("""The following table lists the triggers that belong
						to the schema (and the tables and views they apply to).
						Note that a trigger can apply to a table or view in a
						different schema. Click on a trigger name to view the
						documentation for that trigger."""),
					tag.table(
						tag.thead(
							tag.tr(
								tag.th('Name'),
								tag.th('Timing'),
								tag.th('Event'),
								tag.th('Applies To'),
								tag.th('Description', class_='nosort')
							)
						),
						tag.tbody((
							tag.tr(
								tag.td(self.site.link_to(trigger)),
								tag.td(times[trigger.trigger_time]),
								tag.td(events[trigger.trigger_event]),
								tag.td(self.site.link_to(trigger.relation)),
								tag.td(self.format_comment(trigger.description, summary=True))
							) for trigger in self.dbobject.trigger_list
						)),
						id='trigger-ts',
						summary='Schema triggers'
					),
					class_='section',
					id='triggers'
				)
			)
		if len(self.dbobject.routine_list) > 0:
			body.append(
				tag.div(
					tag.h3('Routines'),
					tag.p("""The following table lists the routines (user
						defined functions and stored procedures) that belong to
						this schema. Click on a routine's name to view the
						documentation for that routine."""),
					tag.table(
						tag.thead(
							tag.tr(
								tag.th('Name'),
								tag.th('Specific Name'),
								tag.th('Type'),
								tag.th('Description', class_='nosort')
							)
						),
						tag.tbody((
							tag.tr(
								tag.td(self.site.link_to(routine)),
								tag.td(routine.specific_name),
								tag.td(self.site.type_names[routine.__class__]),
								tag.td(self.format_comment(routine.description, summary=True))
							) for routine in self.dbobject.routine_list
						)),
						id='routine-ts',
						summary='Schema routines'
					),
					class_='section',
					id='routines'
				)
			)
		if len(self.dbobject.relation_list) > 0:
			body.append(
				tag.div(
					tag.h3('Diagram'),
					tag.p_diagram(self.dbobject),
					self.site.img_of(self.dbobject),
					class_='section',
					id='diagram'
				)
			)
		return body

class SchemaGraph(GraphObjectDocument):
	def generate(self):
		graph = super(SchemaGraph, self).generate()
		schema = self.dbobject
		graph.add(schema, selected=True)
		for relation in schema.relation_list:
			rel_node = graph.add(relation)
			for dependent in relation.dependent_list:
				dep_node = graph.add(dependent)
				dep_edge = dep_node.connect_to(rel_node)
				dep_edge.arrowhead = 'onormal'
			if isinstance(relation, Table):
				for key in relation.foreign_key_list:
					key_node = graph.add(key.ref_table)
					key_edge = rel_node.connect_to(key_node)
					key_edge.arrowhead = 'normal'
				for trigger in relation.trigger_list:
					trig_node = graph.add(trigger)
					trig_edge = rel_node.connect_to(trig_node)
					trig_edge.arrowhead = 'vee'
					for dependency in trigger.dependency_list:
						dep_node = graph.add(dependency)
						dep_edge = trig_node.connect_to(dep_node)
						dep_edge.arrowhead = 'onormal'
			elif isinstance(relation, View):
				for dependency in relation.dependency_list:
					dep_node = graph.add(dependency)
					dep_edge = rel_node.connect_to(dep_node)
					dep_edge.arrowhead = 'onormal'
			elif isinstance(relation, Alias):
				ref_node = graph.add(relation.relation)
				ref_edge = rel_node.connect_to(ref_node)
				ref_edge.arrowhead = 'onormal'
		for trigger in schema.trigger_list:
			rel_node = graph.add(trigger.relation)
			trig_node = graph.add(trigger)
			trig_edge = rel_node.connect_to(trig_node)
			trig_edge.arrowhead = 'vee'
			for dependency in trigger.dependency_list:
				dep_node = graph.add(dependency)
				dep_edge = trig_node.connect_to(dep_node)
				dep_edge.arrowhead = 'onormal'
		return graph
