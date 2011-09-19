# vim: set noet sw=4 ts=4:

"""Implements a highly configurable SQL tokenizer.

This unit implements a configurable SQL tokenizer base class (BaseTokenizer)
and several classes descended from this which implement parsing specific
dialects of SQL, and their particular oddities.

A number of classes which tokenize specific SQL dialects are derived from the
base SQLTokenizer class. Currently the following classes are defined:

BaseTokenizer    -- Base tokenizer class
SQL92Tokenizer   -- ANSI SQL-92
SQL99Tokenizer   -- ANSI SQL-99
SQL2003Tokenizer -- ANSI SQL-2003
"""

from decimal import Decimal
from dbsuite.compat import *

__all__ = [
	'sql92_identchars',
	'sql92_namechars',
	'sql92_keywords',
	'sql99_identchars',
	'sql99_namechars',
	'sql99_keywords',
	'sql2003_identchars',
	'sql2003_namechars',
	'sql2003_keywords',
	'Error',
	'TokenError',
	'Token',
	'TokenTypes',
	'BaseTokenizer',
	'SQL92Tokenizer',
	'SQL99Tokenizer',
	'SQL2003Tokenizer',
]

# Set of characters valid in unquoted identifiers in ANSI SQL-92. This is the
# list of characters used by the tokenizer to recognize an identifier in input
# text. Hence it should include lowercase characters.

sql92_identchars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_0123456789'

# Set of characters valid in unquoted names in ANSI SQL-92. This is the list of
# characters used by the parser to determine when to quote an object's name in
# output text. Hence it should NOT include lowercase characters.

sql92_namechars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ_0123456789'

# Set of reserved keywords in ANSI SQL-92. Obtained from
# <http://developer.mimer.com/validator/sql-reserved-words.tml>

sql92_keywords = [
	'ABSOLUTE', 'ACTION', 'ADD', 'ALL', 'ALLOCATE', 'ALTER', 'AND', 'ANY',
	'ARE', 'AS', 'ASC', 'ASSERTION', 'AT', 'AUTHORIZATION', 'AVG', 'BEGIN',
	'BETWEEN', 'BIT', 'BIT_LENGTH', 'BOTH', 'BY', 'CALL', 'CASCADE',
	'CASCADED', 'CASE', 'CAST', 'CATALOG', 'CHAR', 'CHAR_LENGTH', 'CHARACTER',
	'CHARACTER_LENGTH', 'CHECK', 'CLOSE', 'COALESCE', 'COLLATE', 'COLLATION',
	'COLUMN', 'COMMIT', 'CONDITION', 'CONNECT', 'CONNECTION', 'CONSTRAINT',
	'CONSTRAINTS', 'CONTAINS', 'CONTINUE', 'CONVERT', 'CORRESPONDING', 'COUNT',
	'CREATE', 'CROSS', 'CURRENT', 'CURRENT_DATE', 'CURRENT_PATH',
	'CURRENT_TIME', 'CURRENT_TIMESTAMP', 'CURRENT_USER', 'CURSOR', 'DATE',
	'DAY', 'DEALLOCATE', 'DEC', 'DECIMAL', 'DECLARE', 'DEFAULT', 'DEFERRABLE',
	'DEFERRED', 'DELETE', 'DESC', 'DESCRIBE', 'DESCRIPTOR', 'DETERMINISTIC',
	'DIAGNOSTICS', 'DISCONNECT', 'DISTINCT', 'DO', 'DOMAIN', 'DOUBLE', 'DROP',
	'ELSE', 'ELSEIF', 'END', 'ESCAPE', 'EXCEPT', 'EXCEPTION', 'EXEC',
	'EXECUTE', 'EXISTS', 'EXIT', 'EXTERNAL', 'EXTRACT', 'FALSE', 'FETCH',
	'FIRST', 'FLOAT', 'FOR', 'FOREIGN', 'FOUND', 'FROM', 'FULL', 'FUNCTION',
	'GET', 'GLOBAL', 'GO', 'GOTO', 'GRANT', 'GROUP', 'HANDLER', 'HAVING',
	'HOUR', 'IDENTITY', 'IF', 'IMMEDIATE', 'IN', 'INDICATOR', 'INITIALLY',
	'INNER', 'INOUT', 'INPUT', 'INSENSITIVE', 'INSERT', 'INT', 'INTEGER',
	'INTERSECT', 'INTERVAL', 'INTO', 'IS', 'ISOLATION', 'JOIN', 'KEY',
	'LANGUAGE', 'LAST', 'LEADING', 'LEAVE', 'LEFT', 'LEVEL', 'LIKE', 'LOCAL',
	'LOOP', 'LOWER', 'MATCH', 'MAX', 'MIN', 'MINUTE', 'MODULE', 'MONTH',
	'NAMES', 'NATIONAL', 'NATURAL', 'NCHAR', 'NEXT', 'NO', 'NOT', 'NULL',
	'NULLIF', 'NUMERIC', 'OCTET_LENGTH', 'OF', 'ON', 'ONLY', 'OPEN', 'OPTION',
	'OR', 'ORDER', 'OUT', 'OUTER', 'OUTPUT', 'OVERLAPS', 'PAD', 'PARAMETER',
	'PARTIAL', 'PATH', 'POSITION', 'PRECISION', 'PREPARE', 'PRESERVE',
	'PRIMARY', 'PRIOR', 'PRIVILEGES', 'PROCEDURE', 'PUBLIC', 'READ', 'REAL',
	'REFERENCES', 'RELATIVE', 'REPEAT', 'RESIGNAL', 'RESTRICT', 'RETURN',
	'RETURNS', 'REVOKE', 'RIGHT', 'ROLLBACK', 'ROUTINE', 'ROWS', 'SCHEMA',
	'SCROLL', 'SECOND', 'SECTION', 'SELECT', 'SESSION', 'SESSION_USER', 'SET',
	'SIGNAL', 'SIZE', 'SMALLINT', 'SOME', 'SPACE', 'SPECIFIC', 'SQL',
	'SQLCODE', 'SQLERROR', 'SQLEXCEPTION', 'SQLSTATE', 'SQLWARNING',
	'SUBSTRING', 'SUM', 'SYSTEM_USER', 'TABLE', 'TEMPORARY', 'THEN', 'TIME',
	'TIMESTAMP', 'TIMEZONE_HOUR', 'TIMEZONE_MINUTE', 'TO', 'TRAILING',
	'TRANSACTION', 'TRANSLATE', 'TRANSLATION', 'TRIM', 'TRUE', 'UNDO', 'UNION',
	'UNIQUE', 'UNKNOWN', 'UNTIL', 'UPDATE', 'UPPER', 'USAGE', 'USER', 'USING',
	'VALUE', 'VALUES', 'VARCHAR', 'VARYING', 'VIEW', 'WHEN', 'WHENEVER',
	'WHERE', 'WHILE', 'WITH', 'WORK', 'WRITE', 'YEAR', 'ZONE',
]

