#!/bin/env python
# $Header$
# vim: set noet sw=4 ts=4:

import sys
import os.path
import logging
from htmlutils import *

def write(self, tbspace):
	"""Outputs the documentation for a tablespace object.

	Note that this function becomes the writeTablespace method of the
	Output class in the output.w3 module.
	"""
	logging.debug("Writing documentation for tablespace %s to %s" % (tbspace.name, filename(tbspace)))
	tables = [obj for (name, obj) in sorted(tbspace.tables.items(), key=lambda (name, obj): name)]
	indexes = [obj for (name, obj) in sorted(tbspace.indexes.items(), key=lambda (name, obj): name)]
	doc = self.newDocument(tbspace)
	doc.addSection(id='description', title='Description')
	doc.addContent('<p>%s</p>' % (self.formatDescription(tbspace.description)))
	doc.addSection(id='attributes', title='Attributes')
	doc.addPara("""The following table notes various "vital statistics"
		of the tablespace.""")
	doc.addContent(makeTable(
		head=[(
			"Attribute",
			"Value",
			"Attribute",
			"Value"
		)],
		data=[
			(
				popupLink("created.html", "Created"),
				tbspace.created,
				popupLink("tables.html", "# Tables"),
				len(tables),
			),
			(
				popupLink("createdby.html", "Created By"),
				escape(tbspace.definer),
				popupLink("cardinality.html", "# Indexes"),
				len(indexes),
			),
			(
				popupLink("managedby.html", "Managed By"),
				escape(tbspace.managedBy),
				popupLink("tbspacetype.html", "Data Type"),
				escape(tbspace.dataType),
			),
			(
				popupLink("extentsize.html", "Extent Size"),
				tbspace.extentSize,
				popupLink("prefetchsize.html", "Prefetch Size"),
				tbspace.prefetchSize,
			),
			(
				popupLink("pagesize.html", "Page Size"),
				tbspace.pageSize,
				popupLink("droprecovery.html", "Drop Recovery"),
				tbspace.dropRecovery,
			),
		]))
	if len(tables) > 0:
		doc.addSection(id='tables', title='Tables')
		doc.addPara("""The following table contains all the tables that
			the tablespace contains. Click on a table name to view the
			documentation for that table.""")
		doc.addContent(makeTable(
			head=[(
				"Name",
				"Description"
			)],
			data=[(
				linkTo(table, qualifiedName=True),
				self.formatDescription(table.description)
			) for table in tables]
		))
	if len(indexes) > 0:
		doc.addSection(id='indexes', title='Indexes')
		doc.addPara("""The following table contains all the indexes that
			the tablespace contains. Click on an index name to view the
			documentation for that index.""")
		doc.addContent(makeTable(
			head=[(
				"Name",
				"Applies To",
				"Description"
			)],
			data=[(
				linkTo(index, qualifiedName=True),
				linkTo(index.table, qualifiedName=True),
				self.formatDescription(index.description)
			) for index in indexes]
		))
	doc.write(os.path.join(self._path, filename(tbspace)))

