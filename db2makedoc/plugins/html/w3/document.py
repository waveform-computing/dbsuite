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
from db2makedoc.graph import Graph, Node, Edge, Cluster
from db2makedoc.etree import ProcessingInstruction, fromstring, flatten_html
from db2makedoc.db import (
	DatabaseObject, Database, Schema, Relation,
	Table, View, Alias, Trigger
)
from db2makedoc.plugins.html.document import (
	Attrs, ElementFactory, WebSite, HTMLDocument, HTMLObjectDocument,
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
		# 'blue-dark' CSS class to them
		try:
			thead = self._find(table, 'thead')
		except:
			pass
		else:
			for tr in thead.findall('tr'):
				self._add_class(tr, 'blue-dark')
		try:
			tfoot = self._find(table, 'tfoot')
		except:
			pass
		else:
			for tr in tfoot.findall('tr'):
				self._add_class(tr, 'blue-dark')
		# If there's a tbody element, apply 'even' and 'odd' CSS classes to
		# rows in the body, and add 'basic-table' to the table's CSS classes.
		# We don't do this for tables without an explicit tbody as they are
		# very likely to be pure layout tables (e.g. the search table in the
		# masthead)
		try:
			tbody = self._find(table, 'tbody')
		except:
			pass
		else:
			for index, tr in enumerate(tbody.findall('tr')):
				self._add_class(tr, ['odd', 'even'][index % 2])
			self._add_class(table, 'basic-table')
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
						# XXX Should be conditional on self.site.search
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
				links.insert(0, ' > ')
				links.insert(0, doc.link())
				doc = doc.parent
			return tag.p(links, id='breadcrumbs')
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
			if isinstance(doc, HTMLObjectDocument) and doc.level > 0:
				content = doc.dbobject.name
			elif isinstance(doc, HTMLIndexDocument):
				content = doc.letter
			else:
				content = doc.title
			# Non-top-level items longer than 12 characters are truncated
			# and suffixed with a horizontal ellipsis (\u2026)
			return tag.a(
				[content, content[:11] + u'\u2026'][bool(len(content) > 12 and doc.parent)],
				href=doc.url,
				title=doc.title,
				class_=[None, 'active'][active],
				style=['display: none;', None][visible]
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
			links = [link(doc, active=active), children]
			count = 10
			pdoc = doc.prior
			ndoc = doc.next
			more_above = more_below = False
			while pdoc or ndoc:
				if pdoc:
					more_above = count <= 0 and doc.level > 0
					links.insert(0, link(pdoc, visible=not more_above))
					pdoc = pdoc.prior
					count -= 1
				if ndoc:
					more_below = count <= 0 and doc.level > 0
					links.append(link(ndoc, visible=not more_below))
					ndoc = ndoc.next
					count -= 1
			# Insert "More Items" links if necessary
			if more_above:
				links.insert(0, more(True))
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
		items = sorted(self.items, key=lambda item: '%s %s' % (item.name, item.qualified_name))
		index = tag.dl(
			(
				tag.dt(item.name, ' (', self.site.type_names[item.__class__], ' ', self.site.link_to(item, parent=True), ')'),
				tag.dd(self.format_comment(item.description, summary=True))
			)
			for item in items
		)
		return (
			links,
			tag.hr(),
			index
		)


class W3SearchDocument(W3ArticleDocument):
	"""Document class containing the PHP search script"""

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
		php = r"""
require '__XAPIAN__';

# Defaults and limits
$PAGE_DEFAULT = 1;
$PAGE_MIN = 1;
$PAGE_MAX = 0; # Calculated by run_query()
$COUNT_DEFAULT = 10;
$COUNT_MIN = 10;
$COUNT_MAX = 100;

# Globals derived from GET values
$Q = array_key_exists('q', $_GET) ? strval($_GET['q']) : '';
$REFINE = array_key_exists('refine', $_GET) ? intval($_GET['refine']) : 0;
$PAGE = array_key_exists('page', $_GET) ? intval($_GET['page']) : $PAGE_DEFAULT;
$PAGE = max($PAGE_MIN, $PAGE);
$COUNT = array_key_exists('count', $_GET) ? intval($_GET['count']) : $COUNT_DEFAULT;
$COUNT = max($COUNT_MIN, min($COUNT_MAX, $COUNT));

# Extract additional queries when refine is set
$QUERIES[] = $Q;
if ($REFINE) {
	$i = 0;
	while (array_key_exists('q' . strval($i), $_GET)) {
		$QUERIES[] = strval($_GET['q' . strval($i)]);
		$i++;
	}
}

function run_query() {
	global $QUERIES, $PAGE, $COUNT, $PAGE_MAX;

	$db = new XapianDatabase('search');
	$enquire = new XapianEnquire($db);
	$parser = new XapianQueryParser();
	$parser->set_stemmer(new XapianStem('__LANG__'));
	$parser->set_stemming_strategy(XapianQueryParser::STEM_SOME);
	$parser->set_database($db);
	$query = NULL;
	foreach ($QUERIES as $q) {
		$left = $parser->parse_query($q,
			XapianQueryParser::FLAG_BOOLEAN_ANY_CASE |  # Enable boolean operators (with any case)
			XapianQueryParser::FLAG_PHRASE |            # Enable quoted phrases
			XapianQueryParser::FLAG_LOVEHATE |          # Enable + and -
			XapianQueryParser::FLAG_SPELLING_CORRECTION # Enable suggested corrections
		);
		if ($query)
			$query = new XapianQuery(XapianQuery::OP_AND, $left, $query);
		else
			$query = $left;
	}
	$enquire->set_query($query);
	$result = $enquire->get_mset((($PAGE - 1) * $COUNT) + 1, $COUNT);
	$PAGE_MAX = ceil($result->get_matches_estimated() / floatval($COUNT));
	return $result;
}

function limit_search($doc) {
	global $Q, $QUERIES, $COUNT, $REFINE;

	# Generate the first row
	$tr1 = $doc->createElement('tr');
	$td = $doc->createElement('td');
	$td->appendChild(new DOMAttr('class', 'col1'));
	$td->appendChild(new DOMText('Search for'));
	$tr1->appendChild($td);
	$input = $doc->createElement('input');
	$input->appendChild(new DOMAttr('type', 'text'));
	$input->appendChild(new DOMAttr('name', 'q'));
	$input->appendChild(new DOMAttr('value', $Q));
	$td = $doc->createElement('td');
	$td->appendChild(new DOMAttr('class', 'col2'));
	$td->appendChild($input);
	$td->appendChild(new DOMText(' '));
	$input = $doc->createElement('input');
	$input->appendChild(new DOMAttr('type', 'submit'));
	$input->appendChild(new DOMAttr('value', 'Go'));
	$span = $doc->createElement('span');
	$span->appendChild(new DOMAttr('class', 'button-blue'));
	$span->appendChild($input);
	$td->appendChild($span);
	$td->appendChild(new DOMText(' '));
	$a = $doc->createElement('a');
	$a->appendChild(new DOMAttr('href', 'search.html'));
	$a->appendChild(new DOMAttr('onclick', 'javascript:popup("search.html","internal",300,400);return false;'));
	$a->appendChild(new DOMText('Help'));
	$td->appendChild($a);
	$tr1->appendChild($td);
	# Generate the second row
	$tr2 = $doc->createElement('tr');
	$td = $doc->createElement('td');
	$td->appendChild(new DOMAttr('class', 'col1'));
	$td->appendChild(new DOMText(' '));
	$tr2->appendChild($td);
	$input = $doc->createElement('input');
	$input->appendChild(new DOMAttr('type', 'checkbox'));
	$input->appendChild(new DOMAttr('name', 'refine'));
	$input->appendChild(new DOMAttr('value', '1'));
	if ($REFINE) $input->appendChild(new DOMAttr('checked', 'checked'));
	$label = $doc->createElement('label');
	$label->appendChild($input);
	$label->appendChild(new DOMText(' Search within results'));
	$td = $doc->createElement('td');
	$td->appendChild(new DOMAttr('class', 'col2'));
	$td->appendChild($label);
	$tr2->appendChild($td);
	# Stick it all in a table in a form
	$tbody = $doc->createElement('tbody');
	$tbody->appendChild($tr1);
	$tbody->appendChild($tr2);
	$table = $doc->createElement('table');
	$table->appendChild(new DOMAttr('class', 'limit-search'));
	$table->appendChild($tbody);
	$count = $doc->createElement('input');
	$count->appendChild(new DOMAttr('type', 'hidden'));
	$count->appendChild(new DOMAttr('name', 'count'));
	$count->appendChild(new DOMAttr('value', strval($COUNT)));
	$form = $doc->createElement('form');
	$form->appendChild(new DOMAttr('method', 'GET'));
	$form->appendChild($count);
	foreach ($QUERIES as $i => $q) {
		$query = $doc->createElement('input');
		$query->appendChild(new DOMAttr('type', 'hidden'));
		$query->appendChild(new DOMAttr('name', 'q' . strval($i)));
		$query->appendChild(new DOMAttr('value', $q));
		$form->appendChild($query);
	}
	$form->appendChild($table);
	return $form;
}

function results_count($doc, $matches) {
	global $Q, $PAGE, $COUNT;

	$found = $matches->get_matches_estimated();
	$page_from = (($PAGE - 1) * $COUNT) + 1;
	$page_to = $page_from + $matches->size() - 1;

	$td = $doc->createElement('td');
	$td->appendChild(new DOMAttr('class', 'results-count'));
	$strong = $doc->createElement('strong');
	$strong->appendChild(new DOMText(strval($found)));
	$td->appendChild($strong);
	$td->appendChild(new DOMText(' results found'));
	$td->appendChild($doc->createElement('br'));
	$td->appendChild(new DOMText('Results '));
	$strong = $doc->createElement('strong');
	$strong->appendChild(new DOMText(strval($page_from)));
	$td->appendChild($strong);
	$td->appendChild(new DOMText(' to '));
	$strong = $doc->createElement('strong');
	$strong->appendChild(new DOMText(strval($page_to)));
	$td->appendChild($strong);
	$td->appendChild(new DOMText(' shown by relevance'));
	return $td;
}

function results_page($doc, $page, $label='') {
	global $Q, $PAGE, $PAGE_MIN, $PAGE_MAX, $COUNT;

	if ($label == '') $label = strval($page);
	if (($page < $PAGE_MIN) || ($page > $PAGE_MAX)) {
		return $doc->createTextNode($label);
	}
	elseif ($page == $PAGE) {
		$strong = $doc->createElement('strong');
		$strong->appendChild(new DOMText($label));
		return $strong;
	}
	else {
		$url = sprintf('?q=%s&page=%d&count=%d', $Q, $page, $COUNT);
		if ($REFINE) {
			$url .= '&refine=1';
			foreach (array_slice($QUERIES, 1) as $i => $q)
				$url .= sprintf('&q%d=%s', $i, $q);
		}
		$a = $doc->createElement('a');
		$a->appendChild(new DOMAttr('href', $url));
		$a->appendChild(new DOMText($label));
		return $a;
	}
}

function results_sequence($doc) {
	global $PAGE, $PAGE_MIN, $PAGE_MAX;

	$from = max($PAGE_MIN + 1, $PAGE - 5);
	$to = min($PAGE_MAX - 1, $from + 8);

	$td = $doc->createElement('td');
	$td->appendChild(new DOMAttr('class', 'results-sequence'));
	$td->appendChild(results_page($doc, $PAGE - 1, '< Previous'));
	$td->appendChild(new DOMText(' | '));
	$td->appendChild(results_page($doc, $PAGE_MIN));
	if ($from > $PAGE_MIN + 1) $td->appendChild(new DOMText(' ...'));
	$td->appendChild(new DOMText(' '));
	for ($i = $from; $i <= $to; ++$i) {
		$td->appendChild(results_page($doc, $i));
		$td->appendChild(new DOMText(' '));
	}
	if ($to < $PAGE_MAX - 1) $td->appendChild(new DOMText('... '));
	$td->appendChild(results_page($doc, $PAGE_MAX));
	$td->appendChild(new DOMText(' | '));
	$td->appendChild(results_page($doc, $PAGE + 1, 'Next >'));
	return $td;
}

function results_header($doc, $matches, $header=True) {
	global $Q, $QUERIES;

	$strong = $doc->createElement('strong');
	$strong->appendChild(new DOMText($Q));
	foreach (array_slice($QUERIES, 1) as $q)
		$strong->appendChild(new DOMText(sprintf(' AND %s', $q)));
	$td = $doc->createElement('td');
	$td->appendChild(new DOMAttr('colspan', '2'));
	$td->appendChild(new DOMText('Results for : '));
	$td->appendChild($strong);
	$tr = $doc->createElement('tr');
	$tr->appendChild($td);
	$tbody = $doc->createElement('tbody');
	$tbody->appendChild($tr);
	$tr = $doc->createElement('tr');
	$tr->appendChild(new DOMAttr('class', 'summary-options'));
	$tr->appendChild(results_count($doc, $matches));
	$tr->appendChild(results_sequence($doc));
	$tbody->appendChild($tr);
	$table = $doc->createElement('table');
	if ($header)
		$table->appendChild(new DOMAttr('class', 'results-header'));
	else
		$table->appendChild(new DOMAttr('class', 'results-footer'));
	$table->appendChild($tbody);
	return $table;
}

function results_table($doc, $matches) {
	$table = $doc->createElement('table');
	$table->appendChild(new DOMAttr('class', 'basic-table search-results'));
	$thead = $doc->createElement('thead');
	$table->appendChild($thead);
	# Generate the header row
	$tr = $doc->createElement('tr');
	$tr->appendChild(new DOMAttr('class', 'blue-dark'));
	foreach (array('Document', 'Relevance') as $content) {
		$th = $doc->createElement('th');
		$th->appendChild(new DOMText($content));
		$tr->appendChild($th);
	}
	$thead->appendChild($tr);
	$tbody = $doc->createElement('tbody');
	$table->appendChild($tbody);
	# Generate the result rows
	$match = $matches->begin();
	while (! $match->equals($matches->end())) {
		list($url, $title, $desc) = explode("\n",
			$match->get_document()->get_data(), 3);
		$relevance = $match->get_percent();
		# Generate the link & relevance row
		$a = $doc->createElement('a');
		$a->appendChild(new DOMAttr('href', $url));
		$a->appendChild(new DOMText($title));
		$td1 = $doc->createElement('td');
		$td1->appendChild($a);
		$td2 = $doc->createElement('td');
		$td2->appendChild(new DOMAttr('class', 'relevance'));
		$td2->appendChild(new DOMText(sprintf('%d%%', $relevance)));
		$tr = $doc->createElement('tr');
		$tr->appendChild(new DOMAttr('class', 'result row1'));
		$tr->appendChild($td1);
		$tr->appendChild($td2);
		$tbody->appendChild($tr);
		# Generate the description row
		$div = $doc->createElement('div');
		$div->appendChild(new DOMAttr('class', 'url'));
		$div->appendChild(new DOMText($url));
		$hr = $doc->createElement('div');
		$hr->appendChild(new DOMAttr('class', 'hrule-dots'));
		$td = $doc->createElement('td');
		$td->appendChild(new DOMAttr('colspan', '2'));
		$td->appendChild(new DOMText($desc));
		$td->appendChild($doc->createElement('br'));
		$td->appendChild($div);
		$td->appendChild($hr);
		$tr = $doc->createElement('tr');
		$tr->appendChild(new DOMAttr('class', 'result row2'));
		$tr->appendChild($td);
		$tbody->appendChild($tr);
		# Next!
		$match->next();
	}
	return $table;
}

$doc = new DOMDocument('1.0', '__ENCODING__');
$matches = run_query();

print($doc->saveXML(limit_search($doc)));
print($doc->saveXML(results_header($doc, $matches, True)));
print($doc->saveXML(results_table($doc, $matches)));
print($doc->saveXML(results_header($doc, $matches, False)));
print($doc->saveXML(limit_search($doc)));
"""
		php = php.replace('__XAPIAN__', 'xapian.php')
		php = php.replace('__LANG__', self.site.lang)
		php = php.replace('__ENCODING__', self.site.encoding)
		result = super(W3SearchDocument, self).serialize(content)
		return result.replace('__PHP__', php)


class W3CSSDocument(CSSDocument):
	"""Stylesheet class to supplement the w3v8 style with SQL syntax highlighting."""

	def __init__(self, site):
		super(W3CSSDocument, self).__init__(site, 'styles.css')

	def generate(self):
		# We only need one supplemental CSS stylesheet (the default w3v8 styles
		# are reasonably comprehensive). So this method is brutally simple...
		doc = super(W3CSSDocument, self).generate()
		return doc + u"""
/* Override some w3 styles for SQL syntax highlighting */
ol.sql li {
	line-height: 1em;
	margin-top: 0;
	margin-bottom: 0;
}

/* Styles for search results (the w3v8 search.css is unusable) */
.limit-search {
	background-color: #eee;
	border-bottom: 1px solid #ccc;
	margin: 1em 0;
	padding: 1em 3em;
	width: 100%;
}
.limit-search td { vertical-align: middle; }
.limit-search td.col1 {
	font-weight: bold;
	text-align: right;
	padding: 0 .5em 0 0;
}
.limit-search td.col2 { }
.limit-search input[type="text"] { width: 280px; }

.results-header,
.results-footer {
	border-collapse: collapse;
	width: 100%;
}
.results-header { border-bottom: 1px solid #ccc; margin-bottom: 1em; }
.results-footer { border-top: 1px solid #ccc; margin-top: 1em; }
.results-header td,
.results-footer td { padding: .4em 0; vertical-align: bottom; }
tr.summary-options { background: url(//w3.ibm.com/ui/v8/images/rule-h-blue-dots.gif) left top repeat-x; }
tr.summary-options td.results-count { text-align: left; width: 33%; }
tr.summary-options td.options { text-align: center; }
tr.summary-options td.results-sequence { text-align: right; }

.search-results { width: 100%; }
.search-results tr.result a { display: block; font-weight: bold; }
.search-results tr.result.row1 td { padding: 0.5em 0 0 0; }
.search-results tr.result.row2 td { padding: 0; }

.search-results tr.result .relevance {
	font-weight: bold;
	text-align: right;
}
.search-results tr.result .url {
	font-size: small;
	font-style: italic;
	color: #999;
}

/* Styles for draggable zoom box */
div.zoom {
	border: 2px solid black;
	padding: 0;
	margin: 0;
	background-color: #dd0;
	overflow: hidden;
	position: absolute;
	width: 250px;
	height: 250px;
}

div.zoom img {
	position: absolute;
	top: 0;
	left: 0;
	z-index: 1;
}

div.zoom div {
	cursor: move;
	background: navy;
	color: white;
	font-weight: bold;
	padding: 0;
	margin: 0;
	text-align: center;
	position: absolute;
	width: 250px;
	height: 1.5em;
	top: 0;
	left: 0;
	z-index: 2;
}

div.zoom :link,
div.zoom :visited {
	color: white;
	text-decoration: underline;
	padding: 0 0.5em;
	margin: 0;
	text-align: center;
	display: block;
	position: absolute;
	width: auto;
	height: 1.5em;
	top: 0;
	right: 0;
	z-index: 3;
}

:link.zoom,
:visited.zoom {
	padding: 0.5em;
	background: navy;
	color: white;
	text-decoration: underline;
}

/* Fix display of border around diagrams in Firefox */
#content-main img { border: 0 none; }
"""


class W3JavaScriptDocument(JavaScriptDocument):
	"""Code class to supplement the w3v8 style with some simple routines."""

	def __init__(self, site):
		super(W3JavaScriptDocument, self).__init__(site, 'scripts.js')

	def generate(self):
		doc = super(W3JavaScriptDocument, self).generate()
		return doc + u"""
// IE doesn't have a clue (no Node built-in) so we'll define one just for it...
var ELEMENT_NODE = 1;

// Replace the "More items..." link (e) with the items it's hiding
function showItems(e) {
	var n;
	n = e;
	while (n = n.previousSibling)
		if ((n.nodeType == ELEMENT_NODE) && (n.tagName.toLowerCase() == 'a'))
			if (n.style.display == 'none')
				n.style.display = 'block'
			else
				break;
	n = e;
	while (n = n.nextSibling)
		if ((n.nodeType == ELEMENT_NODE) && (n.tagName.toLowerCase() == 'a'))
			if (n.style.display == 'none')
				n.style.display = 'block'
			else
				break;
	e.style.display = 'none';
	return false;
}

// Toggles the line numbers in a syntax highlighted SQL block
function toggleLineNums(e) {
	if (typeof e == 'string')
		e = document.getElementById(e);
	if (e.className.match(/ *hidenum/))
		e.className = e.className.replace(/ *hidenum/, '')
	else
		e.className += ' hidenum';
	return false;
}

var W3_SEARCH = 'http://w3.ibm.com/search/do/search';
var DOC_SEARCH = 'search.php';

// Toggles the target of the masthead search box
function toggleSearch() {
	var searchForm = document.getElementById("search");
	var searchField = document.getElementById("header-search-field");
	if (searchForm.action == W3_SEARCH) {
		searchForm.action = DOC_SEARCH;
		searchField.name = "q";
	}
	else {
		searchForm.action = W3_SEARCH;
		searchField.name = "qt";
	}
}

// Adds a handler to an event
function addEvent(obj, evt, fn) {
	if (obj.addEventListener)
		obj.addEventListener(evt, fn, false);
	else if (obj.attachEvent)
		obj.attachEvent('on' + evt, fn);
}

// Removes a handler from an event
function removeEvent(obj, evt, fn) {
	if (obj.removeEventListener)
		obj.removeEventListener(evt, fn, false);
	else if (obj.detachEvent)
		obj.detachEvent('on' + evt, fn);
}

// Simple class for storing 2D position. Either specify the X and Y coordinates
// to the constructor, or specify an element (or an element ID), or another
// Position object as the only parameter in which case the element's offset
// will be used
function Position(x, y) {
	if (x === undefined) {
		throw Error('must specify two coordinates or an object for Position');
	}
	else if (y === undefined) {
		var obj = x;
		if (typeof obj == 'string')
			obj = document.getElementById(obj);
		if (typeof obj == 'object') {
			if ((typeof obj.x == 'number') && (typeof obj.y == 'number')) {
				this.x = obj.x;
				this.y = obj.y;
			}
			else {
				this.x = this.y = 0;
				do {
					this.x += obj.offsetLeft;
					this.y += obj.offsetTop
				} while (obj = obj.offsetParent);
			}
		}
		else {
			throw Error('invalid object type for Position');
		}
	}
	else {
		this.x = x;
		this.y = y;
	}
}

// Global zoom object. Implements properties and methods used to control
// draggable zoom boxes over a reduced size image. This code is a modified
// version of PPK's excellent "Drag and drop" script. The original can be
// found at: http://www.quirksmode.org/js/dragdrop.html
zoom = {
	// Configuration variables
	keySpeed: 10, // pixels per keypress event
	defaultTitle: 'Zoom', // title bar of normal zoom box
	mouseTitle: undefined, // title bar of zoom box during mouse drag
	keyTitle: 'Keys: \\u2191\\u2193\\u2190\\u2192 \\u21B5', // title bar of zoom box during keypress drag
	keyLink: 'Keys', // title of the key link

	// Internal variables - do not alter
	startMouse: undefined,
	startElem: undefined,
	min: undefined,
	max: undefined,
	ratioX: undefined,
	ratioY: undefined,
	dXKeys: undefined,
	dYKeys: undefined,
	box: undefined,

	toggle: function (thumb, src, map) {
		if (typeof thumb == 'string')
			thumb = document.getElementById(thumb);
		if (thumb._zoom)
			zoom.done(thumb)
		else
			zoom.init(thumb, src, map);
		return false;
	},

	init: function (thumb, src, map) {
		if (typeof thumb == 'string')
			thumb = document.getElementById(thumb);
		// Create the zoom box
		var box = document.createElement('div');
		var image = document.createElement('img');
		var link = document.createElement('a');
		var title = document.createElement('div');
		image._box = box;
		image.src = src;
		if (map) image.useMap = map;
		link._box = box;
		link.appendChild(document.createTextNode(zoom.keyLink));
		link.href = '#';
		title._box = box;
		title.appendChild(document.createTextNode(zoom.defaultTitle));
		box._thumb = thumb;
		box._title = title;
		box._link = link;
		box._image = image;
		box.className = 'zoom';
		var startPos = new Position(thumb);
		box.style.left = startPos.x + 'px';
		box.style.top = startPos.y + 'px';
		// Place the elements into the document tree
		box.appendChild(title);
		box.appendChild(link);
		box.appendChild(image);
		document.body.appendChild(box);
		thumb._zoom = box;
		// Attach the drag event handlers
		link.onclick = zoom.startDragKeys;
		title.onmousedown = zoom.startDragMouse;
		// Return the top-level <div> in case the caller wants to customize
		// the content
		return box;
	},

	done: function(thumb) {
		if (zoom.box) zoom.endDrag();
		if (typeof thumb == 'string')
			thumb = document.getElementById(thumb);
		// Break all the reference cycles we've setup just in case the JS
		// implementation has shite gc
		var box = thumb._zoom;
		box._image._box = undefined;
		box._image = undefined;
		box._link._box = undefined;
		box._link = undefined;
		box._title = undefined;
		box._thumb = undefined;
		thumb._zoom = undefined;
		// Remove the generated box
		document.body.removeChild(box);
		return false;
	},

	startDragMouse: function (e) {
		if (zoom.mouseTitle !== undefined)
			this._box._title.lastChild.data = zoom.mouseTitle;
		zoom.startDrag(this._box);
		if (!e) var e = window.event;
		zoom.startMouse = new Position(e.clientX, e.clientY);
		addEvent(document, 'mousemove', zoom.dragMouse);
		addEvent(document, 'mouseup', zoom.endDrag);
		return false;
	},

	startDragKeys: function () {
		if (zoom.keyTitle !== undefined)
			this._box._title.lastChild.data = zoom.keyTitle;
		this._box._link.style.display = 'none';
		zoom.startDrag(this._box);
		zoom.dXKeys = zoom.dYKeys = 0;
		addEvent(document, 'keydown', zoom.dragKeys);
		addEvent(document, 'keypress', zoom.switchKeyEvents);
		this.blur();
		return false;
	},

	switchKeyEvents: function () {
		// for Opera and Safari 1.3
		removeEvent(document, 'keydown', zoom.dragKeys);
		removeEvent(document, 'keypress', zoom.switchKeyEvents);
		addEvent(document, 'keypress', zoom.dragKeys);
	},

	startDrag: function (obj) {
		if (zoom.box) zoom.endDrag();
		var thumbW = obj._thumb.offsetWidth - obj.offsetWidth;
		var thumbH = obj._thumb.offsetHeight - obj.offsetHeight;
		var imageW = obj._image.offsetWidth - obj.offsetWidth;
		var imageH = obj._image.offsetHeight - obj.offsetHeight;
		zoom.startElem = new Position(obj);
		zoom.min = new Position(obj._thumb);
		zoom.max = new Position(zoom.min);
		zoom.max.x += thumbW;
		zoom.max.y += thumbH;
		zoom.ratioX = imageW / thumbW;
		zoom.ratioY = imageH / thumbH;
		zoom.box = obj;
		obj.className += ' dragged';
	},

	endDrag: function() {
		removeEvent(document, 'mousemove', zoom.dragMouse);
		removeEvent(document, 'mouseup', zoom.endDrag);
		removeEvent(document, 'keypress', zoom.dragKeys);
		removeEvent(document, 'keypress', zoom.switchKeyEvents);
		removeEvent(document, 'keydown', zoom.dragKeys);
		zoom.box.className = zoom.box.className.replace(/ *dragged/, '');
		zoom.box._link.style.display = 'block';
		zoom.box._title.lastChild.data = zoom.defaultTitle;
		zoom.saveTitle = undefined;
		zoom.startMouse = undefined;
		zoom.startElem = undefined;
		zoom.min = undefined;
		zoom.max = undefined;
		zoom.ratioX = undefined;
		zoom.ratioY = undefined;
		zoom.box = undefined;
	},

	dragMouse: function (e) {
		if (!e) var e = window.event;
		var dX = e.clientX - zoom.startMouse.x;
		var dY = e.clientY - zoom.startMouse.y;
		zoom.setPosition(dX, dY);
		return false;
	},

	dragKeys: function(e) {
		if (!e) var e = window.event;
		switch (e.keyCode) {
			case 37:	// left
			case 63234:
				if (zoom.startElem.x + zoom.dXKeys > zoom.min.x)
					zoom.dXKeys -= zoom.keySpeed;
				break;
			case 38:	// up
			case 63232:
				if (zoom.startElem.y + zoom.dYKeys > zoom.min.y)
					zoom.dYKeys -= zoom.keySpeed;
				break;
			case 39:	// right
			case 63235:
				if (zoom.startElem.x + zoom.dXKeys < zoom.max.x)
					zoom.dXKeys += zoom.keySpeed;
				break;
			case 40:	// down
			case 63233:
				if (zoom.startElem.y + zoom.dYKeys < zoom.max.y)
					zoom.dYKeys += zoom.keySpeed;
				break;
			case 13:	// enter
			case 27:	// escape
				zoom.endDrag();
				return false;
			default:
				return true;
		}
		zoom.setPosition(zoom.dXKeys, zoom.dYKeys);
		if (e.preventDefault) e.preventDefault();
		return false;
	},

	setPosition: function (dx, dy) {
		var newBoxPos = new Position(
			Math.min(Math.max(zoom.startElem.x + dx, zoom.min.x), zoom.max.x),
			Math.min(Math.max(zoom.startElem.y + dy, zoom.min.y), zoom.max.y)
		);
		var newImagePos = new Position(
			(newBoxPos.x - zoom.min.x) * zoom.ratioX,
			(newBoxPos.y - zoom.min.y) * zoom.ratioY
		);
		zoom.box.style.left = newBoxPos.x + 'px';
		zoom.box.style.top = newBoxPos.y + 'px';
		zoom.box._image.style.left = -newImagePos.x + 'px';
		zoom.box._image.style.top = -newImagePos.y + 'px';
	}
}
"""


class W3GraphDocument(GraphObjectDocument):
	"""Graph class representing a database object or collection of objects."""

	def __init__(self, site, dbobject):
		super(W3GraphDocument, self).__init__(site, dbobject)
		(maxw, maxh) = self.site.max_graph_size
		self.graph.ratio = str(float(maxh) / float(maxw))
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
				im = Image.open(self.filename)
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
					im.save(self.zoom_filename)
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

