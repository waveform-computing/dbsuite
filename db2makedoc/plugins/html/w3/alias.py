# $Header$
# vim: set noet sw=4 ts=4:

from db2makedoc.db.alias import Alias
from db2makedoc.plugins.html.w3.document import W3MainDocument, W3GraphDocument

class W3AliasDocument(W3MainDocument):
	def __init__(self, site, alias):
		assert isinstance(alias, Alias)
		super(W3AliasDocument, self).__init__(site, alias)

	def create_sections(self):
		fields = [obj for (name, obj) in sorted(self.dbobject.fields.items(), key=lambda (name, obj): name)]
		dependents = [obj for (name, obj) in sorted(self.dbobject.dependents.items(), key=lambda (name, obj): name)]
		self.section('description', 'Description')
		self.add(self.p(self.format_comment(self.dbobject.description)))
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
					self.dbobject.owner,
				),
				(
					'Alias For',
					(self.a_to(self.dbobject.relation, qualifiedname=True), {'colspan': 3}),
				),
			]
		))
		if len(fields) > 0:
			self.section('field_desc', 'Field Descriptions')
			self.add(self.table(
				head=[(
					"Name",
					"Description"
				)],
				data=[(
					field.name,
					self.format_comment(field.description, summary=True)
				) for field in fields]
			))
			self.section('field_schema', 'Field Schema')
			self.add(self.table(
				head=[(
					"#",
					"Name",
					"Type",
					"Nulls",
					"Key Pos",
					"Cardinality"
				)],
				data=[(
					field.position + 1,
					field.name,
					field.datatype_str,
					field.nullable,
					field.key_index,
					field.cardinality
				) for field in fields]
			))
		if len(dependents) > 0:
			self.section('dependents', 'Dependent Relations')
			self.add(self.table(
				head=[(
					"Name",
					"Type",
					"Description"
				)],
				data=[(
					self.a_to(dep, qualifiedname=True),
					dep.type_name,
					self.format_comment(dep.description, summary=True)
				) for dep in dependents]
			))
		self.section('diagram', 'Diagram')
		self.add(self.img_of(self.dbobject))
		self.section('sql', 'SQL Definition')
		self.add(self.pre(self.format_sql(self.dbobject.create_sql),
			attrs={'class': 'sql'}))

class W3AliasGraph(W3GraphDocument):
	def __init__(self, site, alias):
		assert isinstance(alias, Alias)
		super(W3AliasGraph, self).__init__(site, alias)
	
	def create_graph(self):
		super(W3AliasGraph, self).create_graph()
		alias = self.dbobject
		alias_node = self.add_dbobject(alias, selected=True)
		target_node = self.add_dbobject(alias.relation)
		target_edge = alias_node.connect_to(target_node)
		target_edge.label = '<for>'
		target_edge.arrowhead = 'onormal'
		for dependent in alias.dependent_list:
			dep_node = self.add_dbobject(dependent)
			dep_edge = dep_node.connect_to(alias_node)
			dep_edge.label = '<uses>'
			dep_edge.arrowhead = 'onormal'

