# vim: set noet sw=4 ts=4:

import re
import datetime

tex_special = re.compile(ur'([#$%^&_{}~/\\\u00A0]|\.\.\.)')
def escape_tex(s):
	def subfn(m):
		m = m.group(0)
		return {
			'#':       r'\#',
			'$':       r'\$',
			'%':       r'\%',
			'^':       r'\^{}',
			'&':       r'\&',
			'_':       r'\_',
			'{':       r'\{',
			'}':       r'\}',
			'~':       r'\~',
			'/':       format_cmd('slash'),
			'\\':      format_cmd('textbackslash'),
			'...':     format_cmd('ldots'),
			u'\u00A0': '~',
		}[m]
	return tex_special.sub(subfn, s)

def escape_xml(s):
	return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

def format_cmd(name, content='', options=''):
	if content:
		return r'\%s%s{%s}' % (name, options, content)
	else:
		return r'\%s%s ' % (name, options)

def format_env(name, content='', params=''):
	return '\n'.join((
		r'\begin{%s}%s' % (name, params),
		content,
		r'\end{%s}' % name,
	))

def xml(e, **args):
	return e.__xml__(**args)

def tex(e, **args):
	return e.__tex__(**args)


# Abstract classes

class TeXNode(object):
	__slots__ = ()
	def __tex__(self):
		return ''
	def __xml__(self):
		return ''

class TeXParam(TeXNode):
	__slots__ = ('index',)
	def __init__(self, index=1):
		self.index = index
	def __tex__(self):
		return '#%d' % self.index
	def __xml__(self):
		return escape_xml('#%d' % self.index)

class TeXEmptyElement(TeXNode):
	__slots__ = ('tail',)
	def __init__(self):
		super(TeXEmptyElement, self).__init__()
		self.tail = ''
	def __tex__(self):
		return super(TeXEmptyElement, self).__tex__() + escape_tex(self.tail)
	def __xml__(self):
		return super(TeXEmptyElement, self).__xml__() + escape_xml(self.tail)

class TeXHyphen(TeXEmptyElement):
	__slots__ = ()
	tag = 'hyp'
	tex_cmd = '-'
	def __tex__(self):
		return r'\-' + super(TeXHyphen, self).__tex__()
	def __xml__(self):
		return '-' + super(TeXHyphen, self).__xml__()

class TeXBreak(TeXEmptyElement):
	__slots__ = ()
	tag = 'br'
	tex_cmd = r'\\'
	def __tex__(self):
		return '\\\\\n' + super(TeXBreak, self).__tex__()
	def __xml__(self):
		return '<br/>' + super(TeXBreak, self).__xml__()

class TeXContent(TeXNode):
	__slots__ = ('text',)
	def __init__(self, text=''):
		self.text = text
	def __tex__(self):
		return escape_tex(self.text)
	def __xml__(self):
		return escape_xml(self.text)

class TeXElement(TeXContent):
	__slots__= ('name', 'tail', 'children')
	def __init__(self, name=None):
		super(TeXElement, self).__init__()
		self.name = name or self.tex_cmd
		self.tail = ''
		self.children = []
	def _attrib(self):
		def attrs(c):
			if hasattr(c, '__slots__'):
				result = set(c.__slots__)
			elif hasattr(c, '__dict__'):
				result = set(c.__dict__.iterkeys())
			else:
				result = set()
			for b in c.__bases__:
				if b is not TeXElement and b is not TeXEnvironment:
					result |= attrs(b)
			return result
		return dict((a, getattr(self, a)) for a in attrs(self.__class__))
	def _content_tex(self):
		return escape_tex(self.text) + ''.join(tex(child) for child in self.children)
	def _content_xml(self):
		return escape_xml(self.text) + ''.join(xml(child) for child in self.children)
	def __tex__(self):
		return format_cmd(self.name, self._content_tex()) + escape_tex(self.tail)
	def __xml__(self):
		def format_value(name, value):
			if value is not None:
				if isinstance(value, bool):
					if value:
						return name
				elif name == 'color': # Dirty hack
					return hex(value)
				else:
					return str(value)
		content = self._content_xml()
		attrs = ''.join(
			' %s="%s"' % (name, format_value(name, value))
			for (name, value) in self._attrib().iteritems()
			if format_value(name, value) is not None
		)
		if content:
			return '<%s%s>%s</%s>%s' % (
				self.tag,
				attrs,
				content,
				self.tag,
				escape_xml(self.tail),
			)
		else:
			return '<%s%s/>' % (
				self.tag,
				attrs,
			)

