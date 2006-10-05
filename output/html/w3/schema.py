# $Header$
# vim: set noet sw=4 ts=4:

from db.schema import Schema
from output.html.w3.document import W3MainDocument

class W3SchemaDocument(W3MainDocument):
	def __init__(self, site, schema):
		assert isinstance(schema, Schema)
		super(W3SchemaDocument, self).__init__(site, schema)

	def create_sections(self):
		relations = [obj for (name, obj) in sorted(self.dbobject.relations.items(), key=lambda (name, obj): name)]
		routines = [obj for (name, obj) in sorted(self.dbobject.specific_routines.items(), key=lambda (name, obj): name)]
		indexes = [obj for (name, obj) in sorted(self.dbobject.indexes.items(), key=lambda (name, obj): name)]
		triggers = [obj for (name, obj) in sorted(self.dbobject.triggers.items(), key=lambda (name, obj): name)]
		self.section('description', 'Description')
		self.add(self.p(self.format_description(self.dbobject.description)))
		if len(relations) > 0:
			self.section('relations', 'Relations')
			self.add(self.table(
				head=[(
					"Name",
					"Type",
					"Description"
				)],
				data=[(
					self.a_to(relation),
					relation.type_name,
					self.format_description(relation.description, firstline=True)
				) for relation in relations]
			))
		if len(routines) > 0:
			self.section('routines', 'Routines')
			self.add(self.table(
				head=[(
					"Name",
					"Specific Name",
					"Type",
					"Description"
				)],
				data=[(
					self.a_to(routine),
					routine.specific_name,
					routine.type_name,
					self.format_description(routine.description, firstline=True)
				) for routine in routines]
			))
		if len(indexes) > 0:
			self.section('indexes', 'Indexes')
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
			self.add(self.table(
				head=[(
					"Name",
					"Timing",
					"Event",
					"Applies To",
					"Description")],
				data=[(
					self.a_to(trigger),
					trigger.trigger_time,
					trigger.trigger_event,
					self.a_to(trigger.relation, qualifiedname=True),
					self.format_description(trigger.description, firstline=True)
				) for trigger in triggers]
			))

