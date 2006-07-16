#!/usr/bin/env python
# $Header$
# vim: set noet sw=4 ts=4:

import db.schema
import output.html.w3

class W3SchemaDocument(output.html.w3.W3Document):
	def __init__(self, dbobject, htmlver=XHTML10, htmlstyle=STRICT):
		assert isinstance(self.dbobject, db.schema.Schema)
		super(W3SchemaDocument, self).__init__(dbobject, htmlver, htmlstyle)

	def create_sections(self):
		relations = [obj for (name, obj) in sorted(self.dbobject.relations.items(), key=lambda (name, obj): name)]
		routines = [obj for (name, obj) in sorted(self.dbobject.specificRoutines.items(), key=lambda (name, obj): name)]
		indexes = [obj for (name, obj) in sorted(self.dbobject.indexes.items(), key=lambda (name, obj): name)]
		triggers = [obj for (name, obj) in sorted(self.dbobject.triggers.items(), key=lambda (name, obj): name)]
		self.section('description', 'Description')
		self.add(self.p(self.format_description(self.dbobject.description)))
		if len(relations) > 0:
			self.section('relations', 'Relations')
			self.add(self.p("""The following table contains all the relations
				(tables and views) that the schema contains. Click on a
				relation name to view the documentation for that relation,
				including a list of all objects that exist within it, and that
				the relation references."""))
			self.add(self.table(
				head=[(
					"Name",
					"Type",
					"Description"
				)],
				data=[(
					self.a_to(relation),
					relation.typeName,
					self.format_description(relation.description, firstline=True)
				) for relation in relations]
			))
			if len(routines) > 0:
				self.section('routines', 'Routines')
			self.add(self.p("""The following table contains all the routines
				(functions, stored procedures, and methods) that the schema
				contains. Click on a routine name to view the documentation for
				that routine."""))
			self.add(self.table(
				head=[(
					"Name",
					"Specific Name",
					"Type",
					"Description"
				)],
				data=[(
					self.a_to(routine),
					routine.specificName,
					routine.typeName,
					self.format_description(routine.description, firstline=True)
				) for routine in routines]
			))
		if len(indexes) > 0:
			self.section('indexes', 'Indexes')
			self.add(self.p("""The following table contains all the indexes
				that the schema contains. Click on an index name to view the
				documentation for that index.""")
			self.add(self.table(
				head=[(
					"Name",
					"Unique",
					"Applies To",
					"Description")],
				data=[(
					self.a_to(index),
					index.unique,
					self.a_to(index.table, qualifiedname=True),
					self.format_description(index.description, firstline=True)
				) for index in indexes]
			))
		if len(triggers) > 0:
			self.section('triggers', 'Triggers')
			self.add(self.p("""The following table contains all the triggers
				that the schema contains. Click on a trigger name to view the
				documentation for that trigger."""))
			self.add(self.table(
				head=[(
					"Name",
					"Timing",
					"Event",
					"Applies To",
					"Description")],
				data=[(
					self.a_to(trigger),
					trigger.triggerTime,
					trigger.triggerEvent,
					self.a_to(trigger.relation, qualifiedName=True),
					self.format_description(trigger.description, firstline=True)
				) for trigger in triggers]
			))