class TeXEnvironment(TeXElement):
	__slots__ = ()
	def __init__(self, name=None):
		super(TeXEnvironment, self).__init__(name or self.tex_env)
	def _params(self):
		return ''
	def __tex__(self):
		return format_env(self.name, self._content_tex(), self._params()) + escape_tex(self.tail)


# Concrete classes

class TeXParagraph(TeXElement):
	__slots__ = ()
	tag = 'p'
	tex_cmd = 'par'
	def __tex__(self):
		return '%s\n\n%s' % (self._content_tex(), escape_tex(self.tail))

class TeXQuote(TeXElement):
	__slots__ = ()
	tag = 'q'
	tex_cmd = 'quote'
	def __tex__(self):
		return "``%s''%s" % (self._content_tex(), escape_tex(self.tail))

class TeXAnchor(TeXElement):
	__slots__ = ('id', 'href')
	tag = 'a'
	tex_cmd = 'label'
	def __init__(self, id='', href=''):
		super(TeXAnchor, self).__init__()
		self.id = id
		self.href = href
	def __tex__(self):
		result = []
		# Note: deliberately not escaping id or href
		if self.id:
			result.append(format_cmd('label', self.id))
		if self.href:
			if self.href.startswith('http:') or self.href.startswith('https:') or self.href.startswith('ftp:'):
				result.append(format_cmd('href', self._content_tex(), options='{%s}' % self.href))
			else:
				result.append(format_cmd('hyperref', self._content_tex(), options='[%s]' % self.href))
		return '\n'.join(result)

class TeXPageOf(TeXElement):
	__slots__ = ('href',)
	tag = 'page'
	tex_cmd = 'pageref'
	def __init__(self, href=''):
		super(TeXPageOf, self).__init__()
		self.href = href
	def __tex__(self):
		return format_cmd('pageref', self.href)

class TeXBlockQuote(TeXEnvironment):
	__slots__ = ()
	tag = 'blockquote'
	tex_env = 'quote'

class TeXStrong(TeXElement):
	__slots__ = ()
	tag = 'strong'
	tex_cmd = 'textbf'

class TeXB(TeXStrong):
	__slots__ = ()
	tag = 'b'

class TeXEmphasis(TeXElement):
	__slots__ = ()
	tag = 'em'
	tex_cmd = 'emph'

class TeXI(TeXEmphasis):
	__slots__ = ()
	tag = 'i'

class TeXUnderline(TeXElement):
	__slots__ = ()
	tag = 'u'
	tex_cmd = 'uline'

class TeXStrikeOut(TeXElement):
	__slots__ = ()
	tag = 'strike'
	tex_cmd = 'sout'

class TeXS(TeXStrikeOut):
	__slots__ = ()
	tag = 's'

class TeXSuperScript(TeXElement):
	__slots__ = ()
	tag = 'sup'
	tex_cmd = 'textsuperscript'

class TeXSubScript(TeXElement):
	__slots__ = ()
	tag = 'sub'
	tex_cmd = 'textsubscript'

class TeXHRule(TeXElement):
	__slots__ = ()
	tag = 'hr'
	tex_cmd = 'hrule'
	def __tex__(self):
		return r'{\vskip 8pt\hrule height.2pt\vskip 8pt}'

class TeXSmall(TeXElement):
	__slots__ = ()
	tag = 'small'
	tex_cmd = 'small'

