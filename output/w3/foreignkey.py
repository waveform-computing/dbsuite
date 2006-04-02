#!/bin/env python
# $Header$
# vim: set noet sw=4 ts=4:

import sys
import os.path
import logging
from output.w3.htmlutils import *

def write(self, key):
	"""Outputs the documentation for a foreign key object.

	Note that this function becomes the writeForeignKey method of the
	Output class in the output.w3 module.
	"""
	logging.debug("Writing documentation for foreign key %s to %s" % (key.name, filename(key)))
	position = 0
	fields = []
	for (field1, field2) in key.fields:
		fields.append((field1, field2, position))
		position += 1
	fields = sorted(fields, key=lambda(field1, field2, position): field1.name)
	doc = self.newDocument(key)
	doc.addSection(id='description', title='Description')
	doc.addContent('<p>%s</p>' % (self.formatDescription(key.description)))
	doc.addSection(id='attributes', title='Attributes')
	doc.addPara("""The following table notes various "vital statistics"
		of the foreign key.""")
	doc.addContent(makeTable(
		head=[(
			"Attribute",
			"Value",
			"Attribute",
			"Value"
		)],
		data=[
			(
				'Referenced Table',
				linkTo(key.refTable),
				'Referenced Key',
				linkTo(key.refKey),
			),
			(
				popupLink("created.html", "Created"),
				key.created,
				popupLink("createdby.html", "Created By"),
				escape(key.definer),
			),
			(
				popupLink("enforced.html", "Enforced"),
				key.enforced,
				popupLink("queryoptimize.html", "Query Optimizing"),
				key.queryOptimize,
			),
			(
				popupLink("deleterule.html", "Delete Rule"),
				key.deleteRule,
				popupLink("updaterule.html", "Update Rule"),
				key.updateRule,
			),
		]))
	if len(fields) > 0:
		doc.addSection(id='fields', title='Fields')
		doc.addPara("""The following table contains the fields of the key
			(in alphabetical order) along with the position of the field in
			the key, the field in the parent table that is referenced by
			the key, and the description of the field in the key's table.""")
		doc.addContent(makeTable(
			head=[(
				"#",
				"Field",
				"Parent",
				"Description"
			)],
			data=[(
				position + 1,
				escape(field1.name),
				escape(field2.name),
				self.formatDescription(field1.description)
			) for (field1, field2, position) in fields]
		))
	doc.addSection('sql', 'SQL Definition')
	doc.addPara("""The SQL which can be used to create the key is given
		below. Note that this is not necessarily the same as the actual
		statement used to create the key (it has been reconstructed from
		the content of the system catalog tables and may differ in a number
		of areas).""")
	doc.addContent(makeTag('pre', {'class': 'sql'}, self.formatSql(key.createSql)))
	doc.write(os.path.join(self._path, filename(key)))

