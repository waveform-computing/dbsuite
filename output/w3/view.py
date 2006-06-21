#!/bin/env python
# $Header$
# vim: set noet sw=4 ts=4:

import sys
import os.path
import logging
from output.w3.htmlutils import *

def write(self, view):
	"""Outputs the documentation for a view object.

	Note that this function becomes the writeView method of the
	Output class in the output.w3 module.
	"""
	logging.debug("Writing documentation for view %s to %s" % (view.name, filename(view)))
	fields = [obj for (name, obj) in sorted(view.fields.items(), key=lambda (name, obj): name)]
	triggers = [obj for (name, obj) in sorted(view.triggers.items(), key=lambda (name, obj): name)]
	dependencies = [obj for (name, obj) in sorted(view.dependencies.items(), key=lambda (name, obj): name)]
	dependents = [obj for (name, obj) in sorted(view.dependents.items(), key=lambda (name, obj): name)]
	doc = self.newDocument(view)
	doc.addSection(id='description', title='Description')
	doc.addContent('<p>%s</p>' % (self.formatDescription(view.description)))
	doc.addSection(id='attributes', title='Attributes')
	doc.addPara("""The following table notes various "vital statistics"
		of the view.""")
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
				view.created,
				popupLink("createdby.html", "Created By"),
				escape(view.definer),
			),
			(
				popupLink("colcount.html", "# Columns"),
				len(view.fields),
				popupLink("valid.html", "Valid"),
				view.valid,
			),
			(
				popupLink("readonly.html", "Read Only"),
				view.readOnly,
				popupLink("checkoption.html", "Check Option"),
				escape(view.check),
			),
			(
				popupLink("dependentrel.html", "Dependent Relations"),
				len(view.dependentList),
				popupLink("dependenciesrel.html", "Dependencies"),
				len(view.dependencyList),
			)
		]))
	if len(fields) > 0:
		doc.addSection(id='fields', title='Field Descriptions')
		doc.addPara("""The following table contains the fields of the view
			(in alphabetical order) along with the description of each field.
			For information on the structure and attributes of each field see
			the Field Schema section below.""")
		doc.addContent(makeTable(
			head=[(
				"Name",
				"Description"
			)],
			data=[(
				escape(field.name),
				self.formatDescription(field.description, firstline=True)
			) for field in fields]
		))
		doc.addSection(id='field_schema', title='Field Schema')
		doc.addPara("""The following table contains the attributes of the
			fields of the view (again, fields are in alphabetical order,
			though the # column indicates the 1-based position of the field
			within the view).""")
		doc.addContent(makeTable(
			head=[(
				"#",
				"Name",
				"Type",
				"Nulls"
			)],
			data=[(
				field.position + 1,
				escape(field.name),
				escape(field.datatypeStr),
				field.nullable
			) for field in fields]
		))
	if len(triggers) > 0:
		doc.addSection('triggers', 'Triggers')
		doc.addPara("""The following table details the triggers defined
			against the view, including which actions fire the trigger
			and when. For more information about an individual trigger
			click on the trigger name.""")
		doc.addContent(makeTable(
			head=[(
				"Name",
				"Timing",
				"Event",
				"Description"
			)],
			data=[(
				linkTo(trigger, qualifiedName=True),
				escape(trigger.triggerTime),
				escape(trigger.triggerEvent),
				self.formatDescription(trigger.description, firstline=True)
			) for trigger in triggers]
		))
	if len(dependents) > 0:
		doc.addSection('dependents', 'Dependent Relations')
		doc.addPara("""The following table lists all relations (views or
			materialized query tables) which reference this view in their
			associated SQL statement.""")
		doc.addContent(makeTable(
		    head=[(
				"Name",
				"Type",
				"Description"
			)],
		    data=[(
				linkTo(dep, qualifiedName=True),
				escape(dep.typeName),
				self.formatDescription(dep.description, firstline=True)
			) for dep in dependents]
		))
	if len(dependencies) > 0:
		doc.addSection('dependencies', 'Dependencies')
		doc.addPara("""The following table lists all relations (tables,
			views, materialized query tables, etc.) which this view
			references in it's SQL statement.""")
		doc.addContent(makeTable(
			head=[(
				"Name",
				"Type",
				"Description"
			)],
			data=[(
				linkTo(dep, qualifiedName=True),
				escape(dep.typeName),
				self.formatDescription(dep.description, firstline=True)
			) for dep in dependencies]
		))
	doc.addSection('sql', 'SQL Definition')
	doc.addPara("""The SQL which created the view is given below.
		Note that, in the process of storing the definition of a view, DB2
		removes much of the formatting, hence the formatting in the 
		statement below (which this system attempts to reconstruct) is
		not necessarily the formatting of the original statement.""")
	doc.addContent(makeTag('pre', {'class': 'sql'}, self.formatSql(view.createSql)))
	doc.write(os.path.join(self._path, filename(view)))