class TeXBig(TeXElement):
	__slots__ = ()
	tag = 'big'
	tex_cmd = 'large'

class TeXTeleType(TeXElement):
	__slots__ = ()
	tag = 'tt'
	tex_cmd = 'texttt'

class TeXPreformatted(TeXEnvironment):
	__slots__ = ()
	tag = 'pre'
	tex_env = 'verbatim'

class TeXFont(TeXElement):
	__slots__ = ('size', 'color', 'face')
	tag = 'font'
	tex_cmd = 'font'
	def __init__(self, size=None, color=None, face=None):
		super(TeXFont, self).__init__()
		self.size = size # 1-7
		self.color = color # 0x00RRGGBB
		self.face = face # 'serif', 'roman', 'sans', 'sans-serif', 'teletype', 'monospace'
	def __tex__(self):
		result = self._content_tex()
		if self.size is not None:
			result = format_cmd({
				1: 'tiny',
				2: 'small',
				3: 'normalsize',
				4: 'large',
				5: 'Large',
				6: 'LARGE',
				7: 'huge',
			}[self.size], result)
		if self.color is not None:
			result = format_cmd('textcolor', result, options='{color%06x}' % self.color)
		if self.face is not None:
			result = format_cmd({
				'serif':      'textrm',
				'roman':      'textrm',
				'sans':       'textsf',
				'sans-serif': 'textsf',
				'teletype':   'texttt',
				'monospace':  'texttt',
			}[self.face.lower()], result)
		return result + escape_tex(self.tail)

class TeXListItem(TeXElement):
	__slots__ = ()
	tag = 'li'
	tex_cmd = 'item'
	def __tex__(self):
		return '\n%s%s%s' % (format_cmd(self.name), self._content_tex(), escape_tex(self.tail))

class TeXUnorderedList(TeXEnvironment):
	__slots__ = ()
	tag = 'ul'
	tex_env = 'itemize'

class TeXOrderedList(TeXEnvironment):
	__slots__ = ()
	tag = 'ol'
	tex_env = 'enumerate'

class TeXDefinitionItem(TeXElement):
	__slots__ = ('term',)
	tag = 'di'
	tex_cmd = 'item'
	def __init__(self, term=''):
		super(TeXDefinitionItem, self).__init__()
		self.term = term
	def __tex__(self):
		return '\n%s%s%s' % (
			format_cmd(self.name, options='[%s]' % escape_tex(self.term)),
			self._content_tex(),
			escape_tex(self.tail)
		)

class TeXDefinitionList(TeXEnvironment):
	__slots__ = ()
	tag = 'dl'
	tex_env = 'description'

class TeXTableOfContents(TeXElement):
	__slots__ = ('level')
	tag = 'toc'
	tex_cmd = 'tableofcontents'
	def __init__(self, level=3):
		super(TeXTableOfContents, self).__init__()
		self.level = level

class TeXTableOfFigures(TeXElement):
	__slots__ = ()
	tag = 'tof'
	tex_cmd = 'listoffigures'

class TeXTableOfTables(TeXElement):
	__slots__ = ()
	tag = 'tot'
	tex_cmd = 'listoftables'

class TeXIndexKey(TeXElement):
	__slots__ = ()
	tag = 'key'
	tex_cmd = 'index'

class TeXIndex(TeXElement):
	__slots__ = ()
	tag = 'index'
	tex_cmd = 'printindex'

