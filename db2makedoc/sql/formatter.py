# vim: set noet sw=4 ts=4:

"""Implements a class for reflowing "raw" SQL.

This unit implements a class which reformats SQL that has been "mangled" in
some manner, typically by being parsed and stored by a database (e.g.  line
breaks stripped, all whitespace converted to individual spaces, etc).  The
reformatted SQL is intended to be more palatable for human consumption (aka
"readable" :-)

The class is capable of reformatting the vast majority of the DB2 SQL dialect
(both DDL and DML commands).
"""

import re
import sys
import math
from db2makedoc.sql.dialects import *
from db2makedoc.sql.tokenizer import *

__all__ = [
	'EOF',
	'ERROR',
	'WHITESPACE',
	'COMMENT',
	'KEYWORD',
	'IDENTIFIER',
	'NUMBER',
	'STRING',
	'OPERATOR',
	'LABEL',
	'PARAMETER',
	'TERMINATOR',
	'DATATYPE',
	'REGISTER',
	'STATEMENT',
	'INDENT',
	'VALIGN',
	'VAPPLY',
	'Error',
	'ParseError',
	'ParseBacktrack',
	'ParseTokenError',
	'ParseExpectedOneOfError',
	'ParseExpectedSequenceError',
	'BaseFormatter',
	'DB2LUWFormatter',
]

# Custom token types used by the formatter
(
	DATATYPE,  # Datatypes (e.g. VARCHAR) converted from KEYWORD or IDENTIFIER
	REGISTER,  # Special registers (e.g. CURRENT DATE) converted from KEYWORD or IDENTIFIER
	STATEMENT, # Statement terminator
	INDENT,    # Whitespace indentation at the start of a line
	VALIGN,    # Whitespace indentation within a line to vertically align blocks of text
	VAPPLY,    # Mark the end of a run of VALIGN tokens
) = new_tokens(6)

# Token labels used for formatting error messages and token dumps
TOKEN_LABELS = {
	EOF:        '<eof>',
	ERROR:      'error',
	WHITESPACE: '<space>',
	COMMENT:    'comment',
	KEYWORD:    'keyword',
	IDENTIFIER: 'identifier',
	NUMBER:     'number',
	STRING:     'string',
	OPERATOR:   'operator',
	LABEL:      'label',
	PARAMETER:  'parameter',
	TERMINATOR: '<terminator>',
	DATATYPE:   'datatype',
	REGISTER:   'register',
	STATEMENT:  '<statement-end>',
	INDENT:     '<indent>',
	VALIGN:     '<valign>',
	VAPPLY:     '<vapply>',
}

# Standard size suffixes and multipliers
SUFFIX_KMG = {
	'K': 1024**1,
	'M': 1024**2,
	'G': 1024**3,
}

ctrlchars = re.compile(ur'([\x00-\x1F\x7F]+)')
def quote_str(s, qchar="'"):
	"""Quotes a string, doubling all quotation characters within it.

	The s parameter provides the string to be quoted. The optional qchar
	parameter provides the quotation mark used to enclose the string. If the
	string contains any control characters (tabs, newlines, etc.) they will be
	quoted as a hex-string (i.e. a string prefixed by X which contains bytes
	encoded as two hex numbers), and concatenated to the rest of the string.
	"""
	result = []
	for index, group in enumerate(ctrlchars.split(s)):
		if group:
			if index % 2:
				result.append('X%s%s%s' % (qchar, ''.join('%.2X' % ord(c) for c in group), qchar))
			else:
				result.append('%s%s%s' % (qchar, group.replace(qchar, qchar*2), qchar))
	return ' || '.join(result)

def dump(tokens):
	"""Utility routine for debugging purposes: prints the tokens in a human readable format."""
	print '\n'.join(format_token(token) for token in tokens)

def format_token(token):
	"""Formats a token for the dump routine above."""
	return '%-16s %-20s %-20s' % (TOKEN_LABELS[token[0]], repr(token[1]), repr(token[2]))

def format_ident(name, namechars=set(db2luw_namechars), qchar='"'):
	"""Format an SQL identifier with quotes if required.

	The name parameter provides the object name to format. The optional
	namechars parameter provides the set of characters which are permitted in
	unquoted names. If the entire name consists of such characters (excepting
	the initial character which is not permitted to be a numeral) it will be
	returned unquoted. Otherwise, quote_str() will be called with the optional
	qchar parameter to quote the name.

	Note that the default for namechars is one of the namechars strings from
	the sql.dialects module, NOT one of the identchars strings. While lowercase
	characters are usually permitted in identifiers, they are folded to
	uppercase by the database, and the tokenizer emulates this. This routine is
	for output and therefore lowercase characters in name will trigger quoting.
	"""
	firstchars = namechars - set('0123456789')
	if len(name) == 0:
		raise ValueError('Blank identifier')
	if not name[0] in firstchars:
		return quote_str(name, qchar)
	for c in name[1:]:
		if not c in namechars:
			return quote_str(name, qchar)
	return name

def format_param(param):
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
		return ':%s' % (format_ident(param))

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

class Error(Exception):
	"""Base class for errors in this module"""

	def __init__(self, msg=''):
		"""Initializes an instance of the exception with an optional message"""
		Exception.__init__(self, msg)
		self.message = msg

	def __repr__(self):
		"""Outputs a representation of the exception"""
		return 'Error(%s)' % repr(self.message)

	def __str__(self):
		"""Outputs the message of the exception"""
		return self.message

class ParseError(Error):
	"""Base class for errors encountered during parsing"""
	pass

class ParseBacktrack(ParseError):
	"""Fake exception class raised internally when the parser needs to backtrack"""

	def __init__(self):
		"""Initializes an instance of the exception"""
		# The message is irrelevant as this exception should never propogate
		# outside the parser
		ParseError.__init__(self, msg='')

class ParseTokenError(ParseError):
	"""Raised when a parsing error is encountered"""

	def __init__(self, tokens, errtoken, msg):
		"""Initializes an instance of the exception.

		The parameters are as follows:
		tokens -- The tokens forming the source being parsed
		errtoken -- The token at which the error occurred
		msg -- The descriptive error message
		"""
		# Store the error token and source
		self.source = tokens
		self.token = errtoken
		# Split out the line and column of the error
		(_, _, _, self.line, self.col) = errtoken
		# Initialize the exception
		ParseError.__init__(self, msg)

	def __str__(self):
		"""Outputs a string version of the exception."""
		# Generate a block of context with an indicator showing the error
		context_lines = 5
		sourcelines = ''.join(s for (_, _, s, _, _) in self.source).splitlines()
		lineindex = self.line - 1
		if self.line > len(sourcelines):
			lineindex = -1
		marker = ''.join({'\t': '\t'}.get(c, ' ') for c in sourcelines[lineindex][:self.col-1]) + '^'
		sourcelines.insert(self.line, marker)
		i = self.line - context_lines
		if i < 0:
			i = 0
		context = '\n'.join(sourcelines[i:self.line + context_lines])
		# Format the message with the context
		return '\n'.join([
			self.message + ':',
			'line   : %d' % self.line,
			'column : %d' % self.col,
			'context:',
			context
		])

	def token_name(self, token):
		"""Formats a token for display in an error message string"""
		if isinstance(token, basestring):
			return token
		elif isinstance(token, int):
			return TOKEN_LABELS[token]
		elif isinstance(token, tuple):
			if (len(token) == 1) or (token[0] in (EOF, WHITESPACE, TERMINATOR, STATEMENT)):
				return TOKEN_LABELS[token[0]]
			elif (len(token) == 2) and (token[1] is not None):
				return token[1]
			else:
				return token[2]
		else:
			return None

class ParseExpectedOneOfError(ParseTokenError):
	"""Raised when the parser didn't find a token it was expecting"""

	def __init__(self, tokens, errtoken, expected):
		"""Initializes an instance of the exception.

		The parameters are as follows:
		tokens -- The tokens forming the source being parsed
		errtoken -- The unexpected token that was found
		expected -- A list of alternative tokens that was expected at this location
		"""
		msg = 'Expected %s but found "%s"' % (
			', '.join(['"%s"' % (self.token_name(t),) for t in expected]),
			self.token_name(errtoken)
		)
		ParseTokenError.__init__(self, tokens, errtoken, msg)

class ParseExpectedSequenceError(ParseTokenError):
	"""Raised when the parser didn't find a sequence of tokens it was expecting"""

	def __init__(self, tokens, errtokens, expected):
		"""Initializes an instance of the exception.

		The parameters are as follows:
		tokens -- The tokens forming the source being parsed
		errtokens -- The unexpected sequenced of tokens that was found
		expected -- A sequence of tokens that was expected at this location
		"""
		msg = 'Expected "%s" but found "%s"' % (
			' '.join([self.token_name(t) for t in expected]),
			' '.join([self.token_name(t) for t in errtokens])
		)
		ParseTokenError.__init__(self, tokens, errtokens[0], msg)

