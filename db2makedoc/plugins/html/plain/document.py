# vim: set noet sw=4 ts=4:

"""Plain site and document classes.

This module defines subclasses of the classes in the html module which override
certain methods to provide formatting specific to the plain style.
"""

import os
import codecs
import logging
from db2makedoc.graph import Graph, Node, Edge, Cluster
from db2makedoc.etree import ProcessingInstruction, fromstring
from db2makedoc.db import (
	DatabaseObject, Database, Schema, Relation,
	Table, View, Alias, Trigger
)
from db2makedoc.plugins.html.document import (
	Attrs, ElementFactory, WebSite, HTMLDocument, HTMLObjectDocument,
	HTMLIndexDocument, HTMLExternalDocument, CSSDocument, SQLCSSDocument,
	GraphDocument, GraphObjectDocument
)

# Import the imaging library
try:
	from PIL import Image
except ImportError:
	# Ignore any import errors - the main plugin takes care of warning the
	# user if PIL is required but not present
	pass


class PlainElementFactory(ElementFactory):
	# Overridden to apply plain styles to certain elements

	def _add_class(self, node, cls):
		classes = set(node.attrib.get('class', '').split(' '))
		classes.add(cls)
		node.attrib['class'] = ' '.join(classes)

	def table(self, *content, **attrs):
		table = self._element('table', *content, **attrs)
		# If there's a tbody element, apply 'even' and 'odd' CSS classes to
		# rows in the body.
		try:
			tbody = self._find(table, 'tbody')
		except:
			pass
		else:
			for index, tr in enumerate(tbody.findall('tr')):
				self._add_class(tr, ['odd', 'even'][index % 2])
		return table

tag = PlainElementFactory()


class PlainSite(WebSite):
	"""Site class representing a collection of PlainDocument instances."""

	def __init__(self, database, options):
		super(PlainSite, self).__init__(database, options)
		self.last_updated = options['last_updated']
		self.max_graph_size = options['max_graph_size']
		self.stylesheets = options['stylesheets']


class PlainExternalDocument(HTMLExternalDocument):
	pass


