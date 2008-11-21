# vim: set noet sw=4 ts=4:

"""w3 specific site and document classes.

This module defines subclasses of the classes in the html module which override
certain methods to provide formatting specific to the w3 style [1].

[1] http://w3.ibm.com/standards/intranet/homepage/v8/index.html
"""

import pdb
import os
import logging
from collections import deque
from db2makedoc.graph import Graph, Node, Edge, Cluster
from db2makedoc.etree import ProcessingInstruction, iselement, flatten_html
from db2makedoc.db import (
	DatabaseObject, Database, Schema, Relation,
	Table, View, Alias, Trigger
)
from db2makedoc.plugins.html.document import (
	HTMLElementFactory, ObjectGraph, WebSite, HTMLDocument, HTMLPopupDocument,
	HTMLObjectDocument, HTMLSiteIndexDocument, HTMLExternalDocument,
	StyleDocument, ScriptDocument, GraphDocument, GraphObjectDocument
)
from db2makedoc.plugins.html.database import DatabaseDocument
from db2makedoc.plugins.html.schema import SchemaDocument, SchemaGraph
from db2makedoc.plugins.html.table import TableDocument, TableGraph
from db2makedoc.plugins.html.view import ViewDocument, ViewGraph
from db2makedoc.plugins.html.alias import AliasDocument, AliasGraph
from db2makedoc.plugins.html.uniquekey import UniqueKeyDocument
from db2makedoc.plugins.html.foreignkey import ForeignKeyDocument
from db2makedoc.plugins.html.check import CheckDocument
from db2makedoc.plugins.html.index import IndexDocument
from db2makedoc.plugins.html.trigger import TriggerDocument
from db2makedoc.plugins.html.function import FunctionDocument
from db2makedoc.plugins.html.procedure import ProcedureDocument
from db2makedoc.plugins.html.tablespace import TablespaceDocument

# Import the imaging library
try:
	from PIL import Image
except ImportError:
	# Ignore any import errors - the main plugin takes care of warning the
	# user if PIL is required but not present
	pass

mod_path = os.path.dirname(os.path.abspath(__file__))


