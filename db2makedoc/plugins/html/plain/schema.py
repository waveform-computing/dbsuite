# vim: set noet sw=4 ts=4:

from db2makedoc.db import Schema, Table, View, Alias
from db2makedoc.plugins.html.plain.document import PlainObjectDocument, PlainGraphDocument

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

class PlainSchemaDocument(PlainObjectDocument):
	def __init__(self, site, schema):
		assert isinstance(schema, Schema)
		super(PlainSchemaDocument, self).__init__(site, schema)

	def generate_sections(self):
		tag = self.tag
		result = super(PlainSchemaDocument, self).generate_sections()
		result.append((
			'description', 'Description',
			tag.p(self.format_comment(self.dbobject.description))
		))
		if len(self.dbobject.relation_list) > 0:
			result.append((
				'relations', 'Relations',
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
				)
			))
		if len(self.dbobject.routine_list) > 0:
			result.append((
				'routines', 'Routines',
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
				)
			))
		if len(self.dbobject.relation_list) > 0:
			result.append((
				'diagram', 'Diagram',
				self.site.img_of(self.dbobject)
			))
		return result

class PlainSchemaGraph(PlainGraphDocument):
	def __init__(self, site, schema):
		assert isinstance(schema, Schema)
		super(PlainSchemaGraph, self).__init__(site, schema)

	def generate(self):
		graph = super(PlainSchemaGraph, self).generate()
		schema = self.dbobject
		graph.add(schema)
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
