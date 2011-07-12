# vim: set noet sw=4 ts=4:

"""Implements a class for reflowing "raw" SQL.

This unit implements a class which reformats SQL that has been "mangled" in
some manner, typically by being parsed and stored by a database (e.g.  line
breaks stripped, all whitespace converted to individual spaces, etc).  The
reformatted SQL is intended to be more palatable for human consumption (aka
"readable" :-)
"""

import pdb
import re
import sys
import math
from dbsuite.tokenizer import TokenTypes, Token, Error, TokenError, sql92_namechars, sql92_identchars
from dbsuite.compat import *
from decimal import Decimal
from itertools import tee, izip

__all__ = [
	'dump',
	'dump_token',
	'quote_str',
	'format_ident',
	'format_param',
	'format_size',
	'recalc_positions',
	'format_tokens',
	'convert_indent',
	'convert_valign',
	'merge_whitespace',
	'strip_whitespace',
	'split_lines',
	'Connection',
	'Error',
	'ParseError',
	'ParseBacktrack',
	'ParseTokenError',
	'ParseExpectedOneOfError',
	'ParseExpectedSequenceError',
	'BaseParser',
]

# Add some custom token types used by the formatter
TT = TokenTypes
for (type, name) in (
	('EOF',       '<end-of-file>'),    # Symbolically represents the end of file (e.g. for errors)
	('DATATYPE',  '<datatype>'),       # Datatypes (e.g. VARCHAR) converted from KEYWORD or IDENTIFIER
	('SCHEMA',    '<schema>'),         # Schema identifier converted from IDENTIFIER
	('RELATION',  '<relation>'),       # Relation identifier converted from IDENTIFIER
	('ROUTINE',   '<routine>'),        # Routine identifier converted from IDENTIFIER
	('REGISTER',  '<register>'),       # Special registers (e.g. CURRENT DATE) converted from KEYWORD or IDENTIFIER
	('PASSWORD',  '<password>'),       # Password converted from STRING
	('STATEMENT', '<statement-end>'),  # Statement terminator
	('INDENT',    None),               # Whitespace indentation at the start of a line
	('VALIGN',    None),               # Whitespace indentation within a line to vertically align blocks of text
	('VAPPLY',    None),               # Mark the end of a run of VALIGN tokens
):
	TT.add(type, name)

ctrlchars = re.compile(ur'([\x00-\x1F\x7F-\xFF]+)')
def quote_str(s, quotechar="'"):
	"""Quotes a string, doubling all quotation characters within it.

	The s parameter provides the string to be quoted. The optional quotechar
	parameter provides the quotation mark used to enclose the string. If the
	string contains any control characters (tabs, newlines, etc.) they will be
	quoted as a hex-string (i.e. a string prefixed by X which contains bytes
	encoded as two hex numbers), and concatenated to the rest of the string.
	"""
	result = []
	if s == '':
		# Special case for the empty string (the general case deliberately
		# outputs nothing for empty strings to eliminate leading and trailing
		# empty groups)
		return quotechar*2
	else:
		for index, group in enumerate(ctrlchars.split(s)):
			if group:
				if index % 2:
					result.append('X%s%s%s' % (quotechar, ''.join('%.2X' % ord(c) for c in group), quotechar))
				else:
					result.append('%s%s%s' % (quotechar, group.replace(quotechar, quotechar*2), quotechar))
		return ' || '.join(result)

def dump(tokens):
	"""Utility routine for debugging purposes: prints the tokens in a human readable format."""
	sys.stderr.write('\n'.join(dump_token(token) for token in tokens))
	sys.stderr.write('\n')

def dump_token(token):
	"""Formats a token for the dump routine above."""
	if len(token) == 3:
		return '%-16s %-20s %-20s' % (TT.names[token.type], repr(token.value), repr(token.source))
	else:
		return '%-16s %-20s %-20s (%d:%d)' % (TT.names[token.type], repr(token.value), repr(token.source), token.line, token.column)

def format_ident(name, quotechar='"', namechars=set(sql92_namechars)):
	"""Format an SQL identifier with quotes if required.

	The name parameter provides the object name to format. The optional
	namechars parameter provides the set of characters which are permitted in
	unquoted names. If the entire name consists of such characters (excepting
	the initial character which is not permitted to be a numeral) it will be
	returned unquoted. Otherwise, quote_str() will be called with the optional
	qchar parameter to quote the name.

	Note that the default for namechars is one of the namechars strings from
	the plugins.dialects module, NOT one of the identchars strings. While
	lowercase characters are usually permitted in identifiers, they are folded
	to uppercase by the database, and the tokenizer emulates this. This routine
	is for output and therefore lowercase characters in name will trigger
	quoting.
	"""
	firstchars = namechars - set('0123456789')
	if len(name) == 0:
		raise ValueError('Blank identifier')
	if not name[0] in firstchars:
		return quote_str(name, quotechar)
	for c in name[1:]:
		if not c in namechars:
			return quote_str(name, quotechar)
	return name

