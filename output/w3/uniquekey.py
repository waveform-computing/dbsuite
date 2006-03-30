#!/bin/env python
# $Header$
# vim: set noet sw=4 ts=4:

import sys
import os.path
import logging
from htmlutils import *

def write(self, key):
	"""Outputs the documentation for a unique key object.

	Note that this function becomes the writeUniqueKey method of the
	Output class in the output.w3 module.
	"""
	logging.debug("Writing documentation for unique key %s to %s" % (key.name, filename(key)))
	position = 0
	fields = []
	for field in key.fields:
		fields.append((field, position))
		position += 1
	fields = sorted(fields, key=lambda(field, position): field.name)
	doc = self.newDocument(key)
	doc.addSection(id='attributes', title='Attributes')
	doc.addPara("""The following table notes various "vital statistics"
		of the unique key.""")
	doc.addContent(makeTable(
		head=[(
			"Attribute",
			"Value",
			"Attribute",
			"Value"
		)],
		data=[
			(
				popupLink("createdby.html", "Created By"),
				escape(key.definer),
				popupLink("colcount.html", "# Columns"),
				len(fields),
			),
		]))
	if len(fields) > 0:
		doc.addSection(id='fields', title='Fields')
		doc.addPara("""The following table contains the fields of the key
			(in alphabetical order) along with the position of the field in
			the key, and the description of the field in the key's table.""")
		doc.addContent(makeTable(
			head=[(
				"#",
				"Field",
				"Description"
			)],
			data=[(
				position + 1,
				escape(field.name),
				self.formatDescription(field.description)
			) for (field, position) in fields]
		))
	doc.addSection('sql', 'SQL Definition')
	doc.addPara("""The SQL which can be used to create the key is given
		below. Note that this is not necessarily the same as the actual
		statement used to create the key (it has been reconstructed from
		the content of the system catalog tables and may differ in a number
		of areas).""")
	doc.addContent(makeTag('pre', {'class': 'sql'}, self.formatSql(key.createSql)))
	doc.write(os.path.join(self._path, filename(key)))

