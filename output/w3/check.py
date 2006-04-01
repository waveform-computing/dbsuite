#!/bin/env python
# $Header$
# vim: set noet sw=4 ts=4:

import sys
import os.path
import logging
from htmlutils import *

def write(self, check):
	"""Outputs the documentation for a check object.

	Note that this function becomes the writeCheck method of the
	Output class in the output.w3 module.
	"""
	logging.debug("Writing documentation for check constraint %s to %s" % (check.name, filename(check)))
	fields = sorted(list(check.fields), key=lambda(field): field.name)
	doc = self.newDocument(check)
	doc.addSection(id='description', title='Description')
	doc.addContent('<p>%s</p>' % (self.formatDescription(check.description)))
	doc.addSection(id='attributes', title='Attributes')
	doc.addPara("""The following table notes various "vital statistics"
		of the check.""")
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
				check.created,
				popupLink("createdby.html", "Created By"),
				escape(check.definer),
			),
			(
				popupLink("enforced.html", "Enforced"),
				check.enforced,
				popupLink("queryoptimize.html", "Query Optimizing"),
				check.queryOptimize,
			),
		]))
	if len(fields) > 0:
		doc.addSection(id='fields', title='Fields')
		doc.addPara("""The following table contains the fields that the
			check references in it's SQL expression, and the description of
			the field in the check's table.""")
		doc.addContent(makeTable(
			head=[(
				"Field",
				"Description"
			)],
			data=[(
				escape(field.name),
				self.formatDescription(field.description)
			) for field in fields]
		))
	doc.addSection('sql', 'SQL Definition')
	doc.addPara("""The SQL which can be used to create the check is given
		below. Note that this is not necessarily the same as the actual
		statement used to create the check (it has been reconstructed from
		the content of the system catalog tables and may differ in a number
		of areas).""")
	doc.addContent(makeTag('pre', {'class': 'sql'}, self.formatSql(check.createSql)))
	doc.write(os.path.join(self._path, filename(check)))

