# $Header$
# vim: set noet sw=4 ts=4:

"""w3 specific site and document classes.

This module defines subclasses of the classes in the html module which override
certain methods to provide formatting specific to the w3 style [1].

[1] http://w3.ibm.com/standards/intranet/homepage/v8/index.html
"""

import codecs
from db2makedoc.graph import Graph, Node, Edge, Cluster
from db2makedoc.db import DatabaseObject, Database, Schema, Relation, Table, View, Alias, Trigger
from db2makedoc.plugins.html.document import AttrDict, WebSite, HTMLDocument, CSSDocument, JavaScriptDocument, GraphDocument

# Import the ElementTree API, favouring the faster cElementTree implementation
try:
	from xml.etree.cElementTree import fromstring
except ImportError:
	try:
		from cElementTree import fromstring
	except ImportError:
		try:
			from xml.etree.ElementTree import fromstring
		except ImportError:
			try:
				from elementtree.ElementTree import fromstring
			except ImportError:
				raise ImportError('Unable to find an ElementTree implementation')


class W3Site(WebSite):
	"""Site class representing a collection of W3Document instances."""

	def __init__(self, database):
		"""Initializes an instance of the class."""
		super(W3Site, self).__init__(database)
		self.breadcrumbs = True
		self.last_updated = True
		self.feedback_url = 'http://w3.ibm.com/feedback/'
		self.menu_items = []
		self.related_items = []
		self._document_map = {}
		self._graph_map = {}

	def add_document(self, document):
		"""Adds a document to the website.

		This method overrides the base implementation to map database objects
		to documents and graphs according to the w3 structure.
		"""
		super(W3Site, self).add_document(document)
		if isinstance(document, W3MainDocument):
			self._document_map[document.dbobject] = document
		elif isinstance(document, W3GraphDocument):
			self._graph_map[document.dbobject] = document
	
	def object_document(self, dbobject):
		"""Returns the HTMLDocument associated with a database object."""
		return self._document_map.get(dbobject)

	def object_graph(self, dbobject):
		"""Returns the GraphDocument associated with a database object."""
		return self._graph_map.get(dbobject)


class W3Document(HTMLDocument):
	"""Document class for use with the w3v8 style."""

	def _create_content(self):
		# Call the inherited method to create the skeleton document
		super(W3Document, self)._create_content()
		# Add stylesheets and scripts specific to the w3v8 style
		headnode = self._find_element('head')
		headnode.append(self._meta('IBM.Country', 'US'))
		headnode.append(self._meta('IBM.Effective', self.date.strftime('%Y-%m-%d'), 'iso8601'))
		headnode.append(self._script(src='//w3.ibm.com/ui/v8/scripts/scripts.js'))
		headnode.append(self._style(src='//w3.ibm.com/ui/v8/css/v4-screen.css'))
	
	# HTML CONSTRUCTION METHODS
	# Overridden versions specific to w3 formatting
	
	def _hr(self, attrs={}):
		# Overridden to use the w3 dotted line style (uses <div> instead of <hr>)
		return self._element('div', AttrDict({'class': 'hrule-dots'}) + attrs, u'\u00A0') # \u00A0 == &nbsp;
	
	def _table(self, data, head=[], foot=[], caption='', attrs={}):
		# Overridden to color alternate rows white & gray and to apply the
		# 'title' class to all header rows
		tablenode = super(W3Document, self)._table(data, head, foot, caption, attrs)
		tablenode.attrib['cellpadding'] = '0'
		tablenode.attrib['cellspacing'] = '1'
		tablenode.attrib['class'] = 'basic-table'
		try:
			theadnode = tablenode.find('thead')
		except:
			theadnode = None
		if theadnode:
			for rownode in theadnode.findall('tr'):
				classes = rownode.attrib.get('class', '').split()
				classes.append('blue-med-dark')
				rownode.attrib['class'] = ' '.join(classes)
		try:
			tfootnode = tablenode.find('tfoot')
		except:
			tfootnode = None
		if tfootnode:
			for rownode in tfootnode.findall('tr'):
				classes = rownode.attrib.get('class', '').split()
				classes.append('blue-med-dark')
				rownode.attrib['class'] = ' '.join(classes)
		# The <tbody> element is mandatory, no try..except necessary
		colors = ['white', 'gray']
		tbodynode = tablenode.find('tbody')
		for (index, rownode) in enumerate(tbodynode.findall('tr')):
			classes = rownode.attrib.get('class', '').split()
			classes.append(colors[index % 2])
			rownode.attrib['class'] = ' '.join(classes)
		return tablenode


