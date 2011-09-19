# vim: set noet sw=4 ts=4:

"""Plain site and document classes.

This module defines subclasses of the classes in the html module which override
certain methods to provide formatting specific to the plain style.
"""

import os
import logging
from pkg_resources import resource_string, resource_stream
from dbsuite.graph import Graph, Node, Edge, Cluster
from dbsuite.etree import ProcessingInstruction, iselement
from dbsuite.db import (
	Database, Schema, Relation, Table, View, Alias, UniqueKey,
	ForeignKey, Check, Index, Trigger, Function, Procedure, Tablespace
)
from dbsuite.plugins.html.document import (
	HTMLElementFactory, ObjectGraph, WebSite, HTMLDocument, HTMLPopupDocument,
	HTMLObjectDocument, HTMLSiteIndexDocument, HTMLExternalDocument,
	StyleDocument, ScriptDocument, ImageDocument, GraphDocument,
	GraphObjectDocument
)
from dbsuite.plugins.html.database import DatabaseDocument
from dbsuite.plugins.html.schema import SchemaDocument, SchemaGraph
from dbsuite.plugins.html.table import TableDocument, TableGraph
from dbsuite.plugins.html.view import ViewDocument, ViewGraph
from dbsuite.plugins.html.alias import AliasDocument, AliasGraph
from dbsuite.plugins.html.uniquekey import UniqueKeyDocument
from dbsuite.plugins.html.foreignkey import ForeignKeyDocument
from dbsuite.plugins.html.check import CheckDocument
from dbsuite.plugins.html.index import IndexDocument
from dbsuite.plugins.html.trigger import TriggerDocument
from dbsuite.plugins.html.function import FunctionDocument
from dbsuite.plugins.html.procedure import ProcedureDocument
from dbsuite.plugins.html.tablespace import TablespaceDocument

# Import the imaging library
try:
	from PIL import Image
except ImportError:
	# Ignore any import errors - the main plugin takes care of warning the
	# user if PIL is required but not present
	pass


class PlainElementFactory(HTMLElementFactory):
	def _add_class(self, node, cls):
		classes = set(node.attrib.get('class', '').split(' '))
		classes.add(cls)
		node.attrib['class'] = ' '.join(classes)

	def table(self, *content, **attrs):
		attrs.setdefault('cellspacing', '1')
		table = self._element('table', *content, **attrs)
		sorters = {}
		try:
			thead = self._find(table, 'thead')
		except:
			pass
		else:
			for tr in thead.findall('tr'):
				if 'id' in table.attrib:
					for index, th in enumerate(tr.findall('th')):
						classes = th.attrib.get('class', '').split()
						if 'nosort' in classes:
							sorters[index] = 'false'
						if 'commas' in classes:
							sorters[index] = '"digitComma"'
		# Apply extra styles to tables with a tbody element (other tables are
		# likely to be pure layout tables)
		try:
			tbody = self._find(table, 'tbody')
		except:
			pass
		else:
			# Apply even and odd classes to rows
			for index, tr in enumerate(tbody.findall('tr')):
				self._add_class(tr, ['odd', 'even'][index % 2])
			# If there's an id on the main table element, add a script element
			# within the table definition to activate the jQuery tablesorter
			# plugin for this table
			if 'id' in table.attrib and len(tbody.findall('tr')) > 1:
				script = self.script("""
					$(document).ready(function() {
						$('table#%s').tablesorter({
							cssAsc:       'sort-asc',
							cssDesc:      'sort-desc',
							cssHeader:    'sortable',
							widgets:      ['zebra'],
							widgetZebra:  {css: ['odd', 'even']},
							headers:      {%s}
						});
					});
				""" % (
					table.attrib['id'],
					', '.join(
						'%d: {sorter: %s}' % (index, sorter)
						for (index, sorter) in sorters.iteritems()
					)
				))
				return (table, script)
		return table


