#!/bin/env python
# $Header$
# vim: set noet sw=4 ts=4:

import sys
import os.path
import logging
from output.w3.htmlutils import *

def write(self, alias):
	"""Outputs the documentation for an alias object.

	Note that this function becomes the writeAlias method of the
	Output class in the output.w3 module.
	"""
	logging.debug("Writing documentation for alias %s to %s" % (alias.name, filename(alias)))
	doc = self.newDocument(alias)
	doc.addSection(id='description', title='Description')
	doc.addContent('<p>%s</p>' % (self.formatDescription(alias.description)))
	doc.addSection(id='attributes', title='Attributes')
	doc.addPara("""The following table notes various "vital statistics"
		of the alias.""")
	head=[(
		"Attribute",
		"Value",
		"Attribute",
		"Value"
	)]
	data=[
		(
			popupLink("created.html", "Created"),
			alias.created,
			popupLink("createdby.html", "Created By"),
			escape(alias.definer),
		),
		(
			'Alias For',
			{'colspan': 3, '': linkTo(alias.relation)},
		),
	]
	doc.addContent(makeTable(data, head))
	doc.addSection('sql', 'SQL Definition')
	doc.addPara("""The SQL which created the alias is given below.
		Note that this is not necessarily the same as the actual statement
		used to create the alias (it has been reconstructed from the
		content of the system catalog tables and may differ in a number of
		areas).""")
	doc.addContent(makeTag('pre', {'class': 'sql'}, self.formatSql(alias.createSql)))
	doc.write(os.path.join(self._path, filename(alias)))

