#!/bin/env python
# $Header$
# vim: set noet sw=4 ts=4:

import sys
import os.path
import logging
from output.w3.htmlutils import *

def write(self, index):
	"""Outputs the documentation for an index object.

	Note that this function becomes the writeIndex method of the
	Output class in the output.w3 module.
	"""
	logging.debug("Writing documentation for index %s to %s" % (index.name, filename(index)))
	position = 0
	fields = []
	for (field, ordering) in index.fieldList:
		fields.append((field, ordering, position))
		position += 1
	fields = sorted(fields, key=lambda(field, ordering, position): field.name)
	doc = self.newDocument(index)
	doc.addSection(id='description', title='Description')
	doc.addContent('<p>%s</p>' % (self.formatDescription(index.description)))
	doc.addSection(id='attributes', title='Attributes')
	doc.addPara("""The following table notes various "vital statistics"
		of the index.""")
	if not index.clusterFactor is None:
		clusterRatio = index.clusterFactor # XXX Convert as necessary
	else:
		clusterRatio = index.clusterRatio
	head=[(
		"Attribute",
		"Value",
		"Attribute",
		"Value"
	)]
	data=[
		(
			'Table',
			linkTo(index.table),
			'Tablespace',
			linkTo(index.tablespace),
		),
		(
			popupLink("created.html", "Created"),
			index.created,
			popupLink("laststats.html", "Last Statistics"),
			index.statsUpdated,
		),
		(
			popupLink("createdby.html", "Created By"),
			escape(index.definer),
			popupLink("colcount.html", "# Columns"),
			len(fields),
		),
		(
			popupLink("unique.html", "Unique"),
			index.unique,
			popupLink("reversescans.html", "Reverse Scans"),
			index.reverseScans,
		),
		(
			popupLink("leafpages.html", "Leaf Pages"),
			index.leafPages,
			popupLink("sequentialpages.html", "Sequential Pages"),
			index.sequentialPages,
		),
		(
			popupLink("clusterratio.html", "Cluster Ratio"),
			clusterRatio, # see above
			popupLink("density.html", "Density"),
			index.density,
		),
		(
			popupLink("cardinality.html", "Cardinality"),
			formatContent(index.cardinality[0]),
			{'rowspan': len(index.cardinality[1]) + 1, '': popupLink("levels.html", "Levels")},
			{'rowspan': len(index.cardinality[1]) + 1, '': index.levels},
		),
	]
	for (cardix, card) in enumerate(index.cardinality[1]):
		data.append((
			popupLink("cardinality.html", "Key 1..%d Cardinality" % (cardix + 1)),
			formatContent(card),
		))
	doc.addContent(makeTable(data, head))
	if len(fields) > 0:
		doc.addSection(id='fields', title='Fields')
		doc.addPara("""The following table contains the fields of the index
			(in alphabetical order) along with the position of the field in
			the index, the ordering of the field (Ascending or Descending)
			and the description of the field.""")
		doc.addContent(makeTable(
			head=[(
				"#",
				"Name",
				"Order",
				"Description"
			)],
			data=[(
				position + 1,
				escape(field.name),
				ordering,
				self.formatDescription(field.description, firstline=True)
			) for (field, ordering, position) in fields]
		))
	doc.addSection('sql', 'SQL Definition')
	doc.addPara("""The SQL which created the index is given below.
		Note that this is not necessarily the same as the actual statement
		used to create the index (it has been reconstructed from the
		content of the system catalog tables and may differ in a number of
		areas).""")
	doc.addContent(makeTag('pre', {'class': 'sql'}, self.formatSql(index.createSql)))
	doc.write(os.path.join(self._path, filename(index)))

