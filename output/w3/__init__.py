#!/usr/bin/env python
# $Header$
# vim: set noet sw=4 ts=4:

import sys
import os
import os.path
import datetime
import logging
import re
import shutil
from decimal import Decimal
from htmlutils import *
from xml.sax.saxutils import quoteattr, escape
from document import Document
from db.database import Database
from db.table import Table
from db.view import View
from db.check import Check
from db.uniquekey import UniqueKey, PrimaryKey
from db.foreignkey import ForeignKey
from db.function import Function
from output.w3 import database
from output.w3 import schema
from output.w3 import tablespace
from output.w3 import table
from output.w3 import view
from output.w3 import index
from output.w3 import uniquekey
from output.w3 import foreignkey
from output.w3 import check
from output.w3 import function
from sql.tokenizer import DB2UDBSQLTokenizer
from sql.formatter import SQLFormatter
from sql.htmlhighlighter import SQLHTMLHighlighter

def _copytree(src, dst):
	"""Utility function based on copytree in shutil"""
	names = os.listdir(src)
	errors = []
	if not os.path.isdir(dst):
		try:
			os.unlink(dst)
		except OSError:
			os.mkdir(dst)
	for name in names:
		srcname = os.path.join(src, name)
		dstname = os.path.join(dst, name)
		try:
			if os.path.isdir(srcname):
				_copytree(srcname, dstname)
			else:
				shutil.copy(srcname, dstname)
		except (IOError, os.error), why:
			errors.append((srcname, dstname, why))
		except Error, err:
			errors.extend(err.args[0])
	if errors:
		raise Error, errors

