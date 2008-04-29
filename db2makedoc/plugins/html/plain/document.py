# vim: set noet sw=4 ts=4:

"""Plain site and document classes.

This module defines subclasses of the classes in the html module which override
certain methods to provide formatting specific to the plain style.
"""

import os
import codecs
import logging
from PIL import Image
from db2makedoc.graph import Graph, Node, Edge, Cluster
from db2makedoc.etree import fromstring
from db2makedoc.db import (
	DatabaseObject, Database, Schema, Relation,
	Table, View, Alias, Trigger
)
from db2makedoc.plugins.html.document import (
	AttrDict, WebSite, HTMLDocument, CSSDocument,
	GraphDocument
)


class PlainSite(WebSite):
	"""Site class representing a collection of PlainDocument instances."""

	def __init__(self, database):
		"""Initializes an instance of the class."""
		super(PlainSite, self).__init__(database)
		self.last_updated = True
		self.max_graph_size = (600, 800)
		self.stylesheets = []
		self._document_map = {}
		self._graph_map = {}

	def add_document(self, document):
		"""Adds a document to the website.

		This method overrides the base implementation to map database objects
		to documents and graphs according to the site structure.
		"""
		super(PlainSite, self).add_document(document)
		if isinstance(document, PlainMainDocument):
			self._document_map[document.dbobject] = document
		elif isinstance(document, PlainGraphDocument):
			self._graph_map[document.dbobject] = document
	
	def object_document(self, dbobject):
		"""Returns the HTMLDocument associated with a database object."""
		return self._document_map.get(dbobject)

	def object_graph(self, dbobject):
		"""Returns the GraphDocument associated with a database object."""
		return self._graph_map.get(dbobject)

	def write(self):
		"""Writes all documents in the site to disk."""
		# Overridden to split writing graph documents before other documents
		# when using multi-threaded writing. This avoids a race condition
		# due to the fact that writing a table document (for example) may cause
		# the associated table graph to be written if it hasn't already. If
		# another thread starts writing the graph at the same time, we can
		# wind up with two threads trying to write the graph simultaneously.
		if self.threads > 1:
			# Write graphs first
			self.write_multi(
				doc for doc in self._documents.itervalues()
				if isinstance(doc, GraphDocument)
			)
			# Then write everything else
			self.write_multi(
				doc for doc in self._documents.itervalues()
				if not isinstance(doc, GraphDocument)
			)
		else:
			super(PlainSite, self).write()


class PlainDocument(HTMLDocument):
	"""Document class for use with the plain style."""

	# HTML CONSTRUCTION METHODS
	# Overridden versions specific to plain formatting
	
	def _table(self, data, head=[], foot=[], caption='', attrs={}):
		# Overridden to color alternate rows white & gray
		tablenode = super(PlainDocument, self)._table(data, head, foot, caption, attrs)
		colors = ['even', 'odd']
		tbodynode = tablenode.find('tbody')
		for (index, rownode) in enumerate(tbodynode.findall('tr')):
			classes = rownode.attrib.get('class', '').split()
			classes.append(colors[(index + 1) % 2])
			rownode.attrib['class'] = ' '.join(classes)
		return tablenode