class PlainGraph(ObjectGraph):
	def style(self, item):
		super(PlainGraph, self).style(item)
		# Set the graph to use the same default font as the stylesheet
		# XXX Any way to set a fallback here like in CSS?
		if isinstance(item, (Node, Edge)):
			item.fontname = 'Trebuchet MS'
			item.fontsize = 8.0
		elif isinstance(item, Cluster):
			item.fontname = 'Trebuchet MS'
			item.fontsize = 10.0
		# Set shapes and color schemes on objects that represent database
		# objects
		if hasattr(item, 'dbobject'):
			item.fontcolor = '#000000'
			if isinstance(item.dbobject, Schema):
				item.style = 'filled'
				item.fillcolor = '#eeeeee'
			elif isinstance(item.dbobject, Relation):
				item.style = 'filled'
				if isinstance(item.dbobject, Table):
					item.shape = 'rectangle'
					item.fillcolor = '#aaaaff'
				elif isinstance(item.dbobject, View):
					item.shape = 'octagon'
					item.fillcolor = '#99ff99'
				elif isinstance(item.dbobject, Alias):
					if isinstance(item.dbobject.final_relation, Table):
						item.shape = 'rectangle'
					else:
						item.shape = 'octagon'
					item.fillcolor = '#ffbb99'
			elif isinstance(item.dbobject, Trigger):
				item.shape = 'hexagon'
				item.style = 'filled'
				item.fillcolor = '#ff9999'
		# Outline the selected object more clearly
		if isinstance(item, (Cluster, Node)) and hasattr(item, 'selected'):
			item.color = [item.fillcolor, '#000000'][item.selected]
		elif isinstance(item, Edge):
			item.color = '#999999'


class PlainSite(WebSite):
	def get_options(self, options):
		super(PlainSite, self).get_options(options)
		self.last_updated = options['last_updated']
		self.max_graph_size = options['max_graph_size']
		self.stylesheets = options['stylesheets']

	def get_factories(self):
		self.tag_class = PlainElementFactory
		self.popup_class = PlainPopup
		self.graph_class = PlainGraph
		self.index_class = PlainSiteIndex
		self.document_classes = {
			Database:   set([PlainDatabaseDocument]),
			Schema:     set([PlainSchemaDocument]),
			Table:      set([PlainTableDocument]),
			View:       set([PlainViewDocument]),
			Alias:      set([PlainAliasDocument]),
			UniqueKey:  set([PlainUniqueKeyDocument]),
			ForeignKey: set([PlainForeignKeyDocument]),
			Check:      set([PlainCheckDocument]),
			Index:      set([PlainIndexDocument]),
			Trigger:    set([PlainTriggerDocument]),
			Function:   set([PlainFunctionDocument]),
			Procedure:  set([PlainProcedureDocument]),
			Tablespace: set([PlainTablespaceDocument]),
		}
		graph_map = {
			Schema:  PlainSchemaGraph,
			Table:   PlainTableGraph,
			View:    PlainViewGraph,
			Alias:   PlainAliasGraph,
		}
		# The plugin's configure method has already check all items in
		# self.diagrams are supported
		for item in self.diagrams:
			self.document_classes[item].add(graph_map[item])

	def create_static_documents(self):
		super(PlainSite, self).create_static_documents()
		# Create static documents. Note that we don't keep a reference to the
		# image documents.  Firstly, the objects will be kept alive by virtue
		# of being added to the urls map in this object (by virtue of the
		# add_document call in their constructors). Secondly, no document ever
		# refers directly to these objects - they're referred to solely in in
		# the plain stylesheet
		self.plain_style = PlainStyle(self)
		self.plain_script = PlainScript(self)
		HeaderImage(self)
		SortableImage(self)
		SortAscImage(self)
		SortDescImage(self)
		ExpandImage(self)
		CollapseImage(self)
		if self.search:
			PlainSearch(self)


class PlainExternal(HTMLExternalDocument):
	pass


