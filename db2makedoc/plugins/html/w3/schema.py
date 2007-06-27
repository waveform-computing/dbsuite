# $Header$
# vim: set noet sw=4 ts=4:

from db2makedoc.db import Schema, Table, View, Alias
from db2makedoc.plugins.html.w3.document import W3MainDocument, W3GraphDocument

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

class W3SchemaDocument(W3MainDocument):
	def __init__(self, site, schema):
		assert isinstance(schema, Schema)
		super(W3SchemaDocument, self).__init__(site, schema)

	def _create_sections(self):
		relations = [obj for (name, obj) in sorted(self.dbobject.relations.items(), key=lambda (name, obj): name)]
		routines = [obj for (name, obj) in sorted(self.dbobject.specific_routines.items(), key=lambda (name, obj): name)]
		indexes = [obj for (name, obj) in sorted(self.dbobject.indexes.items(), key=lambda (name, obj): name)]
		triggers = [obj for (name, obj) in sorted(self.dbobject.triggers.items(), key=lambda (name, obj): name)]
		self._section('description', 'Description')
		self._add(self._p(self._format_comment(self.dbobject.description)))
		if len(relations) > 0:
			self._section('relations', 'Relations')
			self._add(self._table(
				head=[(
					"Name",
					"Type",
					"Description"
				)],
				data=[(
					self._a_to(relation),
					relation.type_name,
					self._format_comment(relation.description, summary=True)
				) for relation in relations]
			))
		if len(indexes) > 0:
			self._section('indexes', 'Indexes')
			self._add(self._table(
				head=[(
					"Name",
					"Unique",
					"Applies To",
					"Description")],
				data=[(
					self._a_to(index),
					index.unique,
					self._a_to(index.table, qualifiedname=True),
					self._format_comment(index.description, summary=True)
				) for index in indexes]
			))
		if len(triggers) > 0:
			self._section('triggers', 'Triggers')
			self._add(self._table(
				head=[(
					"Name",
					"Timing",
					"Event",
					"Applies To",
					"Description")],
				data=[(
					self._a_to(trigger),
					times[trigger.trigger_time],
					events[trigger.trigger_event],
					self._a_to(trigger.relation, qualifiedname=True),
					self._format_comment(trigger.description, summary=True)
				) for trigger in triggers]
			))
		if len(routines) > 0:
			self._section('routines', 'Routines')
			self._add(self._table(
				head=[(
					"Name",
					"Specific Name",
					"Type",
					"Description"
				)],
				data=[(
					self._a_to(routine),
					routine.specific_name,
					routine.type_name,
					self._format_comment(routine.description, summary=True)
				) for routine in routines]
			))
		if len(relations) > 0:
			self._section('diagrams', 'Diagrams')
			self._add(self._img_of(self.dbobject))

class W3SchemaGraph(W3GraphDocument):
	def __init__(self, site, schema):
		assert isinstance(schema, Schema)
		super(W3SchemaGraph, self).__init__(site, schema)

	def _create_graph(self):
		super(W3SchemaGraph, self)._create_graph()
		schema = self.dbobject
		self._add_dbobject(schema)
		for relation in schema.relation_list:
			rel_node = self._add_dbobject(relation)
			for dependent in relation.dependent_list:
				dep_node = self._add_dbobject(dependent)
				dep_edge = dep_node.connect_to(rel_node)
				dep_edge.arrowhead = 'onormal'
			if isinstance(relation, Table):
				for key in relation.foreign_key_list:
					key_node = self._add_dbobject(key.ref_table)
					key_edge = rel_node.connect_to(key_node)
					key_edge.arrowhead = 'normal'
				for trigger in relation.trigger_list:
					trig_node = self._add_dbobject(trigger)
					trig_edge = rel_node.connect_to(trig_node)
					trig_edge.arrowhead = 'vee'
					for dependency in trigger.dependency_list:
						dep_node = self._add_dbobject(dependency)
						dep_edge = trig_node.connect_to(dep_node)
						dep_edge.arrowhead = 'onormal'
			elif isinstance(relation, View):
				for dependency in relation.dependency_list:
					dep_node = self._add_dbobject(dependency)
					dep_edge = rel_node.connect_to(dep_node)
					dep_edge.arrowhead = 'onormal'
			elif isinstance(relation, Alias):
				ref_node = self._add_dbobject(relation.relation)
				ref_edge = rel_node.connect_to(ref_node)
				ref_edge.arrowhead = 'onormal'
		for trigger in schema.trigger_list:
			rel_node = self._add_dbobject(trigger.relation)
			trig_node = self._add_dbobject(trigger)
			trig_edge = rel_node.connect_to(trig_node)
			trig_edge.arrowhead = 'vee'
			for dependency in trigger.dependency_list:
				dep_node = self._add_dbobject(dependency)
				dep_edge = trig_node.connect_to(dep_node)
				dep_edge.arrowhead = 'onormal'
