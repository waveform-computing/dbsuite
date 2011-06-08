# vim: set noet sw=4 ts=4:

from dbsuite.tokenizer import BaseTokenizer, TokenTypes as TT

# Set of valid characters for unquoted identifiers and names in IBM DB2 UDB for
# z/OS (see above). Equivalent to IBM DB2 UDB for Linux/Unix/Windows

db2zos_identchars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_$#@0123456789'
db2zos_namechars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ_$#@0123456789'

# Set of reserved keywords in IBM DB2 UDB for z/OS. Obtained from
# <http://publib.boulder.ibm.com/infocenter/dzichelp/v2r2/topic/com.ibm.db2.doc/db2prodhome.htm>
# (see node DB2 UDB for z/OS Version 8 / DB2 reference information / DB2 SQL /
# Additional information for DB2 SQL / Reserved schema names and reserved words /
# Reserved words)

db2zos_keywords = [
	'ADD', 'AFTER', 'ALL', 'ALLOCATE', 'ALLOW', 'ALTER', 'AND', 'ANY', 'AS',
	'ASENSITIVE', 'ASSOCIATE', 'ASUTIME', 'AUDIT', 'AUX', 'AUXILIARY',
	'BEFORE', 'BEGIN', 'BETWEEN', 'BUFFERPOOL', 'BY', 'CALL', 'CAPTURE',
	'CASCADED', 'CASE', 'CAST', 'CCSID', 'CHAR', 'CHARACTER', 'CHECK', 'CLOSE',
	'CLUSTER', 'COLLECTION', 'COLLID', 'COLUMN', 'COMMENT', 'COMMIT', 'CONCAT',
	'CONDITION', 'CONNECT', 'CONNECTION', 'CONSTRAINT', 'CONTAINS', 'CONTINUE',
	'CREATE', 'CURRENT', 'CURRENT_DATE', 'CURRENT_LC_CTYPE', 'CURRENT_PATH',
	'CURRENT_TIME', 'CURRENT_TIMESTAMP', 'CURSOR', 'DATA', 'DATABASE', 'DAY',
	'DAYS', 'DBINFO', 'DECLARE', 'DEFAULT', 'DELETE', 'DESCRIPTOR',
	'DETERMINISTIC', 'DISALLOW', 'DISTINCT', 'DO', 'DOUBLE', 'DROP', 'DSSIZE',
	'DYNAMIC', 'EDITPROC', 'ELSE', 'ELSEIF', 'ENCODING', 'ENCRYPTION', 'END',
	'ENDING', 'END-EXEC', 'ERASE', 'ESCAPE', 'EXCEPT', 'EXCEPTION', 'EXECUTE',
	'EXISTS', 'EXIT', 'EXPLAIN', 'EXTERNAL', 'FENCED', 'FETCH', 'FIELDPROC',
	'FINAL', 'FOR', 'FREE', 'FROM', 'FULL', 'FUNCTION', 'GENERATED', 'GET',
	'GLOBAL', 'GO', 'GOTO', 'GRANT', 'GROUP', 'HANDLER', 'HAVING', 'HOLD',
	'HOUR', 'HOURS', 'IF', 'IMMEDIATE', 'IN', 'INCLUSIVE', 'INDEX', 'INHERIT',
	'INNER', 'INOUT', 'INSENSITIVE', 'INSERT', 'INTO', 'IS', 'ISOBID',
	'ITERATE', 'JAR', 'JOIN', 'KEY', 'LABEL', 'LANGUAGE', 'LC_CTYPE', 'LEAVE',
	'LEFT', 'LIKE', 'LOCAL', 'LOCALE', 'LOCATOR', 'LOCATORS', 'LOCK',
	'LOCKMAX', 'LOCKSIZE', 'LONG', 'LOOP', 'MAINTAINED', 'MATERIALIZED',
	'MICROSECOND', 'MICROSECONDS', 'MINUTE', 'MINUTES', 'MODIFIES', 'MONTH',
	'MONTHS', 'NEXTVAL', 'NO', 'NONE', 'NOT', 'NULL', 'NULLS', 'NUMPARTS',
	'OBID', 'OF', 'ON', 'OPEN', 'OPTIMIZATION', 'OPTIMIZE', 'OR', 'ORDER',
	'OUT', 'OUTER', 'PACKAGE', 'PARAMETER', 'PART', 'PADDED', 'PARTITION',
	'PARTITIONED', 'PARTITIONING', 'PATH', 'PIECESIZE', 'PLAN', 'PRECISION',
	'PREPARE', 'PREVVAL', 'PRIQTY', 'PRIVILEGES', 'PROCEDURE', 'PROGRAM',
	'PSID', 'QUERY', 'QUERYNO', 'READS', 'REFERENCES', 'REFRESH', 'RESIGNAL',
	'RELEASE', 'RENAME', 'REPEAT', 'RESTRICT', 'RESULT', 'RESULT_SET_LOCATOR',
	'RETURN', 'RETURNS', 'REVOKE', 'RIGHT', 'ROLLBACK', 'ROWSET', 'RUN',
	'SAVEPOINT', 'SCHEMA', 'SCRATCHPAD', 'SECOND', 'SECONDS', 'SECQTY',
	'SECURITY', 'SEQUENCE', 'SELECT', 'SENSITIVE', 'SET', 'SIGNAL', 'SIMPLE',
	'SOME', 'SOURCE', 'SPECIFIC', 'STANDARD', 'STATIC', 'STAY', 'STOGROUP',
	'STORES', 'STYLE', 'SUMMARY', 'SYNONYM', 'SYSFUN', 'SYSIBM', 'SYSPROC',
	'SYSTEM', 'TABLE', 'TABLESPACE', 'THEN', 'TO', 'TRIGGER', 'UNDO', 'UNION',
	'UNIQUE', 'UNTIL', 'UPDATE', 'USER', 'USING', 'VALIDPROC', 'VALUE',
	'VALUES', 'VARIABLE', 'VARIANT', 'VCAT', 'VIEW', 'VOLATILE', 'VOLUMES',
	'WHEN', 'WHENEVER', 'WHERE', 'WHILE', 'WITH', 'WLM', 'XMLELEMENT', 'YEAR',
	'YEARS',
]