class PlainDocument(HTMLDocument):
	def generate(self):
		html = super(PlainDocument, self).generate()
		head = html.find('head')
		body = html.find('body')
		tag = self.tag
		return tag.html(
			head,
			tag.body(
				tag.h1(self.site.title, id='top'),
				self.generate_search(),
				self.generate_crumbs(),
				tag.h2(self.title),
				list(body), # Copy of the original <body> content
				self.generate_footer(),
				**body.attrib # Copy of the original <body> attributes
			),
			**html.attrib # Copy of the original <html> attributes
		)

	def generate_head(self):
		head = super(PlainDocument, self).generate_head()
		tag = self.tag
		# Add styles and scripts
		head.append(self.site.plain_style.link())
		head.append(self.site.plain_script.link())
		return head

	def generate_search(self):
		if self.site.search:
			tag = self.tag
			return tag.form(
				'Search: ',
				tag.input(type='text', name='q', size=20),
				' ',
				tag.input(type='submit', value='Go'),
				id='search',
				method='get',
				action='search.php'
			)
		else:
			return ''

	def generate_crumbs(self):
		"""Creates the breadcrumb links above the article body."""
		if self.parent:
			if isinstance(self, PlainSiteIndex):
				doc = self.parent
			else:
				doc = self
			links = [doc.title]
			doc = doc.parent
			while doc:
				links.append(' > ')
				links.append(doc.link())
				doc = doc.parent
			return self.tag.p(reversed(links), id='breadcrumbs')
		else:
			return self.tag.p('', id='breadcrumbs')

	def generate_footer(self):
		if self.site.copyright or self.site.last_updated:
			tag = self.tag
			footer = tag.div(id='footer')
			if self.site.copyright:
				footer.append(tag.p(self.site.copyright, id='copyright'))
			if self.site.last_updated:
				footer.append(tag.p('Updated on %s' % self.site.date.strftime('%a, %d %b %Y'), id='timestamp'))
			return footer
		else:
			return ''


class PlainPopup(HTMLPopupDocument):
	def generate_head(self):
		head = super(PlainPopup, self).generate_head()
		head.append(self.site.plain_style.link())
		return head


class PlainObjectDocument(HTMLObjectDocument, PlainDocument):
	def generate(self):
		doc = super(PlainObjectDocument, self).generate()
		tag = self.tag
		body = doc.find('body')
		# Build a TOC from all <h3> elements contained in <div class="section">
		# elements, and insert it after the page title
		i = 3
		if self.site.search:
			i += 1
		body[i:i] = [
			tag.ul(
				(
					tag.li(tag.a(elem.find('h3').text, href='#' + elem.attrib['id'], title='Jump to section'))
					for elem in body
					if iselement(elem)
					and elem.tag == 'div'
					and elem.attrib.get('class') == 'section'
					and iselement(elem.find('h3'))
					and 'id' in elem.attrib
				),
				id='toc'
			)
		]
		return doc


class PlainSiteIndex(HTMLSiteIndexDocument, PlainDocument):
	def generate_body(self):
		body = super(PlainSiteIndex, self).generate_body()
		tag = self.tag
		# Generate the letter links to other docs in the index, and insert them
		# after the page title
		links = []
		item = self.first
		while item:
			if item is self:
				links.append(tag.strong(item.letter))
			else:
				links.append(tag.a(item.letter, href=item.url))
			links.append(' ')
			item = item.next
		# Add all the JavaScript toggles
		body[0:0] = [
			tag.p(links, id='letters'),
			tag.script("""
				$(document).ready(function() {
					/* Collapse all definition terms and add a click handler to toggle them */
					$('#index-list')
						.children('dd').hide().end()
						.children('dt').addClass('expand').click(function() {
							$(this)
								.toggleClass('expand')
								.toggleClass('collapse')
								.next().slideToggle();
						});
					/* Add the "expand all" and "collapse all" links */
					$('#letters')
						.append(
							$(document.createElement('a'))
								.attr('href', '#')
								.append('Expand all')
								.click(function() {
									$('#index-list')
										.children('dd').show().end()
										.children('dt').removeClass('expand').addClass('collapse');
									return false;
								})
						)
						.append(' ')
						.append(
							$(document.createElement('a'))
								.attr('href', '#')
								.append('Collapse all')
								.click(function() {
									$('#index-list')
										.children('dd').hide().end()
										.children('dt').removeClass('collapse').addClass('expand');
									return false;
								})
						);
				});
			""")
		]
		return body