def format_param(param, namechars=set(sql92_namechars)):
	"""Format a parameter with quotes if required.

	Performs a similar role to format_ident but for parameters instead of
	identifiers.  If the parameter specified by param is None (indicating an
	anonymous parameter) a question mark (?) will be returned. Otherwise, the
	parameter will be returned quoted (if necessary) and prefixed with colon
	(:).
	"""
	if param is None:
		return '?'
	else:
		return ':%s' % (format_ident(param, namechars=namechars))

def format_size(value, for_sql=True):
	"""Formats sizes with standard K/M/G/T/etc. suffixes.

	Given a value, this function returns it with the largest scale suffix
	possible while leaving the value >= 1. If the optional for_sql parameter is
	True (which it is by default), only exact powers will be used when scaling,
	i.e. the result is guaranteed to be a whole number followed by a suffix (if
	value is not an exact binary power it will be returned without scaling).
	Otherwise, the result will be an imprecise scaling intended for human
	readability rather than machine interpreting.
	"""
	if value is None:
		return None
	elif value == 0:
		return str(value)
	else:
		power = math.log(value, 2)
		index = int(power / 10)
		if not for_sql or (value % (1024 ** index) == 0):
			if for_sql:
				suffix = ['', 'K', 'M', 'G', 'T', 'E', 'P'][index]
				size = value / (1024 ** index)
				return "%d%s" % (int(size), suffix)
			else:
				suffix = ['b', 'Kb', 'Mb', 'Gb', 'Tb', 'Eb', 'Pb'][index]
				size = float(value) / (1024 ** index)
				return "%.2f %s" % (size, suffix)
		else:
			return str(value)

def recalc_positions(tokens):
	"""Recalculates token positions.

	This generator function recalculates the position of each token. It is
	intended for wrapping other functions which alter the source of tokens.
	"""
	line = 1
	column = 1
	for token in tokens:
		yield Token(token.type, token.value, token.source, line, column)
		for char in token.source:
			if char == '\n':
				line += 1
				column = 1
			else:
				column += 1

def format_tokens(tokens, reformat=[], terminator=';', statement=';', namechars=set(sql92_namechars)):
	"""Changes token source to a canonical format.

	This generator function handles reformatting tokens into a canonical
	representation (e.g. unquoted identifiers folded to uppercase). The
	optional terminator parameter specifies the terminator for statements
	within a block statement, while the optional statement parameter specifies
	the top-level statement terminator. The reformat parameter specifies which
	types of token will be affected by the function. Note: this function zeros
	the positional elements.
	"""
	for token in tokens:
		if token.type in reformat:
			if token.type in (TT.KEYWORD, TT.REGISTER):
				yield Token(token.type, token.value, token.value, 0, 0)
			elif token.type in (TT.IDENTIFIER, TT.DATATYPE, TT.SCHEMA, TT.RELATION, TT.ROUTINE):
				yield Token(token.type, token.value, format_ident(token.value, namechars=namechars), 0, 0)
			elif token.type == TT.NUMBER:
				# Ensure decimal values with no decimal portion keep the
				# decimal point (fix for #49)
				if isinstance(token.value, Decimal) and token.value.as_tuple()[-1] == 0:
					yield Token(TT.NUMBER, token.value, str(token.value) + '.', 0, 0)
				else:
					yield Token(TT.NUMBER, token.value, str(token.value), 0, 0)
			elif token.type in (TT.STRING, TT.PASSWORD):
				yield Token(token.type, token.value, quote_str(token.value), 0, 0)
			elif token.type == TT.LABEL:
				yield Token(TT.LABEL, token.value, format_ident(token.value, namechars=namechars) + ':', 0, 0)
			elif token.type == TT.PARAMETER:
				yield Token(TT.PARAMETER, token.value, format_param(token.value, namechars=namechars), 0, 0)
			elif token.type == TT.COMMENT:
				# XXX Need more intelligent comment handling
				##yield (TT.COMMENT, token[1], '/*%s*/' % (token[1]))
				yield Token(token.type, token.value, token.source, 0, 0)
			elif token.type == TT.STATEMENT:
				yield Token(TT.STATEMENT, token.value, statement, 0, 0)
			elif token.type == TT.TERMINATOR:
				yield Token(TT.TERMINATOR, token.value, terminator, 0, 0)
			else:
				yield Token(token.type, token.value, token.source, 0, 0)
		else:
			yield Token(token.type, token.value, token.source, 0, 0)

def convert_indent(tokens, indent='\t'):
	"""Converts INDENT tokens into WHITESPACE.

	This generator function converts INDENT tokens into WHITESPACE tokens
	containing the characters specified by the indent parameter. Note: this
	function zeros the positional elements.
	"""
	for token in tokens:
		if token.type == TT.INDENT:
			yield Token(TT.WHITESPACE, None, '\n' + indent * token.value, 0, 0)
		else:
			yield Token(token.type, token.value, token.source, 0, 0)

