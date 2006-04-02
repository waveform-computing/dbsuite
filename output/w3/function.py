#!/bin/env python
# $Header$
# vim: set noet sw=4 ts=4:

import sys
import os.path
import logging
from output.w3.htmlutils import *

def formatParam(param):
	return "%s %s" % (makeTag('em', {}, escape(param.name)), escape(param.datatypeStr))

def formatParams(params):
	# XXX Handle anonymous parmeters here
	return ', '.join([formatParam(param) for param in params])

def formatReturns(function):
	if len(function.returnList) == 0:
		return ''
	elif function.type == 'Row':
		return ' RETURNS ROW(%s)' % (formatParams(function.returnList))
	elif function.type == 'Table':
		return ' RETURNS TABLE(%s)' % (formatParams(function.returnList))
	else:
		return ' RETURNS %s' % (escape(function.returnList[0].datatypeStr))

def prototype(function, link=True):
	return makeTag('code', {}, "%s(%s)%s" % (
		escape(function.qualifiedName),
		formatParams(function.paramList),
		formatReturns(function))
	)

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
		doc.addContent(prototype(function))
		doc.addContent('<p>%s</p>' % (self.formatDescription(function.description)))
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
		##doc.addSection('sql', 'SQL Definition')
		##doc.addPara("""The SQL which can be used to create the function is given
		##	below. Note that this is not necessarily the same as the actual
		##	statement used to create the function (it has been reconstructed from
		##	the content of the system catalog tables and may differ in a number
		##	of areas).""")
		##doc.addContent(makeTag('pre', {'class': 'sql'}, self.formatSql(function.createSql)))
		doc.write(os.path.join(self._path, filename(function)))