class PlainSearch(PlainDocument):
	"""Document class containing the PHP search script"""

	search_php = resource_string(__name__, 'search.php')

	def __init__(self, site):
		super(PlainSearch, self).__init__(site, 'search.php')
		self.title = '%s - Search Results' % site.title
		self.description = 'Search Results'
		self.search = False

	def generate_body(self):
		body = super(PlainSearch, self).generate_body()
		# XXX Dirty hack to work around a bug in ElementTree: if we use an ET
		# ProcessingInstruction here, ET converts XML special chars (<, >,
		# etc.) into XML entities, which is unnecessary and completely breaks
		# the PHP code. Instead we insert a place-holder and replace it with
		# PHP in an overridden serialize() method. This will break horribly if
		# the PHP code contains any non-ASCII characters and/or the target
		# encoding is not ASCII-based (e.g. EBCDIC).
		body.append(ProcessingInstruction('php', '__PHP__'))
		return body

	def serialize(self, content):
		# XXX See generate()
		php = self.search_php
		php = php.replace('__XAPIAN__', 'xapian.php')
		php = php.replace('__LANG__', self.site.lang)
		php = php.replace('__ENCODING__', self.site.encoding)
		result = super(PlainSearch, self).serialize(content)
		return result.replace('__PHP__', php)


class PlainGraphDocument(GraphObjectDocument):
	def __init__(self, site, dbobject):
		super(PlainGraphDocument, self).__init__(site, dbobject)
		self.written = False
		self.scale = None

	def generate(self):
		(maxw, maxh) = self.site.max_graph_size
		graph = super(PlainGraphDocument, self).generate()
		graph.ratio = str(float(maxh) / float(maxw))
		return graph

	def write(self):
		# Overridden to set the introduced "written" flag (to ensure we don't
		# attempt to write the graph more than once due to the induced write()
		# call in the overridden _link() method), and to handle resizing the
		# image if it's larger than the maximum size specified in the config
		try:
			if not self.written:
				super(PlainGraphDocument, self).write()
				self.written = True
				if self.usemap:
					try:
						im = Image.open(self.filename)
					except IOError, e:
						raise Exception('Failed to open image "%s" for resizing: %s' % (self.filename, e))
					(maxw, maxh) = self.site.max_graph_size
					(w, h) = im.size
					if w > maxw or h > maxh:
						# If the graph is larger than the maximum specified size,
						# move the original to name.full.ext and create a smaller
						# version using PIL. The scaling factor is stored so that
						# the overridden map() method can use it to adjust the
						# client side image map
						self.scale = min(float(maxw) / w, float(maxh) / h)
						neww = int(round(w * self.scale))
						newh = int(round(h * self.scale))
						try:
							if w * h * 3 / 1024**2 < 500:
								# Use a high-quality anti-aliased resize if to do so
								# would use <500Mb of RAM (which seems a reasonable
								# cut-off point on modern machines) - the conversion
								# to RGB is the really memory-heavy bit
								im = im.convert('RGB').resize((neww, newh), Image.ANTIALIAS)
							else:
								im = im.resize((neww, newh), Image.NEAREST)
						except Exception, e:
							raise Exception('Failed to resize image "%s" from (%dx%d) to (%dx%d): %s' % (self.filename, w, h, neww, newh, e))
						im.save(self.filename)
		except Exception, e:
			self.write_broken(str(e))

	def map(self):
		# Overridden to allow generating the client-side map for the "full
		# size" graph, or the smaller version potentially produced by the
		# write() method
		self.write()
		result = super(PlainGraphDocument, self).map()
		if self.scale is not None:
			for area in result:
				# Convert coords string into a list of integer tuples
				orig_coords = (
					tuple(int(i) for i in coord.split(','))
					for coord in area.attrib['coords'].split(' ')
				)
				# Resize all the coordinates by the scale
				scaled_coords = (
					tuple(int(round(i * self.scale)) for i in coord)
					for coord in orig_coords
				)
				# Convert the scaled results back into a string
				area.attrib['coords'] = ' '.join(
					','.join(str(i) for i in coord)
					for coord in scaled_coords
				)
		return result


