# vim: set noet sw=4 ts=4:

"""Plain site and document classes.

This module defines subclasses of the classes in the html module which override
certain methods to provide formatting specific to the plain style.
"""

import os
import codecs
import logging
from db2makedoc.graph import Graph, Node, Edge, Cluster
from db2makedoc.etree import ProcessingInstruction
from db2makedoc.db import (
	DatabaseObject, Database, Schema, Relation,
	Table, View, Alias, Trigger
)
from db2makedoc.plugins.html.document import (
	HTMLElementFactory, ObjectGraph, WebSite, HTMLDocument, HTMLObjectDocument,
	HTMLIndexDocument, HTMLExternalDocument, StyleDocument, ScriptDocument,
	ImageDocument, GraphDocument, GraphObjectDocument, SQLStyle, JQueryScript,
	JQueryUIScript, TablesorterScript, ThickboxScript, ThickboxStyle
)

# Import the imaging library
try:
	from PIL import Image
except ImportError:
	# Ignore any import errors - the main plugin takes care of warning the
	# user if PIL is required but not present
	pass

# Determine the path containing this module (used for locating external source
# files like CSS, PHP and JavaScript below)
_my_path = os.path.dirname(os.path.abspath(__file__))


class PlainElementFactory(HTMLElementFactory):
	# Overridden to apply plain styles to certain elements

	def _add_class(self, node, cls):
		classes = set(node.attrib.get('class', '').split(' '))
		classes.add(cls)
		node.attrib['class'] = ' '.join(classes)

	def table(self, *content, **attrs):
		attrs.setdefault('cellspacing', '1')
		table = self._element('table', *content, **attrs)
		nosort = []
		try:
			thead = self._find(table, 'thead')
		except:
			pass
		else:
			for tr in thead.findall('tr'):
				if 'id' in table.attrib:
					for index, th in enumerate(tr.findall('th')):
						if 'nosort' in th.attrib.get('class', '').split():
							nosort.append(index)
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
			# plugin for this table, and scan th elements for any nosort
			# classes to disable sorting on them
			if 'id' in table.attrib:
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
					', '.join('%d: {sorter:false}' % col for col in nosort)
				))
				return (table, script)
		return table


class PlainGraph(ObjectGraph):
	# Overridden to style graphs to fit the site style

	def style(self, item):
		super(PlainGraph, self).style(item)
		# Set the graph to use the same default font as the stylesheet
		# XXX Any way to set a fallback here like in CSS?
		if isinstance(item, (Node, Edge)):
			item.fontname = 'Trebuchet MS'
			item.fontsize = 9.0
		elif isinstance(item, Cluster):
			item.fontname = 'Trebuchet MS'
			item.fontsize = 11.0
		# Set shapes and color schemes on objects that represent database
		# objects
		if hasattr(item, 'dbobject'):
			if isinstance(item.dbobject, Schema):
				item.style = 'filled'
				item.fillcolor = '#ece6d7'
				item.color = '#ece6d7'
			elif isinstance(item.dbobject, Relation):
				item.shape = 'rectangle'
				item.style = 'filled'
				if isinstance(item.dbobject, Table):
					item.fillcolor = '#bbbbff'
				elif isinstance(item.dbobject, View):
					item.style = 'filled,rounded'
					item.fillcolor = '#bbffbb'
				elif isinstance(item.dbobject, Alias):
					if isinstance(item.dbobject.final_relation, View):
						item.style = 'filled,rounded'
					item.fillcolor = '#ffffbb'
				item.color = '#000000'
			elif isinstance(item.dbobject, Trigger):
				item.shape = 'hexagon'
				item.style = 'filled'
				item.fillcolor = '#ffbbbb'


class PlainSite(WebSite):
	"""Site class representing a collection of PlainDocument instances."""

	def __init__(self, database, options):
		super(PlainSite, self).__init__(database, options)
		self.last_updated = options['last_updated']
		self.max_graph_size = options['max_graph_size']
		self.stylesheets = options['stylesheets']
		self.tag = PlainElementFactory()
		self.graph_class = PlainGraph
		# Create static documents. Note that we don't keep a reference to the
		# image documents.  Firstly, the objects will be kept alive by virtue
		# of being added to the urls map in this object (by virtue of the
		# add_document call in their constructors). Secondly, no document ever
		# refers directly to these objects - they're referred to solely in in
		# the plain stylesheet
		self.plain_style = PlainStyle(self)
		self.jquery_script = JQueryScript(self)
		self.tablesorter_script = TablesorterScript(self)
		self.thickbox_style = ThickboxStyle(self)
		self.thickbox_script = ThickboxScript(self)
		HeaderImage(self)
		SortableImage(self)
		SortAscImage(self)
		SortDescImage(self)
		ExpandImage(self)
		CollapseImage(self)