class W3MainDocument(W3Document):
	"""Document class representing a database object (table, view, index, etc.)"""

	# Template of the <body> element of a w3v8 document. This is parsed into an
	# element tree, grafted onto the generated document and then filled in by
	# searching for elements by id in the _create_content() method below.
	template = codecs.getencoder('UTF-8')(u"""\
<?xml version="1.0" encoding="UTF-8"?>
<html>
<head>
</head>
<body id="w3-ibm-com" class="article">

<div class="skip"><a href="#content-main" accesskey="2">Skip to main content</a></div>
<div class="skip"><a href="#left-nav" accesskey="n">Skip to navigation</a></div>
<div id="access-info">
	<p class="access">The access keys for this page are:</p>
	<ul class="access">
		<li>ALT plus 0 links to this site's <a href="http://w3.ibm.com/w3/access-stmt.html" accesskey="0">Accessibility Statement.</a></li>
		<li>ALT plus 1 links to the w3.ibm.com home page.</li>
		<li>ALT plus 2 skips to main content.</li>
		<li>ALT plus 4 skips to the search form.</li>
		<li>ALT plus 9 links to the feedback page.</li>
		<li>ALT plus N skips to navigation.</li>
	</ul>
	<p class="access">Additional accessibility information for w3.ibm.com can be found <a href="http://w3.ibm.com/w3/access-stmt.html">on the w3 Accessibility Statement page.</a></p>
</div>

<div id="masthead">
	<h2 class="access">Start of masthead</h2>
	<div id="prt-w3-sitemark"><img src="//w3.ibm.com/ui/v8/images/id-w3-sitemark-simple.gif" alt="" width="54" height="33" /></div>
	<div id="prt-ibm-logo"><img src="//w3.ibm.com/ui/v8/images/id-ibm-logo-black.gif" alt="" width="44" height="15" /></div>
	<div id="w3-sitemark"><img src="//w3.ibm.com/ui/v8/images/id-w3-sitemark-large.gif" alt="IBM Logo" width="266" height="70" usemap="#sitemark_map" /><map id="sitemark_map" name="sitemark_map"><area shape="rect" alt="Link to W3 Home Page" coords="0,0,130,70" href="http://w3.ibm.com/"  accesskey="1" /></map></div>
	<div id="site-title-only" />
	<div id="ibm-logo"><img src="//w3.ibm.com/ui/v8/images/id-ibm-logo.gif" alt="" width="44" height="15" /></div>
	<div id="persistent-nav"><a id="w3home" href="http://w3.ibm.com/"> w3 Home </a><a id="bluepages" href="http://w3.ibm.com/bluepages/"> BluePages </a><a id="helpnow" href="http://w3.ibm.com/help/"> HelpNow </a><a id="feedback" href="http://w3.ibm.com/feedback/" accesskey="9"> Feedback </a></div>
	<div id="header-search">
		<form action="http://w3.ibm.com/search/w3results.jsp" method="get" id="search">
		<table cellspacing="0" cellpadding="0" class="header-search">
		<tr><td class="label"><label for="header-search-field">Search w3</label></td><td class="field"><input id="header-search-field" name="qt" type="text" accesskey="4" /></td><td class="submit"><label class="access" for="header-search-btn">go button</label><input id="header-search-btn" type="image" alt="Go" src="//w3.ibm.com/ui/v8/images/btn-go-dark.gif" /></td></tr>
		</table>
		</form>
	</div>
	<div id="browser-warning"><img src="//w3.ibm.com/ui/v8/images/icon-system-status-alert.gif" alt="" width="12" height="10" /> This Web page is best used in a modern browser. Since your browser is no longer supported by IBM, please upgrade your web browser at the <a href="http://w3.ibm.com/download/standardsoftware/">ISSI site</a>.</div>
</div>

<div id="content">
	<h1 class="access">Start of main content</h1>

	<div id="content-head" />
	<div id="content-main" />
</div>

<div id="navigation">
	<h2 class="access">Start of left navigation</h2>
	<div id="left-nav" />
</div>

</body>
</html>
""")[0]

	def __init__(self, site, dbobject):
		"""Initializes an instance of the class."""
		self.dbobject = dbobject # must be set before calling the inherited method
		super(W3MainDocument, self).__init__(site, '%s.html' % dbobject.identifier)
		self.title = '%s - %s %s' % (self.site.title, self.dbobject.type_name, self.dbobject.qualified_name)
		self.description = '%s %s' % (self.dbobject.type_name, self.dbobject.qualified_name)
		self.keywords = [self.site.database.name, self.dbobject.type_name, self.dbobject.name, self.dbobject.qualified_name]
		# Add the extra inheritable properties to the site attributes list
		self.breadcrumbs = None
		self.last_updated = None
		self.feedback_url = None
		self.menu_items = None
		self.related_items = None
		self._site_attributes += [
			'breadcrumbs',
			'last_updated',
			'feedback_url',
			'menu_items',
			'related_items',
		]
	
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
		super(W3MainDocument, self)._create_content()
		# Add styles and scripts specific to w3v8 main documents
		headnode = self.doc.find('head')
		headnode.append(self._style(content="""
			@import url("//w3.ibm.com/ui/v8/css/screen.css");
			@import url("//w3.ibm.com/ui/v8/css/icons.css");
			@import url("//w3.ibm.com/ui/v8/css/tables.css");
			@import url("//w3.ibm.com/ui/v8/css/interior.css");
			@import url("//w3.ibm.com/ui/v8/css/interior-1-col.css");
		""", media='all'))
		headnode.append(self._script(src=W3JavaScriptDocument._url))
		headnode.append(self._style(src=W3CSSDocument._url, media='all'))
		headnode.append(self._style(src='//w3.ibm.com/ui/v8/css/print.css', media='print'))
		# Parse the HTML in template and graft the <body> element onto the
		# <body> element in self.doc
		self.doc.remove(self.doc.find('body'))
		self.doc.append(fromstring(self.template).find('body'))
		# Fill in the template
		self.sections = []
		self._append_content(self._find_element('div', 'site-title-only'), '%s Documentation' % self.dbobject.database.name)
		e = self._find_element('a', 'feedback')
		e.attrib['href'] = self.feedback_url
		e = self._find_element('div', 'content-head')
		if self.last_updated:
			self._append_content(e, self._p('Updated on %s' % self.date.strftime('%a, %d %b %Y'), attrs={'id': 'date-stamp'}))
			self._append_content(e, self._hr())
		if self.breadcrumbs:
			self._create_crumbs(e)
		e = self._find_element('div', 'left-nav')
		self._create_menu(e)
		e = self._find_element('div', 'navigation')
		self._create_related(e)
		e = self._find_element('div', 'content-main')
		self._create_sections()
		e.append(self._h('%s %s' % (self.dbobject.type_name, self.dbobject.qualified_name), level=1))
		e.append(self._ul([self._a('#%s' % section['id'], section['title'], 'Jump to section') for section in self.sections]))
		for section in self.sections:
			e.append(self._hr())
			e.append(self._h(section['title'], level=2, attrs={'id': section['id']}))
			self._append_content(e, section['content'])
			e.append(self._p(self._a('#masthead', 'Back to top', 'Jump to top')))
		e.append(self._p(self._a('http://w3.ibm.com/w3/info_terms_of_use.html', 'Terms of use'), attrs={'class': 'terms'}))

	def _create_menu(self, node):
		"""Creates the content of left-hand navigation menu."""
		
		def make_menu_level(selitem, active, subitems):
			"""Builds a list of menu items for a database object and its siblings.

			The make_menu_level() subroutine is called with a database object
			(e.g. a field, table, schema, etc) and returns a list of tuples
			consisting of (url, content, title, active, [children]).
			
			This tuple will eventually be converted into an anchor link, hence
			url will become the href of the link, content will become the text
			content of the link, title will be the value of the title
			attribute, and the boolean active value will indicate whether the
			class "active" is applied to the link. Finally [children] is a list
			of similarly structured tuples giving the entries below the
			corresponding entry.

			Parameters:
			selitem -- The database object to generate menu items around
			active -- True if the database object is the focus of the document (and hence, selected)
			subitems -- The child entries of selitem (if any)
			"""
			# Get the list of siblings and figure out the range of visible items
			if selitem.parent_list is None:
				siblings = [selitem]
				first_visible = 0
				last_visible = 0
			else:
				index = selitem.parent_index
				siblings = selitem.parent_list
				if len(selitem.parent_list) <= 10:
					first_visible = 0
					last_visible = len(siblings) - 1
				elif index <= 3:
					first_visible = 0
					last_visible = 6
				elif index >= len(selitem.parent_list) - 4:
					first_visible = len(siblings) - 7
					last_visible = len(siblings) - 1
				else:
					first_visible = index - 3
					last_visible = index + 3
			more_above = first_visible > 0
			more_below = last_visible < len(siblings) - 1
			# items is a list of tuples of the following fields:
			# (URL, content, title, visible, active, onclick, [children])
			items = []
			index = 0
			for item in siblings:
				content = item.name
				if len(content) > 10:
					content = '%s...' % content[:10]
				title = '%s %s' % (item.type_name, item.qualified_name)
				if item is selitem:
					items.append((
						self.site.object_document(item).url, # url/href
						content,    # content
						title,      # title
						True,       # visible
						active,     # active
						None,       # onclick
						subitems    # children
					))
				else:
					items.append((
						self.site.object_document(item).url, # url/href
						content,    # content
						title,      # title
						first_visible <= index <= last_visible, # visible
						False,      # active
						None,       # onclick
						[]          # children
					))
				index += 1
			if more_above:
				items.insert(0, (
					'',                      # url/href
					u'\u2191 More items...', # content, \u2191 == &uarr;
					'More items',            # title
					True,                    # visible
					False,                   # active
					'show_items(this);',     # onclick
					[]                       # children
				))
			if more_below:
				items.append((
					'',                      # url/href
					u'\u2193 More items...', # content, \u2193 == &darr;
					'More items',            # title
					True,                    # visible
					False,                   # active
					'show_items(this);',     # onclick
					[]                       # children
				))
			return items

		def make_menu_tree(item, active=True):
			"""Builds a tree of menu items for a given database object.

			The make_menu_tree() sub-routine, given a database object, builds a
			tree of tuples (structured as a list of tuples of lists of tuples,
			etc). The tuples are structured as in the make_menu_level
			sub-routine above.

			The tree is built "bottom-up" starting with the selected item (the
			focus of the document being produced) then moving to the parent of
			that item and so on, until the top level is reached.

			Parameters:
			item -- The item to construct a menu tree for
			active -- (optional) If True, item is the focus of the document (and hence, selected)
			"""
			items = []
			while item is not None:
				items = make_menu_level(item, active, items)
				active = False
				item = item.parent
			index = 0
			site_items = [(self.site.home_title, self.site.home_url)] + self.site.menu_items
			for (title, url) in site_items:
				items.insert(index, (
					url,   # url/href
					title, # content
					title, # title
					True,  # visible
					False, # active
					None,  # onclick
					[]     # children
				))
				index += 1
			return items

		def make_menu_elements(parent, items, level=0):
			"""Builds the actual link elements for the menu.

			The make_menu_dom() sub-routine takes the output of the
			make_menu_tree() subroutine and converts it into actual DOM
			elements. This is done in a "top-down" manner (the reverse of
			make_menu_tree()) in order to easily calculate the current nesting
			level (this also explains the separation of make_menu_tree() and
			make_menu_dom()).

			Parameters:
			parent -- The element which will be the parent of the menu elements
			items -- The output of the make_menu_tree() subroutine
			level -- (optional) The current nesting level
			"""
			classes = ['top-level', 'second-level', 'third-level']
			e = self._div('', attrs={'class': classes[level]})
			parent.append(e)
			parent = e
			for (url, content, title, visible, active, onclick, children) in items:
				link = self._a(url, content, title)
				if active:
					link.attrib['class'] = ' '.join(link.attrib.get('class', '').split(' ') + ['active'])
				if not visible:
					link.attrib['style'] = 'display: none;'
				if onclick:
					link.attrib['onclick'] = onclick
				parent.append(link)
				if len(children) > 0 and level + 1 < len(classes):
					make_menu_elements(parent, children, level + 1)

		make_menu_elements(node, make_menu_tree(self.dbobject))
	
	def _create_related(self, node):
		"""Creates the related links after the left-hand navigation menu."""
		if len(self.related_items):
			self._append_content(node, self._p('Related links:'))
			self._append_content(node, self._ul([
				self._a(url, title)
				for (title, url) in self.related_items
			]))

	def _create_crumbs(self, node):
		"""Creates the breadcrumb links at the top of the page."""
		crumbs = []
		item = self.dbobject
		while item is not None:
			crumbs.insert(0, self._a_to(item, typename=True, qualifiedname=False))
			crumbs.insert(0, u' \u00BB ') # \u00BB == &raquo;
			item = item.parent
		crumbs.insert(0, self._a('index.html', 'Home'))
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


