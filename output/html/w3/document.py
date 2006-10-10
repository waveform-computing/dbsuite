# $Header$
# vim: set noet sw=4 ts=4:

# Standard modules
import os.path
import logging
import re
import codecs
import xml.dom
import xml.dom.minidom

# Application-specific modules
from db.base import DocBase
from db.schema import Schema
from db.schemabase import Relation
from db.table import Table
from db.view import View
from db.alias import Alias
from db.trigger import Trigger
from sql.tokenizer import DB2UDBSQLTokenizer
from sql.formatter import SQLFormatter
from sql.htmlhighlighter import SQLDOMHighlighter
from output.html.document import AttrDict, WebSite, HTMLDocument, CSSDocument, GraphDocument
from dot.graph import Graph, Node, Edge, Cluster

class W3Site(WebSite):
	"""Site class representing a collection of W3Document instances."""

	def __init__(self, database):
		"""Initializes an instance of the class."""
		super(W3Site, self).__init__()
		self.database = database
		self.title = '%s Documentation' % self.database.name
		self.keywords = [self.database.name]
		self.copyright = 'Copyright (c) 2001,2006 by IBM corporation'
		self.document_map = {}
		self.graph_map = {}

class W3Document(HTMLDocument):
	"""Document class for use with the w3v8 style."""

	def __init__(self, site, url):
		assert isinstance(site, W3Site)
		super(W3Document, self).__init__(site, url)

	def create_content(self):
		# Call the inherited method to create the skeleton document
		super(W3Document, self).create_content()
		# Add stylesheets and scripts specific to the w3v8 style
		headnode = self.doc.getElementsByTagName('head')[0]
		headnode.appendChild(self.meta('IBM.Country', 'US'))
		headnode.appendChild(self.meta('IBM.Effective', self.date.strftime('%Y-%m-%d'), 'iso8601'))
		headnode.appendChild(self.script(src='//w3.ibm.com/ui/v8/scripts/scripts.js'))
		headnode.appendChild(self.style(src='//w3.ibm.com/ui/v8/css/v4-screen.css'))
	
	# HTML CONSTRUCTION METHODS
	# Overridden versions specific to w3 formatting
	
	def a_to(self, dbobject, typename=False, qualifiedname=False):
		# Special version of "a" to create a link to a database object
		assert isinstance(dbobject, DocBase)
		href = self.site.document_map[dbobject].url
		if qualifiedname:
			content = dbobject.qualified_name
		else:
			content = dbobject.name
		if typename:
			content = '%s %s' % (dbobject.type_name, content)
		return self.a(href, content)

	def img_of(self, dbobject):
		# Special version of "img" to create a graph of a database object
		assert isinstance(dbobject, DocBase)
		return self.element('object', {
			'data': self.site.graph_map[dbobject].url,
			'type': 'image/svg+xml',
			'width': '750',
			'height': '500',
		}, 'Unable to render SVG diagram')

	def hr(self, attrs={}):
		# Overridden to use the w3 dotted line style (uses <div> instead of <hr>)
		return self.element('div', AttrDict({'class': 'hrule-dots'}) + attrs, u'\u00A0') # \u00A0 == &nbsp;
	
	def table(self, data, head=[], foot=[], caption='', attrs={}):
		# Overridden to color alternate rows white & gray and to apply the
		# 'title' class to all header rows
		tablenode = super(W3Document, self).table(data, head, foot, caption, attrs)
		tablenode.setAttribute('cellpadding', '0')
		tablenode.setAttribute('cellspacing', '1')
		tablenode.setAttribute('class', 'basic-table')
		try:
			theadnode = tablenode.getElementsByTagName('thead')[0]
		except:
			theadnode = None
		if theadnode:
			for rownode in theadnode.getElementsByTagName('tr'):
				classes = rownode.getAttribute('class').split()
				classes.append('blue-med-dark')
				rownode.setAttribute('class', ' '.join(classes))
		try:
			tfootnode = tablenode.getElementsByTagName('tfoot')[0]
		except:
			tfootnode = None
		if tfootnode:
			for rownode in tfootnode.getElementsByTagName('tr'):
				classes = rownode.getAttribute('class').split()
				classes.append('blue-med-dark')
				rownode.setAttribute('class', ' '.join(classes))
		# The <tbody> element is mandatory, no try..except necessary
		colors = ['white', 'gray']
		tbodynode = tablenode.getElementsByTagName('tbody')[0]
		for (index, rownode) in enumerate(tbodynode.getElementsByTagName('tr')):
			classes = rownode.getAttribute('class').split()
			classes.append(colors[index % 2])
			rownode.setAttribute('class', ' '.join(classes))
		return tablenode

