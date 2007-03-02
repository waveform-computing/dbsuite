# $Header$
# vim: set noet sw=4 ts=4:

from db2makedoc.db.index import Index
from db2makedoc.plugins.html.w3.document import W3MainDocument

class W3IndexDocument(W3MainDocument):
	def __init__(self, site, index):
		assert isinstance(index, Index)
		super(W3IndexDocument, self).__init__(site, index)

	def create_sections(self):
		fields = [(field, ordering, position) for (position, (field, ordering)) in enumerate(self.dbobject.field_list)]
		fields = sorted(fields, key=lambda (field, ordering, position): field.name)
		self.section('description', 'Description')
		self.add(self.p(self.format_comment(self.dbobject.description)))
		self.section('attributes', 'Attributes')
		self.add(self.p("""The following table notes various "vital statistics"
			of the index."""))
		if not self.dbobject.cluster_factor is None:
			cluster_ratio = self.dbobject.cluster_factor # XXX Convert as necessary
		else:
			cluster_ratio = self.dbobject.cluster_ratio
		head=[(
			"Attribute",
			"Value",
			"Attribute",
			"Value"
		)]
		data=[
			(
				'Table',
				self.a_to(self.dbobject.table),
				'Tablespace',
				self.a_to(self.dbobject.tablespace),
			),
			(
				self.a(self.site.documents['created.html']),
				self.dbobject.created,
				self.a(self.site.documents['laststats.html']),
				self.dbobject.stats_updated,
			),
			(
				self.a(self.site.documents['createdby.html']),
				self.dbobject.definer,
				self.a(self.site.documents['colcount.html']),
				len(fields),
			),
			(
				self.a(self.site.documents['unique.html']),
				self.dbobject.unique,
				self.a(self.site.documents['reversescans.html']),
				self.dbobject.reverse_scans,
			),
			(
				self.a(self.site.documents['leafpages.html']),
				self.dbobject.leaf_pages,
				self.a(self.site.documents['sequentialpages.html']),
				self.dbobject.sequential_pages,
			),
			(
				self.a(self.site.documents['clusterratio.html']),
				cluster_ratio, # see above
				self.a(self.site.documents['density.html']),
				self.dbobject.density,
			),
			(
				self.a(self.site.documents['cardinality.html']),
				self.dbobject.cardinality[0],
				(self.a(self.site.documents['levels.html']), {'rowspan': str(len(self.dbobject.cardinality[1]) + 1)}),
				(self.dbobject.levels,                       {'rowspan': str(len(self.dbobject.cardinality[1]) + 1)}),
			),
		]
		for (cardix, card) in enumerate(self.dbobject.cardinality[1]):
			data.append((
				self.a(self.site.documents['cardinality.html']),
				card,
			))
		self.add(self.table(head=head, data=data))
		if len(fields) > 0:
			self.section('fields', 'Fields')
			self.add(self.table(
				head=[(
					"#",
					"Name",
					"Order",
					"Description"
				)],
				data=[(
					position + 1,
					field.name,
					ordering,
					self.format_comment(field.description, summary=True)
				) for (field, ordering, position) in fields]
			))
		self.section('sql', 'SQL Definition')
		self.add(self.pre(self.format_sql(self.dbobject.create_sql),
			attrs={'class': 'sql'}))