class DocOutput(object):
	"""HTML documentation writer class -- IBM w3 v8 Intranet standard"""

	def __init__(self, database, path="."):
		"""Initializes an instance of the class.

		DocOutput is a "one-shot" class in that initializing and instance also
		causes the documentation to be written by the instance (which is then
		usually discarded).
		"""
		super(DocOutput, self).__init__()
		self._updated = datetime.date.today()
		self._database = database
		self._path = path
		self._tokenizer = DB2UDBSQLTokenizer()
		self._formatter = SQLFormatter()
		self._highlighter = SQLHTMLHighlighter()
		# Copy the contents of the htdocs subdirectory to the target
		_copytree('output/w3/htdocs/', self._path)
		# Write the documentation files for each object
		self.writeDatabase(database)
		for schema in database.schemas.itervalues():
			self.writeSchema(schema)
			for relation in schema.relations.itervalues():
				self.writeRelation(relation)
				if isinstance(relation, Table):
					for constraint in relation.constraints.itervalues():
						self.writeConstraint(constraint)
			for index in schema.indexes.itervalues():
				self.writeIndex(index)
			for function in schema.functions.itervalues():
				self.writeFunction(function)
		for tablespace in database.tablespaces.itervalues():
			self.writeTablespace(tablespace)
	
	def formatSql(self, sql, terminator=";"):
		"""Converts an SQL statement into highlighted HTML.

		Using the tokenizer, reformatter and HTML highlighter units in the
		sql sub-package, this routine takes raw (typically white-space
		mangled) SQL code and returns pretty-printed, syntax highlighted
		SQL in HTML format.

		This routine handles highlighting any arbitrary SQL script.
		"""
		# Tokenize, reformat, and then syntax highlight the provided code
		tokens = self._tokenizer.parse(sql, terminator)
		tokens = self._formatter.parse(tokens)
		return self._highlighter.parse(tokens)

	def formatPrototype(self, sql):
		"""Converts an SQL function prototype into highlighted HTML.

		This method is similar to the formatSql() method, but operates on
		standalone function prototypes which aren't otherwise valid standalone
		SQL scripts.
		"""
		# Tokenize, reformat, and then syntax highlight the provided code
		tokens = self._tokenizer.parse(sql)
		tokens = self._formatter.parseRoutinePrototype(tokens)
		return self._highlighter.parse(tokens)
	
	findref = re.compile(r"@([A-Za-z_$#@][A-Za-z0-9_$#@]*(\.[A-Za-z_$#@][A-Za-z0-9_$#@]*){0,2})\b")
	findfmt = re.compile(r"\B([/_*])(\w+)\1\B")
	def formatDescription(self, text):
		"""Converts simple prefix-based markup in text into HTML.
		
		References in the provided text (specified as @-prefix qualified names)
		are returned as links to the targetted objects (the objects are located
		with the find() method of the Database object at the root of the
		object hierarchy).
		
		Highlights in the text are also converted. Currently *bold* text is
		converted to <strong> tags, /italic/ text is converted to <em> tags,
		and _underlined_ text is convert to <u> tags.
		
		The resulting string is valid HTML; that is, all characters which
		require converting to character entities are converted using the
		escape() function of the xml.sax.saxutils unit.
		"""
		# Replace refs and fmt modifiers with HTML
		start = 0
		result = ''
		while True:
			matchref = self.findref.search(text, start)
			matchfmt = self.findfmt.search(text, start)
			if matchref is not None and (matchfmt is None or matchfmt.start(0) > matchref.start(0)):
				result += escape(text[start:matchref.start(0)])
				start = matchref.end(0)
				target = self._database.find(matchref.group(1))
				if target is None:
					result += escape(matchref.group(1))
				else:
					result += linkTo(target, qualifiedName=True)
			elif matchfmt is not None and (matchref is None or matchfmt.start(0) < matchref.start(0)):
				result += escape(text[start:matchfmt.start(0)])
				start = matchfmt.end(0)
				if matchfmt.group(1) == '*':
					result += makeTag('strong', {}, matchfmt.group(2))
				elif matchfmt.group(1) == '/':
					result += makeTag('em', {}, matchfmt.group(2))
				elif matchfmt.group(1) == '_':
					result += makeTag('u', {}, matchfmt.group(2))
			else:
				result += text[start:]
				break
		# Replace line breaks with line break tags
		return result.replace('\n', '<br />')

	def createMenu(self, item, active=True):
		result = []
		while True:
			result = self.createMenuLevel(item, active, result)
			active = False
			item = item.parent
			if item is None:
				break
		result.insert(0, ('index.html', 'Home', 'Home', [], False))
		return result

	def createMenuLevel(self, selitem, active, subitems):
		moretop = False
		morebot = False
		if selitem.parentList is None:
			slice = [selitem]
		else:
			index = selitem.parentIndex
			if len(selitem.parentList) <= 10:
				slice = selitem.parentList
			elif index <= 3:
				slice = selitem.parentList[:7]
				morebot = True
			elif index >= len(selitem.parentList) - 3:
				slice = selitem.parentList[-7:]
				moretop = True
			else:
				slice = selitem.parentList[index - 3:index + 4]
				moretop = True
				morebot = True
		items = []
		for item in slice:
			label = item.name
			if len(label) > 10:
				label = '%s...' % (label[:10])
			title = '%s %s' % (item.typeName, item.qualifiedName)
			if item == selitem:
				items.append((filename(item), title, escape(label), subitems, active))
			else:
				items.append((filename(item), title, escape(label), [], False))
		if moretop:
			items.insert(0, ('#', 'More items', '&uarr; More items...', [], False))
		if morebot:
			items.append(('#', 'More items', '&darr; More items...', [], False))
		return items

	def newDocument(self, object):
		"""Creates a new Document object for the specified object.
		
		This method returns a new Document object with most of the attributes
		(like doctitle, sitetitle, etc.) filled in from the specified object.
		"""
		doc = Document()
		# Use a single value for the update date of all documents produced by
		# the class
		doc.updated = self._updated
		doc.author = ''
		doc.authoremail = ''
		doc.title = "%s %s" % (object.typeName, object.qualifiedName)
		doc.sitetitle = "%s Documentation" % (self._database.name)
		doc.keywords = [self._database.name, object.typeName, object.name, object.qualifiedName]
		o = object
		while not o is None:
			doc.breadcrumbs.insert(0, (filename(o), '%s %s' % (o.typeName, o.name)))
			o = o.parent
		doc.breadcrumbs.insert(0, ('index.html', 'Home'))
		doc.menu = self.createMenu(object)
		return doc

	# Each of the methods for producing the actual documentation are split off
	# into separate units for readability (honest!)
	writeDatabase = database.write
	writeSchema = schema.write
	writeTablespace = tablespace.write
	writeTable = table.write
	writeView = view.write
	writeIndex = index.write
	writeUniqueKey = uniquekey.write
	writeForeignKey = foreignkey.write
	writeCheck = check.write
	writeFunction = function.write

	def writeRelation(self, relation):
		if isinstance(relation, Table):
			self.writeTable(relation)
		elif isinstance(relation, View):
			self.writeView(relation)

	def writeConstraint(self, constraint):
		if isinstance(constraint, UniqueKey):
			self.writeUniqueKey(constraint)
		elif isinstance(constraint, ForeignKey):
			self.writeForeignKey(constraint)
		elif isinstance(constraint, Check):
			self.writeCheck(constraint)
	
def main():
	pass

if __name__ == "__main__":
	main()