class TeXTable(TeXEnvironment):
	__slots__ = ('align', 'id')
	tag = 'table'
	tex_env = 'longtable'
	def __init__(self, align='left', id=None):
		super(TeXTable, self).__init__()
		try:
			self.align = {
				'l':      'left',
				'left':   'left',
				'r':      'right',
				'right':  'right',
				'c':      'center',
				'center': 'center',
			}[align.strip().lower()]
		except KeyError:
			raise ValueError('invalid table alignment "%s"' % align)
		self.id = id
	def _params(self):
		return '[%s]{@{}%s@{}}' % (
			self.align[0],
			''.join(
				tex(child)
				for child in self.children
				if isinstance(child, TeXTableColumn)
			)
		)
	def _content_tex(self):
		result = []
		caption = [child for child in self.children if isinstance(child, TeXTableCaption)]
		thead = [child for child in self.children if isinstance(child, TeXTableHeader)]
		tfoot = [child for child in self.children if isinstance(child, TeXTableFooter)]
		tbody = [
			child for child in self.children
			if isinstance(child, TeXTableBody)
			and not isinstance(child, TeXTableHeader)
			and not isinstance(child, TeXTableFooter)
		]
		if len(thead) == 0:
			# If there's no thead or tfoot elements, make up blank ones (this
			# ensures that when generating longtables the endhead and endfoot
			# elements are always written which is necessary to prevent the
			# occassional page split immediately after a top rule or before a
			# bottom rule when using the booktabs package)
			thead = [TeXTableHeader()]
		elif len(thead) > 1:
			raise ValueError('more than one table header element found')
		if len(tfoot) == 0:
			tfoot = [TeXTableFooter()]
		elif len(tfoot) > 1:
			raise ValueError('more than one table footer element found')
		if len(tbody) == 0:
			# If there's no tbody element, make one up from all row elements
			# that are direct children (i.e. make an implicit tbody element,
			# like in HTML)
			tbody = [TeXTableBody()]
			tbody[0].children.extend(
				row for row in self.children
				if isinstance(row, TeXTableRow)
			)
		# Generate the table caption and anchor (XXX id only gets included if
		# caption is specified - unfortunately trying to include it without the
		# caption invariably leads to unwanted blank lines somewhere)
		if caption:
			result.append(tex(caption[0]))
			if self.id:
				result.append(format_cmd('label', self.id)) # Note: deliberately not escaping id
			result.append(r'\\')
		result.append(tex(thead[0]))
		result.append(tex(tfoot[0]))
		result.append(tex(tbody[0]))
		return '\n'.join(result)
	def __tex__(self):
		result = []
		result.append(super(TeXTable, self).__tex__())
		return '\n'.join(result)

class TeXTableCaption(TeXElement):
	__slots__ = ()
	tag = 'caption'
	tex_cmd = 'caption'

class TeXTableBody(TeXEnvironment):
	__slots__ = ()
	tag = 'tbody'
	tex_env = 'tablebody'
	def _empty(self):
		return len(list(self._rows())) == 0
	def _rows(self, nobreakall=False):
		return (
			# Prevent page breaks in the first and last couple of rows
			tex(row, nobreak=nobreakall or not (2 < i < len(self.children) - 2))
			for (i, row) in enumerate(self.children)
			if isinstance(row, TeXTableRow)
		)
	def __tex__(self):
		return '\n'.join(self._rows())

class TeXTableHeader(TeXTableBody):
	__slots__ = ()
	tag = 'thead'
	tex_env = 'tablehead'
	def __tex__(self, longtable=True):
		result = []
		result.append(format_cmd('toprule'))
		if not self._empty():
			result.extend(self._rows())
			result.append(format_cmd('midrule'))
		if longtable:
			result.append(format_cmd('endfirsthead'))
			if not self._empty():
				result.extend(self._rows())
				result.append(format_cmd('midrule'))
			result.append(format_cmd('endhead'))
		return '\n'.join(result)

class TeXTableFooter(TeXTableBody):
	__slots__ = ()
	tag = 'tfoot'
	tex_env = 'tablefoot'
	def __tex__(self, longtable=True):
		result = []
		if longtable:
			if not self._empty():
				result.append(format_cmd('midrule'))
				result.extend(self._rows())
			result.append(format_cmd('endfoot'))
		if not self._empty():
			result.append(format_cmd('midrule'))
			result.extend(self._rows())
		result.append(format_cmd('bottomrule'))
		if longtable:
			result.append(format_cmd('endlastfoot'))
		return '\n'.join(result)

