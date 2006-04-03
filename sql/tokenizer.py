#!/bin/env python
# $Header$
# vim: set noet sw=4 ts=4:

"""Implements a highly configurable SQL tokenizer.

This unit implements a configurable SQL tokenizer base class
(SQLTokenizerBase) and several classes descended from this which
implement parsing specific dialects of SQL, and their particular
oddities (like PostgreSQL's $$ quoting mechanism, or MySQL's use of
double-quotes for strings). From the input SQL, the tokenizer classes
output tuples structured as follows:

    (token_type, token_value, source, line, column)

Where token_type is one of the token constants described below,
token_value is the "value" of the token (depends on token_type,
see below), source is the original source code parsed to construct
the token, and line and column provide the 1-based line and column
of the source.

All source elements can be concatenated to reconstruct the original
source verbatim. Hence:

    tokens = SQLTokenizer().tokenize(some_sql)
    some_sql == ''.join([source for (_, _, source, _, _) in tokens])

Depending on token_type, token_value has different values:

    token_type     token_value
    ----------------------------------------------------------------
    EOF            None
    ERROR          A descriptive error message
    WHITESPACE     None
    COMMENT        The content of the comment (excluding delimiters)
    KEYWORD        The keyword folded into uppercase
    IDENTIFIER     The identifier folded into uppercase if it was
                   unquoted in the source, or in original case if
                   it was quoted in some fashion in the source
    NUMBER         The value of the number. In all cases the number
                   is returned as a Decimal to avoid range and
                   rounding problems
    STRING         The content of the string (unquoted and unescaped)
    OPERATOR       The operator
    PARAMETER      The name of the parameter if it was a
                   colon-prefixed named parameter in the source,
                   or None if it was an anonymous ? parameter
    TERMINATOR     None

The base tokenizer also includes several options, primarily to ease
the implementation of the dialect-specific subclasses, though they
may be of use in other situations:

    Attribute      Description
    --------------------------------------------------------------
    keywords       The set of words that are to be treated as
                   reserved keywords.
    identchars     The set of characters that can appear in an
                   unquoted identifier. Note that the parser
                   automatically excludes numerals from this set
                   for the initial character of an identifier.
    newline_split  When False (the default), a list of tokens will
                   be returned by the parse function. When True,
                   any tokens which contain line breaks will be
                   split at those breaks, and the tokens will be
                   returned as a list of a list of tokens (the
                   outer list is organized by lines).
    sql_comments   If True (the default), SQL style comments
                   (--..EOL) will be recognized.
    c_comments     If True, C style comments (/*..*/) will be
                   recognized.  If newline_token is also True,
                   multiline comments will be broken into multiple
                   COMMENT tokens interspersed with NEWLINE
                   tokens. Defaults to False.
    cpp_comments   If True, C++ style comments (//..EOL) will be
                   recognized. Defaults to False.

A number of classes which tokenize specific SQL dialects are derived
from the base SQLTokenizer class. Currently the following classes
are defined:

    Class               Dialect
    --------------------------------------------------------
    SQLTokenizerBase    Base tokenizer class
    SQL92Tokenizer      ANSI SQL-92
    SQL99Tokenizer      ANSI SQL-99
    SQL2003Tokenizer    ANSI SQL-2003
    DB2UDBSQLTokenizer  IBM DB2 UDB for Linux/Unix/Windows 8
    DB2ZOSSQLTokenizer  IBM DB2 UDB for z/OS 8
"""

import sys
import decimal
import dialects

_tokenval = 0

def newToken():
	"""Returns a new token value which is guaranteed to be unique"""
	global _tokenval
	_tokenval += 1
	return _tokenval

def newTokens(count):
	"""Generator function for creating multiple new token values"""
	for i in range(count):
		yield newToken()

# Token constants
(
	EOF,           # End of data
	ERROR,         # Invalid/unknown token
	WHITESPACE,    # Whitespace
	COMMENT,       # A comment
	KEYWORD,       # A reserved keyword (SELECT/UPDATE/INSERT/etc.)
	IDENTIFIER,    # A quoted or unquoted identifier
	NUMBER,        # A numeric literal
	STRING,        # A string literal
	OPERATOR,      # An operator
	PARAMETER,     # A colon-prefixed or simple qmark parameter
	TERMINATOR,    # A statement terminator
) = newTokens(11)

