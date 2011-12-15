# vim: set noet sw=4 ts=4:

import re
from dbsuite.tokenizer import TokenTypes as TT
from dbsuite.plugins.db2.zos.tokenizer import DB2ZOSTokenizer, db2zos_identchars, db2zos_namechars

# Set of valid characters for unquoted identifiers and names in IBM DB2 UDB
# (see above). Obtained from [1] (see node Reference / SQL / Language Elements)
# [1] http://publib.boulder.ibm.com/infocenter/db2luw/v8/index.jsp

db2luw_identchars = db2zos_identchars
db2luw_namechars = db2zos_namechars

# Set of reserved keywords in IBM DB2 UDB. Obtained from
# <http://publib.boulder.ibm.com/infocenter/db2luw/v8/index.jsp> (see node
# Reference / SQL / Reserved schema names and reserved words)

db2luw_keywords = [
	'ADD', 'AFTER', 'ALIAS', 'ALL', 'ALLOCATE', 'ALLOW', 'ALTER', 'AND', 'ANY',
	'APPLICATION', 'AS', 'ASSOCIATE', 'ASUTIME', 'AUDIT', 'AUTHORIZATION',
	'AUX', 'AUXILIARY', 'BEFORE', 'BEGIN', 'BETWEEN', 'BINARY', 'BUFFERPOOL',
	'BY', 'CACHE', 'CALL', 'CALLED', 'CAPTURE', 'CARDINALITY', 'CASCADED',
	'CASE', 'CAST', 'CCSID', 'CHAR', 'CHARACTER', 'CHECK', 'CLOSE', 'CLUSTER',
	'COLLECTION', 'COLLID', 'COLUMN', 'COMMENT', 'COMMIT', 'CONCAT',
	'CONDITION', 'CONNECT', 'CONNECTION', 'CONSTRAINT', 'CONTAINS', 'CONTINUE',
	'COUNT', 'COUNT_BIG', 'CREATE', 'CROSS', 'CURRENT', 'CURRENT_DATE',
	'CURRENT_LC_CTYPE', 'CURRENT_PATH', 'CURRENT_SERVER', 'CURRENT_TIME',
	'CURRENT_TIMESTAMP', 'CURRENT_TIMEZONE', 'CURRENT_USER', 'CURSOR', 'CYCLE',
	'DATA', 'DATABASE', 'DAY', 'DAYS', 'DB2GENERAL', 'DB2GENRL', 'DB2SQL',
	'DBINFO', 'DECLARE', 'DEFAULT', 'DEFAULTS', 'DEFINITION', 'DELETE',
	'DESCRIPTOR', 'DETERMINISTIC', 'DISALLOW', 'DISCONNECT', 'DISTINCT', 'DO',
	'DOUBLE', 'DROP', 'DSNHATTR', 'DSSIZE', 'DYNAMIC', 'EACH', 'EDITPROC',
	'ELSE', 'ELSEIF', 'ENCODING', 'END', 'END-EXEC', 'END-EXEC1', 'ERASE',
	'ESCAPE', 'EXCEPT', 'EXCEPTION', 'EXCLUDING', 'EXECUTE', 'EXISTS', 'EXIT',
	'EXTERNAL', 'FENCED', 'FETCH', 'FIELDPROC', 'FILE', 'FINAL', 'FOR',
	'FOREIGN', 'FREE', 'FROM', 'FULL', 'FUNCTION', 'GENERAL', 'GENERATED',
	'GET', 'GLOBAL', 'GO', 'GOTO', 'GRANT', 'GRAPHIC', 'GROUP', 'HANDLER',
	'HAVING', 'HOLD', 'HOUR', 'HOURS', 'IDENTITY', 'IF', 'IMMEDIATE', 'IN',
	'INCLUDING', 'INCREMENT', 'INDEX', 'INDICATOR', 'INHERIT', 'INNER',
	'INOUT', 'INSENSITIVE', 'INSERT', 'INTEGRITY', 'INTO', 'IS', 'ISOBID',
	'ISOLATION', 'ITERATE', 'JAR', 'JAVA', 'JOIN', 'KEY', 'LABEL', 'LANGUAGE',
	'LC_CTYPE', 'LEAVE', 'LEFT', 'LIKE', 'LINKTYPE', 'LOCAL', 'LOCALE',
	'LOCATOR', 'LOCATORS', 'LOCK', 'LOCKMAX', 'LOCKSIZE', 'LONG', 'LOOP',
	'MAXVALUE', 'MICROSECOND', 'MICROSECONDS', 'MINUTE', 'MINUTES', 'MINVALUE',
	'MODE', 'MODIFIES', 'MONTH', 'MONTHS', 'NEW', 'NEW_TABLE', 'NO', 'NOCACHE',
	'NOCYCLE', 'NODENAME', 'NODENUMBER', 'NOMAXVALUE', 'NOMINVALUE', 'NOORDER',
	'NOT', 'NULL', 'NULLS', 'NUMPARTS', 'OBID', 'OF', 'OLD', 'OLD_TABLE', 'ON',
	'OPEN', 'OPTIMIZATION', 'OPTIMIZE', 'OPTION', 'OR', 'ORDER', 'OUT',
	'OUTER', 'OVERRIDING', 'PACKAGE', 'PARAMETER', 'PART', 'PARTITION', 'PATH',
	'PIECESIZE', 'PLAN', 'POSITION', 'PRECISION', 'PREPARE', 'PRIMARY',
	'PRIQTY', 'PRIVILEGES', 'PROCEDURE', 'PROGRAM', 'PSID', 'QUERYNO', 'READ',
	'READS', 'RECOVERY', 'REFERENCES', 'REFERENCING', 'RELEASE', 'RENAME',
	'REPEAT', 'RESET', 'RESIGNAL', 'RESTART', 'RESTRICT', 'RESULT',
	'RESULT_SET_LOCATOR', 'RETURN', 'RETURNS', 'REVOKE', 'RIGHT', 'ROLLBACK',
	'ROUTINE', 'ROW', 'ROWS', 'RRN', 'RUN', 'SAVEPOINT', 'SCHEMA',
	'SCRATCHPAD', 'SECOND', 'SECONDS', 'SECQTY', 'SECURITY', 'SELECT',
	'SENSITIVE', 'SET', 'SIGNAL', 'SIMPLE', 'SOME', 'SOURCE', 'SPECIFIC',
	'SQL', 'SQLID', 'STANDARD', 'START', 'STATIC', 'STAY', 'STOGROUP',
	'STORES', 'STYLE', 'SUBPAGES', 'SUBSTRING', 'SYNONYM', 'SYSFUN', 'SYSIBM',
	'SYSPROC', 'SYSTEM', 'TABLE', 'TABLESPACE', 'THEN', 'TO', 'TRANSACTION',
	'TRIGGER', 'TRIM', 'TYPE', 'UNDO', 'UNION', 'UNIQUE', 'UNTIL', 'UPDATE',
	'USAGE', 'USER', 'USING', 'VALIDPROC', 'VALUES', 'VARIABLE', 'VARIANT',
	'VCAT', 'VIEW', 'VOLUMES', 'WHEN', 'WHERE', 'WHILE', 'WITH', 'WLM',
	'WRITE', 'YEAR', 'YEARS',
]

