#!/usr/bin/env python
# $Header$
# vim: set noet sw=4 ts=4:

import sys
import os.path
import logging
from htmlutils import *

def write(self, schema):
	"""Outputs the documentation for a schema object.

	Note that this function becomes the writeSchema method of the
	Output class in the output.w3 module.
	"""
	logging.debug("Writing documentation for schema %s to %s" % (schema.name, filename(schema)))
	relations = [obj for (name, obj) in sorted(schema.relations.items(), key=lambda (name, obj): name)]
	routines = [obj for (name, obj) in sorted(schema.specificRoutines.items(), key=lambda (name, obj): name)]
	indexes = [obj for (name, obj) in sorted(schema.indexes.items(), key=lambda (name, obj): name)]
	doc = self.newDocument(schema)
	doc.addSection(id='description', title='Description')
	doc.addContent('<p>%s</p>' % (schema.description))
	if len(relations) > 0:
		doc.addSection(id='relations', title='Relations')
		doc.addPara("""The following table contains all the relations
			(tables and views) that the schema contains. Click on a
			relation name to view the documentation for that relation,
			including a list of all objects that exist within it, and that
			the relation references.""")
		doc.addContent(makeTable(
			head=[(
				"Name",
				"Type",
				"Description"
			)],
			data=[(
				linkTo(relation),
				escape(relation.typeName),
				self.formatDescription(relation.description)
			) for relation in relations]
		))
	if len(routines) > 0:
		doc.addSection(id='routines', title='Routines')
		doc.addPara("""The following table contains all the routines
			(functions, stored procedures, and methods) that the schema
			contains. Click on a routine name to view the documentation for
			that routine.""")
		doc.addContent(makeTable(
			head=[(
				"Name",
				"Type",
				"Description"
			)],
			data=[(
				linkTo(routine),
				escape(routine.typeName),
				self.formatDescription(routine.description)
			) for routine in routines]
		))
	if len(indexes) > 0:
		doc.addSection(id='indexes', title='Indexes')
		doc.addPara("""The following table contains all the indexes that
			the schema contains. Click on an index name to view the
			documentation for that index.""")
		doc.addContent(makeTable(
			head=[(
				"Name",
				"Applies To",
				"Description")],
			data=[(
				linkTo(index),
				linkTo(index.table, qualifiedName=True),
				self.formatDescription(index.description)
			) for index in indexes]
		))
	doc.write(os.path.join(self._path, filename(schema)))

