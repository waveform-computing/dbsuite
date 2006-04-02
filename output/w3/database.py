#!/bin/env python
# $Header$
# vim: set noet sw=4 ts=4:

import sys
import os.path
import logging
from output.w3.htmlutils import *

def write(self, database):
	"""Outputs the documentation for a database object.

	Note that this function becomes the writeDatabase method of the
	Output class in the output.w3 module.
	"""
	logging.debug("Writing documentation for database to %s" % (filename(database)))
	schemas = [obj for (name, obj) in sorted(database.schemas.items(), key=lambda (name, obj):name)]
	tbspaces = [obj for (name, obj) in sorted(database.tablespaces.items(), key=lambda (name, obj):name)]
	doc = self.newDocument(database)
	doc.addSection(id='description', title='Description')
	doc.addContent('<p>%s</p>' % (self.formatDescription(database.description)))
	if len(schemas) > 0:
		doc.addSection(id='schemas', title='Schemas')
		doc.addPara("""The following table contains all schemas (logical
			object containers) in the database. Click on a schema name to
			view the documentation for that schema, including a list of all
			objects that exist within it.""")
		doc.addContent(makeTable(
			head=[(
				"Name",
				"Description"
			)],
			data=[(
				linkTo(schema),
				self.formatDescription(schema.description)
			) for schema in schemas]
		))
	if len(tbspaces) > 0:
		doc.addSection(id='tbspaces', title='Tablespaces')
		doc.addPara("""The following table contains all tablespaces
			(physical object containers) in the database. Click on a
			tablespace name to view the documentation for that tablespace,
			including a list of all tables and/or indexes that exist within
			it.""")
		doc.addContent(makeTable(
			head=[(
				"Name",
				"Description"
			)],
			data=[(
				linkTo(tbspace),
				self.formatDescription(tbspace.description)
			) for tbspace in tbspaces]
		))
	doc.write(os.path.join(self._path, filename(database)))