# Set of characters valid in unquoted identifiers and names in ANSI SQL-99 (see
# above)

sql99_identchars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_0123456789'
sql99_namechars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ_0123456789'

# Set of reserved keywords in ANSI SQL-99. Obtained from
# <http://developer.mimer.com/validator/sql-reserved-words.tml>

sql99_keywords = [
	'ABSOLUTE', 'ACTION', 'ADD', 'AFTER', 'ALL', 'ALLOCATE', 'ALTER', 'AND',
	'ANY', 'ARE', 'ARRAY', 'AS', 'ASC', 'ASENSITIVE', 'ASSERTION',
	'ASYMMETRIC', 'AT', 'ATOMIC', 'AUTHORIZATION', 'BEFORE', 'BEGIN',
	'BETWEEN', 'BINARY', 'BIT', 'BLOB', 'BOOLEAN', 'BOTH', 'BREADTH', 'BY',
	'CALL', 'CALLED', 'CASCADE', 'CASCADED', 'CASE', 'CAST', 'CATALOG', 'CHAR',
	'CHARACTER', 'CHECK', 'CLOB', 'CLOSE', 'COLLATE', 'COLLATION', 'COLUMN',
	'COMMIT', 'CONDITION', 'CONNECT', 'CONNECTION', 'CONSTRAINT',
	'CONSTRAINTS', 'CONSTRUCTOR', 'CONTINUE', 'CORRESPONDING', 'CREATE',
	'CROSS', 'CUBE', 'CURRENT', 'CURRENT_DATE',
	'CURRENT_DEFAULT_TRANSFORM_GROUP', 'CURRENT_PATH', 'CURRENT_ROLE',
	'CURRENT_TIME', 'CURRENT_TIMESTAMP', 'CURRENT_TRANSFORM_GROUP_FOR_TYPE',
	'CURRENT_USER', 'CURSOR', 'CYCLE', 'DATA', 'DATE', 'DAY', 'DEALLOCATE',
	'DEC', 'DECIMAL', 'DECLARE', 'DEFAULT', 'DEFERRABLE', 'DEFERRED', 'DELETE',
	'DEPTH', 'DEREF', 'DESC', 'DESCRIBE', 'DESCRIPTOR', 'DETERMINISTIC',
	'DIAGNOSTICS', 'DISCONNECT', 'DISTINCT', 'DO', 'DOMAIN', 'DOUBLE', 'DROP',
	'DYNAMIC', 'EACH', 'ELSE', 'ELSEIF', 'END', 'EQUALS', 'ESCAPE', 'EXCEPT',
	'EXCEPTION', 'EXEC', 'EXECUTE', 'EXISTS', 'EXIT', 'EXTERNAL', 'FALSE',
	'FETCH', 'FILTER', 'FIRST', 'FLOAT', 'FOR', 'FOREIGN', 'FOUND', 'FREE',
	'FROM', 'FULL', 'FUNCTION', 'GENERAL', 'GET', 'GLOBAL', 'GO', 'GOTO',
	'GRANT', 'GROUP', 'GROUPING', 'HANDLER', 'HAVING', 'HOLD', 'HOUR',
	'IDENTITY', 'IF', 'IMMEDIATE', 'IN', 'INDICATOR', 'INITIALLY', 'INNER',
	'INOUT', 'INPUT', 'INSENSITIVE', 'INSERT', 'INT', 'INTEGER', 'INTERSECT',
	'INTERVAL', 'INTO', 'IS', 'ISOLATION', 'ITERATE', 'JOIN', 'KEY',
	'LANGUAGE', 'LARGE', 'LAST', 'LATERAL', 'LEADING', 'LEAVE', 'LEFT',
	'LEVEL', 'LIKE', 'LOCAL', 'LOCALTIME', 'LOCALTIMESTAMP', 'LOCATOR', 'LOOP',
	'MAP', 'MATCH', 'METHOD', 'MINUTE', 'MODIFIES', 'MODULE', 'MONTH', 'NAMES',
	'NATIONAL', 'NATURAL', 'NCHAR', 'NCLOB', 'NEW', 'NEXT', 'NO', 'NONE',
	'NOT', 'NULL', 'NUMERIC', 'OBJECT', 'OF', 'OLD', 'ON', 'ONLY', 'OPEN',
	'OPTION', 'OR', 'ORDER', 'ORDINALITY', 'OUT', 'OUTER', 'OUTPUT', 'OVER',
	'OVERLAPS', 'PAD', 'PARAMETER', 'PARTIAL', 'PARTITION', 'PATH',
	'PRECISION', 'PREPARE', 'PRESERVE', 'PRIMARY', 'PRIOR', 'PRIVILEGES',
	'PROCEDURE', 'PUBLIC', 'RANGE', 'READ', 'READS', 'REAL', 'RECURSIVE',
	'REF', 'REFERENCES', 'REFERENCING', 'RELATIVE', 'RELEASE', 'REPEAT',
	'RESIGNAL', 'RESTRICT', 'RESULT', 'RETURN', 'RETURNS', 'REVOKE', 'RIGHT',
	'ROLE', 'ROLLBACK', 'ROLLUP', 'ROUTINE', 'ROW', 'ROWS', 'SAVEPOINT',
	'SCHEMA', 'SCOPE', 'SCROLL', 'SEARCH', 'SECOND', 'SECTION', 'SELECT',
	'SENSITIVE', 'SESSION', 'SESSION_USER', 'SET', 'SETS', 'SIGNAL', 'SIMILAR',
	'SIZE', 'SMALLINT', 'SOME', 'SPACE', 'SPECIFIC', 'SPECIFICTYPE', 'SQL',
	'SQLEXCEPTION', 'SQLSTATE', 'SQLWARNING', 'START', 'STATE', 'STATIC',
	'SYMMETRIC', 'SYSTEM', 'SYSTEM_USER', 'TABLE', 'TEMPORARY', 'THEN', 'TIME',
	'TIMESTAMP', 'TIMEZONE_HOUR', 'TIMEZONE_MINUTE', 'TO', 'TRAILING',
	'TRANSACTION', 'TRANSLATION', 'TREAT', 'TRIGGER', 'TRUE', 'UNDER', 'UNDO',
	'UNION', 'UNIQUE', 'UNKNOWN', 'UNNEST', 'UNTIL', 'UPDATE', 'USAGE', 'USER',
	'USING', 'VALUE', 'VALUES', 'VARCHAR', 'VARYING', 'VIEW', 'WHEN',
	'WHENEVER', 'WHERE', 'WHILE', 'WINDOW', 'WITH', 'WITHIN', 'WITHOUT',
	'WORK', 'WRITE', 'YEAR', 'ZONE',
]

