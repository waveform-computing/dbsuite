#!/bin/env python
# $Header$
# vim: set noet sw=4 ts=4:

"""Implements an SQL syntax highlighter based on the output of a tokenizer.

This unit implements a configurable SQL syntax highlighter based on the
tokenizers in the sqltokenizer unit. The highlighter currently outputs a
fragment of HTML/XHTML using span elements to mark up the SQL with CSS classes,
but this could be easily extended to other markup languages. The reason it does
not output a full document is that this raises too many questions (which
version of HTML, how should the CSS rules be included, what's the title of the
document, etc); it's up to you to wrap the output in an HTML document.

Two highlighter classes are implemented: SQLHTMLHighlighter which returns the
generated HTML as a string (basically a mess of <span> elements and content),
and SQLDOMHighlighter which generates a list of DOM nodes (belonging to the
specified document but without a parent) which you can then splice into the
document tree.

To use the highlighter, construct an instance of either class, then call the
parse method passing the output of a tokenizer from the sqltokenizer unit, i.e.
a list of token tuples (or a list of lists of token tuples if newline_split was
active on the tokenizer).

The following attributes can be used to control the output of the highlighter:

    Attribute      Description
    ----------------------------------------------------------------
    css_classes    A dictionary mapping token types (see the
                   sqltokenizer unit) to the name of a CSS class. If
                   a token type does not appear in the dictionary,
                   the corresponding source is not highlighted. See
                   below for more on mapping of token types.
    number_lines   If True, the highlighter output the line number
                   before each line of output by formatting the
                   output into a two-column table (left-hand column
                   used for line numbers, right hand for code).
                   Defaults to False. See below for additional
                   details.
    number_class   If number_lines is True, this is the class used
                   for the cells containing line numbers. Defaults
                   to 'num_cell'.
    sql_class      If number_lines is True, this is the class used
                   for the cells containing SQL (in the right hand
                   column). Defaults to 'sql_cell'.

If number_lines is True, the output is formatted as an incomplete table. That
is, row and data cells are output, but no table, thead or tbody tags allowing
you to format the table however you wish, add a caption, define column headers,
etc. The structure of the columns is as follows:

    +--------+------------------------------------------+
    | Line # | Code                                     |
    +--------+------------------------------------------+
    | Line # | Code                                     |
    +--------+------------------------------------------+
    | Line # | Code                                     |
    +--------+------------------------------------------+

This ensures that line numbers always appear to the left of a line of code, and
that if code happens to wrap due to width limitations, the line numbers still
line up and are not "interrupted" by the wrapped code.

Mapping of tokens to CSS classes is highly configurable. The default
configuration (in the global default_css_classes variable) simply maps some
basic token types to CSS class names (excluding WHITESPACE which generally
doesn't need highlighting (though you are free to add a mapping for it if you
wish).

However, you can also use (token_type, token_value) tuples in the css_classes
dictionary attribute to refine the mapping further. For example:

    highlighter.css_classes = {
        OPERATOR: 'sql_operator',
        (OPERATOR, '+'): 'sql_mathop',
        (OPERATOR, '-'): 'sql_mathop',
        (OPERATOR, '*'): 'sql_mathop',
        (OPERATOR, '/'): 'sql_mathop',
        (OPERATOR, '.'): None
    }

Such a mapping would use the 'sql_mathop' CSS class for the four basic
mathematical operators (plus, minus, multiply, divide), and the 'sql_operator'
CSS class for all other operators (parentheses, etc).  If a CSS class is set to
None, it is as if the token had no mapping, that is, the source code for the
token will not be highlighted. Thus, in the example above, the name qualifier
operator (.) will not be highlighted.
"""

import xml.dom
from xml.sax.saxutils import quoteattr, escape
from tokenizer import *
from formatter import *

default_css_classes = {
	ERROR:      'sql_error',
	COMMENT:    'sql_comment',
	KEYWORD:    'sql_keyword',
	IDENTIFIER: 'sql_identifier',
	DATATYPE:   'sql_datatype',
	REGISTER:   'sql_register',
	NUMBER:     'sql_number',
	STRING:     'sql_string',
	OPERATOR:   'sql_operator',
	PARAMETER:  'sql_parameter',
	TERMINATOR: 'sql_terminator',
	STATEMENT:  'sql_terminator',
}

class SQLHTMLHighlighter(object):
	def __init__(self):
		super(SQLHTMLHighlighter, self).__init__()
		self.css_classes = default_css_classes
		self.number_lines = False
		self.number_class = 'num_cell'
		self.sql_class = 'sql_cell'

	def _format_token(self, token):
		(token_type, token_value, source, _, _) = token
		try:
			css_class = self.css_classes[(token_type, token_value)]
		except KeyError:
			css_class = self.css_classes.get(token_type, None)
		if css_class is not None:
			return '<span class=%s>%s</span>' % (
				quoteattr(css_class),
				escape(source)
			)
		else:
			return escape(source)

	def _format_line(self, linetokens):
		# The following relies on the fact that there is guaranteed to
		# be at least one token per line (at a minimum it will be a
		# WHITESPACE token containing a newline character)
		return "<tr><td class=%s>%d</td><td class=%s>%s</td></tr>" % (
			quoteattr(self.number_class),
			linetokens[0][3], # line number
			quoteattr(self.sql_class),
			''.join([self._format_token(token) for token in linetokens])
		)

	def parse(self, tokens):
		if isinstance(tokens[0], list):
			# We're dealing with a list of lists of tokens (i.e. the
			# newline_split property of the tokenizer was set when parsing)
			return '\n'.join([self._format_line(line) for line in tokens])
		else:
			return ''.join([self._format_token(token) for token in tokens])

class SQLDOMHighlighter(object):
	def __init__(self):
		super(SQLDOMHighlighter, self).__init__()
		self.css_classes = default_css_classes
		self.number_lines = False
		self.number_class = 'num_cell'
		self.sql_class = 'sql_cell'
	
	def _format_token(self, token, doc):
		(token_type, token_value, source, _, _) = token
		try:
			css_class = self.css_classes[(token_type, token_value)]
		except KeyError:
			css_class = self.css_classes.get(token_type, None)
		if css_class is not None:
			spannode = doc.createElement('span')
			spannode.setAttribute('class', css_class)
			spannode.appendChild(doc.createTextNode(source))
			return spannode
		else:
			return doc.createTextNode(source)

	def _format_line(self, linetokens, doc):
		row = doc.createElement('tr')
		cell1 = doc.createElement('td')
		if self.number_class:
			cell1.setAttribute('class', self.number_class)
		cell2 = doc.createElement('td')
		if self.sql_class:
			cell2.setAttribute('class', self.sql_class)
		row.appendChild(cell1)
		row.appendChild(cell2)
		for token in linetokens:
			cell2.appendChild(self._format_token(token))
		return row
		
	def parse(self, tokens, document):
		assert document.nodeType == xml.dom.Node.DOCUMENT_NODE
		# Return a sequence of nodes with no parent (for the caller to splice
		# into the document tree)
		if isinstance(tokens[0], list):
			return [self._format_line(line, document) for line in tokens]
		else:
			return [self._format_token(token, document) for token in tokens]

if __name__ == "__main__":
	pass