class PlainExternalDocument(HTMLExternalDocument):
	pass


class PlainDocument(HTMLDocument):
	"""Document class for use with the plain style."""

	def generate(self):
		doc = super(PlainDocument, self).generate()
		# Add styles and scripts
		tag = self.tag
		headnode = tag._find(doc, 'head')
		headnode.append(self.site.plain_style.link())
		headnode.append(self.site.jquery_script.link())
		headnode.append(self.site.tablesorter_script.link())
		headnode.append(self.site.thickbox_style.link())
		headnode.append(self.site.thickbox_script.link())
		# Add common header elements to the body
		bodynode = tag._find(doc, 'body')
		bodynode.append(tag.h1(self.site.title, id='top'))
		if self.site.search:
			bodynode.append(tag.form(
				'Search: ',
				tag.input(type='text', name='q', size=20),
				' ',
				tag.input(type='submit', value='Go'),
				method='get', action='search.php'
			))
		bodynode.append(self.generate_crumbs())
		return doc

	def generate_crumbs(self):
		"""Creates the breadcrumb links above the article body."""
		if self.parent:
			if isinstance(self, PlainSiteIndexDocument):
				doc = self.parent
			else:
				doc = self
			links = [doc.title]
			doc = doc.parent
			while doc:
				links.insert(0, ' > ')
				links.insert(0, doc.link())
				doc = doc.parent
			return self.tag.p(links, id='breadcrumbs')
		else:
			return self.tag.p('', id='breadcrumbs')

	def format_sql(self, sql, terminator=';', number_lines=False, id=None):
		# Overridden to add line number toggling capability (via jQuery)
		result = super(PlainDocument, self).format_sql(sql, terminator, number_lines, id)
		if number_lines and id:
			result = (result,
				self.tag.script("""
					$(document).ready(function() {
						$('#%(id)s').before(
							$(document.createElement('p')).append(
								$(document.createElement('a'))
									.append('Toggle line numbers')
									.attr('href', '#')
									.click(function() {
										$('#%(id)s').toggleClass('hide-num');
										return false;
									})
							).addClass('toggle')
						);
					});
				""" % {'id': id}))
		return result


class PlainObjectDocument(HTMLObjectDocument, PlainDocument):
	"""Document class representing a database object (table, view, index, etc.)"""

	def __init__(self, site, dbobject):
		super(PlainObjectDocument, self).__init__(site, dbobject)
		self.last_updated = site.last_updated
	
	def generate(self):
		doc = super(PlainObjectDocument, self).generate()
		# Add body content
		tag = self.tag
		bodynode = tag._find(doc, 'body')
		bodynode.append(tag.h2('%s %s' % (self.site.type_names[self.dbobject.__class__], self.dbobject.qualified_name)))
		sections = self.generate_sections()
		if sections:
			bodynode.append(tag.ul((
				tag.li(tag.a(title, href='#' + id, title='Jump to section'))
				for (id, title, content) in sections
			), id='toc'))
			tag._append(bodynode, (
				(tag.h3(title, id=id), content)
				for (id, title, content) in sections
			))
		if self.copyright:
			bodynode.append(tag.p(self.copyright, id='footer'))
		if self.last_updated:
			bodynode.append(tag.p('Updated on %s' % self.date.strftime('%a, %d %b %Y'), id='timestamp'))
		return doc

	def generate_sections(self):
		"""Creates the actual body content."""
		# Override in descendents to return a list of tuples with the following
		# structure: (id, title, [content]). "content" is a list of Elements.
		return []


class PlainSiteIndexDocument(HTMLIndexDocument, PlainDocument):
	"""Document class containing an alphabetical index of objects"""

	def generate(self):
		doc = super(PlainSiteIndexDocument, self).generate()
		# Add body content
		tag = self.tag
		bodynode = tag._find(doc, 'body')
		bodynode.append(tag.h2('%s Index' % self.site.type_names[self.dbclass]))
		# Generate the letter links to other docs in the index
		links = tag.p(id='letters')
		item = self.first
		while item:
			if item is self:
				tag._append(links, tag.strong(item.letter))
			else:
				tag._append(links, tag.a(item.letter, href=item.url))
			tag._append(links, ' ')
			item = item.next
		bodynode.append(links)
		# Sort the list of items in the index, and build the content. Note that
		# self.items is actually reference to a site level object and therefore
		# must be considered read-only, hence why the list is not sorted
		# in-place here
		index = sorted(self.items, key=lambda item: '%s %s' % (item.name, item.qualified_name))
		index = sorted(dict(
			(item1.name, [item2 for item2 in index if item1.name == item2.name])
			for item1 in index
		).iteritems(), key=lambda (name, _): name)
		bodynode.append(tag.dl(
			((
				tag.dt(name),
				tag.dd(
					tag.dl(
						(
							tag.dt(self.site.type_names[item.__class__], ' ', self.site.link_to(item, parent=True)),
							tag.dd(self.format_comment(item.description, summary=True))
						) for item in items
					)
				)
			) for (name, items) in index),
			id='index-list'
		))
		# Generate the script blocks to handle expanding/collapsing definition
		# list entries, and the placeholder for the "expand all" and "collapse
		# all" links
		bodynode.append(tag.script("""
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
		"""))
		return doc


