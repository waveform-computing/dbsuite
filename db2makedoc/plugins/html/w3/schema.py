# vim: set noet sw=4 ts=4:

from db2makedoc.db import Schema, Table, View, Alias
from db2makedoc.plugins.html.w3.document import W3ObjectDocument, W3GraphDocument, tag

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

class W3SchemaDocument(W3ObjectDocument):
	def __init__(self, site, schema):
		assert isinstance(schema, Schema)
		super(W3SchemaDocument, self).__init__(site, schema)

	def generate_sections(self):
		result = super(W3SchemaDocument, self).generate_sections()
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
					id='relation-ts'
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
					id='index-ts'
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
					id='trigger-ts'
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
					id='routine-ts'
				)
			))
		if len(self.dbobject.relation_list) > 0 and self.site.object_graph(self.dbobject):
			result.append((
				'diagram', 'Diagram',
				self.site.img_of(self.dbobject)
			))
		return result

class W3SchemaGraph(W3GraphDocument):
	def __init__(self, site, schema):
		assert isinstance(schema, Schema)
		super(W3SchemaGraph, self).__init__(site, schema)

	def generate(self):
		super(W3SchemaGraph, self).generate()
		schema = self.dbobject
		self.add(schema)
		for relation in schema.relation_list:
			rel_node = self.add(relation)
			for dependent in relation.dependent_list:
				dep_node = self.add(dependent)
				dep_edge = dep_node.connect_to(rel_node)
				dep_edge.arrowhead = 'onormal'
			if isinstance(relation, Table):
				for key in relation.foreign_key_list:
					key_node = self.add(key.ref_table)
					key_edge = rel_node.connect_to(key_node)
					key_edge.arrowhead = 'normal'
				for trigger in relation.trigger_list:
					trig_node = self.add(trigger)
					trig_edge = rel_node.connect_to(trig_node)
					trig_edge.arrowhead = 'vee'
					for dependency in trigger.dependency_list:
						dep_node = self.add(dependency)
						dep_edge = trig_node.connect_to(dep_node)
						dep_edge.arrowhead = 'onormal'
			elif isinstance(relation, View):
				for dependency in relation.dependency_list:
					dep_node = self.add(dependency)
					dep_edge = rel_node.connect_to(dep_node)
					dep_edge.arrowhead = 'onormal'
			elif isinstance(relation, Alias):
				ref_node = self.add(relation.relation)
				ref_edge = rel_node.connect_to(ref_node)
				ref_edge.arrowhead = 'onormal'
		for trigger in schema.trigger_list:
			rel_node = self.add(trigger.relation)
			trig_node = self.add(trigger)
			trig_edge = rel_node.connect_to(trig_node)
			trig_edge.arrowhead = 'vee'
			for dependency in trigger.dependency_list:
				dep_node = self.add(dependency)
				dep_edge = trig_node.connect_to(dep_node)
				dep_edge.arrowhead = 'onormal'
		return self.graph
