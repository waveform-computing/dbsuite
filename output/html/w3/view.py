# $Header$
# vim: set noet sw=4 ts=4:

from db.view import View
from dot.graph import Graph, Node, Edge, Cluster
from output.html.w3.document import W3MainDocument, W3GraphDocument

class W3ViewDocument(W3MainDocument):
	def __init__(self, site, view):
		assert isinstance(view, View)
		super(W3ViewDocument, self).__init__(site, view)
	
	def create_sections(self):
		fields = [obj for (name, obj) in sorted(self.dbobject.fields.items(), key=lambda (name, obj): name)]
		triggers = [obj for (name, obj) in sorted(self.dbobject.triggers.items(), key=lambda (name, obj): name)]
		dependencies = [obj for (name, obj) in sorted(self.dbobject.dependencies.items(), key=lambda (name, obj): name)]
		dependents = [obj for (name, obj) in sorted(self.dbobject.dependents.items(), key=lambda (name, obj): name)]
		self.section('description', 'Description')
		self.add(self.p(self.format_description(self.dbobject.description)))
		self.section('attributes', 'Attributes')
		self.add(self.table(
			head=[(
				'Attribute',
				'Value',
				'Attribute',
				'Value'
			)],
			data=[
				(
					self.a(self.site.documents['created.html']),
					self.dbobject.created,
					self.a(self.site.documents['createdby.html']),
					self.dbobject.definer,
				),
				(
					self.a(self.site.documents['colcount.html']),
					len(self.dbobject.fields),
					self.a(self.site.documents['valid.html']),
					self.dbobject.valid,
				),
				(
					self.a(self.site.documents['readonly.html']),
					self.dbobject.read_only,
					self.a(self.site.documents['checkoption.html']),
					self.dbobject.check,
				),
				(
					self.a(self.site.documents['dependentrel.html']),
					len(self.dbobject.dependent_list),
					self.a(self.site.documents['dependenciesrel.html']),
					len(self.dbobject.dependency_list),
				)
			]))
		if len(fields) > 0:
			self.section('fields', 'Field Descriptions')
			self.add(self.table(
				head=[(
					'Name',
					'Description'
				)],
				data=[(
					field.name,
					self.format_description(field.description, firstline=True)
				) for field in fields]
			))
			self.section('field_schema', 'Field Schema')
			self.add(self.table(
				head=[(
					'#',
					'Name',
					'Type',
					'Nulls'
				)],
				data=[(
					field.position + 1,
					field.name,
					field.datatype_str,
					field.nullable
				) for field in fields]
			))
		if len(triggers) > 0:
			self.section('triggers', 'Triggers')
			self.add(self.table(
				head=[(
					'Name',
					'Timing',
					'Event',
					'Description'
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
					'Name',
					'Type',
					'Description'
				)],
				data=[(
					self.a_to(dep, qualifiedname=True),
					dep.type_name,
					self.format_description(dep.description, firstline=True)
				) for dep in dependents]
			))
		if len(dependencies) > 0:
			self.section('dependencies', 'Dependencies')
			self.add(self.table(
				head=[(
					'Name',
					'Type',
					'Description'
				)],
				data=[(
					self.a_to(dep, qualifiedname=True),
					dep.type_name,
					self.format_description(dep.description, firstline=True)
				) for dep in dependencies]
			))
		self.section('diagram', 'Diagram')
		self.add(self.img_of(self.dbobject))
		self.section('sql', 'SQL Definition')
		self.add(self.pre(self.format_sql(self.dbobject.create_sql), attrs={'class': 'sql'}))

class W3ViewGraph(W3GraphDocument):
	def __init__(self, site, view):
		assert isinstance(view, View)
		super(W3ViewGraph, self).__init__(site, view)

	def create_graph(self):
		view = self.dbobject
		view_node = self.add_dbobject(view, selected=True)
		for dependent in view.dependent_list:
			dep_node = self.add_dbobject(dependent)
			dep_edge = dep_node.connect_to(view_node)
			dep_edge.label = '<uses>'
		for dependency in view.dependency_list:
			dep_node = self.add_dbobject(dependency)
			dep_edge = view_node.connect_to(dep_node)
			dep_edge.label = '<uses>'
