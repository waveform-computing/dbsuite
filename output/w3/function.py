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

def write(self, functions):
	"""Outputs the documentation for a function.

	Note that this function becomes the writeFunction method of the
	Output class in the output.w3 module.
	"""
	# Note that this method (unlike other methods) is passed a *list* of
	# functions (because functions can be overloaded)
	for function in functions:
		logging.debug("Writing documentation for function %s to %s" % (function.name, filename(function)))
		doc = self.newDocument(function)
		doc.addSection(id='description', title='Description')
		doc.addContent(makeTag('p', {}, makeTag('code', {'class': 'sql'}, self.formatPrototype(function.prototype))))
		doc.addContent(makeTag('p', {}, self.formatDescription(function.description)))
		params = list(function.paramList) # Take a copy of the parameter list
		if function.type in ['Row', 'Table']:
			# Extend the list with return parameters if the function is a
			# ROW or TABLE function (and hence, returns multiple named parms)
			params.extend(function.returnList)
		doc.addContent(makeTag('dl', {}, ''.join([
			''.join([
				makeTag('dt', {}, escape(param.name)),
				makeTag('dd', {}, self.formatDescription(param.description)),
			])
			for param in params
		])))
		doc.addSection(id='attributes', title='Attributes')
		doc.addPara("""The following table notes the various attributes and
			properties of the function.""")
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
					function.created,
					popupLink("funcorigin.html", "Origin"),
					function.origin,
				),
				(
					popupLink("createdby.html", "Created By"),
					escape(function.definer),
					popupLink("funclanguage.html", "Language"),
					function.language,
				),
				(
					popupLink("functype.html", "Type"),
					function.type,
					popupLink("sqlaccess.html", "SQL Access"),
					function.sqlAccess,
				),
				(
					popupLink("castfunc.html", "Cast Function"),
					function.castFunction,
					popupLink("assignfunc.html", "Assign Function"),
					function.assignFunction,
				),
				(
					popupLink("externalaction.html", "External Action"),
					function.externalAction,
					popupLink("deterministic.html", "Deterministic"),
					function.deterministic,
				),
				(
					popupLink("nullcall.html", "Call on NULL"),
					function.nullCall,
					popupLink("fenced.html", "Fenced"),
					function.fenced,
				),
				(
					popupLink("parallelcall.html", "Parallel"),
					function.parallel,
					popupLink("threadsafe.html", "Thread Safe"),
					function.threadSafe,
				),
				(
					popupLink("specificname.html", "Specific Name"),
					{'colspan': 3, '': function.specificName},
				),
			]))
		if len(functions) > 1:
			doc.addSection('overloads', 'Overloaded Versions')
			doc.addPara("""Listed below are the prototypes of overloaded
				versions of this function (i.e. functions with the same
				qualified name, but different parameter lists). Click on a
				specific name to view the entry for the overloaded
				function.""")
			doc.addContent(makeTable(
				head=[(
					'Prototype',
					'Specific Name',
				)],
				data=[(
					makeTag('code', {'class': 'sql'}, self.formatPrototype(overload.prototype)),
					makeTag('a', {'href': filename(overload)}, escape(overload.specificName)),
				) for overload in functions if overload != function]
			))
		if function.language == 'SQL':
			doc.addSection('sql', 'SQL Definition')
			doc.addPara("""The SQL which can be used to create the function is
				given below. Note that, in the process of storing the
				definition of a function, DB2 removes much of the formatting,
				hence the formatting in the statement below (which this system
				attempts to reconstruct) is not necessarily the formatting of
				the original statement. The statement terminator used in the
				SQL below is bang (!)""")
			doc.addContent(makeTag('pre', {'class': 'sql'}, self.formatSql(function.createSql, terminator="!")))
		doc.write(os.path.join(self._path, filename(function)))