# Set of characters valid in unquoted identifiers and names in ANSI SQL-2003
# (see above)

sql2003_identchars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_0123456789'
sql2003_namechars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ_0123456789'

# Set of reserved keywords in ANSI SQL-2003. Obtained from
# <http://developer.mimer.com/validator/sql-reserved-words.tml>

sql2003_keywords = [
	'ADD', 'ALL', 'ALLOCATE', 'ALTER', 'AND', 'ANY', 'ARE', 'ARRAY', 'AS',
	'ASENSITIVE', 'ASYMMETRIC', 'AT', 'ATOMIC', 'AUTHORIZATION', 'BEGIN',
	'BETWEEN', 'BIGINT', 'BINARY', 'BLOB', 'BOOLEAN', 'BOTH', 'BY', 'CALL',
	'CALLED', 'CASCADED', 'CASE', 'CAST', 'CHAR', 'CHARACTER', 'CHECK', 'CLOB',
	'CLOSE', 'COLLATE', 'COLUMN', 'COMMIT', 'CONDITION', 'CONNECT',
	'CONSTRAINT', 'CONTINUE', 'CORRESPONDING', 'CREATE', 'CROSS', 'CUBE',
	'CURRENT', 'CURRENT_DATE', 'CURRENT_DEFAULT_TRANSFORM_GROUP',
	'CURRENT_PATH', 'CURRENT_ROLE', 'CURRENT_TIME', 'CURRENT_TIMESTAMP',
	'CURRENT_TRANSFORM_GROUP_FOR_TYPE', 'CURRENT_USER', 'CURSOR', 'CYCLE',
	'DATE', 'DAY', 'DEALLOCATE', 'DEC', 'DECIMAL', 'DECLARE', 'DEFAULT',
	'DELETE', 'DEREF', 'DESCRIBE', 'DETERMINISTIC', 'DISCONNECT', 'DISTINCT',
	'DO', 'DOUBLE', 'DROP', 'DYNAMIC', 'EACH', 'ELEMENT', 'ELSE', 'ELSEIF',
	'END', 'ESCAPE', 'EXCEPT', 'EXEC', 'EXECUTE', 'EXISTS', 'EXIT', 'EXTERNAL',
	'FALSE', 'FETCH', 'FILTER', 'FLOAT', 'FOR', 'FOREIGN', 'FREE', 'FROM',
	'FULL', 'FUNCTION', 'GET', 'GLOBAL', 'GRANT', 'GROUP', 'GROUPING',
	'HANDLER', 'HAVING', 'HOLD', 'HOUR', 'IDENTITY', 'IF', 'IMMEDIATE', 'IN',
	'INDICATOR', 'INNER', 'INOUT', 'INPUT', 'INSENSITIVE', 'INSERT', 'INT',
	'INTEGER', 'INTERSECT', 'INTERVAL', 'INTO', 'IS', 'ITERATE', 'JOIN',
	'LANGUAGE', 'LARGE', 'LATERAL', 'LEADING', 'LEAVE', 'LEFT', 'LIKE',
	'LOCAL', 'LOCALTIME', 'LOCALTIMESTAMP', 'LOOP', 'MATCH', 'MEMBER', 'MERGE',
	'METHOD', 'MINUTE', 'MODIFIES', 'MODULE', 'MONTH', 'MULTISET', 'NATIONAL',
	'NATURAL', 'NCHAR', 'NCLOB', 'NEW', 'NO', 'NONE', 'NOT', 'NULL', 'NUMERIC',
	'OF', 'OLD', 'ON', 'ONLY', 'OPEN', 'OR', 'ORDER', 'OUT', 'OUTER', 'OUTPUT',
	'OVER', 'OVERLAPS', 'PARAMETER', 'PARTITION', 'PRECISION', 'PREPARE',
	'PRIMARY', 'PROCEDURE', 'RANGE', 'READS', 'REAL', 'RECURSIVE', 'REF',
	'REFERENCES', 'REFERENCING', 'RELEASE', 'REPEAT', 'RESIGNAL', 'RESULT',
	'RETURN', 'RETURNS', 'REVOKE', 'RIGHT', 'ROLLBACK', 'ROLLUP', 'ROW',
	'ROWS', 'SAVEPOINT', 'SCOPE', 'SCROLL', 'SEARCH', 'SECOND', 'SELECT',
	'SENSITIVE', 'SESSION_USER', 'SET', 'SIGNAL', 'SIMILAR', 'SMALLINT',
	'SOME', 'SPECIFIC', 'SPECIFICTYPE', 'SQL', 'SQLEXCEPTION', 'SQLSTATE',
	'SQLWARNING', 'START', 'STATIC', 'SUBMULTISET', 'SYMMETRIC', 'SYSTEM',
	'SYSTEM_USER', 'TABLE', 'TABLESAMPLE', 'THEN', 'TIME', 'TIMESTAMP',
	'TIMEZONE_HOUR', 'TIMEZONE_MINUTE', 'TO', 'TRAILING', 'TRANSLATION',
	'TREAT', 'TRIGGER', 'TRUE', 'UNDO', 'UNION', 'UNIQUE', 'UNKNOWN', 'UNNEST',
	'UNTIL', 'UPDATE', 'USER', 'USING', 'VALUE', 'VALUES', 'VARCHAR',
	'VARYING', 'WHEN', 'WHENEVER', 'WHERE', 'WHILE', 'WINDOW', 'WITH',
	'WITHIN', 'WITHOUT', 'YEAR',
]