class BaseFormatter(object):
	"""Base class for parsers.

	Do not use this class directly. Instead use one of the descendent classes
	(currently only DB2LUWFormatter) depending on your needs.
	
	The class accepts input from one of the tokenizers in the tokenizer unit,
	in the form of a list of tokens, where tokens are 5-element tuples with the
	following structure:

		(token_type, token_value, source, line, column)

	To use the class simply pass such a list to the parse method. The method
	will return a list of tokens (just like the list of tokens provided as
	input, but reformatted according to the properties detailed below).

	The token_type element gives the general "family" of the token (such as
	OPERATOR, IDENTIFIER, etc), while the token_value element provides the
	specific type of the token (e.g. "=", "OR", "DISTINCT", etc). The code in
	these classes typically uses "partial" tokens to match against "complete"
	tokens in the source. For example, instead of trying to match on the source
	element (which may vary in case), this class often matches token on the
	first two elements:

		(KEYWORD, "OR", "or", 7, 13)[:2] == (KEYWORD, "OR")

	A set of internal utility methods are used to simplify this further. See
	the _match and _expect methods in particular. The numerous _parse_X methods
	in each class define the grammar of the SQL language being parsed.
	
	The following options are available for customizing the reformatting performed
	by the class:

	reformat    A set of token types to undergo reformatting. By default this
	            set includes all token types output by the parser.  See below
	            for the specific types of reformatting performed by token type.
	indent      If WHITESPACE is present in the reformat set, this is the
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
	            containing lowercase characters, symbols, etc.) will be folded
	            to uppercase.
	DATATYPE    Same as IDENTIFIER.
	LABEL       Same as IDENTIFIER, with a colon suffix.
	PARAMETER   Same as IDENTIFIER, with a colon prefix for named parameters.
	NUMBER      All numbers will be formatted without extraneous leading or
	            trailing zeros (or decimal portions), and uppercase signed
	            exponents (where the original had an exponent). Extraneous
	            unary plus operators will be included where present in the
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
	
	If other token types are included in the set (e.g. EOF, TERMINATOR, etc.)
	they will be ignored.
	"""

	def __init__(self):
		super(BaseFormatter, self).__init__()
		self.indent = ' ' * 4
		self.reformat = set([
			DATATYPE,
			IDENTIFIER,
			KEYWORD,
			LABEL,
			NUMBER,
			PARAMETER,
			REGISTER,
			STATEMENT,
			STRING,
			TERMINATOR,
			WHITESPACE,
		])
		self.line_split = False
		self.statement = ';'
		self.terminator = ';'

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
			while self._token(self._index)[0] in (COMMENT, WHITESPACE, TERMINATOR):
				self._index += 1
			# If not at EOF, parse a statement
			if not self._match(EOF):
				self._parse_top()
				self._expect(STATEMENT) # STATEMENT converts TERMINATOR into STATEMENT
				assert len(self._statestack) == 0
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
		self._statestack = []
		self._index = 0
		self._output = []
		self._level = 0
		# If we're reformatting spaces, strip all WHITESPACE tokens from the
		# input (no point parsing them if we're going to rewrite them all
		# anyway)
		if WHITESPACE in self.reformat:
			self._tokens = [token for token in tokens if token[0] != WHITESPACE]
		else:
			self._tokens = tokens

	def _parse_finish(self):
		"""Cleans up and finalizes tokens in the output."""
		# Firstly, handle translating INDENT tokens into ordinary WHITESPACE
		# tokens, and reformatting other tokens according to the reformat set.
		# Note this phase also strips location information from tokens
		output = []
		for token in self._output:
			token = token[:3]
			if token[0] == INDENT and WHITESPACE in self.reformat:
				token = (WHITESPACE, None, '\n' + self.indent * token[1])
			elif token[0] in self.reformat:
				if token[0] in (KEYWORD, REGISTER):
					token = (token[0], token[1], token[1])
				elif token[0] in (IDENTIFIER, DATATYPE):
					token = (token[0], token[1], format_ident(token[1]))
				elif token[0] == NUMBER:
					token = (NUMBER, token[1], str(token[1]))
				elif token[0] == STRING:
					token = (STRING, token[1], quote_str(token[1]))
				elif token[0] == LABEL:
					token = (LABEL, token[1], format_ident(token[1]) + ':')
				elif token[0] == PARAMETER:
					token = (PARAMETER, token[1], format_param(token[1]))
				elif token[0] == COMMENT:
					# XXX Need more intelligent comment handling
					##token = (COMMENT, token[1], '/*%s*/' % (token[1]))
					pass
				elif token[0] == STATEMENT:
					token = (STATEMENT, token[1], self.statement)
				elif token[0] == TERMINATOR:
					token = (TERMINATOR, token[1], self.terminator)
			output.append(token)
		self._output = output
		# Next, VALIGN and VAPPLY tokens are converted. Multiple passes are
		# used to convert the VALIGN tokens; each pass converts the first
		# VALIGN token found on a contiguous set of lines into WHITESPACE
		# tokens and removes the trailing VAPPLY token
		if WHITESPACE in self.reformat:
			indexes = []
			found = True
			while found:
				found = False
				# Recalculate the positions of all tokens; earlier phases may
				# have altered them and we need accurate positions to calculate
				# vertical alignment positions
				self._recalc_positions()
				aligncol = 0
				i = 0
				while i < len(self._output):
					token = self._output[i]
					if token[0] == VALIGN:
						# Remember the position of the VALIGN token, adjust the
						# alignment column if necessary, and skip to the next
						# line to ignore any further VALIGN tokens on this line
						found = True
						indexes.append(i)
						(line, col) = token[3:]
						aligncol = max(aligncol, col)
						while (self._output[i][3] == line) and (self._output[i][0] != VAPPLY):
							i += 1
					elif token[0] == VAPPLY:
						# Convert all the remembered VALIGN tokens into
						# WHITESPACE tokens with appropriate lengths for
						# vertical alignment, remove the VAPPLY token, and
						# immediately return to the outer loop (to avoid
						# deleting any subsequent VAPPLY tokens)
						found = True
						#assert indexes
						for j in indexes:
							(line, col) = self._output[j][3:]
							self._output[j] = (WHITESPACE, None, ' ' * (aligncol - col), 0, 0)
						indexes = []
						aligncol = 0
						del self._output[i]
						break
					else:
						i += 1
				# If indexes isn't blank, then we encountered VALIGNs without a
				# corresponding VAPPLY (parser bug)
				assert not indexes
		else:
			# If we're not reformatting WHITESPACE tokens, just dump any
			# VALIGN, VAPPLY or INDENT tokens in the output
			self._output = [
				token for token in self._output
				if token[0] not in (VALIGN, VAPPLY, INDENT)
			]
		# If we're doing line splitting, break up any tokens that contain
		# newlines so that every line has a token beginning at column 1
		# Remove all tokens which have no source (likely to only be WHITESPACE
		# tokens generated by the _match() postspace mechanism)
		if self.line_split:
			output = []
			for token in self._output:
				(type, value, source, line, column) = token
				while '\n' in source:
					if isinstance(value, basestring) and '\n' in value:
						i = value.index('\n') + 1
						newvalue = value[:i]
						value = value[i:]
					else:
						newvalue = value
					i = source.index('\n') + 1
					newsource = source[:i]
					source = source[i:]
					output.append((type, newvalue, newsource, line, column))
					line += 1
					column = 1
				output.append((type, value, source, line, column))
			self._output = output
		# Strip trailing whitespace / EOF tokens, then re-append a trailing EOF
		# token (or simply make the output a solitary EOF token if nothing is
		# left)
		while self._output and (self._output[-1][0] in (WHITESPACE, EOF)):
			del self._output[-1]
		if self._output:
			self._output.append((EOF, None, '') + self._output[-1][3:])
		else:
			self._output = [(EOF, None, '', 1, 1)]

	def _parse_top(self):
		"""Top level of the parser.
		
		Override this method in descendents to parse a statement (or whatever
		is at the top of the parse tree).
		"""
		pass

	def _recalc_positions(self):
		"""Recalculates the line and col elements of all output tokens"""
		line = 1
		column = 1
		newoutput = []
		for token in self._output:
			token = token[:3] + (line, column)
			newoutput.append(token)
			source = token[2]
			while '\n' in source:
				line += 1
				column = 1
				source = source[source.index('\n') + 1:]
			column += len(source)
		self._output = newoutput

	def _newline(self, index=0, allowempty=False):
		"""Adds an INDENT token to the output.

		The _newline() method is called to start a new line in the output. It
		does this by appending (or inserting, depending on the index parameter)
		an INDENT token to the output list. Later, during _parse_finish, INDENT
		tokens are converted into WHITESPACE tokens at the specified
		indentation level.

		See _insert_output for an explanation of allowempty.
		"""
		token = (INDENT, self._level, '')
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
		token = (VALIGN, None, '')
		self._insert_output(token, index, True)

	def _vapply(self, index=0):
		"""Inserts a VAPPLY token into the output."""
		token = (VAPPLY, None, '')
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
				while self._output[i][0] in (COMMENT, WHITESPACE):
					i -= 1
				index += 1
		else:
			assert False
		# Check that the statestack invariant (see _save_state()) is preserved
		assert (len(self._statestack) == 0) or (i >= self._statestack[-1][2])
		# Check for duplicates - replace if we're about to duplicate the token
		if not allowempty and self._output[i - 1][0] == token[0] and token[0] == INDENT:
			self._output[i - 1] = token
		else:
			self._output.insert(i, token)

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
		self._statestack.append((self._index, self._level, len(self._output)))

	def _restore_state(self):
		"""Restores the state of the parser from the head of the save stack."""
		(self._index, self._level, output_len) = self._statestack.pop()
		del self._output[output_len:]

	def _forget_state(self):
		"""Destroys the saved state at the head of the save stack."""
		self._statestack.pop()

	def _token(self, index):
		"""Returns the token at the specified index, or an EOF token."""
		try:
			return self._tokens[index]
		except IndexError:
			return self._tokens[-1]

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
		if isinstance(template, basestring):
			if token[0] in (KEYWORD, OPERATOR) and token[1] == template:
				return token
			elif token[0] == IDENTIFIER and token[1] == template and token[2][0] != '"':
				# Only unquoted identifiers are matched (quoted identifiers
				# aren't used in any part of the DB2 SQL dialect)
				return token
		elif isinstance(template, int):
			if token[0] == template:
				return token
			elif token[0] == KEYWORD and template == IDENTIFIER:
				return (IDENTIFIER,) + token[1:]
			elif token[0] in (KEYWORD, IDENTIFIER) and template in (DATATYPE, REGISTER):
				return (template,) + token[1:]
			elif token[0] in (TERMINATOR, EOF) and template == STATEMENT:
				return (STATEMENT,) + token[1:]
			else:
				return None
		elif isinstance(template, tuple):
			if token[:len(template)] == template:
				return token
			elif token[0] in (KEYWORD, IDENTIFIER) and template[0] in (DATATYPE, REGISTER) and token[1] == template[1]:
				return (template[0],) + token[1:]
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
		return self._cmp_tokens(self._token(self._index), template)

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
			t = self._cmp_tokens(self._token(self._index), template)
			if t:
				return t
		return None

	def _prespace_default(self, template):
		"""Determines the default prespace setting for a _match() template."""
		return template not in (
			'.', ',', ')',
			(OPERATOR, '.'),
			(OPERATOR, ','),
			(OPERATOR, ')'),
			TERMINATOR,
			STATEMENT,
			EOF,
		)

	def _postspace_default(self, template):
		"""Determines the default postspace setting for a _match() template."""
		return template not in (
			'.', '(',
			(OPERATOR, '.'),
			(OPERATOR, '('),
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
		token = self._cmp_tokens(self._token(self._index), template)
		if not token:
			return None
		# If a match was found, add a leading space (if WHITESPACE is being
		# reformatted, and prespace permits it)
		if WHITESPACE in self.reformat:
			if prespace is None:
				prespace = self._prespace_default(template)
			if prespace and not (self._output and self._output[-1][0] in (INDENT, WHITESPACE)):
				self._output.append((WHITESPACE, None, ' ', 0, 0))
		self._output.append(token)
		self._index += 1
		while self._token(self._index)[0] in (COMMENT, WHITESPACE):
			self._output.append(self._token(self._index))
			self._index += 1
		# If postspace is False, prevent the next _match call from adding a
		# leading space by adding an empty WHITESPACE token. The final phase of
		# the parser removes empty tokens.
		if WHITESPACE in self.reformat:
			if postspace is None:
				postspace = self._postspace_default(template)
			if not postspace:
				self._output.append((WHITESPACE, None, '', 0, 0))
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
			token for token in self._output[self._statestack[-1][2]:]
			if token[0] not in (COMMENT, WHITESPACE)
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
		raise ParseExpectedOneOfError(self._tokens, self._token(self._index), [template])

	def _expected_sequence(self, templates):
		"""Raises an error explaining a sequence of template tokens was expected."""
		# Build a list of tokens from the source that are as long as the
		# expected sequence
		found = []
		i = self._index
		for template in templates:
			found.append(self._token(self._index))
			i += 1
			while self._token(i)[0] in (COMMENT, WHITESPACE):
				i += 1
		raise ParseExpectedSequenceError(self._tokens, found, templates)

	def _expected_one_of(self, templates):
		"""Raises an error explaining one of several template tokens was expected."""
		raise ParseExpectedOneOfError(self._tokens, self._token(self._index), templates)


class DB2LUWFormatter(BaseFormatter):
	"""Reformatter which breaks up and re-indents DB2 for LUW's SQL dialect.

	This class is, at its core, a full blown SQL language parser that
	understands many common SQL DML and DDL commands (from the basic ones like
	INSERT, UPDATE, DELETE, SELECT, to the more DB2 specific ones such as
	CREATE TABLESPACE, CREATE FUNCTION, and dynamic compound statements).
	"""

	def _parse_top(self):
		# Override _parse_top to make a 'statement' the top of the parse tree
		self._parse_statement()

	def _prespace_default(self, template):
		# Overridden to include array and set operators, and the specific
		# intra-statement terminator used by func/proc definitions
		return super(DB2LUWFormatter, self)._prespace_default(template) and template not in (
			']', '}', ';',
			(OPERATOR, ']'),
			(OPERATOR, '}'),
			(TERMINATOR, ';'),
		)

	def _postspace_default(self, template):
		# Overridden to include array and set operators
		return super(DB2LUWFormatter, self)._postspace_default(template) and template not in (
			'[', '{',
			(OPERATOR, '['),
			(OPERATOR, '{'),
		)

	# PATTERNS ###############################################################

	def _parse_subrelation_name(self):
		"""Parses the (possibly qualified) name of a relation-owned object.

		A relation-owned object is either a column or a constraint. This method
		parses such a name with up to two optional qualifiers (e.g., it is
		possible in a SELECT statement with no table correlation clauses to
		specify SCHEMA.TABLE.COLUMN). The method returns the parsed name as a
		tuple with 3 elements (None is used for qualifiers which are missing).
		"""
		result = (None, None, self._expect(IDENTIFIER)[1])
		if self._match('.'):
			result = (None, result[2], self._expect(IDENTIFIER)[1])
			if self._match('.'):
				result = (result[1], result[2], self._expect(IDENTIFIER)[1])
		return result

	_parse_column_name = _parse_subrelation_name
	_parse_constraint_name = _parse_subrelation_name
	# These are cheats; remote object names consist of server.schema.object
	# instead of schema.relation.object, and source object names consist of
	# schema.package.object, but they'll do
	_parse_remote_object_name = _parse_subrelation_name
	_parse_source_object_name = _parse_subrelation_name

	def _parse_subschema_name(self):
		"""Parses the (possibly qualified) name of a schema-owned object.

		A schema-owned object is a table, view, index, function, sequence, etc.
		This method parses such a name with an optional qualifier (the schema
		name). The method returns the parsed name as a tuple with 2 elements
		(None is used for the schema qualifier if it is missing).
		"""
		result = (None, self._expect(IDENTIFIER)[1])
		if self._match('.'):
			result = (result[1], self._expect(IDENTIFIER)[1])
		return result

	_parse_relation_name = _parse_subschema_name
	_parse_table_name = _parse_subschema_name
	_parse_view_name = _parse_subschema_name
	_parse_alias_name = _parse_subschema_name
	_parse_nickname_name = _parse_subschema_name
	_parse_trigger_name = _parse_subschema_name
	_parse_index_name = _parse_subschema_name
	_parse_routine_name = _parse_subschema_name
	_parse_function_name = _parse_subschema_name
	_parse_procedure_name = _parse_subschema_name
	_parse_method_name = _parse_subschema_name
	_parse_sequence_name = _parse_subschema_name
	_parse_type_name = _parse_subschema_name
	_parse_variable_name = _parse_subschema_name
	# Another cheat; security labels exist within a security policy
	_parse_security_label_name = _parse_subschema_name

	def _parse_size(self, optional=False, suffix={}):
		"""Parses a parenthesized size with an optional scale suffix.

		This method parses a parenthesized integer number. The optional
		parameter controls whether an exception is raised if an opening
		parenthesis is not encountered at the current input position. The
		suffix parameter is a dictionary mapping suffix->multiplier. The global
		constant SUFFIX_KMG defines a commonly used suffix mapping (K->1024,
		M->1024**2, etc.)
		"""
		if optional:
			if not self._match('(', prespace=False):
				return None
		else:
			self._expect('(', prespace=False)
		size = self._expect(NUMBER)[1]
		if suffix:
			suf = self._match_one_of(suffix.keys())
			if suf:
				size *= suffix[suf[1]]
		self._expect(')')
		return size

	def _parse_special_register(self):
		"""Parses a special register (e.g. CURRENT_DATE)"""
		if self._match((REGISTER, 'CURRENT')):
			if self._match_one_of([
				(REGISTER, 'CLIENT_ACCTNG'),
				(REGISTER, 'CLIENT_APPLNAME'),
				(REGISTER, 'CLIENT_USERID'),
				(REGISTER, 'CLIENT_WRKSTNNAME'),
				(REGISTER, 'DATE'),
				(REGISTER, 'DBPARTITIONNUM'),
				(REGISTER, 'DEGREE'),
				(REGISTER, 'ISOLATION'),
				(REGISTER, 'NODE'),
				(REGISTER, 'PATH'),
				(REGISTER, 'SCHEMA'),
				(REGISTER, 'SERVER'),
				(REGISTER, 'SQLID'),
				(REGISTER, 'TIME'),
				(REGISTER, 'TIMESTAMP'),
				(REGISTER, 'TIMEZONE'),
				(REGISTER, 'USER'),
			]):
				pass
			elif self._match_sequence([
				(REGISTER, 'DECFLOAT'),
				(REGISTER, 'ROUNDING'),
				(REGISTER, 'MODE')
			]):
				pass
			elif self._match_sequence([
				(REGISTER, 'DEFAULT'),
				(REGISTER, 'TRANSFORM'),
				(REGISTER, 'GROUP')
			]):
				pass
			elif self._match((REGISTER, 'EXPLAIN')):
				self._expect_one_of([
					(REGISTER, 'MODE'),
					(REGISTER, 'SNAPSHOT')
				])
			elif self._match_sequence([
				(REGISTER, 'FEDERATED'),
				(REGISTER, 'ASYNCHRONY')
			]):
				pass
			elif self._match_sequence([
				(REGISTER, 'IMPLICIT'),
				(REGISTER, 'XMLPARSE'),
				(REGISTER, 'OPTION')]
			):
				pass
			elif self._match_sequence([
				(REGISTER, 'LOCK'),
				(REGISTER, 'TIMEOUT')
			]):
				pass
			elif self._match_sequence([
				(REGISTER, 'MAINTAINED'),
				(REGISTER, 'TABLE'),
				(REGISTER, 'TYPES'),
				(REGISTER, 'FOR'),
				(REGISTER, 'OPTIMIZATION')
			]):
				pass
			elif self._match_sequence([
				(REGISTER, 'MDC'),
				(REGISTER, 'ROLLOUT'),
				(REGISTER, 'MODE')
			]):
				pass
			elif self._match_sequence([
				(REGISTER, 'OPTIMIZATION'),
				(REGISTER, 'PROFILE')
			]):
				pass
			elif self._match_sequence([
				(REGISTER, 'PACKAGE'),
				(REGISTER, 'PATH')
			]):
				pass
			elif self._match_sequence([
				(REGISTER, 'QUERY'),
				(REGISTER, 'OPTIMIZATION')
			]):
				pass
			elif self._match_sequence([
				(REGISTER, 'REFRESH'),
				(REGISTER, 'AGE')
			]):
				pass
			else:
				self._expected((REGISTER,))
		elif self._match((REGISTER, 'CLIENT')):
			self._expect_one_of([
				(REGISTER, 'ACCTNG'),
				(REGISTER, 'APPLNAME'),
				(REGISTER, 'USERID'),
				(REGISTER, 'WRKSTNNAME'),
			])
		else:
			self._expect_one_of([
				(REGISTER, 'CURRENT_DATE'),
				(REGISTER, 'CURRENT_PATH'),
				(REGISTER, 'CURRENT_SCHEMA'),
				(REGISTER, 'CURRENT_SERVER'),
				(REGISTER, 'CURRENT_TIME'),
				(REGISTER, 'CURRENT_TIMESTAMP'),
				(REGISTER, 'CURRENT_TIMEZONE'),
				(REGISTER, 'CURRENT_USER'),
				(REGISTER, 'SESSION_USER'),
				(REGISTER, 'SYSTEM_USER'),
				(REGISTER, 'USER'),
			])

	def _parse_datatype(self):
		"""Parses a (possibly qualified) data type with optional arguments.

		Parses a data type name with an optional qualifier (the schema name).
		The method returns a tuple with the following structure:

			(schema_name, type_name, size, scale)

		If the type has no parameters size and/or scale may be None. If the
		schema is not specified, schema_name is None, unless the type is a
		builtin type in which case the schema_name will always be 'SYSIBM'
		regardless of whether a schema was specified with the type in the
		source.
		"""
		self._save_state()
		try:
			# Try and parse a built-in type
			typeschema = 'SYSIBM'
			size = None
			scale = None
			# Match the optional SYSIBM prefix
			if self._match((DATATYPE, 'SYSIBM')):
				self._expect('.')
			if self._match((DATATYPE, 'SMALLINT')):
				typename = 'SMALLINT'
			elif self._match_one_of([(DATATYPE, 'INT'), (DATATYPE, 'INTEGER')]):
				typename = 'INTEGER'
			elif self._match((DATATYPE, 'BIGINT')):
				typename = 'BIGINT'
			elif self._match((DATATYPE, 'FLOAT')):
				size = self._parse_size(optional=True)
				if size is None or size > 24:
					typename = 'DOUBLE'
				else:
					typename = 'REAL'
			elif self._match((DATATYPE, 'REAL')):
				typename = 'REAL'
			elif self._match((DATATYPE, 'DOUBLE')):
				self._match((DATATYPE, 'PRECISION'))
				typename = 'DOUBLE'
			elif self._match((DATATYPE, 'DECFLOAT')):
				self._parse_size(optional=True)
			elif self._match_one_of([(DATATYPE, 'DEC'), (DATATYPE, 'DECIMAL')]):
				typename = 'DECIMAL'
				if self._match('(', prespace=False):
					size = self._expect(NUMBER)[1]
					if self._match(','):
						scale = self._expect(NUMBER)[1]
					self._expect(')')
			elif self._match_one_of([(DATATYPE, 'NUM'), (DATATYPE, 'NUMERIC')]):
				typename = 'NUMERIC'
				if self._match('(', prespace=False):
					size = self._expect(NUMBER)[1]
					if self._match(','):
						scale = self._expect(NUMBER)[1]
					self._expect(')')
			elif self._match_one_of([(DATATYPE, 'CHAR'), (DATATYPE, 'CHARACTER')]):
				if self._match((DATATYPE, 'VARYING')):
					typename = 'VARCHAR'
					size = self._parse_size(optional=False, suffix=SUFFIX_KMG)
					self._match_sequence(['FOR', 'BIT', 'DATA'])
				elif self._match_sequence([(DATATYPE, 'LARGE'), (DATATYPE, 'OBJECT')]):
					typename = 'CLOB'
					size = self._parse_size(optional=True, suffix=SUFFIX_KMG)
				else:
					typename = 'CHAR'
					size = self._parse_size(optional=True, suffix=SUFFIX_KMG)
					self._match_sequence(['FOR', 'BIT', 'DATA'])
			elif self._match((DATATYPE, 'VARCHAR')):
				typename = 'VARCHAR'
				size = self._parse_size(optional=False, suffix=SUFFIX_KMG)
				self._match_sequence(['FOR', 'BIT', 'DATA'])
			elif self._match((DATATYPE, 'VARGRAPHIC')):
				typename = 'VARGRAPHIC'
				size = self._parse_size(optional=False)
			elif self._match_sequence([(DATATYPE, 'LONG'), (DATATYPE, 'VARCHAR')]):
				typename = 'LONG VARCHAR'
			elif self._match_sequence([(DATATYPE, 'LONG'), (DATATYPE, 'VARGRAPHIC')]):
				typename = 'LONG VARGRAPHIC'
			elif self._match((DATATYPE, 'CLOB')):
				typename = 'CLOB'
				size = self._parse_size(optional=True, suffix=SUFFIX_KMG)
			elif self._match((DATATYPE, 'BLOB')):
				typename = 'BLOB'
				size = self._parse_size(optional=True, suffix=SUFFIX_KMG)
			elif self._match_sequence([(DATATYPE, 'BINARY'), (DATATYPE, 'LARGE'), (DATATYPE, 'OBJECT')]):
				typename = 'BLOB'
				size = self._parse_size(optional=True, suffix=SUFFIX_KMG)
			elif self._match((DATATYPE, 'DBCLOB')):
				typename = 'DBCLOB'
				size = self._parse_size(optional=True, suffix=SUFFIX_KMG)
			elif self._match((DATATYPE, 'GRAPHIC')):
				typename = 'GRAPHIC'
				size = self._parse_size(optional=True)
			elif self._match((DATATYPE, 'DATE')):
				typename = 'DATE'
			elif self._match((DATATYPE, 'TIME')):
				typename = 'TIME'
			elif self._match((DATATYPE, 'TIMESTAMP')):
				typename = 'TIMESTAMP'
			elif self._match((DATATYPE, 'DATALINK')):
				typename = 'DATALINK'
				size = self._parse_size(optional=True)
			elif self._match((DATATYPE, 'XML')):
				typename = 'XML'
			elif self._match((DATATYPE, 'DB2SECURITYLABEL')):
				typeschema = 'SYSPROC'
				typename = 'DB2SECURITYLABEL'
			else:
				raise ParseBacktrack()
		except ParseError:
			# If that fails, rewind and parse a user-defined type (user defined
			# types do not have a size or scale)
			self._restore_state()
			typeschema = None
			typename = self._expect(DATATYPE)[1]
			if self._match('.'):
				typeschema = typename
				typename = self._expect(DATATYPE)[1]
			size = None
			scale = None
		else:
			self._forget_state()
		return (typeschema, typename, size, scale)

	def _parse_ident_list(self, newlines=False):
		"""Parses a comma separated list of identifiers.

		This is a common pattern in SQL, for example within parentheses on the
		left hand side of an assignment in an UPDATE statement, or the INCLUDE
		list of a CREATE UNIQUE INDEX statement.

		The method returns a list of the identifiers seen (primarily useful for
		counting the number of identifiers seen, but has other uses too).
		"""
		result = []
		while True:
			result.append(self._expect(IDENTIFIER)[1])
			if not self._match(','):
				break
			elif newlines:
				self._newline()
		return result

	def _parse_expression_list(self, allowdefault=False, newlines=False):
		"""Parses a comma separated list of expressions.

		This is a common pattern in SQL, for example the parameter list of
		a function, the arguments of an ORDER BY clause, etc. The allowdefault
		parameter indicates whether DEFAULT can appear in the list instead
		of an expression (useful when parsing the VALUES clause of an INSERT
		statement for example).
		"""
		while True:
			if not (allowdefault and self._match('DEFAULT')):
				self._parse_expression()
			if not self._match(','):
				break
			elif newlines:
				self._newline()

	def _parse_datatype_list(self, newlines=False):
		"""Parses a comma separated list of data-types.

		This is another common pattern in SQL, found when trying to define
		the prototype of a function or procedure without using the specific
		name (and a few other places).
		"""
		while True:
			self._parse_datatype()
			if not self._match(','):
				break
			elif newlines:
				self._newline()

	def _parse_ident_type_list(self, newlines=False):
		"""Parses a comma separated list of identifiers and data-types.

		This is a common pattern in SQL, found in the prototype of SQL
		functions, the INCLUDE portion of a SELECT-FROM-DML statement, etc.
		"""
		while True:
			self._expect(IDENTIFIER)
			self._parse_datatype()
			if not self._match(','):
				break
			elif newlines:
				self._newline()

	def _parse_tuple(self, allowdefault=False):
		"""Parses a full-select or a tuple (list) of expressions.

		This is a common pattern found in SQL, for example on the right hand
		side of the IN operator, in an UPDATE statement on the right hand side
		of a parenthesized column list, etc. The easiest way to implement
		this is by saving the current parser state, attempting to parse a
		full-select, rewinding the state if this fails and parsing a tuple
		of expressions.

		The allowdefault parameter is propogated to parse_expression_list. See
		parse_expression_list for more detail.
		"""
		# Opening parenthesis already matched
		self._save_state()
		try:
			# Try and parse a full-select
			self._indent()
			self._parse_full_select()
			self._outdent()
		except ParseError:
			# If that fails, rewind and parse a tuple of expressions
			self._restore_state()
			self._parse_expression_list(allowdefault)
		else:
			self._forget_state()

	# EXPRESSIONS and PREDICATES #############################################

	def _parse_search_condition(self, newlines=True):
		"""Parse a search condition (as part of WHERE/HAVING/etc.)"""
		while True:
			self._match('NOT')
			# Ambiguity: open parentheses could indicate a parentheiszed search
			# condition, or a parenthesized expression within a predicate
			self._save_state()
			try:
				# Attempt to parse a parenthesized search condition
				self._expect('(')
				self._parse_search_condition(newlines)
				self._expect(')')
			except ParseError:
				# If that fails, rewind and parse a predicate instead (which
				# will parse a parenthesized expression)
				self._restore_state()
				self._parse_predicate()
				if self._match('SELECTIVITY'):
					self._expect(NUMBER)
			else:
				self._forget_state()
			if self._match_one_of(['AND', 'OR']):
				if newlines:
					self._newline(-1)
			else:
				break

	def _parse_predicate(self):
		"""Parse high precedence predicate operators (BETWEEN, IN, etc.)"""
		if self._match('EXISTS'):
			self._expect('(')
			self._parse_full_select()
			self._expect(')')
		else:
			self._parse_expression()
			if self._match('NOT'):
				if self._match('LIKE'):
					self._parse_expression()
					if self._match('ESCAPE'):
						self._parse_expression()
				elif self._match('BETWEEN'):
					self._parse_expression()
					self._expect('AND')
					self._parse_expression()
				elif self._match('IN'):
					if self._match('('):
						self._parse_tuple()
						self._expect(')')
					else:
						self._parse_expression()
				else:
					self._expected_one_of(['LIKE', 'BETWEEN', 'IN'])
			elif self._match('LIKE'):
				self._parse_expression()
				if self._match('ESCAPE'):
					self._parse_expression()
			elif self._match('BETWEEN'):
				self._parse_expression()
				self._expect('AND')
				self._parse_expression()
			elif self._match('IN'):
				if self._match('('):
					self._parse_tuple()
					self._expect(')')
				else:
					self._parse_expression()
			elif self._match('IS'):
				self._match('NOT')
				if self._match('VALIDATED'):
					if self._match('ACCORDING'):
						self._expect_sequence(['TO', 'XMLSCHEMA'])
						if self._match('IN'):
							self._expect('(')
							while True:
								self._parse_xml_schema_identification()
								if not self._match(','):
									break
							self._expect(')')
						else:
							self._parse_xml_schema_identification()
				else:
					self._expect_one_of(['NULL', 'VALIDATED'])
			elif self._match('XMLEXISTS'):
				self._expect('(')
				self._expect(STRING)
				if self._match('PASSING'):
					self._match_sequence(['BY', 'REF'])
					while True:
						self._parse_expression()
						self._expect_sequence(['AS', IDENTIFIER])
						self._match_sequence(['BY', 'REF'])
						if not self._match(','):
							break
				self._expect(')')
			elif self._match_one_of(['=', '<', '>', '<>', '<=', '>=']):
				if self._match_one_of(['SOME', 'ANY', 'ALL']):
					self._expect('(')
					self._parse_full_select()
					self._expect(')')
				else:
					self._parse_expression()
			else:
				self._expected_one_of([
					'EXISTS',
					'NOT',
					'LIKE',
					'BETWEEN',
					'IS',
					'IN',
					'=',
					'<',
					'>',
					'<>',
					'<=',
					'>='
				])
	
	def _parse_duration_label(self, optional=False):
		labels = (
			'YEARS',
			'YEAR',
			'DAYS',
			'DAY',
			'MONTHS',
			'MONTH',
			'HOURS',
			'HOUR',
			'MINUTES',
			'MINUTE',
			'SECONDS',
			'SECOND',
			'MICROSECONDS',
			'MICROSECOND',
		)
		if optional:
			self._match_one_of(labels)
		else:
			self._expect_one_of(labels)

	def _parse_expression(self):
		while True:
			self._match_one_of(['+', '-'], postspace=False) # Unary +/-
			if self._match('('):
				self._parse_tuple()
				self._expect(')')
			elif self._match('CAST'):
				self._parse_cast_expression()
			elif self._match('XMLCAST'):
				self._parse_cast_expression()
			elif self._match('CASE'):
				if self._match('WHEN'):
					self._parse_searched_case()
				else:
					self._parse_simple_case()
			elif self._match_sequence(['NEXT', 'VALUE', 'FOR']):
				self._parse_sequence_name()
			elif self._match_sequence(['PREVIOUS', 'VALUE', 'FOR']):
				self._parse_sequence_name()
			elif self._match_sequence(['ROW', 'CHANGE']):
				self._expect_one_of(['TOKEN', 'TIMESTAMP'])
				self._expect('FOR')
				self._parse_table_name()
			elif self._match_one_of([NUMBER, STRING, PARAMETER, 'NULL']): # Literals
				pass
			else:
				# Ambiguity: an identifier could be a register, a function
				# call, a column name, etc.
				self._save_state()
				try:
					self._parse_function_call()
				except ParseError:
					self._restore_state()
					self._save_state()
					try:
						self._parse_special_register()
					except ParseError:
						self._restore_state()
						self._parse_column_name()
					else:
						self._forget_state()
				else:
					self._forget_state()
			# Parse an optional array element suffix
			if self._match('[', prespace=False):
				self._parse_expression()
				self._expect(']')
			# Parse an optional interval suffix
			self._parse_duration_label(optional=True)
			if not self._match_one_of(['+', '-', '*', '/', '||', 'CONCAT']): # Binary operators
				break

	def _parse_function_call(self):
		"""Parses a function call of various types"""
		# Ambiguity: certain functions have "abnormal" internal syntaxes (extra
		# keywords, etc). The _parse_scalar_function_call method is used to
		# handle all "normal" syntaxes. Special methods are tried first for
		# everything else
		self._save_state()
		try:
			self._parse_aggregate_function_call()
		except ParseError:
			self._restore_state()
			self._save_state()
			try:
				self._parse_olap_function_call()
			except ParseError:
				self._restore_state()
				self._save_state()
				try:
					self._parse_xml_function_call()
				except ParseError:
					self._restore_state()
					self._save_state()
					try:
						self._parse_sql_function_call()
					except ParseError:
						self._restore_state()
						self._parse_scalar_function_call()
					else:
						self._forget_state()
				else:
					self._forget_state()
			else:
				self._forget_state()
		else:
			self._forget_state()

	def _parse_aggregate_function_call(self):
		"""Parses an aggregate function with it's optional arg-prefix"""
		# Parse the optional SYSIBM schema prefix
		if self._match('SYSIBM'):
			self._expect('.')
		# Although CORRELATION and GROUPING are aggregate functions they're not
		# included here as their syntax is entirely compatible with "ordinary"
		# functions so _parse_scalar_function_call will handle them
		aggfunc = self._expect_one_of([
			'COUNT',
			'COUNT_BIG',
			'AVG',
			'MAX',
			'MIN',
			'STDDEV',
			'SUM',
			'VARIANCE',
			'VAR',
		])[1]
		self._expect('(', prespace=False)
		if aggfunc in ('COUNT', 'COUNT_BIG') and self._match('*'):
			# COUNT and COUNT_BIG can take '*' as a sole parameter
			pass
		else:
			# The aggregation functions handled by this method have an optional
			# ALL/DISTINCT argument prefix
			self._match_one_of(['ALL', 'DISTINCT'])
			# And only take a single expression as an argument
			self._parse_expression()
		self._expect(')')
		# Parse an OLAP suffix if one exists
		if self._match('OVER'):
			self._parse_olap_window_clause()

	def _parse_olap_function_call(self):
		"""Parses an OLAP function call (some of which have non-standard internal syntax)"""
		if self._match('SYSIBM'):
			self._expect('.')
		olapfunc = self._expect_one_of([
			'ROW_NUMBER',
			'RANK',
			'DENSE_RANK',
			'LAG',
			'LEAD',
			'FIRST_VALUE',
			'LAST_VALUE',
		])[1]
		self._expect('(', prespace=False)
		if olapfunc in ('LAG', 'LEAD'):
			self._parse_expression()
			if self._match(','):
				self._expect(NUMBER)
				if sel._match(','):
					self._parse_expression()
					if self._match(','):
						self._expect_one_of([(STRING, 'RESPECT NULLS'), (STRING, 'IGNORE NULLS')])
		elif olapfunc in ('FIRST_VALUE', 'LAST_VALUE'):
			self._parse_expression()
			if self._match(','):
				self._expect_one_of([(STRING, 'RESPECT NULLS'), (STRING, 'IGNORE NULLS')])
		self._expect(')')
		self._expect('OVER')
		self._parse_olap_window_clause()

	def _parse_xml_function_call(self):
		"""Parses an XML function call (which has non-standard internal syntax)"""
		# Parse the optional SYSIBM schema prefix
		if self._match('SYSIBM'):
			self._expect('.')
		# Note that XML2CLOB (compatibility), XMLCOMMENT, XMLCONCAT,
		# XMLDOCUMENT, XMLTEXT, and XMLXSROBJECTID aren't handled by this
		# method as their syntax is "normal" so _parse_scalar_function_call
		# will handle them
		xmlfunc = self._expect_one_of([
			'XMLAGG',
			'XMLATTRIBUTES',
			'XMLELEMENT',
			'XMLFOREST',
			'XMLGROUP',
			'XMLNAMESPACES',
			'XMLPARSE',
			'XMLPI',
			'XMLQUERY',
			'XMLROW',
			'XMLSERIALIZE',
			'XMLVALIDATE',
			'XMLTABLE',
			'XMLTRANSFORM',
		])[1]
		self._expect('(', prespace=False)
		if xmlfunc == 'XMLAGG':
			self._parse_expression()
			if self._match_sequence(['ORDER', 'BY']):
				while True:
					self._parse_expression()
					self._match_one_of(['ASC', 'DESC'])
					if not self._match(','):
						break
		elif xmlfunc == 'XMLATTRIBUTES':
			while True:
				self._parse_expression()
				if self._match('AS'):
					self._expect(IDENTIFIER)
				if not self._match(','):
					break
		elif xmlfunc == 'XMLELEMENT':
			self._expect('NAME')
			self._expect(IDENTIFIER)
			if self._match(','):
				# XXX We're not specifically checking for namespaces and
				# attributes calls as we should here (although expression_list
				# will parse them just fine)
				self._parse_expression_list()
				if self._match('OPTION'):
					self._parse_xml_value_option()
		elif xmlfunc == 'XMLFOREST':
			while True:
				# XXX We're not specifically checking for a namespaces call as
				# we should here (although expression will parse it just fine)
				self._parse_expression()
				self._match_sequence(['AS', IDENTIFIER])
				if not self._match(','):
					break
				if self._match('OPTION'):
					self._parse_xml_value_option()
		elif xmlfunc == 'XMLGROUP':
			while True:
				self._parse_expression()
				if self._match('AS'):
					self._expect(IDENTIFIER)
				if not self._match(','):
					break
			if self._match_sequence(['ORDER', 'BY']):
				while True:
					self._parse_expression()
					self._match_one_of(['ASC', 'DESC'])
					if not self._match(','):
						break
			if self._match('OPTION'):
				self._parse_xml_row_option(allowroot=True)
		elif xmlfunc == 'XMLNAMESPACES':
			while True:
				if self._match('DEFAULT'):
					self._expect(STRING)
				elif self._match('NO'):
					self._expect_sequence(['DEFAULT', STRING])
				else:
					self._expect_sequence([STRING, 'AS', IDENTIFIER])
				if not self._match(','):
					break
		elif xmlfunc == 'XMLPARSE':
			self._expect_sequence(['DOCUMENT', STRING])
			if self._match_one_of(['STRIP', 'PRESERVE']):
				self._expect('WHITESPACE')
		elif xmlfunc == 'XMLPI':
			self._expect_sequence(['NAME', IDENTIFIER])
			if self._match(','):
				self._expect(STRING)
		elif xmlfunc == 'XMLQUERY':
			self._expect(STRING)
			if self._match('PASSING'):
				self._match_sequence(['BY', 'REF'])
				while True:
					self._parse_expression()
					self._expect_sequence(['AS', IDENTIFIER])
					self._match_sequence(['BY', 'REF'])
					if not self._match(','):
						break
			if self._match('RETURNING'):
				self._expect('SEQUENCE')
				self._match_sequence(['BY', 'REF'])
			self._match_sequence(['EMPTY', 'ON', 'EMPTY'])
		elif xmlfunc == 'XMLROW':
			while True:
				self._parse_expression()
				self._match_sequence(['AS', IDENTIFIER])
				if not self._match(','):
					break
			if self._match('OPTION'):
				self._parse_xml_row_option(allowroot=False)
		elif xmlfunc == 'XMLSERIALIZE':
			self._match('CONTENT')
			self._parse_expression()
			self._expect('AS')
			# XXX Data type can only be CHAR/VARCHAR/CLOB
			self._parse_datatype()
			valid = set(['VERSION', 'INCLUDING', 'EXCLUDING'])
			while valid:
				t = self._match_one_of(valid)
				if t:
					t = t[1]
					valid.remove(t)
				else:
					break
				if t == 'VERSION':
					self._expect(STRING)
				elif t == 'INCLUDING':
					valid.remove('EXCLUDING')
					self._expect('XMLDECLARATION')
				elif t == 'EXCLUDING':
					valid.remove('INCLUDING')
					self._expect('XMLDECLARATION')
		elif xmlfunc == 'XMLVALIDATE':
			self._match('DOCUMENT')
			self._parse_expression()
			if self._match('ACCORDING'):
				self._expect_sequence(['TO', 'XMLSCHEMA'])
				self._parse_xml_schema_identification()
				if self._match('NAMESPACE'):
					self._expect(STRING)
				elif self._match('NO'):
					self._expect('NAMESPACE')
				self._match_sequence(['ELEMENT', IDENTIFIER])
		elif xmlfunc == 'XMLTABLE':
			self._parse_expression()
			if self._match(','):
				self._expect(STRING)
			if self._match('PASSING'):
				self._match_sequence(['BY', 'REF'])
				while True:
					self._parse_expression()
					self._expect_sequence(['AS', IDENTIFIER])
					self._match_sequence(['BY', 'REF'])
					if not self._match(','):
						break
			if self._match('COLUMNS'):
				while True:
					self._expect(IDENTIFIER)
					if not self._match_sequence(['FOR', 'ORDINALITY']):
						self._parse_datatype()
						self._match_sequence(['BY', 'REF'])
						if self._match('DEFAULT'):
							self._parse_expression()
						if self._match('PATH'):
							self._expect(STRING)
					if not self._match(','):
						break
		elif xmlfunc == 'XMLTRANSFORM':
			self._parse_expression()
			self._expect('USING')
			self._parse_expression()
			if self._match('WITH'):
				self._parse_expression()
			if self._match('AS'):
				self._parse_datatype()
		self._expect(')')

	def _parse_xml_schema_identification(self):
		"""Parses an identifier for an XML schema"""
		# ACCORDING TO XMLSCHEMA already matched
		if self._match('ID'):
			self._parse_subschema_name()
		else:
			if self._match('URI'):
				self._expect(STRING)
			elif self._match('NO'):
				self._expect('NAMESPACE')
			else:
				self._expected_one_of(['ID', 'URI', 'NO'])
			self._match_sequence(['LOCATION', STRING])

	def _parse_xml_row_option(self, allowroot=False):
		"""Parses an XML OPTION suffix for rows in certain XML function calls"""
		# OPTION already matched
		valid = set(['ROW', 'AS'])
		if allowroot:
			valid.add('ROOT')
		while valid:
			t = self._expect_one_of(valid)
			if t:
				t = t[1]
				valid.remove(t)
			else:
				break
			if t in ('ROW', 'ROOT'):
				self._expect(IDENTIFIER)
			elif t == 'AS':
				self._expect('ATTRIBUTES')

	def _parse_xml_value_option(self):
		"""Parses an XML OPTION suffix for scalar values in certain XML function calls"""
		# OPTION already matched
		valid = set(['EMPTY', 'NULL', 'XMLBINARY'])
		while valid:
			t = self._expect_one_of(valid)
			if t:
				t = t[1]
				valid.remove(t)
			else:
				break
			if t == 'EMPTY':
				valid.remove('NULL')
				self._expect_sequence(['ON', 'NULL'])
			elif t == 'NULL':
				valid.remove('EMPTY')
				self._expect_sequence(['ON', 'NULL'])
			elif t == 'XMLBINARY':
				self._match('USING')
				self._expect_one_of(['BASE64', 'HEX'])

	def _parse_sql_function_call(self):
		"""Parses scalar function calls with abnormal internal syntax (usually as dictated by the SQL standard)"""
		# Parse the optional SYSIBM schema prefix
		if self._match('SYSIBM'):
			self._expect('.')
		# Note that only the "special" syntax of functions is handled here.
		# Most of these functions will also accept "normal" syntax. In that
		# case, this method will raise a parse error and the caller will
		# backtrack to handle the function as normal with
		# _parse_scalar_function_call
		sqlfunc = self._expect_one_of([
			'CHAR_LENGTH',
			'CHARACTER_LENGTH',
			'OVERLAY',
			'POSITION',
			'SUBSTRING',
			'TRIM',
		])[1]
		self._expect('(', prespace=False)
		if sqlfunc in ('CHAR_LENGTH', 'CHARACTER_LENGTH'):
			self._parse_expression()
			if self._match('USING'):
				self._expect_one_of(['CODEUNITS16', 'CODEUNITS32', 'OCTETS'])
		elif sqlfunc == 'OVERLAY':
			self._parse_expression()
			self._expect('PLACING')
			self._parse_expression()
			self._expect('FROM')
			self._parse_expression()
			if self._match('FOR'):
				self._parse_expression()
			self._expect('USING')
			self._expect_one_of(['CODEUNITS16', 'CODEUNITS32', 'OCTETS'])
		elif sqlfunc == 'POSITION':
			self._parse_expression()
			self._expect('IN')
			self._parse_expression()
			self._expect('USING')
			self._expect_one_of(['CODEUNITS16', 'CODEUNITS32', 'OCTETS'])
		elif sqlfunc == 'SUBSTRING':
			self._parse_expression()
			self._expect('FROM')
			self._parse_expression()
			if self._match('FOR'):
				self._parse_expression()
			self._expect('USING')
			self._expect_one_of(['CODEUNITS16', 'CODEUNITS32', 'OCTETS'])
		elif sqlfunc == 'TRIM':
			if self._match_one_of(['BOTH', 'B', 'LEADING', 'L', 'TRAILING', 'T']):
				self._match(STRING)
				self._expect('FROM')
			self._parse_expression()
		self._expect(')')

	def _parse_scalar_function_call(self):
		"""Parses a scalar function call with all its arguments"""
		self._parse_function_name()
		self._expect('(', prespace=False)
		if not self._match(')'):
			self._parse_expression_list()
			self._expect(')')

	def _parse_olap_range(self, optional):
		"""Parses a ROWS or RANGE specification in an OLAP-function call"""
		# [ROWS|RANGE] already matched
		if self._match('CURRENT'):
			self._expect('ROW')
		elif self._match_one_of(['UNBOUNDED', NUMBER]):
			self._expect_one_of(['PRECEDING', 'FOLLOWING'])
		elif not optional:
			self._expected_one_of(['CURRENT', 'UNBOUNDED', NUMBER])
		else:
			return False
		return True

	def _parse_olap_window_clause(self):
		"""Parses the aggregation suffix in an OLAP-function call"""
		# OVER already matched
		self._expect('(')
		if not self._match(')'):
			self._indent()
			if self._match('PARTITION'):
				self._expect('BY')
				self._parse_expression_list()
			if self._match('ORDER'):
				self._newline(-1)
				self._expect('BY')
				while True:
					if self._match('ORDER'):
						self._expect('OF')
						self._parse_table_name()
					else:
						self._parse_expression()
						if self._match_one_of(['ASC', 'DESC']):
							if self._match('NULLS'):
								self._expect_one_of(['FIRST', 'LAST'])
					if not self._match(','):
						break
			if self._match_one_of(['ROWS', 'RANGE']):
				if not self._parse_olap_range(True):
					self._expect('BETWEEN')
					self._parse_olap_range(False)
					self._expect('AND')
					self._parse_olap_range(False)
			self._outdent()
			self._expect(')')

	def _parse_cast_expression(self):
		"""Parses a CAST() expression"""
		# CAST already matched
		self._expect('(', prespace=False)
		self._parse_expression()
		self._expect('AS')
		self._parse_datatype()
		if self._match('SCOPE'):
			self._parse_relation_name()
		self._expect(')')

	def _parse_searched_case(self):
		"""Parses a searched CASE expression (CASE WHEN expression...)"""
		# CASE WHEN already matched
		# Parse all WHEN cases
		self._indent(-1)
		while True:
			self._parse_search_condition(newlines=False) # WHEN Search condition
			self._expect('THEN')
			self._parse_expression() # THEN Expression
			if self._match('WHEN'):
				self._newline(-1)
			elif self._match('ELSE'):
				self._newline(-1)
				break
			elif self._match('END'):
				self._outdent(-1)
				return
			else:
				self._expected_one_of(['WHEN', 'ELSE', 'END'])
		# Parse the optional ELSE case
		self._parse_expression() # ELSE Expression
		self._outdent()
		self._expect('END')

	def _parse_simple_case(self):
		"""Parses a simple CASE expression (CASE expression WHEN value...)"""
		# CASE already matched
		# Parse the CASE Expression
		self._parse_expression() # CASE Expression
		# Parse all WHEN cases
		self._indent()
		self._expect('WHEN')
		while True:
			self._parse_expression() # WHEN Expression
			self._expect('THEN')
			self._parse_expression() # THEN Expression
			if self._match('WHEN'):
				self._newline(-1)
			elif self._match('ELSE'):
				self._newline(-1)
				break
			elif self._match('END'):
				self._outdent(-1)
				return
			else:
				self._expected_one_of(['WHEN', 'ELSE', 'END'])
		# Parse the optional ELSE case
		self._parse_expression() # ELSE Expression
		self._outdent()
		self._expect('END')

	def _parse_column_expression(self):
		"""Parses an expression representing a column in a SELECT expression"""
		if not self._match_sequence([IDENTIFIER, '.', '*']):
			self._parse_expression()
			# Parse optional column alias
			if self._match('AS'):
				self._expect(IDENTIFIER)
			# Ambiguity: FROM can legitimately appear in this position as a
			# KEYWORD (which the IDENTIFIER match below would accept)
			elif not self._peek('FROM'):
				self._match(IDENTIFIER)

	def _parse_grouping_expression(self):
		"""Parses a grouping-expression in a GROUP BY clause"""
		if not self._match_sequence(['(', ')']):
			self._parse_expression()

	def _parse_super_group(self):
		"""Parses a super-group in a GROUP BY clause"""
		# [ROLLUP|CUBE] already matched
		self._expect('(')
		self._indent()
		while True:
			if self._match('('):
				self._parse_expression_list()
				self._expect(')')
			else:
				self._parse_expression()
			if not self._match(','):
				break
			else:
				self._newline()
		self._outdent()
		self._expect(')')

	def _parse_grouping_sets(self):
		"""Parses a GROUPING SETS expression in a GROUP BY clause"""
		# GROUPING SETS already matched
		self._expect('(')
		self._indent()
		while True:
			if self._match('('):
				while True:
					if self._match_one_of(['ROLLUP', 'CUBE']):
						self._parse_super_group()
					else:
						self._parse_grouping_expression()
					if not self._match(','):
						break
				self._expect(')')
			elif self._match_one_of(['ROLLUP', 'CUBE']):
				self._parse_super_group()
			else:
				self._parse_grouping_expression()
			if not self._match(','):
				break
			else:
				self._newline()
		self._outdent()
		self._expect(')')

	def _parse_group_by(self):
		"""Parses the grouping-expression-list of a GROUP BY clause"""
		# GROUP BY already matched
		alt_syntax = True
		while True:
			if self._match('GROUPING'):
				self._expect('SETS')
				self._parse_grouping_sets()
				alt_syntax = False
			elif self._match_one_of(['ROLLUP', 'CUBE']):
				self._parse_super_group()
				alt_syntax = False
			else:
				self._parse_grouping_expression()
			if not self._match(','):
				break
			else:
				self._newline()
		# Ambiguity: the WITH used in the alternate syntax for super-groups
		# can be mistaken for the WITH defining isolation level at the end
		# of a query. Hence we must use a sequence match here...
		if alt_syntax:
			if not self._match_sequence(['WITH', 'ROLLUP']):
				self._match_sequence(['WITH', 'CUBE'])

	def _parse_sub_select(self, allowinto=False):
		"""Parses a sub-select expression"""
		# SELECT already matched
		self._match_one_of(['ALL', 'DISTINCT'])
		if not self._match('*'):
			self._indent()
			while True:
				self._parse_column_expression()
				if not self._match(','):
					break
				else:
					self._newline()
			self._outdent()
		if allowinto and self._match('INTO'):
			self._indent()
			self._parse_ident_list(newlines=True)
			self._outdent()
		self._expect('FROM')
		self._indent()
		while True:
			self._parse_join_expression()
			if not self._match(','):
				break
			else:
				self._newline()
		self._outdent()
		if self._match('WHERE'):
			self._indent()
			self._parse_search_condition()
			self._outdent()
		if self._match('GROUP'):
			self._expect('BY')
			self._indent()
			self._parse_group_by()
			self._outdent()
		if self._match('HAVING'):
			self._indent()
			self._parse_search_condition()
			self._outdent()
		if self._match('ORDER'):
			self._expect('BY')
			self._indent()
			while True:
				self._parse_expression()
				self._match_one_of(['ASC', 'DESC'])
				if not self._match(','):
					break
				else:
					self._newline()
			self._outdent()
		if self._match('FETCH'):
			self._expect('FIRST')
			self._match(NUMBER) # Row count is optional (defaults to 1)
			self._expect_one_of(['ROW', 'ROWS'])
			self._expect('ONLY')

	def _parse_table_correlation(self, optional=True):
		"""Parses a table correlation clause (with optional column alias list)"""
		if optional:
			# An optional table correlation is almost always ambiguous given
			# that it can start with just about any identifier (the AS is
			# always optional)
			self._save_state()
			try:
				# Call ourselves recursively to try and parse the correlation
				self._parse_table_correlation(False)
			except ParseError:
				# If it fails, rewind and return
				self._restore_state()
			else:
				self._forget_state()
		else:
			if self._match('AS'):
				self._expect(IDENTIFIER)
			# Ambiguity: Several KEYWORDs can legitimately appear in this
			# position. XXX This is horrible - there /must/ be a cleaner way of
			# doing this with states and backtracking
			elif not self._peek_one_of([
					'DO',
					'EXCEPT',
					'FETCH',
					'GROUP',
					'HAVING',
					'CROSS',
					'LEFT',
					'RIGHT',
					'FULL',
					'INTERSECT',
					'ON',
					'ORDER',
					'SET',
					'UNION',
					'USING',
					'WHERE',
					'WITH',
				]):
				self._expect(IDENTIFIER)
			# Parse optional column aliases
			if self._match('('):
				self._parse_ident_list()
				self._expect(')')

	def _parse_values_expression(self, allowdefault=False):
		"""Parses a VALUES expression"""
		# VALUES already matched
		self._indent()
		while True:
			if self._match('('):
				self._parse_expression_list(allowdefault)
				self._expect(')')
			else:
				if not (allowdefault and self._match('DEFAULT')):
					self._parse_expression()
			if self._match(','):
				self._newline()
			else:
				break
		self._outdent()

	def _parse_join_expression(self):
		"""Parses join operators in a table-reference"""
		self._parse_table_ref()
		while True:
			if self._match('CROSS'):
				self._newline(-1)
				self._expect('JOIN')
				self._parse_table_ref()
			elif self._match('INNER'):
				self._newline(-1)
				self._expect('JOIN')
				self._parse_table_ref()
				self._parse_join_condition()
			elif self._match_one_of(['LEFT', 'RIGHT', 'FULL']):
				self._newline(-1)
				self._match('OUTER')
				self._expect('JOIN')
				self._parse_table_ref()
				self._parse_join_condition()
			elif self._match('JOIN'):
				self._newline(-1)
				self._parse_table_ref()
				self._parse_join_condition()
			else:
				break

	def _parse_table_ref(self):
		"""Parses literal table references or functions in a table-reference"""
		# Ambiguity: A table or schema can be named TABLE, FINAL, OLD, etc.
		reraise = False
		self._save_state()
		try:
			if self._match('('):
				# Ambiguity: Open-parenthesis could indicate a full-select or a
				# join expression
				self._save_state()
				try:
					# Try and parse a full-select
					self._parse_full_select()
					reraise = True
					self._expect(')')
					self._parse_table_correlation(optional=False)
				except ParseError:
					# If it fails, rewind and try a join expression instead
					self._restore_state()
					if reraise: raise
					self._parse_join_expression()
					self._expect(')')
				else:
					self._forget_state()
			elif self._match('TABLE'):
				self._expect('(', prespace=False)
				# Ambiguity: TABLE() can indicate a table-function call or a
				# nested table expression
				self._save_state()
				try:
					# Try and parse a full-select
					self._indent()
					self._parse_full_select()
					self._outdent()
				except ParseError:
					# If it fails, rewind and try a function call instead
					self._restore_state()
					self._parse_function_call()
				else:
					self._forget_state()
				reraise = True
				self._expect(')')
				self._parse_table_correlation(optional=False)
			elif self._match_one_of(['FINAL', 'NEW']):
				self._expect('TABLE')
				self._expect('(', prespace=False)
				self._indent()
				if self._expect_one_of(['INSERT', 'UPDATE'])[1] == 'INSERT':
					self._parse_insert_statement()
				else:
					self._parse_update_statement()
				reraise = True
				self._outdent()
				self._expect(')')
				self._parse_table_correlation(optional=True)
			elif self._match('OLD'):
				self._expect('TABLE')
				self._expect('(', prespace=False)
				self._indent()
				if self._expect_one_of(['UPDATE', 'DELETE'])[1] == 'DELETE':
					self._parse_delete_statement()
				else:
					self._parse_update_statement()
				reraise = True
				self._outdent()
				self._expect(')')
				self._parse_table_correlation(optional=True)
			elif self._peek('XMLTABLE'):
				# Bizarrely, the XMLTABLE table function can be used outside a
				# TABLE() reference...
				self._parse_xml_function_call()
			else:
				raise ParseBacktrack()
		except ParseError:
			# If the above fails, rewind and try a simple table reference
			self._restore_state()
			if reraise: raise
			self._parse_table_name()
			self._parse_table_correlation(optional=True)
			# XXX Add support for tablesample-clause
		else:
			self._forget_state()

	def _parse_join_condition(self):
		"""Parses the condition on an SQL-92 style join"""
		# This method can be extended to support USING(ident-list) if this
		# if ever added to DB2 (see PostgreSQL)
		self._indent()
		self._expect('ON')
		self._parse_search_condition()
		self._outdent()

	def _parse_full_select(self, allowdefault=False, allowinto=False):
		"""Parses set operators (low precedence) in a full-select expression"""
		self._parse_relation(allowdefault, allowinto)
		while True:
			if self._match_one_of(['UNION', 'INTERSECT', 'EXCEPT']):
				self._newline(-1)
				self._newline(-1, allowempty=True)
				self._match('ALL')
				self._newline()
				self._newline(allowempty=True)
				# No need to include allowinto here (it's only permitted in a
				# top-level subselect)
				self._parse_relation(allowdefault)
			else:
				break
		if self._match('ORDER'):
			self._expect('BY')
			while True:
				self._parse_expression()
				self._match_one_of(['ASC', 'DESC'])
				if not self._match(','):
					break
		if self._match('FETCH'):
			self._expect('FIRST')
			self._match(NUMBER) # Row count is optional (defaults to 1)
			self._expect_one_of(['ROW', 'ROWS'])
			self._expect('ONLY')

	def _parse_relation(self, allowdefault=False, allowinto=False):
		"""Parses relation generators (high precedence) in a full-select expression"""
		if self._match('('):
			self._indent()
			# No need to include allowinto here (it's only permitted in a
			# top-level subselect)
			self._parse_full_select(allowdefault)
			self._outdent()
			self._expect(')')
		elif self._match('SELECT'):
			self._parse_sub_select(allowinto)
		elif self._match('VALUES'):
			self._parse_values_expression(allowdefault)
		else:
			self._expected_one_of(['SELECT', 'VALUES', '('])

	def _parse_query(self, allowdefault=False, allowinto=False):
		"""Parses a full-select with optional common-table-expression"""
		# Parse the optional common-table-expression
		if self._match('WITH'):
			while True:
				self._expect(IDENTIFIER)
				# Parse the optional column-alias list
				if self._match('('):
					self._indent()
					self._parse_ident_list(newlines=True)
					self._outdent()
					self._expect(')')
				self._expect('AS')
				self._expect('(')
				self._indent()
				# No need to include allowdefault or allowinto here. Neither
				# are ever permitted in a CTE
				self._parse_full_select()
				self._outdent()
				self._expect(')')
				if not self._match(','):
					break
				else:
					self._newline()
			self._newline()
		# Parse the actual full-select. DEFAULT may be permitted here if the
		# full-select turns out to be a VALUES statement
		self._parse_full_select(allowdefault, allowinto)

	# CLAUSES ################################################################

	def _parse_assignment_clause(self, allowdefault):
		"""Parses a SET clause"""
		# SET already matched
		while True:
			if self._match('('):
				# Parse tuple assignment
				while True:
					self._parse_subrelation_name()
					if not self._match(','):
						break
				self._expect_sequence([')', '=', '('])
				self._parse_tuple(allowdefault=True)
				self._expect(')')
			else:
				# Parse simple assignment
				self._parse_subrelation_name()
				if self._match('['):
					self._parse_expression()
					self._expect(']')
				self._expect('=')
				if self._match('ARRAY'):
					self._expect('[', prespace=False)
					# Ambiguity: Expression list vs. select-statement
					self._save_state()
					try:
						self._parse_expression_list()
					except ParseError:
						self._restore_state()
						self._parse_full_select()
					else:
						self._forget_state()
					self._expect(']')
				elif not (allowdefault and self._match('DEFAULT')):
					self._parse_expression()
			if not self._match(','):
				break
			else:
				self._newline()

	def _parse_identity_options(self, alter=None):
		"""Parses options for an IDENTITY column"""
		# AS IDENTITY already matched
		# Build a couple of lists of options which have not yet been seen
		validno = [
			'MINVALUE',
			'MAXVALUE',
			'CACHE',
			'CYCLE',
			'ORDER',
		]
		valid = validno + ['INCREMENT', 'NO']
		if alter is None:
			valid = valid + ['START']
		elif alter == 'SEQUENCE':
			valid = valid + ['RESTART']
		# XXX Allow backward compatibility options here?  Backward
		# compatibility options include comma separation of arguments, and
		# NOMINVALUE instead of NO MINVALUE, etc.
		while valid:
			if alter == 'COLUMN':
				if self._match('RESTART'):
					if self._match('WITH'):
						self._expect(NUMBER)
						continue
				elif self._match('SET'):
					t = self._expect_one_of(valid)[1]
					if t != 'NO': valid.remove(t)
					if t in validno: validno.remove(t)
				else:
					break
			else:
				t = self._match_one_of(valid)
				if t:
					t = t[1]
					if t != 'NO': valid.remove(t)
					if t in validno: validno.remove(t)
				else:
					break
			if t == 'START':
				self._expect_sequence(['WITH', NUMBER])
			elif t == 'RESTART':
				if self._match('WITH'):
					self._expect(NUMBER)
			elif t == 'INCREMENT':
				self._expect_sequence(['BY', NUMBER])
			elif t in ('MINVALUE', 'MAXVALUE', 'CACHE'):
				self._expect(NUMBER)
			elif t in ('CYCLE', 'ORDER'):
				pass
			elif t == 'NO':
				t = self._expect_one_of(validno)[1]
				validno.remove(t)
				valid.remove(t)

	def _parse_column_definition(self, aligntypes=False, alignoptions=False, federated=False):
		"""Parses a column definition in a CREATE TABLE statement"""
		# Parse a column definition
		self._expect(IDENTIFIER)
		if aligntypes:
			self._valign()
		self._parse_datatype()
		if alignoptions and not self._peek_one_of([',', ')']):
			self._valign()
		# Parse column options
		while True:
			if self._match('NOT'):
				self._expect_one_of(['NULL', 'LOGGED', 'COMPACT', 'HIDDEN'])
			elif self._match('LOGGED'):
				pass
			elif self._match('COMPACT'):
				pass
			elif self._match('WITH'):
				self._expect('DEFAULT')
				self._save_state()
				try:
					self._parse_expression()
				except ParseError:
					self._restore_state()
				else:
					self._forget_state()
			elif self._match('DEFAULT'):
				self._save_state()
				try:
					self._parse_expression()
				except ParseError:
					self._restore_state()
				else:
					self._forget_state()
			elif self._match('GENERATED'):
				if self._expect_one_of(['ALWAYS', 'BY'])[1] == 'BY':
					self._expect('DEFAULT')
				if self._match('AS'):
					if self._match('IDENTITY'):
						if self._match('('):
							self._parse_identity_options()
							self._expect(')')
					elif self._match('('):
						self._parse_expression()
						self._expect(')')
					else:
						self._expected_one_of(['IDENTITY', '('])
				else:
					self._expect_sequence(['FOR', 'EACH', 'ROW', 'ON', 'UPDATE', 'AS', 'ROW', 'CHANGE', 'TIMESTAMP'])
			elif self._match('INLINE'):
				self._expect_sequence(['LENGTH', NUMBER])
			elif self._match('COMPRESS'):
				self._expect_sequence(['SYSTEM', 'DEFAULT'])
			elif self._match('COLUMN'):
				self._expect_sequence(['SECURED', 'WITH', IDENTIFIER])
			elif self._match('SECURED'):
				self._expect_sequence(['WITH', IDENTIFIER])
			elif self._match('IMPLICITLY'):
				self._expect('HIDDEN')
			elif federated and self._match('OPTIONS'):
				self._parse_federated_options()
			else:
				self._save_state()
				try:
					self._parse_column_constraint()
				except ParseError:
					self._restore_state()
					break
				else:
					self._forget_state()

	def _parse_column_constraint(self):
		"""Parses a constraint attached to a specific column in a CREATE TABLE statement"""
		# Parse the optional constraint name
		if self._match('CONSTRAINT'):
			self._expect(IDENTIFIER)
		# Parse the constraint definition
		if self._match('PRIMARY'):
			self._expect('KEY')
		elif self._match('UNIQUE'):
			pass
		elif self._match('REFERENCES'):
			self._parse_table_name()
			if self._match('(', prespace=False):
				self._expect(IDENTIFIER)
				self._expect(')')
			t = ['DELETE', 'UPDATE']
			for i in xrange(2):
				if self._match('ON'):
					t.remove(self._expect_one_of(t)[1])
					if self._match('NO'):
						self._expect('ACTION')
					elif self._match('SET'):
						self._expect('NULL')
					elif self._match_one_of(['RESTRICT', 'CASCADE']):
						pass
					else:
						self._expected_one_of([
							'RESTRICT',
							'CASCADE',
							'NO',
							'SET'
						])
				else:
					break
		elif self._match('CHECK'):
			self._expect('(')
			# Ambiguity: check constraint can be a search condition or a
			# functional dependency. Try the search condition first
			self._save_state()
			try:
				self._parse_search_condition()
			except ParseError:
				self._restore_state()
				if self._match('('):
					self._parse_ident_list()
					self._expect(')')
				else:
					self._expect(IDENTIFIER)
				self._expect_sequence(['DETERMINED', 'BY'])
				if self._match('('):
					self._parse_ident_list()
					self._expect(')')
				else:
					self._expect(IDENTIFIER)
			else:
				self._forget_state()
			self._expect(')')
		else:
			self._expected_one_of([
				'CONSTRAINT',
				'PRIMARY',
				'UNIQUE',
				'REFERENCES',
				'CHECK'
			])

	def _parse_table_constraint(self):
		"""Parses a constraint attached to a table in a CREATE TABLE statement"""
		if self._match('CONSTRAINT'):
			self._expect(IDENTIFIER)
		if self._match('PRIMARY'):
			self._expect('KEY')
			self._expect('(')
			self._parse_ident_list()
			self._expect(')')
		elif self._match('UNIQUE'):
			self._expect('(')
			self._parse_ident_list()
			self._expect(')')
		elif self._match('FOREIGN'):
			self._expect('KEY')
			self._expect('(')
			self._parse_ident_list()
			self._expect(')')
			self._expect('REFERENCES')
			self._parse_subschema_name()
			self._expect('(', prespace=False)
			self._parse_ident_list()
			self._expect(')')
			t = ['DELETE', 'UPDATE']
			for i in xrange(2):
				if self._match('ON'):
					t.remove(self._expect_one_of(t)[1])
					if self._match('NO'):
						self._expect('ACTION')
					elif self._match('SET'):
						self._expect('NULL')
					elif self._match_one_of(['RESTRICT', 'CASCADE']):
						pass
					else:
						self._expected_one_of([
							'RESTRICT',
							'CASCADE',
							'NO',
							'SET'
						])
				else:
					break
		elif self._match('CHECK'):
			self._expect('(')
			# Ambiguity: check constraint can be a search condition or a
			# functional dependency. Try the search condition first
			self._save_state()
			try:
				self._parse_search_condition(newlines=False)
			except ParseError:
				self._restore_state()
				if self._match('('):
					self._parse_ident_list()
					self._expect(')')
				else:
					self._expect(IDENTIFIER)
				self._expect_sequence(['DETERMINED', 'BY'])
				if self._match('('):
					self._parse_ident_list()
					self._expect(')')
				else:
					self._expect(IDENTIFIER)
			else:
				self._forget_state()
			self._expect(')')
		else:
			self._expected_one_of([
				'CONSTRAINT',
				'PRIMARY',
				'UNIQUE',
				'FOREIGN',
				'CHECK'
			])

	def _parse_table_definition(self, aligntypes=False, alignoptions=False, federated=False):
		"""Parses a table definition (list of columns and constraints)"""
		self._expect('(')
		self._indent()
		while True:
			self._save_state()
			try:
				# Try parsing a table constraint definition
				self._parse_table_constraint()
			except ParseError:
				# If that fails, rewind and try and parse a column definition
				self._restore_state()
				self._parse_column_definition(aligntypes=aligntypes, alignoptions=alignoptions, federated=federated)
			else:
				self._forget_state()
			if not self._match(','):
				break
			else:
				self._newline()
		if aligntypes:
			self._vapply()
		if alignoptions:
			self._vapply()
		self._outdent()
		self._expect(')')

	def _parse_constraint_alteration(self):
		"""Parses a constraint-alteration in an ALTER TABLE statement"""
		# FOREIGN KEY/CHECK already matched
		self._expect(IDENTIFIER)
		if self._match_one_of(['ENABLE', 'DISABLE']):
			self._expect_sequence(['QUERY', 'OPTIMIZATION'])
		else:
			self._match('NOT')
			self._expect('ENFORCED')

	def _parse_column_alteration(self):
		"""Parses a column-alteration in an ALTER TABLE statement"""
		self._expect(IDENTIFIER)
		if self._match('DROP'):
			self._expect_one_of([
				'IDENTITY',
				'DEFAULT',
				'EXPRESSION'
			])
		elif self._match('COMPRESS'):
			if self._match('SYSTEM'):
				self._expect('DEFAULT')
			else:
				self._expect('OFF')
		else:
			# Ambiguity: SET can introduce several different alterations
			self._save_state()
			try:
				# Try and parse SET (DATA TYPE | EXPRESSION | INLINE LENGTH | GENERATED)
				self._expect('SET')
				if self._match('DATA'):
					self._expect('TYPE')
					self._parse_datatype()
				elif self._match('EXPRESSION'):
					self._expect('AS')
					self._expect('(')
					self._parse_expression()
					self._expect(')')
				elif self._match('INLINE'):
					self._expect_sequence(['LENGTH', NUMBER])
				elif self._match('GENERATED'):
					if self._match(['BY', 'ALWAYS'])[1] == 'BY':
						self._expect('DEFAULT')
					self._expect('AS')
					if self._match('IDENTITY'):
						if self._match('('):
							self._parse_identity_options()
							self._expect(')')
					elif self._match('('):
						self._parse_expression()
						self._expect(')')
					else:
						self._expected_one_of(['IDENTITY', '('])
				else:
					raise ParseBacktrack()
			except ParseBacktrack:
				# NOTE: This exception block is only called on a ParseBacktrack
				# error. Other parse errors will propogate outward. If the
				# above SET clauses didn't match, try an identity-alteration.
				self._restore_state()
				self._parse_identity_options(alter='COLUMN')
			else:
				self._forget_state()

	def _parse_federated_column_alteration(self):
		"""Parses a column-alteration in an ALTER NICKNAME statement"""
		self._expect(IDENTIFIER)
		while True:
			if self._match('LOCAL'):
				if self._match('NAME'):
					self._expect(IDENTIFIER)
				elif self._match('TYPE'):
					self._parse_datatype()
			elif self._match('OPTIONS'):
				self._parse_federated_options(alter=True)
			if not self._match(','):
				break

	def _parse_auth_list(self):
		"""Parses an authorization list in a GRANT or REVOKE statement"""
		# [TO|FROM] already matched
		while True:
			if not self._match('PUBLIC'):
				self._match_one_of(['USER', 'GROUP', 'ROLE'])
				self._expect(IDENTIFIER)
			if not self._match(','):
				break

	def _parse_grant_revoke(self, grant):
		"""Parses the body of a GRANT or REVOKE statement"""
		# [GRANT|REVOKE] already matched
		seclabel = False
		if self._match_one_of([
			'BINDADD',
			'CONNECT',
			'CREATETAB',
			'CREATE_EXTERNAL_ROUTINE',
			'CREATE_NOT_FENCED_ROUTINE',
			'IMPLICIT_SCHEMA',
			'DBADM',
			'LOAD',
			'QUIESCE_CONNECT',
			'SECADM',
		]):
			self._expect_sequence(['ON', 'DATABASE'])
		elif self._match('EXEMPTION'):
			self._expect_sequence(['ON', 'RULE'])
			if self._match_one_of([
				'DB2LBACREADARRAY',
				'DB2LBACREADSET',
				'DB2LBACREADTREE',
				'DB2LBACWRITEARRAY',
				'DB2LBACWRITESET',
				'DB2LBACWRITETREE',
				'ALL'
			])[1] == 'DB2LBACWRITEARRAY':
				self._expect_one_of(['WRITEDOWN', 'WRITEUP'])
			self._expect_sequence(['FOR', IDENTIFIER])
		elif self._match_one_of([
			'ALTERIN',
			'CREATEIN',
			'DROPIN',
		]):
			self._expect_sequence(['ON', 'SCHEMA', IDENTIFIER])
		elif self._match('CONTROL'):
			self._expect('ON')
			if self._match('INDEX'):
				self._parse_index_name()
			else:
				self._match('TABLE')
				self._parse_table_name()
		elif self._match('USAGE'):
			self._expect('ON')
			if self._match('SEQUENCE'):
				self._parse_sequence_name()
			elif self._match('WORKLOAD'):
				self._expect(IDENTIFIER)
			else:
				self._expected_one_of(['SEQUENCE', 'WORKLOAD'])
		elif self._match('ALTER'):
			self._expect('ON')
			if self._match('SEQUENCE'):
				self._parse_sequence_name()
			else:
				self._match('TABLE')
				self._parse_table_name()
		elif self._match('ALL'):
			self._match('PRIVILEGES')
			self._expect('ON')
			if self._match('VARIABLE'):
				self._parse_variable_name()
			else:
				self._match('TABLE')
				self._parse_table_name()
		elif self._match('USE'):
			self._expect_sequence(['OF', 'TABLESPACE', IDENTIFIER])
		elif self._match_sequence(['EXECUTE', 'ON']):
			if self._match_one_of(['FUNCTION', 'PROCEDURE']):
				# Ambiguity: Can use schema.* or schema.name(prototype) here
				if not self._match('*') and not self._match_sequence([IDENTIFIER, '.', '*']):
					self._parse_routine_name()
					if self._match('(', prespace=False):
						self._parse_datatype_list()
						self._expect(')')
			elif self._match('SPECIFIC'):
				self._expect_one_of(['FUNCTION', 'PROCEDURE'])
				self._parse_routine_name()
			else:
				self._expected_one_of(['FUNCTION', 'PROCEDURE', 'SPECIFIC'])
		elif self._match('PASSTHRU'):
			self._expect_sequence(['ON', 'SERVER', IDENTIFIER])
		elif self._match_sequence(['SECURITY', 'LABEL']):
			self._expect(IDENTIFIER)
			seclabel = grant
		elif self._match('ROLE'):
			self._parse_ident_list()
		elif self._match('SETSESSIONUSER'):
			self._expect('ON')
			if not self._match('PUBLIC'):
				self._expect_sequence(['USER', IDENTIFIER])
		else:
			# Ambiguity: Here we could be matching table privs (SELECT, INSERT,
			# et al.) or variable privs (READ, WRITE), or arbitrary IDENTIFIERs
			# for GRANT ROLE where ROLE has been ommitted. Hence we just loop
			# round grabbing IDENTs (taking care of the special syntax for
			# REFERENCES and UPDATE which can include a column list)
			while True:
				if self._expect(IDENTIFIER)[1] in ('REFERENCES', 'UPDATE'):
					if self._match('('):
						self._parse_ident_list()
						self._expect(')')
				if not self._match(','):
					break
			self._expect('ON')
			if self._match('VARIABLE'):
				self._parse_variable_name()
			else:
				self._match('TABLE')
				self._parse_table_name()
		# XXX The following is a bit lax, but again, adhering strictly to the
		# syntax results in a ridiculously complex syntax
		self._expect(['FROM', 'TO'][grant])
		self._parse_auth_list()
		if seclabel:
			if self._match('FOR'):
				self._expect_one_of(['ALL', 'READ', 'WRITE'])
				self._expect('ACCESS')
		elif grant:
			self._match_sequence(['WITH', 'GRANT', 'OPTION'])
		else:
			self._match_sequence(['BY', 'ALL'])
			self._match('RESTRICT')

	def _parse_tablespace_size_attributes(self):
		"""Parses DMS size attributes in a CREATE TABLESPACE statement"""
		if self._match('AUTORESIZE'):
			self._expect_one_of(['NO', 'YES'])
		if self._match('INTIALSIZE'):
			self._expect(NUMBER)
			self._expect_one_of(['K', 'M', 'G'])
		if self._match('INCREASESIZE'):
			self._expect(NUMBER)
			self._expect_one_of(['K', 'M', 'G', 'PERCENT'])
		if self._match('MAXSIZE'):
			if not self._match('NONE'):
				self._expect(NUMBER)
				self._expect_one_of(['K', 'M', 'G'])

	def _parse_database_container_clause(self, size=True):
		"""Parses a container clause for a DMS tablespace"""
		self._expect('(')
		while True:
			self._expect_one_of(['FILE', 'DEVICE'])
			self._expect(STRING)
			if size:
				self._expect(NUMBER)
				self._match_one_of(['K', 'M', 'G'])
			if not self._match(','):
				break
		self._expect(')')

	def _parse_system_container_clause(self):
		"""Parses a container clause for an SMS tablespace"""
		self._expect('(')
		while True:
			self._expect(STRING)
			if not self._match(','):
				break
		self._expect(')')

	def _parse_db_partitions_clause(self, size=False):
		"""Parses an DBPARTITIONNUM clause in a CREATE/ALTER TABLESPACE statement"""
		self._expect_one_of([
			'DBPARTITIONNUM',
			'DBPARTITIONNUMS',
			'NODE', # compatibility option
			'NODES', # compatibility option
		])
		self._expect('(')
		while True:
			self._expect(NUMBER)
			self._match_sequence(['TO', NUMBER])
			if size:
				self._expect_sequence(['SIZE', NUMBER])
			if not self._match(','):
				break
		self._expect(')')

	def _parse_function_predicates_clause(self):
		"""Parses the PREDICATES clause in a CREATE FUNCTION statement"""
		# PREDICATES already matched
		# The surrounding parentheses seem to be optional (although the syntax
		# diagram in the DB2 Info Center implies otherwise)
		parens = self._match('(')
		self._expect('WHEN')
		self._match_one_of(['=', '<>', '<', '>', '<=', '>='])
		if self._match('EXPRESSION'):
			self._expect_sequence(['AS', IDENTIFIER])
		else:
			self._parse_expression()
		valid = ['SEARCH', 'FILTER']
		while valid:
			t = self._match_one_of(valid)
			if t:
				t = t[1]
				valid.remove(t)
			else:
				break
			if t == 'SEARCH':
				self._expect('BY')
				self._match('EXACT')
				self._expect('INDEX')
				self._expect('EXTENSION')
				self._parse_index_name()
				self._expect('WHEN')
				while True:
					self._expect_sequence(['KEY', '(', IDENTIFIER, ')', 'USE', IDENTIFIER, '('])
					self._parse_ident_list()
					self._expect(')')
					if not self._match('WHEN'):
						break
			elif t == 'FILTER':
				self._expect('USING')
				if self._match('CASE'):
					if self._match('WHEN'):
						self._parse_searched_case()
					else:
						self._parse_simple_case()
				else:
					self._parse_scalar_function_call()
		if parens:
			self._expect(')')

	def _parse_federated_options(self, alter=False):
		"""Parses an OPTIONS list for a federated object"""
		# OPTIONS already matched
		self._expect('(')
		while True:
			if alter and self._match('DROP'):
				self._expect(IDENTIFIER)
			else:
				if alter:
					self._match_one_of('ADD', 'SET')
				else:
					self._match('ADD')
				self._expect(IDENTIFIER)
				self._expect(STRING)
			if not self._match(','):
				break
		self._expect(')')

	def _parse_remote_server(self):
		"""Parses a remote server specification"""
		# SERVER already matched
		if self._match('TYPE'):
			self._expect(IDENTIFIER)
			if self._match('VERSION'):
				self._parse_server_version()
				if self._match('WRAPPER'):
					self._expect(IDENTIFIER)
		else:
			self._expect(IDENTIFIER)
			if self._match('VERSION'):
				self._parse_server_version()

	def _parse_server_version(self):
		"""Parses a federated server version"""
		# VERSION already matched
		if self._match(NUMBER):
			if self._match('.'):
				self._expect(NUMBER)
				if self._match('.'):
					self._expect(NUMBER)
		elif self._match(STRING):
			pass
		else:
			self._expected_one_of([NUMBER, STRING])

	def _parse_partition_boundary(self):
		"""Parses a partition boundary in a PARTITION clause"""
		if self._match('STARTING'):
			self._match('FROM')
			if self._match('('):
				while True:
					self._expect_one_of([NUMBER, 'MINVALUE', 'MAXVALUE'])
					if not self._match(','):
						break
				self._expect(')')
			else:
				self._expect_one_of([NUMBER, 'MINVALUE', 'MAXVALUE'])
			self._match_one_of(['INCLUSIVE', 'EXCLUSIVE'])
		self._expect('ENDING')
		self._match('AT')
		if self._match('('):
			while True:
				self._expect_one_of([NUMBER, 'MINVALUE', 'MAXVALUE'])
				if not self._match(','):
					break
			self._expect(')')
		else:
			self._expect_one_of([NUMBER, 'MINVALUE', 'MAXVALUE'])
		self._match_one_of(['INCLUSIVE', 'EXCLUSIVE'])

	def _parse_copy_options(self):
		"""Parse copy options for CREATE TABLE... LIKE statements"""
		# XXX Tidy this up (shouldn't just be a 2-time loop)
		for i in xrange(2):
			if self._match_one_of(['INCLUDING', 'EXCLUDING']):
				if self._match('COLUMN'):
					self._expect('DEFAULTS')
				elif self._match('DEFAULTS'):
					pass
				elif self._match('IDENTITY'):
					self._match_sequence(['COLUMN', 'ATTRIBUTES'])

	def _parse_refreshable_table_options(self, alter=False):
		"""Parses refreshable table options in a materialized query definition"""
		if not alter and self._match('WITH'):
			self._expect_sequence(['NO', 'DATA'])
			self._parse_copy_options()
		else:
			valid = [
				'DATA',
				'REFRESH',
				'ENABLE',
				'DISABLE',
				'MAINTAINED',
			]
			while valid:
				t = self._match_one_of(valid)
				if t:
					t = t[1]
					valid.remove(t)
				else:
					break
				if t == 'DATA':
					self._expect_sequence(['INITIALLY', 'DEFERRED'])
				elif t == 'REFRESH':
					self._expect_one_of(['DEFERRED', 'IMMEDIATE'])
				elif t in ('ENABLE', 'DISABLE'):
					self._expect_sequence(['QUERY', 'OPTIMIZATION'])
					if t == 'ENABLE':
						valid.remove('DISABLE')
					else:
						valid.remove('ENABLE')
				elif t == 'MAINTAINED':
					self._expect('BY')
					self._expect_one_of(['SYSTEM', 'USER', 'FEDERATED_TOOL'])

	def _parse_action_types_clause(self):
		"""Parses an action types clause in a WORK ACTION"""
		if self._match('MAP'):
			self._expect('ACTIVITY')
			if self._match_one_of(['WITH', 'WITHOUT']):
				self._expect('NESTED')
			self._expect('TO')
			self._expect(IDENTIFIER)
		elif self._match('WHEN'):
			self._parse_threshold_predicate()
			self._parse_threshold_exceeded_actions()
		elif self._match('PREVENT'):
			self._expect('EXECUTION')
		elif self._match('COUNT'):
			self._expect('ACTIVITY')
		elif self._match('COLLECT'):
			if self._match('ACTIVITY'):
				self._expect('DATA')
				self._parse_collect_activity_data_clause()
			elif self._match('AGGREGATE'):
				self._expect_sequence(['ACTIVITY', 'DATA'])
				self._match_one_of(['BASE', 'EXTENDED'])
		else:
			self._expected_one_of(['MAP', 'WHEN', 'PREVENT', 'COUNT', 'COLLECT'])

	def _parse_threshold_predicate(self):
		"""Parses a threshold predicate in a WORK ACTION"""
		if self._match_one_of([
			'TOTALDBPARTITIONCONNECTIONS',
			'CONCURRENTWORKLOADOCCURRENCES',
			'CONCURRENTWORKLOADACTIVITIES',
			'ESTIMATEDSQLCOST',
			'SQLROWSRETURNED',
		]):
			self._expect_sequence(['>', NUMBER])
		elif self._match('TOTALSCPARTITIONCONNECTIONS'):
			self._expect_sequence(['>', NUMBER])
			if self._match('QUEUEDCONNECTIONS'):
				if self._match('>'):
					self._expect(NUMBER)
				elif self._match('UNBOUNDED'):
					pass
				else:
					self._expected_one_of(['>', 'UNBOUNDED'])
		elif self._match('CONCURRENTDBCOORDACTIVITIES'):
			self._expect_sequence(['>', NUMBER])
			if self._match('QUEUEDACTIVITIES'):
				if self._match('>'):
					self._expect(NUMBER)
				elif self._match('UNBOUNDED'):
					pass
				else:
					self._expected_one_of(['>', 'UNBOUNDED'])
		elif self._match_one_of([
			'CONNECTIONIDLETIME',
			'ACTIVITYTOTALTIME',
		]):
			self._expect_sequence(['>', NUMBER])
			self._expect_one_of([
				'DAY',
				'DAYS',
				'HOUR',
				'HOURS',
				'MINUTE',
				'MINUTES'
			])
		elif self._match('SQLTEMPSPACE'):
			self._expect_sequence(['>', NUMBER])
			self._expect_one_of(['K', 'M', 'G'])

	def _parse_threshold_exceeded_actions(self):
		"""Parses a threshold exceeded actions clause in a WORK ACTION"""
		if self._match_sequence(['COLLECT', 'ACTIVITY', 'DATA']):
			self._parse_collect_activity_data_clause(alter=True)
		if self._match('STOP'):
			self._expect('EXECUTION')
		elif not self._match('CONTINUE'):
			self._expected_one_of(['STOP', 'CONTINUE'])

	def _parse_collect_activity_data_clause(self, alter=False):
		"""Parses a COLLECT ACTIVITY clause in an action clause"""
		# COLLECT ACTIVITY DATA already matched
		if not (alter and self._match('NONE')):
			self._expect('ON')
			if self._match('ALL'):
				self._match_sequence(['DATABASE', 'PARTITIONS'])
			elif self._match('COORDINATOR'):
				self._match_sequence(['DATABASE', 'PARTITION'])
			else:
				self._expected_one_of(['ALL', 'COORDINATOR'])
			if self._match('WITHOUT'):
				self._expect('DETAILS')
			elif self._match('WITH'):
				self._expect('DETAILS')
				if self._match('AND'):
					self._expect('VALUES')
			else:
				self._expected_one_of(['WITHOUT', 'WITH'])

	def _parse_histogram_template_clause(self):
		"""Parses a history template clause in a WORK ACTION"""
		if self._match('ACTIVITY'):
			self._expect_one_of(['LIFETIME', 'QUEUETIME', 'EXECUTETIME', 'ESIMATEDCOST', 'INTERARRIVALTIME'])
			self._expect_sequence(['HISTOGRAM', 'TEMPLATE'])
			self._expect_one_of(['SYSDEFAULTHISTOGRAM', IDENTIFIER])

	def _parse_work_attributes(self):
		"""Parses a work attributes clause in a WORK CLASS"""
		self._expect_sequence(['WORK', 'TYPE'])
		if self._match_one_of(['READ', 'WRITE', 'DML']):
			self._parse_for_from_to_clause()
		elif self._match('ALL'):
			if self._match('FOR'):
				self._parse_for_from_to_clause()
			if self._match('ROUTINES'):
				self._parse_routines_in_schema_clause()
		elif self._match('CALL'):
			if self._match('ROUTINES'):
				self._parse_routines_in_schema_clause()
		elif not self._match_one_of(['DDL', 'LOAD']):
			self._expected_one_of(['READ', 'WRITE', 'DML', 'DDL', 'LOAD', 'ALL', 'CALL'])

	def _parse_for_from_to_clause(self, alter=False):
		"""Parses a FOR .. FROM .. TO clause in a WORK CLASS definition"""
		# FOR already matched
		if alter and self._match('ALL'):
			self._expect_sequence(['UNITS', 'UNBOUNDED'])
		else:
			self._expect_one_of(['TIMERONCOST', 'CARDINALITY'])
			self._expect_sequence(['FROM', NUMBER])
			if self._match('TO'):
				self._expect_one_of(['UNBOUNDED', NUMBER])

	def _parse_routines_in_schema_clause(self, alter=False):
		"""Parses a schema clause in a WORK CLASS definition"""
		# ROUTINES already matched
		if alter and self._match('ALL'):
			pass
		else:
			self._expect_sequence(['IN', 'SCHEMA', IDENTIFIER])

	def _parse_position_clause(self):
		"""Parses a POSITION clause in a WORK CLASS definition"""
		# POSITION already matched
		if self._match('AT'):
			self._expect(NUMBER)
		elif self._match_one_of(['BEFORE', 'AFTER']):
			self._expect(IDENTIFIER)
		elif self._match('LAST'):
			pass
		else:
			self._expected_one_of(['AT', 'BEFORE', 'AFTER', 'LAST'])

	def _parse_connection_attributes(self):
		"""Parses connection attributes in a WORKLOAD"""
		if self._match_one_of([(REGISTER, 'APPLNAME'), (REGISTER, 'SYSTEM_USER')]):
			pass
		elif self._match((REGISTER, 'SESSION_USER')):
			self._match('GROUP')
		elif self._match('CURRENT'):
			self._expect_one_of([
				(REGISTER, 'CLIENT_USERID'),
				(REGISTER, 'CLIENT_APPLNAME'),
				(REGISTER, 'CLIENT_WRKSTNNAME'),
				(REGISTER, 'CLIENT_ACCTNG')
			])
		else:
			self._expected_one_of(['APPLNAME', 'SYSTEM_USER', 'SESSION_USER', 'CURRENT'])
		self._expect('(')
		while True:
			if not self._match(STRING):
				self._expect(')')
				break

	def _parse_audit_policy(self, alter=False):
		"""Parses an AUDIT POLICY definition"""
		valid = set(['CATEGORIES', 'ERROR'])
		while valid:
			t = self._match_one_of(valid)
			if t:
				t = t[1]
				valid.remove(t)
			else:
				break
			if t == 'CATEGORIES':
				while True:
					if self._expect_one_of([
						'ALL',
						'AUDIT',
						'CHECKING',
						'CONTEXT',
						'EXECUTE',
						'OBJMAINT',
						'SECMAINT',
						'VALIDATE'
					])[1] == 'EXECUTE':
						if self._match_one_of(['WITH', 'WITHOUT']):
							self._expect('DATA')
					self._expect('STATUS')
					self._expect_one_of(['BOTH', 'FAILURE', 'NONE', 'SUCCESS'])
					if not self._match(','):
						break
			elif t == 'ERROR':
				self._expect('TYPE')
				self._expect_one_of(['NORMAL', 'AUDIT'])
		# If we're defining a new policy, ensure both terms are specified
		if not alter and valid:
			self._expected(valid.pop())

	def _parse_evm_group(self):
		"""Parses an event monitor group in a non-wlm event monitor definition"""
		while True:
			self._expect(IDENTIFIER)
			if self._match('('):
				valid = set(['TABLE', 'IN', 'PCTDEACTIVATE', 'TRUNC', 'INCLUDES', 'EXCLUDES'])
				while valid:
					t = self._match_one_of(valid)
					if t:
						t = t[1]
						valid.remove(t)
					else:
						break
					if t == 'TABLE':
						self._parse_table_name()
					elif t == 'IN':
						self._expect(IDENTIFIER)
					elif t == 'PCTDEACTIVATE':
						self._expect(NUMBER)
					elif t == 'TRUNC':
						pass
					elif t == 'INCLUDES' or t == 'EXCLUDES':
						self._expect('(')
						while True:
							self._expect(IDENTIFIER)
							if not self._match(','):
								break
						self._expect(')')
				self._expect(')')
			if not self._match(','):
				break

	def _parse_evm_write_to(self):
		"""Parses a WRITE TO clause in an event monitor definition"""
		# WRITE TO already matched
		if self._match('TABLE'):
			valid = set(['BUFFERSIZE', 'BLOCKED', 'NONBLOCKED', 'evm-group'])
			while valid:
				t = self._match_one_of(valid)
				if t:
					t = t[1]
					valid.remove(t)
				elif 'evm-group' in valid:
					self._save_state()
					try:
						self._parse_evm_group()
						valid.remove('evm-group')
					except ParseError:
						self._restore_state()
						break
					else:
						self._forget_state()
				else:
					break
				if t == 'BUFFERSIZE':
					self._expect(NUMBER)
				elif t == 'BLOCKED':
					valid.remove('NONBLOCKED')
				elif t == 'NONBLOCKED':
					valid.remove('BLOCKED')
		elif self._match('PIPE'):
			self._expect(STRING)
		elif self._match('FILE'):
			self._expect(STRING)
			valid = set(['MAXFILES', 'MAXFILESIZE', 'BUFFERSIZE', 'BLOCKED', 'NONBLOCKED', 'APPEND', 'REPLACE'])
			while valid:
				t = self._match_one_of(valid)
				if t:
					t = t[1]
					valid.remove(t)
				else:
					break
				if t == 'MAXFILES' or t == 'MAXFILESIZE':
					self._expect_one_of(['NONE', NUMBER])
				elif t == 'BLOCKED':
					valid.remove('NONBLOCKED')
				elif t == 'NONBLOCKED':
					valid.remove('BLOCKED')
				elif t== 'APPEND':
					valid.remove('REPLACE')
				elif t == 'REPLACE':
					valid.remove('APPEND')
		else:
			self._expected_one_of(['TABLE', 'PIPE', 'FILE'])

	def _parse_evm_options(self):
		"""Parses the options after an event monitor definition"""
		valid = set(['WRITE', 'AUTOSTART', 'MANUALSTART', 'ON', 'LOCAL', 'GLOBAL'])
		while valid:
			t = self._match_one_of(valid)
			if t:
				t = t[1]
				valid.remove(t)
			else:
				break
			if t == 'WRITE':
				self._expect('TO')
				self._parse_evm_write_to()
			elif t == 'AUTOSTART':
				valid.remove('MANUALSTART')
			elif t == 'MANUALSTART':
				valid.remove('AUTOSTART')
			elif t == 'ON':
				self._expect_one_of(['NODE', 'DBPARTITIONNUM'])
				self._expect(NUMBER)
			elif t == 'LOCAL':
				valid.remove('GLOBAL')
			elif t == 'GLOBAL':
				valid.remove('LOCAL')

	def _parse_nonwlm_event_monitor(self):
		"""Parses a non-wlm event monitor definition"""
		while True:
			if self._match_one_of(['DATABASE', 'TABLES', 'BUFFERPOOLS', 'TABLESPACES']):
				pass
			elif self._match('DEADLOCKS'):
				if self._match_sequence(['WITH', 'DETAILS']):
					if self._match('HISTORY'):
						self._match('VALUES')
			elif self._match_one_of(['CONNECTIONS', 'STATEMENTS', 'TRANSACTIONS']):
				if self._match('WHERE'):
					self._parse_search_condition()
			else:
				self._expected_one_of([
					'DATABASE',
					'TABLES',
					'BUFFERPOOLS',
					'TABLESPACES',
					'DEADLOCKS',
					'CONNECTIONS',
					'STATEMENTS',
					'TRANSACTIONS',
				])
			if not self._match(','):
				break
		self._parse_evm_options()

	def _parse_wlm_event_monitor(self):
		"""Parses a wlm event monitor definition"""
		if self._expect_one_of(['ACTIVITIES', 'STATISTICS', 'THRESHOLD'])[1] == 'THRESHOLD':
			self._expect('VIOLATIONS')
		self._parse_evm_options()

	# STATEMENTS #############################################################

	def _parse_allocate_cursor_statement(self):
		"""Parses an ALLOCATE CURSOR statement in a procedure"""
		# ALLOCATE already matched
		self._expect_sequence([IDENTIFIER, 'CURSOR', 'FOR', 'RESULT', 'SET', IDENTIFIER])

	def _parse_alter_audit_policy_statement(self):
		"""Parses an ALTER AUDIT POLICY statement"""
		# ALTER AUDIT POLICY already matched
		self._expect(IDENTIIER)
		self._parse_audit_policy(alter=True)

	def _parse_alter_bufferpool_statement(self):
		"""Parses an ALTER BUFFERPOOL statement"""
		# ALTER BUFFERPOOL already matched
		self._expect(IDENTIFIER)
		if self._match('ADD'):
			if self._expect_one_of(['NODEGROUP', 'DATABASE'])[1] == 'DATABASE':
				self._expect_sequence(['PARTITION', 'GROUP'])
			self._expect(IDENTIFIER)
		elif self._match('NUMBLOCKPAGES'):
			self._expect(NUMBER)
			if self._match('BLOCKSIZE'):
				self._expect(NUMBER)
		elif self._match('BLOCKSIZE'):
			self._expect(NUMBER)
		elif self._match('NOT'):
			self._expect_sequence(['EXTENDED', 'STORAGE'])
		elif self._match('EXTENDED'):
			self._expect('STORAGE')
		else:
			self._match_one_of(['IMMEDIATE', 'DEFERRED'])
			if self._match_one_of(['DBPARTITIONNUM', 'NODE']):
				self._expect(NUMBER)
			self._expect('SIZE')
			if self._match(NUMBER):
				self._match('AUTOMATIC')
			else:
				self._expect_one_of([NUMBER, 'AUTOMATIC'])

	def _parse_alter_database_statement(self):
		"""Parses an ALTER DATABASE statement"""
		# ALTER DATABASE already matched
		if not self._match('ADD'):
			self._expect(IDENTIFIER)
			self._expect('ADD')
		self._expect_sequence(['STORAGE', 'ON'])
		while True:
			self._expect(STRING)
			if not self._match(','):
				break

	def _parse_alter_function_statement(self, specific):
		"""Parses an ALTER FUNCTION statement"""
		# ALTER [SPECIFIC] FUNCTION already matched
		self._parse_function_name()
		if not specific and self._match('(', prespace=False):
			if not self._match(')'):
				self._parse_datatype_list()
				self._expect(')')
		first = True
		while True:
			if self._match('EXTERNAL'):
				self._expect('NAME')
				self._expect_one_of([STRING, IDENTIFIER])
			elif self._match('NOT'):
				self._expect_one_of(['FENCED', 'THREADSAFE'])
			elif self._match_one_of(['FENCED', 'THREADSAFE']):
				pass
			elif first:
				self._expected_one_of([
					'EXTERNAL',
					'NOT',
					'FENCED',
					'THREADSAFE',
				])
			else:
				break
			first = False

	def _parse_alter_partition_group_statement(self):
		"""Parses an ALTER DATABASE PARTITION GROUP statement"""
		# ALTER [DATABASE PARTITION GROUP|NODEGROUP] already matched
		self._expect(IDENTIFIER)
		while True:
			if self._match('ADD'):
				self._parse_db_partitions_clause(size=False)
				if self._match('LIKE'):
					self._expect_one_of(['DBPARTITIONNUM', 'NODE'])
					self._expect(NUMBER)
				elif self._match('WITHOUT'):
					self._expect('TABLESPACES')
			elif self._match('DROP'):
				self._parse_db_partitions_clause(size=False)
			else:
				self._expected_one_of(['ADD', 'DROP'])
			if not self._match(','):
				break

	def _parse_alter_histogram_template_statement(self):
		"""Parses an ALTER HISTOGRAM TEMPLATE statement"""
		# ALTER HISTOGRAM TEMPLATE already matched
		self._expect_sequence([IDENTIFIER, 'HIGH', 'BIN', 'VALUE', NUMBER])

	def _parse_alter_nickname_statement(self):
		"""Parses an ALTER NICKNAME statement"""
		# ALTER NICKNAME already matched
		self._parse_nickname_name()
		if self._match('OPTIONS'):
			self._parse_federated_options(alter=True)
		while True:
			if self._match('ADD'):
				self._parse_table_constraint()
			elif self._match('ALTER'):
				if self._match('FOREIGN'):
					self._expect('KEY')
					self._parse_constraint_alteration()
				elif self._match('CHECK'):
					self._parse_constraint_alteration()
				else:
					# Ambiguity: A column can be called COLUMN
					self._save_state()
					try:
						self._match('COLUMN')
						self._parse_federated_column_alteration()
					except ParseError:
						self._restore_state()
						self._parse_federated_column_alteration()
					else:
						self._forget_state()
			elif self._match('DROP'):
				if self._match('PRIMARY'):
					self._expect('KEY')
				elif self._match('FOREIGN'):
					self._expect_sequence(['KEY', IDENTIFIER])
				elif self._match_one_of(['UNIQUE', 'CHECK', 'CONSTRAINT']):
					self._expect(IDENTIFIER)
				else:
					self._expected_one_of(['PRIMARY', 'FOREIGN', 'CHECK', 'CONSTRAINT'])
			elif self._match_one_of(['ALLOW', 'DISALLOW']):
				self._expect('CACHING')
			else:
				break
			self._newline()

	def _parse_alter_procedure_statement(self, specific):
		"""Parses an ALTER PROCEDURE statement"""
		# ALTER [SPECIFIC] PROCEDURE already matched
		self._parse_procedure_name()
		if not specific and self._match('(', prespace=False):
			if not self._match(')'):
				self._parse_datatype_list()
				self._expect(')')
		first = True
		while True:
			if self._match('EXTERNAL'):
				if self._match('NAME'):
					self._expect([STRING, IDENTIFIER])
				elif self._match('ACTION'):
					pass
				else:
					self._expected_one_of(['NAME', 'ACTION'])
			elif self._match('NOT'):
				self._expect_one_of(['FENCED', 'THREADSAFE'])
			elif self._match_one_of(['FENCED', 'THREADSAFE']):
				pass
			elif self._match('NO'):
				self._expect_sequence(['EXTERNAL', 'ACTION'])
			elif self._match('NEW'):
				self._expect_sequence(['SAVEPOINT', 'LEVEL'])
			elif self._match('ALTER'):
				self._expect_sequence(['PARAMETER', IDENTIFIER, 'SET', 'DATA', 'TYPE'])
				self._parse_datatype()
			elif first:
				self._expected_one_of([
					'EXTERNAL',
					'NOT',
					'FENCED',
					'NO',
					'EXTERNAL',
					'THREADSAFE',
					'ALTER',
				])
			else:
				break
			first = False

	def _parse_alter_security_label_component_statement(self):
		"""Parses an ALTER SECURITY LABEL COMPONENT statement"""
		# ALTER SECURITY LABEL COMPONENT already matched
		self._expect_sequence(IDENTIFIER, 'ADD', 'ELEMENT', STRING)
		if self._match_one_of(['BEFORE', 'AFTER']):
			self._expect(STRING)
		elif self._match('ROOT'):
			pass
		elif self._match('UNDER'):
			self._expect(STRING)
			if self._match('OVER'):
				while True:
					self._expect(STRING)
					if not self._match(','):
						break
					self._expect('OVER')

	def _parse_alter_security_policy_statement(self):
		"""Parses an ALTER SECURITY POLICY statement"""
		# ALTER SECURITY POLICY
		self._expect(IDENTIFIER)
		while True:
			if self._match('ADD'):
				self._expect_sequence(['SECURITY', 'LABEL', 'COMPONENT', IDENTIFIER])
			elif self._match_one_of(['OVERRIDE', 'RESTRICT']):
				self._expect_sequence(['NOT', 'AUTHORIZED', 'WRITE', 'SECURITY', 'LABEL'])
			elif self._match_one_of(['USE', 'IGNORE']):
				self._expect_one_of(['GROUP', 'ROLE'])
				self._expect('AUTHORIZATIONS')
			else:
				break

	def _parse_alter_sequence_statement(self):
		"""Parses an ALTER SEQUENCE statement"""
		# ALTER SEQUENCE already matched
		self._parse_sequence_name()
		self._parse_identity_options(alter='SEQUENCE')

	def _parse_alter_server_statement(self):
		"""Parses an ALTER SERVER statement"""
		# ALTER SERVER already matched
		self._parse_remote_server()
		if self._match('OPTIONS'):
			self._parse_federated_options(alter=True)

	def _parse_alter_service_class_statement(self):
		"""Parses an ALTER SERVICE CLASS statement"""
		# ALTER SERVICE CLASS already matched
		self._expect(IDENTIFIER)
		if self._match('UNDER'):
			self._expect(IDENTIFIER)
		first = True
		while True:
			if self._match('AGENT'):
				self._expect('PRIORITY')
				self._expect_one_of(['DEFAULT', NUMBER])
			elif self._match('PREFETCH'):
				self._expect('PRIORITY')
				self._expect_one_of(['LOW', 'MEDIUM', 'HIGH', 'DEFAULT'])
			elif self._match('OUTBOUND'):
				self._expect('CORRELATOR')
				self._expect_one_of(['NONE', STRING])
			elif self._match('COLLECT'):
				if self._match('ACTIVITY'):
					self._expect('DATA')
					if self._match('ON'):
						if self._match('ALL'):
							self._match_sequence(['DATABASE', 'PARTITIONS'])
						elif self._match('COORDINATOR'):
							self._match_sequence(['DATABASE', 'PARTITION'])
						else:
							self._expected_one_of(['ALL', 'COORDINATOR'])
						self._expect_one_of(['WITH', 'WITHOUT'])
						self._expect('DETAILS')
						self._match_sequence(['AND', 'VALUES'])
					elif self._match('NONE'):
						pass
					else:
						self._expected_one_of(['ON', 'NONE'])
				elif self._match('AGGREGATE'):
					if self._match('ACTIVITY'):
						self._expect('DATA')
						self._match_one_of(['BASE', 'EXTENDED', 'NONE'])
					elif self._match('REQUEST'):
						self._expect('DATA')
						self._match_one_of(['BASE', 'NONE'])
					else:
						self._expected_one_of(['ACTIVITY', 'REQUEST'])
				else:
					self._expected_one_of(['ACTIVITY', 'AGGREGATE'])
			elif self._match('ACTIVITY'):
				self._expect_one_of(['LIFETIME', 'QUEUETIME', 'EXECUTETIME', 'ESTIMATEDCOST', 'INTERARRIVALTIME'])
				self._expect_sequence(['HISTOGRAM', 'TEMPLATE', IDENTIFIER])
			elif self._match('REQUEST'):
				self._expect_sequence(['EXECUTETIME', 'HISTOGRAM', 'TEMPLATE', IDENTIFIER])
			elif self._match_one_of(['ENABLE', 'DISABLE']):
				pass
			elif not first:
				break
			else:
				self._expected_one_of([
					'AGENT',
					'PREFETCH',
					'OUTBOUND',
					'COLLECT',
					'ACTIVITY',
					'REQUEST',
					'ENABLE',
					'DISABLE'
				])

	def _parse_alter_table_statement(self):
		"""Parses an ALTER TABLE statement"""
		# ALTER TABLE already matched
		self._parse_table_name()
		self._indent()
		while True:
			if self._match('ADD'):
				if self._match('RESTRICT'):
					self._expect_sequence(['ON', 'DROP'])
				elif self._match('PARTITION'):
					# Ambiguity: optional partition name
					self._save_state()
					try:
						self._match(IDENTIFIER)
						self._parse_partition_boundary()
					except ParseError:
						self._restore_state()
						self._parse_partition_boundary()
					else:
						self._forget_state()
					if self._match('IN'):
						self._expect(IDENTIFIER)
					if self._match('LONG'):
						self._expect('IN')
						self._expect(IDENTIFIER)
				elif self._match('MATERIALIZED'):
					self._expect('QUERY')
					self._expect('(')
					self._indent()
					self._parse_full_select()
					self._outdent()
					self._expect(')')
					self._parse_refreshable_table_options(alter=True)
				elif self._match('QUERY'):
					self._expect('(')
					self._indent()
					self._parse_full_select()
					self._outdent()
					self._expect(')')
					self._parse_refreshable_table_options(alter=True)
				elif self._match('('):
					self._indent()
					self._parse_full_select()
					self._outdent()
					self._expect(')')
					self._parse_refreshable_table_options(alter=True)
				elif self._match('COLUMN'):
					self._parse_column_definition()
				elif self._match('SECURITY'):
					self._expect('POLICY')
					self._expect(IDENTIFIER)
				else:
					self._save_state()
					try:
						# Try parsing a table constraint definition
						self._parse_table_constraint()
					except ParseError:
						# If that fails, rewind and try and parse a column definition
						self._restore_state()
						self._parse_column_definition()
					else:
						self._forget_state()
			elif self._match('ATTACH'):
				self._expect('PARTITION')
				# Ambiguity: optional partition name
				self._save_state()
				try:
					self._match(IDENTIFIER)
					self._parse_partition_boundary()
				except ParseError:
					self._restore_state()
					self._parse_partition_boundary()
				else:
					self._forget_state()
				self._expect('FROM')
				self._parse_table_name()
			elif self._match('DETACH'):
				self._expect_sequence(['PARTITION', IDENTIFIER, 'FROM'])
				self._parse_table_name()
			elif self._match('ALTER'):
				if self._match('FOREIGN'):
					self._expect('KEY')
					self._parse_constraint_alteration()
				elif self._match('CHECK'):
					self._parse_constraint_alteration()
				else:
					# Ambiguity: A column can be called COLUMN
					self._save_state()
					try:
						self._match('COLUMN')
						self._parse_column_alteration()
					except ParseError:
						self._restore_state()
						self._parse_column_alteration()
					else:
						self._forget_state()
			elif self._match('DROP'):
				if self._match('PRIMARY'):
					self._expect('KEY')
				elif self._match('FOREIGN'):
					self._expect_sequence(['KEY', IDENTIFIER])
				elif self._match_one_of(['UNIQUE', 'CHECK', 'CONSTRAINT']):
					self._expect(IDENTIFIER)
				elif self._match('COLUMN'):
					self._expect(IDENTIFIER)
					self._match_one_of(['CASCADE', 'RESTRICT'])
				elif self._match('RESTRICT'):
					self._expect_sequence(['ON', 'DROP'])
				elif self._match('DISTRIBUTION'):
					pass
				elif self._match('MATERIALIZED'):
					self._expect('QUERY')
				elif self._match('QUERY'):
					pass
				elif self._match('SECURITY'):
					self._expect('POLICY')
				else:
					self._expect(IDENTIFIER)
					self._match_one_of(['CASCADE', 'RESTRICT'])
			elif self._match('DATA'):
				self._expect('CAPTURE')
				if self._match('CHANGES'):
					self._match_sequence(['INCLUDE', 'LONGVAR', 'COLUMNS'])
				elif self._match('NONE'):
					pass
				else:
					self._expected_one_of(['NONE', 'CHANGES'])
			elif self._match('PCTFREE'):
				self._expect(NUMBER)
			elif self._match('LOCKSIZE'):
				self._expect_one_of(['ROW', 'BLOCKINSERT', 'TABLE'])
			elif self._match('APPEND'):
				self._expect_one_of(['ON', 'OFF'])
			elif self._match('VOLATILE'):
				self._match('CARDINALITY')
			elif self._match('NOT'):
				self._expect('VOLATILE')
				self._match('CARDINALITY')
			elif self._match('COMPRESS'):
				self._expect_one_of(['YES', 'NO'])
			elif self._match('ACTIVATE'):
				if self._expect_one_of(['NOT', 'VALUE'])[1] == 'NOT':
					self._expect_sequence(['LOGGED', 'INITIALLY'])
					if self._match('WITH'):
						self._expect_sequence(['EMPTY', 'TABLE'])
				else:
					self._expect('COMPRESSION')
			elif self._match('DEACTIVATE'):
				self._expect_sequence(['VALUE', 'COMPRESSION'])
			else:
				break
			self._newline()
		self._outdent()

	def _parse_alter_tablespace_statement(self):
		"""Parses an ALTER TABLESPACE statement"""
		# ALTER TABLESPACE already matched
		self._expect(IDENTIFIER)
		first = True
		while True:
			if self._match('ADD'):
				if self._match('TO'):
					self._expect_sequence(['STRIPE', 'SET', IDENTIFIER])
					self._parse_database_container_clause()
					if self._match('ON'):
						self._parse_db_partitions_clause(size=False)
				else:
					# Ambiguity: could be a Database or a System container
					# clause here
					reraise = False
					self._save_state()
					try:
						# Try a database clause first
						self._parse_database_container_clause()
						reraise = True
						if self._match('ON'):
							self._parse_db_partitions_clause(size=False)
					except ParseError:
						# If that fails, rewind and try a system container
						# clause
						self._restore_state()
						if reraise: raise
						self._parse_system_container_clause()
						self._parse_db_partitions_clause(size=False)
					else:
						self._forget_state()
			elif self._match('BEGIN'):
				self._expect_sequence(['NEW', 'STRIPE', 'SET'])
				self._parse_database_container_clause()
				if self._match('ON'):
					self._parse_db_partitions_clause(size=False)
			elif self._match('DROP'):
				self._parse_database_container_clause(size=False)
				if self._match('ON'):
					self._parse_db_partitions_clause(size=False)
			elif self._match_one_of(['EXTEND', 'REDUCE']):
				# Ambiguity: could be a Database or ALL containers clause
				reraise = False
				self._save_state()
				try:
					# Try an ALL containers clause first
					self._expect_sequence(['(', 'ALL'])
					reraise = True
					self._match('CONTAINERS')
					self._expect(NUMBER)
					self._match_one_of(['K', 'M', 'G'])
					self._expect(')')
				except ParseError:
					# If that fails, rewind and try a database container clause
					self._restore_state()
					if reraise: raise
					self._parse_database_container_clause()
				else:
					self._forget_state()
				if self._match('ON'):
					self._parse_db_partitions_clause(size=False)
			elif self._match('PREFETCHSIZE'):
				if not self._match('AUTOMATIC'):
					self._expect(NUMBER)
					self._match_one_of(['K', 'M', 'G'])
			elif self._match('BUFFERPOOL'):
				self._expect(IDENTIFIER)
			elif self._match('OVERHEAD'):
				self._expect(NUMBER)
			elif self._match('TRANSFERRATE'):
				self._expect(NUMBER)
			elif self._match('NO'):
				self._expect_sequence(['FILE', 'SYSTEM', 'CACHING'])
			elif self._match('FILE'):
				self._expect_sequence(['SYSTEM', 'CACHING'])
			elif self._match('DROPPED'):
				self._expect_sequence(['TABLE', 'RECOVERY'])
				self._expect_one_of(['ON', 'OFF'])
			elif self._match('SWITCH'):
				self._expect('ONLINE')
			elif self._match('INCREASESIZE'):
				self._expect(NUMBER)
				self._expect_one_of(['K', 'M', 'G', 'PERCENT'])
			elif self._match('MAXSIZE'):
				if not self_match('NONE'):
					self._expect(NUMBER)
					self._expect_one_of(['K', 'M', 'G'])
			elif self._match('CONVERT'):
				self._expect_sequence(['TO', 'LARGE'])
			elif first:
				self._expected_one_of([
					'ADD',
					'BEGIN',
					'DROP'
					'EXTEND',
					'REDUCE',
					'PREFETCHSIZE',
					'BUFFERPOOL',
					'OVERHEAD',
					'TRANSFERRATE',
					'NO',
					'FILE',
					'DROPPED',
					'SWITCH',
					'INCREASESIZE',
					'MAXSIZE',
					'CONVERT',
				])
			else:
				break
			first = False

	def _parse_alter_threshold_statement(self):
		"""Parses an ALTER THRESHOLD statement"""
		# ALTER THRESHOLD already matched
		self._expect(IDENTIFIER)
		while True:
			if self._match('WHEN'):
				self._parse_threshold_predicate()
				self._parse_threshold_exceeded_actions()
			elif not self._match_one_of(['ENABLE', 'DISABLE']):
				break

	def _parse_alter_trusted_context_statement(self):
		"""Parses an ALTER TRUSTED CONTEXT statement"""
		# ALTER TRUSTED CONTEXT already matched
		self._expect(IDENTIFIER)
		first = True
		while True:
			if self._match('ADD'):
				if self._match('ATTRIBUTES'):
					self._expect('(')
					while True:
						self._expect_sequence(['ADDRESS', STRING])
						if self._match('WITH'):
							self._expect_sequence(['ENCRYPTION', STRING])
						if not self._match(','):
							break
					self._expect(')')
				elif self._match('USE'):
					self._expect('FOR')
					while True:
						if not self._match('PUBLIC'):
							self._expect(IDENTIFIER)
							self._match_sequence(['ROLE', IDENTIFIER])
							if self._match_one_of(['WITH', 'WITHOUT']):
								self._expect('AUTHENTICATION')
						if not self._match(','):
							break
				else:
					self._expected_one_of(['ATTRIBUTES', 'USE'])
			elif self._match('DROP'):
				if self._match('ATTRIBUTES'):
					self._expect('(')
					while True:
						self._expect_sequence(['ADDRESS', STRING])
						if not self._match(','):
							break
					self._expect(')')
				elif self._match('USE'):
					self._expect('FOR')
					while True:
						if not self._match('PUBLIC'):
							self._expect(IDENTIFIER)
						if not self._match(','):
							break
				else:
					self._expected_one_of(['ATTRIBUTES', 'USE'])
			elif self._match('ALTER'):
				while True:
					if self._match('SYSTEM'):
						self._expect_sequence(['AUTHID', IDENTIFIER])
					elif self._match('ATTRIBUTES'):
						self._expect('(')
						while True:
							self._expect_one_of(['ADDRESS', 'ENCRYPTION'])
							self._expect(STRING)
							if not self._match(','):
								break
						self._expect(')')
					elif self._match('NO'):
						self._expect_sequence(['DEFAULT', 'ROLE'])
					elif self._match('DEFAULT'):
						self._expect_sequence(['ROLE', IDENTIFIER])
					elif not self._match_one_of(['ENABLE', 'DISABLE']):
						break
			elif self._match('REPLACE'):
				self._expect_sequence(['USE', 'FOR'])
				while True:
					if not self._match('PUBLIC'):
						self._expect(IDENTIFIER)
						self._match_sequence(['ROLE', IDENTIFIER])
						if self._match_one_of(['WITH', 'WITHOUT']):
							self._expect('AUTHENTICATION')
					if not self._match(','):
						break
			elif first:
				self._expected_one_of(['ALTER', 'ADD', 'DROP', 'REPLACE'])
			else:
				break
			first = False

	def _parse_alter_user_mapping_statement(self):
		"""Parses an ALTER USER MAPPING statement"""
		# ALTER USER MAPPING already matched
		if not self._match('USER'):
			self._expect_sequence([IDENTIFIER, 'SERVER', IDENTIFIER, 'OPTIONS'])
			self._parse_federated_options(alter=True)

	def _parse_alter_view_statement(self):
		"""Parses an ALTER VIEW statement"""
		# ALTER VIEW already matched
		self._parse_view_name()
		self._expect_one_of(['ENABLE', 'DISABLE'])
		self._expect_sequence(['QUERY', 'OPTIMIZATION'])

	def _parse_alter_work_action_set_statement(self):
		"""Parses an ALTER WORK ACTION SET statement"""
		# ALTER WORK ACTION SET already matched
		self._expect(IDENTIFIER)
		first = True
		while True:
			if self._match('ADD'):
				self._match_sequence(['WORK', 'ACTION'])
				self._expect_sequence([IDENTIFIER, 'ON', 'WORK', 'CLASS', IDENTIFIER])
				self._parse_action_types_clause()
				self._parse_histogram_template_clause()
				self._match_one_of(['ENABLE', 'DISABLE'])
			elif self._match('ALTER'):
				self._match_sequence(['WORK', 'ACTION'])
				self._expect(IDENTIFIER)
				while True:
					if self._match('SET'):
						self._expect_sequence(['WORK', 'CLASS', IDENTIFIER])
					elif self._match('ACTIVITY'):
						self._expect_one_of(['LIFETIME', 'QUEUETIME', 'EXECUTETIME', 'ESIMATEDCOST', 'INTERARRIVALTIME'])
						self._expect_sequence(['HISTOGRAM', 'TEMPLATE', IDENTIFIER])
					elif self._match_one_of(['ENABLE', 'DISABLE']):
						pass
					else:
						# Ambiguity: could be the end of the loop, or an action
						# types clause
						self._save_state()
						try:
							self._parse_action_types_clause()
						except ParseError:
							self._restore_state()
							break
						else:
							self._forget_state()
			elif self._match('DROP'):
				self._match_sequence(['WORK', 'ACTION'])
				self._expect(IDENTIFIER)
			elif self._match_one_of(['ENABLE', 'DISABLE']):
				pass
			elif first:
				self._expected_one_of(['ADD', 'ALTER', 'DROP', 'ENABLE', 'DISABLE'])
			else:
				break
			first = False

	def _parse_alter_work_class_set_statement(self):
		"""Parses an ALTER WORK CLASS SET statement"""
		# ALTER WORK CLASS SET already matched
		self._expect(IDENTIFIER)
		outer = True
		while True:
			if self._match('ADD'):
				self._match_sequence(['WORK', 'CLASS'])
				self._expect(IDENTIFIER)
				self._parse_work_attributes()
				self._expect('POSITION')
				self._parse_position_clause()
			elif self._match('ALTER'):
				self._match_sequence(['WORK', 'CLASS'])
				self._expect(IDENTIFIER)
				inner = True
				while True:
					if self._match('FOR'):
						self._parse_for_from_to_clause(alter=True)
					elif self._match('POSITION'):
						self._parse_position_clause()
					elif self._match('ROUTINES'):
						self._parse_routines_in_schema_clause(alter=True)
					elif inner:
						self._expected_one_of(['FOR', 'POSITION', 'ROUTINES'])
					else:
						break
					inner = False
			elif self._match('DROP'):
				self._match_sequence(['WORK', 'CLASS'])
				self._expect(IDENTIFIER)
			elif outer:
				self._expected_one_of(['ADD', 'ALTER', 'DROP'])
			else:
				break
			outer = False

	def _parse_alter_workload_statement(self):
		"""Parses an ALTER WORKLOAD statement"""
		self._expect(IDENTIFIER)
		first = True
		while True:
			if self._match('ADD'):
				self._parse_connection_attributes()
			elif self._match('DROP'):
				self._parse_connection_attributes()
			elif self._match_one_of(['ALLOW', 'DISALLOW']):
				self._expect_sequence(['DB', 'ACCESS'])
			elif self._match_one_of(['ENABLE', 'DISABLE']):
				pass
			elif self._match('SERVICE'):
				self._expect_sequence(['CLASS', IDENTIFIER])
				if self._match('UNDER'):
					self._expect(IDENTIFIER)
			elif self._match('POSITION'):
				self._parse_position_clause()
			elif self._match_sequence(['COLLECT', 'ACTIVITY', 'DATA']):
				self._parse_collect_activity_data_clause(alter=True)
			elif first:
				self._expected_one_of([
					'ADD',
					'DROP',
					'ALLOW',
					'DISALLOW',
					'ENABLE',
					'DISABLE',
					'SERVICE',
					'POSITION',
					'COLLECT'
				])
			else:
				break
			first = False

	def _parse_alter_wrapper_statement(self):
		"""Parses an ALTER WRAPPER statement"""
		# ALTER WRAPPER already matched
		self._expect(IDENTIFIER)
		self._expect('OPTIONS')
		self._parse_federated_options(alter=True)

	def _parse_associate_locators_statement(self):
		"""Parses an ASSOCIATE LOCATORS statement in a procedure"""
		# ASSOCIATE already matched
		self._match_sequence(['RESULT', 'SET'])
		self._expect_one_of(['LOCATOR', 'LOCATORS'])
		self._expect('(')
		self._parse_ident_list()
		self._expect(')')
		self._expect_sequence(['WITH', 'PROCEDURE'])
		self._parse_procedure_name()

	def _parse_audit_statement(self):
		"""Parses an AUDIT statement"""
		# AUDIT already matched
		while True:
			if self._match_one_of([
				'DATABASE',
				'SYSADM',
				'SYSCTRL',
				'SYSMAINT',
				'SYSMON',
				'SECADM',
				'DBADM',
			]):
				pass
			elif self._match('TABLE'):
				self._parse_table_name()
			elif self._match_sequence(['TRUSTED', 'CONTEXT']):
				self._expect(IDENTIFIER)
			elif self._match_one_of(['USER', 'GROUP', 'ROLE']):
				self._expect(IDENTIFIER)
			else:
				self._expected_one_of([
					'DATABASE',
					'SYSADM',
					'SYSCTRL',
					'SYSMAINT',
					'SYSMON',
					'SECADM',
					'DBADM',
					'TABLE',
					'TRUSTED',
					'USER',
					'GROUP',
					'ROLE',
				])
			if not self._match(','):
				break
		if self._match_one_of(['USING', 'REPLACE']):
			self._expect_sequence(['POLICY', IDENTIFIER])
		elif not self._match_sequence(['REMOVE', 'POLICY']):
			self._expected_one_of(['USING', 'REPLACE', 'REMOVE'])

	def _parse_call_statement(self):
		"""Parses a CALL statement"""
		# CALL already matched
		self._parse_subschema_name()
		if self._match('(', prespace=False):
			self._parse_expression_list()
			self._expect(')')

	def _parse_case_statement(self, inproc):
		"""Parses a CASE-conditional in a procedure"""
		# CASE already matched
		if self._match('WHEN'):
			# Parse searched-case-statement
			simple = False
			self._indent(-1)
		else:
			# Parse simple-case-statement
			self._parse_expression()
			self._indent()
			self._expect('WHEN')
			simple = True
		# Parse WHEN clauses (only difference is predicate/expression after
		# WHEN)
		t = None
		while True:
			if simple:
				self._parse_expression()
			else:
				self._parse_search_condition()
			self._expect('THEN')
			self._indent()
			while True:
				if inproc:
					self._parse_procedure_statement()
				else:
					self._parse_routine_statement()
				self._expect((TERMINATOR, ';'))
				t = self._match_one_of(['WHEN', 'ELSE', 'END'])
				if t:
					self._outdent(-1)
					t = t[1]
					break
				else:
					self._newline()
			if t != 'WHEN':
				break
		# Handle ELSE clause (common to both variations)
		if t == 'ELSE':
			self._indent()
			while True:
				if inproc:
					self._parse_procedure_statement()
				else:
					self._parse_routine_statement()
				self._expect((TERMINATOR, ';'))
				if self._match('END'):
					self._outdent(-1)
					break
				else:
					self._newline()
		self._outdent(-1)
		self._expect('CASE')

	def _parse_close_statement(self):
		"""Parses a CLOSE cursor statement"""
		# CLOSE already matched
		self._expect(IDENTIFIER)
		self._match_sequence(['WITH', 'RELEASE'])

	def _parse_comment_statement(self):
		"""Parses a COMMENT ON statement"""
		# COMMENT ON already matched
		# Ambiguity: table/view can be called TABLE, VIEW, ALIAS, etc.
		reraise = False
		self._save_state()
		try:
			# Try parsing an extended TABLE/VIEW comment first
			self._parse_relation_name()
			self._expect('(')
			self._indent()
			while True:
				self._expect(IDENTIFIER)
				self._valign()
				self._expect_sequence(['IS', STRING])
				reraise = True
				if self._match(','):
					self._newline()
				else:
					break
			self._vapply()
			self._outdent()
			self._expect(')')
		except ParseError:
			# If that fails, rewind and parse a single-object comment
			self._restore_state()
			if reraise: raise
			if self._match_one_of(['ALIAS', 'TABLE', 'NICKNAME', 'INDEX', 'TRIGGER', 'VARIABLE']):
				self._parse_subschema_name()
			elif self._match('TYPE'):
				if self._match('MAPPING'):
					self._expect(IDENTIFIER)
				else:
					self._parse_subschema_name()
			elif self._match('PACKAGE'):
				self._parse_subschema_name()
				self._match('VERSION')
				# XXX Ambiguity: IDENTIFIER will match "IS" below. How to solve
				# this? Only double-quoted identifiers are actually permitted
				# here (or strings)
				self._match_one_of([IDENTIFIER, STRING])
			elif self._match_one_of(['DISTINCT', 'DATA']):
				self._expect('TYPE')
				self._parse_type_name()
			elif self._match_one_of(['COLUMN', 'CONSTRAINT']):
				self._parse_subrelation_name()
			elif self._match_one_of(['SCHEMA', 'TABLESPACE', 'WRAPPER', 'WORKLOAD', 'NODEGROUP', 'ROLE', 'THRESHOLD']):
				self._expect(IDENTIFIER)
			elif self._match_sequence(['DATABASE', 'PARTITION', 'GROUP']):
				self._expect(IDENTIFIER)
			elif self._match_sequence(['AUDIT', 'POLICY']):
				self._expect(IDENTIFIER)
			elif self._match_sequence(['SECURITY', 'POLICY']):
				self._expect(IDENTIFIER)
			elif self._match_sequence(['SECURITY', 'LABEL']):
				self._match('COMPONENT')
				self._expect(IDENTIFIER)
			elif self._match('SERVER'):
				if self._match('OPTION'):
					self._expect_sequence([IDENTIFIER, 'FOR'])
					self._parse_remote_server()
				else:
					self._expect(IDENTIFIER)
			elif self._match('SERVICE'):
				self._expect('CLASS')
				self._expect(IDENTIFIER)
				self._match_sequence(['UNDER', IDENTIFIER])
			elif self._match_sequence(['TRUSTED', 'CONTEXT']):
				self._expect(IDENTIFIER)
			elif self._match_sequence(['HISTOGRAM', 'TEMPLATE']):
				self._expect(IDENTIFIER)
			elif self._match_sequence(['WORK', 'ACTION', 'SET']):
				self._expect(IDENTIFIER)
			elif self._match_sequence(['WORK', 'CLASS', 'SET']):
				self._expect(IDENTIFIER)
			elif self._match('FUNCTION'):
				if self._match('MAPPING'):
					self._expect(IDENTIFIER)
				else:
					self._parse_routine_name()
					if self._match('(', prespace=False):
						self._parse_datatype_list()
						self._expect(')')
			elif self._match('PROCEDURE'):
				self._parse_routine_name()
				if self._match('(', prespace=False):
					self._parse_datatype_list()
					self._expect(')')
			elif self._match('SPECIFIC'):
				self._expect_one_of(['FUNCTION', 'PROCEDURE'])
				self._parse_routine_name()
			else:
				self._expected_one_of([
					'ALIAS',
					'AUDIT',
					'COLUMN',
					'CONSTRAINT',
					'DATA',
					'DATABASE',
					'DISTINCT',
					'FUNCTION',
					'HISTOGRAM',
					'INDEX',
					'NICKNAME',
					'PROCEDURE',
					'ROLE',
					'SCHEMA',
					'SECURITY',
					'SERVER',
					'SERVICE',
					'SPECIFIC',
					'TABLE',
					'TABLESPACE',
					'THRESHOLD',
					'TRIGGER',
					'TRUSTED',
					'TYPE',
					'VARIABLE',
					'WORK',
					'WORKLOAD',
					'WRAPPER',
				])
			self._expect_sequence(['IS', STRING])
		else:
			self._forget_state()

	def _parse_commit_statement(self):
		"""Parses a COMMIT statement"""
		# COMMIT already matched
		self._match('WORK')

	def _parse_create_alias_statement(self):
		"""Parses a CREATE ALIAS statement"""
		# CREATE ALIAS already matched
		self._parse_relation_name()
		self._expect('FOR')
		self._parse_relation_name()

	def _parse_create_audit_policy_statement(self):
		"""Parses a CREATE AUDIT POLICY statement"""
		# CREATE AUDIT POLICY already matched
		self._expect(IDENTIFIER)
		self._parse_audit_policy()

	def _parse_create_bufferpool_statement(self):
		"""Parses a CREATE BUFFERPOOL statement"""
		# CREATE BUFFERPOOL already matched
		self._expect(IDENTIFIER)
		self._match_one_of(['IMMEDIATE', 'DEFERRED'])
		if self._match('ALL'):
			self._expect('DBPARTITIONNUMS')
		elif self._match('DATABASE'):
			self._expect_sequence(['PARTITION', 'GROUP'])
			self._parse_ident_list()
		elif self._match('NODEGROUP'):
			self._parse_ident_list()
		self._expect('SIZE')
		if self._match(NUMBER):
			self._match('AUTOMATIC')
		elif self._match('AUTOMATIC'):
			pass
		else:
			self._expected_one_of([NUMBER, 'AUTOMATIC'])
		# Parse function options (which can appear in any order)
		valid = set(['NUMBLOCKPAGES', 'PAGESIZE', 'EXTENDED', 'EXCEPT', 'NOT'])
		while valid:
			t = self._match_one_of(valid)
			if t:
				t = t[1]
				valid.remove(t)
			else:
				break
			if self._match('EXCEPT'):
				self._expect('ON')
				self._parse_db_partitions_clause(size=True)
			elif t == 'NUMBLOCKPAGES':
				self._expect(NUMBER)
				if self._match('BLOCKSIZE'):
					self._expect(NUMBER)
			elif t == 'PAGESIZE':
				self._expect(NUMBER)
				self._match('K')
			elif t == 'EXTENDED':
				self._expect('STORAGE')
				valid.remove('NOT')
			elif t == 'NOT':
				self._expect_sequence(['EXTENDED', 'STORAGE'])
				valid.remove('EXTENDED')

	def _parse_create_database_partition_group_statement(self):
		"""Parses an CREATE DATABASE PARTITION GROUP statement"""
		# CREATE [DATABASE PARTITION GROUP|NODEGROUP] already matched
		self._expect(IDENTIFIER)
		if self._match('ON'):
			if self._match('ALL'):
				self._expect_one_of(['DBPARTITIONNUMS', 'NODES'])
			else:
				self._parse_db_partitions_clause(size=False)

	def _parse_create_event_monitor_statement(self):
		"""Parses a CREATE EVENT MONITOR statement"""
		# CREATE EVENT MONITOR already matched
		self._expect(IDENTIFIER)
		self._expect('FOR')
		self._save_state()
		try:
			self._parse_wlm_event_monitor()
		except ParseError:
			self._restore_state()
			self._parse_nonwlm_event_monitor()
		else:
			self._forget_state()

	def _parse_create_function_statement(self):
		"""Parses a CREATE FUNCTION statement"""
		# CREATE FUNCTION already matched
		self._parse_function_name()
		# Parse parameter list
		self._expect('(', prespace=False)
		if not self._match(')'):
			while True:
				self._save_state()
				try:
					self._expect(IDENTIFIER)
					self._parse_datatype()
				except ParseError:
					self._restore_state()
					self._parse_datatype()
				else:
					self._forget_state()
				self._match_sequence(['AS', 'LOCATOR'])
				if not self._match(','):
					break
			self._expect(')')
		self._indent()
		# Parse function options (which can appear in any order)
		valid = set([
			'ALLOW',
			'CALLED',
			'CARDINALITY',
			'CONTAINS',
			'DBINFO',
			'DETERMINISTIC',
			'DISALLOW',
			'EXTERNAL',
			'FENCED',
			'FINAL',
			'INHERIT',
			'LANGUAGE',
			'MODIFIES',
			'NO',
			'NOT',
			'NULL',
			'PARAMETER',
			'READS',
			'RETURNS',
			'SCRATCHPAD',
			'SPECIFIC',
			'STATIC',
			'THREADSAFE',
			'TRANSFORM',
			'VARIANT',
		])
		while True:
			# Ambiguity: INHERIT SPECIAL REGISTERS (which appears in the
			# variable order options) and INHERIT ISOLATION LEVEL (which must
			# appear after the variable order options). See below.
			self._save_state()
			try:
				t = self._match_one_of(valid)
				if t:
					t = t[1]
					# Note that matches aren't removed from valid, because it's
					# simply too complex to figure out what option disallows
					# other options in many cases
				else:
					# break would skip the except and else blocks
					raise ParseBacktrack()
				if t == 'ALLOW':
					self._expect('PARALLEL')
					if self._match_sequence(['EXECUTE', 'ON', 'ALL']):
						self._match_sequence(['DATABASE', 'PARTITIONS'])
						self._expect_sequence(['RESULT', 'TABLE', 'DISTRIBUTED'])
				elif t == 'CALLED':
					self._expect_sequence(['ON', 'NULL', 'INPUT'])
				elif t == 'CARDINALITY':
					self._expect(NUMBER)
				elif t == 'CONTAINS':
					self._expect('SQL')
				elif t == 'DBINFO':
					pass
				elif t == 'DETERMINISTIC':
					pass
				elif t == 'DISALLOW':
					self._expect('PARALLEL')
				elif t == 'EXTERNAL':
					if self._match('NAME'):
						self._expect_one_of([STRING, IDENTIFIER])
					else:
						self._expect('ACTION')
				elif t == 'FENCED':
					pass
				elif t == 'FINAL':
					self._expect('CALL')
				elif t == 'INHERIT':
					# Try and parse INHERIT SPECIAL REGISTERS first
					if not self._match('SPECIAL'):
						raise ParseBacktrack()
					self._expect('REGISTERS')
				elif t == 'LANGUAGE':
					self._expect_one_of(['SQL', 'C', 'JAVA', 'CLR', 'OLE'])
				elif t == 'MODIFIES':
					self._expect_sequence(['SQL', 'DATA'])
				elif t == 'NO':
					t = self._expect_one_of(['DBINFO', 'EXTERNAL', 'FINAL', 'SCRATCHPAD'])[1]
					if t == 'EXTERNAL':
						self._expect('ACTION')
					elif t == 'FINAL':
						self._expect('CALL')
				elif t == 'NOT':
					self._expect_one_of(['DETERMINISTIC', 'FENCED', 'THREADSAFE', 'VARIANT'])
				elif t == 'NULL':
					self._expect('CALL')
				elif t == 'PARAMETER':
					if self._match('CCSID'):
						self._expect_one_of(['ASCII', 'UNICODE'])
					else:
						self._expect('STYLE')
						self._expect_one_of(['DB2GENERAL', 'DB2GENERL', 'JAVA', 'SQL', 'DB2SQL'])
				elif t == 'READS':
					self._expect_sequence(['SQL', 'DATA'])
				elif t == 'RETURNS':
					if self._match('NULL'):
						self._expect_sequence(['ON', 'NULL', 'INPUT'])
					elif self._match_one_of(['ROW', 'TABLE']):
						self._expect('(')
						while True:
							self._expect(IDENTIFIER)
							self._parse_datatype()
							self._match_sequence(['AS', 'LOCATOR'])
							if not self._match(','):
								break
						self._expect(')')
					else:
						self._parse_datatype()
						if self._match_sequence(['CAST', 'FROM']):
							self._parse_datatype()
						self._match_sequence(['AS', 'LOCATOR'])
				elif t == 'SCRATCHPAD':
					self._expect(NUMBER)
				elif t == 'SPECIFIC':
					self._expect(IDENTIFIER)
				elif t == 'STATIC':
					self._expect('DISPATCH')
				elif t == 'THREADSAFE':
					pass
				elif t == 'TRANSFORM':
					self._expect_sequence(['GROUP', IDENTIFIER])
				elif t == 'VARIANT':
					pass
				self._newline()
			except ParseBacktrack:
				# NOTE: This block only gets called for ParseBacktrack errors.
				# Other parse errors will propogate outward. If the above has
				# failed, rewind, and drop out of the loop so we can try
				# INHERIT ISOLATION LEVEL (and PREDICATES)
				self._restore_state()
				break
			else:
				self._forget_state()
		# Parse optional PREDICATES clause
		if self._match('PREDICATES'):
			self._parse_function_predicates_clause()
			self._newline()
		if self._match('INHERIT'):
			self._expect_sequence(['ISOLATION', 'LEVEL'])
			self._expect_one_of(['WITH', 'WITHOUT'])
			self._expect_sequence(['LOCK', 'REQUEST'])
		# Parse the function body
		self._outdent()
		if self._expect_one_of(['BEGIN', 'RETURN'])[1] == 'BEGIN':
			self._parse_dynamic_compound_statement()
		else:
			self._indent()
			self._parse_return_statement()
			self._outdent()

	def _parse_create_function_mapping_statement(self):
		"""Parses a CREATE FUNCTION MAPPING statement"""
		# CREATE FUNCTION MAPPING already matched
		if not self._match('FOR'):
			self._expect_sequence([IDENTIFIER, 'FOR'])
		if not self._match('SPECIFIC'):
			self._parse_function_name()
			self._expect('(', prespace=False)
			self._parse_datatype_list()
			self._expect(')')
		else:
			self._parse_function_name()
		self._expect('SERVER')
		self._parse_remote_server()
		if self._match('OPTIONS'):
			self._parse_federated_options()
		self._match_sequence(['WITH', 'INFIX'])

	def _parse_create_histogram_template_statement(self):
		"""Parses a CREATE HISTOGRAM TEMPLATE statement"""
		# CREATE HISTOGRAM TEMPLATE already matched
		self._expect_sequence([IDENTIFIER, 'HIGH', 'BIN', 'VALUE', NUMBER])

	def _parse_create_index_statement(self, unique):
		"""Parses a CREATE INDEX statement"""
		# CREATE [UNIQUE] INDEX already matched
		self._parse_index_name()
		self._indent()
		self._expect('ON')
		self._parse_table_name()
		self._expect('(')
		self._indent()
		while True:
			self._expect(IDENTIFIER)
			self._match_one_of(['ASC', 'DESC'])
			if not self._match(','):
				break
			else:
				self._newline()
		self._outdent()
		self._expect(')')
		self._match_sequence(['IN', IDENTIFIER])
		valid = set([
			'SPECIFICATION',
			'INCLUDE',
			'CLUSTER',
			'PCTFREE',
			'LEVEL2',
			'MINPCTUSED',
			'ALLOW',
			'DISALLOW',
			'PAGE',
			'COLLECT'
		])
		while valid:
			t = self._match_one_of(valid)
			if t:
				self._newline(-1)
				t = t[1]
				valid.remove(t)
			else:
				break
			if t == 'SPECIFICATION':
				self._expect('ONLY')
			elif t == 'INCLUDE':
				self._expect('(')
				self._indent()
				self._parse_ident_list(newlines=True)
				self._outdent()
				self._expect(')')
			elif t == 'CLUSTER':
				pass
			elif t == 'PCTFREE' or t == 'MINPCTUSED':
				self._expect(NUMBER)
			elif t == 'LEVEL2':
				self._expect_sequence(['PCTFREE', NUMBER])
			elif t == 'ALLOW' or t == 'DISALLOW':
				valid.discard('ALLOW')
				valid.discard('DISALLOW')
				self._expect_sequence(['REVERSE', 'SCANS'])
			elif t == 'PAGE':
				self._expect('SPLIT')
				self._expect_one_of(['SYMMETRIC', 'HIGH', 'LOW'])
			elif t == 'COLLECT':
				self._match('SAMPLED')
				self._match('DETAILED')
				self._expect('STATISTICS')

	def _parse_create_nickname_statement(self):
		"""Parses a CREATE NICKNAME statement"""
		# CREATE NICKNAME already matched
		self._parse_nickname_name()
		if self._match('FOR'):
			self._parse_remote_object_name()
		else:
			self._parse_table_definition(aligntypes=True, alignoptions=True, federated=True)
			self._expect_sequence(['FOR', 'SERVER', IDENTIFIER])
		if self._match('OPTIONS'):
			self._parse_federated_options()

	def _parse_create_procedure_statement(self):
		"""Parses a CREATE PROCEDURE statement"""
		# CREATE PROCEDURE already matched
		self._parse_procedure_name()
		if self._match('SOURCE'):
			self._parse_source_object_name()
			if self._match('(', prespace=False):
				self._expect(')')
			elif self._match('NUMBER'):
				self._expect_sequence(['OF', 'PARAMETERS', NUMBER])
			if self._match('UNIQUE'):
				self._expect(STRING)
			self.expect_sequence(['FOR', 'SERVER', IDENTIFIER])
		elif self._match('(', prespace=False):
			if not self._match(')'):
				while True:
					self._match_one_of(['IN', 'OUT', 'INOUT'])
					self._save_state()
					try:
						self._expect(IDENTIFIER)
						self._parse_datatype()
					except ParseError:
						self._restore_state()
						self._parse_datatype()
					else:
						self._forget_state()
					if not self._match(','):
						break
				self._expect(')')
		self._indent()
		# Parse procedure options (which can appear in any order)
		valid = set([
			'CALLED',
			'CONTAINS',
			'DBINFO',
			'DETERMINISTIC',
			'DYNAMIC',
			'EXTERNAL',
			'FENCED',
			'INHERIT',
			'LANGUAGE',
			'MODIFIES',
			'NEW',
			'NO',
			'NOT',
			'NOT',
			'NULL',
			'OLD',
			'PARAMETER',
			'PROGRAM',
			'READS',
			'RESULT',
			'SPECIFIC',
			'THREADSAFE',
			'WITH',
		])
		while True:
			t = self._match_one_of(valid)
			if t:
				t = t[1]
				# Note that matches aren't removed from valid, because it's
				# simply too complex to figure out what option disallows other
				# options in many cases
			else:
				break
			if t == 'CALLED':
				self._expect_sequence(['ON', 'NULL', 'INPUT'])
			elif t == 'CONTAINS':
				self._expect('SQL')
			elif t == 'DBINFO':
				pass
			elif t == 'DETERMINISTIC':
				pass
			elif t == 'DYNAMIC':
				self._expect_sequence(['RESULT', 'SETS', NUMBER])
			elif t == 'EXTERNAL':
				if self._match('NAME'):
					self._expect_one_of([STRING, IDENTIFIER])
				else:
					self._expect('ACTION')
			elif t == 'FENCED':
				pass
			elif t == 'INHERIT':
				self._expect_sequence(['SPECIAL', 'REGISTERS'])
			elif t == 'LANGUAGE':
				self._expect_one_of(['SQL', 'C', 'JAVA', 'COBOL', 'CLR', 'OLE'])
			elif t == 'MODIFIES':
				self._expect_sequence(['SQL', 'DATA'])
			elif t in ['NEW', 'OLD']:
				self._expect_sequence(['SAVEPOINT', 'LEVEL'])
			elif t == 'NO':
				if self._match('EXTERNAL'):
					self._expect('ACTION')
				else:
					self._expect('DBINFO')
			elif t == 'NOT':
				self._expect_one_of(['DETERMINISTIC', 'FENCED', 'THREADSAFE'])
			elif t == 'NULL':
				self._expect('CALL')
			elif t == 'PARAMETER':
				if self._match('CCSID'):
					self._expect_one_of(['ASCII', 'UNICODE'])
				else:
					self._expect('STYLE')
					p = self._expect_one_of([
						'DB2GENERAL',
						'DB2GENERL',
						'DB2DARI',
						'DB2SQL',
						'GENERAL',
						'SIMPLE',
						'JAVA',
						'SQL'
					])[1]
					if p == 'GENERAL':
						self._match_sequence(['WITH', 'NULLS'])
					elif p == 'SIMPLE':
						self._expect('CALL')
						self._match_sequence(['WITH', 'NULLS'])
			elif t == 'PROGRAM':
				self._expect('TYPE')
				self._expect_one_of(['SUB', 'MAIN'])
			elif t == 'READS':
				self._expect_sequence(['SQL', 'DATA'])
			elif t == 'RESULT':
				self._expect_sequence(['SETS', NUMBER])
			elif t == 'SPECIFIC':
				self._expect(IDENTIFIER)
			elif t == 'THREADSAFE':
				pass
			elif t == 'WITH':
				self._expect_sequence(['RETURN', 'TO'])
				self._expect_one_of(['CALLER', 'CLIENT'])
				self._expect('ALL')
			self._newline()
		self._outdent()
		self._expect('BEGIN')
		self._parse_procedure_compound_statement()

	def _parse_create_role_statement(self):
		"""Parses a CREATE ROLE statement"""
		# CREATE ROLE already matched
		self._expect(IDENTIFIER)

	def _parse_create_schema_statement(self):
		"""Parses a CREATE SCHEMA statement"""
		# CREATE SCHEMA already matched
		if self._match('AUTHORIZATION'):
			self._expect(IDENTIFIER)
		else:
			self._expect(IDENTIFIER)
			if self._match('AUTHORIZATION'):
				self._expect(IDENTIFIER)
		# Parse CREATE/COMMENT/GRANT statements
		while True:
			if self._match('CREATE'):
				if self._match('TABLE'):
					self._parse_create_table_statement()
				elif self._match('VIEW'):
					self._parse_create_view_statement()
				elif self._match('INDEX'):
					self._parse_create_index_statement(unique=False)
				elif self._match_sequence(['UNIQUE', 'INDEX']):
					self._parse_create_index_statement(unique=True)
				else:
					self._expected_one_of(['TABLE', 'VIEW', 'INDEX', 'UNIQUE'])
			elif self._match_sequence(['COMMENT', 'ON']):
				self._parse_comment_statement()
			elif self._match('GRANT'):
				self._parse_grant_statement()
			else:
				break

	def _parse_create_security_label_component_statement(self):
		"""Parses a CREATE SECURITY LABEL COMPONENT statement"""
		# CREATE SECURITY LABEL COMPONENT already matched
		self._expect(IDENTIFIER)
		if self._match('ARRAY'):
			self._expect('[', prespace=False)
			while True:
				self._expect(STRING)
				if not self._match(','):
					break
			self._expect(']')
		elif self._match('SET'):
			self._expect('{', prespace=False)
			while True:
				self._expect(STRING)
				if not self._match(','):
					break
			self._expect('}')
		elif self._match('TREE'):
			self._expect_sequence(['(', STRING, 'ROOT'], prespace=False)
			while self._match(','):
				self._expect_sequence([STRING, 'UNDER', STRING])
			self._expect(')')

	def _parse_create_security_label_statement(self):
		"""Parses a CREATE SECURITY LABEL statement"""
		# CREATE SECURITY LABEL already matched
		self._parse_security_label_name()
		while True:
			self._expect_sequence(['COMPONENT', IDENTIFIER, STRING])
			while self._match_sequence([',', STRING]):
				pass
			if not self._match(','):
				break

	def _parse_create_security_policy_statement(self):
		"""Parses a CREATE SECURITY POLICY statement"""
		# CREATE SECURITY POLICY already matched
		self._expect_sequence([IDENTIFIER, 'COMPONENTS'])
		while True:
			self._expect(IDENTIFIER)
			if not self._match(','):
				break
		self._expect_sequence(['WITH', 'DB2LBACRULES'])
		if self._match_one_of(['OVERRIDE', 'RESTRICT']):
			self._expect_sequence(['NOT', 'AUTHORIZED', 'WRITE', 'SECURITY', 'LABEL'])

	def _parse_create_sequence_statement(self):
		"""Parses a CREATE SEQUENCE statement"""
		# CREATE SEQUENCE already matched
		self._parse_sequence_name()
		if self._match('AS'):
			self._parse_datatype()
		self._parse_identity_options()

	def _parse_create_service_class_statement(self):
		"""Parses a CREATE SERVICE CLASS statement"""
		# CREATE SERVICE CLASS already matched
		self._expect(IDENTIFIER)
		if self._match('UNDER'):
			self._expect(IDENTIFIER)
		if self._match_sequence(['AGENT', 'PRIORITY']):
			self._expect_one_of(['DEFAULT', NUMBER])
		if self._match_sequence(['PREFETCH', 'PRIORITY']):
			self._expect_one_of(['DEFAULT', 'HIGH', 'MEDIUM', 'LOW'])
		if self._match_sequence(['OUTBOUND', 'CORRELATOR']):
			self._expect_one_of(['NONE', STRING])
		if self._match_sequence(['COLLECT', 'ACTIVITY', 'DATA']):
			self._parse_collect_activity_data_clause(alter=True)
		if self._match_sequence(['COLLECT', 'AGGREGATE', 'ACTIVITY', 'DATA']):
			self._expect_one_of(['NONE', 'BASE', 'EXTENDED'])
		if self._match_sequence(['COLLECT', 'AGGREGATE', 'REQUEST', 'DATA']):
			self._expect_one_of(['NONE', 'BASE'])
		self._parse_histogram_template_clause()
		self._match_one_of(['ENABLE', 'DISABLE'])
	
	def _parse_create_server_statement(self):
		"""Parses a CREATE SERVER statement"""
		# CREATE SERVER already matched
		self._expect(IDENTIFIER)
		if self._match('TYPE'):
			self._expect(IDENTIFIER)
		if self._match('VERSION'):
			self._parse_server_version()
		if self._match('WRAPPER'):
			self._expect(IDENTIFIER)
		if self._match('AUTHORIZATION'):
			self._expect_sequence([IDENTIFIER, 'PASSWORD', IDENTIFIER])
		if self._match('OPTIONS'):
			self._parse_federated_options()

	def _parse_create_table_statement(self):
		"""Parses a CREATE TABLE statement"""
		# CREATE TABLE already matched
		self._parse_table_name()
		if self._match('LIKE'):
			self._parse_relation_name()
			self._parse_copy_options()
		else:
			# Ambiguity: Open parentheses could indicate an optional field list
			# preceding a materialized query or staging table definition
			reraise = False
			self._save_state()
			try:
				# Try parsing CREATE TABLE ... AS first
				if self._match('('):
					self._indent()
					self._parse_ident_list(newlines=True)
					self._outdent()
					self._expect(')')
				if self._match('AS'):
					reraise = True
					self._expect('(')
					self._indent()
					self._parse_full_select()
					self._outdent()
					self._expect(')')
					self._parse_refreshable_table_options()
				elif self._match('FOR'):
					reraise = True
					self._parse_relation_name()
					self._expected_sequence(['PROPAGATE', 'IMMEDIATE'])
				else:
					self._expected_one_of(['AS', 'FOR'])
			except ParseError:
				# If that fails, rewind and parse other CREATE TABLE forms
				self._restore_state()
				if reraise: raise
				self._parse_table_definition(aligntypes=True, alignoptions=True, federated=False)
			else:
				self._forget_state()
		# Parse table option suffixes. Not all of these are valid with
		# particular table definitions, but it's too difficult to sort out
		# which are valid for what we've parsed so far
		valid = set([
			'ORGANIZE',
			'DATA',
			'IN',
			'INDEX',
			'LONG',
			'DISTRIBUTE',
			'PARTITION',
			'COMPRESS',
			'VALUE',
			'WITH',
			'NOT',
			'CCSID',
			'SECURITY',
			'OPTIONS',
		])
		while valid:
			t = self._match_one_of(valid)
			if t:
				t = t[1]
				valid.remove(t)
			else:
				break
			if t == 'ORGANIZE':
				self._expect('BY')
				if self._match_sequence(['KEY', 'SEQUENCE']):
					self._expect('(')
					while True:
						self._expect(IDENTIFIER)
						if self._match('STARTING'):
							self._match('FROM')
							self._expect(NUMBER)
						self._expect('ENDING')
						self._match('AT')
						self._expect(NUMBER)
						if not self._match(','):
							break
					self._expect(')')
					self._expect_one_of(['ALLOW', 'DISALLOW'])
					self._expect('OVERFLOW')
					if self._match('PCTFREE'):
						self._expect(INTEGER)
				else:
					self._match('DIMENSIONS')
					self._expect('(')
					while True:
						if self._match('('):
							self._parse_ident_list()
							self._expect(')')
						else:
							self._expect(IDENTIFIER)
						if not self._match(','):
							break
			elif t == 'DATA':
				self._expect('CAPTURE')
				self._expect_one_of(['CHANGES', 'NONE'])
			elif t == 'IN':
				self._parse_ident_list()
				if self._match('NO'):
					self._expect('CYCLE')
				else:
					self._match('CYCLE')
			elif t == 'LONG':
				self._expect('IN')
				self._parse_ident_list()
			elif t == 'INDEX':
				self._expect_sequence(['IN', IDENTIFIER])
			elif t == 'DISTRIBUTE':
				self._expect('BY')
				if self._match('REPLICATION'):
					pass
				else:
					self._match('HASH')
					self._expect('(', prespace=False)
					self._parse_ident_list()
					self._expect(')')
			elif t == 'PARTITION':
				self._expect('BY')
				self._match('RANGE')
				self._expect('(')
				while True:
					self._expect(IDENTIFIER)
					if self._match('NULLS'):
						self._expect_one_of(['FIRST', 'LAST'])
					if not self._match(','):
						break
				self._expect_sequence([')', '('])
				while True:
					if self._match('PARTITION'):
						self._expect(IDENTIFIER)
					self._parse_partition_boundary()
					if self._match('IN'):
						self._expect(IDENTIFIER)
					elif self._match('EVERY'):
						if self._match('('):
							self._expect(NUMBER)
							self._parse_duration_label()
							self._expect(')')
						else:
							self._expect(NUMBER)
							self._parse_duration_label()
					if not self._match(','):
						break
			elif t == 'COMPRESS':
				self._expect_one_of(['NO', 'YES'])
			elif t == 'VALUE':
				self._expect('COMPRESSION')
			elif t == 'WITH':
				self._expect_sequence(['RESTRICT', 'ON', 'DROP'])
			elif t == 'NOT':
				self._expect_sequence(['LOGGED', 'INITIALLY'])
			elif t == 'CCSID':
				self._expect_one_of(['ASCII', 'UNICODE'])
			elif t == 'SECURITY':
				self._expect_sequence(['POLICY', IDENTIFIER])
			elif t == 'OPTIONS':
				self._parse_federated_options(alter=False)

	def _parse_create_tablespace_statement(self, tbspacetype='REGULAR'):
		"""Parses a CREATE TABLESPACE statement"""
		# CREATE TABLESPACE already matched
		self._expect(IDENTIFIER)
		if self._match('IN'):
			if self._match('DATABASE'):
				self._expect_sequence(['PARTITION', 'GROUP'])
			elif self._match('NODEGROUP'):
				pass
			self._expect(IDENTIFIER)
		if self._match('PAGESIZE'):
			self._expect(NUMBER)
			self._match('K')
		if self._match('MANAGED'):
			self._expect('BY')
			if self._match('AUTOMATIC'):
				self._expect('STORAGE')
				self._parse_tablespace_size_attributes()
			elif self._match('DATABASE'):
				self._expect('USING')
				while True:
					self._parse_database_container_clause()
					if self._match('ON'):
						self._parse_db_partitions_clause(size=False)
					if not self._match('USING'):
						break
				self._parse_tablespace_size_attributes()
			elif self._match('SYSTEM'):
				self._expect('USING')
				while True:
					self._parse_system_container_clause()
					if self._match('ON'):
						self._parse_db_partitions_clause(size=False)
					if not self._match('USING'):
						break
			else:
				self._expected_one_of(['AUTOMATIC', 'DATABASE', 'SYSTEM'])
		if self._match('EXTENTSIZE'):
			self._expect(NUMBER)
			self._match_one_of(['K', 'M'])
		if self._match('PREFETCHSIZE'):
			self._expect(NUMBER)
			self._match_one_of(['K', 'M', 'G'])
		if self._match('BUFFERPOOL'):
			self._expect(IDENTIFIER)
		if self._match('OVERHEAD'):
			self._expect(NUMBER)
		if self._match('NO'):
			self._expect_sequence(['FILE', 'SYSTEM', 'CACHING'])
		elif self._match('FILE'):
			self._expect_sequence(['SYSTEM', 'CACHING'])
		if self._match('TRANSFERRATE'):
			self._expect(NUMBER)
		if self._match('DROPPED'):
			self._expect_sequence(['TABLE', 'RECOVERY'])
			self._expect_one_of(['ON', 'OFF'])
	
	def _parse_create_threshold_statement(self):
		"""Parses a CREATE THRESHOLD statement"""
		# CREATE THRESHOLD already matched
		self._expect_sequence([IDENTIFIER, 'FOR'])
		if self._match('SERVICE'):
			self._expect_sequence(['CLASS', IDENTIFIER])
			if self._match('UNDER'):
				self._expect(IDENTIFIER)
		elif self._match('WORKLOAD'):
			self._expect(IDENTIFIER)
		elif not self._match('DATABASE'):
			self._expected_one_of(['SERVICE', 'WORKLOAD', 'DATABASE'])
		self._expect_sequence(['ACTIVITIES', 'ENFORCEMENT'])
		if self._match('DATABASE'):
			self._match('PARTITION')
		elif self._match('WORKLOAD'):
			self._expect('OCCURRENCE')
		else:
			self._expected_one_of(['DATABASE', 'WORKLOAD'])
		self._match_one_of(['ENABLE', 'DISABLE'])
		self._expect('WHEN')
		self._parse_threshold_predicate()
		self._parse_threshold_exceeded_actions()

	def _parse_create_trigger_statement(self):
		"""Parses a CREATE TRIGGER statement"""
		# CREATE TRIGGER already matched
		self._parse_trigger_name()
		self._indent()
		if self._match_sequence(['NO', 'CASCADE', 'BEFORE']):
			pass
		elif self._match_sequence(['INSTEAD', 'OF']):
			pass
		elif self._match('AFTER'):
			pass
		else:
			self._expected_one_of(['AFTER', 'NO', 'INSTEAD'])
		if self._match('UPDATE'):
			if self._match('OF'):
				self._indent()
				self._parse_ident_list(newlines=True)
				self._outdent()
		else:
			self._expect_one_of(['INSERT', 'DELETE', 'UPDATE'])
		self._expect('ON')
		self._parse_table_name()
		if self._match('REFERENCING'):
			self._newline(-1)
			valid = ['OLD', 'NEW', 'OLD_TABLE', 'NEW_TABLE']
			while valid:
				if len(valid) == 4:
					t = self._expect_one_of(valid)
				else:
					t = self._match_one_of(valid)
				if t:
					t = t[1]
					valid.remove(t)
				else:
					break
				if t in ('OLD', 'NEW'):
					if 'OLD_TABLE' in valid: valid.remove('OLD_TABLE')
					if 'NEW_TABLE' in valid: valid.remove('NEW_TABLE')
				elif t in ('OLD_TABLE', 'NEW_TABLE'):
					if 'OLD' in valid: valid.remove('OLD')
					if 'NEW' in valid: valid.remove('NEW')
				self._match('AS')
				self._expect(IDENTIFIER)
		self._newline()
		self._expect_sequence(['FOR', 'EACH'])
		self._expect_one_of(['ROW', 'STATEMENT'])
		# XXX MODE DB2SQL appears to be deprecated syntax
		if self._match('MODE'):
			self._newline(-1)
			self._expect('DB2SQL')
		if self._match('WHEN'):
			self._expect('(')
			self._indent()
			self._parse_search_condition()
			self._outdent()
			self._expect(')')
		try:
			label = self._expect(LABEL)[1]
			self._outdent(-1)
			self._newline()
		except ParseError:
			label = None
		if self._match('BEGIN'):
			if not label: self._outdent(-1)
			self._parse_dynamic_compound_statement(label=label)
		else:
			self._parse_routine_statement()
			if not label: self._outdent()

	def _parse_create_trusted_context_statement(self):
		"""Parses a CREATE TRUSTED CONTEXT statement"""
		# CREATE TRUSTED CONTEXT already matched
		self._expect_sequence([IDENTIFIER, 'BASED', 'UPON', 'CONNECTION', 'USING'])
		valid = set([
			'SYSTEM',
			'ATTRIBUTES',
			'NO',
			'DEFAULT',
			'DISABLE',
			'ENABLE',
			'WITH',
		])
		while valid:
			t = self._match_one_of(valid)
			if t:
				t = t[1]
				valid.remove(t)
			else:
				break
			if t == 'SYSTEM':
				self._expect_sequence(['AUTHID', IDENTIFIER])
			elif t == 'ATTRIBUTES':
				self._expect('(')
				if self._match('ADDRESS'):
					self._expect(STRING)
					if self._match('WITH'):
						self._expect_sequence(['ENCRYPTION', STRING])
				elif self._match('ENCRYPTION'):
					self._expect(STRING)
				if not self._match(','):
					break
				self._expect(')')
			elif t == 'NO':
				valid.remove('DEFAULT')
				self._expect_sequence(['DEFAULT', 'ROLE'])
			elif t == 'DEFAULT':
				valid.remove('NO')
				self._expect_sequence(['ROLE', IDENTIFIER])
			elif t == 'DISABLE':
				valid.remove('ENABLE')
			elif t == 'ENABLE':
				valid.remove('DISABLE')
			elif t == 'WITH':
				self._expect_sequence(['USE', 'FOR'])
				if not self._match('PUBLIC'):
					self._expect(IDENTIFIER)
					if self._match('ROLE'):
						self._expect(IDENTIFIER)
				if self._match_one_of(['WITH', 'WITHOUT']):
					self._expect('AUTHENTICATION')

	def _parse_create_type_statement(self):
		"""Parses a CREATE DISTINCT TYPE statement"""
		# CREATE DISTINCT TYPE already matched
		self._parse_type_name()
		self._expect('AS')
		self._parse_datatype()
		if self._match('ARRAY'):
			self._expect('[', prespace=False)
			self._match(NUMBER)
			self._expect(']')
		else:
			self._match_sequence(['WITH', 'COMPARISONS'])

	def _parse_create_type_mapping_statement(self):
		"""Parses a CREATE TYPE MAPPING statement"""
		# CREATE TYPE MAPPING already matched
		self._match(IDENTIFIER)
		valid = set(['FROM', 'TO'])
		t = self._expect_one_of(valid)[1]
		valid.remove(t)
		self._match_sequence(['LOCAL', 'TYPE'])
		self._parse_datatype()
		self._expect_one_of(valid)
		self._parse_remote_server()
		self._match('REMOTE')
		self._expect('TYPE')
		self._parse_type_name()
		if self._match('FOR'):
			self._expect_sequence(['BIT', 'DATA'])
		elif self._match('(', prespace=False):
			if self._match('['):
				self._expect_sequence([NUMBER, '..', NUMBER], interspace=False)
				self._expect(']')
			else:
				self._expect(NUMBER)
			if self._match(','):
				if self._match('['):
					self._expect_sequence([NUMBER, '..', NUMBER], interspace=False)
					self._expect(']')
				else:
					self._expect(NUMBER)
			self._expect(')')
			if self._match('P'):
				self._expect_one_of(['=', '>', '<', '>=', '<=', '<>'])
				self._expect('S')

	def _parse_create_user_mapping_statement(self):
		"""Parses a CREATE USER MAPPING statement"""
		# CREATE USER MAPPING already matched
		self._expect('FOR')
		self._expect_one_of(['USER', IDENTIFIER])
		self._expect_sequence(['SERVER', IDENTIFIER])
		self._expect('OPTIONS')
		self._parse_federated_options(alter=False)

	def _parse_create_variable_statement(self):
		"""Parses a CREATE VARIABLE statement"""
		# CREATE VARIABLE already matched
		self._parse_variable_name()
		self._parse_datatype()
		if self._match('DEFAULT'):
			self._parse_expression()

	def _parse_create_view_statement(self):
		"""Parses a CREATE VIEW statement"""
		# CREATE VIEW already matched
		self._parse_view_name()
		if self._match('('):
			self._indent()
			self._parse_ident_list(newlines=True)
			self._outdent()
			self._expect(')')
		self._expect('AS')
		self._newline()
		self._parse_query()
		valid = set(['CASCADED', 'LOCAL', 'CHECK', 'ROW', 'NO'])
		while valid:
			if not self._match('WITH'):
				break
			t = self._expect_one_of(valid)[1]
			valid.remove(t)
			if t in ('CASCADED', 'LOCAL', 'CHECK'):
				valid.discard('CASCADED')
				valid.discard('LOCAL')
				valid.discard('CHECK')
				if t != 'CHECK':
					self._expect('CHECK')
				self._expect('OPTION')
			elif t == 'NO':
				valid.remove('ROW')
				self._expect_sequence(['ROW', 'MOVEMENT'])
			elif t == 'ROW':
				valid.remove('NO')
				self._expect('MOVEMENT')

	def _parse_create_work_action_set_statement(self):
		"""Parses a CREATE WORK ACTION SET statement"""
		# CREATE WORK ACTION SET already matched
		self._expect(IDENTIFIER)
		self._expect('FOR')
		if self._match('SERVICE'):
			self._expect_sequence(['CLASS', IDENTIFIER])
		elif self._match('DATABASE'):
			pass
		else:
			self._expected_one_of(['SERVICE', 'DATABASE'])
		self._expect_sequence(['USING', 'WORK', 'CLASS', 'SET', IDENTIFIER])
		if self._match('('):
			self._indent()
			while True:
				self._expect_sequence(['WORK', 'ACTION', IDENTIFIER, 'ON', 'WORK', 'CLASS', IDENTIFIER])
				self._parse_action_types_clause()
				self._parse_histogram_template_clause()
				self._match_one_of(['ENABLE', 'DISABLE'])
				if self._match(','):
					self._newline()
				else:
					break
			self._outdent()
			self._expect(')')
		self._match_one_of(['ENABLE', 'DISABLE'])

	def _parse_create_work_class_set_statement(self):
		"""Parses a CREATE WORK CLASS SET statement"""
		# CREATE WORK CLASS SET already matched
		self._expect(IDENTIFIER)
		if self._match('('):
			self._indent()
			while True:
				self._match_sequence(['WORK', 'CLASS'])
				self._expect(IDENTIFIER)
				self._parse_work_attributes()
				if self._match('POSITION'):
					self._parse_position_clause()
				if self._match(','):
					self._newline()
				else:
					break
			self._outdent()
			self._expect(')')

	def _parse_create_workload_statement(self):
		"""Parses a CREATE WORKLOAD statement"""
		# CREATE WORKLOAD statement
		self._expect(IDENTIFIER)
		first = True
		while True:
			# Repeatedly try and match connection attributes. Only raise a
			# parse error if the first match fails
			try:
				self._parse_connection_attributes()
			except ParseError, e:
				if first:
					raise e
			else:
				first = False
		self._match_one_of(['ENABLE', 'DISABLE'])
		if self._match_one_of(['ALLOW', 'DISALLOW']):
			self._expect_sequence(['DB', 'ACCESS'])
		if self._match_sequence(['SERVICE', 'CLASS']):
			if not self._match('SYSDEFAULTUSERCLASS'):
				self._expect(IDENTIFIER)
				self._match_sequence(['UNDER', IDENTIFIER])
		if self._match('POSITION'):
			self._parse_position_clause()
		if self._match_sequence(['COLLECT', 'ACTIVITY', 'DATA']):
			self._parse_collect_activity_data_clause(alter=True)

	def _parse_create_wrapper_statement(self):
		"""Parses a CREATE WRAPPER statement"""
		# CREATE WRAPPER already matched
		self._expect(IDENTIFIER)
		if self._match('LIBRARY'):
			self._expect(STRING)
		if self._match('OPTIONS'):
			self._parse_federated_options(alter=False)

	def _parse_declare_cursor_statement(self):
		"""Parses a top-level DECLARE CURSOR statement"""
		# DECLARE already matched
		self._expect_sequence([IDENTIFIER, 'CURSOR'])
		self._match_sequence(['WITH', 'HOLD'])
		self._expect('FOR')
		self._newline()
		self._parse_select_statement()

	def _parse_declare_global_temporary_table_statement(self):
		"""Parses a DECLARE GLOBAL TEMPORARY TABLE statement"""
		# DECLARE GLOBAL TEMPORARY TABLE already matched
		self._parse_table_name()
		if self._match('LIKE'):
			self._parse_table_name()
			self._parse_copy_options()
		elif self._match('AS'):
			self._parse_full_select()
			self._expect_sequence(['DEFINITION', 'ONLY'])
			self._parse_copy_options()
		else:
			self._parse_table_definition(aligntypes=True, alignoptions=False, federated=False)
		valid = set(['ON', 'NOT', 'WITH', 'IN', 'PARTITIONING'])
		while valid:
			t = self._match_one_of(valid)
			if t:
				t = t[1]
				valid.remove(t)
			else:
				break
			if t == 'ON':
				self._expect('COMMIT')
				self._expect_one_of(['DELETE', 'PRESERVE'])
				self._expect('ROWS')
			elif t == 'NOT':
				self._expect('LOGGED')
				if self._match('ON'):
					self._expect('ROLLBACK')
					self._expect_one_of(['DELETE', 'PRESERVE'])
					self._expect('ROWS')
			elif t == 'WITH':
				self._expect('REPLACE')
			elif t == 'IN':
				self._expect(IDENTIFIER)
			elif t == 'PARTITIONING':
				self._expect('KEY')
				self._expect('(')
				self._parse_ident_list()
				self._expect(')')
				self._match_sequence(['USING', 'HASHING'])

	def _parse_delete_statement(self):
		"""Parses a DELETE statement"""
		# DELETE already matched
		self._expect('FROM')
		if self._match('('):
			self._indent()
			self._parse_full_select()
			self._outdent()
			self._expect(')')
		else:
			self._parse_subschema_name()
		# Ambiguity: INCLUDE is an identifier and hence can look like a table
		# correlation name
		reraise = False
		self._save_state()
		try:
			# Try and parse a mandatory table correlation followed by a
			# mandatory INCLUDE
			self._parse_table_correlation(optional=False)
			self._newline()
			self._expect('INCLUDE')
			reraise = True
			self._expect('(')
			self._indent()
			self._parse_ident_type_list(newlines=True)
			self._outdent()
			self._expect(')')
			# XXX Is SET required for an assignment clause? The syntax diagram
			# doesn't think so...
			if self._match('SET'):
				self._parse_assignment_clause(allowdefault=False)
		except ParseError:
			# If that fails, rewind and parse an optional INCLUDE or an
			# optional table correlation
			self._restore_state()
			if reraise: raise
			if self._match('INCLUDE'):
				self._newline(-1)
				self._expect('(')
				self._indent()
				self._parse_ident_type_list(newlines=True)
				self._outdent()
				self._expect(')')
				if self._match('SET'):
					self._newline(-1)
					self._parse_assignment_clause(allowdefault=False)
			else:
				self._parse_table_correlation()
		else:
			self._forget_state()
		if self._match('WHERE'):
			self._newline(-1)
			self._indent()
			self._parse_search_condition()
			self._outdent()
		if self._match('WITH'):
			self._newline(-1)
			self._expect_one_of(['RR', 'RS', 'CS', 'UR'])

	def _parse_drop_statement(self):
		"""Parses a DROP statement"""
		# DROP already matched
		if self._match_one_of(['ALIAS', 'SYNONYM', 'TABLE', 'VIEW', 'NICKNAME', 'VARIABLE']):
			self._parse_subschema_name()
		elif self._match_sequence(['FUNCTION', 'MAPPING']):
			self._parse_function_name()
		elif self._match_one_of(['FUNCTION', 'PROCEDURE']):
			self._parse_routine_name()
			if self._match('(', prespace=False):
				self._parse_datatype_list()
				self._expect(')')
		elif self._match('SPECIFIC'):
			self._expect_one_of(['FUNCTION', 'PROCEDURE'])
			self._parse_routine_name()
		elif self._match('INDEX'):
			self._parse_index_name()
		elif self._match('SEQUENCE'):
			self._parse_sequence_name()
		elif self._match_sequence(['SERVICE', 'CLASS']):
			self._expect(IDENTIFIER)
			if self._match('UNDER'):
				self._expect(IDENTIFIER)
		elif self._match_one_of(['TABLESPACE', 'TABLESPACES']):
			self._parse_ident_list()
		elif self._match_one_of(['DATA', 'DISTINCT']):
			self._expect('TYPE')
			self._parse_type_name()
		elif self._match_sequence(['TYPE', 'MAPPING']):
			self._parse_type_name()
		elif self._match('TYPE'):
			self._parse_type_name()
		elif self._match_sequence(['USER', 'MAPPING']):
			self._expect('FOR')
			self._expect_one_of(['USER', IDENTIFIER])
			self._expect_sequence(['SERVER', IDENTIFIER])
		elif (self._match_sequence(['AUDIT', 'POLICY']) or
			self._match('BUFFERPOOL') or
			self._match_sequence(['EVENT', 'MONITOR']) or
			self._match_sequence(['HISTORGRAM', 'TEMPLATE']) or
			self._match('NODEGROUP') or
			self._match_sequence(['DATABASE', 'PARTITION', 'GROUP']) or
			self._match('ROLE') or
			self._match('SCHEMA') or
			self._match_sequence(['SECURITY', 'LABEL', 'COMPONENT']) or
			self._match_sequence(['SECURITY', 'LABEL']) or
			self._match_sequence(['SECURITY', 'POLICY']) or
			self._match('SERVER') or
			self._match('THRESHOLD') or
			self._match('TRIGGER') or
			self._match_sequence(['TRUSTED', 'CONTEXT']) or
			self._match_sequence(['WORK', 'ACTION', 'SET']) or
			self._match_sequence(['WORK', 'CLASS', 'SET']) or
			self._match('WORKLOAD') or
			self._match('WRAPPER')):
			self._expect(IDENTIFIER)
		else:
			self._expected_one_of([
				'ALIAS',
				'AUDIT',
				'BUFFERPOOL',
				'DATA',
				'DATABASE',
				'DISTINCT',
				'EVENT',
				'FUNCTION',
				'HISTOGRAM',
				'INDEX',
				'NICKNAME',
				'NODEGROUP',
				'PROCEDURE',
				'ROLE',
				'SCHEMA',
				'SECURITY',
				'SEQUENCE',
				'SERVICE',
				'SPECIFIC',
				'TABLE',
				'TABLESPACE',
				'THRESHOLD',
				'TRIGGER',
				'TRUSTED',
				'TYPE',
				'USER',
				'VARIABLE',
				'VIEW',
				'WORK',
				'WORKLOAD',
				'WRAPPER',
			])
		# XXX Strictly speaking, this isn't DB2 syntax - it's generic SQL. But
		# if we stick to strict DB2 semantics, this routine becomes boringly
		# long...
		self._match_one_of(['RESTRICT', 'CASCADE'])

	def _parse_execute_immediate_statement(self):
		"""Parses an EXECUTE IMMEDIATE statement in a procedure"""
		# EXECUTE IMMEDIATE already matched
		self._parse_expression()

	def _parse_explain_statement(self):
		"""Parses an EXPLAIN statement"""
		# EXPLAIN already matched
		if self._match('PLAN'):
			self._match('SELECTION')
		else:
			self._expect_one_of(['PLAN', 'ALL'])
		if self._match_one_of(['FOR', 'WITH']):
			self._expect('SNAPSHOT')
		self._match_sequence(['WITH', 'REOPT', 'ONCE'])
		self._match_sequence(['SET', 'QUERYNO', '=', NUMBER])
		self._match_sequence(['SET', 'QUEYRTAG', '=', STRING])
		self._expect('FOR')
		if self._match('DELETE'):
			self._parse_delete_statement()
		elif self._match('INSERT'):
			self._parse_insert_statement()
		elif self._match('MERGE'):
			self._parse_merge_statement()
		elif self._match_sequence(['REFRESH', 'TABLE']):
			self._parse_refresh_table_statement()
		elif self._match_sequence(['SET', 'INTEGRITY']):
			self._parse_set_integrity_statement()
		elif self._match('UPDATE'):
			self._parse_update_statement()
		else:
			self._parse_select_statement()

	def _parse_fetch_statement(self):
		"""Parses a FETCH FROM statement in a procedure"""
		# FETCH already matched
		self._match('FROM')
		self._expect(IDENTIFIER)
		if self._match('INTO'):
			self._parse_ident_list()
		elif self._match('USING'):
			self._expect('DESCRIPTOR')
			self._expect(IDENTIFIER)
		else:
			self._expected_one_of(['INTO', 'USING'])

	def _parse_flush_optimization_profile_cache_statement(self):
		"""Parses a FLUSH OPTIMIZATION PROFILE CACHE statement"""
		# FLUSH OPTIMIZATION PROFILE CACHE already matched
		if not self._match('ALL'):
			self._parse_subschema_name()

	def _parse_for_statement(self, inproc, label=None):
		"""Parses a FOR-loop in a dynamic compound statement"""
		# FOR already matched
		self._expect_sequence([IDENTIFIER, 'AS'])
		if inproc:
			reraise = False
			self._indent()
			# Ambiguity: IDENTIFIER vs. select-statement
			self._save_state()
			try:
				self._expect_sequence([IDENTIFIER, 'CURSOR'])
				reraise = True
				if self._match_one_of(['WITH', 'WITHOUT']):
					self._expect('HOLD')
				self._expect('FOR')
			except ParseError:
				self._restore_state()
				if reraise: raise
			else:
				self._forget_state()
			self._parse_select_statement()
			self._outdent()
		else:
			self._indent()
			self._parse_query()
			self._outdent()
		self._expect('DO')
		self._indent()
		while True:
			if inproc:
				self._parse_procedure_statement()
			else:
				self._parse_routine_statement()
			self._expect((TERMINATOR, ';'))
			self._newline()
			if self._match('END'):
				break
		self._outdent(-1)
		self._expect('FOR')
		if label:
			self._match((IDENTIFIER, label))

	def _parse_free_locator_statement(self):
		"""Parses a FREE LOCATOR statement"""
		# FREE LOCATOR already matched
		self._parse_ident_list()

	def _parse_get_diagnostics_statement(self):
		"""Parses a GET DIAGNOSTICS statement in a dynamic compound statement"""
		# GET DIAGNOSTICS already matched
		if self._match('EXCEPTION'):
			self._expect((NUMBER, 1))
			while True:
				self._expect_sequence([IDENTIFIER, '='])
				self._expect_one_of(['MESSAGE_TEXT', 'DB2_TOKEN_STRING'])
				if not self._match(','):
					break
		else:
			self._expect_sequence([IDENTIFIER, '='])
			self._expect(['ROW_COUNT', 'DB2_RETURN_STATUS'])

	def _parse_goto_statement(self):
		"""Parses a GOTO statement in a procedure"""
		# GOTO already matched
		self._expect(IDENTIFIER)

	def _parse_grant_statement(self):
		"""Parses a GRANT statement"""
		# GRANT already matched
		self._parse_grant_revoke(grant=True)

	def _parse_if_statement(self, inproc):
		"""Parses an IF-conditional in a dynamic compound statement"""
		# IF already matched
		t = 'IF'
		while True:
			if t in ('IF', 'ELSEIF'):
				self._parse_search_condition(newlines=False)
				self._expect('THEN')
				self._indent()
				while True:
					if inproc:
						self._parse_procedure_statement()
					else:
						self._parse_routine_statement()
					self._expect((TERMINATOR, ';'))
					t = self._match_one_of(['ELSEIF', 'ELSE', 'END'])
					if t:
						self._outdent(-1)
						t = t[1]
						break
					else:
						self._newline()
			elif t == 'ELSE':
				self._indent()
				while True:
					if inproc:
						self._parse_procedure_statement()
					else:
						self._parse_routine_statement()
					self._expect((TERMINATOR, ';'))
					if self._match('END'):
						self._outdent(-1)
						break
					else:
						self._newline()
				break
			else:
				break
		self._expect('IF')

	def _parse_insert_statement(self):
		"""Parses an INSERT statement"""
		# INSERT already matched
		self._expect('INTO')
		if self._match('('):
			self._indent()
			self._parse_full_select()
			self._outdent()
			self._expect(')')
		else:
			self._parse_subschema_name()
		if self._match('('):
			self._indent()
			self._parse_ident_list(newlines=True)
			self._outdent()
			self._expect(')')
		if self._match('INCLUDE'):
			self._newline(-1)
			self._expect('(')
			self._indent()
			self._parse_ident_type_list(newlines=True)
			self._outdent()
			self._expect(')')
		# Parse a full-select with optional common-table-expression, allowing
		# the DEFAULT keyword in (for example) a VALUES clause
		self._newline()
		self._parse_query(allowdefault=True)
		if self._match('WITH'):
			self._newline(-1)
			self._expect_one_of(['RR', 'RS', 'CS', 'UR'])

	def _parse_iterate_statement(self):
		"""Parses an ITERATE statement within a loop"""
		# ITERATE already matched
		self._match(IDENTIFIER)

	def _parse_leave_statement(self):
		"""Parses a LEAVE statement within a loop"""
		# LEAVE already matched
		self._match(IDENTIFIER)

	def _parse_lock_table_statement(self):
		"""Parses a LOCK TABLE statement"""
		# LOCK TABLE already matched
		self._parse_table_name()
		self._expect('IN')
		self._expect_one_of(['SHARE', 'EXCLUSIVE'])
		self._expect('MODE')

	def _parse_loop_statement(self, inproc, label=None):
		"""Parses a LOOP-loop in a procedure"""
		# LOOP already matched
		self._indent()
		while True:
			if inproc:
				self._parse_procedure_statement()
			else:
				self._parse_routine_statement()
			self._expect((TERMINATOR, ';'))
			if self._match('END'):
				self._outdent(-1)
				break
			else:
				self._newline()
		self._expect('LOOP')
		if label:
			self._match((IDENTIFIER, label))

	def _parse_merge_statement(self):
		# MERGE already matched
		self._expect('INTO')
		if self._match('('):
			self._indent()
			self._parse_full_select()
			self._outdent()
			self._expect(')')
		else:
			self._parse_subschema_name()
		self._parse_table_correlation()
		self._expect('USING')
		self._parse_table_ref()
		self._expect('ON')
		self._parse_search_condition()
		self._expect('WHEN')
		while True:
			self._match('NOT')
			self._expect('MATCHED')
			if self._match('AND'):
				self._parse_search_condition()
			self._expect('THEN')
			self._indent()
			if self._match('UPDATE'):
				self._expect('SET')
				self._parse_assignment_clause(allowdefault=True)
			elif self._match('INSERT'):
				if self._match('('):
					self._parse_ident_list()
					self._expect(')')
				self._expect('VALUES')
				if self._match('('):
					self._parse_expression_list(allowdefault=True)
					self._expect(')')
				else:
					if not self._match('DEFAULT'):
						self._parse_expression()
				if not self._match(','):
					break
			elif self._match('DELETE'):
				pass
			elif self._match('SIGNAL'):
				self._parse_signal_statement
			self._outdent()
			if not self._match('WHEN'):
				break
		self._match_sequence(['ELSE', 'IGNORE'])

	def _parse_open_statement(self):
		"""Parses an OPEN cursor statement"""
		# OPEN already matched
		self._expect(IDENTIFIER)

	def _parse_refresh_table_statement(self):
		"""Parses a REFRESH TABLE statement"""
		# REFRESH TABLE already matched
		while True:
			self._parse_table_name()
			queryopt = False
			if self._match('ALLOW'):
				if self._match_one_of(['NO', 'READ', 'WRITE']):
					self._expect('ACCESS')
				elif self._match_sequence(['QUERY', 'OPTIMIZATION']):
					queryopt = True
					self._expect_sequence(['USING', 'REFRESH', 'DEFERRED', 'TABLES'])
					self._match_sequence(['WITH', 'REFRESH', 'AGE', 'ANY'])
				else:
					self._expected_one_of(['NO', 'READ', 'WRITE', 'QUERY'])
			if not queryopt:
				if self._match_sequence(['USING', 'REFRESH', 'DEFERRED', 'TABLES']):
					self._match_sequence(['WITH', 'REFRESH', 'AGE', 'ANY'])
			if not self._match(','):
				break
		self._match('NOT')
		self._match('INCREMENTAL')

	def _parse_release_savepoint_statement(self):
		"""Parses a RELEASE SAVEPOINT statement"""
		# RELEASE [TO] SAVEPOINT already matched
		self._expect(IDENTIFIER)

	def _parse_rename_tablespace_statement(self):
		"""Parses a RENAME TABLESPACE statement"""
		# RENAME TABLESPACE already matched
		self._expect_sequence([IDENTIFIER, 'TO', IDENTIFIER])

	def _parse_rename_statement(self):
		"""Parses a RENAME statement"""
		# RENAME already matched
		if self._match('INDEX'):
			self._parse_index_name()
		else:
			self._match('TABLE')
			self._parse_table_name()
		self._expect_sequence(['TO', IDENTIFIER])

	def _parse_repeat_statement(self, inproc, label=None):
		"""Parses a REPEAT-loop in a procedure"""
		# REPEAT already matched
		self._indent()
		while True:
			if inproc:
				self._parse_procedure_statement()
			else:
				self._parse_routine_statement()
			self._expect((TERMINATOR, ';'))
			self._newline()
			if self._match('UNTIL'):
				break
			else:
				self._newline()
		self._outdent(-1)
		self._parse_search_condition()
		self._expect_sequence(['END', 'REPEAT'])
		if label:
			self._match((IDENTIFIER, label))

	def _parse_resignal_statement(self):
		"""Parses a RESIGNAL statement in a dynamic compound statement"""
		# SIGNAL already matched
		if self._match('SQLSTATE'):
			self._match('VALUE')
			self._expect_one_of([IDENTIFIER, STRING])
		else:
			if not self._match(IDENTIFIER):
				return
		if self._match('SET'):
			self._expect_sequence(['MESSAGE_TEXT', '='])
			self._parse_expression()

	def _parse_return_statement(self):
		"""Parses a RETURN statement in a compound statement"""
		# RETURN already matched
		self._save_state()
		try:
			# Try and parse a select-statement
			self._parse_query()
		except ParseError:
			# If it fails, rewind and try an expression or tuple instead
			self._restore_state()
			self._parse_expression()
		else:
			self._forget_state()

	def _parse_revoke_statement(self):
		"""Parses a REVOKE statement"""
		# REVOKE already matched
		self._parse_grant_revoke(grant=False)

	def _parse_rollback_statement(self):
		"""Parses a ROLLBACK statement"""
		# ROLLBACK already matched
		self._match('WORK')
		if self._match('TO'):
			self._expect('SAVEPOINT')
			self._match(IDENTIFIER)

	def _parse_savepoint_statement(self):
		"""Parses a SAVEPOINT statement"""
		# SAVEPOINT already matched
		self._expect(IDENTIFIER)
		self._match('UNIQUE')
		self._expect_sequence(['ON', 'ROLLBACK', 'RETAIN', 'CURSORS'])
		self._match_sequence(['ON', 'ROLLBACK', 'RETAIN', 'LOCKS'])

	def _parse_select_statement(self, allowinto=False):
		"""Parses a SELECT statement"""
		# A top-level select-statement never permits DEFAULTS, although it
		# might permit INTO in a procedure
		self._parse_query(allowdefault=False, allowinto=allowinto)
		# Parse optional SELECT attributes (FOR UPDATE, WITH isolation, etc.)
		valid = ['WITH', 'FOR', 'OPTIMIZE']
		while valid:
			t = self._match_one_of(valid)
			if t:
				self._newline(-1)
				t = t[1]
				valid.remove(t)
			else:
				break
			if t == 'FOR':
				if self._match_one_of(['READ', 'FETCH']):
					self._expect('ONLY')
				elif self._match('UPDATE'):
					if self._match('OF'):
						self._parse_ident_list()
				else:
					self._expected_one_of(['READ', 'FETCH', 'UPDATE'])
			elif t == 'OPTIMIZE':
				self._expect_sequence(['FOR', NUMBER])
				self._expect_one_of(['ROW', 'ROWS'])
			elif t == 'WITH':
				if self._expect_one_of(['RR', 'RS', 'CS', 'UR'])[1] in ('RR', 'RS'):
					if self._match('USE'):
						self._expect_sequence(['AND', 'KEEP'])
						self._expect_one_of(['SHARE', 'EXCLUSIVE', 'UPDATE'])
						self._expect('LOCKS')

	def _parse_set_integrity_statement(self):
		"""Parses a SET INTEGRITY statement"""

		def parse_access_mode():
			if self._match_one_of(['NO', 'READ']):
				self._expect('ACCESS')

		def parse_cascade_clause():
			if self._match('CASCADE'):
				if self._expect_one_of(['DEFERRED', 'IMMEDIATE'])[1] == 'IMMEDIATE':
					if self._match('TO'):
						if self._match('ALL'):
							self._expect('TABLES')
						else:
							while True:
								if self._match('MATERIALIZED'):
									self._expect_sequence(['QUERY', 'TABLES'])
								elif self._match('FOREIGN'):
									self._expect_sequence(['KEY', 'TABLES'])
								elif self._match('STAGING'):
									self._expect('TABLES')
								else:
									self._expected_one_of(['MATERIALIZED', 'STAGING', 'FOREIGN'])
								if not self._match(','):
									break

		def parse_check_options():
			valid = [
				'INCREMENTAL',
				'NOT',
				'FORCE',
				'PRUNE',
				'FULL',
				'FOR',
			]
			while valid:
				t = self._match_one_of(valid)
				if t:
					t = t[1]
					valid.remove(t)
				else:
					break
				if t == 'INCREMENTAL':
					valid.remove('NOT')
				elif t == (KEYWORD, 'NOT'):
					self._expect('INCREMENTAL')
					valid.remove('INCREMENTAL')
				elif t == 'FORCE':
					self._expect('GENERATED')
				elif t == 'PRUNE':
					pass
				elif t == 'FULL':
					self._expect('ACCESS')
				elif t == 'FOR':
					self._expect('EXCEPTION')
					while True:
						self._expect('IN')
						self._parse_table_name()
						self._expect('USE')
						self._parse_table_name()
						if not self._match(','):
							break

		def parse_integrity_options():
			if not self._match('ALL'):
				while True:
					if self._match('FOREIGN'):
						self._expect('KEY')
					elif self._match('CHECK'):
						pass
					elif self._match('DATALINK'):
						self._expect_sequence(['RECONCILE', 'PENDING'])
					elif self._match('MATERIALIZED'):
						self._expect('QUERY')
					elif self._match('GENERATED'):
						self._expect('COLUMN')
					elif self._match('STAGING'):
						pass
					else:
						self._expected_one_of([
							'FOREIGN',
							'CHECK',
							'DATALINK',
							'MATERIALIZED',
							'GENERATED',
							'STAGING',
						])
					if not self._match(','):
						break

		# SET INTEGRITY already matched
		self._expect('FOR')
		# Ambiguity: SET INTEGRITY ... CHECKED and SET INTEGRITY ... UNCHECKED
		# have very different syntaxes, but only after initial similarities.
		reraise = False
		self._save_state()
		try:
			# Try and parse SET INTEGRITY ... IMMEDIATE CHECKED
			while True:
				self._parse_table_name()
				if self._match(','):
					reraise = True
				else:
					break
			if self._match('OFF'):
				reraise = True
				parse_access_mode()
				parse_cascade_clause()
			elif self._match('TO'):
				reraise = True
				self._expect_sequence(['DATALINK', 'RECONCILE', 'PENDING'])
			elif self._match('IMMEDIATE'):
				reraise = True
				self._expect('CHECKED')
				parse_check_options()
			elif self._match('FULL'):
				reraise = True
				self._expect('ACCESS')
			elif self._match('PRUNE'):
				reraise = True
			else:
				self._expected_one_of(['OFF', 'TO', 'IMMEDIATE', 'FULL', 'PRUNE'])
		except ParseError:
			# If that fails, parse SET INTEGRITY ... IMMEDIATE UNCHECKED
			self._restore_state()
			if reraise: raise
			while True:
				self._parse_table_name()
				parse_integrity_options()
				if self._match('FULL'):
					self._expect('ACCESS')
				if not self._match(','):
					break
		else:
			self._forget_state()

	def _parse_set_isolation_statement(self):
		"""Parses a SET ISOLATION statement"""
		# SET [CURRENT] ISOLATION already matched
		self._match('=')
		self._expect_one_of(['UR', 'CS', 'RR', 'RS', 'RESET'])

	def _parse_set_lock_timeout_statement(self):
		"""Parses a SET LOCK TIMEOUT statement"""
		# SET [CURRENT] LOCK TIMEOUT already matched
		self._match('=')
		if self._match('WAIT'):
			self._match(NUMBER)
		elif self._match('NOT'):
			self._expect('WAIT')
		elif self._match('NULL'):
			pass
		elif self._match(NUMBER):
			pass
		else:
			self._expected_one_of(['WAIT', 'NOT', 'NULL', NUMBER])

	def _parse_set_path_statement(self):
		"""Parses a SET PATH statement"""
		# SET [CURRENT] PATH already matched
		self._match('=')
		while True:
			if self._match_sequence([(REGISTER, 'SYSTEM'), (REGISTER, 'PATH')]):
				pass
			elif self._match((REGISTER, 'USER')):
				pass
			elif self._match((REGISTER, 'CURRENT')):
				self._match((REGISTER, 'PACKAGE'))
				self._expect((REGISTER, 'PATH'))
			elif self._match((REGISTER, 'CURRENT_PATH')):
				pass
			else:
				self._expect_one_of([IDENTIFIER, STRING])
			if not self._match(','):
				break

	def _parse_set_schema_statement(self):
		"""Parses a SET SCHEMA statement"""
		# SET [CURRENT] SCHEMA already matched
		self._match('=')
		self._expect_one_of([
			(REGISTER, 'USER'),
			(REGISTER, 'SESSION_USER'),
			(REGISTER, 'SYSTEM_USER'),
			(REGISTER, 'CURRENT_USER'),
			IDENTIFIER,
			STRING,
		])

	def _parse_set_session_auth_statement(self):
		"""Parses a SET SESSION AUTHORIZATION statement"""
		# SET SESSION AUTHORIZATION already matched
		self._match('=')
		self._expect_one_of([
			(REGISTER, 'USER'),
			(REGISTER, 'SYSTEM_USER'),
			(REGISTER, 'CURRENT_USER'),
			IDENTIFIER,
			STRING,
		])
		self._match_sequence(['ALLOW', 'ADMINISTRATION'])

	def _parse_set_statement(self):
		"""Parses a SET statement in a dynamic compound statement"""
		# SET already matched
		if self._match('CURRENT'):
			if self._match_sequence(['DECFLOAT', 'ROUNDING', 'MODE']):
				self._match('=')
				self._expect_one_of([
					'ROUND_CEILING',
					'ROUND_FLOOR',
					'ROUND_DOWN',
					'ROUND_HALF_EVEN',
					'ROUND_HALF_UP',
					STRING,
				])
			if self._match('DEGREE'):
				self._match('=')
				self._expect(STRING)
			elif self._match('EXPLAIN'):
				if self._match('MODE'):
					self._match('=')
					if self._match_one_of(['EVALUATE', 'RECOMMEND']):
						self._expect_one_of(['INDEXES', 'PARTITIONINGS'])
					elif self._match_one_of(['NO', 'YES', 'REOPT', 'EXPLAIN']):
						pass
					else:
						self._expected_one_of([
							'NO',
							'YES',
							'REOPT',
							'EXPLAIN',
							'EVALUATE',
							'RECOMMEND',
						])
				elif self._match('SNAPSHOT'):
					self._expect_one_of(['NO', 'YES', 'EXPLAIN', 'REOPT'])
				else:
					self._expected_one_of(['MODE', 'SNAPSHOT'])
			elif self._match_sequence(['FEDERATED', 'ASYNCHRONY']):
				self._match('=')
				self._expect_one_of(['ANY', NUMBER])
			elif self._match_sequence(['IMPLICIT', 'XMLPARSE', 'OPTION']):
				self._match('=')
				self._expect(STRING)
			elif self._match('ISOLATION'):
				self._parse_set_isolation_statement()
			elif self._match_sequence(['LOCK', 'TIMEOUT']):
				self._parse_set_lock_timeout_statement()
			elif self._match('MAINTAINED'):
				self._match('TABLE')
				self._expect('TYPES')
				self._match_sequence(['FOR', 'OPTIMIZATION'])
				self._match('=')
				while True:
					if self._match_one_of(['ALL', 'NONE']):
						break
					elif self._match_one_of(['FEDERATED_TOOL', 'USER', 'SYSTEM']):
						pass
					elif self._match('CURRENT'):
						self._expect('MAINTAINED')
						self._match('TABLE')
						self._expect('TYPES')
						self._match_sequence(['FOR', 'OPTIMIZATION'])
					if not self._match(','):
						break
			elif self._match_sequence(['MDC', 'ROLLOUT', 'MODE']):
				self._expect_one_of(['NONE', 'IMMEDATE', 'DEFERRED'])
			elif self._match_sequence(['OPTIMIZATION', 'PROFILE']):
				self._match('=')
				if not self._match(STRING) and not self._match('NULL'):
					self._parse_subschema_name()
			elif self._match_sequence(['QUERY', 'OPTIMIZATION']):
				self._match('=')
				self._expect(NUMBER)
			elif self._match_sequence(['REFRESH', 'AGE']):
				self._match('=')
				self._expect_one_of(['ANY', NUMBER])
			elif self._match('PATH'):
				self._parse_set_path_statement()
			elif self._match('SCHEMA'):
				self._parse_set_schema_statement()
			else:
				self._expected_one_of([
					'DEGREE',
					'EXPLAIN',
					'ISOLATION',
					'LOCK',
					'MAINTAINED',
					'QUERY',
					'REFRESH',
					'PATH',
					'SCHEMA',
				])
		elif self._match_sequence(['COMPILATION', 'ENVIRONMENT']):
			self._match('=')
			self._expect(IDENTIFIER)
		elif self._match('ISOLATION'):
			self._parse_set_isolation_statement()
		elif self._match_sequence(['ENCRYPTION', 'PASSWORD']):
			self._match('=')
			self._expect(STRING)
		elif self._match_sequence(['EVENT', 'MONITOR']):
			self._expect(IDENTIFIER)
			self._expect('STATE')
			self._match('=')
			self._expect(NUMBER)
		elif self._match('PASSTHRU'):
			self._expect_one_of(['RESET', IDENTIFIER])
		elif self._match('PATH'):
			self._parse_set_path_statement()
		elif self._match('ROLE'):
			self._match('=')
			self._expect(IDENTIFIER)
		elif self._match('CURRENT_PATH'):
			self._parse_set_path_statement()
		elif self._match('SCHEMA'):
			self._parse_set_schema_statement()
		elif self._match_sequence(['SERVER', 'OPTION']):
			self._expect_sequence([IDENTIFIER, 'TO', STRING, 'FOR', 'SERVER', IDENTIFIER])
		elif self._match_sequence(['SESSION', 'AUTHORIZATION']):
			self._parse_set_session_auth_statement()
		elif self._match('SESSION_USER'):
			self._parse_set_session_auth_statement()
		else:
			self._parse_assignment_clause(allowdefault=True)

	def _parse_signal_statement(self):
		"""Parses a SIGNAL statement in a dynamic compound statement"""
		# SIGNAL already matched
		if self._match('SQLSTATE'):
			self._match('VALUE')
			self._expect_one_of([IDENTIFIER, STRING])
		else:
			self._expect(IDENTIFIER)
		if self._match('SET'):
			self._expect_sequence(['MESSAGE_TEXT', '='])
			self._parse_expression()
		elif self._match('('):
			# XXX Ensure syntax only valid within a trigger
			self._parse_expression()
			self._expect(')')

	def _parse_transfer_ownership_statement(self):
		"""Parses a TRANSFER OWNERSHIP statement"""
		# TRANSFER OWNERSHIP already matched
		self._expect('OF')
		if self._match_one_of(['ALIAS', 'TABLE', 'VIEW', 'NICKNAME', 'VARIABLE']):
			self._parse_subschema_name()
		elif self._match_sequence(['FUNCTION', 'MAPPING']):
			self._parse_function_name()
		elif self._match_one_of(['FUNCTION', 'PROCEDURE']):
			self._parse_routine_name()
			if self._match('('):
				self._parse_datatype_list()
				self._expect(')')
		elif self._match('SPECIFIC'):
			self._expect_one_of(['FUNCTION', 'PROCEDURE'])
			self._parse_routine_name()
		elif self._match('INDEX'):
			self._parse_index_name()
		elif self._match('SEQUENCE'):
			self._parse_sequence_name()
		elif self._match('DISTINCT'):
			self._expect('TYPE')
			self._parse_type_name()
		elif self._match_sequence(['TYPE', 'MAPPING']):
			self._parse_type_name()
		elif self._match('TYPE'):
			self._parse_type_name()
		elif (self._match_sequence(['EVENT', 'MONITOR']) or
			self._match('NODEGROUP') or
			self._match_sequence(['DATABASE', 'PARTITION', 'GROUP']) or
			self._match('SCHEMA') or
			self._match('TABLESPACE') or
			self._match('TRIGGER')):
			self._expect(IDENTIFIER)
		else:
			self._expected_one_of([
				'ALIAS',
				'DATABASE',
				'DISTINCT',
				'EVENT',
				'FUNCTION',
				'INDEX',
				'NICKNAME',
				'NODEGROUP',
				'PROCEDURE',
				'SCHEMA',
				'SEQUENCE',
				'SPECIFIC',
				'TABLE',
				'TABLESPACE',
				'TRIGGER',
				'TYPE',
				'VARIABLE',
				'VIEW',
			])
		if self._match('USER'):
			self._expect(IDENTIFIER)
		else:
			self._expect_one_of([
				(REGISTER, 'USER'),
				(REGISTER, 'SESSION_USER'),
				(REGISTER, 'SYSTEM_USER'),
			])
		self._expect_sequence(['PERSERVE', 'PRIVILEGES'])

	def _parse_update_statement(self):
		"""Parses an UPDATE statement"""
		# UPDATE already matched
		if self._match('('):
			self._indent()
			self._parse_full_select()
			self._outdent()
			self._expect(')')
		else:
			self._parse_subschema_name()
		# Ambiguity: INCLUDE is an identifier and hence can look like a table
		# correlation name
		reraise = False
		self._save_state()
		try:
			# Try and parse a mandatory table correlation followed by a
			# mandatory INCLUDE
			self._parse_table_correlation(optional=False)
			self._newline()
			self._expect('INCLUDE')
			reraise = True
			self._expect('(')
			self._indent()
			self._parse_ident_type_list(newlines=True)
			self._outdent()
			self._expect(')')
		except ParseError:
			# If that fails, rewind and parse an optional INCLUDE or an
			# optional table correlation
			self._restore_state()
			if reraise: raise
			if self._match('INCLUDE'):
				self._newline(-1)
				self._expect('(')
				self._indent()
				self._parse_ident_type_list(newlines=True)
				self._outdent()
				self._expect(')')
			else:
				self._parse_table_correlation()
		else:
			self._forget_state()
		# Parse mandatory assignment clause allow DEFAULT values
		self._expect('SET')
		self._indent()
		self._parse_assignment_clause(allowdefault=True)
		self._outdent()
		if self._match('WHERE'):
			self._indent()
			self._parse_search_condition()
			self._outdent()
		if self._match('WITH'):
			self._expect_one_of(['RR', 'RS', 'CS', 'UR'])

	def _parse_while_statement(self, inproc, label=None):
		"""Parses a WHILE-loop in a dynamic compound statement"""
		# WHILE already matched
		self._parse_search_condition(newlines=False)
		self._newline()
		self._expect('DO')
		self._indent()
		while True:
			if inproc:
				self._parse_procedure_statement()
			else:
				self._parse_routine_statement()
			self._expect((TERMINATOR, ';'))
			if self._match('END'):
				self._outdent(-1)
				break
			else:
				self._newline()
		self._expect('WHILE')
		if label:
			self._match((IDENTIFIER, label))

	# COMPOUND STATEMENTS ####################################################

	def _parse_routine_statement(self):
		"""Parses a statement in a routine/trigger/compound statement"""
		# XXX Only permit RETURN when part of a function/method/trigger
		# XXX Only permit ITERATE when part of a loop
		if self._match('CALL'):
			self._parse_call_statement()
		elif self._match('DELETE'):
			self._parse_delete_statement()
		elif self._match('FOR'):
			self._parse_for_statement(inproc=False)
		elif self._match_sequence(['GET', 'DIAGNOSTICS']):
			self._parse_get_diagnostics_statement()
		elif self._match('IF'):
			self._parse_if_statement(inproc=False)
		elif self._match('INSERT'):
			self._parse_insert_statement()
		elif self._match('ITERATE'):
			self._parse_iterate_statement()
		elif self._match('LEAVE'):
			self._parse_leave_statement()
		elif self._match('MERGE'):
			self._parse_merge_statement()
		elif self._match('RETURN'):
			self._parse_return_statement()
		elif self._match('SET'):
			self._parse_set_statement()
		elif self._match('SIGNAL'):
			self._parse_signal_statement()
		elif self._match('UPDATE'):
			self._parse_update_statement()
		elif self._match('WHILE'):
			self._parse_while_statement(inproc=False)
		else:
			try:
				label = self._expect(LABEL)[1]
			except ParseError:
				self._parse_select_statement()
			else:
				if self._match('FOR'):
					self._parse_for_statement(inproc=False, label=label)
				elif self._match('WHILE'):
					self._parse_while_statement(inproc=False, label=label)
				else:
					self._expected_one_of(['FOR', 'WHILE'])

	def _parse_dynamic_compound_statement(self, label=None):
		"""Parses a dynamic compound statement"""
		# BEGIN already matched
		self._expect('ATOMIC')
		self._indent()
		# Parse optional variable/condition declarations
		if self._match('DECLARE'):
			while True:
				count = len(self._parse_ident_list())
				if count == 1 and self._match('CONDITION'):
					self._expect('FOR')
					if self._match('SQLSTATE'):
						self._match('VALUE')
					self._expect(STRING)
				else:
					self._parse_datatype()
					if self._match('DEFAULT'):
						self._parse_expression()
				self._expect((TERMINATOR, ';'))
				self._newline()
				if not self._match('DECLARE'):
					break
		# Parse routine statements
		while True:
			self._parse_routine_statement()
			self._expect((TERMINATOR, ';'))
			if self._match('END'):
				break
			else:
				self._newline()
		self._outdent(-1)
		if label:
			self._match((IDENTIFIER, label))

	def _parse_procedure_statement(self):
		"""Parses a procedure statement within a procedure body"""
		# XXX Should PREPARE be supported here?
		try:
			label = self._expect(LABEL)[1]
			self._newline()
		except ParseError:
			label = None
		# Procedure specific statements
		if self._match('ALLOCATE'):
			self._parse_allocate_cursor_statement()
		elif self._match('ASSOCIATE'):
			self._parse_associate_locators_statement()
		elif self._match('BEGIN'):
			self._parse_procedure_compound_statement(label=label)
		elif self._match('CASE'):
			self._parse_case_statement(inproc=True)
		elif self._match('CLOSE'):
			self._parse_close_statement()
		elif self._match_sequence(['EXECUTE', 'IMMEDIATE']):
			self._parse_execute_immediate_statement()
		elif self._match('FETCH'):
			self._parse_fetch_statement()
		elif self._match('GOTO'):
			self._parse_goto_statement()
		elif self._match('LOOP'):
			self._parse_loop_statement(inproc=True, label=label)
		elif self._match('OPEN'):
			self._parse_open_statement()
		elif self._match('REPEAT'):
			self._parse_repeat_statement(inproc=True, label=label)
		# Dynamic compound specific statements
		elif self._match('FOR'):
			self._parse_for_statement(inproc=True, label=label)
		elif self._match_sequence(['GET', 'DIAGNOSTICS']):
			self._parse_get_diagnostics_statement()
		elif self._match('IF'):
			self._parse_if_statement(inproc=True)
		elif self._match('ITERATE'):
			self._parse_iterate_statement()
		elif self._match('LEAVE'):
			self._parse_leave_statement()
		elif self._match('RETURN'):
			self._parse_return_statement()
		elif self._match('SET'):
			self._parse_set_statement()
		elif self._match('SIGNAL'):
			self._parse_signal_statement()
		elif self._match('WHILE'):
			self._parse_while_statement(inproc=True, label=label)
		# Generic SQL statements
		elif self._match('AUDIT'):
			self._parse_audit_statement()
		elif self._match('CALL'):
			self._parse_call_statement()
		elif self._match_sequence(['COMMENT', 'ON']):
			self._parse_comment_statement()
		elif self._match('COMMIT'):
			self._parse_commit_statement()
		elif self._match('CREATE'):
			if self._match('TABLE'):
				self._parse_create_table_statement()
			elif self._match('VIEW'):
				self._parse_create_view_statement()
			elif self._match('UNIQUE'):
				self._expect('INDEX')
				self._parse_create_index_statement()
			elif self._match('INDEX'):
				self._parse_create_index_statement()
			else:
				self._expected_one_of(['TABLE', 'VIEW', 'INDEX', 'UNIQUE'])
		elif self._match_sequence(['DECLARE', 'GLOBAL', 'TEMPORARY', 'TABLE']):
			self._parse_declare_global_temporary_table_statement()
		elif self._match('DELETE'):
			self._parse_delete_statement()
		elif self._match('DROP'):
			# XXX Limit this to tables, views and indexes somehow?
			self._parse_drop_statement()
		elif self._match('EXPLAIN'):
			self._parse_explain_statement()
		elif self._match_sequence(['FLUSH', 'OPTIMIZATION', 'PROFILE', 'CACHE']):
			self._parse_flush_optimization_profile_cache_statement()
		elif self._match_sequence(['FREE', 'LOCATOR']):
			self._parse_free_locator_statement()
		elif self._match('GRANT'):
			self._parse_grant_statement()
		elif self._match('INSERT'):
			self._parse_insert_statement()
		elif self._match_sequence(['LOCK', 'TABLE']):
			self._parse_lock_table_statement()
		elif self._match('MERGE'):
			self._parse_merge_statement()
		elif self._match('RELEASE'):
			self._match('TO')
			self._expect('SAVEPOINT')
			self._parse_release_savepoint_statement()
		elif self._match('RESIGNAL'):
			self._parse_resignal_statement()
		elif self._match('ROLLBACK'):
			self._parse_rollback_statement()
		elif self._match('SAVEPOINT'):
			self._parse_savepoint_statement()
		elif self._match_sequence(['TRANSFER', 'OWNERSHIP']):
			self._parse_transfer_ownership_statement()
		elif self._match('UPDATE'):
			self._parse_update_statement()
		else:
			self._parse_select_statement(allowinto=True)

	def _parse_procedure_compound_statement(self, label=None):
		"""Parses a procedure compound statement (body)"""
		# BEGIN already matched
		if self._match('NOT'):
			self._expect('ATOMIC')
		else:
			self._match('ATOMIC')
		self._indent()
		# Ambiguity: there's several statements beginning with DECLARE that can
		# occur mixed together or in a specific order here, so we use saved
		# states to test for each consecutive block of DECLAREs
		# Try and parse DECLARE variable|condition|return-code
		while True:
			reraise = False
			self._save_state()
			try:
				self._expect('DECLARE')
				if self._match('SQLSTATE'):
					reraise = True
					self._expect_one_of(['CHAR', 'CHARACTER'])
					self._expect_sequence(['(', (NUMBER, 5), ')'], prespace=False)
					self._match_sequence(['DEFAULT', STRING])
				elif self._match('SQLCODE'):
					reraise = True
					self._expect_one_of(['INT', 'INTEGER'])
					self._match_sequence(['DEFAULT', NUMBER])
				else:
					count = len(self._parse_ident_list())
					if count == 1 and self._match('CONDITION'):
						reraise = True
						self._expect('FOR')
						if self._match('SQLSTATE'):
							self._match('VALUE')
						self._expect(STRING)
					else:
						self._parse_datatype()
						if self._match('DEFAULT'):
							reraise = True
							self._parse_expression()
				self._expect((TERMINATOR, ';'))
				self._newline()
			except ParseError:
				self._restore_state()
				if reraise: raise
				break
			else:
				self._forget_state()
		# Try and parse DECLARE statement
		while True:
			reraise = False
			self._save_state()
			try:
				self._expect('DECLARE')
				self._parse_ident_list()
				self._expect('STATEMENT')
				reraise = True
				self._expect((TERMINATOR, ';'))
				self._newline()
			except ParseError:
				self._restore_state()
				if reraise: raise
				break
			else:
				self._forget_state()
		# Try and parse DECLARE CURSOR
		while True:
			reraise = False
			self._save_state()
			try:
				self._expect_sequence(['DECLARE', IDENTIFIER, 'CURSOR'])
				reraise = True
				if self._match('WITH'):
					if self._match('RETURN'):
						self._expect('TO')
						self._expect_one_of(['CALLER', 'CLIENT'])
					else:
						self._expect('HOLD')
						if self._match('WITH'):
							self._expect_sequence(['RETURN', 'TO'])
							self._expect_one_of(['CALLER', 'CLIENT'])
				self._expect('FOR')
				# Ambiguity: statement name could be reserved word
				self._save_state()
				try:
					# Try and parse a SELECT statement
					# XXX Is SELECT INTO permitted in a DECLARE CURSOR?
					self._parse_select_statement()
				except ParseError:
					# If that fails, rewind and parse a simple statement name
					self._restore_state()
					self._expect(IDENTIFIER)
				else:
					self._forget_state()
				self._expect((TERMINATOR, ';'))
				self._newline()
			except ParseError:
				self._restore_state()
				if reraise: raise
				break
			else:
				self._forget_state()
		# Try and parse DECLARE HANDLER
		while True:
			reraise = False
			self._save_state()
			try:
				self._expect('DECLARE')
				self._expect_one_of(['CONTINUE', 'UNDO', 'EXIT'])
				self._expect('HANDLER')
				reraise = True
				self._expect('FOR')
				if self._match('NOT'):
					self._expect('FOUND')
				elif self._match_one_of(['SQLEXCEPTION', 'SQLWARNING']):
					pass
				else:
					while True:
						if self._match('SQLSTATE'):
							self._match('VALUE')
							self._expect(STRING)
						else:
							self._expect(IDENTIFIER)
						if not self._match(','):
							break
				self._parse_procedure_statement()
				self._expect((TERMINATOR, ';'))
				self._newline()
			except ParseError:
				self._restore_state()
				if reraise: raise
				break
			else:
				self._forget_state()
		# Parse procedure statements
		while True:
			self._parse_procedure_statement()
			self._expect((TERMINATOR, ';'))
			if self._match('END'):
				break
			else:
				self._newline()
		self._outdent(-1)
		if label:
			self._match((IDENTIFIER, label))

	def _parse_statement(self):
		"""Parses a top-level statement in an SQL script"""
		# XXX CREATE EVENT MONITOR
		# If we're reformatting WHITESPACE, add a blank WHITESPACE token to the
		# output - this will suppress leading whitespace in front of the first
		# word of the statement
		self._output.append((WHITESPACE, None, '', 0, 0))
		if self._match('ALTER'):
			if self._match('TABLE'):
				self._parse_alter_table_statement()
			elif self._match('SEQUENCE'):
				self._parse_alter_sequence_statement()
			elif self._match('FUNCTION'):
				self._parse_alter_function_statement(specific=False)
			elif self._match('PROCEDURE'):
				self._parse_alter_procedure_statement(specific=False)
			elif self._match('SPECIFIC'):
				if self._match('FUNCTION'):
					self._parse_alter_function_statement(specific=True)
				elif self._match('PROCEDURE'):
					self._parse_alter_procedure_statement(specific=True)
				else:
					self._expected_one_of(['FUNCTION', 'PROCEDURE'])
			elif self._match('NICKNAME'):
				self._parse_alter_nickname_statement()
			elif self._match('TABLESPACE'):
				self._parse_alter_tablespace_statement()
			elif self._match('BUFFERPOOL'):
				self._parse_alter_bufferpool_statement()
			elif self._match_sequence(['DATABASE', 'PARTITION', 'GROUP']):
				self._parse_alter_partition_group_statement()
			elif self._match('DATABASE'):
				self._parse_alter_database_statement()
			elif self._match('NODEGROUP'):
				self._parse_alter_partition_group_statement()
			elif self._match('SERVER'):
				self._parse_alter_server()
			elif self._match_sequence(['HISTOGRAM', 'TEMPLATE']):
				self._parse_alter_histogram_template_statement()
			elif self._match_sequence(['AUDIT', 'POLICY']):
				self._parse_alter_audit_policy_statement()
			elif self._match_sequence(['SECURITY', 'LABEL', 'COMPONENT']):
				self._parse_alter_security_label_component_statement()
			elif self._match_sequence(['SECURITY', 'POLICY']):
				self._parse_alter_security_policy_statement()
			elif self._match_sequence(['SERVICE', 'CLASS']):
				self._parse_alter_service_class_statement()
			elif self._match('THRESHOLD'):
				self._parse_alter_threshold_statement()
			elif self._match_sequence(['TRUSTED', 'CONTEXT']):
				self._parse_alter_trusted_context_statement()
			elif self._match_sequence(['USER', 'MAPPING']):
				self._parse_alter_user_mapping_statement()
			elif self._match('VIEW'):
				self._parse_alter_view_statement()
			elif self._match_sequence(['WORK', 'ACTION', 'SET']):
				self._parse_alter_work_action_set_statement()
			elif self._match_sequence(['WORK', 'CLASS', 'SET']):
				self._parse_alter_work_class_set_statement()
			elif self._match('WORKLOAD'):
				self._parse_alter_workload_statement()
			elif self._match('WRAPPER'):
				self._parse_alter_wrapper_statement()
			else:
				self._expected_one_of([
					'AUDIT',
					'BUFFERPOOL',
					'DATABASE',
					'FUNCTION',
					'HISTOGRAM',
					'NICKNAME',
					'NODEGROUP',
					'PROCEDURE',
					'SECURITY',
					'SEQUENCE',
					'SERVER',
					'SERVICE',
					'SPECIFIC',
					'TABLE',
					'TABLESPACE',
					'THRESHOLD',
					'TRUSTED',
					'USER',
					'VIEW',
					'WORK',
					'WORKLOAD',
					'WRAPPER',
				])
		elif self._match('AUDIT'):
			self._parse_audit_statement()
		elif self._match('BEGIN'):
			self._parse_dynamic_compound_statement()
		elif self._match_sequence(['COMMENT', 'ON']):
			self._parse_comment_statement()
		elif self._match('COMMIT'):
			self._parse_commit_statement()
		elif self._match('CREATE'):
			if self._match('TABLE'):
				self._parse_create_table_statement()
			elif self._match('VIEW'):
				self._parse_create_view_statement()
			elif self._match('ALIAS'):
				self._parse_create_alias_statement()
			elif self._match_sequence(['UNIQUE', 'INDEX']):
				self._parse_create_index_statement(unique=True)
			elif self._match('INDEX'):
				self._parse_create_index_statement(unique=False)
			elif self._match('DISTINCT'):
				self._expect('TYPE')
				self._parse_create_type_statement()
			elif self._match('SEQUENCE'):
				self._parse_create_sequence_statement()
			elif self._match_sequence(['FUNCTION', 'MAPPING']):
				self._parse_create_function_mapping_statement()
			elif self._match('FUNCTION'):
				self._parse_create_function_statement()
			elif self._match('PROCEDURE'):
				self._parse_create_procedure_statement()
			elif self._match('TABLESPACE'):
				self._parse_create_tablespace_statement()
			elif self._match('BUFFERPOOL'):
				self._parse_create_bufferpool_statement()
			elif self._match_sequence(['DATABASE', 'PARTITION', 'GROUP']):
				self._parse_create_database_partition_group_statement()
			elif self._match('NODEGROUP'):
				self._parse_create_database_partition_group_statement()
			elif self._match('TRIGGER'):
				self._parse_create_trigger_statement()
			elif self._match('SCHEMA'):
				self._parse_create_schema_statement()
			elif self._match_sequence(['AUDIT', 'POLICY']):
				self._parse_create_audit_policy_statement()
			elif self._match_sequence(['EVENT', 'MONITOR']):
				self._parse_create_event_monitor_statement()
			elif self._match_sequence(['HISTOGRAM', 'TEMPLATE']):
				self._parse_create_histogram_template_statement()
			elif self._match('NICKNAME'):
				self._parse_create_nickname_statement()
			elif self._match('ROLE'):
				self._parse_create_role_statement()
			elif self._match_sequence(['SECURITY', 'LABEL', 'COMPONENT']):
				self._parse_create_security_label_component_statement()
			elif self._match_sequence(['SECURITY', 'LABEL']):
				self._parse_create_security_label_statement()
			elif self._match_sequence(['SECURITY', 'POLICY']):
				self._parse_create_security_policy_statement()
			elif self._match_sequence(['SERVICE', 'CLASS']):
				self._parse_create_service_class_statement()
			elif self._match('SERVER'):
				self._parse_create_server_statement()
			elif self._match('THRESHOLD'):
				self._parse_create_threshold_statement()
			elif self._match_sequence(['TRUSTED', 'CONTEXT']):
				self._parse_create_trusted_context_statement()
			elif self._match_sequence(['TYPE', 'MAPPING']):
				self._parse_create_type_mapping_statement()
			elif self._match_sequence(['USER', 'MAPPING']):
				self._parse_create_user_mapping_statement()
			elif self._match('VARIABLE'):
				self._parse_create_variable_statement()
			elif self._match_sequence(['WORK', 'ACTION', 'SET']):
				self._parse_create_work_action_set_statement()
			elif self._match_sequence(['WORK', 'CLASS', 'SET']):
				self._parse_create_work_class_set_statement()
			elif self._match('WORKLOAD'):
				self._parse_create_workload_statement()
			elif self._match('WRAPPER'):
				self._parse_create_wrapper_statement()
			else:
				tbspacetype = self._match_one_of([
					'REGULAR',
					'LONG',
					'LARGE',
					'TEMPORARY',
					'USER',
					'SYSTEM',
				])[1]
				if tbspacetype:
					if tbspacetype in ('USER', 'SYSTEM'):
						self._expect('TEMPORARY')
					elif tbspacetype == 'TEMPORARY':
						tbspacetype = 'SYSTEM'
					elif tbspacetype == 'LONG':
						tbspacetype = 'LARGE'
					self._expect('TABLESPACE')
					self._parse_create_tablespace_statement(tbspacetype)
				else:
					self._expected_one_of([
						'ALIAS',
						'AUDIT',
						'BUFFERPOOL',
						'DATABASE',
						'DISTINCT',
						'EVENT',
						'FUNCTION',
						'INDEX',
						'NICKNAME',
						'NODEGROUP',
						'PROCEDURE',
						'ROLE',
						'SECURITY',
						'SEQUENCE',
						'SERVER',
						'SERVICE',
						'TABLE',
						'TABLESPACE',
						'THRESHOLD',
						'TRIGGER',
						'TRUSTED',
						'TYPE',
						'UNIQUE',
						'USER',
						'VARIABLE',
						'VIEW',
						'WORK',
						'WORKLOAD',
						'WRAPPER',
					])
		elif self._match('DELETE'):
			self._parse_delete_statement()
		elif self._match('DROP'):
			self._parse_drop_statement()
		elif self._match_sequence(['DECLARE', 'GLOBAL', 'TEMPORARY', 'TABLE']):
			self._parse_declare_global_temporary_table_statement()
		elif self._match('DECLARE'):
			self._parse_declare_cursor_statement()
		elif self._match('EXPLAIN'):
			self._parse_explain_statement()
		elif self._match_sequence(['FLUSH', 'OPTIMIZATION', 'PROFILE', 'CACHE']):
			self._parse_flush_optimization_profile_cache_statement()
		elif self._match_sequence(['FREE', 'LOCATOR']):
			self._parse_free_locator_statement()
		elif self._match('GRANT'):
			self._parse_grant_statement()
		elif self._match('INSERT'):
			self._parse_insert_statement()
		elif self._match_sequence(['LOCK', 'TABLE']):
			self._parse_lock_table_statement()
		elif self._match('MERGE'):
			self._parse_merge_statement()
		elif self._match_sequence(['REFRESH', 'TABLE']):
			self._parse_refresh_table_statement()
		elif self._match('RELEASE'):
			self._match('TO')
			self._expect('SAVEPOINT')
			self._parse_release_savepoint_statement()
		elif self._match_sequence(['RENAME', 'TABLESPACE']):
			self._parse_rename_tablespace_statement()
		elif self._match('RENAME'):
			self._parse_rename_statement()
		elif self._match('REVOKE'):
			self._parse_revoke_statement()
		elif self._match('ROLLBACK'):
			self._parse_rollback_statement()
		elif self._match('SAVEPOINT'):
			self._parse_savepoint_statement()
		elif self._match_sequence(['SET', 'INTEGRITY']):
			self._parse_set_integrity_statement()
		elif self._match('SET'):
			self._parse_set_statement()
		elif self._match_sequence(['TRANSFER', 'OWNERSHIP']):
			self._parse_transfer_ownership_statement()
		elif self._match('UPDATE'):
			self._parse_update_statement()
		else:
			self._parse_select_statement()

	def parse_routine_prototype(self, tokens):
		"""Parses a routine prototype"""
		# It's a bit of hack sticking this here. This method doesn't really
		# belong here and should probably be in a sub-class (it's only used
		# for syntax highlighting function prototypes in the documentation
		# system)
		self._parse_init(tokens)
		# Skip leading whitespace
		if self._token(self._index)[0] in (COMMENT, WHITESPACE):
			self._index += 1
		self._parse_function_name()
		# Parenthesized parameter list is mandatory
		self._expect('(', prespace=False)
		if not self._match(')'):
			while True:
				self._match_one_of(['IN', 'OUT', 'INOUT'])
				self._save_state()
				try:
					self._expect(IDENTIFIER)
					self._parse_datatype()
				except ParseError:
					self._restore_state()
					self._parse_datatype()
				else:
					self._forget_state()
				if not self._match(','):
					break
			self._expect(')')
		# Parse the return type
		if self._match('RETURNS'):
			if self._match_one_of(['ROW', 'TABLE']):
				self._expect('(')
				self._parse_ident_type_list()
				self._expect(')')
			else:
				self._parse_datatype()
		self._parse_finish()
		return self._output
