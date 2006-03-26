#!/bin/env python
# $Header$
# vim: set noet sw=4 ts=4:

import datetime
from string import Template
from xml.sax.saxutils import quoteattr, escape
from w3.htmlutils import *

class Document(object):
	def __init__(self):
		"""HTML document class"""
		super(Document, self).__init__()
		# XXX Figure out how to better search for the template
		self._template = Template(open("w3/template.html").read())
		self._sections = []
		# Attribute                            Format
		self.updated = datetime.date.today() # datetime object
		self.author = ''                     # simple text
		self.authoremail = ''                # e-mail address
		self.sitetitle = ''                  # HTML
		self.title = ''                      # HTML
		self.description = ''                # HTML
		self.keywords = []                   # List of keywords
		self.breadcrumbs = []                # List of (href, title) tuples
		self.menu = []                       # List of (href, title, [children]) tuples

	def addSection(self, id, title):
		"""Starts a new section in the current document with the specified id and title"""
		self._sections.append({
			'id': id,
			'title': title,
			'content': []
		})

	def addContent(self, content):
		"""Adds HTML content to the end of the current section"""
		self._sections[-1]['content'].append(content)

	def addPara(self, para):
		"""Adds a paragraph of text to the end of the current section"""
		self.addContent(makeTag('p', {}, escape(para)))
	
	def write(self, filename):
		"""Writes the document to the specified file"""
		# Construct an index to place before the sections content
		index = makeUnorderedList([
			makeTag('a', {'href': '#' + section['id'], 'title': 'Jump to section'}, escape(section['title']))
			for section in self._sections
		])
		# Concatenate all document sections together with headers before each
		content = ''.join([
			''.join([
				makeTag('div', {'class': 'hrule-dots'}, '&nbsp;'),
				makeTag('h2', {'id': section['id']}, escape(section['title'])),
				''.join(section['content']),
				makeTag('p', {}, makeTag('a', {'href': '#masthead', 'title': 'Jump to top'}, 'Back to top'))
			])
			for section in self._sections
		])
		# Construct the body from a header, the index and the content from above
		body = ''.join([
			makeTag('h1', {}, self.title),
			makeTag('p', {}, self.description),
			index,
			content
		])
		# Construct the breadcrumb links
		crumbs = ' &raquo; '.join([
			makeTag('a', {'href': crumbhref}, escape(crumbtitle))
			for (crumbhref, crumbtitle) in self.breadcrumbs
		])
		# Mutually recursive functions for making the menu divs and links
		def makeMenuLink(level, index, href, title, children):
			linkattr = {'href': href}
			if (index == 0) and (level == 0): linkattr['id'] = 'site-home'
			return ''.join([
				makeTag('a', linkattr, title),
				makeMenuDiv(level + 1, children)
			])

		def makeMenuDiv(level, data):
			if len(data) > 0:
				divclass = ['top-level', 'second-level', 'third-level'][level]
				return makeTag('div', {'class': divclass}, ''.join([
					makeMenuLink(level, index, href, title, children)
					for (index, (href, title, children)) in enumerate(data)
				]))
			else:
				return ''
		# Put the body and a number of other substitution values (mostly for
		# the metadata in the document HEAD) into a dictionary
		values = {
			# Fields formatted as attributes for use in <HEAD>
			'headupdated':     quoteattr(str(self.updated)),
			'headauthor':      quoteattr(self.author),
			'headauthoremail': quoteattr(self.authoremail),
			'headdoctitle':    quoteattr(stripTags(self.title)),
			'headsitetitle':   quoteattr(stripTags(self.sitetitle)),
			'headdescription': quoteattr(stripTags(self.description)),
			'headkeywords':    quoteattr(', '.join(self.keywords)),
			# Fields formatted as content for use in <BODY>
			'bodyauthor':      makeTag('a', {'href': self.authoremail}, escape(self.author)),
			'bodydoctitle':    self.title,
			'bodysitetitle':   self.sitetitle,
			'bodyupdated':     escape(self.updated.strftime('%a, %d %b %Y')),
			'breadcrumbs':     crumbs,
			'menu':            makeMenuDiv(0, self.menu),
			'body':            body,
		}
		# Substitute all the values into the main template and write it to a file
		open(filename, "w").write(self._template.substitute(values))
