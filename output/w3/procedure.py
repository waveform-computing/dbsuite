#!/bin/env python
# $Header$
# vim: set noet sw=4 ts=4:

import sys
import os.path
import logging
from output.w3.htmlutils import *
from sql.tokenizer import DB2UDBSQLTokenizer
from sql.formatter import SQLFormatter
from sql.htmlhighlighter import SQLHTMLHighlighter

def write(self, procedures):
	"""Outputs the documentation for a procedure.

	Note that this function becomes the writeProcedure method of the
	Output class in the output.w3 module.
	"""
	# Note that this method (unlike other methods) is passed a *list* of
	# procedures. Admittedly, procedures cannot currently be overloaded in DB2,
	# but they may be in the future (like functions) and this keeps the code
	# future proof without any detrimental effects
	for procedure in procedures:
		logging.debug("Writing documentation for procedure %s to %s" % (procedure.name, filename(procedure)))
		doc = self.newDocument(procedure)
		doc.addSection(id='description', title='Description')
		doc.addContent(makeTag('p', {}, makeTag('code', {'class': 'sql'}, self.formatPrototype(procedure.prototype))))
		doc.addContent(makeTag('p', {}, self.formatDescription(procedure.description)))
		# XXX What about the IN/OUT/INOUT state of procedure parameters?
		doc.addContent(makeTag('dl', {}, ''.join([
			''.join([
				makeTag('dt', {}, escape(param.name)),
				makeTag('dd', {}, self.formatDescription(param.description)),
			])
			for param in procedure.paramList
		])))
		doc.addSection(id='attributes', title='Attributes')
		doc.addPara("""The following table notes the various attributes and
			properties of the procedure.""")
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
					procedure.created,
					popupLink("funcorigin.html", "Origin"),
					procedure.origin,
				),
				(
					popupLink("createdby.html", "Created By"),
					escape(procedure.definer),
					popupLink("funclanguage.html", "Language"),
					procedure.language,
				),
				(
					popupLink("sqlaccess.html", "SQL Access"),
					procedure.sqlAccess,
					popupLink("nullcall.html", "Call on NULL"),
					procedure.nullCall,
				),
				(
					popupLink("externalaction.html", "External Action"),
					procedure.externalAction,
					popupLink("deterministic.html", "Deterministic"),
					procedure.deterministic,
				),
				(
					popupLink("fenced.html", "Fenced"),
					procedure.fenced,
					popupLink("threadsafe.html", "Thread Safe"),
					procedure.threadSafe,
				),
				(
					popupLink("specificname.html", "Specific Name"),
					{'colspan': 3, '': procedure.specificName},
				),
			]))
		if len(procedures) > 1:
			doc.addSection('overloads', 'Overloaded Versions')
			doc.addPara("""Listed below are the prototypes of overloaded
				versions of this procedure (i.e. procedures with the same
				qualified name, but different parameter lists). Click on a
				specific name to view the entry for the overloaded
				procedure.""")
			doc.addContent(makeTable(
				head=[(
					'Prototype',
					'Specific Name',
				)],
				data=[(
					makeTag('code', {'class': 'sql'}, self.formatPrototype(overload.prototype)),
					makeTag('a', {'href': filename(overload)}, escape(overload.specificName)),
				) for overload in procedures if overload != procedure]
			))
		if procedure.language == 'SQL':
			doc.addSection('sql', 'SQL Definition')
			doc.addPara("""The SQL which can be used to create the procedure is
				given below. Note that, in the process of storing the
				definition of a procedure, DB2 removes much of the formatting,
				hence the formatting in the statement below (which this system
				attempts to reconstruct) is not necessarily the formatting of
				the original statement. The statement terminator used in the
				SQL below is bang (!)""")
			doc.addContent(makeTag('pre', {'class': 'sql'}, self.formatSql(procedure.createSql, terminator="!")))
		doc.write(os.path.join(self._path, filename(procedure)))