class Error(Exception):
	"""Base class for errors in this module."""
	pass

class TokenError(Error):
	"""Raised when a token-related error is encountered."""

	def __init__(self, source, token, msg, context_lines=5):
		"""Initializes an instance of the exception.

		The parameters are as follows:
		source -- The source being parsed
		token -- The token at which the error occurred
		msg -- The descriptive error message
		context_lines -- The number of lines of context to display in messages
		"""
		# Store the error token and source
		self.source = source
		self.token = token
		self.line, self.column = token.line, token.column
		self.context_lines = context_lines
		# Initialize the exception
		Error.__init__(self, msg)

	def __str__(self):
		"""Outputs a string version of the exception."""
		# Generate a block of context with an indicator showing the error
		source_lines = self.source.splitlines()
		line_index = self.line - 1
		if self.line > len(source_lines):
			line_index = -1
		marker = ''.join({'\t': '\t'}.get(c, ' ') for c in source_lines[line_index][:self.column - 1]) + '^'
		source_lines.insert(self.line, marker)
		i = self.line - self.context_lines
		if i < 0:
			i = 0
		context = '\n'.join(source_lines[i:self.line + self.context_lines])
		# Format the message with the context
		return '\n'.join([
			self.args[0] + ':',
			'line   : %d' % self.line,
			'column : %d' % self.column,
			'context:',
			context
		])


class TokenTypes(object):
	"""Simple utility class for defining token type constants."""

	def __init__(self):
		super(TokenTypes, self).__init__()
		self.names = {}
		self._counter = 0

	def add(self, new_type, type_name=None):
		if hasattr(self, new_type):
			raise ValueError('%s is already registered as a token type' % new_type)
		if type_name is None:
			type_name = new_type
		setattr(self, new_type, self._counter)
		self.names[self._counter] = type_name
		self._counter += 1

# Replace the class with an instance of itself and a conveniently short alias
TokenTypes = TokenTypes()
TT = TokenTypes