class PlainSearchDocument(PlainDocument):
	"""Document class containing the PHP search script"""

	search_php = open(os.path.join(_my_path, 'search.php'), 'r').read()

	def __init__(self, site):
		super(PlainSearchDocument, self).__init__(site, 'search.php')
		self.title = '%s - Search Results' % site.title
		self.description = 'Search Results'
		self.search = False
		self.last_updated = site.last_updated
	
	def generate(self):
		doc = super(PlainSearchDocument, self).generate()
		tag = self.tag
		bodynode = tag._find(doc, 'body')
		bodynode.append(tag.p(
			tag.a(self.site.home_title, href=self.site.home_url),
			' > ',
			'Search Results',
			id='breadcrumbs'
		))
		bodynode.append(tag.h2('Search Results'))
		# XXX Dirty hack to work around a bug in ElementTree: if we use an ET
		# ProcessingInstruction here, ET converts XML special chars (<, >,
		# etc.) into XML entities, which is unnecessary and completely breaks
		# the PHP code. Instead we insert a place-holder and replace it with
		# PHP in an overridden serialize() method. This will break horribly if
		# the PHP code contains any non-ASCII characters and/or the target
		# encoding is not ASCII-based (e.g. EBCDIC).
		bodynode.append(ProcessingInstruction('php', '__PHP__'))
		if self.copyright:
			bodynode.append(tag.p(self.copyright, id='footer'))
		if self.last_updated:
			bodynode.append(tag.p('Indexed on %s' % self.date.strftime('%a, %d %b %Y'), id='timestamp'))
		return doc
	
	def serialize(self, content):
		# XXX See generate()
		php = self.search_php
		php = php.replace('__XAPIAN__', 'xapian.php')
		php = php.replace('__LANG__', self.site.lang)
		php = php.replace('__ENCODING__', self.site.encoding)
		result = super(PlainSearchDocument, self).serialize(content)
		return result.replace('__PHP__', php)


class PlainGraphDocument(GraphObjectDocument):
	"""Graph class representing a database object or collection of objects."""

	def __init__(self, site, dbobject):
		"""Initializes an instance of the class."""
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
		if not self.written:
			super(PlainGraphDocument, self).write()
			self.written = True
			if self.usemap:
				try:
					im = Image.open(self.filename)
				except IOError, e:
					logging.warning('Failed to open image "%s" for resizing: %s' % (self.filename, e))
					if os.path.exists(self.filename):
						newname = '%s.broken' % self.filename
						logging.warning('Removing potentially corrupt image file "%s" to "%s"' % (self.filename, newname))
						if os.path.exists(newname):
							os.unlink(newname)
						os.rename(self.filename, newname)
					return
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
					if w * h * 3 / 1024**2 < 500:
						# Use a high-quality anti-aliased resize if to do so
						# would use <500Mb of RAM (which seems a reasonable
						# cut-off point on modern machines) - the conversion
						# to RGB is the really memory-heavy bit
						im = im.convert('RGB').resize((neww, newh), Image.ANTIALIAS)
					else:
						im = im.resize((neww, newh), Image.NEAREST)
					im.save(self.filename)

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

mod_path = os.path.dirname(os.path.abspath(__file__))

class PlainStyle(StyleDocument):
	def __init__(self, site):
		super(PlainStyle, self).__init__(site, os.path.join(mod_path, 'styles.css'))

class HeaderImage(ImageDocument):
	def __init__(self, site):
		super(HeaderImage, self).__init__(site, os.path.join(mod_path, 'header.png'))

class SortableImage(ImageDocument):
	def __init__(self, site):
		super(SortableImage, self).__init__(site, os.path.join(mod_path, 'sortable.png'))

class SortAscImage(ImageDocument):
	def __init__(self, site):
		super(SortAscImage, self).__init__(site, os.path.join(mod_path, 'sortasc.png'))

class SortDescImage(ImageDocument):
	def __init__(self, site):
		super(SortDescImage, self).__init__(site, os.path.join(mod_path, 'sortdesc.png'))

class ExpandImage(ImageDocument):
	def __init__(self, site):
		super(ExpandImage, self).__init__(site, os.path.join(mod_path, 'expand.png'))

class CollapseImage(ImageDocument):
	def __init__(self, site):
		super(CollapseImage, self).__init__(site, os.path.join(mod_path, 'collapse.png'))

