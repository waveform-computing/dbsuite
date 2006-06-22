#!/bin/env python
# $Header$
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
from sql.dialects import *
from sql.tokenizer import *

# Custom token types used by the formatter
(
	DATATYPE,  # Datatypes (e.g. VARCHAR) converted from KEYWORD or IDENTIFIER
	REGISTER,  # Special registers (e.g. CURRENT DATE) converted from KEYWORD or IDENTIFIER
	STATEMENT, # Statement terminator
	INDENT,    # Whitespace indentation at the start of a line
	VALIGN,    # Whitespace indentation within a line to vertically align blocks of text
	VAPPLY,    # Mark the end of a run of VALIGN tokens
) = newTokens(6)

# Token labels used for formatting error messages
TOKEN_LABELS = {
	EOF:        '<eof>',
	WHITESPACE: '<space>',
	KEYWORD:    'keyword',
	OPERATOR:   'operator',
	IDENTIFIER: 'identifier',
	REGISTER:   'register',
	DATATYPE:   'datatype',
	COMMENT:    'comment',
	NUMBER:     'number',
	STRING:     'string',
	TERMINATOR: '<terminator>',
	STATEMENT:  '<statement-end>',
}

# Standard size suffixes and multipliers
SUFFIX_KMG = {
	'K': 1024**1,
	'M': 1024**2,
	'G': 1024**3,
}

class Error(Exception):
	"""Base class for errors in this module"""

	def __init__(self, msg=''):
		"""Initializes an instance of the exception with an optional message"""
		Exception.__init__(self, msg)
		self.message = msg
	
	def __repr__(self):
		"""Outputs a representation of the exception"""
		return self.message

	__str__ = __repr__

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
		sourcelines = ''.join([s for (_, _, s, _, _) in self.source]).splitlines()
		marker = ''.join([{'\t': '\t'}.get(c, ' ') for c in sourcelines[self.line-1][:self.col-1]]) + '^'
		sourcelines.insert(self.line, marker)
		i = self.line - 5
		if i < 0: i = 0
		context = '\n'.join(sourcelines[i:self.line + 5])
		# Format the message with the context
		return ('%s:\n'
				'line   : %d\n'
				'column : %d\n'
				'context:\n%s' % (self.message, self.line, self.col, context))

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
	SQLParser or CLPParser depending on your needs. Both the "concrete" parser
	operate in the same manner (as they are derived from this base class),
	described below:

	The class accepts input from one of the tokenizers in the sqltokenizer
	unit, which in the form of a list of tokens, where tokens are tuples with
	the following structure:

		(token_type, token_value, token_source, line, column)

	In other words, this class accepts the output of the SQLTokenizer class in
	the tokenizer unit. To use the class simply pass such a list to the parse
	method. The method will return a list of tokens (just like the list of
	tokens provided as input, but reformatted).

	The token_type element gives the general "family" of the token (such as
	OPERATOR, IDENTIFIER, etc), while the token_value element provides the
	specific type of the token (e.g. "=", "OR", "DISTINCT", etc). The code in
	these classes typically uses "partial" tokens to match against "complete"
	tokens in the source. For example, instead of trying to match on the
	token_source element (which may vary in case), this class often matches
	token on the first two elements:

		(KEYWORD, "OR", "or", 7, 13)[:2] == (KEYWORD, "OR")

	A set of internal utility methods are used to simplify this further. See
	the match and expect methods in particular. The numerous parseX methods in
	the unit define the grammar of the SQL language being parsed.
	"""

	def __init__(self):
		"""Initializes an instance of the class"""
		super(BaseFormatter, self).__init__()
		self.indent = " "*4 # Default indent is 4 spaces
		self.debugging = 0
	
	def _insert_output(self, token, index):
		"""Inserts the specified token into the output.

		This utility routine is used by _newline() and other formatting routines
		to insert tokens into the output sometime prior to the current end of
		the output. The index parameter (which is always negative) specifies
		how many non-junk tokens are to be skipped over before inserting the
		specified token.

		Note that the method takes care to preserve the invariants that the
		state save/restore methods rely upon.
		"""
		if not index:
			self._output.append(token)
		else:
			i = -1
			while True:
				while self._output[i][0] in (COMMENT, WHITESPACE):
					i -= 1
				index += 1
				if index >= 0:
					break
			# Check that the invariant is preserved (see _save_state())
			assert (len(self._statestack) == 0) or (len(self._output) + i >= self._statestack[-1][2])
			self._output.insert(i, token)

	def _newline(self, index=0):
		"""Adds an INDENT token to the output.

		The _newline() method is called to start a new line in the output. It
		does this by appending (or inserting, depending on the index parameter)
		an INDENT token to the output list. Such a token starts a new line,
		indented to the current indentation level.
		"""
		token = (INDENT, self._level, "\n" + self.indent * self._level)
		self._insert_output(token, index)

	def _indent(self, index=0):
		"""Increments the indentation level and starts a new line."""
		self._level += 1
		self._newline(index)

	def _outdent(self, index=0):
		"""Decrements the indentation level and starts a new line."""
		self._level -= 1
		# Stop two or more consecutive outdent() calls from leaving blank lines
		if self._output[-1][0] == INDENT:
			del self._output[-1]
		self._newline(index)
	
	def _valign(self, index=0):
		"""Inserts a VALIGN token into the output."""
		token = (VALIGN, None, '')
		self._insert_output(token, index)
	
	def _vapply(self, index=0):
		"""Inserts a VAPPLY token into the output."""
		token = (VAPPLY, None, '')
		self._insert_output(token, index)

	def _save_state(self):
		"""Saves the current state of the parser on a stack for later retrieval."""
		# An invariant observed throughout this class (and its descendents) is
		# that the output list NEVER shrinks, and is only ever appended to.
		# Hence, to be able to roll back to a prior state, we don't need to
		# store the entire output list, merely its length will suffice.
		#
		# Note that the _newline() method does *insert* rather than append
		# tokens (when called with a negative index).  However, provided the
		# tokens are inserted *after* the in the output list where the state
		# was last saved, this also maintains the invariant (the _newline()
		# method includes an assertion to ensure this is the case).
		self._statestack.append((self._index, self._level, len(self._output)))

	def _restore_state(self):
		"""Restores the state of the parser from the head of the save stack."""
		(self._index, self._level, output_len) = self._statestack.pop()
		del self._output[output_len:]

	def _forget_state(self):
		"""Destroys the saved state at the head of the save stack."""
		self._statestack.pop()
	
	def _token(self, index):
		"""Returns the token at the specified index, or an token EOF."""
		try:
			return self._tokens[index]
		except IndexError:
			return self._tokens[-1]

	def _cmp_tokens(self, token, template):
		"""Compares a token against a partial template token.

		If the template token is just a string, it will match a KEYWORD,
		OPERATOR, or IDENTIFIER token with the same value (the second element
		of a token).  If a partial token is an integer (like the KEYWORD,
		IDENTIFIER, etc.  constants) it will match a token with the same type,
		with the following exceptions:

		* IDENTIFIER will also match KEYWORD tokens (to allow keywords to be
		  used as identifiers)
		* DATATYPE and REGISTER will match KEYWORD or IDENTIFIER (DATATYPE and
		  REGISTER tokens should never appear in the input and this allows
		  keywords like CHARACTER or identifiers like DECIMAL to be treated as
		  datatypes, and things like CURRENT DATE to be treated as special
		  registers)
		* STATEMENT will match TERMINATOR (STATEMENT tokens are terminators
		  but specific to a top-level SQL statement or CLP command)

		If a partial token is a tuple it will match a token with the same
		element values up to the number of elements in the partial token.

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
			elif token[0] == TERMINATOR and template == STATEMENT:
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
			assert False, "Invalid template token"
	
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

	def _match(self, template):
		"""Attempt to match the current token against a template token.
		
		Matches the provided template token against the current token in the
		stream. If the match is successful the current position is moved
		forward to the next non-junk token, and the (potentially transformed)
		matched token is returned. Otherwise, None is returned and the current
		position is not moved.
		"""
		t = self._cmp_tokens(self._token(self._index), template)
		if not t:
			return None
		self._output.append(t)
		self._index += 1
		while self._token(self._index)[0] in (COMMENT, WHITESPACE):
			self._output.append(self._token(self._index))
			self._index += 1
		return t

	def _match_sequence(self, templates):
		"""Attempt to match the next sequence of tokens against a list of template tokens.

		Matches the list of non-junk tokens (tokens which are not WHITESPACE or
		COMMENT) from the current position up to the length of the templates
		list. The _cmp_tokens() method is used for matching. Refer to that
		method for the matching algorithm.

		The method returns the list of the non-junk tokens that were matched.
		If a match is found, the output list and current token position are
		updated. Otherwise, no changes to the internal state are made
		(regardless of the length of the list of tokens to match).
		"""
		r = []
		i = self._index
		for template in templates:
			# Attempt to match the current token against the expected token
			t = self._cmp_tokens(self._token(i), template)
			if not t:
				return None
			# If it matched, append it to the output list
			r.append(t)
			i += 1
			# Skip comments and whitespace (adding them to the output list too)
			while self._token(i)[0] in (COMMENT, WHITESPACE):
				r.append(self._token(i))
				i += 1
		# If we've completed the loop, we've got a match so update _output and
		# _index with the new values
		self._output.extend(r)
		self._index = i
		# Strip WHITESPACE and COMMENT tokens from the return list
		return [t for t in r if t[0] not in (COMMENT, WHITESPACE)]

	def _match_one_of(self, templates):
		"""Attempt to match the current token against one of several templates.

		Matches the current token against one of several possible
		partial tokens provided in a list. If a match is found, the method
		returns the matched token, and moves the current position forward to
		the next non-junk token. If no match is found, the method returns None.
		"""
		for template in templates:
			t = self._cmp_tokens(self._token(self._index), template)
			if t:
				# If a match is found, update _output, and skip to the next
				# non-junk token
				self._output.append(t)
				self._index += 1
				while self._token(self._index)[0] in [COMMENT, WHITESPACE]:
					self._output.append(self._token(self._index))
					self._index += 1
				return t
		return None

	def _expect(self, template):
		"""Match the current token against a template token, or raise an error.

		The _expect() method is essentially the same as _match() except that if
		a match is not found, a ParseError exception is raised stating that the
		parser "expected" the specified token, but found something else.
		"""
		result = self._match(template)
		if not result:
			self._expected(template)
		return result

	def _expect_sequence(self, templates):
		"""Match the next sequence of tokens against a list of templates, or raise an error.

		The _expect_sequence() method is equivalent to the _match_sequence()
		method except that if a match is not found, a ParseError exception is
		raised with a message indicating that a certain sequence was expected,
		but something else was found.
		"""
		result = self._match_sequence(templates)
		if not result:
			self._expected_sequence(templates)
		return result

	def _expect_one_of(self, templates):
		"""Match the current token against one of several templates, or raise an error.

		The _expect_one_of() method is equivalent to the _match_one_of() method
		except that if a match is not found, a ParseError exception is raised
		with a message indicating that one of several possibilities was
		expected, but something else was found.
		"""
		result = self._match_one_of(templates)
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

	def _format_token(self, t):
		"""Reformats tokens for output"""
		
		def quote_str(s, qchar):
			"""Quote a string, doubling all quotation characters within it"""
			ctrlchars = set(chr(c) for c in xrange(32))
			if ctrlchars & set(s):
				# If the string contains non-printable control characters,
				# format it as a hexstring
				return 'X%s%s%s' % (qchar, ''.join('%.2X' % (ord(c),) for c in s), qchar)
			else:
				return '%s%s%s' % (qchar, s.replace(qchar, qchar*2), qchar)
		
		def format_ident(ident):
			"""Format an SQL identifier with quotes if required"""
			identchars = set(ibmdb2udb_identchars)
			quotedident = not ident[0] in (identchars - set('0123456789'))
			if not quotedident:
				for c in ident[1:]:
					if not c in identchars:
						quotedident = True
						break
			if quotedident:
				return quote_str(ident, '"')
			else:
				return ident
		
		def format_param(param):
			"""Format a parameter with quotes if required"""
			if param is None:
				return '?'
			else:
				return ':%s' % (format_ident(param))
			
		# Override this method in descendent classes to transform the token in
		# whatever manner you wish. Return the transformed token without the
		# line and column elements (the last two) as these will be recalculated
		# in _recalc_positions(). To remove a token from the output, return
		# None.
		if t[0] == IDENTIFIER:
			return (t[0], t[1], format_ident(t[1]))
		elif t[0] == REGISTER:
			return (t[0], t[1], format_ident(t[1]))
		elif t[0] == DATATYPE:
			return (t[0], t[1], format_ident(t[1]))
		elif t[0] == PARAMETER:
			return (t[0], t[1], format_param(t[1]))
		elif t[0] == KEYWORD:
			return (t[0], t[1], t[1])
		elif t[0] == WHITESPACE:
			return (t[0], None, ' ')
		elif t[0] == COMMENT:
			return (t[0], t[1], '/*%s*/' % (t[1]))
		elif t[0] == NUMBER:
			return (t[0], t[1], str(t[1]))
		elif t[0] == STRING:
			return (t[0], t[1], quote_str(t[1], "'"))
		elif t[0] == TERMINATOR:
			return (t[0], None, ';')
		elif t[0] == STATEMENT:
			return (t[0], None, '!')
		elif t[0] == INDENT:
			return (WHITESPACE, None, '\n' + self.indent*t[1])
		else:
			return t[:3]
	
	def _reformat_output(self):
		"""Reformats all output tokens with _format_token()"""
		newoutput = []
		for token in self._output:
			token = self._format_token(token)
			if token:
				newoutput.append(token)
		self._output = newoutput
	
	def _convert_valign(self):
		"""Converts the first VALIGN token on each line into a WHITESPACE token"""
		result = False
		indexes = []
		aligncol = 0
		i = 0
		while i < len(self._output):
			(tokentype, _, _, line, col) = self._output[i]
			if tokentype == VALIGN:
				indexes.append(i)
				aligncol = max(aligncol, col)
				# Skip to the next line (to ignore any further VALIGN tokens on
				# this line)
				while (self._output[i][3] == line) and (self._output[i][0] != VAPPLY):
					i += 1
			elif tokentype == VAPPLY:
				if indexes:
					result = True
					for j in indexes:
						# Convert each VALIGN token into an aligned WHITESPACE
						# token
						(_, _, _, line, col) = self._output[j]
						self._output[j] = (WHITESPACE, None, ' '*(aligncol - col), line, col)
					indexes = []
					aligncol = 0
					i += 1
				else:
					# No more VALIGN tokens found in the range, so remove the
					# VAPPLY token (no need to increment i here)
					del self._output[i]
			else:
				i += 1
		return result
	
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

	def _parse_init(self, tokens):
		"""Sets up the parser with the specified tokens as input"""
		self._statestack = list()
		# Check that newline_split wasn't used in the tokenizer
		if isinstance(tokens[0], list):
			raise Error('Tokens must not be organized by line')
		self._tokens = tokens
		self._index = 0
		self._output = []
		self._level = 0
	
	def _parse_finish(self):
		"""Cleans up output tokens and recalculates line and column positions"""
		self._reformat_output()
		self._recalc_positions()
		while self._convert_valign():
			self._recalc_positions()

	def _parse_top(self):
		"""Top level of the parser"""
		# Override this method in descendents to parse a statement (or
		# whatever is at the top of the parse tree)
		pass

	def parse(self, tokens):
		"""Parses an arbitrary statement or script"""
		self._parse_init(tokens)
		while True:
			# Ignore leading whitespace and empty statements
			while self._token(self._index)[0] in (COMMENT, WHITESPACE, TERMINATOR):
				self._index += 1
			# If not at EOF, parse a statement
			if not self._match(EOF):
				# Output some debugging info (if debugging is set)
				if self.debugging:
					preview = ''.join([token[2] for token in self._tokens[self._index:self._index + 10]])
					preview = re.sub(r'[\t\n ]+', ' ', preview).strip()
					print 'Parsing top-level "%s..."' % (preview,)
				self._parse_top()
				# Check for terminator (use STATEMENT to mark any terminator
				# found as a top-level statement terminator)
				self._expect(STATEMENT)
				# If the state stack has any entries something has gone wrong
				# (some method has saved state but forgotten to clean it up
				# before exiting)
				assert len(self._statestack) == 0
				# Reset the indent level and leave a blank line
				self._level = 0
				self._newline()
				self._newline()
			else:
				break
		self._parse_finish()
		return self._output

