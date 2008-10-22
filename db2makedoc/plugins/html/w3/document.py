# vim: set noet sw=4 ts=4:

"""w3 specific site and document classes.

This module defines subclasses of the classes in the html module which override
certain methods to provide formatting specific to the w3 style [1].

[1] http://w3.ibm.com/standards/intranet/homepage/v8/index.html
"""

import os
import re
import codecs
import logging
from collections import deque
from db2makedoc.graph import Graph, Node, Edge, Cluster
from db2makedoc.etree import ProcessingInstruction, fromstring, flatten_html
from db2makedoc.db import (
	DatabaseObject, Database, Schema, Relation,
	Table, View, Alias, Trigger
)
from db2makedoc.plugins.html.document import (
	ElementFactory, WebSite, HTMLDocument, HTMLObjectDocument,
	HTMLIndexDocument, HTMLExternalDocument, CSSDocument, JavaScriptDocument,
	GraphDocument, GraphObjectDocument, SQLCSSDocument
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


class W3ElementFactory(ElementFactory):
	# Overridden to apply w3 styles to certain elements

	def _add_class(self, node, cls):
		classes = set(node.attrib.get('class', '').split(' '))
		classes.add(cls)
		node.attrib['class'] = ' '.join(classes)

	def hr(self, *content, **attrs):
		# Horizontal rules are implemented as a div with class 'hrule-dots'
		if not content:
			content = (u'\u00A0',) # &nbsp;
		result = self._element('div', *content, **attrs)
		self._add_class(result, 'hrule-dots')
		return result

	def table(self, *content, **attrs):
		table = self._element('table', *content, **attrs)
		# If there are thead and tfoot elements in content, apply the
		# 'blue-dark' CSS class to them. Also check for th elements
		# with the 'nosort' class (see tablesorter extension below)
		nosort = []
		try:
			thead = self._find(table, 'thead')
		except:
			pass
		else:
			for tr in thead.findall('tr'):
				self._add_class(tr, 'blue-dark')
				if 'id' in table.attrib:
					for index, th in enumerate(tr.findall('th')):
						if 'nosort' in th.attrib.get('class', '').split():
							nosort.append(index)
		try:
			tfoot = self._find(table, 'tfoot')
		except:
			pass
		else:
			for tr in tfoot.findall('tr'):
				self._add_class(tr, 'blue-dark')
		try:
			tbody = self._find(table, 'tbody')
		except:
			pass
		else:
			# If there's a tbody element, apply 'even' and 'odd' CSS classes to
			# rows in the body, and add 'basic-table' to the table's CSS
			# classes.  We don't do this for tables without an explicit tbody
			# as they are very likely to be pure layout tables (e.g. the search
			# table in the masthead)
			for index, tr in enumerate(tbody.findall('tr')):
				self._add_class(tr, ['odd', 'even'][index % 2])
			self._add_class(table, 'basic-table')
			# If there's an id on the main table element, add a script element
			# within the table definition to activate the jQuery tablesorter
			# plugin for this table. Scan the th elements for any with the
			# 'nosort' class and disable sorting on those columns
			if 'id' in table.attrib:
				table.append(self.script("""
					$(document).ready(function() {
						$('table.basic-table#%s').tablesorter({
							cssAsc:       'header-sort-up',
							cssDesc:      'header-sort-down',
							cssHeader:    'header',
							widgets:      ['zebra'],
							widgetZebra:  {css: ['odd', 'even']},
							headers:      {%s},
						});
					});
				""" % (
					table.attrib['id'],
					', '.join('%d: {sorter:false}' % col for col in nosort)
				)))
		return table

tag = W3ElementFactory()


class W3Site(WebSite):
	"""Site class representing a collection of W3Document instances."""

	def __init__(self, database, options):
		"""Initializes an instance of the class."""
		super(W3Site, self).__init__(database, options)
		self.breadcrumbs = options['breadcrumbs']
		self.last_updated = options['last_updated']
		self.max_graph_size = options['max_graph_size']
		self.feedback_url = options['feedback_url']
		self.menu_items = options['menu_items']
		self.related_items = options['related_items']
		self.object_menus = {}
		self.menu = None


class W3ExternalDocument(HTMLExternalDocument):
	pass


class W3Document(HTMLDocument):
	"""Document class for use with the w3v8 style."""

	def generate(self):
		doc = super(W3Document, self).generate()
		# Add stylesheets and scripts specific to the w3v8 style
		headnode = tag._find(doc, 'head')
		headnode.append(tag.meta(name='IBM.Country', content=self.site.sublang)) # XXX Add a country config item?
		headnode.append(tag.meta(name='IBM.Effective', content=self.date, scheme='iso8601'))
		headnode.append(tag.script(src='//w3.ibm.com/ui/v8/scripts/scripts.js'))
		headnode.append(tag.style(src='//w3.ibm.com/ui/v8/css/v4-screen.css'))
		# Tag the body as a w3 document
		bodynode = tag._find(doc, 'body')
		bodynode.attrib['id'] = 'w3-ibm-com'
		return doc


class W3PopupDocument(W3Document):
	"""Document class representing a popup help window."""

	def __init__(self, site, url, title, body, width=400, height=300):
		"""Initializes an instance of the class."""
		super(W3PopupDocument, self).__init__(site, url)
		self.search = False
		self.title = title
		self.body = body
		self.width = width
		self.height = height

	def generate(self):
		# Call the inherited method to create the skeleton document
		doc = super(W3PopupDocument, self).generate()
		# Add styles specific to w3v8 popup documents
		headnode = tag._find(doc, 'head')
		headnode.append(tag.style(src='//w3.ibm.com/ui/v8/css/v4-interior.css'))
		headnode.append(tag.style("""
			@import url("//w3.ibm.com/ui/v8/css/screen.css");
			@import url("//w3.ibm.com/ui/v8/css/interior.css");
			@import url("//w3.ibm.com/ui/v8/css/popup-window.css");
		""", media='all'))
		headnode.append(tag.style(src='//w3.ibm.com/ui/v8/css/print.css', media='print'))
		for sheet in self.site.stylesheets:
			headnode.append(sheet.link())
		# Generate the popup content
		bodynode = tag._find(doc, 'body')
		bodynode.append(tag.div(
			tag.img(src='//w3.ibm.com/ui/v8/images/id-w3-sitemark-small.gif', width=182, height=26,
				alt='', id='popup-w3-sitemark'),
			id='popup-masthead'
		))
		bodynode.append(tag.div(
			tag.div(
				tag.h1(self.title),
				self.body,
				tag.div(
					tag.hr(),
					tag.div(
						tag.a('Close Window', href='javascript:close();', class_='float-right'),
						tag.a('Print', href='javascript:window.print();', class_='popup-print-link'),
						class_='content'
					),
					tag.div(u'\u00A0', style='clear:both;'),
					id='popup-footer'
				),
				tag.p(tag.a('Terms of use', href='http://w3.ibm.com/w3/info_terms_of_use.html'), class_='terms'),
				id='content-main'
			),
			id='content'
		))
		return doc

	def link(self):
		# Modify the link to use the JS popup() routine
		return tag.a(self.title, href=self.url, title=self.title,
			onclick='javascript:popup("%s","internal",%d,%d);return false;' % (self.url, self.height, self.width))


class W3ArticleDocument(W3Document):
	"""Article class (full web page) for use with the w3v8 style."""

	def __init__(self, site, url, filename=None):
		"""Initializes an instance of the class."""
		super(W3ArticleDocument, self).__init__(site, url, filename)
		self.breadcrumbs = site.breadcrumbs
		self.last_updated = site.last_updated
		self.feedback_url = site.feedback_url
		self.menu_items = site.menu_items
		self.related_items = site.related_items

	def generate(self):
		doc = super(W3ArticleDocument, self).generate()
		# Add the w3v8 1-column article styles
		headnode = tag._find(doc, 'head')
		headnode.append(tag.style("""
			@import url("//w3.ibm.com/ui/v8/css/screen.css");
			@import url("//w3.ibm.com/ui/v8/css/icons.css");
			@import url("//w3.ibm.com/ui/v8/css/tables.css");
			@import url("//w3.ibm.com/ui/v8/css/interior.css");
			@import url("//w3.ibm.com/ui/v8/css/interior-1-col.css");
		""", media='all'))
		headnode.append(tag.style(src='//w3.ibm.com/ui/v8/css/print.css', media='print'))
		for sheet in self.site.stylesheets:
			headnode.append(sheet.link())
		for script in self.site.scripts:
			headnode.append(script.link())
		# Generate the masthead and accessibility sections
		bodynode = tag._find(doc, 'body')
		bodynode.attrib['class'] = 'article'
		bodynode.append(tag.div(tag.a('Skip to main content', href='#content-main', accesskey='2'), class_='skip'))
		bodynode.append(tag.div(tag.a('Skip to navigation', href='#left-nav', accesskey='n'), class_='skip'))
		bodynode.append(tag.div(
			tag.p('The access keys for this page are:', class_='access'),
			tag.ul(
				tag.li('ALT plus 0 links to this site\'s ',
					tag.a('Accessibility Statement', href='http://w3.ibm.com/w3/access-stmt.html', accesskey='0')
				),
				tag.li('ALT plus 1 links to the w3.ibm.com home page.'),
				tag.li('ALT plus 2 skips to the main content.'),
				tag.li('ALT plus 4 skips to the search form.'),
				tag.li('ALT plus 9 links to the feedback page.'),
				tag.li('ALT plus N skips to navigation.'),
				class_='access'
			),
			tag.p('Additional accessibility information for w3.ibm.com can be found ',
				tag.a('on the w3 Accessibility Statement page', href='http://w3.ibm.com/w3/access-stmt.html'),
				class_='access'
			),
			id='access-info'
		))
		bodynode.append(tag.div(
			tag.h2('Start of masthead', class_='access'),
			tag.div(
				tag.img(src='//w3.ibm.com/ui/v8/images/id-w3-sitemark-simple.gif', width=54, height=33),
				id='prt-w3-sitemark'
			),
			tag.div(
				tag.img(src='//w3.ibm.com/ui/v8/images/id-ibm-logo-black.gif', width=44, height=15),
				id='prt-ibm-logo'
			),
			tag.div(
				tag.img(src='//w3.ibm.com/ui/v8/images/id-w3-sitemark-large.gif', width=266, height=70,
					alt='IBM Logo', usemap='#sitemark_map'),
				tag.map(
					tag.area(shape='rect', alt='Link to W3 Home Page', coords='0,0,130,70', href='http://w3.ibm.com/', accesskey='1'),
					id='sitemark_map', name='sitemark_map'
				),
				id='w3-sitemark'
			),
			tag.div(self.site.title, id='site-title-only'),
			tag.div(
				tag.img(src='//w3.ibm.com/ui/v8/images/id-ibm-logo.gif', width=44, height=15, alt=''),
				id='ibm-logo'
			),
			tag.div(
				tag.a(' w3 Home ', id='w3home', href='http://w3.ibm.com/'),
				tag.a(' BluePages ', id='bluepages', href='http://w3.ibm.com/bluepages/'),
				tag.a(' HelpNow ', id='helpnow', href='http://w3.ibm.com/help/'),
				tag.a(' Feedback ', id='feedback', href=self.feedback_url, accesskey='9'),
				id='persistent-nav'
			),
			tag.div(
				tag.form(
					tag.table(
						tag.tr(
							tag.td(
								tag.label('Search w3', for_='header-search-field'),
								class_='label'
							),
							tag.td(
								tag.input(id='header-search-field', name='qt', type='text', accesskey='4'),
								class_='field'
							),
							tag.td(
								tag.label('go button', class_='access', for_='header-search-btn'),
								tag.input(id='header-search-btn', type='image', alt='Go', src='//w3.ibm.com/ui/v8/images/btn-go-dark.gif'),
								class_='submit'
							)
						),
						tag.tr(
							tag.td(),
							tag.td(
								tag.input(
									tag.label(' Search %s' % self.site.title, for_='header-search-this'), id='header-search-this',
									name='header-search-this', type='checkbox', value='doc', onclick='javascript:toggleSearch();'
								),
								colspan=2, class_='limiter'
							)
						),
						cellspacing=0, cellpadding=0, class_='header-search'
					),
					action='http://w3.ibm.com/search/do/search', method='get', id='search'
				),
				id='header-search'
			),
			tag.div(
				tag.img(src='//w3.ibm.com/ui/v8/images/icon-system-status-alert.gif', width=12, height=10, alt=''),
				' This Web page is best used in a modern browser. Since your browser is no longer supported by IBM,',
				' please upgrade your web browser at the ',
				tag.a('ISSI site', href='http://w3.ibm.com/download/standardsoftware/'),
				'.',
				id='browser-warning'
			),
			id='masthead'
		))
		bodynode.append(tag.div(
			tag.h1('Start of main content', class_='access'),
			tag.div(
				self.generate_head(),
				self.generate_crumbs(),
				id='content-head'
			),
			tag.div(
				tag.h1(self.title),
				self.generate_main(),
				tag.p(
					tag.a('Terms of use', href='http://w3.ibm.com/w3/info_terms_of_use.html'),
					class_='terms'
				),
				id='content-main'
			),
			id='content'
		))
		bodynode.append(tag.div(
			tag.h2('Start of left navigation', class_='access'),
			tag.div(
				self.generate_menu(),
				id='left-nav'
			),
			self.generate_related(),
			id='navigation'
		))
		return doc

	def generate_crumbs(self):
		"""Creates the breadcrumb links above the article body."""
		if self.breadcrumbs and self.parent:
			if isinstance(self, W3SiteIndexDocument):
				doc = self.parent
			else:
				doc = self
			links = [doc.title]
			doc = doc.parent
			while doc:
				links.append(' > ')
				links.append(doc.link())
				doc = doc.parent
			return tag.p(reversed(links), id='breadcrumbs')
		else:
			return ''

	def generate_related(self):
		"""Creates the related links below the left-hand navigation menu."""
		if self.related_items:
			return (
				tag.p('Related links:'),
				tag.ul(tag.li(tag.a(title, href=url)) for (title, url) in self.related_items)
			)
		else:
			return ''

	def generate_menu(self):
		"""Creates the left navigation menu links."""

		def link(doc, active=False, visible=True):
			"""Sub-routine which generates a menu link from a document."""
			if isinstance(doc, HTMLObjectDocument) and doc.parent:
				content = doc.dbobject.name
			elif isinstance(doc, HTMLIndexDocument):
				content = doc.letter
			else:
				content = doc.title
			# Non-top-level items longer than 12 characters are truncated
			# and suffixed with a horizontal ellipsis (\u2026)
			if len(content) > 12 and doc.parent:
				content = content[:11] + u'\u2026'
			return tag.a(
				content,
				href=doc.url,
				title=doc.title,
				class_=(None, 'active')[active],
				style=('display: none;', None)[visible]
			)

		def more(above):
			"""Sub-routine which generates a "More Items" link."""
			return tag.a(
				[u'\u2193', u'\u2191'][above] + ' More items',
				href='#',
				title='More items',
				onclick='javascript:return showItems(this);'
			)

		def menu(doc, active=True, children=''):
			"""Sub-routine which generates all menu links recursively."""
			# Recurse upwards if level is too high (w3v8 doesn't support more
			# than 3 levels of menus)
			if doc.level >= 3:
				return menu(doc.parent, active, '')
			# Build the list of links for this menu level. The count is the
			# number of visible items before we start hiding things with "More
			# Items"
			links = deque((link(doc, active=active), children))
			count = 10
			pdoc = doc.prior
			ndoc = doc.next
			more_above = more_below = False
			while pdoc or ndoc:
				if pdoc:
					more_above = count <= 0 and doc.level > 0
					links.appendleft(link(pdoc, visible=not more_above))
					pdoc = pdoc.prior
					count -= 1
				if ndoc:
					more_below = count <= 0 and doc.level > 0
					links.append(link(ndoc, visible=not more_below))
					ndoc = ndoc.next
					count -= 1
			# Insert "More Items" links if necessary
			if more_above:
				links.appendleft(more(True))
			if more_below:
				links.append(more(False))
			# Wrap the list of links in a div
			links = tag.div(links, class_=['top-level', 'second-level', 'third-level'][doc.level])
			# Recurse up the document hierarchy if there are more levels
			if doc.level:
				return menu(doc.parent, False, links)
			else:
				return links

		return menu(self)

	def generate_head(self):
		"""Creates the header text above the article body."""
		if self.last_updated:
			return (
				tag.p('Updated on ', self.date.strftime('%a, %d %b %Y'), id='date-stamp'),
				tag.hr()
			)
		else:
			return ''

	def generate_main(self):
		"""Creates the article body."""
		return ''


class W3ObjectDocument(HTMLObjectDocument, W3ArticleDocument):
	"""Document class representing a database object (table, view, index, etc.)"""

	def flatten(self, content):
		# This overridden implementation returns flattened text from the
		# content-main <div> only, so that things like the links in the left
		# navigation menu don't corrupt the search results
		return flatten_html(tag._find(content, 'div', id='content-main'))

	def generate_main(self):
		sections = self.generate_sections()
		return (
			tag.ul((
				tag.li(tag.a(title, href='#' + id, title='Jump to section'))
				for (id, title, content) in sections
			), id='content-toc'),
			(
				(tag.hr(), tag.h2(title, id=id), content, tag.p(tag.a('Back to top', href='#masthead')))
				for (id, title, content) in sections
			)
		)

	def generate_sections(self):
		"""Creates the actual body content."""
		# Override in descendents to return a list of tuples with the following
		# structure: (id, title, [content]). "content" is a list of Elements.
		return []


class W3SiteIndexDocument(HTMLIndexDocument, W3ArticleDocument):
	"""Document class containing an alphabetical index of objects"""

	def generate_main(self):
		# Generate the letter links to other docs in the index
		links = tag.p()
		doc = self.first
		while doc:
			if doc is self:
				tag._append(links, tag.strong(doc.letter))
			else:
				tag._append(links, tag.a(doc.letter, href=doc.url))
			tag._append(links, ' ')
			doc = doc.next
		# Sort the list of items in the index, and build the content. Note that
		# self.items is actually reference to a site level object and therefore
		# must be considered read-only, hence why the list is not sorted
		# in-place here
		index = sorted(self.items, key=lambda item: '%s %s' % (item.name, item.qualified_name))
		index = sorted(dict(
			(item1.name, [item2 for item2 in index if item1.name == item2.name])
			for item1 in index
		).iteritems(), key=lambda (name, _): name)
		index = tag.dl(
			(
				tag.dt(name),
				tag.dd(
					tag.dl(
						(
							tag.dt(self.site.type_names[item.__class__], ' ', self.site.link_to(item, parent=True)),
							tag.dd(self.format_comment(item.description, summary=True))
						) for item in items
					)
				)
			) for (name, items) in index
		)
		return (
			links,
			tag.hr(),
			index
		)


class W3SearchDocument(W3ArticleDocument):
	"""Document class containing the PHP search script"""

	search_php = open(os.path.join(_my_path, 'search.php'), 'r').read()

	def __init__(self, site):
		super(W3SearchDocument, self).__init__(site, 'search.php')
		self.title = 'Search results'
		self.description = self.title
		self.search = False
		self.last_updated = site.last_updated
	
	def _get_parent(self):
		result = super(W3SearchDocument, self)._get_parent()
		if not result:
			return self.site.object_document(self.site.database)
		else:
			return result

	def generate_main(self):
		# XXX Dirty hack to work around a bug in ElementTree: if we use an ET
		# ProcessingInstruction here, ET converts XML special chars (<, >,
		# etc.) into XML entities, which is unnecessary and completely breaks
		# the PHP code. Instead we insert a place-holder and replace it with
		# PHP in an overridden serialize() method. This will break horribly if
		# the PHP code contains any non-ASCII characters and/or the target
		# encoding is not ASCII-based (e.g. EBCDIC).
		return ProcessingInstruction('php', '__PHP__')

	def serialize(self, content):
		# XXX See generate_main()
		php = self.search_php
		php = php.replace('__XAPIAN__', 'xapian.php')
		php = php.replace('__LANG__', self.site.lang)
		php = php.replace('__ENCODING__', self.site.encoding)
		result = super(W3SearchDocument, self).serialize(content)
		return result.replace('__PHP__', php)


class W3CSSDocument(CSSDocument):
	"""Stylesheet class to supplement the w3v8 style with SQL syntax highlighting."""

	styles_css = codecs.open(os.path.join(_my_path, 'styles.css'), 'r', 'UTF-8').read()

	def __init__(self, site):
		super(W3CSSDocument, self).__init__(site, 'styles.css')

	def generate(self):
		# We only need one supplemental CSS stylesheet (the default w3v8 styles
		# are reasonably comprehensive). So this method is brutally simple...
		doc = super(W3CSSDocument, self).generate()
		# If local search is not enabled, ensure the local search check box is
		# not shown
		if not self.site.search:
			doc += u"""
td.limiter { display: none; }
"""
		return doc + self.styles_css


class W3JavaScriptDocument(JavaScriptDocument):
	"""Code class to supplement the w3v8 style with some simple routines."""

	scripts_js = codecs.open(os.path.join(_my_path, 'scripts.js'), 'r', 'UTF-8').read()

	def __init__(self, site):
		super(W3JavaScriptDocument, self).__init__(site, 'scripts.js')

	def generate(self):
		doc = super(W3JavaScriptDocument, self).generate()
		return doc + self.scripts_js


class W3JQueryDocument(JavaScriptDocument):
	"""Class encapsulating the jQuery JavaScript library."""

	jquery_js = codecs.open(os.path.join(_my_path, 'jquery.js'), 'r', 'UTF-8').read()

	def __init__(self, site):
		super(W3JQueryDocument, self).__init__(site, 'jquery.js')

	def generate(self):
		return self.jquery_js


class W3JQueryTableSorterDocument(JavaScriptDocument):
	"""Class encapsulating the TableSorter jQuery plugin."""

	jquery_tablesorter_js = codecs.open(os.path.join(_my_path, 'jquery.tablesorter.js'), 'r', 'UTF-8').read()

	def __init__(self, site):
		super(W3JQueryTableSorterDocument, self).__init__(site, 'jquery.tablesorter.js')

	def generate(self):
		return self.jquery_tablesorter_js


class W3GraphDocument(GraphObjectDocument):
	"""Graph class representing a database object or collection of objects."""

	def __init__(self, site, dbobject):
		super(W3GraphDocument, self).__init__(site, dbobject)
		(maxw, maxh) = self.site.max_graph_size
		ratio = float(maxh) / float(maxw)
		self.graph.ratio = str(ratio)
		# Define a maximum size to prevent using /ridiculous/ amounts of memory
		# for stupidly huge schema diagrams. The maximum size is calculated as
		# the lesser of five times the requested maximum size (so PIL still
		# gets to do some nice resizing - or nicer than graphviz at any rate)
		# and an image 5000 pixels on a side (which would require 75Mb of RAM
		# in 24-bit colour)
		if maxw > maxh:
			maxw = min(maxw * 5, 5000)
			maxh = maxw * ratio
		else:
			maxh = min(maxh * 5, 5000)
			maxw = maxh / ratio
		dpi = float(self.graph.dpi)
		self.graph.size = '%f,%f' % (maxw / dpi, maxh / dpi)
		self.written = False
		if self.usemap:
			s, ext = os.path.splitext(self.filename)
			self.zoom_filename = s + os.path.extsep + 'zoom' + ext
			s, ext = self.url.rsplit('.', 1)
			self.zoom_url = s + '.zoom.' + ext
			self.scale = None

	def write(self):
		# Overridden to set the introduced "written" flag (to ensure we don't
		# attempt to write the graph more than once due to the induced write()
		# call in the overridden _link() method), and to handle resizing the
		# image if it's larger than the maximum size specified in the config
		if not self.written:
			super(W3GraphDocument, self).write()
			self.written = True
			if self.usemap:
				try:
					im = Image.open(self.filename)
				except IOError, e:
					logging.warning('Failed to open image "%s" for resizing: %s' % (self.filename, e))
					if os.path.exists(self.filename):
						newname = '%s.broken' % self.filename
						logging.warning('Moving potentially corrupt image file "%s" to "%s"' % (self.filename, newname))
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
					# the overridden _map() method can use it to adjust the
					# client side image map
					self.scale = min(float(maxw) / w, float(maxh) / h)
					logging.debug('Writing %s' % self.zoom_filename)
					if os.path.exists(self.zoom_filename):
						os.unlink(self.zoom_filename)
					os.rename(self.filename, self.zoom_filename)
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

	def map(self, zoom=False):
		# Overridden to allow generating the client-side map for the "full
		# size" graph, or the smaller version potentially produced by the
		# write() method
		if not self.written:
			self.write()
		result = super(W3GraphDocument, self).map()
		if self.scale is not None:
			if zoom:
				# Rewrite the id and name attributes
				result.attrib['id'] = self.zoom_url.rsplit('.', 1)[0] + '.map'
				result.attrib['name'] = result.attrib['id']
			else:
				for area in result:
					# Convert coords string in a list of integer tuples
					coords = [
						tuple(int(i) for i in coord.split(','))
						for coord in area.attrib['coords'].split(' ')
					]
					# Resize all the coordinates by the scale
					coords = [
						tuple(int(round(i * self.scale)) for i in coord)
						for coord in coords
					]
					# Convert the scaled results back into a string
					area.attrib['coords'] = ' '.join(
						','.join(str(i) for i in coord)
						for coord in coords
					)
		return result

	def link(self, *args, **kwargs):
		# Overridden to allow "zoomed" graphs with some extra JavaScript. The
		# write() method handles checking if a graph is large
		# (>self.max_graph_size) and creating a second scaled down version if
		# it is. The scaled down version is then used as the image in the page,
		# and a chunk of JavaScript (defined in W3JavaScriptDocument) uses the
		# full size image in a "zoom box".
		if self.usemap:
			if not self.written:
				self.write()
			# If the graph uses a client side image map for links a bit
			# more work is required. We need to get the graph to generate
			# the <map> doc, then import all elements from that
			# doc into the doc this instance contains...
			map_small = self.map(zoom=False)
			image = tag.img(src=self.url, id=self.url, usemap='#' + map_small.attrib['id'])
			if self.scale is None:
				return [image, map_small]
			else:
				map_zoom = self.map(zoom=True)
				link = tag.p(tag.a('Zoom On/Off', href='#', class_='zoom',
					onclick='javascript:return zoom.toggle("%s", "%s", "#%s");' % (
						self.url,             # thumbnail element id
						self.zoom_url,        # src of full image
						map_zoom.attrib['id'] # full image map element id
					)
				))
				return [link, image, map_small, map_zoom]
		else:
			return super(W3GraphDocument, self).link()

