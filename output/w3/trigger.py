#!/bin/env python
# $Header$
# vim: set noet sw=4 ts=4:

import sys
import os.path
import logging
from output.w3.htmlutils import *

def write(self, trigger):
	"""Outputs the documentation for a trigger object.

	Note that this function becomes the writeTrigger method of the
	Output class in the output.w3 module.
	"""
	logging.debug("Writing documentation for trigger %s to %s" % (trigger.name, filename(trigger)))
	doc = self.newDocument(trigger)
	doc.addSection(id='description', title='Description')
	doc.addContent('<p>%s</p>' % (self.formatDescription(trigger.description)))
	doc.addSection(id='attributes', title='Attributes')
	doc.addPara("""The following table notes various "vital statistics"
		of the trigger.""")
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
				trigger.created,
				popupLink("createdby.html", "Created By"),
				escape(trigger.definer),
			),
			(
				"Relation",
				linkTo(trigger.relation, qualifiedName=True),
				popupLink("valid.html", "Valid"),
				trigger.valid,
			),
			(
				popupLink("triggertiming.html", "Timing"),
				trigger.triggerTime,
				popupLink("triggerevent.html", "Event"),
				trigger.triggerEvent,
			),
		]))
	doc.addSection('sql', 'SQL Definition')
	doc.addPara("""The SQL which created the trigger is given below.
		Note that, in the process of storing the definition of a trigger,
		DB2 removes much of the formatting, hence the formatting in the 
		statement below (which this system attempts to reconstruct) is
		not necessarily the formatting of the original statement.""")
	doc.addContent(makeTag('pre', {'class': 'sql'}, self.formatSql(trigger.createSql, terminator="!")))
	doc.write(os.path.join(self._path, filename(trigger)))