class SQLFormatter(BaseFormatter):
	"""Reformatter which breaks up and re-indents SQL.

	This class is, at its core, a full blown SQL language parser that
	understands many common SQL DML and DDL commands (from the basic ones like
	INSERT, UPDATE, DELETE, SELECT, to the more DB2 specific ones such as
	CREATE TABLESPACE, CREATE FUNCTION, and dynamic compound statements).
	"""

	def __init__(self):
		super(SQLFormatter, self).__init__()

	def _parse_top(self):
		# Override _parse_top to make a 'statement' the top of the parse tree
		self._parse_statement()

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
	_parse_trigger_name = _parse_subschema_name
	_parse_index_name = _parse_subschema_name
	_parse_routine_name = _parse_subschema_name
	_parse_function_name = _parse_subschema_name
	_parse_procedure_name = _parse_subschema_name
	_parse_method_name = _parse_subschema_name
	_parse_sequence_name = _parse_subschema_name
	_parse_type_name = _parse_subschema_name

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
			if not self._match('('):
				return None
		else:
			self._expect('(')
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
				(REGISTER, 'PATH'),
				(REGISTER, 'SCHEMA'),
				(REGISTER, 'SERVER'),
				(REGISTER, 'TIME'),
				(REGISTER, 'TIMESTAMP'),
				(REGISTER, 'TIMEZONE'),
				(REGISTER, 'USER'),
			]):
				pass
			elif self._match((REGISTER, 'DEFAULT')):
				self._expect_sequence([(REGISTER, 'TRANSFORM'), (REGISTER, 'GROUP')])
			elif self._match((REGISTER, 'EXPLAIN')):
				self._expect_one_of([(REGISTER, 'MODE'), (REGISTER, 'SNAPSHOT')])
			elif self._match((REGISTER, 'LOCK')):
				self._expect((REGISTER, 'TIMEOUT'))
			elif self._match((REGISTER, 'MAINTAINED')):
				self._expect_sequence([
					(REGISTER, 'TABLE'),
					(REGISTER, 'TYPES'),
					(REGISTER, 'FOR'),
					(REGISTER, 'OPTIMIZATION')
				])
			elif self._match((REGISTER, 'PACKAGE')):
				self._expect((REGISTER, 'PATH'))
			elif self._match((REGISTER, 'QUERY')):
				self._expect((REGISTER, 'OPTIMIZATION'))
			elif self._match((REGISTER, 'REFRESH')):
				self._expect((REGISTER, 'AGE'))
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
				(REGISTER, 'USER'),
				(REGISTER, 'SYSTEM_USER'),
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
			self._match_sequence([(DATATYPE, 'SYSIBM'), '.'])
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
			elif self._match_one_of([(DATATYPE, 'DEC'), (DATATYPE, 'DECIMAL')]):
				typename = 'DECIMAL'
				if self._match('('):
					size = self._expect(NUMBER)[1]
					if self._match(','):
						scale = self._expect(NUMBER)[1]
					self._expect(')')
			elif self._match_one_of([(DATATYPE, 'NUM'), (DATATYPE, 'NUMERIC')]):
				typename = 'NUMERIC'
				if self._match('('):
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
				self._parse_expression1()
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
			self._parse_full_select1()
			self._outdent()
		except ParseError:
			# If that fails, rewind and parse a tuple of expressions
			self._restore_state()
			self._parse_expression_list(allowdefault)
		else:
			self._forget_state()

	# EXPRESSIONS and PREDICATES #############################################
	
	def _parse_predicate1(self, linebreaks=True):
		"""Parse low precedence predicate operators (OR)"""
		self._parse_predicate2(linebreaks)
		while True:
			if self._match('OR'):
				if linebreaks: self._newline(-1)
				self._parse_predicate2(linebreaks)
			else:
				break

	def _parse_predicate2(self, linebreaks=True):
		"""Parse medium precedence predicate operators (AND)"""
		self._parse_predicate3(linebreaks)
		while True:
			if self._match('AND'):
				if linebreaks: self._newline(-1)
				self._parse_predicate3(linebreaks)
			else:
				break

	def _parse_predicate3(self, linebreaks=True):
		"""Parse high precedence predicate operators (BETWEEN, IN, etc.)"""
		# Ambiguity: Open parenthesis could indicate a grouping of predicates
		# or expressions
		self._save_state()
		try:
			if self._match('('):
				self._parse_predicate1(linebreaks)
				self._expect(')')
			elif self._match('EXISTS'):
				self._expect('(')
				self._parse_full_select1()
				self._expect(')')
			else:
				raise ParseBacktrack()
		except ParseError:
			# If that fails, or we don't match an open parenthesis, parse an
			# ordinary high-precedence predicate operator
			self._restore_state()
			self._parse_expression1()
			if self._match('NOT'):
				if self._match('LIKE'):
					self._parse_expression1()
				elif self._match('BETWEEN'):
					self._parse_expression1()
					self._expect('AND')
					self._parse_expression1()
				elif self._match('IN'):
					if self._match('('):
						self._parse_tuple()
						self._expect(')')
					else:
						self._parse_expression1()
				else:
					self._parse_predicate3(linebreaks)
			elif self._match('LIKE'):
				self._parse_expression1()
			elif self._match('BETWEEN'):
				self._parse_expression1()
				self._expect('AND')
				self._parse_expression1()
			elif self._match('IN'):
				if self._match('('):
					self._parse_tuple()
					self._expect(')')
				else:
					self._parse_expression1()
			elif self._match('IS'):
				self._match('NOT')
				self._expect('NULL')
			elif self._match_one_of(['=', '<', '>', '<>', '<=', '>=']):
				if self._match_one_of(['SOME', 'ANY', 'ALL']):
					self._expect('(')
					self._parse_full_select1()
					self._expect(')')
				else:
					self._parse_expression1()
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
		else:
			self._forget_state()

	def _parse_expression1(self):
		"""Parse low precedence expression operators (+, -, ||, CONCAT)"""
		self._parse_expression2()
		while True:
			if self._match('+'):
				self._parse_expression2()
			elif self._match('-'):
				self._parse_expression2()
			elif self._match('||'):
				self._parse_expression2()
			elif self._match('CONCAT'):
				self._parse_expression2()
			else:
				break

	def _parse_expression2(self):
		"""Parse medium precedence expression operators (*, /)"""
		self._parse_expression3()
		while True:
			if self._match('*'):
				self._parse_expression1()
			elif self._match('/'):
				self._parse_expression1()
			else:
				break

	def _parse_expression3(self):
		"""Parse high precedence expression operators (literals, etc.)"""
		if self._match('('):
			self._parse_tuple()
			self._expect(')')
		elif self._match('+'): # Unary +
			self._parse_expression3()
		elif self._match('-'): # Unary -
			self._parse_expression3()
		elif self._match('CAST'):
			self._parse_cast_expression()
		elif self._match('CASE'):
			if self._match('WHEN'):
				self._indent(-1)
				self._parse_searched_case()
			else:
				self._parse_simple_case()
		elif self._match_one_of([NUMBER, STRING, PARAMETER, 'NULL']):
			pass
		else:
			self._save_state()
			try:
				# Try and parse an aggregation function
				self._parse_aggregate_function_call()
			except ParseError:
				self._restore_state()
				self._save_state()
				try:
					# Try and parse a scalar function
					self._parse_scalar_function_call()
				except ParseError:
					self._restore_state()
					self._save_state()
					try:
						# Try and parse a special register
						self._parse_special_register()
					except ParseError:
						self._restore_state()
						# Parse a normal column reference
						self._parse_column_name()
					else:
						self._forget_state()
				else:
					self._forget_state()
			else:
				self._forget_state()
		# Parse an optional interval suffix
		self._match_one_of([
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
		])

	def _parse_aggregate_function_call(self):
		"""Parses an aggregate function with it's optional arg-prefix"""
		# Parse the optional SYSIBM schema prefix
		self._match_sequence(['SYSIBM', '.'])
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
		self._expect('(')
		if aggfunc in ('COUNT', 'COUNT_BIG') and self._match('*'):
			# COUNT and COUNT_BIG can take '*' as a sole parameter
			pass
		else:
			# Aggregation functions have an optional ALL/DISTINCT argument prefix
			self._match_one_of(['ALL', 'DISTINCT'])
			# And only take a single expression as an argument
			self._parse_expression1()
		self._expect(')')
		# Parse an OLAP suffix if one exists
		if self._match('OVER'):
			self._parse_olap_function_call()

	def _parse_scalar_function_call(self):
		"""Parses a scalar function call with all its arguments"""
		self._parse_function_name()
		self._expect('(')
		if not self._match(')'):
			self._parse_expression_list()
			self._expect(')')
		# Parse an OLAP suffix if one exists
		if self._match('OVER'):
			self._parse_olap_function_call()
	
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
	
	def _parse_olap_function_call(self):
		"""Parses the aggregation suffix in an OLAP-function call"""
		# OVER already matched
		self._expect('(')
		if self._match('PARTITION'):
			self._expect('BY')
			self._parse_expression_list()
		if self._match('ORDER'):
			self._expect('BY')
			while True:
				if self._match('ORDER'):
					self._expect('OF')
					self._parse_table_name()
				else:
					self._parse_expression1()
					if self._match_one_of(['ASC', 'DESC']):
						if self._match('NULLS'):
							self._expect_one_of(['FIRST', 'LAST'])
				if not self._match((OPERATOR, ',')):
					break
		if self._match_one_of(['ROWS', 'RANGE']):
			if not self._parse_olap_range(True):
				self._expect('BETWEEN')
				self._parse_olap_range(False)
				self._expect('AND')
				self._parse_olap_range(False)
		self._expect(')')
	
	def _parse_cast_expression(self):
		"""Parses a CAST() expression"""
		# CAST already matched
		self._expect('(')
		self._parse_expression1()
		self._expect('AS')
		self._parse_datatype()
		self._expect(')')

	def _parse_searched_case(self):
		"""Parses a searched CASE expression (CASE WHEN expression...)"""
		# CASE WHEN already matched
		# Parse all WHEN cases
		while True:
			self._parse_predicate1(linebreaks=False) # WHEN Search condition
			self._expect('THEN')
			self._parse_expression1() # THEN Expression
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
		self._parse_expression1() # ELSE Expression
		self._outdent()
		self._expect('END')

	def _parse_simple_case(self):
		"""Parses a simple CASE expression (CASE expression WHEN value...)"""
		# CASE already matched
		# Parse the CASE Expression
		self._parse_expression1() # CASE Expression
		# Parse all WHEN cases
		self._indent()
		self._expect('WHEN')
		while True:
			self._parse_expression1() # WHEN Expression
			self._expect('THEN')
			self._parse_expression1() # THEN Expression
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
		self._parse_expression1() # ELSE Expression
		self._outdent()
		self._expect('END')

	def _parse_column_expression(self):
		"""Parses an expression representing a column in a SELECT expression"""
		if not self._match_sequence([IDENTIFIER, '.', '*']):
			self._parse_expression1()
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
			self._parse_expression1()
	
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
				self._parse_expression1()
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
				altSyntax = False
			elif self._match_one_of(['ROLLUP', 'CUBE']):
				self._parse_super_group()
				altSyntax = False
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

	def _parse_sub_select(self):
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
		self._expect('FROM')
		self._indent()
		while True:
			self._parse_table_ref1()
			if not self._match(','):
				break
			else:
				self._newline()
		self._outdent()
		if self._match('WHERE'):
			self._indent()
			self._parse_predicate1()
			self._outdent()
		if self._match('GROUP'):
			self._expect('BY')
			self._indent()
			self._parse_group_by()
			self._outdent()
		if self._match('HAVING'):
			self._indent()
			self._parse_predicate1()
			self._outdent()
		if self._match('ORDER'):
			self._expect('BY')
			self._indent()
			while True:
				self._parse_expression1()
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
			# position
			elif not self._peek_one_of([
					'WHERE',
					'GROUP',
					'HAVING',
					'ORDER',
					'FETCH',
					'UNION',
					'INTERSECT',
					'EXCEPT',
					'WITH',
					'ON',
					'USING',
					'SET',
				]):
				self._expect(IDENTIFIER)
			# Parse optional column aliases
			if self._match('('):
				self._parse_ident_list()
				self._expect(')')

	def _parse_table_function_call(self):
		"""Parses a table function call with all its arguments"""
		# Syntactically, this is identical to a scalar function call
		self._parse_scalar_function_call()

	def _parse_values_clause(self, allowdefault=False):
		"""Parses a VALUES expression"""
		# VALUES already matched
		self._indent()
		while True:
			if self._match('('):
				self._parse_expression_list(allowdefault, newlines=True)
				self._expect(')')
			else:
				if not (allowdefault and self._match('DEFAULT')):
					self._parse_expression1()
			if not self._match(','):
				break
		self._outdent()

	def _parse_table_ref1(self):
		"""Parses join operators in a table-reference"""
		self._parse_table_ref2()
		while True:
			if self._match('INNER'):
				self._newline(-1)
				self._expect('JOIN')
				self._parse_table_ref2()
				self._parse_join_condition()
			elif self._match_one_of(['LEFT', 'RIGHT', 'FULL']):
				self._newline(-1)
				self._match('OUTER')
				self._expect('JOIN')
				self._parse_table_ref2()
				self._parse_join_condition()
			elif self._match('JOIN'):
				self._newline(-1)
				self._parse_table_ref2()
				self._parse_join_condition()
			else:
				break

	def _parse_table_ref2(self):
		"""Parses literal table references or functions in a table-reference"""
		# Ambiguity: A table or schema can be named TABLE, FINAL, OLD, etc.
		reraise = False
		self._save_state()
		try:
			if self._match('('):
				# Ambiguity: Open-parenthesis could indicate a full-select or a
				# join group
				self._save_state()
				try:
					# Try and parse a full-select
					self._parse_full_select1()
					reraise = True
					self._expect(')')
					self._parse_table_correlation(optional=False)
				except ParseError:
					# If it fails, rewind and try a join group instead
					self._restore_state()
					if reraise: raise
					self._parse_table_ref1()
					self._expect(')')
				else:
					self._forget_state()
			elif self._match('TABLE'):
				self._expect('(')
				# Ambiguity: TABLE() can indicate a table-function call or a
				# nested table expression
				self._save_state()
				try:
					# Try and parse a full-select
					self._parse_full_select1()
				except ParseError:
					# If it fails, rewind and try a table function call instead
					self._restore_state()
					self._parse_table_function_call()
				else:
					self._forget_state()
				reraise = True
				self._expect(')')
				self._parse_table_correlation(optional=False)
			elif self._match_one_of(['FINAL', 'NEW']):
				self._expect('TABLE')
				self._expect('(')
				if self._expect_one_of(['INSERT', 'UPDATE'])[1] == 'INSERT':
					self._parse_insert_statement()
				else:
					self._parse_update_statement()
				reraise = True
				self._expect(')')
				self._parse_table_correlation(optional=True)
			elif self._match('OLD'):
				self._expect('TABLE')
				self._expect('(')
				if self._expect_one_of(['UPDATE', 'DELETE'])[1] == 'DELETE':
					self._parse_delete_statement()
				else:
					self._parse_update_statement()
				reraise = True
				self._expect(')')
				self._parse_table_correlation(optional=True)
			else:
				raise ParseBacktrack()
		except ParseError:
			# If the above fails, rewind and try a simple table reference
			self._restore_state()
			if reraise: raise
			self._parse_table_name()
			self._parse_table_correlation(optional=True)
		else:
			self._forget_state()

	def _parse_join_condition(self):
		"""Parses the condition on an SQL-92 style join"""
		# This method can be extended to support USING(ident-list) if this
		# if ever added to DB2 (see PostgreSQL)
		self._indent()
		self._expect('ON')
		self._parse_predicate1()
		self._outdent()

	def _parse_full_select1(self, allowdefault=False):
		"""Parses set operators (low precedence) in a full-select expression"""
		self._parse_full_select2(allowdefault)
		while True:
			if self._match_one_of(['UNION', 'INTERSECT', 'EXCEPT']):
				self._newline(-1)
				self._match('ALL')
				self._newline()
				self._newline()
				self._parse_full_select2(allowdefault)
			else:
				break
		if self._match('ORDER'):
			self._expect('BY')
			while True:
				self._parse_expression1()
				self._match_one_of(['ASC', 'DESC'])
				if not self._match(','):
					break
		if self._match('FETCH'):
			self._expect('FIRST')
			self._match(NUMBER) # Row count is optional (defaults to 1)
			self._expect_one_of(['ROW', 'ROWS'])
			self._expect('ONLY')

	def _parse_full_select2(self, allowdefault=False):
		"""Parses relation generators (high precedence) in a full-select expression"""
		if self._match('('):
			self._parse_full_select1(allowdefault)
			self._expect(')')
		elif self._match('SELECT'):
			self._parse_sub_select()
		elif self._match('VALUES'):
			self._parse_values_clause(allowdefault)
		else:
			self._expected_one_of(['SELECT', 'VALUES', '('])

	def _parse_query(self, allowdefault=False):
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
				# Note that DEFAULT is *never* permitted in a CTE
				self._parse_full_select1(allowdefault=False)
				self._outdent()
				self._expect(')')
				if not self._match(','):
					break
				else:
					self._newline()
			self._newline()
		# Parse the actual full-select. DEFAULT may be permitted here if the
		# full-select turns out to be a VALUES statement
		self._parse_full_select1(allowdefault)

	# CLAUSES ################################################################

	def _parse_set_clause(self, allowdefault):
		"""Parses a SET clause"""
		# SET already matched
		while True:
			if self._match('('):
				# Parse tuple assignment
				self._parse_ident_list()
				self._expect_sequence([')', '=', '('])
				self._parse_tuple(allowdefault=True)
				self._expect(')')
			else:
				# Parse simple assignment
				self._expect_sequence([IDENTIFIER, '='])
				if not (allowdefault and self._match('DEFAULT')):
					self._parse_expression1()
			if not self._match(','):
				break

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
		while True:
			if not valid:
				break
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
	
	def _parse_column_definition(self, aligntypes=False):
		"""Parses a column definition in a CREATE TABLE statement"""
		# Parse a column definition
		self._expect(IDENTIFIER)
		if aligntypes:
			self._valign()
		self._parse_datatype()
		# Parse column options
		while True:
			if self._match('NOT'):
				self._expect('NULL')
			elif self._match('WITH'):
				self._expect('DEFAULT')
				self._save_state()
				try:
					self._parse_expression1()
				except ParseError:
					self._restore_state()
				else:
					self._forget_state()
			elif self._match('DEFAULT'):
				self._save_state()
				try:
					self._parse_expression1()
				except ParseError:
					self._restore_state()
				else:
					self._forget_state()
			elif self._match('GENERATED'):
				if self._expect_one_of(['ALWAYS', 'BY'])[1] == 'BY':
					self._expect('DEFAULT')
				self._expect('AS')
				if self._match('IDENTITY'):
					if self._match('('):
						self._parse_identity_options()
						self._expect(')')
				elif self._match('('):
					self._parse_expression1()
					self._expect(')')
				else:
					self._expected_one_of(['IDENTITY', '('])
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
			if self._match('('):
				self._expect(IDENTIFIER)
				self._expect(')')
			t = ['DELETE', 'UPDATE']
			for i in xrange(2):
				if self._match('ON'):
					t.remove(self._expect(t)[1])
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
			self._parse_predicate1()
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
			self._expect('(')
			self._parse_ident_list()
			self._expect(')')
			t = ['DELETE', 'UPDATE']
			for i in xrange(2):
				if self._match('ON'):
					t.remove(self._expect(t)[1])
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
			self._parse_predicate1()
			self._expect(')')
		else:
			self._expected_one_of([
				'CONSTRAINT',
				'PRIMARY',
				'UNIQUE',
				'FOREIGN',
				'CHECK'
			])

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
					self._parse_expression1()
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
						self._parse_expression1()
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

	def _parse_auth_list(self):
		"""Parses an authorization list in a GRANT or REVOKE statement"""
		# [TO|FROM] already matched
		while True:
			self._match_one_of(['USER', 'GROUP'])
			self._expect_one_of(['PUBLIC', IDENTIFIER])
			if not self._match(','):
				break

	def _parse_grant_revoke(self, grant):
		"""Parses the body of a GRANT or REVOKE statement"""
		# [GRANT|REVOKE] already matched
		tofrom = ['FROM', 'TO'][grant]
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
		]):
			self._expect_sequence(['ON', 'DATABASE', tofrom])
			self._parse_auth_list()
			if not grant and self._match('BY'):
				self._expect('ALL')
		elif self._match_one_of([
			'ALTERIN',
			'CREATEIN',
			'DROPIN',
		]):
			self._expect_sequence(['ON', 'SCHEMA', IDENTIFIER, tofrom])
			self._parse_auth_list()
			if grant and self._match('WITH'):
				self._expect_sequence(['GRANT', 'OPTION'])
			elif not grant and self._match('BY'):
				self._expect('ALL')
		elif self._match('CONTROL'):
			self._expect('ON')
			if self._match('INDEX'):
				self._expect_sequence([IDENTIFIER, tofrom])
				self._parse_auth_list()
				if not grant and self._match('BY'):
					self._expect('ALL')
			else:
				self._match('TABLE')
				self._parse_table_name()
				self._expect(tofrom)
				self._parse_auth_list()
				if grant and self._match('WITH'):
					self._expect_sequence(['GRANT', 'OPTION'])
				elif not grant and self._match('BY'):
					self._expect('ALL')
		elif self._match('USAGE'):
			self._expect_sequence(['ON', 'SEQUENCE'])
			self._parse_sequence_name()
			self._expect(tofrom)
			self._parse_auth_list()
			if grant and self._match('WITH'):
				self._expect_sequence(['GRANT', 'OPTION'])
			elif not grant:
				self._match('RESTRICT')
		elif self._match('ALTER'):
			self._expect('ON')
			if self._match('SEQUENCE'):
				self._parse_sequence_name()
				self._expect(tofrom)
				self._parse_auth_list()
				if grant and self._match('WITH'):
					self._expect_sequence(['GRANT', 'OPTION'])
				elif not grant:
					self._match('RESTRICT')
			else:
				self._match('TABLE')
				self._parse_table_name()
				self._expect(tofrom)
				self._parse_auth_list()
				if grant and self._match('WITH'):
					self._expect_sequence(['GRANT', 'OPTION'])
				elif not grant and self._match('BY'):
					self._expect('ALL')
		elif self._match('USE'):
			self._expect_sequence(['OF', 'TABLESPACE', IDENTIFIER, tofrom])
			self._parse_auth_list()
			if grant and self._match('WITH'):
				self._expect_sequence(['GRANT', 'OPTION'])
			elif not grant and self._match('BY'):
				self._expect('ALL')
		elif self._match('EXECUTE'):
			self._expect('ON')
			if self._match_one_of(['FUNCTION', 'PROCEDURE']):
				# Ambiguity: Can use schema.* or schema.name(prototype) here
				if not self._match('*') and not self._match_sequence([IDENTIFIER, '.', '*']):
					self._parse_routine_name()
					if self._match('('):
						while True:
							self._parse_datatype()
							if not self._match(','):
								break
						self._expect(')')
			elif self._match('SPECIFIC'):
				self._expect_one_of(['FUNCTION', 'PROCEDURE'])
				self._parse_routine_name()
			else:
				self._expected_one_of(['FUNCTION', 'PROCEDURE', 'SPECIFIC'])
			self._expect((KEYWORD, tofrom))
			self._parse_auth_list()
			if grant and self._match('WITH'):
				self._expect_sequence(['GRANT', 'OPTION'])
			elif not grant:
				if self._match('BY'):
					self._expect('ALL')
				self._expect('RESTRICT')
		else:
			if self._match('ALL'):
				self._match('PRIVILEGES')
			elif self._match_one_of(['REFERENCES', 'UPDATE']):
				if self._match('('):
					self._parse_ident_list()
					self._expect(')')
			elif self._match_one_of(['DELETE', 'INDEX', 'INSERT', 'SELECT']):
				pass
			else:
				self._expected_one_of([
					# Prefix of GRANT ... ON TABLE
					'ALL',
					'DELETE',
					'INDEX',
					'INSERT',
					'SELECT',
					'REFERENCES',
					'UPDATE',
					# Other possibilities from above
					'ALTER',
					'USAGE',
					'EXECUTE',
					'CONNECT',
					'USE',
					'BINDADD',
					'CREATETAB',
					'CREATE_EXTERNAL_ROUTINE',
					'CREATE_NOT_FENCED_ROUTINE',
					'IMPLICIT_SCHEMA',
					'DBADM',
					'LOAD',
					'QUIESCE_CONNECT',
					'ALTERIN',
					'CREATEIN',
					'DROPIN',
					'CONTROL',
				])
			self._expect('ON')
			self._match('TABLE')
			self._parse_table_name()
			self._expect(tofrom)
			self._parse_auth_list()
			if grant and self._match('WITH'):
				self._expect_sequence(['GRANT', 'OPTION'])
			elif not grant and self._match('BY'):
				self._expect('ALL')
	
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
		"""Parses an ON DBPARTITIONNUM clause in a CREATE/ALTER TABLESPACE statement"""
		# ON already matched
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
			self._parse_expression1()
		valid = ['SEARCH', 'FILTER']
		while True:
			if not valid:
				break
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
	
	# STATEMENTS #############################################################

	def _parse_allocate_cursor_statement(self):
		"""Parses an ALLOCATE CURSOR statement in a procedure """
		# ALLOCATE already matched
		self._expect_sequence([IDENTIFIER, 'CURSOR', 'FOR', 'RESULT', 'SET', IDENTIFIER])
	
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
			self._expect(NUMBER)

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
		if not specific and self._match('('):
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
	
	def _parse_alter_procedure_statement(self, specific):
		"""Parses an ALTER PROCEDURE statement"""
		# ALTER [SPECIFIC] PROCEDURE already matched
		self._parse_procedure_name()
		if not specific and self._match('('):
			if not self._match(')'):
				self._parse_datatype_list()
				self._expect(')')
		first = True
		while True:
			if self._match('EXTERNAL'):
				self._expect('NAME')
				self._expect([STRING, IDENTIFIER])
			elif self._match('NOT'):
				self._expect_one_of(['FENCED', 'THREADSAFE'])
			elif self._match_one_of(['FENCED', 'THREADSAFE']):
				pass
			elif self._match('NO'):
				self._expect_sequence(['EXTERNAL', 'ACTION'])
			elif self._match('NEW'):
				self._expect_sequence(['SAVEPOINT', 'LEVEL'])
			elif first:
				self._expected_one_of([
					'EXTERNAL',
					'NOT',
					'FENCED',
					'NO',
					'EXTERNAL',
					'THREADSAFE',
				])
			else:
				break
			first = False
	
	def _parse_alter_sequence_statement(self):
		"""Parses an ALTER SEQUENCE statement"""
		# ALTER SEQUENCE already matched
		self._parse_sequence_name()
		self._parse_identity_options(alter='SEQUENCE')
	
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
				])
			else:
				break
			first = False

	def _parse_alter_table_statement(self):
		"""Parses an ALTER TABLE statement"""
		# ALTER TABLE already matched
		self._parse_table_name()
		self._indent()
		while True:
			if self._match('ADD'):
				if self._match('RESTRICT'):
					self._expect_sequence(['ON', 'DROP'])
				elif self._match('COLUMN'):
					self._parse_column_definition()
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
				elif self._match('RESTRICT'):
					self._expect_sequence(['ON', 'DROP'])
				else:
					self._expected_one_of(['PRIMARY', 'FOREIGN', 'CHECK', 'CONSTRAINT'])
			elif self._match('LOCKSIZE'):
				self._expect_one_of(['ROW', 'TABLE'])
			elif self._match('APPEND'):
				self._expect_one_of(['ON', 'OFF'])
			elif self._match('VOLATILE'):
				self._match('CARDINALITY')
			elif self._match('NOT'):
				self._expect('VOLATILE')
				self._match('CARDINALITY')
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

	def _parse_call_statement(self):
		"""Parses a CALL statement"""
		# CALL already matched
		self._parse_subschema_name()
		if self._match('('):
			self._parse_expression_list()
			self._expect(')')
	
	def _parse_case_statement(self, inproc):
		"""Parses a CASE-conditional in a procedure"""
		# XXX Implement support for labels
		# CASE already matched
		if self._match('WHEN'):
			# Parse searched-case-statement
			simple = False
			self._indent(-1)
		else:
			# Parse simple-case-statement
			self._parse_expression1()
			self._indent()
			self._expect('WHEN')
			simple = True
		# Parse WHEN clauses (only difference is predicate/expression after
		# WHEN)
		t = None
		while True:
			if simple:
				self._parse_expression1()
			else:
				self._parse_predicate1()
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
			while True:
				self._expect_sequence([IDENTIFIER, 'IS', STRING])
				reraise = True
				if not self._match(','):
					break
			self._expect(')')
		except ParseError:
			# If that fails, rewind and parse a single-object comment
			self._restore_state()
			if reraise: raise
			if self._match_one_of(['ALIAS', 'TABLE', 'INDEX', 'TRIGGER', 'TYPE']):
				self._parse_subschema_name()
			elif self._match_one_of(['DISTINCT', 'DATA']):
				self._expect('TYPE')
				self._parse_type_name()
			elif self._match_one_of(['COLUMN', 'CONSTRAINT']):
				self._parse_subrelation_name()
			elif self._match_one_of(['SCHEMA', 'TABLESPACE']):
				self._expect(IDENTIFIER)
			elif self._match_one_of(['FUNCTION', 'PROCEDURE']):
				self._parse_routine_name()
				if self._match('('):
					self._parse_datatype_list()
					self._expect(')')
			elif self._match('SPECIFIC'):
				self._expect_one_of(['FUNCTION', 'PROCEDURE'])
				self._parse_routine_name()
			else:
				self._expected_one_of([
					'ALIAS',
					'TABLE',
					'INDEX',
					'TRIGGER',
					'DATA',
					'DISTINCT',
					'TYPE',
					'COLUMN',
					'CONSTRAINT',
					'SCHEMA',
					'TABLESPACE',
					'FUNCTION',
					'PROCEDURE',
					'SPECIFIC',
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
		self._expect(NUMBER)
		# Parse function options (which can appear in any order)
		valid = [
			'NUMBLOCKPAGES',
			'PAGESIZE',
			'EXTENDED',
			'EXCEPT',
			'NOT',
		]
		while True:
			if not valid:
				break
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

	def _parse_create_distinct_type_statement(self):
		"""Parses a CREATE DISTINCT TYPE statement"""
		# CREATE DISTINCT TYPE already matched
		self._parse_type_name()
		self._expect('AS')
		self._parse_datatype()
		self._match_sequence(['WITH', 'COMPARISONS'])
	
	def _parse_create_function_statement(self):
		"""Parses a CREATE FUNCTION statement"""
		# CREATE FUNCTION already matched
		# XXX Implement support for CREATE FUNCTION (external)
		self._parse_function_name()
		# Parse parameter list
		self._expect('(')
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
		])
		# It's all too difficult trying to track exactly what can still be
		# specified in a CREATE FUNCTION statement (given the different types
		# of SQL, external scalar, external table, etc). Here we simply loop
		# round accepting any valid argument without tracking which we've seen
		# before
		while True:
			# Ambiguity: INHERIT SPECIAL REGISTERS (which appears in the
			# variable order options) and INHERIT ISOLATION LEVEL (which must
			# appear after the variable order options). See below.
			self._save_state()
			try:
				t = self._match_one_of(valid)
				if t:
					t = t[1]
				else:
					# break would skip the except and else blocks
					raise ParseBacktrack()
				if t == 'ALLOW':
					self._expect('PARALLEL')
				elif t == 'CALLED':
					self._expect_sequence(['ON', 'NULL', 'INPUT'])
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
					self._expect_one_of(['DETERMINISTIC', 'FENCED', 'THREADSAFE'])
				elif t == 'NULL':
					self._expect('CALL')
				elif t == 'PARAMETER':
					if self._match('CCSID'):
						self._expect_one_of(['ASCII', 'UNICODE'])
					else:
						self._expect('STYLE')
						self._expect_one_of(['DB2GENERAL', 'JAVA', 'SQL'])
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

	def _parse_create_index_statement(self, unique):
		"""Parses a CREATE INDEX statement"""
		# CREATE [UNIQUE] INDEX already matched
		self._parse_index_name()
		self._indent()
		self._expect('ON')
		self._parse_table_name()
		# Parse column list (with optional order indicators)
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
		# Parse optional include columns
		if self._match('INCLUDE'):
			self._newline(-1)
			self._expect('(')
			self._indent()
			self._parse_ident_list(newlines=True)
			self._outdent()
			self._expect(')')
		# Parse index options
		if self._match_one_of(['ALLOW', 'DISALLOW']):
			self._expect_sequence(['REVERSE', 'SCANS'])

	def _parse_create_partition_group_statement(self):
		"""Parses an CREATE DATABASE PARTITION GROUP statement"""
		# CREATE [DATABASE PARTITION GROUP|NODEGROUP] already matched
		self._expect(IDENTIFIER)
		if self._match('ON'):
			if self._match('ALL'):
				self._expect_one_of(['DBPARTITIONNUMS', 'NODES'])
			else:
				self._parse_db_partitions_clause(size=False)
	
	def _parse_create_procedure_statement(self):
		"""Parses a CREATE PROCEDURE statement"""
		# CREATE PROCEDURE already matched
		self._parse_procedure_name()
		if self._match('('):
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
			'SPECIFIC',
			'THREADSAFE',
		])
		# It's all too difficult trying to track exactly what can still be
		# specified in a CREATE PROCEDURE statement. Here we simply loop round
		# accepting any valid argument without tracking which we've seen before
		while True:
			t = self._match_one_of(valid)
			if t:
				t = t[1]
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
					if self._expect_one_of(['DB2GENERAL', 'DB2SQL', 'GENERAL', 'JAVA', 'SQL'])[1] == 'GENERAL':
						self._match_sequence(['WITH', 'NULLS'])
			elif t == 'PROGRAM':
				self._expect('TYPE')
				self._expect_one_of(['SUB', 'MAIN'])
			elif t == 'READS':
				self._expect_sequence(['SQL', 'DATA'])
			elif t == 'SPECIFIC':
				self._expect(IDENTIFIER)
			elif t == 'THREADSAFE':
				pass
			self._newline()
		self._outdent()
		self._expect('BEGIN')
		self._parse_procedure_compound_statement()
	
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
					self._parse_create_index_statement()
				else:
					self._expected_one_of(['TABLE', 'VIEW', 'INDEX'])
			elif self._match('COMMENT'):
				self._expect('ON')
				self._parse_comment_statement()
			elif self._match('GRANT'):
				self._parse_grant_statement()
			else:
				break
	
	def _parse_create_sequence_statement(self):
		"""Parses a CREATE SEQUENCE statement"""
		# CREATE SEQUENCE already matched
		self._parse_sequence_name()
		if self._match('AS'):
			self._parse_datatype()
		self._parse_identity_options()

	def _parse_create_tablespace_statement(self, tbspacetype='REGULAR'):
		"""Parses a CREATE TABLESPACE statement"""
		# CREATE TABLESPACE already matched
		self._expect(IDENTIFIER)
		if self._match('IN'):
			if self._match('DATABASE'):
				self._expect_sequence(['PARTITION', 'GROUP'])
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
	
	def _parse_create_table_statement(self):
		"""Parses a CREATE TABLE statement"""

		def parse_copy_options():
			# XXX Tidy this up (shouldn't just be a 2-time loop)
			for i in xrange(2):
				if self._match_one_of(['INCLUDING', 'EXCLUDING']):
					if self._match('COLUMN'):
						self._expect('DEFAULTS')
					elif self._match('DEFAULTS'):
						pass
					elif self._match('IDENTITY'):
						self._match_sequence(['COLUMN', 'ATTRIBUTES'])

		# CREATE TABLE already matched
		self._parse_table_name()
		if self._match('LIKE'):
			self._parse_relation_name()
			parse_copy_options()
		else:
			# Ambiguity: Open parentheses could indicate an optional field list
			# preceding a CREATE ... AS statement.
			reraise = False
			self._save_state()
			try:
				# Try parsing CREATE TABLE ... AS first
				if self._match('('):
					self._indent()
					self._parse_ident_list(newlines=True)
					self._outdent()
					self._expect(')')
				self._expect('AS')
				reraise = True
				self._expect('(')
				self._indent()
				self._parse_full_select1()
				self._outdent()
				self._expect(')')
				if self._match('WITH'):
					self._expect_sequence(['NO', 'DATA'])
					parse_copy_options()
				else:
					valid = [
						'DATA',
						'REFRESH',
						'ENABLE',
						'DISABLE',
						'MAINTAINED',
					]
					while True:
						if not valid:
							break
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
			except ParseError:
				# If that fails, rewind and parse other CREATE TABLE forms
				self._restore_state()
				if reraise: raise
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
						self._parse_column_definition(aligntypes=True)
					else:
						self._forget_state()
					if not self._match(','):
						break
					else:
						self._newline()
				self._outdent()
				self._vapply()
				self._expect(')')
			else:
				self._forget_state()
		# XXX Try and handle the bizarre [WITH NO DATA/IN/copy-options]
		# ordering when parsing CREATE TABLE ... AS
		# XXX Implement additional options (VALUE COMPRESSION, REPLICATED, WITH
		# RESTRICT, NOT LOGGED, ORGANIZE BY, etc.)
		# Parse tablespaces
		if self._match('IN'):
			self._expect(IDENTIFIER)
			if self._match('INDEX'):
				self._expect('IN')
				self._expect(IDENTIFIER)
			if self._match('LONG'):
				self._expect('IN')
				self._expect(IDENTIFIER)

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
			while True:
				if not valid:
					break
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
			self._parse_predicate1()
			self._outdent()
			self._expect(')')
		if self._match('BEGIN'):
			self._outdent(-1)
			self._parse_dynamic_compound_statement()
		else:
			# XXX Add support for label
			self._indent()
			self._parse_routine_statement()
			self._outdent()
			self._outdent()

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

	def _parse_declare_cursor_statement(self):
		"""Parses a top-level DECLARE CURSOR statement"""
		# DECLARE already matched
		self._expect_sequence([IDENTIFIER, 'CURSOR'])
		self._match_sequence(['WITH', 'HOLD'])
		self._expect('FOR')
		self._newline()
		self._parse_select_statement()

	def _parse_delete_statement(self):
		"""Parses a DELETE statement"""
		# DELETE already matched
		self._expect('FROM')
		if self._match('('):
			self._indent()
			self._parse_full_select1()
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
			if self._match('SET'):
				self._parse_set_clause(allowdefault=False)
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
					self._parse_set_clause(allowdefault=False)
			else:
				self._parse_table_correlation()
		else:
			self._forget_state()
		if self._match('WHERE'):
			self._newline(-1)
			self._indent()
			self._parse_predicate1()
			self._outdent()
		if self._match('WITH'):
			self._newline(-1)
			self._expect_one_of(['RR', 'RS', 'CS', 'UR'])
	
	def _parse_drop_statement(self):
		"""Parses a DROP statement"""
		# DROP already matched
		if self._match('ALIAS'):
			self._parse_alias_name()
		elif self._match('BUFFERPOOL'):
			self._expect(IDENTIFIER)
		elif self._match('EVENT'):
			self._expect('MONITOR')
			self._expect(IDENTIFIER)
		elif self._match_one_of(['TABLE', 'VIEW']):
			self._match('HIERARCHY')
			self._parse_relation_name()
		elif self._match_one_of(['TABLESPACE', 'TABLESPACES']):
			self._parse_ident_list()
		elif self._match('TRIGGER'):
			self._expect(IDENTIFIER)
		elif self._match('INDEX'):
			if self._match('EXTENSION'):
				self._parse_index_name()
				self._expect('RESTRICT')
			else:
				self._parse_index_name()
		elif self._match_one_of(['FUNCTION', 'PROCEDURE']):
			self._parse_routine_name()
			if self._match('('):
				self._parse_datatype_list()
				self._expect(')')
			self._match('RESTRICT')
		elif self._match('SPECIFIC'):
			self._expect_one_of(['FUNCTION', 'PROCEDURE'])
			self._parse_routine_name()
			self._match('RESTRICT')
		elif self._match_one_of(['DATA', 'DISTINCT']):
			self._expect('TYPE')
			self._parse_type_name()
		elif self._match('TYPE'):
			self._parse_type_name()
		elif self._match('SCHEMA'):
			self._expect(IDENTIFIER)
			self._match('RESTRICT')
		else:
			self._expected_one_of([
				'ALIAS',
				'BUFFERPOOL',
				'TABLE',
				'VIEW',
				'INDEX',
				'FUNCTION',
				'PROCEDURE',
				'SPECIFIC',
				'DISTINCT',
				'DATA',
				'TYPE',
				'SCHEMA',
				'TABLESPACE',
				'TRIGGER',
				'EVENT',
			])

	def _parse_execute_immediate_statement(self):
		"""Parses an EXECUTE IMMEDIATE statement in a procedure"""
		# EXECUTE IMMEDIATE already matched
		self._parse_expression1()
			
	def _parse_for_statement(self, inproc):
		"""Parses a FOR-loop in a dynamic compound statement"""
		# XXX Implement support for labels
		# FOR already matched
		self._expect_sequence([IDENTIFIER, 'AS'])
		if inproc:
			reraise = False
			self._indent()
			self._save_state()
			try:
				self._expect_sequence([IDENTIFIER, 'CURSOR'])
				reraise = True
				self._match_sequence(['WITH', 'HOLD'])
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
	
	def _parse_get_diagnostics_statement(self):
		"""Parses a GET DIAGNOSTICS statement in a dynamic compound statement"""
		# GET already matched
		self._expect('DIAGNOSTICS')
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
		# XXX Implement support for labels
		# IF already matched
		t = 'IF'
		while True:
			if t in ('IF', 'ELSEIF'):
				self._parse_predicate1(linebreaks=False)
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
			self._parse_full_select1()
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

	def _parse_loop_statement(self, inproc):
		"""Parses a LOOP-loop in a procedure"""
		# XXX Implement support for labels
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
	
	def _parse_merge_statement(self):
		# MERGE already matched
		self._expect('INTO')
		if self._match('('):
			self._indent()
			self._parse_full_select1()
			self._outdent()
			self._expect(')')
		else:
			self._parse_subschema_name()
		self._parse_table_correlation()
		self._expect('USING')
		if self._match('('):
			self._indent()
			self._parse_full_select1()
			self._outdent()
			self._expect(')')
		else:
			self._parse_subschema_name()
		self._parse_table_correlation()
		self._expect('ON')
		self._parse_predicate1()
		self._expect('WHEN')
		while True:
			self._match('NOT')
			self._expect('MATCHED')
			if self._match('AND'):
				self._parse_predicate1()
			self._expect('THEN')
			self._indent()
			if self._match('UPDATE'):
				self._expect('SET')
				self._parse_set_clause(allowdefault=True)
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
						self._parse_expression1()
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
			if not self._match(','):
				break
		self._match('NOT')
		self._match('INCREMENTAL')
	
	def _parse_release_savepoint_statement(self):
		"""Parses a RELEASE SAVEPOINT statement"""
		# RELEASE [TO] SAVEPOINT already matched
		self._expect(IDENTIFIER)
	
	def _parse_repeat_statement(self, inproc):
		"""Parses a REPEAT-loop in a procedure"""
		# XXX Implement support for labels
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
		self._parse_predicate1()
		self._expect_sequence(['END', 'REPEAT'])
	
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
			self._parse_expression1()
	
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
			self._parse_expression1()
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
	
	def _parse_savepoint_statement(self):
		"""Parses a SAVEPOINT statement"""
		# SAVEPOINT already matched
		self._expect(IDENTIFIER)
		self._match('UNIQUE')
		self._expect_sequence(['ON', 'ROLLBACK', 'RETAIN', 'CURSORS'])
		self._match_sequence(['ON', 'ROLLBACK', 'RETAIN', 'LOCKS'])
	
	def _parse_select_statement(self):
		"""Parses a SELECT statement"""
		self._parse_query()
		# Parse optional SELECT attributes (FOR UPDATE, WITH isolation, etc.)
		valid = ['WITH', 'FOR', 'OPTIMIZE']
		while True:
			if not valid:
				break
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
			while True:
				if not valid:
					break
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
			(REGISTER, 'CURRENT_USER'),
			IDENTIFIER,
			STRING,
		])
		self._match_sequence(['ALLOW', 'ADMINISTRATION'])

	def _parse_set_statement(self, inproc):
		"""Parses a SET statement in a dynamic compound statement"""
		# SET already matched
		if self._match('CURRENT'):
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
			elif self._match('ISOLATION'):
				self._parse_set_isolation_statement()
			elif self._match('LOCK'):
				self._expect('TIMEOUT')
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
			elif self._match('QUERY'):
				self._expect('OPTIMIZATION')
				self._match('=')
				self._expect(NUMBER)
			elif self._match('REFRESH'):
				self._expect('AGE')
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
		elif self._match('ISOLATION'):
			self._parse_set_isolation_statement()
		elif self._match('ENCRYPTION'):
			self._expect('PASSWORD')
			self._match('=')
			self._expect(STRING)
		elif self._match('INTEGRITY'):
			self._parse_set_integrity_statement()
		elif self._match('PATH'):
			self._parse_set_path_statement()
		elif self._match('CURRENT_PATH'):
			self._parse_set_path_statement()
		elif self._match('SCHEMA'):
			self._parse_set_schema_statement()
		elif self._match('SESSION'):
			self._expect('AUTHORIZATION')
			self._parse_set_session_auth_statement()
		elif self._match('SESSION_USER'):
			self._parse_set_session_auth_statement()
		elif inproc:
			self._parse_set_clause(allowdefault=False)
		else:
			self._expected_one_of([
				'CURRENT',
				'ISOLATION',
				'ENCRYPTION',
				'INTEGRITY',
				'PATH',
				'SCHEMA',
			])
	
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
			self._parse_expression1()
		elif self._match('('):
			# XXX Ensure syntax only valid within a trigger
			self._parse_expression1()
			self._expect(')')
	
	def _parse_update_statement(self):
		"""Parses an UPDATE statement"""
		# UPDATE already matched
		if self._match('('):
			self._indent()
			self._parse_full_select1()
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
		self._parse_set_clause(allowdefault=True)
		self._outdent()
		if self._match('WHERE'):
			self._indent()
			self._parse_predicate1()
			self._outdent()
		if self._match('WITH'):
			self._expect_one_of(['RR', 'RS', 'CS', 'UR'])

	def _parse_while_statement(self, inproc):
		"""Parses a WHILE-loop in a dynamic compound statement"""
		# XXX Implement support for labels
		# WHILE already matched
		self._parse_predicate1(linebreaks=False)
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
	
	# COMPOUND STATEMENTS ####################################################

	def _parse_routine_statement(self):
		"""Parses a statement in a routine/trigger/compound statement"""
		# XXX Only permit RETURN when part of a function/method/trigger
		# XXX Only permit ITERATE & LEAVE when part of a loop
		if self._match('CALL'):
			self._parse_call_statement()
		elif self._match('GET'):
			self._parse_get_diagnostics_statement()
		elif self._match('SET'):
			self._parse_set_statement(inproc=True)
		elif self._match('FOR'):
			self._parse_for_statement(inproc=False)
		elif self._match('WHILE'):
			self._parse_while_statement(inproc=False)
		elif self._match('IF'):
			self._parse_if_statement(inproc=False)
		elif self._match('SIGNAL'):
			self._parse_signal_statement()
		elif self._match('RETURN'):
			self._parse_return_statement()
		elif self._match('ITERATE'):
			self._parse_iterate_statement()
		elif self._match('LEAVE'):
			self._parse_leave_statement()
		elif self._match('INSERT'):
			self._parse_insert_statement()
		elif self._match('UPDATE'):
			self._parse_update_statement()
		elif self._match('DELETE'):
			self._parse_delete_statement()
		elif self._match('MERGE'):
			self._parse_merge_statement()
		else:
			self._parse_select_statement()
	
	def _parse_dynamic_compound_statement(self):
		"""Parses a dynamic compound statement"""
		# XXX Implement support for labelled blocks
		# XXX Only permit labels when part of a function/method/trigger
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
						self._parse_expression1()
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
	
	def _parse_procedure_statement(self):
		"""Parses a procedure statement within a procedure body"""
		# Procedure specific statements
		if self._match('REPEAT'):
			self._parse_repeat_statement(inproc=True)
		elif self._match('LOOP'):
			self._parse_loop_statement(inproc=True)
		elif self._match('CASE'):
			self._parse_case_statement(inproc=True)
		elif self._match('GOTO'):
			self._parse_goto_statement()
		elif self._match('ALLOCATE'):
			self._parse_allocate_cursor_statement()
		elif self._match('ASSOCIATE'):
			self._parse_associate_locators_statement()
		elif self._match('OPEN'):
			self._parse_open_statement()
		elif self._match('CLOSE'):
			self._parse_close_statement()
		elif self._match('EXECUTE'):
			self._expect('IMMEDIATE')
			self._parse_execute_immediate_statement()
		# Dynamic compound specific statements
		elif self._match('GET'):
			self._parse_get_diagnostics_statement()
		elif self._match('SET'):
			self._parse_set_statement(inproc=True)
		elif self._match('FOR'):
			self._parse_for_statement(inproc=True)
		elif self._match('WHILE'):
			self._parse_while_statement(inproc=True)
		elif self._match('IF'):
			self._parse_if_statement(inproc=True)
		elif self._match('SIGNAL'):
			self._parse_signal_statement()
		elif self._match('RETURN'):
			self._parse_return_statement()
		elif self._match('ITERATE'):
			self._parse_iterate_statement()
		elif self._match('LEAVE'):
			self._parse_leave_statement()
		# Generic SQL statements
		elif self._match('CALL'):
			self._parse_call_statement()
		elif self._match('INSERT'):
			self._parse_insert_statement()
		elif self._match('UPDATE'):
			self._parse_update_statement()
		elif self._match('DELETE'):
			self._parse_delete_statement()
		elif self._match('MERGE'):
			self._parse_merge_statement()
		elif self._match('GRANT'):
			self._parse_grant_statement()
		elif self._match('COMMENT'):
			self._expect('ON')
			self._parse_comment_statement()
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
		elif self._match('DROP'):
			# XXX Limit this to tables, views and indexes somehow?
			self._parse_drop_statement()
		elif self._match('COMMIT'):
			self._parse_commit_statement()
		elif self._match('ROLLBACK'):
			self._parse_rollback_statement()
		elif self._match('REFRESH'):
			self._expect('TABLE')
			self._parse_refresh_table_statement()
		elif self._match('RELEASE'):
			self._match('TO')
			self._expect('SAVEPOINT')
			self._parse_release_savepoint_statement()
		elif self._match('SAVEPOINT'):
			self._parse_savepoint_statement()
		elif self._match('RESIGNAL'):
			self._parse_resignal_statement()
		else:
			self._parse_select_statement()
	
	def _parse_procedure_compound_statement(self):
		"""Parses a procedure compound statement (body)"""
		# BEGIN already matched
		# XXX Implement support for labelled blocks
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
					self._expect_sequence(['(', (NUMBER, 5), ')'])
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
							self._parse_expression1()
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
	
	def _parse_statement(self):
		"""Parses a top-level statement in an SQL script"""
		# XXX CREATE EVENT MONITOR
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
			elif self._match('TABLESPACE'):
				self._parse_alter_tablespace_statement()
			elif self._match('BUFFERPOOL'):
				self._parse_alter_bufferpool_statement()
			elif self._match('DATABASE'):
				if self._match('PARTITION'):
					self._expect('GROUP')
					self._parse_alter_partition_group_statement()
				else:
					self._parse_alter_database_statement()
			elif self._match('NODEGROUP'):
				self._parse_alter_partition_group_statement()
			else:
				self._expected_one_of([
					'TABLE',
					'SEQUENCE',
					'FUNCTION',
					'PROCEDURE',
					'SPECIFIC',
					'TABLESPACE',
					'DATABASE',
					'NODEGROUP',
				])
		elif self._match('CREATE'):
			if self._match('TABLE'):
				self._parse_create_table_statement()
			elif self._match('VIEW'):
				self._parse_create_view_statement()
			elif self._match('ALIAS'):
				self._parse_create_alias_statement()
			elif self._match('UNIQUE'):
				self._expect('INDEX')
				self._parse_create_index_statement(unique=True)
			elif self._match('INDEX'):
				self._parse_create_index_statement(unique=False)
			elif self._match('DISTINCT'):
				self._expect('TYPE')
				self._parse_create_distinct_type_statement()
			elif self._match('SEQUENCE'):
				self._parse_create_sequence_statement()
			elif self._match('FUNCTION'):
				self._parse_create_function_statement()
			elif self._match('PROCEDURE'):
				self._parse_create_procedure_statement()
			elif self._match('TABLESPACE'):
				self._parse_create_tablespace_statement()
			elif self._match('BUFFERPOOL'):
				self._parse_create_bufferpool_statement()
			elif self._match('DATABASE'):
				self._expect('PARTITION')
				self._expect('GROUP')
				self._parse_create_partition_group_statement()
			elif self._match('NODEGROUP'):
				self._parse_create_partition_group_statement()
			elif self._match('TRIGGER'):
				self._parse_create_trigger_statement()
			elif self._match('SCHEMA'):
				self._parse_create_schema_statement()
			else:
				tbspacetype = self._match_one_of([
					'REGULAR',
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
					self._expect('TABLESPACE')
					self._parse_create_tablespace_statement(tbspacetype)
				else:
					self._expected_one_of([
						'ALIAS',
						'BUFFERPOOL',
						'TABLE',
						'VIEW',
						'INDEX',
						'UNIQUE',
						'DISTINCT',
						'SEQUENCE',
						'FUNCTION',
						'PROCEDURE',
						'TABLESPACE',
						'TRIGGER',
						'DATABASE',
						'NODEGROUP',
					])
		elif self._match('DROP'):
			self._parse_drop_statement()
		elif self._match('DECLARE'):
			self._parse_declare_cursor_statement()
		elif self._match('BEGIN'):
			self._parse_dynamic_compound_statement()
		elif self._match('COMMIT'):
			self._parse_commit_statement()
		elif self._match('ROLLBACK'):
			self._parse_rollback_statement()
		elif self._match('INSERT'):
			self._parse_insert_statement()
		elif self._match('UPDATE'):
			self._parse_update_statement()
		elif self._match('DELETE'):
			self._parse_delete_statement()
		elif self._match('MERGE'):
			self._parse_merge_statement()
		elif self._match('GRANT'):
			self._parse_grant_statement()
		elif self._match('REVOKE'):
			self._parse_revoke_statement()
		elif self._match('COMMENT'):
			self._expect('ON')
			self._parse_comment_statement()
		elif self._match('LOCK'):
			self._expect('TABLE')
			self._parse_lock_table_statement()
		elif self._match('SET'):
			self._parse_set_statement(inproc=False)
		else:
			self._parse_select_statement()

	def parseRoutinePrototype(self, tokens):
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
		self._expect('(')
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

if __name__ == '__main__':
	pass
