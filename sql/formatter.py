#!/bin/env python
# $Header$
# vim: set noet sw=4 ts=4:

"""Implements a class for reflowing "raw" SQL.

This unit implements a class which reformats SQL that has been "mangled"
in some manner, typically by being parsed and stored by a database (e.g.
line breaks stripped, all whitespace converted to individual spaces, etc).
The reformatted SQL is intended to be more palatable for human consumption
(aka "readable" :-)

Currently the class is capable of reformatting the following SQL statements:

ALTER TABLE
CREATE TABLE
CREATE VIEW
CREATE INDEX
CREATE FUNCTION
DROP
SELECT (*)
INSERT
UPDATE
DELETE
Dynamic-compound-statements

(*) The SELECT implementation is reasonably complete, handling simply SELECTs,
sub-SELECTs, common-table-expressions from SQL-99, calls to table functions,
full-selects (with set operators), and SELECTs on the results of other DML
operations (i.e. INSERT, UPDATE, DELETE).

"""

from collections import deque
from dialects import *
from tokenizer import *

# Custom token types used by the formatter
(
	DATATYPE,  # Datatypes (e.g. VARCHAR) converted from KEYWORD or IDENTIFIER
	INDENT,    # Whitespace indentation at the start of a line
) = newTokens(2)

class ParseError(Exception):
		# XXX Implement __str__ to provide context
		pass

class ParseExpectedError(ParseError):
	pass