class DB2LUWTokenizer(DB2ZOSTokenizer):
	"""IBM DB2 for Linux/Unix/Windows tokenizer class."""

	# XXX Need to add support for changing statement terminator on the fly
	# with --# SET TERMINATOR c (override _handle_minus() to check if last
	# token is a COMMENT, if so, set terminator property)

	def __init__(self):
		super(DB2LUWTokenizer, self).__init__()
		self.keywords = set(db2luw_keywords)
		self.ident_chars = set(db2luw_identchars)
		# Support for C-style /*..*/ comments add in DB2 v8 FP9
		self.c_comments = True
		# DB2 supports nested /*..*/ comments in accordance with SQL 2003
		# (although almost everyone else seems to have ignored this - probably
		# sensibly)
		self.c_comments_nested = True

	def _handle_ident(self):
		super(DB2LUWTokenizer, self)._handle_ident()
		# Rewrite the special values INFINITY, NAN and SNAN to their decimal
		# counterparts with token type NUMBER
		if self._tokens[-1][:2] == (TT.IDENTIFIER, 'INFINITY'):
			self._tokens[-1] = Token(TT.NUMBER, Decimal('Infinity'), *self._tokens[-1][2:])
		elif self._tokens[-1][:2] == (TT.IDENTIFIER, 'NAN'):
			self._tokens[-1] = Token(TT.NUMBER, Decimal('NaN'), *self._tokens[-1][2:])
		elif self._tokens[-1][:2] == (TT.IDENTIFIER, 'SNAN'):
			self._tokens[-1] = Token(TT.NUMBER, Decimal('sNaN'), *self._tokens[-1][2:])

	def _handle_period(self):
		"""Parses full-stop characters (".") in the source."""
		# Override the base method to handle DB2 LUW's method qualifiers (..)
		if self._peek() == '.':
			self._add_token(TT.OPERATOR, '..')
			self._next(2)
		else:
			super(DB2LUWTokenizer, self)._handle_period()

	def _handle_equal(self):
		"""Parses equality characters ("=") in the source."""
		# Override the base method to handle DB2 LUW's parameter name operator (=>)
		if self._peek() == '>':
			self._add_token(TT.OPERATOR, '=>')
			self._next(2)
		else:
			super(DB2LUWTokenizer, self)._handle_equal()

	def _handle_open_bracket(self):
		self._next()
		self._add_token(TT.OPERATOR, '[')

	def _handle_close_bracket(self):
		self._next()
		self._add_token(TT.OPERATOR, ']')

	def _handle_open_brace(self):
		self._next()
		self._add_token(TT.OPERATOR, '{')

	def _handle_close_brace(self):
		self._next()
		self._add_token(TT.OPERATOR, '}')

	# XXX Support for UESCAPE needed at some point. This probably can't be
	# implemented directly in the tokenizer. Instead, add a separate token type
	# for UTF-8 strings and a "pre-parse" phase to the parser which scans for
	# the new token type and a UESCAPE suffix and decodes the combination into
	# a STRING token
	utf8re = re.compile(r'\\(\\|[0-9A-Fa-f]{4}|\+[0-9A-Fa-f]{6})')
	def _handle_utf8string(self):
		"""Parses a UTF-8 string literal in the source."""
		if self._peek() == '&':
			self._next(2)
			if not self._char == "'":
				self._add_token(TT.ERROR, "Expected ' but found %s" % self._char)
			else:
				def utf8sub(match):
					if match.group(1) == '\\':
						return '\\'
					elif match.group(1).startswith('+'):
						return unichr(int(match.group(1)[1:], 16))
					else:
						return unichr(int(match.group(1), 16))
				try:
					s = self._extract_string(self.multiline_str)
				except ValueError, e:
					self._add_token(TT.ERROR, str(e))
				else:
					self._add_token(TT.STRING, utf8re.sub(utf8sub, s.decode('UTF-8')))
		elif self._peek().upper() == 'X' and self._peek(2) == "'":
			self._handle_unihexstring()
		else:
			self._handle_ident()

	def _init_jump(self):
		super(DB2LUWTokenizer, self)._init_jump()
		self._jump['['] = self._handle_open_bracket
		self._jump[']'] = self._handle_close_bracket
		self._jump['{'] = self._handle_open_brace
		self._jump['}'] = self._handle_close_brace
		self._jump['u'] = self._handle_utf8string
		self._jump['U'] = self._handle_utf8string