class W3ElementFactory(HTMLElementFactory):
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
				script = self.script("""
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
				))
				return (table, script)
		return table


class W3Graph(ObjectGraph):
	def style(self, item):
		super(W3Graph, self).style(item)
		# Set the graph to use the same default font as the stylesheet
		# XXX Any way to set a fallback here like in CSS?
		if isinstance(item, (Node, Edge)):
			item.fontname = 'Verdana'
			item.fontsize = 8.0
		elif isinstance(item, Cluster):
			item.fontname = 'Verdana'
			item.fontsize = 10.0
		# Set shapes and color schemes on objects that represent database
		# objects
		if hasattr(item, 'dbobject'):
			if isinstance(item.dbobject, Schema):
				item.style = 'filled'
				item.fillcolor = '#dddddd'
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
			elif isinstance(item.dbobject, Trigger):
				item.shape = 'hexagon'
				item.style = 'filled'
				item.fillcolor = '#ffbbbb'
		# Outline the selected object more clearly
		if isinstance(item, (Cluster, Node)) and hasattr(item, 'selected'):
			item.color = ['#000000', '#0055aa'][item.selected]


class W3Site(WebSite):
	def get_options(self, options):
		super(W3Site, self).get_options(options)
		self.breadcrumbs = options['breadcrumbs']
		self.confidential = options['confidential']
		self.last_updated = options['last_updated']
		self.max_graph_size = options['max_graph_size']
		self.feedback_url = options['feedback_url']
		self.menu_items = options['menu_items']
		self.related_items = options['related_items']
		self.object_menus = {}
		self.menu = None

	def get_factories(self):
		self.tag_class = W3ElementFactory
		self.popup_class = W3Popup
		self.graph_class = W3Graph

	def create_documents(self, phase=0):
		result = super(W3Site, self).create_documents(phase)
		if phase == 0:
			self.w3_style = W3Style(self)
			if self.search:
				W3Search(self)
			return True
		else:
			return result


class W3External(HTMLExternalDocument):
	pass


class W3Document(HTMLDocument):
	def generate_head(self):
		head = super(W3Document, self).generate_head()
		tag = self.tag
		# Remove the thickbox script and styles - they interfere with w3v8
		# styles, and we're using traditional w3v8 scripts for our popups
		# anyway
		del head[-2:]
		# Add stylesheets and scripts specific to the w3v8 style
		head.append(tag.meta(name='IBM.Country', content=self.site.sublang)) # XXX Add a country config item?
		head.append(tag.meta(name='IBM.Effective', content=self.site.date, scheme='iso8601'))
		head.append(tag.script(src='//w3.ibm.com/ui/v8/scripts/scripts.js'))
		head.append(tag.style(src='//w3.ibm.com/ui/v8/css/v4-screen.css'))
		return head

	def generate_body(self):
		body = super(W3Document, self).generate_body()
		# Tag the body as a w3 document
		body.attrib['id'] = 'w3-ibm-com'
		return body


class W3Popup(W3Document):
	def __init__(self, site, url, title, body, width=400, height=300):
		super(W3Popup, self).__init__(site, url)
		self.search = False
		self.title = title
		self.body = body
		self.width = int(width)
		self.height = int(height)

	def generate_head(self):
		head = super(W3Popup, self).generate_head()
		tag = self.tag
		# Add styles specific to w3v8 popup documents
		head.append(tag.style(src='//w3.ibm.com/ui/v8/css/v4-interior.css'))
		head.append(tag.style("""
			@import url("//w3.ibm.com/ui/v8/css/screen.css");
			@import url("//w3.ibm.com/ui/v8/css/interior.css");
			@import url("//w3.ibm.com/ui/v8/css/popup-window.css");
		""", media='all'))
		head.append(tag.style(src='//w3.ibm.com/ui/v8/css/print.css', media='print'))
		head.append(self.site.w3_style.link())
		return head

	def generate_body(self):
		body = super(W3Popup, self).generate_body()
		tag = self.tag
		# Generate the popup content
		body.append(
			tag.div(
				tag.img(src='//w3.ibm.com/ui/v8/images/id-w3-sitemark-small.gif', width=182, height=26,
					alt='', id='popup-w3-sitemark'),
				id='popup-masthead'
			)
		)
		body.append(
			tag.div(
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
			)
		)
		return body

	def link(self):
		# Modify the link to use the w3v8 JavaScript popup() routine
		return self.tag.a(self.title, href=self.url, title=self.title,
			onclick='javascript:popup("%s","internal",%d,%d);return false;' % (self.url, self.height, self.width))


class W3Article(W3Document):
	def generate(self):
		html = super(W3Article, self).generate()
		head = html.find('head')
		body = html.find('body')
		tag = self.tag
		return tag.html(
			head,
			tag.body(
				tag.div(tag.a('Skip to main content', href='#content-main', accesskey='2'), class_='skip'),
				tag.div(tag.a('Skip to navigation', href='#left-nav', accesskey='n'), class_='skip'),
				tag.div(
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
				),
				tag.div(
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
						tag.a(' Feedback ', id='feedback', href=self.site.feedback_url, accesskey='9'),
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
				),
				tag.div(
					tag.h1('Start of main content', class_='access'),
					tag.div(
						self.generate_header(),
						self.generate_crumbs(),
						id='content-head'
					),
					tag.div(
						tag.h1(self.title),
						self.generate_classification(),
						list(body), # Copy of the original <body> content
						tag.p(
							tag.a('Terms of use', href='http://w3.ibm.com/w3/info_terms_of_use.html'),
							class_='terms'
						),
						id='content-main'
					),
					id='content'
				),
				tag.div(
					tag.h2('Start of left navigation', class_='access'),
					tag.div(
						self.generate_menu(),
						id='left-nav'
					),
					self.generate_related(),
					id='navigation'
				),
				**body.attrib # Copy of the original <body> attributes
			),
			**html.attrib # Copy of the original <html> attributes
		)

	def generate_head(self):
		head = super(W3Article, self).generate_head()
		tag = self.tag
		# Add the w3v8 1-column article styles
		head.append(tag.style("""
			@import url("//w3.ibm.com/ui/v8/css/screen.css");
			@import url("//w3.ibm.com/ui/v8/css/icons.css");
			@import url("//w3.ibm.com/ui/v8/css/tables.css");
			@import url("//w3.ibm.com/ui/v8/css/interior.css");
			@import url("//w3.ibm.com/ui/v8/css/interior-1-col.css");
		""", media='all'))
		head.append(tag.style(src='//w3.ibm.com/ui/v8/css/print.css', media='print'))
		head.append(self.site.w3_style.link())
		return head

	def generate_body(self):
		body = super(W3Article, self).generate_body()
		body.attrib['class'] = 'article'
		return body

	def generate_crumbs(self):
		"""Creates the breadcrumb links above the article body."""
		if self.site.breadcrumbs and self.parent:
			if isinstance(self, W3SiteIndex):
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
			return ''

	def generate_classification(self):
		"""Creates the security classification label, if any."""
		if self.site.confidential:
			return tag.p('IBM Confidential', class_='confidential')
		else:
			return ''

	def generate_related(self):
		"""Creates the related links below the left-hand navigation menu."""
		if self.site.related_items:
			tag = self.tag
			return (
				tag.p('Related links:'),
				tag.ul(tag.li(tag.a(title, href=url)) for (title, url) in self.site.related_items)
			)
		else:
			return ''

	def generate_menu(self):
		"""Creates the left navigation menu links."""

		def link(doc, active=False, visible=True):
			"""Sub-routine which generates a menu link from a document."""
			if isinstance(doc, HTMLObjectDocument) and doc.parent:
				content = doc.dbobject.name
			elif isinstance(doc, HTMLSiteIndexDocument):
				content = doc.letter
			else:
				content = doc.title
			# Non-top-level items longer than 12 characters are truncated
			# and suffixed with a horizontal ellipsis (\u2026)
			if len(content) > 12 and doc.parent:
				content = content[:11] + u'\u2026'
			return self.tag.a(
				content,
				href=doc.url,
				title=doc.title,
				class_=(None, 'active')[active],
				style=('display: none;', None)[visible]
			)

		def more(above):
			"""Sub-routine which generates a "More Items" link."""
			return self.tag.a(
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
			links = self.tag.div(links, class_=['top-level', 'second-level', 'third-level'][doc.level])
			# Recurse up the document hierarchy if there are more levels
			if doc.level:
				return menu(doc.parent, False, links)
			else:
				return links

		return menu(self)

	def generate_header(self):
		"""Creates the header text above the article body."""
		if self.site.last_updated:
			return (
				self.tag.p('Updated on ', self.site.date.strftime('%a, %d %b %Y'), id='date-stamp'),
				self.tag.hr()
			)
		else:
			return ''


class W3ObjectDocument(HTMLObjectDocument, W3Article):
	def flatten(self, content):
		# This overridden implementation returns flattened text from the
		# content-main <div> only, so that things like the links in the left
		# navigation menu don't corrupt the search results
		return flatten_html(self.tag._find(content, 'div', id='content-main'))

	def generate(self):
		doc = super(W3ObjectDocument, self).generate()
		tag = self.tag
		body = doc.find('body')
		# Convert the top Description section into body text with a TOC for
		# other sections, convert all <h3> elements into <h2> elements with a
		# blue bar style (to denote different section types) and add "Back to
		# top" links, all as per w3v8
		sections = [
			elem for elem in body[4][2]
			if elem.tag == 'div'
			and elem.attrib.get('class') == 'section'
			and iselement(elem.find('h3'))
			and 'id' in elem.attrib
		]
		sections[0].remove(sections[0].find('h3'))
		sections[0].append(
			tag.ul(
				tag.li(tag.a(section.find('h3').text, href='#' + section.attrib['id'], title='Jump to section'))
				for section in sections[1:]
			)
		)
		for section in sections[1:]:
			heading = section.find('h3')
			heading.tag = 'h2'
			heading.attrib['class'] = 'bar-blue-med'
			section.append(tag.p(tag.a('Back to top', href='#masthead')))
		return doc


class W3SiteIndex(HTMLSiteIndexDocument, W3Article):
	def generate_body(self):
		body = super(W3SiteIndex, self).generate_body()
		tag = self.tag
		# Generate the JavaScript toggles
		body[0:0] = [
			tag.p(id='expand-collapse-links'),
			tag.script("""
				$(document).ready(function() {
				/* Collapse all definition terms and add a click handler to toggle them */
				$('#index-list')
					.children('dd').hide().end()
					.children('dt').addClass('expand-link-dark').click(function() {
						$(this)
							.toggleClass('expand-link-dark')
							.toggleClass('collapse-link-dark')
							.next().slideToggle();
					});
					/* Add the "expand all" and "collapse all" links */
					$('#expand-collapse-links')
						.append(
							$(document.createElement('a'))
								.attr('href', '#')
								.append('Expand all')
								.click(function() {
									$('#index-list')
										.children('dd').show().end()
										.children('dt').removeClass('expand-link-dark').addClass('collapse-link-dark');
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
										.children('dt').removeClass('collapse-link-dark').addClass('expand-link-dark');
									return false;
								})
						);
				});
			""")
		]
		return body


class W3Search(W3Article):
	"""Document class containing the PHP search script"""

	search_php = open(os.path.join(mod_path, 'search.php'), 'r').read()

	def __init__(self, site):
		super(W3Search, self).__init__(site, 'search.php')
		self.title = 'Search results'
		self.description = self.title
		self.search = False
	
	def _get_parent(self):
		result = super(W3Search, self)._get_parent()
		if not result:
			return self.site.object_document(self.site.database)
		else:
			return result

	def generate_body(self):
		body = super(W3Search, self).generate_body()
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
		# XXX See generate_main()
		php = self.search_php
		php = php.replace('__XAPIAN__', 'xapian.php')
		php = php.replace('__LANG__', self.site.lang)
		php = php.replace('__ENCODING__', self.site.encoding)
		result = super(W3Search, self).serialize(content)
		return result.replace('__PHP__', php)


class W3GraphDocument(GraphObjectDocument):
	def __init__(self, site, dbobject):
		super(W3GraphDocument, self).__init__(site, dbobject)
		self.written = False
		self.scale = None

	def generate(self):
		(maxw, maxh) = self.site.max_graph_size
		graph = super(W3GraphDocument, self).generate()
		graph.ratio = str(float(maxh) / float(maxw))
		return graph
	
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
		result = super(W3GraphDocument, self).map()
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


# Declare classes for all the static documents in the W3 HTML plugin

class W3Script(ScriptDocument):
	def __init__(self, site):
		super(W3Script, self).__init__(site, os.path.join(mod_path, 'scripts.js'))

class W3Style(StyleDocument):
	def __init__(self, site):
		super(W3Style, self).__init__(site, os.path.join(mod_path, 'styles.css'))
	def generate(self):
		# If local search is not enabled, ensure the local search check box is not shown
		result = super(W3Style, self).generate()
		if not self.site.search:
			result += u'\ntd.limiter { display: none; }'
		return result

# Declare styled document and graph classes

class W3DatabaseDocument(W3ObjectDocument, DatabaseDocument):
	pass

class W3SchemaDocument(W3ObjectDocument, SchemaDocument):
	pass

class W3TableDocument(W3ObjectDocument, TableDocument):
	pass

class W3ViewDocument(W3ObjectDocument, ViewDocument):
	pass

class W3AliasDocument(W3ObjectDocument, AliasDocument):
	pass

class W3UniqueKeyDocument(W3ObjectDocument, UniqueKeyDocument):
	pass

class W3ForeignKeyDocument(W3ObjectDocument, ForeignKeyDocument):
	pass

class W3CheckDocument(W3ObjectDocument, CheckDocument):
	pass

class W3IndexDocument(W3ObjectDocument, IndexDocument):
	pass

class W3TriggerDocument(W3ObjectDocument, TriggerDocument):
	pass

class W3FunctionDocument(W3ObjectDocument, FunctionDocument):
	pass

class W3ProcedureDocument(W3ObjectDocument, ProcedureDocument):
	pass

class W3TablespaceDocument(W3ObjectDocument, TablespaceDocument):
	pass

class W3SchemaGraph(SchemaGraph, W3GraphDocument):
	pass

class W3TableGraph(TableGraph, W3GraphDocument):
	pass

class W3ViewGraph(ViewGraph, W3GraphDocument):
	pass

class W3AliasGraph(AliasGraph, W3GraphDocument):
	pass