# Define the set of tokens required by the tokenizers below
for (type, name) in (
	('ERROR',      None),            # Invalid/unknown token
	('WHITESPACE', '<space>'),       # Whitespace
	('COMMENT',    '<comment>'),     # A comment
	('KEYWORD',    '<keyword>'),     # A reserved keyword (SELECT/UPDATE/INSERT/etc.)
	('IDENTIFIER', '<name>'),        # A quoted or unquoted identifier
	('NUMBER',     '<number>'),      # A numeric literal
	('STRING',     '<string>'),      # A string literal
	('OPERATOR',   '<operator>'),    # An operator
	('LABEL',      '<label>'),       # A procedural label
	('PARAMETER',  '<parameter>'),   # A colon-prefixed or simple qmark parameter
	('TERMINATOR', '<terminator>'),  # A statement terminator
):
	TT.add(type, name)

# Declare the Token namedtuple class
Token = namedtuple('Token', (
	'type',
	'value',
	'source',
	'line',
	'column'
))


class BaseTokenizer(object):
	"""Base SQL tokenizer class.

	This base tokenizer class is used to convert a string containing SQL source
	code into a list of "tokens". See the parse() method for more information
	on the structure of tokens.

	Various options are available to customize the behaviour of the tokenizer
	(primarily to ease implementation of the dialect-specific subclasses,
	though they may be of use in other situations):

	keywords       The set of words that are to be treated as reserved
	               keywords.
	ident_chars    The set of characters that can appear in an unquoted
	               identifier. Note that the parser automatically excludes
	               numerals from this set for the initial character of an
	               identifier.
	sql_comments   If True (the default), SQL style comments (--..EOL) will be
	               recognized.
	c_comments     If True, C style comments (/*..*/) will be recognized.
	c_comments_nested If True, C stytle comments (/*..*/) are allowed to be
	               nested - this is in accordance with SQL 2003 but is not
	               widely implemented.
	cpp_comments   If True, C++ style comments (//..EOL) will be recognized.
	multiline_str  If True (the default), string literals will be permitted to
	               span lines.
	raise_errors   If True (the default), errors encountered during parsing
	               will be raised as TokenError exceptions. If False, errors
	               will be returned as ERROR tokens and parsing will continue.
	"""

	def __init__(self):
		self.keywords = set(sql92_keywords)
		self.ident_chars = set(sql92_identchars)
		self.space_chars = ' \t\r\n'
		self.sql_comments = True
		self.c_comments = False
		self.c_comments_nested = False
		self.cpp_comments = False
		self.multiline_str = True
		self.raise_errors = True

	def parse(self, sql, terminator=';', line_split=False):
		"""Parses the provided source into a list of token tuples.

		This is the only public method of the tokenizer class, called to
		tokenize the provided source.  The method returns a list of 5-element
		tuples with the following structure:

			(type, value, source, line, column)

		The elements of the tuple can also be accessed by the names listed
		above (tokens are instances of the Token namedtuple class).

		The type element is one of the token constants described below, value
		is the "value" of the token (depends on type, see below), source is the
		characters from sql parsed to construct the token, and line and column
		provide the 1-based line and column of the start of the source element
		in sql. All source elements can be concatenated to reconstruct the
		original source verbatim. Hence:

			tokens = SQLTokenizer().tokenize(sql)
			sql == ''.join([source for (_, _, source, _, _) in tokens])

		Depending on token type, the token's value has different content:

			ERROR          A descriptive error message
			WHITESPACE     None
			COMMENT        The content of the comment (excluding delimiters)
			KEYWORD        The keyword folded into uppercase
			IDENTIFIER     The identifier folded into uppercase if it was
			               unquoted in the source, or in original case if it
			               was quoted in some fashion in the source
			LABEL          Same as IDENTIFIER
			NUMBER         The value of the number. A number with no decimal
			               portion is converted to a python long. A number with
			               a decimal portion is converted to Decimal, while a
			               number with an exponent is converted to a float
			               (regardless of presence or absence of decimal
			               portion)
			STRING         The content of the string (unquoted and unescaped)
			OPERATOR       The operator
			PARAMETER      The name of the parameter if it was a colon-prefixed
			               named parameter in the source, or None for anonymous
			               parameters
			TERMINATOR     None

		The sql parameter specifies the SQL script to tokenize. The optional
		terminator parameter specifies the character or string used to separate
		top-level statements in the script. The optional line_split parameter
		specifies whether multiline tokens will be split in the output. If
		False (the default), multi-line tokens will be returned as a single
		token - hence, one can assume WHITESPACE or COMMENT tokens will never
		be immediately followed by another token of the same type. If True,
		tokens will be split at line breaks to ensure every line has a token
		with column 1 (useful when performing per-line processing on the
		result).
		"""
		self._states = []
		self._source = sql
		self._index = 0
		self._marked_index = -1
		self._line = 1
		self._line_start = 0
		self._token_start = 0
		self._token_line = self.line
		self._token_column = self.column
		self._tokens = []
		self._init_jump()
		# Note that setting terminator must be done AFTER initializing the jump
		# table as doing so re-writes elements within that table. The
		# terminator is not handled within _init_jump as some dialects may
		# permit changes to the terminator in the middle of a script.
		# Descendents of this class wishing to implement such behaviour simply
		# need to set the terminator property during tokenizing.
		self._terminator = None
		self._saved_handler = None
		self.terminator = terminator
		# Loop over the sql using the jump table to parse characters (note:
		# Python strings aren't null terminated; the _char property simply
		# returns a null character when _index moves beyond the end of the
		# string)
		while self._char != '\0':
			self._jump.get(self._char, self._handle_default)()
		# If line_split is True, split up any tokens that cross line breaks
		# (much easier to do it here than in the tokenizer itself)
		if line_split:
			result = []
			for token in self._tokens:
				(type, value, source, line, column) = token
				while '\n' in source:
					if isinstance(value, basestring) and '\n' in value:
						i = value.index('\n') + 1
						newvalue, value = value[:i], value[i:]
					else:
						newvalue = value
					i = source.index('\n') + 1
					newsource, source = source[:i], source[i:]
					result.append(Token(type, newvalue, newsource, line, column))
					line += 1
					column = 1
				if source or type not in (TT.WHITESPACE, TT.COMMENT):
					result.append(Token(type, value, source, line, column))
			self._tokens = result
		return self._tokens

	def _init_jump(self):
		"""Initializes a dictionary of character handlers."""
		self._jump = {}
		for char in self.space_chars:
			self._jump[char] = self._handle_space
		for char in self.ident_chars:
			self._jump[char] = self._handle_ident
		# If numerals were included in ident_chars above, they will be
		# overwritten by the next bit (numerals are never permitted as the
		# first character in an unquoted identifier)
		for char in '0123456789':
			self._jump[char] = self._handle_digit
		# Add jump entries for symbols. Descendent classes will add extra
		# symbols that they handle after this
		self._jump.update({
			'(': self._handle_open_parens,
			')': self._handle_close_parens,
			'+': self._handle_plus,
			'-': self._handle_minus,
			'*': self._handle_asterisk,
			'/': self._handle_slash,
			'.': self._handle_period,
			',': self._handle_comma,
			':': self._handle_colon,
			'?': self._handle_question,
			'<': self._handle_less,
			'=': self._handle_equal,
			'>': self._handle_greater,
			"'": self._handle_apos,
			'"': self._handle_quote,
			'|': self._handle_bar,
			';': self._handle_semicolon,
		})

	def _add_token(self, type, value):
		"""Adds the current token to the output list.

		This utility method adds the token which ends at the current _index to
		the output list (_tokens). The start of the token, and it's line and
		column in the input is tracked  by the internal _token_start,
		_token_line, and _token_column attributes and may not be specified. The
		type and value parameters specify the type and value (first and second
		elements of the token) respectively.
		"""
		token = Token(
			type,
			value,
			self._source[self._token_start:self._index],
			self._token_line,
			self._token_column
		)
		if type == TT.ERROR and self.raise_errors:
			raise TokenError(self._source, token, value)
		self._tokens.append(token)
		self._token_start = self._index
		self._token_line = self.line
		self._token_column = self.column

	def _save_state(self):
		"""Saves the current state of the tokenizer on a stack for later retrieval."""
		self._states.append((
			self._index,
			self._line,
			self._line_start,
			self._token_start,
			self._token_line,
			self._token_column,
			len(self._tokens)
		))

	def _restore_state(self):
		"""Restores the state of the tokenizer from the head of the save stack."""
		(
			self._index,
			self._line,
			self._line_start,
			self._token_start,
			self._token_line,
			self._token_column,
			tokens_len
		) = self._states.pop()
		del self._tokens[tokens_len:]

	def _forget_state(self):
		"""Destroys the saved state at the head of the save stack."""
		self._states.pop()

	def _next(self, count=1):
		"""Moves the position of the tokenizer forward count positions.

		The _index variable should never be modified directly by handler
		methods. Likewise, the _source variable should never be directly read
		by handler methods. Instead, use the _next() method and the _char
		property. The _next() method keeps track of the current line and column
		positions, while the _char property handles reporting all line breaks
		(CR, CR/LF, or just LF) as plain LF characters (making handler coding
		easier).
		"""
		while count > 0:
			count -= 1
			if self._source[self._index] == '\r':
				if self._source[self._index + 1] == '\n':
					self._index += 2
				else:
					self._index += 1
				self._line += 1
				self._line_start = self._index
			elif self._source[self._index] == '\n':
				self._index += 1
				self._line += 1
				self._line_start = self._index
			else:
				self._index += 1

	@property
	def _char(self):
		"""Returns the current character at the position of the tokenizer.

		Returns the character in _source at _index, but converts all line
		breaks to a single LF character as this makes handler code slightly
		easier to write.
		"""
		try:
			if self._source[self._index] == '\r':
				return '\n'
			else:
				return self._source[self._index]
		except IndexError:
			return '\0'

	def _peek(self, count=1):
		"""Returns the character the next position of the tokenizer.

		Returns the character immediately after the current character in
		_source, and (like the _char property) handles converting all line
		breaks into single LF characters. If count is specified it indicates
		how many characters ahead to peek.
		"""
		self._save_state()
		try:
			self._next(count)
			return self._char
		finally:
			self._restore_state()

	def _mark(self):
		"""Marks the current position in the source for later retrieval.

		The _mark() method is used with the _marked_chars property. A handler
		can call mark to save the current position in the source code, then
		query _marked_chars to obtain a string of all characters from the
		marked position to the current position (assuming the handler has moved
		the current position forward since calling _mark().

		The _marked_chars property handles converting all line breaks to LF
		(like the _next() method and _char property).
		"""
		self._marked_index = self._index

	@property
	def _marked_chars(self):
		"""Returns the characters from the marked position to the current.

		After calling _mark() at a starting position, a handler can later use
		_marked_chars to retrieve all characters from that marked position to
		the current position (useful for extracting the content of large blocks
		of code like comments, strings, etc).
		"""
		assert self._marked_index >= 0
		return self._source[self._marked_index:self._index].replace('\r\n', '\n').replace('\r', '\n')

	@property
	def line(self):
		"""Returns the current 1-based line position."""
		return self._line

	@property
	def column(self):
		"""Returns the current 1-based column position."""
		return (self._index - self._line_start) + 1

	def _get_terminator(self):
		"""Returns the current statement terminator string (or character)."""
		return self._terminator
	def _set_terminator(self, value):
		"""Sets the current statement terminator string (or character).

		The _set_terminator() method sets the current terminator string (or
		character), and updates the internal jump table as necessary.
		"""
		if not value:
			raise ValueError("Statement terminator string must contain at least one character")
		# Restore the saved handler, if necessary. We don't need to do this
		# if there was no prior terminator (such as in a new instance of
		# the class). If the saved handler is the default handler (None),
		# simply remove the first character of the terminator from the jump
		# table
		if self._terminator is not None:
			if self._saved_handler is None:
				del self._jump[self._terminator[0]]
			else:
				self._jump[self._terminator[0]] = self._saved_handler
		# Replace the handler (if any) for the statement terminator
		# character (or the first character of the statement terminator
		# string) with a special handler and save the original handler for
		# use by the special handler
		if (value == '\r\n') or (value == '\r'):
			value = '\n'
		self._terminator = value
		self._saved_handler = self._jump.get(value[0])
		self._jump[value[0]] = self._handle_terminator
	terminator = property(_get_terminator, _set_terminator)

	def _extract_string(self, multiline):
		"""Extracts a quoted string from the source code.

		Returns the content of a quoted string in the source code. The current
		position (in _index) is assumed to be the opening quote of the string
		(either ' or " although the function doesn't confirm this). Quotation
		characters can be escaped within the string by doubling, for example:

			'Doubled ''quotation'' characters'

		The method returns the unescaped content of the string. Hence, in the
		case above the method would return "Doubled 'quotation' characters"
		(without the double-quotes). The _index variable is incremented to the
		character beyond the closing quote of the string.

		Strings may span multiple lines if multiline is True (which it should
		be for SQL strings, but not quoted identifiers). If a CR, LF or NULL
		character is encountered in the string, an exception is raised (calling
		methods convert this exception into an ERROR token).

		This method should be overridden in descendent classes to handle those
		SQL dialects which permit additonal escaping mechanisms (like C
		backslash escaping).
		"""
		qchar = self._char
		qcount = 1
		self._next()
		self._mark()
		while True:
			if self._char == '\0':
				raise ValueError('Unterminated string starting on line %d' % self._token_line)
			elif self._char == '\n' and not multiline:
				raise ValueError('Illegal line break found in token')
			elif self._char == qchar:
				qcount += 1
			if self._char == qchar and self._peek() != qchar and qcount & 1 == 0:
				break
			self._next()
		content = self._marked_chars.replace(qchar*2, qchar)
		self._next()
		return content

	def _handle_apos(self):
		"""Parses single quote characters (') in the source."""
		try:
			self._add_token(TT.STRING, self._extract_string(self.multiline_str))
		except ValueError, e:
			self._add_token(TT.ERROR, str(e))

	def _handle_asterisk(self):
		"""Parses an asterisk character ("*") in the source."""
		self._next()
		self._add_token(TT.OPERATOR, '*')

	def _handle_bar(self):
		"""Parses a vertical bar character ("|") in the source."""
		self._next()
		if self._char == '|':
			self._next()
			self._add_token(TT.OPERATOR, '||')
		else:
			self._add_token(TT.ERROR, "Expected | but found %s" % self._char)

	def _handle_close_parens(self):
		"""Parses a closing parenthesis character (")") in the source."""
		self._next()
		self._add_token(TT.OPERATOR, ')')

	def _handle_colon(self):
		"""Parses a colon character (":") in the source."""
		# XXX Need to handle a colon followed by white-space as an OPERATOR here (for compound labels)
		self._next()
		if self._char in ['"', "'"]:
			try:
				self._add_token(TT.PARAMETER, self._extract_string(False))
			except ValueError, e:
				self._add_token(TT.ERROR, str(e))
		else:
			self._mark()
			while self._char in self.ident_chars: self._next()
			self._add_token(TT.PARAMETER, self._marked_chars)

	def _handle_comma(self):
		"""Parses a comma character (",") in the source."""
		self._next()
		self._add_token(TT.OPERATOR, ',')

	def _handle_default(self):
		"""Parses unexpected characters, returning an error."""
		self._add_token(TT.ERROR, 'Unexpected character %s' % self._char)
		self._next()

	def _handle_digit(self):
		"""Parses numeric digits (0..9) in the source."""
		self._mark()
		self._next()
		convert = long
		valid = set('0123456789Ee.')
		while self._char in valid:
			if self._char == '.':
				convert = Decimal
				valid -= set('.')
			elif self._char in 'Ee':
				convert = float
				valid -= set('Ee.')
				if self._peek() in '-+':
					self._next()
			self._next()
		try:
			self._add_token(TT.NUMBER, convert(self._marked_chars))
		except ValueError, e:
			self._add_token(TT.ERROR, str(e))

	def _handle_equal(self):
		"""Parses equality characters ("=") in the source."""
		self._next()
		self._add_token(TT.OPERATOR, '=')

	def _handle_greater(self):
		"""Parses greater-than characters (">") in the source."""
		self._next()
		if self._char == '=':
			self._next()
			self._add_token(TT.OPERATOR, '>=')
		else:
			self._add_token(TT.OPERATOR, '>')

	def _handle_ident(self):
		"""Parses unquoted identifier characters (variable) in the source."""
		self._mark()
		self._next()
		while self._char in self.ident_chars: self._next()
		ident = self._marked_chars.upper()
		if self._char == ':':
			self._next()
			self._add_token(TT.LABEL, ident)
		elif ident in self.keywords:
			self._add_token(TT.KEYWORD, ident)
		else:
			self._add_token(TT.IDENTIFIER, ident)

	def _handle_less(self):
		"""Parses less-than characters ("<") in the source."""
		self._next()
		if self._char == '=':
			self._next()
			self._add_token(TT.OPERATOR, '<=')
		elif self._char == '>':
			self._next()
			self._add_token(TT.OPERATOR, '<>')
		else:
			self._add_token(TT.OPERATOR, '<')

	def _handle_minus(self):
		"""Parses minus characters ("-") in the source."""
		self._next()
		if self.sql_comments and (self._char == '-'):
			self._next()
			self._mark()
			while not self._char in '\0\n': self._next()
			content = self._marked_chars
			self._next()
			self._add_token(TT.COMMENT, content)
		else:
			self._add_token(TT.OPERATOR, '-')

	def _handle_open_parens(self):
		"""Parses open parenthesis characters ("(") in the source."""
		self._next()
		self._add_token(TT.OPERATOR, '(')

	def _handle_period(self):
		"""Parses full-stop characters (".") in the source."""
		if self._peek() in '0123456789':
			# Numbers can start with . in SQL
			self._handle_digit()
		else:
			self._next()
			self._add_token(TT.OPERATOR, '.')

	def _handle_plus(self):
		"""Parses plus characters ("+") in the source."""
		self._next()
		self._add_token(TT.OPERATOR, '+')

	def _handle_question(self):
		"""Parses question marks ("?") in the source."""
		self._next()
		self._add_token(TT.PARAMETER, None)

	def _handle_quote(self):
		"""Parses double quote characters (") in the source."""
		try:
			ident = self._extract_string(False)
			if self._char == ':':
				self._next()
				self._add_token(TT.LABEL, ident)
			else:
				self._add_token(TT.IDENTIFIER, ident)
		except ValueError, e:
			self._add_token(ERROR, str(e))

	def _handle_semicolon(self):
		"""Parses semi-colon characters (;) in the source."""
		self._next()
		self._add_token(TT.TERMINATOR, ';')

	def _handle_slash(self):
		"""Parses forward-slash characters ("/") in the source."""
		self._next()
		if self.cpp_comments and (self._char == '/'):
			self._next()
			self._mark()
			while not self._char in '\0\n':
				self._next()
			content = self._marked_chars
			self._add_token(TT.COMMENT, content)
		elif self.c_comments and (self._char == '*'):
			self._next()
			self._mark()
			try:
				nest_count = 0
				while True:
					if self._char == '\0':
						raise ValueError('Unterminated comment starting on line %d' % self._token_line)
					elif (self._char == '/') and (self._peek() == '*') and self.c_comments_nested:
						self._next(2)
						nest_count += 1
					elif (self._char == '*') and (self._peek() == '/'):
						if self.c_comments_nested and nest_count > 0:
							self._next(2)
							nest_count -= 1
						else:
							content = self._marked_chars
							self._next(2)
							self._add_token(TT.COMMENT, content)
							break
					else:
						self._next()
			except ValueError, e:
				self._add_token(TT.ERROR, str(e))
		else:
			self._add_token(TT.OPERATOR, '/')

	def _handle_terminator(self):
		"""Parses statement terminator characters (variable) in the source."""
		if self._source.startswith(self._terminator, self._index):
			self._next(len(self._terminator))
			self._add_token(TT.TERMINATOR, self._terminator)
		elif self._saved_handler is not None:
			self._saved_handler()

	def _handle_space(self):
		"""Parses whitespace characters in the source."""
		while self._char in self.space_chars:
			if self._char == '\n':
				self._next()
				break
			else:
				self._next()
		self._add_token(TT.WHITESPACE, None)


class SQL92Tokenizer(BaseTokenizer):
	"""ANSI SQL-92 tokenizer class."""
	pass


class SQL99Tokenizer(BaseTokenizer):
	"""ANSI SQL-99 tokenizer class."""

	def __init__(self):
		super(SQL99Tokenizer, self).__init__()
		self.keywords = set(sql99_keywords)
		self.ident_chars = set(sql99_identchars)


class SQL2003Tokenizer(BaseTokenizer):
	"""ANSI SQL-2003 tokenizer class."""

	def __init__(self):
		super(SQL2003Tokenizer, self).__init__()
		self.keywords = set(sql2003_keywords)
		self.ident_chars = set(sql2003_identchars)