class TeXTableColumn(TeXElement):
	__slots__ = ('align', 'nowrap', 'width')
	tag = 'col'
	tex_cmd = 'tablespec'
	def __init__(self, align='left', nowrap=True, width=None):
		super(TeXTableColumn, self).__init__()
		try:
			self.align = {
				'l':      'left',
				'left':   'left',
				'r':      'right',
				'right':  'right',
				'c':      'center',
				'center': 'center',
			}[align.strip().lower()]
		except KeyError:
			raise ValueError('invalid align value "%s"' % align)
		self.nowrap = bool(nowrap)
		self.width = width
		if self.nowrap:
			if self.width is not None:
				raise ValueError('invalid width; non-wrappable columns are always auto-sized')
		else:
			if self.align != 'left':
				raise ValueError('invalid align; wrappable columns must be left-aligned')
			if self.width is None:
				raise ValueError('missing width; wrappable columns must have a width')
	def __tex__(self):
		if self.nowrap:
			return {
				'left':   'l',
				'right':  'r',
				'center': 'c',
			}[self.align]
		else:
			return 'p{%s}' % self.width

class TeXTableRow(TeXElement):
	__slots__ = ()
	tag = 'tr'
	tex_cmd = 'tablerow'
	def __tex__(self, nobreak=False):
		template = r'%s \\*' if nobreak else r'%s \\'
		return template % ' & '.join(
			tex(cell)
			for cell in self.children
			if isinstance(cell, TeXTableCell)
		)

class TeXTableCell(TeXElement):
	__slots__ = ()
	tag = 'td'
	tex_cmd = 'tablecell'
	def __tex__(self):
		# rstrip the content to avoid an extraneous paragraph break
		return self._content_tex().rstrip() + escape_tex(self.tail)

class TeXTableHeaderCell(TeXTableCell):
	__slots__ = ()
	tag = 'th'
	tex_cmd = 'tablehead'
	def __tex__(self):
		# rstrip the content to avoid an extraneous paragraph break
		return format_cmd('textbf', self._content_tex().rstrip()) + escape_tex(self.tail)

class TeXTitle(TeXElement):
	__slots__ = ()
	tag = 'title'
	tex_cmd = 'title'

class TeXAuthor(TeXElement):
	__slots__ = ()
	tag = 'author'
	tex_cmd = 'author'

class TeXDate(TeXElement):
	__slots__ = ()
	tag = 'date'
	tex_cmd = 'date'

class TeXMakeTitle(TeXElement):
	__slots__ = ()
	tag = 'maketitle'
	tex_cmd = 'maketitle'

class TeXTopMatter(TeXElement):
	__slots__ = ('title', 'author_name', 'author_email', 'date')
	tag = 'topmatter'
	tex_cmd = 'topmatter'
	def __init__(self, title='', author_name='', author_email='', date=None):
		super(TeXTopMatter, self).__init__()
		self.title = title
		self.author_name = author_name
		self.author_email = author_email
		self.date = date
	def __tex__(self):
		result = []
		result.append(TeXTitle())
		result[-1].text = self.title
		if self.author_name:
			result.append(TeXAuthor())
			result[-1].text = self.author_name
			if self.author_email:
				result[-1].children.append(TeXBreak())
				email = TeXTeleType()
				email.text = self.author_email
				result[-1].children.append(email)
		if self.date:
			result.append(TeXDate())
			result[-1].text = str(self.date)
		result.append(TeXMakeTitle())
		return '\n'.join(tex(elem) for elem in result)

class TeXSection(TeXEnvironment):
	__slots__ = ('title', 'toc_title', 'toc_include', 'id')
	tag = 'section'
	tex_env = 'section'
	def __init__(self, title='', toc_title=None, toc_include=True, id=None):
		super(TeXSection, self).__init__()
		self.title = title
		self.toc_title = toc_title
		self.toc_include = toc_include
		self.id = id
	def __tex__(self):
		result = ['', ''] # leave a couple of blank links before a new (sub)section
		# Break the page before top level sections
		if type(self) == TeXSection:
			result.append(format_cmd('newpage'))
		if not self.toc_include:
			options = '*'
		elif self.toc_title:
			options = '[%s]' % escape_tex(self.toc_title)
		else:
			options = ''
		result.append(format_cmd(self.name, escape_tex(self.title), options=options))
		if self.id:
			result.append(format_cmd('label', self.id)) # Note: deliberately not escaping id
		result.append(self._content_tex())
		result.append(escape_tex(self.tail))
		return '\n'.join(result)

