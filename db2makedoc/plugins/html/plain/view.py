# vim: set noet sw=4 ts=4:

from db2makedoc.db import View
from db2makedoc.plugins.html.plain.document import PlainObjectDocument, PlainGraphDocument, tag

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

class PlainViewDocument(PlainObjectDocument):
	def __init__(self, site, view):
		assert isinstance(view, View)
		super(PlainViewDocument, self).__init__(site, view)
	
	def generate_sections(self):
		result = super(PlainViewDocument, self).generate_sections()
		fields = [obj for (name, obj) in sorted(self.dbobject.fields.items(), key=lambda (name, obj): name)]
		triggers = [obj for (name, obj) in sorted(self.dbobject.triggers.items(), key=lambda (name, obj): name)]
		dependencies = [obj for (name, obj) in sorted(self.dbobject.dependencies.items(), key=lambda (name, obj): name)]
		dependents = [obj for (name, obj) in sorted(self.dbobject.dependents.items(), key=lambda (name, obj): name)]
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
						tag.td(len(fields)),
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
		if len(fields) > 0:
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
							tag.td(field.name),
							tag.td(field.datatype_str),
							tag.td(field.nullable),
							tag.td(self.format_comment(field.description, summary=True))
						) for field in fields
					))
				)
			))
		if len(triggers) > 0:
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
						) for trigger in triggers
					))
				)
			))
		if len(dependents) > 0:
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
							tag.td(dep.type_name),
							tag.td(self.format_comment(dep.description, summary=True))
						) for dep in dependents
					))
				)
			))
		if len(dependencies) > 0:
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
							tag.td(dep.type_name),
							tag.td(self.format_comment(dep.description, summary=True))
						) for dep in dependencies
					))
				)
			))
		result.append((
			'diagram', 'Diagram',
			self.site.img_of(self.dbobject)
		))
		result.append((
			'sql', 'SQL Definition',
			self.format_sql(self.dbobject.create_sql, number_lines=True)
		))
		return result

class PlainViewGraph(PlainGraphDocument):
	def __init__(self, site, view):
		assert isinstance(view, View)
		super(PlainViewGraph, self).__init__(site, view)

	def generate(self):
		super(PlainViewGraph, self).generate()
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