class W3MainDocument(W3Document):
	"""Document class representing a database object (table, view, index, etc.)"""

	# Template of the <body> element of a w3v8 document. This is parsed into a
	# DOM tree, grafted onto the generated document and then filled in by
	# searching for elements by id in the create_content() method below.
	template = xml.dom.minidom.parseString(codecs.getencoder('UTF-8')(u"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html
	PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
	"http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" lang="en" xml:lang="en">
<head>
</head>
<body id="w3-ibm-com" class="article">

<!-- start accessibility prolog -->
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
<!-- end accessibility prolog -->

<!-- start masthead -->
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
<!-- stop masthead -->

<!-- start content -->
<div id="content">
	<h1 class="access">Start of main content</h1>

	<!-- start content head -->
	<div id="content-head">
		<p id="date-stamp" />
		<div class="hrule-dots">\u00A0</div>
		<p id="breadcrumbs" />
	</div>
	<!-- stop content head -->

	<!-- start main content -->
	<div id="content-main">
	</div>
	<!-- stop main content -->

</div>
<!-- stop content -->

<!-- start navigation -->
<div id="navigation">
	<h2 class="access">Start of left navigation</h2>

	<!-- left nav -->
	<div id="left-nav">
	</div>

	<!-- start related links -->
	<p>Related links:</p>
	<ul>
		<li><a href="http://isls.endicott.ibm.com/Documentation/nw3Doc.htm">IS&amp;LS Documentation Home</a></li>
		<li><a href="http://isls5.endicott.ibm.com/bmsiwIC/index.html">BMS/IW Reference</a></li>
		<li><a href="http://bmt.stuttgart.de.ibm.com/">BMT Homepage</a></li>
		<li><a href="https://servicesim.portsmouth.uk.ibm.com/cgi-bin/db2www/~bmtdoc/docu_bmt.mac/report">BMT Dynamic Documentation</a></li>
	    <li><a href="http://publib.boulder.ibm.com/infocenter/db2luw/v8/index.jsp">IBM DB2 UDB Info Center</a></li>
	</ul>
	<!-- stop related links -->

</div>
<!-- stop navigation -->

</body>
</html>
""")[0])

	def __init__(self, site, dbobject):
		"""Initializes an instance of the class."""
		super(W3MainDocument, self).__init__(site, '%s.html' % dbobject.identifier)
		self.dbobject = dbobject
		self.site.document_map[dbobject] = self
		self.title = '%s - %s %s' % (self.site.title, self.dbobject.type_name, self.dbobject.qualified_name)
		self.description = '%s %s' % (self.dbobject.type_name, self.dbobject.qualified_name)
		self.keywords = [self.site.database.name, self.dbobject.type_name, self.dbobject.name, self.dbobject.qualified_name]
		self.tokenizer = DB2UDBSQLTokenizer()
		self.formatter = SQLFormatter()
		self.highlighter = SQLDOMHighlighter()
	
	def write(self):
		# Overridden to add logging
		logging.debug('Writing documentation for %s %s to %s' % (self.dbobject.type_name, self.dbobject.name, self.filename))
		super(W3MainDocument, self).write()

	def format_sql(self, sql, terminator=';'):
		"""Syntax highlights an SQL script with <span> elements.

        Using the tokenizer, reformatter and HTML highlighter units in the
        sql sub-package, this routine takes raw (typically white-space
        mangled) SQL code and returns pretty-printed, syntax highlighted
        SQL in HTML format.

        This routine handles highlighting any arbitrary SQL script.
		"""
		tokens = self.tokenizer.parse(sql, terminator)
		tokens = self.formatter.parse(tokens)
		return self.highlighter.parse(tokens, self.doc)

	def format_prototype(self, sql):
		"""Syntax highlights an SQL routine prototype with <span> elements.

        This method is similar to the format_sql() method, but operates on
        standalone function prototypes which aren't otherwise valid standalone
        SQL scripts.
		"""
		tokens = self.tokenizer.parse(sql)
		tokens = self.formatter.parseRoutinePrototype(tokens)
		return self.highlighter.parse(tokens, self.doc)

	findref = re.compile(r'@([A-Za-z_$#@][A-Za-z0-9_$#@]*(\.[A-Za-z_$#@][A-Za-z0-9_$#@]*){0,2})\b')
	findfmt = re.compile(r'\B([/_*])(\w+)\1\B')
	def format_description(self, text, firstline=False):
		"""Formats simple prefix-based markup into HTML.
		
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
		if firstline:
			text = text.split('\n')[0]
		# Convert simple markup to HTML
		start = 0
		result = []
		while True:
			matchref = self.findref.search(text, start)
			matchfmt = self.findfmt.search(text, start)
			if matchref is not None and (matchfmt is None or matchfmt.start(0) > matchref.start(0)):
				result.append(text[start:matchref.start(0)])
				start = matchref.end(0)
				target = self.dbobject.database.find(matchref.group(1))
				if target is None:
					result.append(text[start:matchref.group(1)])
				else:
					result.append(self.a_to(target, qualifiedname=True))
			elif matchfmt is not None and (matchref is None or matchfmt.start(0) < matchref.start(0)):
				result.append(text[start:matchfmt.start(0)])
				start = matchfmt.end(0)
				if matchfmt.group(1) == '*':
					result.append(self.strong(matchfmt.group(2)))
				elif matchfmt.group(1) == '/':
					result.append(self.em(matchfmt.group(2)))
				elif matchfmt.group(1) == '_':
					result.append(self.u(matchfmt.group(2)))
				else:
					assert False
			else:
				result.append(text[start:])
				break
		# Convert strings into text nodes and line breaks in <br> elements
		items = []
		for item in result:
			if isinstance(item, basestring):
				lines = item.split('\n')
				first = True
				for line in lines:
					if not first:
						items.append(self.doc.createElement('br'))
					else:
						first = False
					items.append(self.doc.createTextNode(line))
			else:
				items.append(item)
		return items

	def create_content(self):
		# Overridden to automatically set the link objects and generate the
		# content from the sections filled in by descendent classes in
		# create_sections
		if not self.link_first:
			self.link_first = self.site.document_map.get(self.dbobject.first)
		if not self.link_prior:
			self.link_prior = self.site.document_map.get(self.dbobject.prior)
		if not self.link_next:
			self.link_next = self.site.document_map.get(self.dbobject.next)
		if not self.link_last:
			self.link_last = self.site.document_map.get(self.dbobject.last)
		if not self.link_up:
			self.link_up = self.site.document_map.get(self.dbobject.parent)
		# Call the inherited method to create the skeleton document
		super(W3MainDocument, self).create_content()
		# Add styles specific to w3v8 main documents
		headnode = self.doc.getElementsByTagName('head')[0]
		headnode.appendChild(self.style(content="""
			@import url("//w3.ibm.com/ui/v8/css/screen.css");
			@import url("//w3.ibm.com/ui/v8/css/icons.css");
			@import url("//w3.ibm.com/ui/v8/css/tables.css");
			@import url("//w3.ibm.com/ui/v8/css/interior.css");
			@import url("//w3.ibm.com/ui/v8/css/interior-1-col.css");
		""", media='all'))
		headnode.appendChild(self.style(src='sql.css', media='all'))
		headnode.appendChild(self.style(src='//w3.ibm.com/ui/v8/css/print.css', media='print'))
		# Parse the HTML in template and graft the <body> element onto the
		# <body> element in self.doc
		oldbodynode = self.doc.getElementsByTagName('body')[0]
		newbodynode = self.template.getElementsByTagName('body')[0]
		newbodynode = self.doc.importNode(newbodynode, deep=True)
		self.doc.documentElement.replaceChild(newbodynode, oldbodynode)
		# Fill in the template
		self.append_content(self.find_element('div', 'site-title-only'), '%s Documentation' % self.dbobject.database.name)
		self.append_content(self.find_element('p', 'date-stamp'), 'Updated on %s' % self.date.strftime('%a, %d %b %Y'))
		self.create_crumbs()
		self.create_menu()
		self.sections = []
		self.create_sections()
		mainnode = self.find_element('div', 'content-main')
		mainnode.appendChild(self.h('%s %s' % (self.dbobject.type_name, self.dbobject.qualified_name), level=1))
		mainnode.appendChild(self.ul([self.a('#%s' % section['id'], section['title'], 'Jump to section') for section in self.sections]))
		for section in self.sections:
			mainnode.appendChild(self.hr())
			mainnode.appendChild(self.h(section['title'], level=2, attrs={'id': section['id']}))
			self.append_content(mainnode, section['content'])
			mainnode.appendChild(self.p(self.a('#masthead', 'Back to top', 'Jump to top')))
		mainnode.appendChild(self.p(self.a('http://w3.ibm.com/w3/info_terms_of_use.html', 'Terms of use'), attrs={'class': 'terms'}))

	def create_menu(self):
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
			moretop = False
			morebot = False
			if selitem.parent_list is None:
				slice = [selitem]
			else:
				index = selitem.parent_index
				if len(selitem.parent_list) <= 10:
					slice = selitem.parent_list
				elif index <= 3:
					slice = selitem.parent_list[:7]
					morebot = True
				elif index >= len(selitem.parent_list) - 4:
					slice = selitem.parent_list[-7:]
					moretop = True
				else:
					slice = selitem.parent_list[index - 3:index + 4]
					moretop = True
					morebot = True
			# items is a list of tuples of (URL, content, title, active, [children])
			items = []
			for item in slice:
				content = item.name
				if len(content) > 10: content = '%s...' % content[:10]
				title = '%s %s' % (item.type_name, item.qualified_name)
				if item == selitem:
					items.append((self.site.document_map[item].url, content, title, active, subitems))
				else:
					items.append((self.site.document_map[item].url, content, title, False, []))
			if moretop:
				items.insert(0, ('#', u'\u2191 More items...', 'More items', False, [])) # \u2191 == &uarr;
			if morebot:
				items.append(('#', u'\u2193 More items...', 'More items', False, [])) # \u2193 == &darr;
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
			# items is a list of tuples of (URL, content, title, active, [children])
			items = []
			while item is not None:
				items = make_menu_level(item, active, items)
				active = False
				item = item.parent
			items.insert(0, ('index.html', 'Home', 'Home', False, []))
			return items

		def make_menu_dom(parent, items, level=0):
			"""Builds the actual DOM link elements for the menu.

			The make_menu_dom() sub-routine takes the output of the
			make_menu_tree() subroutine and converts it into actual DOM
			elements. This is done in a "top-down" manner (the reverse of
			make_menu_tree()) in order to easily calculate the current nesting
			level (this also explains the separation of make_menu_tree() and
			make_menu_dom()).

			Parameters:
			parent -- The DOM node which will be the parent of the menu elements
			items -- The output of the make_menu_tree() subroutine
			level -- (optional) The current nesting level
			"""
			classes = ['top-level', 'second-level', 'third-level']
			parent = parent.appendChild(self.doc.createElement('div'))
			parent.setAttribute('class', classes[level])
			for (url, content, title, active, children) in items:
				link = parent.appendChild(self.a(url, content, title))
				if active:
					link.setAttribute('class', 'active')
				if len(children) > 0 and level + 1 < len(classes):
					make_menu_dom(parent, children, level + 1)

		make_menu_dom(self.find_element('div', 'left-nav'), make_menu_tree(self.dbobject))

	def create_crumbs(self):
		"""Creates the breadcrumb links at the top of the page."""
		crumbs = []
		item = self.dbobject
		while item is not None:
			crumbs.insert(0, self.a_to(item, typename=True, qualifiedname=False))
			crumbs.insert(0, self.doc.createTextNode(u' \u00BB ')) # \u00BB == &raquo;
			item = item.parent
		crumbs.insert(0, self.a('index.html', 'Home'))
		self.append_content(self.find_element('p', 'breadcrumbs'), crumbs)
	
	# CONTENT METHODS
	# The following methods are for use in descendent classes to fill the
	# sections list with content. Basically, all descendent classes need to do
	# is override the create_sections() method, calling section() and add() in
	# their implementation

	def create_sections(self):
		# Override in descendent classes
		pass

	def section(self, id, title):
		"""Starts a new section in the body of the current document.

		Parameters:
		id -- The id of the anchor at the start of the section
		title -- The title text of the section
		"""
		self.sections.append({'id': id, 'title': title, 'content': []})
	
	def add(self, content):
		"""Add HTML content or elements to the end of the current section.

		Parameters:
		content -- A string, Node, NodeList, or tuple/list of Nodes
		"""
		self.sections[-1]['content'].append(content)

class W3PopupDocument(W3Document):
	"""Document class representing a popup help window."""

	# Template of the <body> element of a popup document. This is parsed into a
	# DOM tree, grafted onto the generated document and then filled in by
	# searching for elements by id in the create_content() method below.

	def __init__(self, site, url, title, body, width=400, height=300):
		"""Initializes an instance of the class."""
		super(W3PopupDocument, self).__init__(site, url)
		# Modify the url to use the JS popup() routine. Note that this won't
		# affect the filename property (used by write()) as the super-class'
		# constructor will already have set that
		self.url = 'javascript:popup("%s","internal",%d,%d)' % (url, height, width)
		self.title = title
		self.content = xml.dom.minidom.parseString(codecs.getencoder('UTF-8')(u"""\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html
	PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
	"http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">
<head>
</head>
<body id="w3-ibm-com">

<!-- start popup masthead //////////////////////////////////////////// -->
<div id="popup-masthead">
	<img id="popup-w3-sitemark" src="//w3.ibm.com/ui/v8/images/id-w3-sitemark-small.gif" alt="" width="182" height="26" />
</div>
<!-- stop popup masthead //////////////////////////////////////////// -->

<!-- start content //////////////////////////////////////////// -->
<div id="content">
	<!-- start main content -->
	<div id="content-main">
		<h1>%s</h1>
		%s
		<!-- start popup footer //////////////////////////////////////////// -->
		<div id="popup-footer">
			<div class="hrule-dots">\u00A0</div>
			<div class="content">
				<a class="float-right" href="javascript:close();">Close Window</a>
				<a class="popup-print-link" href="javascript://">Print</a>
			</div>
			<div style="clear:both;">\u00A0</div>
		</div>
		<!-- stop popup footer //////////////////////////////////////////// -->

		<p class="terms"><a href="http://w3.ibm.com/w3/info_terms_of_use.html">Terms of use</a></p>
	</div>
	<!-- stop main content -->

</div>
<!-- stop content //////////////////////////////////////////// -->

</body>
</html>
""" % (title, body))[0])
	
	def write(self):
		# Overridden to add logging
		logging.debug('Writing popup document to %s' % self.filename)
		super(W3PopupDocument, self).write()

	def create_content(self):
		# Call the inherited method to create the skeleton document
		super(W3PopupDocument, self).create_content()
		# Add styles specific to w3v8 popup documents
		headnode = self.doc.getElementsByTagName('head')[0]
		headnode.appendChild(self.style(src='//w3.ibm.com/ui/v8/css/v4-interior.css'))
		headnode.appendChild(self.style(content="""
			@import url("//w3.ibm.com/ui/v8/css/screen.css");
			@import url("//w3.ibm.com/ui/v8/css/interior.css");
			@import url("//w3.ibm.com/ui/v8/css/popup-window.css");
		""", media='all'))
		headnode.appendChild(self.style(src='sql.css', media='all'))
		headnode.appendChild(self.style(src='//w3.ibm.com/ui/v8/css/print.css', media='print'))
		# Graft the <body> element from self.content onto the <body> element in
		# self.doc
		oldbodynode = self.doc.getElementsByTagName('body')[0]
		newbodynode = self.content.getElementsByTagName('body')[0]
		newbodynode = self.doc.importNode(newbodynode, deep=True)
		self.doc.documentElement.replaceChild(newbodynode, oldbodynode)

class W3CSSDocument(CSSDocument):
	"""Stylesheet class to supplement the w3v8 style with SQL syntax highlighting."""

	def __init__(self, site, url):
		"""Initializes an instance of the class."""
		assert isinstance(site, W3Site)
		super(W3CSSDocument, self).__init__(site, url)
		# We only need one supplemental CSS stylesheet (the default w3v8 are
		# pretty comprehensive). So this class is brutally simple...
		self.doc = """\
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
	/* No way to do this in IE? ... oh well */
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

td.num_cell { background-color: silver; }
td.sql_cell { background-color: gray; }
"""

class W3GraphDocument(GraphDocument):
	"""Graph class representing a database object or collection of objects."""

	def __init__(self, site, dbobject):
		"""Initializes an instance of the class."""
		assert isinstance(site, W3Site)
		super(W3GraphDocument, self).__init__(site, '%s.svg' % dbobject.identifier)
		self.dbobject_map = {}
		self.dbobject = dbobject
		self.site.graph_map[dbobject] = self
	
	def create_graph(self):
		# Override in descendent classes to generate nodes, edges, etc. in the
		# graph
		pass

	def create_content(self):
		# Call the inherited method in case it does anything
		super(W3GraphDocument, self).create_content()
		# Call create_graph to create the content of the graph
		self.create_graph()
		# Tweak some of the graph attributes to make it scale a bit more nicely
		self.graph.rankdir = 'LR'
		self.graph.dpi = '75'
		self.graph.ratio = '1.5' # See width and height attributes in img_of()
		# Transform dbobject attributes on Node, Edge and Cluster objects into
		# URL attributes 

		def rewrite_url(node):
			if isinstance(node, (Node, Edge, Cluster)) and hasattr(node, 'dbobject'):
				node.URL = self.site.document_map[node.dbobject].url

		def rewrite_font(node):
			if isinstance(node, (Node, Edge, Cluster)):
				node.fontname = 'Verdana'

		self.graph.touch(rewrite_url)
		self.graph.touch(rewrite_font)

	def write(self):
		# Overridden to add logging
		logging.debug('Writing graph for %s %s to %s' % (self.dbobject.type_name, self.dbobject.name, self.filename))
		super(W3GraphDocument, self).write()
	
	def add_dbobject(self, dbobject, selected=False):
		"""Utility method to add a database object to the graph.

		This utility method adds the specified database object along with
		standardized formatting depending on the type of the object.
		"""
		assert isinstance(dbobject, DocBase)
		o = self.dbobject_map.get(dbobject, None)
		if o is None:
			if isinstance(dbobject, Schema):
				o = Cluster(self.graph, dbobject.qualified_name)
				o.label = dbobject.name
				o.style = 'filled'
				o.fillcolor = '#ece6d7'
				o.color = '#ece6d7'
			elif isinstance(dbobject, Relation):
				cluster = self.add_dbobject(dbobject.schema)
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
				cluster = self.add_dbobject(dbobject.schema)
				o = Node(cluster, dbobject.qualified_name)
				o.shape = 'hexagon'
				o.style = 'filled'
				o.fillcolor = '#ffbbbb'
				o.label = dbobject.name
			if selected:
				o.style += ',setlinewidth(3)'
			o.dbobject = dbobject
			self.dbobject_map[dbobject] = o
		return o
