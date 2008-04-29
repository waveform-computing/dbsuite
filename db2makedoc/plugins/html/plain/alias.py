# vim: set noet sw=4 ts=4:

from db2makedoc.db import Alias
from db2makedoc.plugins.html.plain.document import PlainMainDocument, PlainGraphDocument

class PlainAliasDocument(PlainMainDocument):
	def __init__(self, site, alias):
		assert isinstance(alias, Alias)
		super(PlainAliasDocument, self).__init__(site, alias)

	def _create_sections(self):
		fields = [obj for (name, obj) in sorted(self.dbobject.fields.items(), key=lambda (name, obj): name)]
		dependents = [obj for (name, obj) in sorted(self.dbobject.dependents.items(), key=lambda (name, obj): name)]
		self._section('description', 'Description')
		self._add(self._p(self._format_comment(self.dbobject.description)))
		self._section('attributes', 'Attributes')
		self._add(self._table(
			head=[(
				'Attribute',
				'Value',
				'Attribute',
				'Value'
			)],
			data=[
				(
					'Created',
					self.dbobject.created,
					'Owner',
					self.dbobject.owner,
				),
				(
					'Alias For',
					(self._a_to(self.dbobject.relation, qualifiedname=True), {'colspan': 3}),
				),
			]
		))
		if len(fields) > 0:
			self._section('fields', 'Fields')
			self._add(self._table(
				head=[(
					"#",
					"Name",
					"Type",
					"Nulls",
					"Key Pos",
					"Cardinality",
					"Description",
				)],
				data=[(
					field.position + 1,
					field.name,
					field.datatype_str,
					field.nullable,
					field.key_index,
					field.cardinality,
					self._format_comment(field.description, summary=True),
				) for field in fields]
			))
		if len(dependents) > 0:
			self._section('dependents', 'Dependent Relations')
			self._add(self._table(
				head=[(
					"Name",
					"Type",
					"Description"
				)],
				data=[(
					self._a_to(dep, qualifiedname=True),
					dep.type_name,
					self._format_comment(dep.description, summary=True)
				) for dep in dependents]
			))
		self._section('diagram', 'Diagram')
		self._add(self._img_of(self.dbobject))
		self._section('sql', 'SQL Definition')
		self._add(self._pre(self._format_sql(self.dbobject.create_sql),
			attrs={'class': 'sql'}))

class PlainAliasGraph(PlainGraphDocument):
	def __init__(self, site, alias):
		assert isinstance(alias, Alias)
		super(PlainAliasGraph, self).__init__(site, alias)
	
	def _create_graph(self):
		super(PlainAliasGraph, self)._create_graph()
		alias = self.dbobject
		alias_node = self._add_dbobject(alias, selected=True)
		target_node = self._add_dbobject(alias.relation)
		target_edge = alias_node.connect_to(target_node)
		target_edge.label = '<for>'
		target_edge.arrowhead = 'onormal'
		for dependent in alias.dependent_list:
			dep_node = self._add_dbobject(dependent)
			dep_edge = dep_node.connect_to(alias_node)
			dep_edge.label = '<uses>'
			dep_edge.arrowhead = 'onormal'

