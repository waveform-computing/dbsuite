#!/bin/env python
# $Header$
# vim: set noet sw=4 ts=4:

import db.view
import output.html.w3

class W3ViewDocument(output.html.W3.W3Document):
	def __init__(self, dbobject, htmlver=XHTML10, htmlstyle=STRICT):
		assert isinstance(self.dbobject, db.view.View)
		super(W3ViewDocument, self).__init__(dbobject, htmlver, htmlstyle)
	
	def create_sections(self):
		fields = [obj for (name, obj) in sorted(self.dbobject.fields.items(), key=lambda (name, obj): name)]
		triggers = [obj for (name, obj) in sorted(self.dbobject.triggers.items(), key=lambda (name, obj): name)]
		dependencies = [obj for (name, obj) in sorted(self.dbobject.dependencies.items(), key=lambda (name, obj): name)]
		dependents = [obj for (name, obj) in sorted(self.dbobject.dependents.items(), key=lambda (name, obj): name)]
		self.section('description', 'Description')
		self.add('<p>%s</p>' % (self.format_description(self.dbobject.description)))
		self.section('attributes', 'Attributes')
		self.add(self.p("""The following table notes various "vital statistics"
			of the view."""))
		self.add(makeTable(
			head=[(
				'Attribute',
				'Value',
				'Attribute',
				'Value'
			)],
			data=[
				(
					self.a('created.html', 'Created', popup=True),
					self.dbobject.created,
					self.a('createdby.html', 'Created By', popup=True),
					self.dbobject.definer,
				),
				(
					self.a('colcount.html', '# Columns', popup=True),
					len(self.dbobject.fields),
					self.a('valid.html', 'Valid', popup=True),
					self.dbobject.valid,
				),
				(
					self.a('readonly.html', 'Read Only', popup=True),
					self.dbobject.readOnly,
					self.a('checkoption.html', 'Check Option', popup=True),
					self.dbobject.check,
				),
				(
					self.a('dependentrel.html', 'Dependent Relations', popup=True),
					len(self.dbobject.dependentList),
					self.a('dependenciesrel.html', 'Dependencies', popup=True),
					len(self.dbobject.dependencyList),
				)
			]))
		if len(fields) > 0:
			self.section('fields', 'Field Descriptions')
			self.add(self.p("""The following table contains the fields of the
				view (in alphabetical order) along with the description of each
				field.  For information on the structure and attributes of each
				field see the Field Schema section below."""))
			self.add(makeTable(
				head=[(
					'Name',
					'Description'
				)],
				data=[(
					field.name,
					self.format_description(field.description, firstline=True)
				) for field in fields]
			))
			self.section('field_schema', 'Field Schema')
			self.add(self.p("""The following table contains the attributes of
				the fields of the view (again, fields are in alphabetical
				order, though the # column indicates the 1-based position of
				the field within the view)."""))
			self.add(makeTable(
				head=[(
					'#',
					'Name',
					'Type',
					'Nulls'
				)],
				data=[(
					field.position + 1,
					field.name,
					field.datatypeStr,
					field.nullable
				) for field in fields]
			))
		if len(triggers) > 0:
			self.section('triggers', 'Triggers')
			self.add(self.p("""The following table details the triggers defined
				against the view, including which actions fire the trigger and
				when. For more information about an individual trigger click on
				the trigger name."""))
			self.add(makeTable(
				head=[(
					'Name',
					'Timing',
					'Event',
					'Description'
				)],
				data=[(
					self.a_to(trigger, qualifiedname=True),
					trigger.triggerTime,
					trigger.triggerEvent,
					self.format_description(trigger.description, firstline=True)
				) for trigger in triggers]
			))
		if len(dependents) > 0:
			self.section('dependents', 'Dependent Relations')
			self.add(self.p("""The following table lists all relations (views
				or materialized query tables) which reference this view in
				their associated SQL statement."""))
			self.add(makeTable(
				head=[(
					'Name',
					'Type',
					'Description'
				)],
				data=[(
					self.a_to(dep, qualifiedname=True),
					dep.typeName,
					self.format_description(dep.description, firstline=True)
				) for dep in dependents]
			))
		if len(dependencies) > 0:
			self.section('dependencies', 'Dependencies')
			self.add(self.p("""The following table lists all relations (tables,
				views, materialized query tables, etc.) which this view
				references in it's SQL statement."""))
			self.add(makeTable(
				head=[(
					'Name',
					'Type',
					'Description'
				)],
				data=[(
					self.a_to(dep, qualifiedname=True),
					dep.typeName,
					self.format_description(dep.description, firstline=True)
				) for dep in dependencies]
			))
		self.section('sql', 'SQL Definition')
		self.add(self.p("""The SQL which created the view is given below.  Note
			that, in the process of storing the definition of a view, DB2
			removes much of the formatting, hence the formatting in the
			statement below (which this system attempts to reconstruct) is not
			necessarily the formatting of the original statement."""))
		self.add(self.pre(self.format_sql(self.dbobject.createSql), attrs={'class': 'sql'}))