class TeXSubSection(TeXSection):
	__slots__ = ()
	tag = 'subsection'
	tex_env = 'subsection'

class TeXSubSubSection(TeXSection):
	__slots__ = ()
	tag = 'subsubsection'
	tex_env = 'subsubsection'

class TeXCustomCommand(TeXElement):
	__slots__ = ()
	# See TeXFactory._new_command()

class TeXCustomEnvironment(TeXEnvironment):
	__slots__ = ()
	# See TeXFactory._new_environment()


class TeXDocument(TeXEnvironment):
	tag = 'document'
	tex_env = 'document'

	def __init__(self, doc_class='article', encoding='utf8x', font_packages=[],
			font_size=10, paper_size='a4paper', landscape=False, twoside=False,
			margin_size=None, binding_size=None, bookmarks=True, doc_title='',
			author_name='', author_email='', subject='', keywords=[],
			creator=''):
		super(TeXDocument, self).__init__()
		self.author_email = author_email
		self.author_name = author_name
		self.binding_size = binding_size
		self.bookmarks = bookmarks
		self.colors = None # see TeXFactory.font()
		self.commands = None # see TeXFactory._new_command()
		self.creator = creator
		self.doc_class = doc_class
		self.doc_title = doc_title
		self.encoding = encoding
		self.environments = None # see TeXFactory._new_environment()
		self.font_packages = font_packages
		self.font_size = font_size
		self.keywords = ','.join(keywords)
		self.landscape = landscape
		self.margin_size = margin_size
		self.paper_size = paper_size
		self.subject = subject
		self.twoside = twoside

	def _find(self, elem_class, root=None):
		# Recursively searches the tree for elements of the specified class,
		# and yields them as a generator
		if not root:
			root = self
		if isinstance(root, TeXElement):
			# Do a hybrid of a DFS and BFS search (performance optimization -
			# specifically helps with the makeindex search)
			for elem in root.children:
				if isinstance(elem, elem_class):
					yield elem
			for elem in root.children:
				for result in self._find(elem_class, elem):
					yield result
		if isinstance(root, elem_class):
			yield root

	def _packages(self):
		# Yields package names and/or tuples of (package_name, package_options)
		if self.encoding == 'utf8x':
			self.uses_unicode = True # see _preamble()
			yield 'ucs'
		yield ('inputenc', '[%s]' % self.encoding) # Encoding must be as early as possible
		options = []
		if isinstance(self.paper_size, basestring):
			options.append('paper=%s' % self.paper_size)
		elif isinstance(self.paper_size, tuple):
			options.append('paper_size={%s,%s}' % self.paper_size)
		if self.landscape:
			options.append('landscape')
		if self.twoside:
			options.append('twoside')
		if self.margin_size:
			if isinstance(self.margin_size, tuple):
				if len(self.margin_size) == 4:
					for k, v in zip(('top', 'right', 'bottom', 'left'), self.margin_size):
						options.append('%s=%s' % (k, v))
				elif len(self.margin_size) == 2:
					for k, v in zip(('vmargin', 'hmargin'), self.margin_size):
						options.append('%s=%s' % (k, v))
				elif len(self.margin_size) == 1:
					options.append('margin=%s' % self.margin_size)
				else:
					raise ValueError('margin_size must contain 1, 2, or 4 elements')
		if self.binding_size:
			options.append('bindingoffset=%s' % self.binding_size)
		yield ('geometry', '[%s]' % ','.join(options))
		yield 'fixltx2e'
		yield 'color'
		for p in self.font_packages:
			yield p
		if any(self._find(TeXUnderline)):
			self.uses_underline = True # see _preamble()
			yield 'ulem'
		for elem in self._find(TeXTableOfContents):
			self.uses_toc = True # see _preamble()
			self.toc_level = elem.level
			break
		if any(self._find(TeXIndex)):
			self.uses_index = True # see _preamble()
			yield 'makeidx'
		if any(self._find(TeXTable)):
			yield 'longtable'
			yield 'booktabs'
		options = ['font=small', 'labelfont=bf']
		yield ('caption', '[%s]' % ','.join(options))
		options = ['bookmarks=%s' % str(self.bookmarks).lower()]
		if self.encoding == 'utf8x':
			options.append('unicode=true')
		yield ('hyperref', '[%s]' % ','.join(options)) # Must be last ... because

	def _preamble(self):
		self.toc_level = 3
		self.uses_toc = False
		self.uses_index = False
		self.uses_underline = False
		self.uses_unicode = False
		# Start with the document class
		yield format_cmd('documentclass', self.doc_class, '[%s]' % self.font_size)
		# Add all the packages, then deal with preamble options
		for package in self._packages():
			if not isinstance(package, basestring):
				package, options = package
			else:
				options = ''
			yield format_cmd('usepackage', package, options)
		# Configure the hyperref package (note: bookmarks and unicode are dealt
		# with in _packages())
		options = [
			'colorlinks=true',
			'linkcolor=black',
			'citecolor=black',
			'filecolor=blue',
			'urlcolor=blue',
		]
		if self.doc_title:
			options.append('pdftitle={%s}' % escape_tex(self.doc_title))
		if self.author_name or self.author_email:
			if self.author_name and self.author_email:
				author = '%s <%s>' % (self.author_name, self.author_email)
			else:
				author = self.author_name or self.author_email
			options.append('pdfauthor={%s}' % escape_tex(author))
		if self.subject:
			options.append('pdfsubject={%s}' % escape_tex(self.subject))
		if self.keywords:
			options.append('pdfkeywords={%s}' % escape_tex(self.keywords))
		if self.creator:
			options.append('pdfcreator={%s}' % escape_tex(self.creator))
		yield format_cmd('hypersetup', ',%'.join('\n    ' + option for option in options))
		# Define all the custom style commands and environments
		if self.commands:
			for name, definition in self.commands.iteritems():
				yield '%s[1]{%s}' % (
					format_cmd('newcommand', '\\' + name),
					tex(definition(TeXParam(1)))
				)
		if self.environments:
			for name, (prefix, suffix, preamble) in self.environments.iteritems():
				yield '%s\n%s%%\n{%s}%%\n{%s}' % (
					preamble,
					format_cmd('newenvironment', name),
					prefix,
					suffix
				)
		# Define all the custom colors (must be done after styles to ensure
		# font calls in the styles have registered their colors before this
		# point)
		if self.colors:
			for name, color in self.colors.iteritems():
				yield '%s{rgb}{%f,%f,%f}' % (
					format_cmd('definecolor', name),
					float((color & 0xFF0000) >> 16) / 0xFF,
					float((color & 0x00FF00) >>  8) / 0xFF,
					float((color & 0x0000FF) >>  0) / 0xFF,
				)
		# Generate the index auxilliary file
		if self.uses_index:
			yield format_cmd('makeindex')
		# Set the depth counter
		if self.uses_toc:
			yield format_cmd('setcounter', str(self.toc_level), '{tocdepth}')

	def _content_tex(self):
		result = super(TeXDocument, self)._content_tex()
		if self.uses_underline:
			result = '\n'.join((format_cmd('normalem'), result))
		return result

	def __tex__(self):
		# Generate the preamble and document content, then encode the whole lot
		# appropriately
		result = [line for line in self._preamble()]
		result.append(super(TeXDocument, self).__tex__())
		if self.uses_unicode:
			codec_name = 'utf-8'
		else:
			codec_name = self.encoding
		return '\n'.join(result).encode(codec_name)