class DB2ZOSTokenizer(BaseTokenizer):
	"""IBM DB2 for z/OS tokenizer class."""

	def __init__(self):
		super(DB2ZOSTokenizer, self).__init__()
		self.keywords = set(db2zos_keywords)
		self.ident_chars = set(db2zos_identchars)

	def _handle_not(self):
		"""Parses characters meaning "NOT" (! and ^) in the source."""
		self._next()
		try:
			negatedop = {
				'=': '<>',
				'>': '<=',
				'<': '>=',
			}[self._char]
		except KeyError:
			self._add_token(TT.ERROR, "Expected >, <, or =, but found %s" % self._char)
		else:
			self._next()
			self._add_token(TT.OPERATOR, negatedop)

	def _handle_hexstring(self):
		"""Parses a hexstring literal in the source."""
		if self._peek() == "'":
			self._next()
			try:
				s = self._extract_string(False)
				if len(s) % 2 != 0:
					raise ValueError('Hex-string must have an even length')
				s = ''.join(chr(int(s[i:i + 2], 16)) for i in xrange(0, len(s), 2))
			except ValueError, e:
				self._add_token(TT.ERROR, str(e))
			else:
				self._add_token(TT.STRING, s)
		else:
			self._handle_ident()

	def _handle_unihexstring(self):
		"""Parses a unicode hexstring literal in the source."""
		if self._peek().upper() == 'X' and self._peek(2).upper() == "'":
			self._next(2)
			try:
				s = self._extract_string(False)
				if len(s) % 4 != 0:
					raise ValueError('Unicode hex-string must have a length which is a multiple of 4')
				s = ''.join(unichr(int(s[i:i + 4], 16)) for i in xrange(0, len(s), 4))
			except ValueError, e:
				self._add_token(TT.ERROR, str(e))
			else:
				self._add_token(TT.STRING, s)
		else:
			self._handle_ident()

	def _handle_unistring(self):
		"""Parses a graphic literal in the source."""
		if self._peek() == "'":
			self._next()
			try:
				# XXX Needs testing ... what exactly is the Info Center on
				# about with these Graphic String literals (mixing DBCS in an
				# SBCS/MBCS file?!)
				s = unicode(self._extract_string(self.multiline_str))
			except ValueError, e:
				self._add_token(TT.ERROR, str(e))
			else:
				self._add_token(TT.STRING, s)
		elif self._char.upper() == 'G' and self._peek().upper() == 'X' and self._peek(2).upper() == "'":
			self._handle_unihexstring()
		else:
			self._handle_ident()

	def _init_jump(self):
		super(DB2ZOSTokenizer, self)._init_jump()
		self._jump['!'] = self._handle_not
		self._jump['^'] = self._handle_not
		self._jump['x'] = self._handle_hexstring
		self._jump['X'] = self._handle_hexstring
		self._jump['n'] = self._handle_unistring
		self._jump['N'] = self._handle_unistring
		self._jump['g'] = self._handle_unistring
		self._jump['G'] = self._handle_unistring
		self._jump[u'\xac'] = self._handle_not # Hook character (legacy "not" representation)