class SQLFormatter(object):
	"""Reformatter which breaks up and re-indents SQL.

	This class is, at its core, a full blown SQL language parser that
	understands many common SQL DML and DDL commands.

	The class accepts input from one of the tokenizers in the sqltokenizer
	unit, which in the form of a list of tokens, where tokens are tuples with
	the following structure:

		(token_type, token_value, token_source, line, column)

	In other words, this class accepts the output of the SQLTokenizer class
	in the tokenizer unit. To use the class simply pass such a list to the
	parse method. The method will return a list of tokens (just like the
	list of tokens provided as input, but reformatted).

	The token_type element gives the general "family" of the token (such as
	OPERATOR, IDENTIFIER, etc), while the token_value element provides the
	specific type of the token (e.g. "=", "OR", "DISTINCT", etc). The code
	in this class typically uses "partial" tokens to match against "complete"
	tokens in the source. For example, instead of trying to match on the
	token_source element (which may vary in case), this class often matches
	token on the first two elements:

		(KEYWORD, "OR", "or", 7, 13)[:2] == (KEYWORD, "OR")

	A set of internal utility methods are used to simplify this further. See
	the match and expect methods in particular. The numerous parseX methods in
	the unit define the grammar of the SQL language being parsed. The dialect
	used by the class is the IBM DB2 UDB for LUW dialect, with a few extensions
	and rarely used extensions removed (or at least, not yet implemented!)
	"""

	def __init__(self):
		super(SQLFormatter, self).__init__()
		self.indent = " "*4 # Default indent is 4 spaces

	def _tokenName(self, token):
		"""Reformats a token (or a partial matching token) for use in a message.

		If the provided token is complete, the token_source element (the third
		element in the tuple) is used. Otherwise, the second field (token_value)
		or the first element (token_type, converted to a string) is used. If
		the result is purely symbolic (such as a single space character, or a
		comma), it will be placed within quotes.

		If multiple tokens are passed in a list, the result contains all the
		passed tokens, separated by commas.
		"""
		if type(token) == type([]):
			return ",".join([self._tokenName(t) for t in token])
		else:
			if (len(token) == 1) or (token[0] in (EOF, WHITESPACE, TERMINATOR)):
				result = {
					EOF:        '<eof>',
					WHITESPACE: '<space>',
					KEYWORD:    'keyword',
					OPERATOR:   'operator',
					IDENTIFIER: 'identifier',
					DATATYPE:   'datatype',
					COMMENT:    'comment',
					NUMBER:     'number',
					STRING:     'string',
					TERMINATOR: '<statement-end>',
				}[token[0]]
			elif len(token) == 2:
				result = '"%s"' % (token[1])
			elif len(token) >= 3:
				result = '"%s"' % (token[2])
			return result

	def _tokenOutput(self, token):
		"""Reformats an output token for use in the final output.

		The _tokenOutput() method is only called at the end of parsing, when
		the list of output tokens has been assembled. It is then called
		repeatedly to format each token. For example, all WHITESPACE tokens
		are output as a single space (whitespace tokens inserted by the
		formatter, like INDENT, are converted back to WHITESPACE tokens but
		the source field is output verbatim).
		
		Note that output tokens don't have line or column elements.
		"""
		def quotestr(s, qchar):
			return "%s%s%s" % (qchar, s.replace(qchar, qchar*2), qchar)
		
		def formatident(ident):
			identchars = set(ibmdb2udb_identchars)
			quotedident = not ident[0] in (identchars - set("0123456789"))
			if not quotedident:
				for c in ident[1:]:
					if not c in identchars:
						quotedident = True
						break
			if quotedident:
				return quotestr(ident, '"')
			else:
				return ident
		
		def formatparam(param):
			if param is None:
				return "?"
			else:
				return ":%s" % (formatident(param))
		
		if token[0] == IDENTIFIER:
			# Format identifiers using subroutine above
			return (IDENTIFIER, token[1], formatident(token[1]))
		elif token[0] == DATATYPE:
			# Treat datatypes like identifiers (as they are essentially)
			return (DATATYPE, token[1], formatident(token[1]))
		elif token[0] == PARAMETER:
			# Format parameters using subroutine above
			return (PARAMETER, token[1], formatparam(token[1]))
		elif token[0] == KEYWORD:
			# All keywords converted to uppercase
			return (KEYWORD, token[1], token[1])
		elif token[0] == WHITESPACE:
			# All original whitespace compressed to a single space
			return (WHITESPACE, None, " ")
		elif token[0] == COMMENT:
			# All comments converted to C-style
			return (COMMENT, token[1], "/*%s*/" % (token[1]))
		elif token[0] == NUMBER:
			# Numbers reformatted by Decimal library
			return (NUMBER, token[1], str(token[1]))
		elif token[0] == STRING:
			# All strings converted to single quotes
			return (STRING, token[1], quotestr(token[1], "'"))
		elif token[0] == INDENT:
			# Indentation is converted to WHITESPACE tokens
			return (WHITESPACE, None, "\n" + self.indent*token[1])
		else:
			# All other tokens returned verbatim
			return token

	def _saveState(self):
		"""Saves the current state of the parser on a stack for later retrieval."""
		self._statestack.append((
			list(self._tokens), # list() is used to ensure we take a copy
			self._index,
			self._level,
			list(self._output), # list() is used to ensure we take a copy
		))

	def _restoreState(self):
		"""Restores the state of the parser from the head of the save stack."""
		(
			self._tokens,
			self._index,
			self._level,
			self._output,
		) = self._statestack.pop()

	def _forgetState(self):
		"""Destroys the saved state at the head of the save stack."""
		self._statestack.pop()

	def _token(self):
		"""Returns the current token, or the EOF token if the index is at or beyond EOF"""
		try:
			return self._tokens[self._index]
		except IndexError:
			return self._tokens[-1]

	def _newline(self, index=0):
		"""Adds an INDENT token to the output.

		The _newline() method is called to start a new line in the output. It
		does this by appending (or inserting, depending on the index parameter)
		an INDENT token to the output list. Such a token starts a new line,
		indented to the current indentation level.

		If the index parameter is False, 0, or ommitted, the new INDENT token
		is appended to the output. If the index parameter is -1, the new INDENT
		token is inserted immediately before the last non-ignorable
		(non-whitespace or comment) token. If the index parameter is -2, it
		is inserted before the second to last non-ignorable token and so on.

		The index parameter, if specified, may not be greater than zero.
		"""
		token = (INDENT, self._level, "\n" + self.indent * self._level)
		if not index:
			self._output.append(token)
		else:
			i = -1
			while True:
				while self._output[i][0] in (COMMENT, WHITESPACE): i -= 1
				index += 1
				if index >= 0: break
			self._output.insert(i, token)

	def _indent(self, index=0):
		self._level += 1
		self._newline(index)

	def _outdent(self, index=0):
		self._level -= 1
		# Stop two or more consecutive outdent() calls from leaving blank lines
		if self._output[-1][0] == INDENT:
			del self._output[-1]
		self._newline(index)

	def _skip(self):
		"""Move on to the next token (ignoring comments and whitespace by default).

		The _skip() method is used to move the position of the parser on to
		the next "normative" token (i.e. non-whitespace or comment token) in
		the source.

		As a side effect it also appends the tokens it moves over to the output
		list. However, the last two elements of each token (the line and column
		in the original source) are discarded (as, by definition, the formatter
		will invalidate these values anyway).
		"""
		if not self._token()[0] in (COMMENT, WHITESPACE):
			self._output.append(self._token()[:3])
			self._index += 1
		while self._token()[0] in (COMMENT, WHITESPACE):
			self._output.append(self._token()[:3])
			self._index += 1

	def _match(self, tokens):
		"""Attempt to match the current token against a selection of partial tokens.

		If the current token matches ANY of the specified partial tokens,
		the method returns the current token. Otherwise, the method returns
		None (hence when a match has been found the result can be used to
		evaluate to True in an if statement, or False otherwise -- or the
		result can be used to test *which* token of the choices provided was
		matched).
		"""
		# Wrap tokens in a list if only one was specified
		if type(tokens) != type([]):
			tokens = [tokens]
		# Does the current token match any of the specified tokens? If so, set
		# the result to the current token, otherwise None
		if True in [self._token()[:len(token)] == token for token in tokens]:
			result = self._token()
		else:
			return None
		# Move to the next token
		self._skip()
		return result

	def _expect(self, tokens):
		"""Match the current token against a selection of partial tokens.

		The _expect() method is essentially the same as _match() except that if
		a match is not found, a ParseError exception is raised stating that the
		parser "expected" one of the specified tokens, but found something
		else.
		"""
		result = self._match(tokens)
		if not result:
			t = self._token()
			raise ParseError('Expected %s but found %s on line %d, column %d' %
				(self._tokenName(tokens), self._tokenName(t), t[3], t[4]), t)
		else:
			return result

	def _keywordIdent(self, dontconvert=[]):
		"""Convert the current token into an IDENTIFIER if it is a KEYWORD.

		The _keywordIdent() method is used immediately prior to a call to
		_expect() to match an IDENTIFIER token. If the current token is a
		KEYWORD token it is converted to an IDENTIFIER token to allow the
		match to succeed, unless the value of the KEYWORD token matches one
		of the entries in the dontconvert list.

		This is used because many SQL dialects permit reserved words to be
		used as identifiers wherever ambiguity would not result from such use.
		"""
		# If the current token is a KEYWORD, convert it into an IDENTIFIER
		if (self._token()[0] == KEYWORD) and (self._token()[1] not in dontconvert):
			token = self._token()
			self._tokens[self._index] = (IDENTIFIER, token[1], token[2], token[3], token[4])

	def _identDatatype(self):
		"""Convert the current token into a DATATYPE if it is an IDENTIFIER.
		
		The _identDatatype() method is used immediately prior to a call to
		_expect() to match a DATATYPE token. If the current token is an
		IDENTIFIER token (which might previously have been a KEYWORD token
		converted by _keywordIdent() above), it is converted to a DATATYPE
		token (a custom token type introduced by this unit).
		
		This is used to permit alternate highlighting for datatypes by the
		SQLHighlighter class (which knows about the custom DATATYPE token
		type).
		"""
		# If the current token is an IDENTIFIER, convert it into a DATATYPE
		if (self._token()[0] == IDENTIFIER):
			token = self._token()
			self._tokens[self._index] = (DATATYPE, token[1], token[2], token[3], token[4])

	def _parseRelationObjectName(self):
		"""Parses the (possibly qualified) name of a relation-owned object.

		A relation-owned object is either a column or a constraint. This method
		parses such a name with up to two optional qualifiers (e.g., it is
		possible in a SELECT statement with no table correlation clauses to
		specify SCHEMA.TABLE.COLUMN). The method returns the parsed name as
		a tuple with 1, 2, or 3 elements (depending on whether any qualifiers
		were found).
		"""
		# Parse the first (and possibly final) name
		self._keywordIdent()
		result = (self._expect((IDENTIFIER,))[1],)
		# Check for a qualifier (without _skipping whitespace)
		if self._match((OPERATOR, ".")):
			self._keywordIdent()
			result = (result[0], self._expect((IDENTIFIER,))[1])
			# Check for another qualifier (without _skipping whitespace)
			if self._match((OPERATOR, ".")):
				self._keywordIdent()
				result = (result[0], result[1], self._expect((IDENTIFIER,))[1])
		return result

	def _parseSchemaObjectName(self):
		"""Parses the (possibly qualified) name of a schema-owned object.

		A schema-owned object is a table, view, index, function, sequence,
		etc. This method parses such a name with an optional qualifier (the
		schema name). The method returns the parsed name as a tuple with 1 or
		2 elements (depending on whether a qualifier was found).
		"""
		# Parse the first (and possibly final) name
		self._keywordIdent()
		result = (self._expect((IDENTIFIER,))[1],)
		# Check for a qualifier (without _skipping whitespace)
		if self._match((OPERATOR, ".")):
			self._keywordIdent()
			result = (result[0], self._expect((IDENTIFIER,))[1])
		return result

	def _parseDataType(self):
		"""Parses a (possibly qualified) data type with optional arguments.

		Parses a data type name with an optional qualifier (the schema name).
		The method returns a tuple with the following structure:

			(schema_name, type_name, (arg1, arg2))

		The schema_name, arg1, and arg2 elements may be ommitted if they were
		not found in the source. Therefore, the structure above represents the
		"maximum" number of elements that will be returned, e.g. in the case
		of SYSIBM.DECIMAL(10,2). The "minimum" that would be returned, e.g. in
		the case of INTEGER, would be:

			(type_name, ())

		Hence, the tuple for arguments is always returned (even if empty) as
		the last element of the result tuple.
		"""
		# Parse the type name (or schema name)
		self._keywordIdent()
		self._identDatatype()
		result = [self._expect((DATATYPE,))[1]]
		# Check for a qualifier (without _skipping whitespace)
		if self._match((OPERATOR, ".")):
			self._keywordIdent()
			self._identDatatype()
			result = [result[0], self._expect((DATATYPE,))[1]]
		# Parse the optional argument(s)
		args = ()
		if self._match((OPERATOR, "(")):
			args = (self._expect((NUMBER,)),)
			# Parse optional units (kilobytes, megabytes, gigabytes)
			units = self._match([(IDENTIFIER, "K"), (IDENTIFIER, "M"), (IDENTIFIER, "G")])
			if units:
				args = (args[0] * { "K": 1024, "M": 1024*1024, "G": 1024*1024*1024 }[units[1]],)
			# Parse the optional second argument
			if self._match((OPERATOR, ",")):
				args = (args[0], self._expect((NUMBER,)))
			self._expect((OPERATOR, ")"))
		result.append(args)
		return tuple(result)

	def _parsePredicate1(self, linebreaks=True):
		"""Parse low precedence predicate operators (OR)"""
		self._parsePredicate2(linebreaks)
		while True:
			if self._match((KEYWORD, "OR")):
				if linebreaks: self._newline(-1)
				self._parsePredicate2(linebreaks)
			else:
				break

	def _parsePredicate2(self, linebreaks=True):
		"""Parse medium precedence predicate operators (AND)"""
		self._parsePredicate3(linebreaks)
		while True:
			if self._match((KEYWORD, "AND")):
				if linebreaks: self._newline(-1)
				self._parsePredicate3(linebreaks)
			else:
				break

	def _parsePredicate3(self, linebreaks=True):
		"""Parse high precedence predicate operators (BETWEEN, IN, etc.)"""
		# Ambiguity: Open parenthesis could indicate a grouping of predicates or expressions
		self._saveState()
		try:
			# XXX Handle EXISTS predicate
			if self._match((OPERATOR, "(")):
				# Try and parse parenthesis group as a predicate
				self._parsePredicate1(linebreaks)
				self._expect((OPERATOR, ")"))
			elif self._match((KEYWORD, "EXISTS")):
				self._expect((OPERATOR, "("))
				self._parseFullSelect1()
				self._expect((OPERATOR, ")"))
			else:
				raise ParseError()
		except ParseError:
			# If that fails, or we don't match an open parenthesis, parse an
			# ordinary high-precedence predicate operator
			self._restoreState()
			self._parseExpression1()
			if self._match((KEYWORD, "NOT")):
				if self._match((KEYWORD, "LIKE")):
					self._parseExpression1()
				elif self._match((KEYWORD, "BETWEEN")):
					self._parseExpression1()
					self._expect((KEYWORD, "AND"))
					self._parseExpression1()
				elif self._match((KEYWORD, "IN")):
					if self._match((OPERATOR, "(")):
						self._saveState()
						try:
							# Try and parse a full-select
							self._indent()
							self._parseFullSelect1()
							self._outdent()
							self._expect((OPERATOR, ")"))
						except ParseError:
							# If that fails, rewind and parse a tuple of expressions
							self._restoreState()
							while True:
								self._parseExpression1()
								if self._expect([(OPERATOR, ","), (OPERATOR, ")")])[:2] == (OPERATOR, ")"):
									break
						else:
							self._forgetState()
					else:
						self.parseExpression1()
				else:
					self._parsePredicate3(linebreaks)
			elif self._match((KEYWORD, "LIKE")):
				self._parseExpression1()
			elif self._match((KEYWORD, "BETWEEN")):
				self._parseExpression1()
				self._expect((KEYWORD, "AND"))
				self._parseExpression1()
			elif self._match((KEYWORD, "IN")):
				if self._match((OPERATOR, "(")):
					self._saveState()
					try:
						# Try and parse a full-select
						self._indent()
						self._parseFullSelect1()
						self._outdent()
						self._expect((OPERATOR, ")"))
					except ParseError:
						# If that fails, rewind and parse a tuple of expressions
						self._restoreState()
						while True:
							self._parseExpression1()
							if self._expect([(OPERATOR, ","), (OPERATOR, ")")])[:2] == (OPERATOR, ")"):
								break
					else:
						self._forgetState()
				else:
					self.parseExpression1()
			elif self._match((KEYWORD, "IS")):
				self._match((KEYWORD, "NOT"))
				self._expect((KEYWORD, "NULL"))
			elif self._match([(OPERATOR, "="), (OPERATOR, "<"), (OPERATOR, ">"),
				(OPERATOR, "<>"), (OPERATOR, "<="), (OPERATOR, ">=")]):
				if self._match([(KEYWORD, "SOME"), (KEYWORD, "ANY"), (KEYWORD, "ALL")]):
					self._expect((OPERATOR, "("))
					self._parseFullSelect1()
					self._expect((OPERATOR, ")"))
				else:
					self._parseExpression1()
			else:
				self._expect([(KEYWORD, "NOT"), (KEYWORD, "LIKE"), (KEYWORD, "BETWEEN"),
					(KEYWORD, "IS"), (KEYWORD, "IN"), (OPERATOR, "="), (OPERATOR, "<"),
					(OPERATOR, ">"), (OPERATOR, "<>"), (OPERATOR, "<="), (OPERATOR, ">=")])
		else:
			self._forgetState()

	def _parseExpression1(self):
		"""Parse low precedence expression operators (+, -, ||, CONCAT)"""
		self._parseExpression2()
		while True:
			if self._match((OPERATOR, "+")):
				self._parseExpression2()
			elif self._match((OPERATOR, "-")):
				self._parseExpression2()
			elif self._match((OPERATOR, "||")):
				self._parseExpression2()
			elif self._match((KEYWORD, "CONCAT")):
				self._parseExpression2()
			else:
				break

	def _parseExpression2(self):
		"""Parse medium precedence expression operators (*, /)"""
		self._parseExpression3()
		while True:
			if self._match((OPERATOR, "*")):
				self._parseExpression1()
			elif self._match((OPERATOR, "/")):
				self._parseExpression1()
			else:
				break

	def _parseExpression3(self):
		"""Parse high precedence expression operators (literals, etc.)"""
		if self._match((OPERATOR, "(")):
			# Ambiguity: Open-parenthesis could indicate a full-select or simple grouping
			self._saveState()
			try:
				# Try and parse a full-select
				self._parseFullSelect1()
				self._expect((OPERATOR, ")"))
			except ParseError:
				# If it fails, rewind and try an expression or tuple instead
				self._restoreState()
				while True:
					self._parseExpression1()
					if self._expect([(OPERATOR, ","), (OPERATOR, ")")])[:2] == (OPERATOR, ")"):
						break
			else:
				self._forgetState()
		elif self._match((OPERATOR, "+")): # Unary +
			self._parseExpression3()
		elif self._match((OPERATOR, "-")): # Unary -
			self._parseExpression3()
		elif self._match((KEYWORD, "CAST")):
			self._parseCast()
		elif self._match((KEYWORD, "CASE")):
			if self._match((KEYWORD, "WHEN")):
				self._indent(-1)
				self._parseSearchedCase()
			else:
				self._parseSimpleCase()
		elif self._match((KEYWORD, "CURRENT")):
			self._expect([(KEYWORD,), (IDENTIFIER,)])
		elif self._match([(NUMBER,), (STRING,), (PARAMETER,), (KEYWORD, "NULL")]):
			pass
		else:
			self._saveState()
			try:
				# Try and parse an aggregation function
				self._parseAggregateFunction()
			except ParseError:
				self._restoreState()
				self._saveState()
				try:
					# Try and parse a scalar function
					self._parseScalarFunction()
				except ParseError:
					self._restoreState()
					# Parse a normal column reference
					self._parseRelationObjectName()
				else:
					self._forgetState()
			else:
				self._forgetState()

	def _parseAggregateFunction(self):
		"""Parses an aggregate function with it's optional arg-prefix"""
		# Parse the optional SYSIBM schema prefix
		if self._match((KEYWORD, "SYSIBM")):
			self._expect((OPERATOR, "."))
		aggfunc = self._expect([
			# COUNT and COUNT_BIG are KEYWORDs
			(KEYWORD, "COUNT"),
			(KEYWORD, "COUNT_BIG"),
			# Other aggregate functions are not KEYWORDs
			(IDENTIFIER, "AVG"),
			(IDENTIFIER, "MAX"),
			(IDENTIFIER, "MIN"),
			(IDENTIFIER, "STDDEV"),
			(IDENTIFIER, "SUM"),
			(IDENTIFIER, "VARIANCE"),
			(IDENTIFIER, "VAR"),
		])[:2]
		self._expect((OPERATOR, "("))
		if (aggfunc[1] in ("COUNT", "COUNT_BIG")) and self._match((OPERATOR, "*")):
			# COUNT and COUNT_BIG can take "*" as a sole parameter
			pass
		else:
			# Aggregation functions have an optional ALL/DISTINCT argument prefix
			self._match([(KEYWORD, "ALL"), (KEYWORD, "DISTINCT")])
			# And only take a single expression as an argument
			self._parseExpression1()
		self._expect((OPERATOR, ")"))

	def _parseScalarFunction(self):
		"""Parses a scalar function call with all its arguments"""
		# Parse the function name
		self._parseSchemaObjectName()
		# Parse the arguments (the enclosing parentheses are mandatory)
		self._expect((OPERATOR, "("))
		if not self._match((OPERATOR, ")")):
			while True:
				self._parseExpression1() # Argument Expression
				if self._expect([(OPERATOR, ","), (OPERATOR, ")")])[:2] == (OPERATOR, ")"):
					break
	
	def _parseCast(self):
		"""Parses a CAST() expression"""
		# CAST already matched
		self._expect((OPERATOR, "("))
		self._parseExpression1()
		self._expect((KEYWORD, "AS"))
		self._parseDataType()
		self._expect((OPERATOR, ")"))

	def _parseSearchedCase(self):
		"""Parses a searched CASE expression (CASE WHEN expression...)"""
		# CASE WHEN already matched
		# Parse all WHEN cases
		while True:
			self._parsePredicate1(linebreaks=False) # WHEN Search condition
			self._expect((KEYWORD, "THEN"))
			self._parseExpression1() # THEN Expression
			if self._match((KEYWORD, "WHEN")):
				self._newline(-1)
			elif self._match((KEYWORD, "ELSE")):
				self._newline(-1)
				break
			else:
				self._outdent()
				self._expect((KEYWORD, "END"))
				return
		# Parse the optional ELSE case
		self._parseExpression1() # ELSE Expression
		self._outdent()
		self._expect((KEYWORD, "END"))

	def _parseSimpleCase(self):
		"""Parses a simple CASE expression (CASE expression WHEN value...)"""
		# CASE already matched
		# Parse the CASE Expression
		self._parseExpression1() # CASE Expression
		# Parse all WHEN cases
		self._indent()
		self._expect((KEYWORD, "WHEN"))
		while True:
			self._parseExpression1() # WHEN Expression
			self._expect((KEYWORD, "THEN"))
			self._parseExpression1() # THEN Expression
			if self._match((KEYWORD, "WHEN")):
				self._newline(-1)
			elif self._match((KEYWORD, "ELSE")):
				self._newline(-1)
				break
			else:
				self._outdent()
				self._expect((KEYWORD, "END"))
				return
		# Parse the optional ELSE case
		self._parseExpression1() # ELSE Expression
		self._outdent()
		self._expect((KEYWORD, "END"))

	def _parseSubSelect(self):
		"""Parses a sub-select expression"""
		# SELECT already matched
		# Parse the optional ALL and DISTINCT modifiers
		self._match([(KEYWORD, "ALL"), (KEYWORD, "DISTINCT")])
		# Parse the SELECT expressions
		self._indent()
		while True:
			self._parseColumnExpression()
			if self._match((OPERATOR, ",")):
				self._newline()
			else:
				break
		self._outdent()
		# Parse the mandatory FROM clause
		self._expect((KEYWORD, "FROM"))
		self._indent()
		while True:
			self._parseTableRef1()
			if self._match((OPERATOR, ",")):
				self._newline()
			else:
				break
		self._outdent()
		# Parse the optional WHERE clause
		if self._match((KEYWORD, "WHERE")):
			self._indent()
			self._parsePredicate1()
			self._outdent()
		# Parse the optional GROUP BY clause
		# XXX Handle GROUPING SET
		if self._match((KEYWORD, "GROUP")):
			self._expect((KEYWORD, "BY"))
			self._indent()
			while True:
				self._parseExpression1()
				if self._match((OPERATOR, ",")):
					self._newline()
				else:
					break
			self._outdent()
		# Parse the optional HAVING clause
		if self._match((KEYWORD, "HAVING")):
			self._indent()
			self._parsePredicate1()
			self._outdent()
		# Parse the optional ORDER BY clause
		# XXX Handle numeric column references
		if self._match((KEYWORD, "ORDER")):
			self._expect((KEYWORD, "BY"))
			self._indent()
			while True:
				self._parseExpression1()
				# Parse the optional order specification
				self._match([(IDENTIFIER, "ASC"), (IDENTIFIER, "DESC")])
				if self._match((OPERATOR, ",")):
					self._newline()
				else:
					break
			self._outdent()
		# Parse the optional FETCH FIRST clause
		if self._match((KEYWORD, "FETCH")):
			self._expect((IDENTIFIER, "FIRST")) # FIRST isn't a keyword
			self._match((NUMBER,)) # Row count is optional (defaults to 1)
			self._expect([(KEYWORD, "ROW"), (KEYWORD, "ROWS")])
			self._expect((IDENTIFIER, "ONLY")) # ONLY isn't a keyword

	def _parseColumnExpression(self):
		"""Parses an expression representing a column in a SELECT expression"""
		self._saveState()
		try:
			# Attempt to parse exposed-name.*
			self._keywordIdent()
			if self._match((IDENTIFIER,)):
				self._expect((OPERATOR, "."))
			self._expect((OPERATOR, "*"))
		except ParseError:
			# If that fails, rewind and parse an ordinary expression
			self._restoreState()
			self._parseExpression1()
			# Parse optional column alias
			if self._match((KEYWORD, "AS")):
				self._keywordIdent()
				self._expect((IDENTIFIER,))
			else:
				# Ambiguity: FROM can legitimately appear in this position as a KEYWORD
				self._keywordIdent(["FROM"])
				self._match((IDENTIFIER,))
		else:
			self._forgetState()

	def _parseTableCorrelation(self):
		"""Parses a table correlation clause (with optional column alias list)"""
		# Parse the correlation clause
		if self._match((KEYWORD, "AS")):
			self._keywordIdent()
			self._expect((IDENTIFIER,))
		else:
			# Ambiguity: Several KEYWORDs can legitimately appear in this position
			self._keywordIdent(["WHERE", "GROUP", "HAVING", "ORDER", "FETCH", "UNION", "INTERSECT", "EXCEPT", "WITH", "ON"])
			self._expect((IDENTIFIER,))
		# Parse optional column aliases
		if self._match((OPERATOR, "(")):
			while True:
				self._keywordIdent()
				self._expect((IDENTIFIER,))
				if self._expect([(OPERATOR, ","), (OPERATOR, ")")])[:2] == (OPERATOR, ")"):
					break

	def _parseTableFunction(self):
		"""Parses a table function call with all its arguments"""
		# Syntactically, this is identical to a scalar function call
		self._parseScalarFunction()

	def _parseValues(self):
		"""Parses a VALUES expression"""
		# VALUES already matched
		self._indent()
		while True:
			if self._match((OPERATOR, "(")):
				while True:
					self._parseExpression1()
					if self._expect([(OPERATOR, ","), (OPERATOR, ")")])[:2] == (OPERATOR, ")"):
						break
			else:
				self._parseExpression1()
			if self._match((OPERATOR, ",")):
				self._newline()
			else:
				break
		self._outdent()

	def _parseTableRef1(self):
		"""Parses join operators in a table-reference"""
		self._parseTableRef2()
		while True:
			natural = bool(self._match((KEYWORD, "NATURAL")))
			if natural:
				self._newline(-1)
			if self._match([(KEYWORD, "INNER"), (KEYWORD, "CROSS")]):
				if not natural: self._newline(-1)
				self._expect((KEYWORD, "JOIN"))
				self._parseTableRef2()
				if not natural: self._parseJoinCondition()
			elif self._match([(KEYWORD, "LEFT"), (KEYWORD, "RIGHT"), (KEYWORD, "FULL")]):
				if not natural: self._newline(-1)
				self._match((KEYWORD, "OUTER"))
				self._expect((KEYWORD, "JOIN"))
				self._parseTableRef2()
				if not natural: self._parseJoinCondition()
			elif self._match((KEYWORD, "JOIN")):
				if not natural: self._newline(-1)
				self._parseTableRef2()
				if not natural: self._parseJoinCondition()
			else:
				break

	def _parseTableRef2(self):
		"""Parses literal table references or functions in a table-reference"""
		# Ambiguity: A table or schema can be named TABLE, FINAL, OLD, etc.
		self._saveState()
		try:
			if self._match((OPERATOR, "(")):
				# Ambiguity: Open-parenthesis could indicate a full-select or a join group
				self._saveState()
				try:
					# Try and parse a full-select
					self._parseFullSelect1()
					self._expect((OPERATOR, ")"))
					self._parseTableCorrelation()
				except ParseError:
					# If it fails, rewind and try a table reference instead
					self._restoreState()
					self._parseTableRef1()
					self._expect((OPERATOR, ")"))
				else:
					self._forgetState()
			elif self._match((KEYWORD, "TABLE")):
				self._expect((OPERATOR, "("))
				# Ambiguity: TABLE() can indicate a table-function call or a nested table expression
				self._saveState()
				try:
					# Try and parse a full-select
					self._parseFullSelect1()
				except ParseError:
					# If it fails, rewind and try a table function call instead
					self._restoreState()
					self._parseTableFunction()
				else:
					self._forgetState()
				self._expect((OPERATOR, ")"))
				self._parseTableCorrelation()
			elif self._match([(KEYWORD, "FINAL"), (KEYWORD, "NEW")]):
				self._expect((KEYWORD, "TABLE"))
				self._expect((OPERATOR, "("))
				if self._expect([(KEYWORD, "INSERT"), (KEYWORD, "UPDATE")])[:2] == (KEYWORD, "INSERT"):
					self._parseInsertStatement()
				else:
					self._parseUpdateStatement()
				self._expect((OPERATOR, ")"))
				self._saveState()
				try:
					self._parseTableCorrelation()
				except ParseError:
					self._restoreState()
				else:
					self._forgetState()
			elif self._match((KEYWORD, "OLD")):
				self._expect((OPERATOR, "("))
				if self._expect([(KEYWORD, "UPDATE"), (KEYWORD, "DELETE")])[:2] == (KEYWORD, "DELETE"):
					self._parseDeleteStatement()
				else:
					self._parseUpdateStatement()
				self._expect((OPERATOR, ")"))
				self._saveState()
				try:
					self._parseTableCorrelation()
				except ParseError:
					self._restoreState()
				else:
					self._forgetState()
			else:
				raise ParseError()
		except ParseError:
			self._restoreState()
			self._parseSchemaObjectName()
			self._saveState()
			try:
				self._parseTableCorrelation()
			except ParseError:
				self._restoreState()
			else:
				self._forgetState()
		else:
			self._forgetState()

	def _parseJoinCondition(self):
		"""Parses the condition on an SQL-92 style join"""
		self._indent()
		if self._expect([(KEYWORD, "ON"), (KEYWORD, "USING")])[:2] == (KEYWORD, "ON"):
			self._parsePredicate1()
		else:
			# XXX Is the USING method standard SQL?
			self._expect((OPERATOR, "("))
			while True:
				self._keywordIdent()
				self._expect((IDENTIFIER,))
				if not self._match((OPERATOR, ",")):
					break
			self._expect((OPERATOR, ")"))
		self._outdent()

	def _parseFullSelect1(self):
		"""Parses set operators (low precedence) in a full-select expression"""
		self._parseFullSelect2()
		while True:
			if self._match([(KEYWORD, "UNION"), (KEYWORD, "INTERSECT"), (KEYWORD, "EXCEPT")]):
				self._newline(-1)
				self._match((KEYWORD, "ALL"))
				self._newline()
				self._newline()
				self._parseFullSelect2()
			else:
				break
		# Parse the optional ORDER BY clause
		# XXX Handle numeric column references
		if self._match((KEYWORD, "ORDER")):
			self._expect((KEYWORD, "BY"))
			while True:
				self._parseExpression1()
				# Parse the optional order specification
				self._match([(IDENTIFIER, "ASC"), (IDENTIFIER, "DESC")])
				if not self._match((OPERATOR, ",")):
					break
		# Parse the optional FETCH FIRST clause
		if self._match((KEYWORD, "FETCH")):
			self._expect((IDENTIFIER, "FIRST")) # FIRST isn't a keyword
			self._match((NUMBER,)) # Row count is optional (defaults to 1)
			self._expect([(KEYWORD, "ROW"), (KEYWORD, "ROWS")])
			self._expect((IDENTIFIER, "ONLY")) # ONLY isn't a keyword

	def _parseFullSelect2(self):
		"""Parses relation generators (high precedence) in a full-select expression"""
		if self._match((OPERATOR, "(")):
			self._parseFullSelect1()
			self._expect((OPERATOR, ")"))
		elif self._match((KEYWORD, "SELECT")):
			self._parseSubSelect()
		elif self._match((KEYWORD, "VALUES")):
			self._parseValues()
		else:
			self._expect([(KEYWORD, "SELECT"), (KEYWORD, "VALUES"), (OPERATOR, "(")])

	def _parseColumnDefinition(self):
		"""Parses a column definition in a CREATE TABLE statement"""
		# Parse a column definition
		self._keywordIdent()
		self._expect((IDENTIFIER,))
		self._parseDataType()
		# Parse column options
		while True:
			if self._match((KEYWORD, "NOT")):
				self._expect((KEYWORD, "NULL"))
			elif self._match((KEYWORD, "WITH")):
				self._expect((KEYWORD, "DEFAULT"))
				self._saveState()
				try:
					self._parseExpression1()
				except ParseError:
					self._restoreState()
				else:
					self._forgetState()
			elif self._match((KEYWORD, "DEFAULT")):
				self._saveState()
				try:
					self._parseExpression1()
				except ParseError:
					self._restoreState()
				else:
					self._forgetState()
			elif self._match((KEYWORD, "GENERATED")):
				if self._expect([(IDENTIFIER, "ALWAYS"), (KEYWORD, "BY")])[:2] == (KEYWORD, "BY"): # ALWAYS is not a KEYWORD
					self._expect((KEYWORD, "DEFAULT"))
				self._expect((KEYWORD, "AS"))
				if self._expect([(KEYWORD, "IDENTITY"), (OPERATOR, "(")])[:2] == (KEYWORD, "IDENTITY"):
					if self._match((OPERATOR, "(")):
						# XXX Allow backward compatibility options here?
						# Backward compatibility options include comma
						# separation of arguments, and NOMINVALUE instead
						# of NO MINVALUE, etc.
						while True:
							if self._match((KEYWORD, "START")):
								self._expect((KEYWORD, "WITH"))
								self._expect((NUMBER,))
							elif self._match((KEYWORD, "INCREMENT")):
								self._expect((KEYWORD, "BY"))
								self._expect((NUMBER,))
							elif self._match([(KEYWORD, "MINVALUE"), (KEYWORD, "MAXVALUE"), (KEYWORD, "CACHE")]):
								self._expect((NUMBER,))
							elif self._match((KEYWORD, "NO")):
								self._expect([(KEYWORD, "MINVALUE"), (KEYWORD, "MAXVALUE"), (KEYWORD, "CACHE"), (KEYWORD, "CYCLE"), (KEYWORD, "ORDER")])
							elif self._match((OPERATOR, ")")):
								break
							else:
								self._expect([(KEYWORD, "START"), (KEYWORD, "INCREMENT"), (KEYWORD, "MINVALUE"), (KEYWORD, "MAXVALUE"), (KEYWORD, "CACHE"), (KEYWORD, "ORDER")])
				else:
					self._parseExpression1()
					self._expect((OPERATOR, ")"))
			else:
				self._saveState()
				try:
					self._parseColumnConstraint()
				except ParseError:
					self._restoreState()
					break
				else:
					self._forgetState()

	def _parseColumnConstraint(self):
		"""Parses a constraint attached to a specific column in a CREATE TABLE statement"""
		# Parse the optional constraint name
		if self._match((KEYWORD, "CONSTRAINT")):
			self._keywordIdent()
			self._expect((IDENTIFIER,))
		# Parse the constraint definition
		if self._match((KEYWORD, "PRIMARY")):
			self._expect((KEYWORD, "KEY"))
		elif self._match((KEYWORD, "UNIQUE")):
			pass
		elif self._match((KEYWORD, "REFERENCES")):
			self._parseSchemaObjectName()
			if self._match((OPERATOR, "(")):
				self._keywordIdent()
				self._expect((IDENTIFIER,))
				self._expect((OPERATOR, ")"))
			t = [(KEYWORD, "DELETE"), (KEYWORD, "UPDATE")]
			for i in xrange(2):
				if self._match((KEYWORD, "ON")):
					t.remove(self._expect(t)[:2])
					if self._match((KEYWORD, "NO")):
						self._expect((IDENTIFIER, "ACTION")) # ACTION is not a KEYWORD
					elif self._match((KEYWORD, "SET")):
						self._expect((KEYWORD, "NULL"))
					else:
						self._expect([
							(KEYWORD, "RESTRICT"),
							(IDENTIFIER, "CASCADE"), # CASCADE is not a KEYWORD
							(KEYWORD, "NO"),
							(KEYWORD, "SET")
						])
				else:
					break
		elif self._match((KEYWORD, "CHECK")):
			self._expect((OPERATOR, "("))
			self._parsePredicate1()
			self._expect((OPERATOR, ")"))
		else:
			self._expect([
				(KEYWORD, "CONSTRAINT"),
				(KEYWORD, "PRIMARY"),
				(KEYWORD, "UNIQUE"),
				(KEYWORD, "REFERENCES"),
				(KEYWORD, "CHECK")
			])

	def _parseTableConstraint(self):
		"""Parses a constraint attached to a table in a CREATE TABLE statement"""
		if self._match((KEYWORD, "CONSTRAINT")):
			self._keywordIdent()
			self._expect((IDENTIFIER,))
		if self._match((KEYWORD, "PRIMARY")):
			self._expect((KEYWORD, "KEY"))
			self._expect((OPERATOR, "("))
			while True:
				self._keywordIdent()
				self._expect((IDENTIFIER,))
				if self._expect([(OPERATOR, ","), (OPERATOR, ")")])[:2] == (OPERATOR, ")"):
					break
		elif self._match((KEYWORD, "UNIQUE")):
			self._expect((OPERATOR, "("))
			while True:
				self._keywordIdent()
				self._expect((IDENTIFIER,))
				if self._expect([(OPERATOR, ","), (OPERATOR, ")")])[:2] == (OPERATOR, ")"):
					break
		elif self._match((KEYWORD, "FOREIGN")):
			self._expect((KEYWORD, "KEY"))
			self._expect((OPERATOR, "("))
			while True:
				self._keywordIdent()
				self._expect((IDENTIFIER,))
				if self._expect([(OPERATOR, ","), (OPERATOR, ")")])[:2] == (OPERATOR, ")"):
					break
			self._expect((KEYWORD, "REFERENCES"))
			self._parseSchemaObjectName()
			self._expect((OPERATOR, "("))
			while True:
				self._keywordIdent()
				self._expect((IDENTIFIER,))
				if self._expect([(OPERATOR, ","), (OPERATOR, ")")])[:2] == (OPERATOR, ")"):
					break
			t = [(KEYWORD, "DELETE"), (KEYWORD, "UPDATE")]
			for i in xrange(2):
				if self._match((KEYWORD, "ON")):
					t.remove(self._expect(t)[:2])
					if self._match((KEYWORD, "NO")):
						self._expect((IDENTIFIER, "ACTION")) # ACTION is not a KEYWORD
					elif self._match((KEYWORD, "SET")):
						self._expect((KEYWORD, "NULL"))
					else:
						self._expect([
							(KEYWORD, "RESTRICT"),
							(IDENTIFIER, "CASCADE"), # CASCADE is not a KEYWORD
							(KEYWORD, "NO"),
							(KEYWORD, "SET")
						])
				else:
					break
		elif self._match((KEYWORD, "CHECK")):
			self._expect((OPERATOR, "("))
			self._parsePredicate1()
			self._expect((OPERATOR, ")"))
		else:
			self._expect([
				(KEYWORD, "CONSTRAINT"),
				(KEYWORD, "PRIMARY"),
				(KEYWORD, "UNIQUE"),
				(KEYWORD, "FOREIGN"),
				(KEYWORD, "CHECK")
			])

	def _parseCallStatement(self):
		"""Parses a CALL statement"""
		# CALL already matched
		self._parseSchemaObjectName()
		if self._match((OPERATOR, "(")):
			while True:
				self._parseExpression1()
				if self._match([(OPERATOR, ","), (OPERATOR, ")")])[:2] == (OPERATOR, ")"):
					break
	
	def _parseSetStatement(self):
		"""Parses a SET statement in a dynamic compound statement"""
		# SET already matched
		while True:
			if self._match((OPERATOR, "(")):
				# Parse tuple assignment ( (FIELD1,FIELD2)=(...) )
				while True:
					self._keywordIdent()
					self._expect((IDENTIFIER,))
					if self._expect([(OPERATOR, ","), (OPERATOR, ")")])[:2] == (OPERATOR, ")"):
						break
				self._expect((OPERATOR, "="))
				self._expect((OPERATOR, "("))
				# Ambiguity: Tuple of expressions or a full-select
				self._saveState()
				try:
					self._indent()
					self._parseFullSelect1()
					self._outdent()
					self._expect((OPERATOR, ")"))
				except ParseError:
					self._restoreState()
					while True:
						self._parseExpression1()
						if self._expect([(OPERATOR, ","), (OPERATOR, ")")])[:2] == (OPERATOR, ")"):
							break
				else:
					self._forgetState()
			else:
				# Parse simple assignment (FIELD=VALUE)
				self._keywordIdent()
				self._expect((IDENTIFIER,))
				self._expect((OPERATOR, "="))
				self._parseExpression1()
			if not self._match((OPERATOR, ",")):
				break
	
	def _parseForStatement(self):
		"""Parses a FOR-loop in a dynamic compound statement"""
		# XXX Implement support for labels
		# FOR already matched
		self._keywordIdent()
		self._expect((IDENTIFIER,))
		self._expect((KEYWORD, "AS"))
		# XXX Implement support for CURSOR clause in procedures
		self._indent()
		self._parseSelectStatement()
		self._outdent()
		self._expect((KEYWORD, "DO"))
		self._indent()
		while True:
			self._parseRoutineStatement()
			self._expect((TERMINATOR, ";"))
			self._newline()
			if self._match((KEYWORD, "END")):
				break
		self._outdent(-1)
		self._expect((KEYWORD, "FOR"))
	
	def _parseWhileStatement(self):
		"""Parses a WHILE-loop in a dynamic compound statement"""
		# XXX Implement support for labels
		# WHILE already matched
		self._parsePredicate1()
		self._newline()
		self._expect((KEYWORD, "DO"))
		self._indent()
		while True:
			self._parseRoutineStatement()
			self._expect((TERMINATOR, ";"))
			self._newline()
			if self._match((KEYWORD, "END")):
				break
		self._outdent(-1)
		self._expect((KEYWORD, "WHILE"))
	
	def _parseGetDiagnosticStatement(self):
		"""Parses a GET DIAGNOSTICS statement in a dynamic compound statement"""
		# GET already matched
		self._expect((IDENTIFIER, "DIAGNOSTICS")) # DIAGNOSTIC is not a KEYWORD
		if self._match((KEYWORD, "EXCEPTION")):
			self._expect((NUMBER, 1))
			while True:
				self._keywordIdent()
				self._expect((IDENTIFIER,))
				self._expect((OPERATOR, "="))
				self._expect([
					(IDENTIFIER, "MESSAGE_TEXT"),
					(IDENTIFIER, "DB2_TOKEN_STRING")
				]) # MESSAGE_TEXT and DB2_TOKEN_STRING are not KEYWORDs
				if not self._match((OPERATOR, ",")):
					break
		else:
			self._keywordIdent()
			self._expect((IDENTIFIER,))
			self._expect((OPERATOR, "="))
			self._expect([
				(IDENTIFIER, "ROW_COUNT"),
				(IDENTIFIER, "DB2_RETURN_STATUS")
			]) # ROW_COUNT and DB2_RETURN_STATUS are not KEYWORDs
	
	def _parseIfStatement(self):
		"""Parses an IF-conditional in a dynamic compound statement"""
		# IF already matched
		t = (KEYWORD, "IF")
		while True:
			if t in ((KEYWORD, "IF"), (KEYWORD, "ELSEIF")):
				self._parsePredicate1()
				self._expect((KEYWORD, "THEN"))
				self._indent()
				while True:
					self._parseRoutineStatement()
					self._expect((TERMINATOR, ";"))
					self._newline()
					t = self._match([
						(KEYWORD, "ELSEIF"),
						(KEYWORD, "ELSE"),
						(KEYWORD, "END")
					])
					if t:
						self._outdent(-1)
						break
			elif t == (KEYWORD, "ELSE"):
				self._indent()
				while True:
					self._parseRoutineStatement()
					self._expect((TERMINATOR, ";"))
					if self._match((KEYWORD, "END")):
						self._outdent(-1)
						break
				break
			else:
				break
		self._expect((KEYWORD, "IF"))

	def _parseSignalStatement(self):
		"""Parses a SIGNAL statement in a dynamic compound statement"""
		# SIGNAL already matched
		if self._match((IDENTIFIER, "SQLSTATE")): # SQLSTATE is not a KEYWORD
			self._match((IDENTIFIER, "VALUE")) # VALUE is not a KEYWORD
			self._keywordIdent()
			self._expect([(IDENTIFIER,), (STRING,)])
		else:
			self._keywordIdent()
			self._expect((IDENTIFIER,))
		if self._match((KEYWORD, "SET")):
			self._expect((IDENTIFIER, "MESSAGE_TEXT"))
			self._expect((OPERATOR, "="))
			self._parseExpression1()
		# We deliberately don't parse the deprecated parenthesized expression
		# syntax here
	
	def _parseIterateStatement(self):
		"""Parses an ITERATE statement within a loop"""
		# ITERATE already matched
		self._keywordIdent()
		self._match((IDENTIFIER,))
	
	def _parseLeaveStatement(self):
		"""Parses a LEAVE statement within a loop"""
		# LEAVE already matched
		self._keywordIdent()
		self._match((IDENTIFIER,))
	
	def _parseReturnStatement(self):
		"""Parses a RETURN statement in a compound statement"""
		# RETURN already matched
		self._saveState()
		try:
			# Try and parse a select-statement
			self._parseSelectStatement()
		except ParseError:
			# If it fails, rewind and try an expression or tuple instead
			self._restoreState()
			self._parseExpression1()
		else:
			self._forgetState()

	def _parseDynamicCompoundStatement(self):
		"""Parses a dynamic compound statement"""
		# XXX Implement support for labelled blocks
		# XXX Only permit labels when part of a function/method/trigger
		# BEGIN already matched
		self._expect((IDENTIFIER, "ATOMIC")) # ATOMIC is not a KEYWORD
		self._indent()
		# Parse optional variable/condition declarations
		if self._match((KEYWORD, "DECLARE")):
			while True:
				self._keywordIdent()
				self._expect((IDENTIFIER,))
				if self._match((KEYWORD, "CONDITION")):
					self._expect((KEYWORD, "FOR"))
					if self._match((IDENTIFIER, "SQLSTATE")): # SQLSTATE is not a KEYWORD
						self._match((IDENTIFIER, "VALUE")) # VALUE is no a KEYWORD
					self._expect((STRING,))
				else:
					self._parseDataType()
					if self._match((KEYWORD, "DEFAULT")):
						self._parseExpression1()
				self._expect((TERMINATOR, ";"))
				self._newline()
				if not self._match((KEYWORD, "DECLARE")):
					break
		# Parse routine statements
		while True:
			self._parseRoutineStatement()
			self._expect((TERMINATOR, ";"))
			self._newline()
			if not self._match((KEYWORD, "END")):
				break
		self._outdent(-1)
	
	def _parseSelectStatement(self):
		"""Parses a SELECT statement optionally preceded by a common-table-expression"""
		# Parse the optional common-table-expression
		if self._match((KEYWORD, "WITH")):
			while True:
				self._keywordIdent()
				self._expect((IDENTIFIER,))
				# Parse the optional column-alias list
				if self._match((OPERATOR, "(")):
					self._indent()
					while True:
						self._keywordIdent()
						self._expect((IDENTIFIER,))
						if self._match((OPERATOR, ",")):
							self._newline()
						else:
							break
					self._outdent()
					self._expect((OPERATOR, ")"))
				self._expect((KEYWORD, "AS"))
				self._expect((OPERATOR, "("))
				self._indent()
				self._parseFullSelect1()
				self._outdent()
				self._expect((OPERATOR, ")"))
				if self._match((OPERATOR, ",")):
					self._newline()
				else:
					break
			self._newline()
		self._parseFullSelect1()
		# XXX Parse read-only-clause
		# XXX Parse update-clause
		# XXX Parse optimize-for-clause
		# XXX Parse isolation-clause

	def _parseInsertStatement(self):
		"""Parses an INSERT statement"""
		# XXX Add INCLUDE column capability and correlation clauses for target
		# INSERT already matched
		self._expect((KEYWORD, "INTO"))
		# XXX Parse table correlation
		self._parseSchemaObjectName()
		# Parse optional column list
		if self._match((OPERATOR, "(")):
			while True:
				self._keywordIdent()
				self._expect((IDENTIFIER,))
				if self._expect([(OPERATOR, ","), (OPERATOR, ")")])[:2] == (OPERATOR, ")"):
					break
		# XXX A common table expression is permitted here
		# Parse a full-select (SELECT or VALUES)
		self._parseFullSelect1()

	def _parseUpdateStatement(self):
		"""Parses an UPDATE statement"""
		# XXX Add INCLUDE column capability and correlation clauses for target
		# UPDATE already matched
		# XXX Parse table correlation
		self._parseSchemaObjectName()
		# Parse mandatory assignment clause
		self._expect((KEYWORD, "SET"))
		while True:
			if self._match((OPERATOR, "(")):
				# Parse tuple assignment ( (FIELD1,FIELD2)=(...) )
				while True:
					self._keywordIdent()
					self._expect((IDENTIFIER,))
					if self._expect([(OPERATOR, ","), (OPERATOR, ")")])[:2] == (OPERATOR, ")"):
						break
				self._expect((OPERATOR, "="))
				self._expect((OPERATOR, "("))
				# Ambiguity: Tuple of expressions or a full-select
				self._saveState()
				try:
					self._parseFullSelect1()
					self._expect((OPERATOR, ")"))
				except ParseError:
					self._restoreState()
					while True:
						if not self._match((KEYWORD, "DEFAULT")):
							self._parseExpression1()
						if self._expect([(OPERATOR, ","), (OPERATOR, ")")])[:2] == (OPERATOR, ")"):
							break
				else:
					self._forgetState()
			else:
				# Parse simple assignment (FIELD=VALUE)
				self._keywordIdent()
				self._expect((IDENTIFIER,))
				self._expect((OPERATOR, "="))
				if not self._match((KEYWORD, "DEFAULT")):
					self._parseExpression1()
			if not self._match((OPERATOR, ",")):
				break
		# Parse optional WHERE clause
		if self._match((KEYWORD, "WHERE")):
			self._parsePredicate1()

	def _parseDeleteStatement(self):
		"""Parses a DELETE statement"""
		# XXX Add INCLUDE column capability and correlation clauses for target
		# DELETE already matched
		self._expect((KEYWORD, "FROM"))
		# XXX Parse table correlation
		self._parseSchemaObjectName()
		# Parse optional WHERE clause
		if self._match((KEYWORD, "WHERE")):
			self._parsePredicate1()
	
	def _parseMergeStatement(self):
		# XXX Implement MERGE parsing
		pass

	def _parseCreateTableStatement(self):
		"""Parses a CREATE TABLE statement"""
		# CREATE TABLE already matched
		self._parseSchemaObjectName()
		# Parse elements
		self._expect((OPERATOR, "("))
		self._indent()
		while True:
			self._saveState()
			try:
				# Try parsing a table constraint definition
				self._parseTableConstraint()
			except ParseError:
				# If that fails, rewind and try and parse a column definition
				self._restoreState()
				self._parseColumnDefinition()
			else:
				self._forgetState()
			if self._match((OPERATOR, ",")):
				self._newline()
			else:
				break
		self._outdent()
		self._expect((OPERATOR, ")"))
		# Parse tablespaces
		if self._match((KEYWORD, "IN")):
			self._keywordIdent()
			self._expect((IDENTIFIER,))
			if self._match((KEYWORD, "INDEX")):
				self._expect((KEYWORD, "IN"))
				self._keywordIdent()
				self._expect((IDENTIFIER,))
			if self._match((KEYWORD, "LONG")):
				self._expect((KEYWORD, "IN"))
				self._keywordIdent()
				self._expect((IDENTIFIER,))

	def _parseAlterTableStatement(self):
		"""Parses an ALTER TABLE statement"""
		# ALTER TABLE already matched
		self._parseSchemaObjectName()
		self._indent()
		# XXX Implement ALTER TABLE sometable ALTER COLUMN/CONSTRAINT
		while True:
			if self._match((KEYWORD, "ADD")):
				if self._match((KEYWORD, "RESTRICT")):
					self._expect((KEYWORD, "ON"))
					self._expect((KEYWORD, "DROP"))
				elif self._match((KEYWORD, "COLUMN")):
					self._parseColumnDefinition()
				else:
					self._saveState()
					try:
						# Try parsing a table constraint definition
						self._parseTableConstraint()
					except ParseError:
						# If that fails, rewind and try and parse a column definition
						self._restoreState()
						self._parseColumnDefinition()
					else:
						self._forgetState()
			elif self._match((KEYWORD, "DROP")):
				if self._match((KEYWORD, "PRIMARY")):
					self._expect((KEYWORD, "KEY"))
				elif self._match((KEYWORD, "FOREIGN")):
					self._expect((KEYWORD, "KEY"))
					self._keywordIdent()
					self._expect((IDENTIFIER,))
				elif self._match([(KEYWORD, "UNIQUE"), (KEYWORD, "CHECK"), (KEYWORD, "CONSTRAINT")]):
					self._keywordIdent()
					self._expect((IDENTIFIER,))
				elif self._match((KEYWORD, "RESTRICT")):
					self._expect((KEYWORD, "ON"))
					self._expect((KEYWORD, "DROP"))
				else:
					self._expect([(KEYWORD, "PRIMARY"), (KEYWORD, "FOREIGN"), (KEYWORD, "CHECK"), (KEYWORD, "CONSTRAINT")])
			elif self._match((KEYWORD, "LOCKSIZE")):
				self._expect([(KEYWORD, "ROW"), (KEYWORD, "TABLE")])
			elif self._match((IDENTIFIER, "APPEND")):
				self._expect([(KEYWORD, "ON"), (IDENTIFIER, "OFF")])
			elif self._match((IDENTIFIER, "VOLATILE")):
				self._match((KEYWORD, "CARDINALITY"))
			elif self._match((KEYWORD, "NOT")):
				self._expect((IDENTIFIER, "VOLATILE"))
				self._match((KEYWORD, "CARDINALITY"))
			elif self._match((IDENTIFIER, "ACTIVATE")):
				if self._expect([(KEYWORD, "NOT"), (IDENTIFIER, "VALUE")])[:2] == (KEYWORD, "NOT"):
					self._expect((IDENTIFIER, "LOGGED"))
					self._expect((IDENTIFIER, "INITIALLY"))
					if self._match((KEYWORD, "WITH")):
						self._expect((IDENTIFIER, "EMPTY"))
						self._expect((KEYWORD, "TABLE"))
				else:
					self._expect((IDENTIFIER, "COMPRESSION"))
			elif self._match((IDENTIFIER, "DEACTIVATE")):
				self._expect((IDENTIFIER, "VALUE"))
				self._expect((IDENTIFIER, "COMPRESSION"))
			else:
				break
			self._newline()
		self._outdent()

	def _parseCreateIndexStatement(self):
		"""Parses a CREATE INDEX statement"""
		# CREATE [UNIQUE] INDEX already matched
		self._parseSchemaObjectName()
		self._indent()
		self._expect((KEYWORD, "ON"))
		self._parseSchemaObjectName()
		# Parse column list (with optional order indicators)
		self._expect((OPERATOR, "("))
		self._indent()
		while True:
			self._keywordIdent()
			self._expect((IDENTIFIER,))
			self._match([(IDENTIFIER, "ASC"), (IDENTIFIER, "DESC")]) # ASC and DESC aren't KEYWORDs
			if self._match((OPERATOR, ",")):
				self._newline()
			else:
				break
		self._outdent()
		self._expect((OPERATOR, ")"))
		# Parse optional include columns
		if self._match((IDENTIFIER, "INCLUDE")): # INCLUDE isn't a KEYWORD
			self._newline(-1)
			self._expect((OPERATOR, "("))
			self._indent()
			while True:
				self._keywordIdent()
				self._expect((IDENTIFIER,))
				if self._match((OPERATOR, ",")):
					self._newline()
				else:
					break
			self._outdent()
			self._expect((OPERATOR, ")"))
		# Parse index options
		if self._match([(KEYWORD, "ALLOW"), (KEYWORD, "DISALLOW")]):
			self._expect((IDENTIFIER, "REVERSE")) # REVERSE isn't a KEYWORD
			self._expect((IDENTIFIER, "SCANS")) # SCANS isn't a KEYWORD

	def _parseCreateViewStatement(self):
		"""Parses a CREATE VIEW statement"""
		# CREATE VIEW already matched
		self._parseSchemaObjectName()
		if self._match((OPERATOR, "(")):
			self._indent()
			while True:
				self._keywordIdent()
				self._expect((IDENTIFIER,))
				if self._match((OPERATOR, ",")):
					self._newline()
				else:
					break
			self._outdent()
			self._expect((OPERATOR, ")"))
		self._expect((KEYWORD, "AS"))
		self._newline()
		self._parseSelectStatement()

	def _parseCreateFunctionStatement(self):
		"""Parses a CREATE FUNCTION statement"""
		# CREATE FUNCTION already matched
		self._parseSchemaObjectName()
		# Parse parameter list
		self._expect((OPERATOR, "("))
		if not self._match((OPERATOR, ")")):
			while True:
				self._keywordIdent()
				self._expect((IDENTIFIER,))
				self._parseDataType()
				if self._expect([(OPERATOR, ","), (OPERATOR, ")")])[:2] == (OPERATOR, ")"):
					break
		self._indent()
		# Parse function options (which can appear in any order)
		valid = [
			((KEYWORD, "RETURNS")),
			((KEYWORD, "SPECIFIC")),
			((KEYWORD, "LANGUAGE")),
			((KEYWORD, "PARAMETER")),
			((KEYWORD, "NOT")),
			((KEYWORD, "DETERMINISTIC")),
			((KEYWORD, "NO")),
			((KEYWORD, "EXTERNAL")),
			((KEYWORD, "READS")),
			((KEYWORD, "MODIFIES")),
			((KEYWORD, "CONTAINS")),
			((KEYWORD, "STATIC")),
			((KEYWORD, "CALLED")),
			((KEYWORD, "NULL")),
			((KEYWORD, "INHERITS")),
		]
		while True:
			t = self._match(valid)
			if t:
				t = t[:2]
				valid.remove(t)
			else:
				break
			if t == (KEYWORD, "RETURNS"):
				if self._match([(KEYWORD, "ROW"), (KEYWORD, "TABLE")]):
					self._expect((OPERATOR, "("))
					while True:
						self._keywordIdent()
						self._expect((IDENTIFIER,))
						self._parseDataType()
						if self._expect([(OPERATOR, ","), (OPERATOR, ")")])[:2] == (OPERATOR, ")"):
							break
				else:
					self._parseDataType()
				self._newline()
			elif t == (KEYWORD, "SPECIFIC"):
				self._keywordIdent()
				self._expect((IDENTIFIER,))
				self._newline()
			elif t == (KEYWORD, "LANGUAGE"):
				self._expect((KEYWORD, "SQL"))
				self._newline()
			elif t == (KEYWORD, "PARAMETER"):
				self._expect((KEYWORD, "CCSID"))
				self._expect([
					(IDENTIFIER, "ASCII"), # ASCII is not a KEYWORD
					(IDENTIFIER, "UNICODE"), # UNICODE is not a KEYWORD
				])
				self._newline()
			elif t == (KEYWORD, "NOT"):
				self._expect((KEYWORD, "DETERMINISTIC"))
				valid.remove((KEYWORD, "DETERMINISTIC"))
				self._newline()
			elif t == (KEYWORD, "DETERMINISTIC"):
				valid.remove((KEYWORD, "NOT"))
				self._newline()
			elif t == (KEYWORD, "NO"):
				self._expect((KEYWORD, "EXTERNAL"))
				self._expect((IDENTIFIER, "ACTION")) # ACTION is not a KEYWORD
				valid.remove((KEYWORD, "EXTERNAL"))
				self._newline()
			elif t == (KEYWORD, "EXTERNAL"):
				self._expect((IDENTIFIER, "ACTION")) # ACTION is not a KEYWORD
				valid.remove((KEYWORD, "NO"))
				self._newline()
			elif t == (KEYWORD, "READS"):
				self._expect((KEYWORD, "SQL"))
				self._expect((KEYWORD, "DATA"))
				valid.remove((KEYWORD, "MODIFIES"))
				valid.remove((KEYWORD, "CONTAINS"))
				self._newline()
			elif t == (KEYWORD, "MODIFIES"):
				self._expect((KEYWORD, "SQL"))
				self._expect((KEYWORD, "DATA"))
				valid.remove((KEYWORD, "READS"))
				valid.remove((KEYWORD, "CONTAINS"))
				self._newline()
			elif t == (KEYWORD, "CONTAINS"):
				self._expect((KEYWORD, "SQL"))
				valid.remove((KEYWORD, "READS"))
				valid.remove((KEYWORD, "MODIFIES"))
				self._newline()
			elif t == (KEYWORD, "STATIC"):
				self._expect((IDENTIFIER, "DISPATCH")) # DISPATCH is not a KEYWORD
				self._newline()
			elif t == (KEYWORD, "CALLED"):
				self._expect((KEYWORD, "ON"))
				self._expect((KEYWORD, "NULL"))
				self._expect((IDENTIFIER, "INPUT")) # INPUT is not a KEYWORD
				valid.remove((KEYWORD, "NULL"))
				self._newline()
			elif t == (KEYWORD, "NULL"):
				self._expect((KEYWORD, "CALL"))
				valid.remove((KEYWORD, "CALLED"))
				self._newline()
			elif t == (KEYWORD, "INHERITS"):
				self._expect((IDENTIFIER, "SPECIAL")) # SPECIAL is not a KEYWORD
				self._expect((IDENTIFIER, "REGISTERS")) # REGISTERS is not a KEYWORD
				self._newline()
		# Parse optional PREDICATES clause
		if self._match((IDENTIFIER, "PREDICATES")): # PREDICATES is not a KEYWORD
			# XXX Implement the (horribly complex) PREDICATES clause
			pass
			self._newline()
		if self._match((KEYWORD, "INHERIT")):
			self._expect((KEYWORD, "ISOLATION"))
			self._expect((IDENTIFIER, "LEVEL")) # LEVEL is not a KEYWORD
			self._expect([
				(KEYWORD, "WITH"),
				(IDENTIFIER, "WITHOUT"), # WITHOUT is not a KEYWORD
			])
			self._expect((KEYWORD, "LOCK"))
			self._expect((IDENTIFIER, "REQUEST")) # REQUEST is not a KEYWORD
		# Parse the function body
		self._outdent()
		if self._expect([(KEYWORD, "BEGIN"), (KEYWORD, "RETURN")])[:2] == (KEYWORD, "BEGIN"):
			self._parseDynamicCompoundStatement()
		else:
			self._indent()
			self._parseReturnStatement()
			self._outdent()

	def _parseDropStatement(self):
		"""Parses a DROP statement"""
		# XXX Lots more things to implement here...
		# DROP already matched
		if self._match((KEYWORD, "ALIAS")):
			self._parseSchemaObjectName()
		elif self._match([(KEYWORD, "TABLE"), (KEYWORD, "VIEW")]):
			self._match((IDENTIFIER, "HIERARCHY")) # HIERARCHY is not a KEYWORD
			self._parseSchemaObjectName()
		elif self._match((KEYWORD, "INDEX")):
			if self._match((IDENTIFIER, "EXTENSION")): # EXTENSION is not a KEYWORD
				self._parseSchemaObjectName()
				self._expect((KEYWORD, "RESTRICT"))
			else:
				self._parseSchemaObjectName()
		elif self._match((KEYWORD, "FUNCTION")):
			self._parseSchemaObjectName()
			if self._match((OPERATOR, "(")):
				while True:
					self._parseDataType()
					if self._expect([(OPERATOR, ","), (OPERATOR, ")")])[:2] == (OPERATOR, ")"):
						break
			self._match((KEYWORD, "RESTRICT"))
		elif self._match((KEYWORD, "SPECIFIC")):
			self._parseSchemaObjectName()
			self._match((KEYWORD, "RESTRICT"))
		elif self._match([(KEYWORD, "DATA"), (KEYWORD, "DISTINCT")]):
			self._expect((KEYWORD, "TYPE"))
			self._parseSchemaObjectName()
		elif self._match((KEYWORD, "TYPE")):
			self._parseSchemaObjectName()
		elif self._match((KEYWORD, "SCHEMA")):
			self._keywordIdent()
			self._expect((IDENTIFIER,))
			# XXX Add CASCADE here for PostgreSQL?
			self._match((KEYWORD, "RESTRICT"))
		else:
			self._expect([
				(KEYWORD, "ALIAS"),
				(KEYWORD, "TABLE"),
				(KEYWORD, "VIEW"),
				(KEYWORD, "INDEX"),
				(KEYWORD, "FUNCTION"),
				(KEYWORD, "SPECIFIC"),
				(KEYWORD, "DISTINCT"),
				(KEYWORD, "DATA"),
				(KEYWORD, "TYPE"),
				(KEYWORD, "SCHEMA"),
			])

	def _parseRoutineStatement(self):
		"""Parses a statement in a routine/trigger/compound statement"""
		# XXX Only permit RETURN when part of a function/method/trigger
		# XXX Only permit ITERATE & LEAVE when part of a loop
		if self._match((KEYWORD, "CALL")):
			self._parseCallStatement()
		elif self._match((KEYWORD, "GET")):
			self._parseGetDiagnosticStatement()
		elif self._match((KEYWORD, "SET")):
			self._parseSetStatement()
		elif self._match((KEYWORD, "FOR")):
			self._parseForStatement()
		elif self._match((KEYWORD, "WHILE")):
			self._parseWhileStatement()
		elif self._match((KEYWORD, "IF")):
			self._parseIfStatement()
		elif self._match((KEYWORD, "SIGNAL")):
			self._parseSignalStatement()
		elif self._match((KEYWORD, "RETURN")):
			self._parseReturnStatement()
		elif self._match((KEYWORD, "ITERATE")):
			self._parseIterateStatement()
		elif self._match((KEYWORD, "LEAVE")):
			self._parseLeaveStatement()
		elif self._match((KEYWORD, "INSERT")):
			self._parseInsertStatement()
		elif self._match((KEYWORD, "UPDATE")):
			self._parseUpdateStatement()
		elif self._match((KEYWORD, "DELETE")):
			self._parseDeleteStatement()
		elif self._match((KEYWORD, "MERGE")):
			self._parseMergeStatement()
		else:
			self._parseSelectStatement()

	def _parseTopLevelStatement(self):
		"""Parses a top-level statement in an SQL script"""
		# XXX Implement dynamic compound statements
		# XXX Implement CREATE/DROP DB...
		# XXX Implement CREATE/DROP TABLESPACE...
		if self._match((KEYWORD, "BEGIN")):
			self._parseDynamicCompoundStatement()
		if self._match((KEYWORD, "INSERT")):
			self._parseInsertStatement()
		elif self._match((KEYWORD, "UPDATE")):
			self._parseUpdateStatement()
		elif self._match((KEYWORD, "DELETE")):
			self._parseDeleteStatement()
		elif self._match((KEYWORD, "MERGE")):
			self._parseMergeStatement()
		elif self._match((KEYWORD, "ALTER")):
			self._expect((KEYWORD, "TABLE"))
			self._parseAlterTableStatement()
		elif self._match((KEYWORD, "CREATE")):
			if self._match((KEYWORD, "TABLE")):
				self._parseCreateTableStatement()
			elif self._match((KEYWORD, "VIEW")):
				self._parseCreateViewStatement()
			elif self._match((KEYWORD, "UNIQUE")):
				self._expect((KEYWORD, "INDEX"))
				self._parseCreateIndexStatement()
			elif self._match((KEYWORD, "INDEX")):
				self._parseCreateIndexStatement()
			elif self._match((KEYWORD, "FUNCTION")):
				self._parseCreateFunctionStatement()
			else:
				self._expect([(KEYWORD, "TABLE"), (KEYWORD, "VIEW"), (KEYWORD, "INDEX")])
		elif self._match((KEYWORD, "DROP")):
			self._parseDropStatement()
		else:
			self._parseSelectStatement()

	def _parseInit(self, tokens):
		"""Sets up the parser with the specified tokens as input"""
		self._statestack = deque()
		# Check that newline_split wasn't used in the tokenizer
		if type(tokens[0]) == type([]):
			raise ParseError("Tokens must not be organized by line")
		self._tokens = list(tokens) # Take a COPY of the token list
		self._index = 0
		self._level = 0
		self._output = []
	
	def _parseFinish(self):
		"""Cleans up output tokens and recalculates line and column positions"""
		# Format/convert all output tokens
		self._output = [self._tokenOutput(token) for token in self._output]
		# Recalculate line and column elements for all tokens
		line = 1
		column = 1
		tokens = []
		for token in self._output:
			tokens.append(token + (line, column))
			(_, _, source) = token
			# Note that all line breaks are \n by this point
			while '\n' in source:
				line += 1
				column = 1
				source = source[source.index('\n') + 1:]
			column += len(source)
		self._output = tokens

	def _parseError(self, exception):
		"""Pretty-prints an ParseError exception with source context"""
		# Print the error message
		print "Error: %s" % (exception[0])
		# Print some context lines from the source
		(_, _, _, errorline, errorcol) = exception[1]
		currline = 1
		source = ''.join([s for (_, _, s, _, _) in self._tokens])
		for line in source.splitlines():
			if (currline >= errorline - 2) and (currline <= errorline + 2):
				print line
				# Highlight the position of the parse error
				if currline == errorline:
					print ' '*(errorcol-1) + '^'
			currline += 1

	def parseRoutinePrototype(self, tokens):
		"""Parses a routine prototype"""
		# It's a bit of hack sticking this here. This method doesn't really
		# belong here and should probably be in a sub-class (it's only used
		# for syntax highlighting function prototypes in the documentation
		# system)
		self._parseInit(tokens)
		try:
			# Skip leading whitespace
			if self._token()[0] in (COMMENT, WHITESPACE):
				self._skip()
			# Parse the function name
			self._parseSchemaObjectName()
			# Parenthesized parameter list is mandatory
			self._expect((OPERATOR, "("))
			if not self._match((OPERATOR, ")")):
				while True:
					# Parse parameter name
					self._keywordIdent()
					self._expect((IDENTIFIER,))
					# Parse parameter datatype
					self._parseDataType()
					if self._expect([(OPERATOR, ","), (OPERATOR, ")")])[:2] == (OPERATOR, ")"):
						break
			# Parse the return type
			self._expect((KEYWORD, "RETURNS"))
			if self._match([(KEYWORD, "ROW"), (KEYWORD, "TABLE")]):
				self._expect((OPERATOR, "("))
				while True:
					# Parse return parameter name
					self._keywordIdent()
					self._expect((IDENTIFIER,))
					# Parse return parameter datatype
					self._parseDataType()
					if self._expect([(OPERATOR, ","), (OPERATOR, ")")])[:2] == (OPERATOR, ")"):
						break
			else:
				self._parseDataType()
		except ParseError, e:
			self._parseError(e)
			raise
		self._parseFinish()
		return self._output

	def parse(self, tokens):
		"""Parses an arbitrary SQL statement or script"""
		self._parseInit(tokens)
		try:
			while True:
				# Skip leading whitespace
				if self._token()[0] in (COMMENT, WHITESPACE):
					self._skip()
				self._parseTopLevelStatement()
				# Look for a terminator or EOF
				if self._expect([(TERMINATOR,), (EOF,)])[:1] == (EOF,):
					break
				else:
					# Match any more terminators (blank statements)
					while self._match((TERMINATOR,)):
						pass
					# Check if EOF occurs after the terminator
					if self._match((EOF,)):
						break
					# Otherwise, reset the indent level and leave a blank line
					self._level = 0
					self._newline()
					self._newline()
		except ParseError, e:
			self._parseError(e)
			raise
		self._parseFinish()
		return self._output

if __name__ == "__main__":
	# XXX Robust test cases
	pass