# Build a mapping of tags to element classes, to be used by the initializer of
# the factory class below. This isn't done in the initializer as the available
# classes are not expected to change
tag_map = dict(
	(c.tag, c) for c in locals().itervalues()
	if type(c) == type(object)
	and issubclass(c, TeXNode)
	and hasattr(c, 'tag')
)

class TeXFactory(object):
	def __init__(self):
		self._custom_colors = {}
		self._custom_commands = {}
		self._custom_environments = {}

	def _format(self, content):
		"""Reformats content into a human-readable string"""
		if isinstance(content, basestring):
			# Strings (including unicode) are returned verbatim
			return content
		else:
			# Everything else is converted to an ASCII string
			return str(content)

	def _append(self, node, contents):
		"""Adds content (string, node, node-list, etc.) to a node"""
		if isinstance(contents, basestring):
			if contents != '':
				if len(node.children) == 0:
					node.text += contents
				else:
					last = node.children[-1]
					last.tail += contents
		elif isinstance(contents, (int, long, bool, datetime.datetime, datetime.date, datetime.time)):
			# XXX This branch exists for optimization purposes only (the except
			# branch below is moderately expensive)
			self._append(node, self._format(contents))
		elif isinstance(contents, TeXNode):
			if isinstance(contents, (TeXElement, TeXEmptyElement)):
				contents.tail = ''
			node.children.append(contents)
		else:
			try:
				for content in contents:
					self._append(node, content)
			except TypeError:
				self._append(node, self._format(contents))

	def _element(self, _class, *contents, **attrs):
		elem = _class(**attrs)
		for content in contents:
			self._append(elem, content)
		return elem

	def _new_command(self, name, definition):
		if name in tag_map:
			raise KeyError('command "%s" is a standard command' % name)
		if name in self._custom_commands:
			raise KeyError('command "%s" has already been defined' % name)
		# Store the definition of the new command. Documents constructed by
		# this factory will inherit these definitions (the document generator
		# method below sets the document's style attribute to _custom_commands)
		self._custom_commands[name] = definition
		# Generate the class for the command and attach a new generator method
		# for it to this class. Note that the class will literally output
		# elements of the new command, not its definition
		elem_class = type('TeX%s' % name, (TeXCustomCommand,), {
			'tag':     name,
			'tex_cmd': name,
		})
		def generator(*content, **attrs):
			return self._element(elem_class, *content, **attrs)
		setattr(self, name, generator)

	def _new_environment(self, name, prefix, suffix, preamble=''):
		# It's far too complicated to allow the definition of an environment in
		# the same way we allow commands to be defined (i.e. by a lambda
		# function) so we just accept raw LaTeX to include in the preamble as
		# the environemnt's prefix and suffix
		self._custom_environments[name] = (prefix, suffix, preamble)
		env_class = type('TeX%s' % name, (TeXCustomEnvironment,), {
			'tag':     name,
			'tex_env': name,
		})
		def generator(*content, **attrs):
			return self._element(env_class, *content, **attrs)
		setattr(self, name, generator)

	def __getattr__(self, name):
		elem_name = name.rstrip('_')
		try:
			elem_class = tag_map[elem_name]
		except KeyError:
			raise AttributeError('unknown element "%s"' % elem_name)
		def generator(*content, **attrs):
			return self._element(elem_class, *content, **attrs)
		setattr(self, name, generator)
		return generator

	def document(self, *content, **attrs):
		# Give the document a reference to all the custom commands and colors
		# defined (see _new_command() and font() for more details)
		elem = self._element(TeXDocument, *content, **attrs)
		elem.colors = self._custom_colors
		elem.commands = self._custom_commands
		elem.environments = self._custom_environments
		return elem

	def font(self, *content, **attrs):
		elem = self._element(TeXFont, *content, **attrs)
		if 'color' in attrs:
			color = attrs['color']
			self._custom_colors['color%06x' % color] = color
		return elem