class W3PopupDocument(W3Document):
	"""Document class representing a popup help window."""

	# Template of the <body> element of a popup document. This is parsed into
	# an element tree, grafted onto the generated document and then filled in
	# by searching for elements by id in the _create_content() method below.
	template = codecs.getencoder('UTF-8')(u"""\
<?xml version="1.0" encoding="UTF-8"?>
<html>
<head>
</head>
<body id="w3-ibm-com">

<div id="popup-masthead">
	<img id="popup-w3-sitemark" src="//w3.ibm.com/ui/v8/images/id-w3-sitemark-small.gif" alt="" width="182" height="26" />
</div>

<div id="content">
	<div id="content-main">
		<h1>%s</h1>
		%s
		<div id="popup-footer">
			<div class="hrule-dots">\u00A0</div>
			<div class="content">
				<a class="float-right" href="javascript:close();">Close Window</a>
				<a class="popup-print-link" href="javascript://">Print</a>
			</div>
			<div style="clear:both;">\u00A0</div>
		</div>

		<p class="terms"><a href="http://w3.ibm.com/w3/info_terms_of_use.html">Terms of use</a></p>
	</div>
</div>

</body>
</html>
""")[0]

	def __init__(self, site, url, title, body, width=400, height=300):
		"""Initializes an instance of the class."""
		super(W3PopupDocument, self).__init__(site, url)
		# Modify the url to use the JS popup() routine. Note that this won't
		# affect the filename property (used by write()) as the super-class'
		# constructor will already have set that
		self.url = 'javascript:popup("%s","internal",%d,%d)' % (url, height, width)
		self.title = title
		self.body = body
	
	def _create_content(self):
		# Call the inherited method to create the skeleton document
		super(W3PopupDocument, self)._create_content()
		# Add styles specific to w3v8 popup documents
		headnode = self.doc.find('head')
		headnode.append(self._style(src='//w3.ibm.com/ui/v8/css/v4-interior.css'))
		headnode.append(self._style(content="""
			@import url("//w3.ibm.com/ui/v8/css/screen.css");
			@import url("//w3.ibm.com/ui/v8/css/interior.css");
			@import url("//w3.ibm.com/ui/v8/css/popup-window.css");
		""", media='all'))
		headnode.append(self._style(src=W3CSSDocument._url, media='all'))
		headnode.append(self._style(src='//w3.ibm.com/ui/v8/css/print.css', media='print'))
		# Graft the <body> element from self.content onto the <body> element in
		# self.doc
		self.doc.remove(self.doc.find('body'))
		self.doc.append(fromstring(self.template % (self.title, self.body)).find('body'))