def debugTokens(tokens):
	for (token_type, token_value, source, line, column) in tokens:
		token_type = {
			EOF:        'EOF',
			ERROR:      'ERROR',
			WHITESPACE: 'WHITESPACE',
			COMMENT:    'COMMENT',
			KEYWORD:    'KEYWORD',
			IDENTIFIER: 'IDENTIFIER',
			NUMBER:     'NUMBER',
			STRING:     'STRING',
			OPERATOR:   'OPERATOR',
			PARAMETER:  'PARAMETER',
			TERMINATOR: 'TERMINATOR',
		}[token_type]
		print "(%3d,%3d)  %-10s  %-10s  (%s)" % (line, column, token_type, source, token_value)

class SQLTokenizerBase(object):
	"""Base SQL tokenizer class."""
	
	def __init__(self):
		"""Initializes an instance of the class."""
		self._terminator = ';'
		self._savedhandler = None
		self.keywords = set(dialects.sql92_keywords)
		self.identchars = set(dialects.sql92_identchars)
		self.spacechars = ' \t\r\n'
		self.newline_split = False
		self.sql_comments = True
		self.c_comments = False
		self.cpp_comments = False

	def _addToken(self, tokentype, tokenvalue):
		self._tokens.append((
			tokentype,
			tokenvalue,
			self._source[self._tokenstart:self._index],
			self._tokenline,
			self._tokencolumn
		))
		self._tokenstart = self._index
		self._tokenline = self.line
		self._tokencolumn = self.column

	def _next(self, count=1):
		"""Moves the position of the tokenizer forward count positions.

		The _index variable should never be modified
		directly by handler methods. Likewise, the _source
		variable should never be directly read by handler
		methods. Instead, use the next() method and the char
		and nextchar properties. The next() method keeps
		track of the current line and column positions,
		while the char property handles reporting all line
		breaks (CR, CR/LF, or just LF) as plain LF characters
		(making handler coding easier).
		"""
		while count > 0:
			count -= 1
			if (self._source[self._index] == '\r') or (self._source[self._index] == '\n'):
				if (self._source[self._index] == '\r') and (self._source[self._index + 1] == '\n'):
					self._index += 2
				else:
					self._index += 1
				self._line += 1
				self._linestart = self._index
			else:
				self._index += 1

	def _mark(self):
		"""Marks the current position in the source for later retrieval.

		The mark() method is used with the markedchars
		property. A handler can call mark to save the current
		position in the source code, then query markedchars
		to obtain a string of all characters from the marked
		position to the current position (assuming the handler
		has moved the current position forward since calling
		mark().

		The markedtext property handles converting all line
		breaks to LF (like the next() method and char/nextchar
		properties).
		"""
		self._markedindex = self._index

	def _getChar(self):
		"""Returns the current character at the position of the tokenizer.

		The _getChar() method returns the character in
		_source at _index, but converts all line breaks to
		a single LF character as this makes handler code
		slightly easier to write.
		"""
		try:
			if self._source[self._index] == '\r':
				return '\n'
			else:
				return self._source[self._index]
		except IndexError:
			return '\0'

	def _getNextChar(self):
		"""Returns the character the next position of the tokenizer.

		The _getNextChar() method returns the character
		immediately after the current character in _source,
		and (like _getChar()) handles converting all line
		breaks into single LF characters.
		"""
		try:
			if self._source[self._index] == '\r':
				if self._source[self._index + 1] == '\n':
					return self._source[self._index + 2]
				else:
					return self._source[self._index + 1]
			elif self._source[self._index + 1] == '\r':
				return '\n'
			else:
				return self._source[self._index + 1]
		except IndexError:
			return '\0'

	def _getMarkedChars(self):
		"""Returns the characters from the marked position to the current.

		After calling _mark() at a starting position, a
		handler can later use _getMarkedChars() to retrieve
		all characters from that marked position to the
		current position (useful for extracting the content
		of large blocks of code like comments, strings, etc).
		"""
		assert self._markedindex >= 0
		return self._source[self._markedindex:self._index].replace('\r\n', '\n')

	def _getLine(self):
		"""Returns the current 1-based line position."""
		return self._line

	def _getColumn(self):
		"""Returns the current 1-based column position."""
		return (self._index - self._linestart) + 1

	def _getTerminator(self):
		"""Returns the current statement terminator string (or character)."""
		return self._terminator

	def _setTerminator(self, value):
		"""Sets the current statement terminator string (or character).

		The _setTerminator() method sets the current
		terminator string (or character), and updates the
		internal _jump table as necessary.
		"""
		# Restore the saved handler, if necessary. We don't need to do this if
		# there was no prior terminator (such as in a new instance of the,
		# class). If the saved handler is the default (error) handler, simply
		# remove the first character of the terminator from the jump table
		if len(value) == 0:
			raise ValueError("Statement terminator string must contain at least one character")
		if len(self._terminator) > 0:
			if self._savedhandler == self._handleDefault:
				del self._jump[self._terminator[0]]
			else:
				self._jump[self._terminator[0]] = self._savedhandler
		# Replace the handler (if any) for the statement terminator character
		# (or the first character of the statement terminator string) with
		# a special handler and save the original handler for use by the
		# special handler
		if (value == '\r\n') or (value == '\r'): value = '\n'
		self._terminator = value
		self._savedhandler = self._jump.get(value[0], self._handleDefault)
		self._jump[value[0]] = self._handleStatementTerm

	char = property(_getChar, doc="""The current character the tokenizer is looking at, or the NULL character if EOF has been reached""")
	nextchar = property(_getNextChar, doc="""The character immediately after the current character, or the NULL character if it is past the EOF""")
	markedchars = property(_getMarkedChars, doc="""The characters between the marked position and the current position in the source code""")
	line = property(_getLine, doc="""Returns the 1-based line of the position of the tokenizer in the source code""")
	column = property(_getColumn, doc="""Returns the 1-based column of the position of the tokenizer in the source code""")
	terminator = property(_getTerminator, _setTerminator, doc="""The current statement termination string. Defaults to ';'""")

	def _extractQuotedString(self):
		"""Extracts a quoted string from the source code.

		Returns the content of a quoted string in the
		source code. The current position (in _index)
		is assumed to be the opening quote of the string
		(either ' or " although the function doesn't confirm
		this). Quotation characters can be escaped within
		the string by doubling, for example:

			'Doubled ''quotation'' characters'

		The method returns the unescaped content of the
		string. Hence, in the case above the method would
		return "Doubled 'quotation' characters" (without the
		double-quotes). The _index variable is incremented to
		the character beyond the closing quote of the string.

		Strings may not span multiple lines. If a CR, LF
		or NULL character is encountered in the string,
		an exception is raised (calling methods convert
		this exception into an ERROR token).

		This method should be overridden in descendent
		classes to handle those SQL dialects which permit
		additonal escaping mechanisms (like C backslash
		escaping).
		"""
		qchar = self.char
		qcount = 1
		self._next()
		self._mark()
		while True:
			if self.char == '\0':
				raise ValueError('Incomplete string at end of source')
			elif self.char == '\n':
				raise ValueError('Line break found in string')
			elif self.char == qchar:
				qcount += 1
			if self.char == qchar and self.nextchar != qchar and qcount & 1 == 0:
				break
			self._next()
		content = self.markedchars.replace(qchar*2, qchar)
		self._next()
		return content

	def _handleAsterisk(self):
		"""Parses an asterisk character ("*") in the source."""
		self._next()
		self._addToken(OPERATOR, '*')

	def _handleBar(self):
		"""Parses a vertical bar character ("|") in the source."""
		self._next()
		if self.char == '|':
			self._next()
			self._addToken(OPERATOR, '||')
		else:
			self._addToken(ERROR, 'Invalid operator |')

	def _handleCloseParenthesis(self):
		"""Parses a closing parenthesis character (")") in the source."""
		self._next()
		self._addToken(OPERATOR, ')')

	def _handleColon(self):
		"""Parses a colon character (":") in the source."""
		self._next()
		if self.char in ['"', "'"]:
			try:
				self._addToken(PARAMETER, self._extractQuotedString())
			except ValueError, e:
				self._addToken(ERROR, str(e))
		else:
			self._mark()
			while self.char in self.identchars: self._next()
			self._addToken(PARAMETER, self.markedchars)

	def _handleComma(self):
		"""Parses a comma character (",") in the source."""
		self._next()
		self._addToken(OPERATOR, ',')

	def _handleDefault(self):
		"""Parses unexpected characters, returning an error."""
		self._next()
		self._addToken(ERROR, 'Unexpected character %s' % (self.char))

	def _handleDigit(self):
		"""Parses numeric digits (0..9) in the source."""
		self._mark()
		self._next()
		validchars = set('0123456789Ee.')
		while self.char in validchars:
			if self.char == '.':
				validchars -= set('.')
			elif self.char in 'Ee':
				validchars -= set('Ee.')
				if self.nextchar in '-+':
					self._next()
			self._next()
		try:
			self._addToken(NUMBER, decimal.Decimal(self.markedchars))
		except ValueError, e:
			self._addToken(ERROR, str(e))

	def _handleDoubleQuote(self):
		"""Parses double quote characters (") in the source."""
		try:
			self._addToken(IDENTIFIER, self._extractQuotedString())
		except ValueError, e:
			self._addToken(ERROR, str(e))

	def _handleEqual(self):
		"""Parses equality characters ("=") in the source."""
		self._next()
		self._addToken(OPERATOR, '=')

	def _handleGreater(self):
		"""Parses greater-than characters (">") in the source."""
		self._next()
		if self.char == '=':
			self._next()
			self._addToken(OPERATOR, '>=')
		else:
			self._addToken(OPERATOR, '>')

	def _handleIdent(self):
		"""Parses unquoted identifier characters (variable) in the source."""
		self._mark()
		self._next()
		while self.char in self.identchars: self._next()
		ident = self.markedchars.upper()
		if ident in self.keywords:
			self._addToken(KEYWORD, ident)
		else:
			self._addToken(IDENTIFIER, ident)

	def _handleLess(self):
		"""Parses less-than characters ("<") in the source."""
		self._next()
		if self.char == '=':
			self._next()
			self._addToken(OPERATOR, '<=')
		elif self.char == '>':
			self._next()
			self._addToken(OPERATOR, '<>')
		else:
			self._addToken(OPERATOR, '<')

	def _handleMinus(self):
		"""Parses minus characters ("-") in the source."""
		self._next()
		if self.sql_comments and (self.char == '-'):
			self._next()
			self._mark()
			while not self.char in '\0\n': self._next()
			content = self.markedchars
			self._next()
			self._addToken(COMMENT, content)
		else:
			self._addToken(OPERATOR, '-')

	def _handleOpenParenthesis(self):
		"""Parses open parenthesis characters ("(") in the source."""
		self._next()
		self._addToken(OPERATOR, '(')

	def _handlePeriod(self):
		"""Parses full-stop characters (".") in the source."""
		if self.nextchar in '0123456789':
			# Numbers can start with . in SQL
			self._handleDigit()
		else:
			self._next()
			self._addToken(OPERATOR, '.')

	def _handlePlus(self):
		"""Parses plus characters ("+") in the source."""
		self._next()
		self._addToken(OPERATOR, '+')

	def _handleQuote(self):
		"""Parses single quote characters (') in the source."""
		try:
			self._addToken(STRING, self._extractQuotedString())
		except ValueError, e:
			self._addToken(ERROR, str(e))

	def _handleSemiColon(self):
		"""Parses semi-colon characters (;) in the source."""
		self._next()
		self._addToken(TERMINATOR, ';')

	def _handleSlash(self):
		"""Parses forward-slash characters ("/") in the source."""
		self._next()
		if self.cpp_comments and (self.char == '/'):
			self._next()
			self._mark()
			while not self.char in '\0\n': self._next()
			content = self.markedchars
			self._next()
			self._addToken(COMMENT, content)
		elif self.c_comments and (self.char == '*'):
			self._next()
			self._mark()
			try:
				while True:
					if self.char == '\0':
						raise ValueError("Incomplete comment")
					elif (self.char == '\n') and self.newline_split:
						self._next()
						self._addToken(COMMENT, self.markedchars)
						self._mark()
					elif (self.char == '*') and (self.nextchar == '/'):
						content = self.markedchars
						self._next(2)
						self._addToken(COMMENT, content)
						break
					else:
						self._next()
			except ValueError, e:
				self._addToken(ERROR, str(e))
		else:
			self._addToken(OPERATOR, '/')

	def _handleStatementTerm(self):
		"""Parses statement terminator characters (variable) in the source."""
		if self._source.startswith(self._terminator, self._index):
			self._next(len(self._terminator))
			self._addToken(TERMINATOR, None)
		else:
			self._savedhandler()

	def _handleWhitespace(self):
		"""Parses whitespace characters in the source."""
		while self.char in self.spacechars: self._next()
		self._addToken(WHITESPACE, None)

	def _initHandlers(self):
		"""Initializes a dictionary of character handlers."""
		# Update the _jump dictionary of characters as a method table
		self._jump.update({
			'(': self._handleOpenParenthesis,
			')': self._handleCloseParenthesis,
			'+': self._handlePlus,
			'-': self._handleMinus,
			'*': self._handleAsterisk,
			'/': self._handleSlash,
			'.': self._handlePeriod,
			',': self._handleComma,
			':': self._handleColon,
			'<': self._handleLess,
			'=': self._handleEqual,
			'>': self._handleGreater,
			"'": self._handleQuote,
			'"': self._handleDoubleQuote,
			'|': self._handleBar,
			';': self._handleSemiColon,
		})
		for char in self.spacechars:
			self._jump[char] = self._handleWhitespace
		for char in self.identchars:
			self._jump[char] = self._handleIdent
		# If numerals were included in identchars above, they will be
		# overwritten by the next bit (numerals are never permitted as the
		# first character in an identifier)
		for char in '0123456789':
			self._jump[char] = self._handleDigit

	def parse(self, source, terminator=';'):
		"""Parses the provided source into a list of token tuples."""
		self._source = source
		self._index = 0
		self._markedindex = -1
		self._line = 1
		self._linestart = 0
		self._tokenstart = 0
		self._tokenline = self.line
		self._tokencolumn = self.column
		self._tokens = []
		self._jump = {}
		self._initHandlers()
		# Note that setting terminator must be done AFTER initializing the
		# jump table as doing so re-writes elements within that table
		self.terminator = terminator
		while self.char != '\0':
			# Use the jump table to parse the token
			try:
				self._jump[self.char]()
			except KeyError:
				self._handleDefault()
		self._addToken(EOF, None)
		if self.newline_split:
			# Split the list of tokens into a list of lines of lists of tokens
			newtokens = []
			linetokens = []
			currentline = 1
			for token in self._tokens:
				(_, _, _, line, _) = token
				if line == currentline:
					linetokens.append(token)
				else:
					newtokens.append(linetokens)
					linetokens = [token]
					currentline = line
			newtokens.append(linetokens)
			return newtokens
		else:
			return self._tokens

