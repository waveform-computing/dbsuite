# $Header$
# vim: set noet sw=4 ts=4:

from db.schema import Schema
from db.table import Table
from output.html.w3.document import W3MainDocument, W3GraphDocument

class W3SchemaDocument(W3MainDocument):
	def __init__(self, site, schema):
		assert isinstance(schema, Schema)
		super(W3SchemaDocument, self).__init__(site, schema)

	def create_sections(self):
		relations = [obj for (name, obj) in sorted(self.dbobject.relations.items(), key=lambda (name, obj): name)]
		routines = [obj for (name, obj) in sorted(self.dbobject.specific_routines.items(), key=lambda (name, obj): name)]
		indexes = [obj for (name, obj) in sorted(self.dbobject.indexes.items(), key=lambda (name, obj): name)]
		triggers = [obj for (name, obj) in sorted(self.dbobject.triggers.items(), key=lambda (name, obj): name)]
		self.section('description', 'Description')
		self.add(self.p(self.format_comment(self.dbobject.description)))
		if len(relations) > 0:
			self.section('relations', 'Relations')
			self.add(self.table(
				head=[(
					"Name",
					"Type",
					"Description"
				)],
				data=[(
					self.a_to(relation),
					relation.type_name,
					self.format_comment(relation.description, summary=True)
				) for relation in relations]
			))
		if len(indexes) > 0:
			self.section('indexes', 'Indexes')
			self.add(self.table(
				head=[(
					"Name",
					"Unique",
					"Applies To",
					"Description")],
				data=[(
					self.a_to(index),
					index.unique,
					self.a_to(index.table, qualifiedname=True),
					self.format_comment(index.description, summary=True)
				) for index in indexes]
			))
		if len(triggers) > 0:
			self.section('triggers', 'Triggers')
			self.add(self.table(
				head=[(
					"Name",
					"Timing",
					"Event",
					"Applies To",
					"Description")],
				data=[(
					self.a_to(trigger),
					trigger.trigger_time,
					trigger.trigger_event,
					self.a_to(trigger.relation, qualifiedname=True),
					self.format_comment(trigger.description, summary=True)
				) for trigger in triggers]
			))
		if len(routines) > 0:
			self.section('routines', 'Routines')
			self.add(self.table(
				head=[(
					"Name",
					"Specific Name",
					"Type",
					"Description"
				)],
				data=[(
					self.a_to(routine),
					routine.specific_name,
					routine.type_name,
					self.format_comment(routine.description, summary=True)
				) for routine in routines]
			))
		if len(relations) > 0:
			self.section('diagrams', 'Diagrams')
			self.add(self.img_of(self.dbobject))

class W3SchemaGraph(W3GraphDocument):
	def __init__(self, site, schema):
		assert isinstance(schema, Schema)
		super(W3SchemaGraph, self).__init__(site, schema)

	def create_graph(self):
		super(W3SchemaGraph, self).create_graph()
		schema = self.dbobject
		self.add_dbobject(schema)
		for relation in schema.relation_list:
			rel_node = self.add_dbobject(relation)
			for dependent in relation.dependent_list:
				dep_node = self.add_dbobject(dependent)
				dep_edge = dep_node.connect_to(rel_node)
				dep_edge.label = '<uses>'
				dep_edge.arrowhead = 'onormal'
			if isinstance(relation, Table):
				for key in relation.foreign_key_list:
					key_node = self.add_dbobject(key.ref_table)
					key_edge = rel_node.connect_to(key_node)
					key_edge.label = key.name
					key_edge.arrowhead = 'normal'
				for trigger in relation.trigger_list:
					trig_node = self.add_dbobject(trigger)
					trig_edge = rel_node.connect_to(trig_node)
					trig_edge.label = ('<%s %s>' % (trigger.trigger_time, trigger.trigger_event)).lower()
					trig_edge.arrowhead = 'vee'
					for dependency in trigger.dependency_list:
						dep_node = self.add_dbobject(dependency)
						dep_edge = trig_node.connect_to(dep_node)
						dep_edge.label = '<uses>'
						dep_edge.arrowhead = 'onormal'
		for trigger in schema.trigger_list:
			rel_node = self.add_dbobject(trigger.relation)
			trig_node = self.add_dbobject(trigger)
			trig_edge = rel_node.connect_to(trig_node)
			trig_edge.label = ('<%s %s>' % (trigger.trigger_time, trigger.trigger_event)).lower()
			trig_edge.arrowhead = 'vee'
			for dependency in trigger.dependency_list:
				dep_node = self.add_dbobject(dependency)
				dep_edge = trig_node.connect_to(dep_node)
				dep_edge.label = '<uses>'
				dep_edge.arrowhead = 'onormal'