def convert_valign(tokens):
	"""Converts VALIGN and VAPPLY tokens into WHITESPACE.

	This generator function converts VALIGN and VAPPLY tokens into WHITESPACE
	tokens.  Multiple passes are used to convert the VALIGN tokens; each pass
	converts the first VALIGN token found on a set of lines prior to a VAPPLY
	token into a WHITESPACE token. The final result will require recalculation
	of positions if any tokens have been replaced.
	"""
	indexes = []
	aligncol = alignline = 0
	more = True
	while more:
		result = []
		more = False
		for i, token in enumerate(recalc_positions(tokens)):
			line, col = token.line, token.column
			result.append(token)
			if token.type == TT.VALIGN:
				if indexes and alignline == line:
					# If we encounter more than one VALIGN on a line, remember
					# that we need another pass
					more = True
				else:
					# Remember the position of the VALIGN token in the result,
					# adjust the alignment column if necessary, and remember
					# the line number so we can ignore any further VALIGN
					# tokens on this line
					indexes.append(i)
					aligncol = max(aligncol, col)
					alignline = line
			elif token.type == TT.VAPPLY:
				# Convert all the remembered VALIGN tokens into WHITESPACE
				# tokens with appropriate lengths for vertical alignment
				for j in indexes:
					line, col = result[j].line, result[j].column
					result[j] = Token(TT.WHITESPACE, None, ' ' * (aligncol - col), 0, 0)
				# Convert the VAPPLY token into a zero-length WHITESPACE token.
				# We cannot simply remove it as that would invalidate the
				# indexes being generated for the input sequence by the
				# enumerate() call in the loop
				if indexes:
					result[-1] = Token(TT.WHITESPACE, None, '', 0, 0)
					indexes = []
					aligncol = alignline = 0
		# If indexes isn't blank, then we encountered VALIGNs without a
		# corresponding VAPPLY (parser bug)
		assert not indexes
		tokens = result
	return result

def merge_whitespace(tokens):
	"""Merges consecutive WHITESPACE tokens.

	This generator function merges consecutive WHITESPACE tokens which can
	result from various mechanisms (especially the VALIGN conversion). It also
	ditches WHITESPACE tokens with no source. Note: this function relies on
	positional elements being present in the tokens.
	"""
	empty = True
	a, b = tee(tokens)
	# Advance the second copy by one element
	for elem in b:
		empty = False
		break
	space = ''
	line = col = 1
	# Iterate pairwise over the tokens
	for last, token in izip(a, b):
		if last.type == TT.WHITESPACE:
			if token.type == last.type:
				space += token.source
			elif space:
				yield Token(TT.WHITESPACE, None, space, line, col)
		else:
			if token.type == TT.WHITESPACE:
				space, line, col = token[2:]
			yield last
	if not empty:
		if token.type == TT.WHITESPACE:
			yield Token(TT.WHITESPACE, None, space, line, col)
		else:
			yield token

def strip_whitespace(tokens):
	"""Strips trailing WHITESPACE tokens from all lines of output.

	This generator function strips trailing WHITESPACE tokens at the end of a
	line from the provided sequence of tokens. The function assumes that
	WHITESPACE tokens have been merged (two will not appear consecutively).
	Positions present in the tokens are preserved.
	"""
	last = None
	for token in tokens:
		if token.type == TT.WHITESPACE:
			if '\n' in token.source:
				last = Token(TT.WHITESPACE, None, '\n' + token.source.split('\n', 1)[1], token.line, token.column)
			else:
				last = token
		else:
			if last:
				yield last
				last = None
			yield token

def split_lines(tokens):
	"""Splits tokens which contain line breaks.

	This generator function splits up any tokens that contain line breaks so
	that every line has a token beginning at column 1. Note: this function
	relies on positional elements being present in the tokens.
	"""
	for token in tokens:
		(type, value, source, line, column) = token
		while '\n' in source:
			if isinstance(value, basestring) and '\n' in value:
				i = value.index('\n') + 1
				new_value, value = value[:i], value[i:]
			else:
				new_value = value
			i = source.index('\n') + 1
			new_source, source = source[:i], source[i:]
			yield Token(type, new_value, new_source, line, column)
			line += 1
			column = 1
		if source or type not in (TT.WHITESPACE, TT.COMMENT):
			yield Token(type, value, source, line, column)

class ParseError(Error):
	"""Raised when a parsing error is found."""
	pass

class ParseBacktrack(ParseError):
	"""Fake exception class raised internally when the parser needs to backtrack."""

	def __init__(self):
		"""Initializes an instance of the exception."""
		# The message is irrelevant as this exception should never propogate
		# outside the parser
		ParseError.__init__(self, '')