class W3CSSDocument(CSSDocument):
	"""Stylesheet class to supplement the w3v8 style with SQL syntax highlighting."""

	_url = 'sql.css'

	def __init__(self, site):
		super(W3CSSDocument, self).__init__(site, self._url)

	def _create_content(self):
		# We only need one supplemental CSS stylesheet (the default w3v8 styles
		# are reasonably comprehensive). So this method is brutally simple...
		self.doc = u"""\
/* SQL syntax highlighting */
.sql {
	font-size: 8pt;
	font-family: "Courier New", monospace;
}

pre.sql {
	background-color: #ddd;
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
#content-main img { border: 0 none; }
"""


class W3JavaScriptDocument(JavaScriptDocument):
	"""Code class to supplement the w3v8 style with some simple routines."""

	_url = 'scripts.js'

	def __init__(self, site):
		super(W3JavaScriptDocument, self).__init__(site, self._url)

	def _create_content(self):
		self.doc = u"""\
// IE doesn't have a clue (no Node built-in) so we'll define one just for it...
var ELEMENT_NODE = 1;

// Replace the "More items..." link (e) with the items it's hiding
function show_items(e) {
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
}
"""


class W3GraphDocument(GraphDocument):
	"""Graph class representing a database object or collection of objects."""

	def __init__(self, site, dbobject):
		"""Initializes an instance of the class."""
		self.dbobject = dbobject # must be set before calling the inherited method
		super(W3GraphDocument, self).__init__(site, '%s.png' % dbobject.identifier)
		self._dbobject_map = {}
	
	def _create_graph(self):
		# Override in descendent classes to generate nodes, edges, etc. in the
		# graph
		pass

	def _create_content(self):
		# Call the inherited method in case it does anything
		super(W3GraphDocument, self)._create_content()
		# Call _create_graph to create the content of the graph
		self._create_graph()
		# Tweak some of the graph attributes to make it scale a bit more nicely
		self.graph.rankdir = 'LR'
		self.graph.size = '10,20'
		self.graph.dpi = '96'
		self.graph.ratio = '1.5'
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
				node.fontsize = 9.0
			elif isinstance(node, Cluster):
				node.fontname = 'Verdana'
				node.fontsize = 12.0

		self.graph.touch(rewrite_url)
		self.graph.touch(rewrite_font)

	def _add_dbobject(self, dbobject, selected=False):
		"""Utility method to add a database object to the graph.

		This utility method adds the specified database object along with
		standardized formatting depending on the type of the object.
		"""
		assert isinstance(dbobject, DatabaseObject)
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
