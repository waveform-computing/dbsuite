# vim: set noet sw=4 ts=4:

from db2makedoc.db import View
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

class W3ViewDocument(W3ObjectDocument):
	def __init__(self, site, view):
		assert isinstance(view, View)
		super(W3ViewDocument, self).__init__(site, view)
	
	def generate_sections(self):
		result = super(W3ViewDocument, self).generate_sections()
		result.append((
			'description', 'Description',
			tag.p(self.format_comment(self.dbobject.description))
		))
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
						tag.td(self.site.url_document('createdby.html').link()),
						tag.td(self.dbobject.owner)
					),
					tag.tr(
						tag.td(self.site.url_document('colcount.html').link()),
						tag.td(len(self.dbobject.field_list)),
						tag.td(self.site.url_document('readonly.html').link()),
						tag.td(self.dbobject.read_only)
					),
					tag.tr(
						tag.td(self.site.url_document('dependentrel.html').link()),
						tag.td(len(self.dbobject.dependent_list)),
						tag.td(self.site.url_document('dependenciesrel.html').link()),
						tag.td(len(self.dbobject.dependency_list))
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
							tag.th('Description')
						)
					),
					tag.tbody((
						tag.tr(
							tag.td(field.position + 1),
							tag.td(field.name, class_='nowrap'),
							tag.td(field.datatype_str, class_='nowrap'),
							tag.td(field.nullable),
							tag.td(self.format_comment(field.description, summary=True))
						) for field in self.dbobject.field_list
					))
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
							tag.th('Description')
						)
					),
					tag.tbody((
						tag.tr(
							tag.td(self.site.link_to(trigger)),
							tag.td(times[trigger.trigger_time]),
							tag.td(events[trigger.trigger_event]),
							tag.td(self.format_comment(trigger.description, summary=True))
						) for trigger in self.dbobject.trigger_list
					))
				)
			))
		if len(self.dbobject.dependent_list) > 0:
			result.append((
				'dependents', 'Dependent Relations',
				tag.table(
					tag.thead(
						tag.tr(
							tag.th('Name'),
							tag.th('Type'),
							tag.th('Description')
						)
					),
					tag.tbody((
						tag.tr(
							tag.td(self.site.link_to(dep)),
							tag.td(self.site.type_names[dep.__class__]),
							tag.td(self.format_comment(dep.description, summary=True))
						) for dep in self.dbobject.dependent_list
					))
				)
			))
		if len(self.dbobject.dependency_list) > 0:
			result.append((
				'dependencies', 'Dependencies',
				tag.table(
					tag.thead(
						tag.tr(
							tag.th('Name'),
							tag.th('Type'),
							tag.th('Description')
						)
					),
					tag.tbody((
						tag.tr(
							tag.td(self.site.link_to(dep)),
							tag.td(self.site.type_names[dep.__class__]),
							tag.td(self.format_comment(dep.description, summary=True))
						) for dep in self.dbobject.dependency_list
					))
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
					tag.p(tag.a('Line #s On/Off', href='#', onclick='javascript:return toggleLineNums("sqldef");', class_='zoom')),
					self.format_sql(self.dbobject.create_sql, number_lines=True, id='sqldef')
				]
			))
		return result

class W3ViewGraph(W3GraphDocument):
	def __init__(self, site, view):
		assert isinstance(view, View)
		super(W3ViewGraph, self).__init__(site, view)

	def generate(self):
		super(W3ViewGraph, self).generate()
		view = self.dbobject
		view_node = self.add(view, selected=True)
		for dependent in view.dependent_list:
			dep_node = self.add(dependent)
			dep_edge = dep_node.connect_to(view_node)
			dep_edge.label = '<uses>'
			dep_edge.arrowhead = 'onormal'
		for dependency in view.dependency_list:
			dep_node = self.add(dependency)
			dep_edge = view_node.connect_to(dep_node)
			dep_edge.label = '<uses>'
			dep_edge.arrowhead = 'onormal'
		return self.graph