class PlainMainDocument(PlainDocument):
	"""Document class representing a database object (table, view, index, etc.)"""

	def __init__(self, site, dbobject):
		"""Initializes an instance of the class."""
		self.dbobject = dbobject # must be set before calling the inherited method
		super(PlainMainDocument, self).__init__(site, '%s.html' % dbobject.identifier)
		self.title = '%s - %s %s' % (self.site.title, self.dbobject.type_name, self.dbobject.qualified_name)
		self.description = '%s %s' % (self.dbobject.type_name, self.dbobject.qualified_name)
		self.keywords = [self.site.database.name, self.dbobject.type_name, self.dbobject.name, self.dbobject.qualified_name]
		# Add the extra inheritable properties to the site attributes list
		self.last_updated = None
		self._site_attributes.append('last_updated')
	
	def _create_content(self):
		# Overridden to automatically set the link objects and generate the
		# content from the sections filled in by descendent classes in
		# _create_sections()
		if not self.link_first and self.dbobject.first:
			self.link_first = self.site.object_document(self.dbobject.first)
		if not self.link_prior and self.dbobject.prior:
			self.link_prior = self.site.object_document(self.dbobject.prior)
		if not self.link_next and self.dbobject.next:
			self.link_next = self.site.object_document(self.dbobject.next)
		if not self.link_last and self.dbobject.last:
			self.link_last = self.site.object_document(self.dbobject.last)
		if not self.link_up and self.dbobject.parent:
			self.link_up = self.site.object_document(self.dbobject.parent)
		# Call the inherited method to create the skeleton document
		super(PlainMainDocument, self)._create_content()
		# Add styles
		headnode = self.doc.find('head')
		headnode.append(self._style(src=PlainCSSDocument._url, media='all'))
		if self.site.stylesheets:
			for url in self.site.stylesheets:
				headnode.append(self._style(src=url, media='all'))
		# Add body content
		bodynode = self.doc.find('body')
		bodynode.append(self._h(self.site.title, level=1, attrs={'id': 'top'}))
		self._create_crumbs(bodynode)
		bodynode.append(self._h('%s %s' % (self.dbobject.type_name, self.dbobject.qualified_name), level=2))
		self.sections = []
		self._create_sections()
		bodynode.append(self._ul([
			self._a('#%s' % section['id'], section['title'], 'Jump to section')
			for section in self.sections
		], attrs={'id': 'toc'}))
		for section in self.sections:
			bodynode.append(self._h(section['title'], level=3, attrs={'id': section['id']}))
			self._append_content(bodynode, section['content'])
			bodynode.append(self._p(self._a('#top', 'Back to top', 'Jump to top')))
		if self.site.copyright:
			bodynode.append(self._p(self.site.copyright, attrs={'id': 'footer'}))
		if self.last_updated:
			bodynode.append(self._p('Updated on %s' % self.date.strftime('%a, %d %b %Y'), attrs={'id': 'timestamp'}))

	def _create_crumbs(self, node):
		"""Creates the breadcrumb links at the top of the page."""
		crumbs = []
		item = self.dbobject
		while item is not None:
			crumbs.insert(0, self._a_to(item, typename=True, qualifiedname=False))
			crumbs.insert(0, ' > ')
			item = item.parent
		crumbs.insert(0, self._a(self.site.home_url, self.site.home_title))
		self._append_content(node, self._p(crumbs, attrs={'id': 'breadcrumbs'}))
	
	# CONTENT METHODS
	# The following methods are for use in descendent classes to fill the
	# sections list with content. Basically, all descendent classes need to do
	# is override the _create_sections() method, calling section() and add() in
	# their implementation

	def _create_sections(self):
		# Override in descendent classes
		pass

	def _section(self, id, title):
		"""Starts a new section in the body of the current document.

		Parameters:
		id -- The id of the anchor at the start of the section
		title -- The title text of the section
		"""
		self.sections.append({'id': id, 'title': title, 'content': []})
	
	def _add(self, content):
		"""Add HTML content or elements to the end of the current section.

		Parameters:
		content -- A string, Node, NodeList, or tuple/list of Nodes
		"""
		self.sections[-1]['content'].append(content)


class PlainCSSDocument(CSSDocument):
	"""Stylesheet class to define the base site style."""

	_url = 'styles.css'

	def __init__(self, site):
		super(PlainCSSDocument, self).__init__(site, self._url)

	def _create_content(self):
		self.doc = u"""\
/* General styles */

body {
	font-family: "BitStream Vera Sans", "Verdana", "Arial", "Helvetica", sans-serif;
	font-size: 10pt;
	margin: 0.5em;
	padding: 0;
}

table {
    border: 1px solid black;
    border-collapse: collapse;
}

table tr.odd { background: white; }
table tr.even { background: #ddd; }

table td,
table th { border-left: 1px solid black; padding: 0.2em 0.5em; }
table th { background: #47b; color: white; text-align: left; }
table td { vertical-align: top; }

h1 {
    background: #259;
    color: white;
    text-align: center;
    padding: 0.3em;
    margin-top: 0;
}

h3 {
    background: #47b;
    color: white;
    padding: 0.5em;
}

ul#toc {
    position: fixed;
    top: 0.5em;
    right: 0.5em;
    background: #ddf;
    padding: 1.5em 2em;
    margin: 0;
    list-style: none;
}

p#footer,
p#timestamp {
    color: #777;
    text-align: center;
    margin: 0;
}

/* SQL syntax highlighting */
.sql {
	font-size: 9pt;
	font-family: "Courier New", monospace;
}

pre.sql {
	background-color: #ddf;
	padding: 1em;
	/* Ensure <pre> stuff wraps if it's too long */
	white-space: -moz-pre-wrap; /* Mozilla */
	white-space: -o-pre-wrap;   /* Opera 7 */
	white-space: -pre-wrap;     /* Opera 4-6 */
	white-space: pre-wrap;      /* CSS 2.1 (Opera8+) */
	/* No way to do this in IE... */
}

.sql span.sql_error      { background-color: red; }
.sql span.sql_comment    { color: green; }
.sql span.sql_keyword    { font-weight: bold; color: blue; }
.sql span.sql_datatype   { font-weight: bold; color: green; }
.sql span.sql_register   { font-weight: bold; color: purple; }
.sql span.sql_identifier { }
.sql span.sql_number     { color: maroon; }
.sql span.sql_string     { color: maroon; }
.sql span.sql_operator   { }
.sql span.sql_parameter  { font-style: italic; }
.sql span.sql_terminator { }

/* Cell formats for line-numbered SQL */
td.num_cell { background-color: silver; }
td.sql_cell { background-color: gray; }

/* Fix display of border around diagrams in Firefox */
img { border: 0 none; }
"""