class ParseTokenError(TokenError, ParseError):
	"""Raised when a parsing error including token details is encountered."""

	def token_name(self, token):
		"""Formats a token for display in an error message string"""
		if isinstance(token, basestring):
			return token
		elif isinstance(token, int):
			return TT.names[token]
		elif isinstance(token, Token):
			if token.type in (TT.EOF, TT.WHITESPACE, TT.TERMINATOR, TT.STATEMENT):
				return TT.names[token.type]
			elif token.value is not None:
				return token.value
			else:
				return token.source
		elif isinstance(token, tuple):
			if (len(token) == 1) or (token[0] in (TT.EOF, TT.WHITESPACE, TT.TERMINATOR, TT.STATEMENT)):
				return TT.names[token[0]]
			elif (len(token) == 2) and (token[1] is not None):
				return token[1]
			else:
				return token[2]
		else:
			return None

class ParseExpectedOneOfError(ParseTokenError):
	"""Raised when the parser didn't find a token it was expecting."""

	def __init__(self, source, token, expected):
		"""Initializes an instance of the exception.

		The parameters are as follows:
		source -- The source being parsed
		token -- The unexpected token that was found
		expected -- A list of alternative tokens that was expected at this location
		"""
		self.expected = expected
		msg = 'Expected %s but found "%s"' % (
			', '.join(['"%s"' % (self.token_name(t),) for t in expected]),
			self.token_name(token)
		)
		ParseTokenError.__init__(self, source, token, msg)

class ParseExpectedSequenceError(ParseTokenError):
	"""Raised when the parser didn't find a sequence of tokens it was expecting"""

	def __init__(self, source, tokens, expected):
		"""Initializes an instance of the exception.

		The parameters are as follows:
		source -- The source being parsed
		tokens -- The unexpected sequenced of tokens that was found
		expected -- A sequence of tokens that was expected at this location
		"""
		self.expected = expected
		msg = 'Expected "%s" but found "%s"' % (
			' '.join([self.token_name(t) for t in expected]),
			' '.join([self.token_name(t) for t in tokens])
		)
		ParseTokenError.__init__(self, source, tokens[0], msg)