# Declare classes for all the static documents in the plain HTML plugin

class PlainStyle(StyleDocument):
	def __init__(self, site):
		super(PlainStyle, self).__init__(site, 'styles.css', resource_stream(__name__, 'styles.css'))

class PlainScript(ScriptDocument):
	def __init__(self, site):
		super(PlainScript, self).__init__(site, 'script.js', resource_stream(__name__, 'scripts.js'))

class HeaderImage(ImageDocument):
	def __init__(self, site):
		super(HeaderImage, self).__init__(site, 'header.png', resource_stream(__name__, 'header.png'))

class SortableImage(ImageDocument):
	def __init__(self, site):
		super(SortableImage, self).__init__(site, 'sortable.png', resource_stream(__name__, 'sortable.png'))

class SortAscImage(ImageDocument):
	def __init__(self, site):
		super(SortAscImage, self).__init__(site, 'sortasc.png', resource_stream(__name__, 'sortasc.png'))

class SortDescImage(ImageDocument):
	def __init__(self, site):
		super(SortDescImage, self).__init__(site, 'sortdesc.png', resource_stream(__name__, 'sortdesc.png'))

class ExpandImage(ImageDocument):
	def __init__(self, site):
		super(ExpandImage, self).__init__(site, 'expand.png', resource_stream(__name__, 'expand.png'))

class CollapseImage(ImageDocument):
	def __init__(self, site):
		super(CollapseImage, self).__init__(site, 'collapse.png', resource_stream(__name__, 'collapse.png'))


# Declare styled document and graph classes

class PlainDatabaseDocument(PlainObjectDocument, DatabaseDocument):
	pass

class PlainSchemaDocument(PlainObjectDocument, SchemaDocument):
	pass

class PlainTableDocument(PlainObjectDocument, TableDocument):
	pass

class PlainViewDocument(PlainObjectDocument, ViewDocument):
	pass

class PlainAliasDocument(PlainObjectDocument, AliasDocument):
	pass

class PlainUniqueKeyDocument(PlainObjectDocument, UniqueKeyDocument):
	pass

class PlainForeignKeyDocument(PlainObjectDocument, ForeignKeyDocument):
	pass

class PlainCheckDocument(PlainObjectDocument, CheckDocument):
	pass

class PlainIndexDocument(PlainObjectDocument, IndexDocument):
	pass

class PlainTriggerDocument(PlainObjectDocument, TriggerDocument):
	pass

class PlainFunctionDocument(PlainObjectDocument, FunctionDocument):
	pass

class PlainProcedureDocument(PlainObjectDocument, ProcedureDocument):
	pass

class PlainTablespaceDocument(PlainObjectDocument, TablespaceDocument):
	pass

class PlainSchemaGraph(SchemaGraph, PlainGraphDocument):
	pass

class PlainTableGraph(TableGraph, PlainGraphDocument):
	pass

class PlainViewGraph(ViewGraph, PlainGraphDocument):
	pass

class PlainAliasGraph(AliasGraph, PlainGraphDocument):
	pass