class SQL92Tokenizer(SQLTokenizerBase):
	"""ANSI SQL-92 tokenizer class."""
	pass

class SQL99Tokenizer(SQLTokenizerBase):
	"""ANSI SQL-99 tokenizer class."""
	
	def __init__(self):
		super(SQL99Tokenizer, self).__init__()
		self.keywords = set(dialects.sql99_keywords)
		self.identchars = set(dialects.sql99_identchars)

class SQL2003Tokenizer(SQLTokenizerBase):
	"""ANSI SQL-2003 tokenizer class."""
	
	def __init__(self):
		super(SQL2003Tokenizer, self).__init__()
		self.keywords = set(dialects.sql2003_keywords)
		self.identchars = set(dialects.sql2003_identchars)

class DB2ZOSSQLTokenizer(SQLTokenizerBase):
	"""IBM DB2 UDB for z/OS tokenizer class."""
	
	def __init__(self):
		super(DB2ZOSSQLTokenizer, self).__init__()
		self.keywords = set(dialects.ibmdb2zos_keywords)
		self.identchars = set(dialects.ibmdb2zos_identchars)

	def _handleNot(self):
		"""Parses characters meaning "NOT" (! and ^) in the source."""
		self._next()
		try:
			negatedop = {
				'=': '<>',
				'>': '<=',
				'<': '>=',
			}[self.char]
		except KeyError:
			self._addToken(ERROR, "Expected >, <, or =, but found %s" % (self.char))
		else:
			self._next()
			self._addToken(OPERATOR, negatedop)

	def _initHandlers(self):
		self._jump['!'] = self._handleNot
		self._jump['^'] = self._handleNot
		# XXX What about the hook character here ... how to encode?
		super(DB2ZOSSQLTokenizer, self)._initHandlers()

class DB2UDBSQLTokenizer(DB2ZOSSQLTokenizer):
	"""IBM DB2 UDB for Linux/Unix/Windows tokenizer class."""

	def __init__(self):
		super(DB2UDBSQLTokenizer, self).__init__()
		self.keywords = set(dialects.ibmdb2udb_keywords)
		self.identchars = set(dialects.ibmdb2udb_identchars)
		# Support for C-style /*..*/ comments add in DB2 UDB v8 FP9
		self.c_comments = True
	
	def _handlePeriod(self):
		"""Parses full-stop characters (".") in the source."""
		# Override the base method to handle DB2 UDB's method qualifiers (..)
		if self.nextchar == '.':
			self._addToken(OPERATOR, '..')
			self._next(2)
		else:
			super(DB2UDBSQLTokenizer, self)._handlePeriod()

if __name__ == "__main__":
	# XXX Robust test cases
	pass