class PlainGraphDocument(GraphDocument):
	"""Graph class representing a database object or collection of objects."""

	def __init__(self, site, dbobject):
		"""Initializes an instance of the class."""
		self.dbobject = dbobject # must be set before calling the inherited method
		super(PlainGraphDocument, self).__init__(site, '%s.png' % dbobject.identifier)
		self._dbobject_map = {}
		self._written = False
		self._scale = None
	
	def write(self):
		# Overridden to set the introduced "_written" flag (to ensure we don't
		# attempt to write the graph more than once due to the induced write()
		# call in the overridden _link() method), and to handle resizing the
		# image if it's larger than the maximum size specified in the config
		if not self._written:
			super(PlainGraphDocument, self).write()
			self._written = True
			if self._usemap:
				im = Image.open(self.filename)
				(maxw, maxh) = self.site.max_graph_size
				(w, h) = im.size
				if w > maxw or h > maxh:
					# If the graph is larger than the maximum specified size,
					# move the original to name.full.ext and create a smaller
					# version using PIL. The scaling factor is stored so that
					# the overridden _map() method can use it to adjust the
					# client side image map
					self._scale = min(float(maxw) / w, float(maxh) / h)
					neww = int(round(w * self._scale))
					newh = int(round(h * self._scale))
					if w * h * 3 / 1024**2 < 500:
						# Use a high-quality anti-aliased resize if to do so
						# would use <500Mb of RAM (which seems a reasonable
						# cut-off point on modern machines) - the conversion
						# to RGB is the really memory-heavy bit
						im = im.convert('RGB').resize((neww, newh), Image.ANTIALIAS)
					else:
						im = im.resize((neww, newh), Image.NEAREST)
					im.save(self.filename)
	
	def _map(self):
		# Overridden to allow generating the client-side map for the "full
		# size" graph, or the smaller version potentially produced by the
		# write() method
		if not self._written:
			self.write()
		result = super(PlainGraphDocument, self)._map()
		if self._scale is not None:
			for area in result:
				# Convert coords string into a list of integer tuples
				coords = [
					tuple(int(i) for i in coord.split(','))
					for coord in area.attrib['coords'].split(' ')
				]
				# Resize all the coordinates by the scale
				coords = [
					tuple(int(round(i * self._scale)) for i in coord)
					for coord in coords
				]
				# Convert the scaled results back into a string
				area.attrib['coords'] = ' '.join(
					','.join(str(i) for i in coord)
					for coord in coords
				)
		return result
	
	def _create_content(self):
		# Call the inherited method in case it does anything
		super(PlainGraphDocument, self)._create_content()
		# Call _create_graph to create the content of the graph
		self._create_graph()
		# Transform dbobject attributes on Node, Edge and Cluster objects into
		# URL attributes 

		def rewrite_url(node):
			if isinstance(node, (Node, Edge, Cluster)) and hasattr(node, 'dbobject'):
				doc = self.site.object_document(node.dbobject)
				if doc:
					node.URL = doc.url

		def rewrite_font(node):
			if isinstance(node, (Node, Edge)):
				node.fontname = 'Verdana'
				node.fontsize = 8.0
			elif isinstance(node, Cluster):
				node.fontname = 'Verdana'
				node.fontsize = 10.0

		self.graph.touch(rewrite_url)
		self.graph.touch(rewrite_font)
		# Tweak some of the graph attributes to make it scale a bit more nicely
		self.graph.rankdir = 'LR'
		#self.graph.size = '10,20'
		self.graph.dpi = '96'
		(maxw, maxh) = self.site.max_graph_size
		self.graph.ratio = str(float(maxh) / float(maxw))

	def _create_graph(self):
		# Override in descendent classes to generate nodes, edges, etc. in the
		# graph
		pass

	def _add_dbobject(self, dbobject, selected=False):
		"""Utility method to add a database object to the graph.

		This utility method adds the specified database object along with
		standardized formatting depending on the type of the object.
		"""
		assert isinstance(dbobject, DatabaseObject)
		assert not self._written
		o = self._dbobject_map.get(dbobject, None)
		if o is None:
			if isinstance(dbobject, Schema):
				o = Cluster(self.graph, dbobject.qualified_name)
				o.label = dbobject.name
				o.style = 'filled'
				o.fillcolor = '#ece6d7'
				o.color = '#ece6d7'
			elif isinstance(dbobject, Relation):
				cluster = self._add_dbobject(dbobject.schema)
				o = Node(cluster, dbobject.qualified_name)
				o.shape = 'rectangle'
				o.style = 'filled'
				o.label = dbobject.name
				if isinstance(dbobject, Table):
					o.fillcolor = '#bbbbff'
				elif isinstance(dbobject, View):
					o.style = 'filled,rounded'
					o.fillcolor = '#bbffbb'
				elif isinstance(dbobject, Alias):
					if isinstance(dbobject.final_relation, View):
						o.style = 'filled,rounded'
					o.fillcolor = '#ffffbb'
				o.color = '#000000'
			elif isinstance(dbobject, Trigger):
				cluster = self._add_dbobject(dbobject.schema)
				o = Node(cluster, dbobject.qualified_name)
				o.shape = 'hexagon'
				o.style = 'filled'
				o.fillcolor = '#ffbbbb'
				o.label = dbobject.name
			if selected:
				o.style += ',setlinewidth(3)'
			o.dbobject = dbobject
			self._dbobject_map[dbobject] = o
		return o
