# vim: set noet sw=4 ts=4:

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

class ViewDocument(HTMLObjectDocument):
	def generate_body(self):
		body = super(ViewDocument, self).generate_body()
		tag = self.tag
		body.append(
			tag.div(
				tag.h3('Description'),
				tag.p(self.format_comment(self.dbobject.description)),
				class_='section',
				id='description'
			)
		)
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
						),
						summary='View attributes'
						# XXX Include system?
					)
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
								tag.th('Description', class_='nosort')
							)
						),
						tag.tbody((
							tag.tr(
								tag.td(field.position + 1),
								tag.td(field.name),
								tag.td(field.datatype_str),
								tag.td(field.nullable),
								tag.td(self.format_comment(field.description, summary=True))
							) for field in self.dbobject.field_list
						)),
						id='field-ts',
						summary='View fields'
					),
					class_='section',
					id='fields'
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
						id='trigger-ts',
						summary='View triggers'
					),
					class_='section',
					id='triggers'
				)
			)
		if len(self.dbobject.dependent_list) > 0:
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
							) for dep in self.dbobject.dependent_list
						)),
						id='rdep-ts',
						summary='View dependents'
					),
					class_='section',
					id='dependents'
				)
			)
		if len(self.dbobject.dependency_list) > 0:
			body.append(
				tag.div(
					tag.h3('Dependencies'),
					tag.p_dependencies(self.dbobject),
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
							) for dep in self.dbobject.dependency_list
						)),
						id='dep-ts',
						summary='View dependencies'
					),
					class_='section',
					id='dependencies'
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

class ViewGraph(GraphObjectDocument):
	def generate(self):
		graph = super(ViewGraph, self).generate()
		view = self.dbobject
		view_node = graph.add(view, selected=True)
		for dependent in view.dependent_list:
			dep_node = graph.add(dependent)
			dep_edge = dep_node.connect_to(view_node)
			dep_edge.label = '<uses>'
			dep_edge.arrowhead = 'onormal'
		for dependency in view.dependency_list:
			dep_node = graph.add(dependency)
			dep_edge = view_node.connect_to(dep_node)
			dep_edge.label = '<uses>'
			dep_edge.arrowhead = 'onormal'
		return graph
