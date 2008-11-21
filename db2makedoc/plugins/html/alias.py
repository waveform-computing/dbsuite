# vim: set noet sw=4 ts=4:

from db2makedoc.db import View
from db2makedoc.plugins.html.document import HTMLObjectDocument, GraphObjectDocument

def _inc_index(i):
	if i is None:
		return i
	else:
		return i + 1

class AliasDocument(HTMLObjectDocument):
	def generate_body(self):
		body = super(AliasDocument, self).generate_body()
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
							tag.td('Alias For'),
							tag.td(self.site.link_to(self.dbobject.relation), colspan=3)
						)
					),
					summary='Alias attributes'
				),
				class_='section',
				id='attributes'
			)
		)
		if len(self.dbobject.field_list) > 0:
			if isinstance(self.dbobject.final_relation, View):
				table = tag.table(
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
					summary='Alias fields'
				)
			else:
				table = tag.table(
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
							tag.td(field.position + 1),
							tag.td(field.name),
							tag.td(field.datatype_str),
							tag.td(field.nullable),
							tag.td(_inc_index(field.key_index)), # XXX For Py2.5: field.key_index + 1 if field.key_index is not None else None,
							tag.td(field.cardinality),
							tag.td(self.format_comment(field.description, summary=True))
						) for field in self.dbobject.field_list
					)),
					id='field-ts',
					summary='Alias fields'
				)
			body.append(
				tag.div(
					tag.h3('Fields'),
					tag.p_relation_fields(self.dbobject),
					table,
					class_='section',
					id='fields'
				)
			)
		if len(self.dbobject.dependent_list) > 0:
			body.append(
				tag.div(
					tag.h3('Dependent Relations'),
					tag.p_dependent_relations(self.dbobject),
					tag.p_tablesort(),
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
						id='dep-ts',
						summary='Alias dependents'
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


class AliasGraph(GraphObjectDocument):
	def generate(self):
		graph = super(AliasGraph, self).generate()
		alias = self.dbobject
		alias_node = graph.add(alias, selected=True)
		target_node = graph.add(alias.relation)
		target_edge = alias_node.connect_to(target_node)
		target_edge.label = '<for>'
		target_edge.arrowhead = 'onormal'
		for dependent in alias.dependent_list:
			dep_node = graph.add(dependent)
			dep_edge = dep_node.connect_to(alias_node)
			dep_edge.label = '<uses>'
			dep_edge.arrowhead = 'onormal'
		return graph