class BaseParser(object):
	"""Base class for parsers.

	Do not use this class directly. Instead use one of the descendent classes
	(currently only DB2LUWParser) depending on your needs.

	The class accepts input from one of the tokenizers in the tokenizer unit,
	in the form of a list of tokens, where tokens are 5-element tuples with the
	following structure:

	    (type, value, source, line, column)

	The elements of the tuple can also be accessed by the names listed above
	(tokens are instances of the Token namedtuple class).

	To use the class simply pass such a list to the parse method. The method
	will return a list of tokens (just like the list of tokens provided as
	input, but reformatted according to the properties detailed below).

	The type element gives the general "family" of the token (such as OPERATOR,
	IDENTIFIER, etc), while the value element provides the specific type of the
	token (e.g. "=", "OR", "DISTINCT", etc). The code in these classes
	typically uses "partial" tokens to match against "complete" tokens in the
	source. For example, instead of trying to match on the source element
	(which may vary in case), this class often matches token on the first two
	elements:

	    (TT.KEYWORD, "OR", "or", 7, 13)[:2] == (TT.KEYWORD, "OR")

	A set of internal utility methods are used to simplify this further. See
	the _match and _expect methods in particular. The numerous _parse_X methods
	in each class define the grammar of the SQL language being parsed.

	The following options are available for customizing the reformatting
	performed by the class:

	reformat    A set of token types to undergo reformatting. By default this
	            set includes all token types output by the parser.  See below
	            for the specific types of reformatting performed by token type.
	indent      If TT.WHITESPACE is present in the reformat set, this is the
	            indentation that should be used in the output. Defaults to 4
	            spaces.
	line_split  When False (the default), multi-line tokens (e.g. comments,
	            whitespace) will be returned as a single token. When True,
	            tokens will be forcibly split at line breaks to ensure every
	            line has a token with column 1 (useful when performing per-line
	            processing on the result).
	statement   If STATEMENT is present in the reformat set, this defines
	            the string used to terminate statements. Note: intra-statement
	            terminators, such as the semi-colon used to terminate
	            statements within a stored procedure definition are unaffected
	            by this option; this option determines how statement
	            terminators will be output. Defaults to semi-colon.
	terminator  If TERMINATOR is present in the reformat set, this defines the
	            string used to terminate statements within a compound SQL block
	            (e.g. the body of a stored procedure or function definition).
	            Defaults to semi-colon.

	The following list defines the type of reformatting performed on each token
	type when it is present in the reformat set:

	KEYWORD     All keywords will be folded to uppercase.
	REGISTER    All special register keywords will be folded to uppercase.
	IDENTIFIER  All identifiers capable of being represented unquoted (not
	            containing lowercase characters, symbols, etc.) will be
	            unquoted (if originally quoted), and folded to uppercase.
	DATATYPE    Same as IDENTIFIER.
	SCHEMA      Same as IDENTIFIER.
	RELATION    Same as IDENTIFIER.
	ROUTINE     Same as IDENTIFIER.
	LABEL       Same as IDENTIFIER, with a colon suffix.
	PARAMETER   Same as IDENTIFIER, with a colon prefix for named parameters.
	NUMBER      All numbers will be formatted without extraneous leading or
	            trailing zeros (or decimal portions), and uppercase signed
	            exponents (where the original had an exponent). Extraneous
	            unary plus operators (+) will be included where present in the
	            original source.
	STRING      All string literals will be formatted into a minimal safe
	            representation, e.g. if a hexstring contains no control
	            characters, it will be converted to an ordinary string literal
	            (and vice versa).
	STATEMENT   All inter-statement terminators will be changed to the string
	            specified in the statement property.
	TERMINATOR  All intra-statement terminators will be changed to the string
	            specified in the terminator property.
	WHITESPACE  All spacing in the original source will be discarded and
	            replaced with spacing determined by an algorithm (e.g. spaces
	            either side of all arithmetic operators, one space after
	            commas, etc).

	If other token types are included in the set (e.g. TERMINATOR) they will be
	ignored.
	"""

	def __init__(self):
		super(BaseParser, self).__init__()
		self.indent = ' ' * 4
		self.reformat = set([
			TT.DATATYPE,
			TT.IDENTIFIER,
			TT.SCHEMA,
			TT.RELATION,
			TT.ROUTINE,
			TT.KEYWORD,
			TT.LABEL,
			TT.NUMBER,
			TT.PARAMETER,
			TT.REGISTER,
			TT.STATEMENT,
			TT.STRING,
			TT.PASSWORD,
			TT.TERMINATOR,
			TT.WHITESPACE,
		])
		self.line_split = False
		self.statement = ';'
		self.terminator = ';'
		self.namechars = sql92_namechars
		self.identchars = sql92_identchars

	def parse(self, tokens):
		"""Parses an arbitrary statement or script.

		This is the main public method of the parser. Given a list of tokens
		(as generated by one of the tokenizers in the tokenizer module) it
		parses the script represented by the tokens, reformatting the
		whitespace and, where necessary, changing token types according to
		context (e.g. the word DATE could be used as a function or column name,
		or as a datatype, or as part of the special register CURRENT DATE).
		"""
		self._parse_init(tokens)
		while True:
			# Ignore leading whitespace and empty statements
			while self._token().type in (TT.COMMENT, TT.WHITESPACE, TT.TERMINATOR):
				self._index += 1
			# If not at EOF, parse a statement (mustn't match the EOF otherwise
			# we'll wind up adding it to the output list)
			if not self._peek(TT.EOF):
				self._parse_top()
				self._expect(TT.STATEMENT) # STATEMENT converts TERMINATOR into STATEMENT
				assert len(self._states) == 0
				# Reset the indent level and leave a blank line
				self._level = 0
				self._newline()
				self._newline(allowempty=True)
			else:
				break
		self._parse_finish()
		return self._output

	def _parse_init(self, tokens):
		"""Sets up the parser with the specified tokens as input."""
		self._states = []
		self._index = 0
		self._output = []
		self._level = 0
		self._tokens = tokens
		# Reconstruct a copy of the source; this is only used for exceptions
		# which use the original source string for context reporting
		self._source = ''.join(token.source for token in tokens)

	def _parse_finish(self):
		"""Cleans up and finalizes tokens in the output."""
		output = self._output
		output = format_tokens(output, reformat=self.reformat,
			terminator=self.terminator, statement=self.statement,
			namechars=set(self.namechars))
		if TT.WHITESPACE in self.reformat:
			output = recalc_positions(convert_valign(convert_indent(output, indent=self.indent)))
		else:
			output = recalc_positions(token for token in output if token.type not in (TT.INDENT, TT.VALIGN, TT.VAPPLY))
		output = merge_whitespace(output)
		if TT.WHITESPACE in self.reformat:
			output = strip_whitespace(output)
		if self.line_split:
			output = split_lines(output)
		self._output = list(output)

	def _parse_top(self):
		"""Top level of the parser.

		Override this method in descendents to parse a statement (or whatever
		is at the top of the parse tree).
		"""
		raise NotImplementedError

	def _newline(self, index=0, allowempty=False):
		"""Adds an INDENT token to the output.

		The _newline() method is called to start a new line in the output. It
		does this by appending (or inserting, depending on the index parameter)
		an INDENT token to the output list. Later, during _parse_finish, INDENT
		tokens are converted into WHITESPACE tokens at the specified
		indentation level.

		See _insert_output for an explanation of allowempty.
		"""
		token = Token(TT.INDENT, self._level, '', 0, 0)
		self._insert_output(token, index, allowempty)

	def _indent(self, index=0, allowempty=False):
		"""Increments the indentation level and starts a new line."""
		self._level += 1
		self._newline(index, allowempty)

	def _outdent(self, index=0, allowempty=False):
		"""Decrements the indentation level and starts a new line."""
		self._level -= 1
		assert self._level >= 0
		self._newline(index, allowempty)

	def _valign(self, index=0):
		"""Inserts a VALIGN token into the output."""
		token = Token(TT.VALIGN, None, '', 0, 0)
		self._insert_output(token, index, True)

	def _vapply(self, index=0):
		"""Inserts a VAPPLY token into the output."""
		token = Token(TT.VAPPLY, None, '', 0, 0)
		self._insert_output(token, index, True)

	def _insert_output(self, token, index, allowempty):
		"""Inserts the specified token into the output.

		This utility routine is used by _newline() and other formatting routines
		to insert tokens into the output sometime prior to the current end of
		the output. The index parameter (which is always negative) specifies
		how many non-junk tokens are to be skipped over before inserting the
		specified token.

		Note that the method takes care to preserve the invariants that the
		state save/restore methods rely upon.

		If allowempty is False, and the token to be inserted is an INDENT
		(newline) token, the method will scan for an existing token of the same
		time at the requested insert location. If an existing INDENT token is
		found, it will be replaced by the new token. Otherwise, (if allowempty
		is True) the new token will be inserted unconditionally. In other
		words, this parameter allows or disallows the insertion of empty lines.
		"""
		if index == 0:
			i = len(self._output)
		elif index < 0:
			i = len(self._output) - 1
			while index < 0:
				while self._output[i].type in (TT.COMMENT, TT.WHITESPACE):
					i -= 1
				index += 1
		else:
			assert False
		# Check that the statestack invariant (see _save_state()) is preserved
		assert (len(self._states) == 0) or (i >= self._states[-1][2])
		# Check for duplicates - replace if we're about to duplicate the token
		if not allowempty and self._output[i - 1].type == token.type and token.type == TT.INDENT:
			self._output[i - 1] = token
		else:
			self._output.insert(i, token)

	def _update_output(self, token, index):
		"""Changes the specified token in the output.

		This utility routine is used to rewrite tokens in the output sometime
		prior to the current end of the output.  The index parameter (which is
		always negative) specifies how many non-junk tokens are to be skipped
		over before changing the specified token.

		Note that the method takes care to preserve the invariants that the
		state save/restore methods rely upon.
		"""
		if index == 0:
			i = len(self._output)
		elif index < 0:
			i = len(self._output) - 1
			while index < 0:
				while self._output[i].type in (TT.COMMENT, TT.WHITESPACE):
					i -= 1
				index += 1
		else:
			assert False
		# Check that the statestack invariant (see _save_state()) is preserved
		assert (len(self._states) == 0) or (i >= self._states[-1][2])
		# Check for duplicates - replace if we're about to duplicate the token
		self._output[i - 1] = token

	def _save_state(self):
		"""Saves the current state of the parser on a stack for later retrieval."""
		# An invariant observed throughout this class (and its descendents) is
		# that the output list NEVER shrinks, and is only ever appended to.
		# Hence, to be able to roll back to a prior state, we don't need to
		# store the entire output list, merely its length will suffice.
		#
		# Note that the _insert_output() method does *insert* rather than
		# append tokens (when called with a negative index).  However, provided
		# the tokens are inserted *after* the position in the output list where
		# the state was last saved, this also maintains the invariant (the
		# _insert_output() method includes an assertion to ensure this is the
		# case).
		self._states.append((
			self._index,
			self._level,
			len(self._output)
		))

	def _restore_state(self):
		"""Restores the state of the parser from the head of the save stack."""
		(
			self._index,
			self._level,
			output_len
		) = self._states.pop()
		del self._output[output_len:]

	def _forget_state(self):
		"""Destroys the saved state at the head of the save stack."""
		self._states.pop()

	def _token(self, index=None):
		"""Returns the token at the specified index, or an EOF token."""
		try:
			return self._tokens[self._index if index is None else index]
		except IndexError:
			# If the current index is beyond the end of the token stream,
			# return a "fake" EOF token to represent this
			if self._tokens:
				return Token(TT.EOF, None, '', *self._tokens[-1][3:])
			else:
				return Token(TT.EOF, None, '', 0, 0)

	def _cmp_tokens(self, token, template):
		"""Compares a token against a partial template.

		If the template is just a string, it will match a KEYWORD, OPERATOR, or
		IDENTIFIER token with the same value (the second element of a token).
		If the template is an integer (like the KEYWORD or IDENTIFIER
		constants) it will match a token with the same type, with the following
		exceptions:

		* IDENTIFIER will also match KEYWORD tokens (to allow keywords to be
		  used as identifiers)
		* DATATYPE and REGISTER will match KEYWORD or IDENTIFIER (DATATYPE and
		  REGISTER tokens should never appear in the input and this allows
		  keywords like CHARACTER or identifiers like DECIMAL to be treated as
		  datatypes, and things like CURRENT DATE to be treated as special
		  registers)
		* STATEMENT will match TERMINATOR (STATEMENT tokens are terminators
		  but specific to a top-level SQL statement or CLP command), or EOF
		  (the script is assumed to end with an implicit terminator)

		If the template is a tuple it will match a token with the same element
		values up to the number of elements in the partial token.

		The method returns the matched token (transformed if any
		transformations were necessary to make the match, e.g. KEYWORD to
		IDENTIFIER).
		"""
		# List of token type transformations that are permitted to occur in
		# order to obtain a successful match (e.g. if we're expecting a
		# DATATYPE but find an IDENTIFIER, the comparison method may mutate the
		# IDENTIFIER token into a DATATYPE token and return it, indicating a
		# successful match)
		transforms = {
			TT.KEYWORD:     (TT.IDENTIFIER, TT.DATATYPE, TT.REGISTER, TT.SCHEMA, TT.RELATION, TT.ROUTINE),
			TT.IDENTIFIER:  (TT.DATATYPE, TT.REGISTER, TT.SCHEMA, TT.RELATION, TT.ROUTINE),
			TT.STRING:      (TT.PASSWORD,),
			TT.TERMINATOR:  (TT.STATEMENT,),
			TT.EOF:         (TT.STATEMENT,),
		}
		if isinstance(template, basestring):
			if token.type in (TT.KEYWORD, TT.OPERATOR) and token.value == template:
				return token
			elif token.type == TT.IDENTIFIER and token.value == template and token.source[0] != '"':
				# Only unquoted identifiers are matched (quoted identifiers
				# aren't used in any part of the SQL dialect)
				return token
		elif isinstance(template, int):
			if token.type == template:
				return token
			elif template in transforms.get(token.type, ()):
				return Token(template, *token[1:])
			else:
				return None
		elif isinstance(template, tuple):
			if token[:len(template)] == template:
				return token
			elif (token.value == template[1]) and (template[0] in transforms.get(token.type, ())):
				return Token(template[0], *token[1:])
			else:
				return None
		else:
			assert False, "Invalid template token (%s) %s" % (str(type(template)), str(template))

	def _peek(self, template):
		"""Compares the current token against a template token.

		Compares the provided template token against the current token in the
		stream. If the comparison is successful, the input token is returned
		(note that the _cmp_tokens() method may transform the token to match
		the provided template). Otherwise, None is returned. The current
		position, and the output list are never altered by this method.
		"""
		return self._cmp_tokens(self._token(), template)

	def _peek_one_of(self, templates):
		"""Compares the current token against several template tokens.

		Compares the provided list of template tokens against the current token
		in the stream. If the comparison is successful, the input token is
		returned (note that the _cmp_tokens() method may transform the token to
		match the template which successfully matched). Otherwise, None is
		returned. The current position, and the output list are never altered
		by this method.
		"""
		for template in templates:
			t = self._cmp_tokens(self._token(), template)
			if t:
				return t
		return None

	def _prespace_default(self, template):
		"""Determines the default prespace setting for a _match() template."""
		return template not in (
			'.', ',', ')',
			(TT.OPERATOR, '.'),
			(TT.OPERATOR, ','),
			(TT.OPERATOR, ')'),
			TT.TERMINATOR,
			TT.STATEMENT,
		)

	def _postspace_default(self, template):
		"""Determines the default postspace setting for a _match() template."""
		return template not in (
			'.', '(',
			(TT.OPERATOR, '.'),
			(TT.OPERATOR, '('),
		)

	def _match(self, template, prespace=None, postspace=None):
		"""Attempt to match the current token against a template token.

		Matches the provided template token against the current token in the
		stream. If the match is successful the current position is moved
		forward to the next non-junk token, and the (potentially transformed)
		matched token is returned. Otherwise, None is returned and the current
		position is not moved.

		The prespace and postspace parameters affect the insertion of
		WHITESPACE tokens into the output when WHITESPACE is present in the
		reformat set property, and a match is successful. If prespace is True,
		a WHITESPACE token containing a single space is added to the output
		prior to appending the matching token. However, if prespace is False,
		no WHITESPACE token will be added, only the matching token.  If
		postspace is False, it will override the prespace setting of the next
		match (useful for suppressing space next to right-associative operators
		like unary plus/minus).

		Note that a False value in either prespace or postspace always
		overrides a True value, i.e. if a match sets postspace to False, the
		value of prespace in the subsequent match is irrelevant; no space will
		be added.  Likewise if a match sets postspace to True, a False prespace
		value in a subsequent match will override this and prevent space from
		being added.

		By default prespace and postspace are None. In this case, the
		_prespace_default() and _postspace_default() methods will be called to
		determine the default based on the match template. These methods should
		be overridden by descendents to deal with additional syntax introduced
		by the dialect they represent. The default implementations in this
		class suppress prespace in the case of dot, comma and close-parenthesis
		operators and postspace in the case of dot and open-parenthesis.
		"""
		# Compare the current token against the template. Note that the
		# template may transform the token in order to match (see _cmp_tokens)
		token = self._cmp_tokens(self._token(), template)
		if not token:
			return None
		# If a match was found, add a leading space (if WHITESPACE is being
		# reformatted, and prespace permits it)
		if TT.WHITESPACE in self.reformat:
			if prespace is None:
				prespace = self._prespace_default(template)
			if prespace and self._output and self._output[-1].type not in (TT.INDENT, TT.WHITESPACE):
				self._output.append(Token(TT.WHITESPACE, None, ' ', 0, 0))
		self._output.append(token)
		self._index += 1
		while self._token().type in (TT.COMMENT, TT.WHITESPACE):
			if self._token().type == TT.COMMENT or TT.WHITESPACE not in self.reformat:
				self._output.append(self._token())
			self._index += 1
		# If postspace is False, prevent the next _match call from adding a
		# leading space by adding an empty WHITESPACE token. The final phase of
		# the parser removes empty tokens.
		if TT.WHITESPACE in self.reformat:
			if postspace is None:
				postspace = self._postspace_default(template)
			if not postspace:
				self._output.append(Token(TT.WHITESPACE, None, '', 0, 0))
		return token

	def _match_sequence(self, templates, prespace=None, postspace=None, interspace=None):
		"""Attempt to match the next sequence of tokens against a list of template tokens.

		Matches the list of non-junk tokens (tokens which are not WHITESPACE or
		COMMENT) from the current position up to the length of the templates
		list. The _cmp_tokens() method is used for matching. Refer to that
		method for the matching algorithm.

		The method returns the list of the non-junk tokens that were matched.
		If a match is found, the output list and current token position are
		updated. Otherwise, no changes to the internal state are made
		(regardless of the length of the list of tokens to match).

		See _match() for a description of prespace and postspace. The optional
		interspace parameter specifies the spacing rule between each template
		in the sequence.
		"""
		self._save_state()
		# Build lists of prespace and postspace settings for each template and
		# zip them together in the loop
		prespaces = [prespace] + [interspace for i in xrange(len(templates) - 1)]
		postspaces = [interspace for i in xrange(len(templates) - 1)] + [postspace]
		for (template, prespace, postspace) in zip(templates, prespaces, postspaces):
			if not self._match(template, prespace, postspace):
				self._restore_state()
				return None
		# If the loop completes, we've matched all templates in the sequence.
		# Use the last entry on the state stack to determine all the tokens
		# we've added to the output and strip out all the COMMENT and
		# WHITESPACE tokens
		result = [
			token for token in self._output[self._states[-1][2]:]
			if token.type not in (TT.COMMENT, TT.WHITESPACE)
		]
		self._forget_state()
		return result

	def _match_one_of(self, templates, prespace=None, postspace=None):
		"""Attempt to match the current token against one of several templates.

		Matches the current token against one of several possible
		partial tokens provided in a list. If a match is found, the method
		returns the matched token, and moves the current position forward to
		the next non-junk token. If no match is found, the method returns None.

		See _match() for a description of prespace and postspace.
		"""
		for template in templates:
			token = self._match(template, prespace, postspace)
			if token:
				return token
		return None

	def _expect(self, template, prespace=None, postspace=None):
		"""Match the current token against a template token, or raise an error.

		The _expect() method is essentially the same as _match() except that if
		a match is not found, a ParseError exception is raised stating that the
		parser "expected" the specified token, but found something else.

		See _match() for a description of prespace and postspace.
		"""
		result = self._match(template, prespace, postspace)
		if not result:
			self._expected(template)
		return result

	def _expect_sequence(self, templates, prespace=None, postspace=None, interspace=None):
		"""Match the next sequence of tokens against a list of templates, or raise an error.

		The _expect_sequence() method is equivalent to the _match_sequence()
		method except that if a match is not found, a ParseError exception is
		raised with a message indicating that a certain sequence was expected,
		but something else was found.

		See _match() for a description of prespace and postspace. The optional
		interspace parameter specifies the spacing rule between each template
		in the sequence.
		"""
		result = self._match_sequence(templates, prespace, postspace, interspace)
		if not result:
			self._expected_sequence(templates)
		return result

	def _expect_one_of(self, templates, prespace=None, postspace=None):
		"""Match the current token against one of several templates, or raise an error.

		The _expect_one_of() method is equivalent to the _match_one_of() method
		except that if a match is not found, a ParseError exception is raised
		with a message indicating that one of several possibilities was
		expected, but something else was found.

		See _match() for a description of prespace and postspace.
		"""
		result = self._match_one_of(templates, prespace, postspace)
		if not result:
			self._expected_one_of(templates)
		return result

	def _expected(self, template):
		"""Raises an error explaining a token template was expected."""
		raise ParseExpectedOneOfError(self._source, self._token(), [template])

	def _expected_sequence(self, templates):
		"""Raises an error explaining a sequence of template tokens was expected."""
		# Build a list of tokens from the source that are as long as the
		# expected sequence
		found = []
		i = self._index
		for template in templates:
			found.append(self._token())
			i += 1
			while self._token(i).type in (TT.COMMENT, TT.WHITESPACE):
				i += 1
		raise ParseExpectedSequenceError(self._source, found, templates)

	def _expected_one_of(self, templates):
		"""Raises an error explaining one of several template tokens was expected."""
		raise ParseExpectedOneOfError(self._source, self._token(), templates)

