#!/bin/env python
# $Header$
# vim: set noet sw=4 ts=4:

from db.index import Index
from output.html.w3.document import W3Document

class W3IndexDocument(W3Document):
	def __init__(self, site, index):
		assert isinstance(index, Index)
		super(W3IndexDocument, self).__init__(site, index)

	def create_sections(self):
		fields = [(field, ordering, position) for (position, (field, ordering)) in enumerate(self.dbobject.fieldList)]
		fields = sorted(fields, key=lambda (field, ordering, position): field.name)
		self.section('description', 'Description')
		self.add(self.p(self.format_description(self.dbobject.description)))
		self.section('attributes', 'Attributes')
		self.add(self.p("""The following table notes various "vital statistics"
			of the index."""))
		if not self.dbobject.clusterFactor is None:
			clusterRatio = self.dbobject.clusterFactor # XXX Convert as necessary
		else:
			clusterRatio = self.dbobject.clusterRatio
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
				self.a("created.html", "Created", popup=True),
				self.dbobject.created,
				self.a("laststats.html", "Last Statistics", popup=True),
				self.dbobject.statsUpdated,
			),
			(
				self.a("createdby.html", "Created By", popup=True),
				self.dbobject.definer,
				self.a("colcount.html", "# Columns", popup=True),
				len(fields),
			),
			(
				self.a("unique.html", "Unique", popup=True),
				self.dbobject.unique,
				self.a("reversescans.html", "Reverse Scans", popup=True),
				self.dbobject.reverseScans,
			),
			(
				self.a("leafpages.html", "Leaf Pages", popup=True),
				self.dbobject.leafPages,
				self.a("sequentialpages.html", "Sequential Pages", popup=True),
				self.dbobject.sequentialPages,
			),
			(
				self.a("clusterratio.html", "Cluster Ratio", popup=True),
				clusterRatio, # see above
				self.a("density.html", "Density", popup=True),
				self.dbobject.density,
			),
			(
				self.a("cardinality.html", "Cardinality", popup=True),
				self.dbobject.cardinality[0],
				{'rowspan': len(self.dbobject.cardinality[1]) + 1, '': self.a("levels.html", "Levels", popup=True)},
				{'rowspan': len(self.dbobject.cardinality[1]) + 1, '': self.dbobject.levels},
			),
		]
		for (cardix, card) in enumerate(self.dbobject.cardinality[1]):
			data.append((
				self.a("cardinality.html", "Key 1..%d Cardinality" % (cardix + 1), popup=True),
				card,
			))
		self.add(self.table(head=head, data=data))
		if len(fields) > 0:
			self.section('fields', 'Fields')
			self.add(self.p("""The following table contains the fields of the
				index (in alphabetical order) along with the position of the
				field in the index, the ordering of the field (Ascending or
				Descending) and the description of the field."""))
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
					self.format_description(field.description, firstline=True)
				) for (field, ordering, position) in fields]
			))
		self.section('sql', 'SQL Definition')
		self.add(self.p("""The SQL which created the index is given below.
			Note that this is not necessarily the same as the actual statement
			used to create the index (it has been reconstructed from the
			content of the system catalog tables and may differ in a number of
			areas)."""))
		self.add(self.pre(self.format_sql(self.dbobject.createSql), attrs={'class': 'sql'}))