class PlainDocument(HTMLDocument):
	"""Document class for use with the plain style."""

	def generate(self):
		# Overridden to add basic styling
		doc = super(PlainDocument, self).generate()
		# Add styles
		headnode = tag._find(doc, 'head')
		for sheet in self.site.stylesheets:
			headnode.append(sheet.link())
		if self.site.stylesheets:
			for url in self.site.stylesheets:
				headnode.append(tag.style(src=url, media='all'))
		headnode.append(tag.script("""
function popup(url, type, height, width) {
	newWin = window.open(url, 'popupWindow', 'height=' + height + ',width=' + width +
		',resizable=yes,menubar=no,status=no,toolbar=no,scrollbars=yes');
	newWin.focus();
	return false;
}"""))
		# Add common header elements to the body
		bodynode = tag._find(doc, 'body')
		bodynode.append(tag.h1(self.site.title, id='top'))
		if self.site.search:
			bodynode.append(tag.form(
				'Search: ',
				tag.input(type='text', name='q', size=20),
				' ',
				tag.input(type='submit', value='Go'),
				method='GET', action='search.php'
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
			return tag.p(links, id='breadcrumbs')
		else:
			return tag.p()


class PlainObjectDocument(HTMLObjectDocument, PlainDocument):
	"""Document class representing a database object (table, view, index, etc.)"""

	def __init__(self, site, dbobject):
		super(PlainObjectDocument, self).__init__(site, dbobject)
		self.last_updated = site.last_updated
	
	def generate(self):
		# Call the inherited method to create the skeleton document
		doc = super(PlainObjectDocument, self).generate()
		# Add body content
		bodynode = tag._find(doc, 'body')
		bodynode.append(tag.h2('%s %s' % (self.site.type_names[self.dbobject.__class__], self.dbobject.qualified_name)))
		sections = self.generate_sections()
		if sections:
			bodynode.append(tag.ul((
				tag.li(tag.a(title, href='#' + id, title='Jump to section'))
				for (id, title, content) in sections
			), id='toc'))
			tag._append(bodynode, (
				(tag.h3(title, id=id), content, tag.p(tag.a('Back to top', href='#top')))
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
		# Call the inherited method to create the skeleton document
		doc = super(PlainSiteIndexDocument, self).generate()
		# Add body content
		bodynode = tag._find(doc, 'body')
		bodynode.append(tag.h2('%s Index' % self.site.type_names[self.dbclass]))
		# Generate the letter links to other docs in the index
		links = tag.p()
		item = self.first
		while item:
			if item is self:
				tag._append(links, tag.strong(item.letter))
			else:
				tag._append(links, tag.a(item.letter, href=item.url))
			tag._append(links, ' ')
			item = item.next
		bodynode.append(links)
		bodynode.append(tag.hr())
		# Sort the list of items in the index, and build the content. Note that
		# self.items is actually reference to a site level object and therefore
		# must be considered read-only, hence why the list is not sorted
		# in-place here
		items = sorted(self.items, key=lambda item: '%s %s' % (item.name, item.qualified_name))
		bodynode.append(tag.dl(
			(
				tag.dt(item.name, ' (', self.site.type_names[item.__class__], ' ', self.site.link_to(item, parent=True), ')'),
				tag.dd(self.format_comment(item.description, summary=True))
			)
			for item in items
		))
		return doc


class PlainPopupDocument(PlainDocument):
	"""Document class representing a popup help window."""

	def __init__(self, site, url, title, body, width=400, height=300):
		"""Initializes an instance of the class."""
		super(PlainPopupDocument, self).__init__(site, url)
		self.title = title
		self.body = body
		self.width = width
		self.height = height
	
	def generate(self):
		# Call the inherited method to create the skeleton document
		doc = super(PlainPopupDocument, self).generate()
		# Add styles specific to w3v8 popup documents
		headnode = tag._find(doc, 'head')
		# Generate the popup content
		bodynode = tag._find(doc, 'body')
		del bodynode[:] # Clear the existing body content
		bodynode.append(tag.div(
			tag.h2(self.title),
			self.body,
			tag.div(
				tag.hr(),
				tag.div(
					tag.a('Close Window', href='javascript:close();'),
					tag.a('Print', href='javascript:window.print();'),
					class_='content'
				),
				id='footer'
			)
		))
		return doc

	def link(self):
		# Modify the link to use the JS popup() routine
		return tag.a(self.title, href=self.url, title=self.title,
			onclick='javascript:return popup("%s","internal",%d,%d);' % (self.url, self.height, self.width))


class PlainSearchDocument(PlainDocument):
	"""Document class containing the PHP search script"""

	def __init__(self, site):
		super(PlainSearchDocument, self).__init__(site, 'search.php')
		self.title = '%s - Search Results' % site.title
		self.description = 'Search Results'
		self.search = False
		self.last_updated = site.last_updated
	
	def generate(self):
		doc = super(PlainSearchDocument, self).generate()
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
		php = r"""
require '__XAPIAN__';

# Defaults and limits
$PAGE_DEFAULT = 1;
$PAGE_MIN = 1;
$PAGE_MAX = 0; # Calculated by run_query()
$COUNT_DEFAULT = 20;
$COUNT_MIN = 10;
$COUNT_MAX = 100;

# Globals derived from GET values
$Q = array_key_exists('q', $_GET) ? strval($_GET['q']) : '';
$PAGE = array_key_exists('page', $_GET) ? intval($_GET['page']) : $PAGE_DEFAULT;
$PAGE = max($PAGE_MIN, $PAGE);
$COUNT = array_key_exists('count', $_GET) ? intval($_GET['count']) : $COUNT_DEFAULT;
$COUNT = max($COUNT_MIN, min($COUNT_MAX, $COUNT));

function run_query() {
	global $Q, $PAGE, $COUNT, $PAGE_MAX;

	$db = new XapianDatabase('search');
	$enquire = new XapianEnquire($db);
	$parser = new XapianQueryParser();
	$parser->set_stemmer(new XapianStem('__LANG__'));
	$parser->set_stemming_strategy(XapianQueryParser::STEM_SOME);
	$parser->set_database($db);
	$query = $parser->parse_query($Q,
		XapianQueryParser::FLAG_BOOLEAN_ANY_CASE |  # Enable boolean operators (with any case)
		XapianQueryParser::FLAG_PHRASE |            # Enable quoted phrases 
		XapianQueryParser::FLAG_LOVEHATE |          # Enable + and -
		XapianQueryParser::FLAG_SPELLING_CORRECTION # Enable suggested corrections
	);
	$enquire->set_query($query);
	$result = $enquire->get_mset((($PAGE - 1) * $COUNT) + 1, $COUNT);
	$PAGE_MAX = ceil($result->get_matches_estimated() / floatval($COUNT));
	return $result;
}

function result_header($doc, $matches) {
	global $Q, $PAGE, $COUNT;

	$page_from = (($PAGE - 1) * $COUNT) + 1;
	$page_to = $page_from + $matches->size() - 1;
	$label = sprintf('Showing results %d to %d of about %d for "%s"',
		$page_from, $page_to, $matches->get_matches_estimated(), $Q);
	$result = $doc->createElement('p');
	$result->appendChild(new DOMText($label));
	return $result;
}

function result_table($doc, $matches) {
	$result = $doc->createElement('table');
	$result->appendChild(new DOMAttr('class', 'searchresults'));
	# Write the header row
	$row = $doc->createElement('tr');
	foreach (array('Relevance', 'Link') as $content) {
		$cell = $doc->createElement('th');
		$cell->appendChild(new DOMText($content));
		$row->appendChild($cell);
	}
	$result->appendChild($row);
	# Write the result rows
	$i = $matches->begin();
	while (! $i->equals($matches->end())) {
		list($url, $data) = explode("\n", $i->get_document()->get_data(), 2);
		$relevance = new DOMText(sprintf('%d%%', $i->get_percent()));
		$link = $doc->createElement('a');
		$link->appendChild(new DOMAttr('href', $url));
		$link->appendChild(new DOMText($data));
		$row = $doc->createElement('tr');
		foreach (array($relevance, $link) as $content) {
			$cell = $doc->createElement('td');
			$cell->appendChild($content);
			$row->appendChild($cell);
		}
		$result->appendChild($row);
		$i->next();
	}
	return $result;
}

function result_page_link($doc, $page, $label='') {
	global $Q, $PAGE, $PAGE_MIN, $PAGE_MAX, $COUNT;

	if ($label == '') $label = strval($page);
	if (($page == $PAGE) || ($page < $PAGE_MIN) || ($page > $PAGE_MAX)) {
		$result = $doc->createTextNode($label);
	}
	else {
		$result = $doc->createElement('a');
		$result->appendChild(new DOMAttr('href',
			sprintf('?q=%s&page=%d&count=%d', $Q, $page, $COUNT)));
		$result->appendChild(new DOMText($label));
	}
	return $result;
}

function result_pages($doc) {
	global $PAGE, $PAGE_MIN, $PAGE_MAX;

	$result = $doc->createElement('p');
	$result->appendChild(new DOMAttr('class', 'search-pages'));
	$result->appendChild(result_page_link($doc, $PAGE - 1, '< Previous'));
	$result->appendChild(new DOMText(' '));
	for ($i = $PAGE_MIN; $i <= $PAGE_MAX; $i++) {
		$result->appendChild(result_page_link($doc, $i));
		$result->appendChild(new DOMText(' '));
	}
	$result->appendChild(result_page_link($doc, $PAGE + 1, 'Next >'));
	return $result;
}

try {
	$doc = new DOMDocument('1.0', '__ENCODING__');
	$root = $doc->createElement('div');
	$doc->appendChild($root);
	$matches = run_query();
	$root->appendChild(result_header($doc, $matches));
	$root->appendChild(result_pages($doc));
	$root->appendChild(result_table($doc, $matches));
	print($doc->saveXML($doc->documentElement));
}
catch (Exception $e) {
	print(htmlspecialchars($e->getMessage() . "\n"));
}
"""
		php = php.replace('__XAPIAN__', 'xapian.php')
		php = php.replace('__LANG__', self.site.lang)
		php = php.replace('__ENCODING__', self.site.encoding)
		result = super(PlainSearchDocument, self).serialize(content)
		return result.replace('__PHP__', php)


class PlainCSSDocument(CSSDocument):
	"""Stylesheet class to define the base site style."""

	def __init__(self, site):
		super(PlainCSSDocument, self).__init__(site, 'styles.css')

	def generate(self):
		doc = super(PlainCSSDocument, self).generate()
		return doc + u"""\
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

dl dt {
	font-weight: bold;
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

p.search-pages {
	font-weight: bold;
}

/* Fix display of border around diagrams in Firefox */
img { border: 0 none; }
"""


class PlainGraphDocument(GraphObjectDocument):
	"""Graph class representing a database object or collection of objects."""

	def __init__(self, site, dbobject):
		"""Initializes an instance of the class."""
		super(PlainGraphDocument, self).__init__(site, dbobject)
		(maxw, maxh) = site.max_graph_size
		self.graph.ratio = str(float(maxh) / float(maxw))
		self.written = False
		self.scale = None
	
	def write(self):
		# Overridden to set the introduced "written" flag (to ensure we don't
		# attempt to write the graph more than once due to the induced write()
		# call in the overridden _link() method), and to handle resizing the
		# image if it's larger than the maximum size specified in the config
		if not self.written:
			super(PlainGraphDocument, self).write()
			self.written = True
			if self.usemap:
				im = Image.open(self.filename)
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
		if not self.written:
			self.write()
		result = super(PlainGraphDocument, self).map()
		if self.scale is not None:
			for area in result:
				# Convert coords string into a list of integer tuples
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

