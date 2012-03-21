# vim: set noet sw=4 ts=4:

from dbsuite.plugins.db2.zos.tokenizer import db2zos_namechars, db2zos_identchars
from dbsuite.parser import BaseParser, ParseError, ParseBacktrack, quote_str
from dbsuite.tokenizer import TokenTypes as TT, Token
from dbsuite.compat import *

# Standard size suffixes and multipliers
SUFFIX_KMG = {
	'K': 1024**1,
	'M': 1024**2,
	'G': 1024**3,
}

# Default sizes for certain datatypes
CHAR_DEFAULT_SIZE = 1
BLOB_DEFAULT_SIZE = 1024*1024
DECIMAL_DEFAULT_SIZE = 5
DECIMAL_DEFAULT_SCALE = 0
DECFLOAT_DEFAULT_SIZE = 34
TIMESTAMP_DEFAULT_SIZE = 6

class DB2ZOSParser(BaseParser):
	"""Reformatter which breaks up and re-indents DB2 for LUW's SQL dialect.

	This class is, at its core, a full blown SQL language parser that
	understands many common SQL DML and DDL commands (from the basic ones like
	INSERT, UPDATE, DELETE, SELECT, to the more DB2 specific ones such as
	CREATE TABLESPACE, CREATE FUNCTION, and dynamic compound statements).
	"""

	def __init__(self):
		super(DB2ZOSParser, self).__init__()
		self.namechars = db2zos_namechars
		self.identchars = db2zos_identchars
		self.current_schema = None

	def _parse_init(self, tokens):
		super(DB2ZOSParser, self)._parse_init(tokens)
		self.current_schema = None

	def _save_state(self):
		# Override _save_state to save the current schema
		self._states.append((
			self._index,
			self._level,
			len(self._output),
			self.current_schema
		))

	def _restore_state(self):
		# Override _restore_state to restore the current schema
		(
			self._index,
			self._level,
			output_len,
			self.current_schema
		) = self._states.pop()
		del self._output[output_len:]

	def _parse_top(self):
		# Override _parse_top to make a 'statement' the top of the parse tree
		self._parse_statement()

	def _prespace_default(self, template):
		# Overridden to include array and set operators, and the specific
		# intra-statement terminator used by func/proc definitions
		return super(DB2ZOSParser, self)._prespace_default(template) and template not in (
			']', '}', ';',
			(TT.OPERATOR, ']'),
			(TT.OPERATOR, '}'),
			(TT.TERMINATOR, ';'),
		)

	def _postspace_default(self, template):
		# Overridden to include array and set operators
		return super(DB2ZOSParser, self)._postspace_default(template) and template not in (
			'[', '{',
			(TT.OPERATOR, '['),
			(TT.OPERATOR, '{'),
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
		token1 = self._expect(TT.IDENTIFIER)
		result = (None, None, token1.value)
		if self._match('.'):
			self._update_output(Token(TT.RELATION, token1.value, token1.source, token1.line, token1.column), -2)
			token2 = self._expect(TT.IDENTIFIER)
			result = (None, result[2], token2.value)
			if self._match('.'):
				self._update_output(Token(TT.SCHEMA, token1.value, token1.source, token1.line, token1.column), -4)
				self._update_output(Token(TT.RELATION, token2.value, token2.source, token2.line, token2.column), -2)
				token3 = self._expect(TT.IDENTIFIER)
				result = (result[1], result[2], token3.value)
		return result

	_parse_column_name = _parse_subrelation_name
	_parse_constraint_name = _parse_subrelation_name
	# These are cheats; remote object names consist of server.schema.object
	# instead of schema.relation.object, and source object names consist of
	# schema.package.object, but they'll do
	_parse_remote_object_name = _parse_subrelation_name
	_parse_source_object_name = _parse_subrelation_name
	# These are also cheats; routine, type and variables names as of 9.7 are
	# either [schema.]routine (1 or 2-part) or schema.module.routine (3-part)
	_parse_function_name = _parse_subrelation_name
	_parse_procedure_name = _parse_subrelation_name
	_parse_method_name = _parse_subrelation_name
	_parse_type_name = _parse_subrelation_name
	_parse_variable_name = _parse_subrelation_name

	def _parse_subschema_name(self):
		"""Parses the (possibly qualified) name of a schema-owned object.

		A schema-owned object is a table, view, index, function, sequence, etc.
		This method parses such a name with an optional qualifier (the schema
		name). The method returns the parsed name as a tuple with 2 elements
		(None is used for the schema qualifier if it is missing).
		"""
		token1 = self._expect(TT.RELATION)
		result = (None, token1.value)
		if self._match('.'):
			self._update_output(Token(TT.SCHEMA, token1.value, token1.source, token1.line, token1.column), -2)
			token2 = self._expect(TT.RELATION)
			result = (result[1], token2.value)
		return result

	_parse_relation_name = _parse_subschema_name
	_parse_table_name = _parse_subschema_name
	_parse_view_name = _parse_subschema_name
	_parse_alias_name = _parse_subschema_name
	_parse_nickname_name = _parse_subschema_name
	_parse_trigger_name = _parse_subschema_name
	_parse_index_name = _parse_subschema_name
	_parse_routine_name = _parse_subschema_name
	_parse_module_name = _parse_subschema_name
	_parse_sequence_name = _parse_subschema_name
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
		size = self._expect(TT.NUMBER)[1]
		if suffix:
			suf = self._match_one_of(suffix.keys())
			if suf:
				size *= suffix[suf[1]]
		self._expect(')')
		return size

	def _parse_special_register(self):
		"""Parses a special register (e.g. CURRENT_DATE)"""
		if self._match((TT.REGISTER, 'CURRENT')):
			if self._match((TT.REGISTER, 'TIMESTAMP')):
				if self._match('('):
					self._expect_sequence([TT.INTEGER, ')'])
			elif self._match_one_of([
				(TT.REGISTER, 'CLIENT_ACCTNG'),
				(TT.REGISTER, 'CLIENT_APPLNAME'),
				(TT.REGISTER, 'CLIENT_USERID'),
				(TT.REGISTER, 'CLIENT_WRKSTNNAME'),
				(TT.REGISTER, 'DATE'),
				(TT.REGISTER, 'DBPARTITIONNUM'),
				(TT.REGISTER, 'DEGREE'),
				(TT.REGISTER, 'ISOLATION'),
				(TT.REGISTER, 'NODE'),
				(TT.REGISTER, 'PATH'),
				(TT.REGISTER, 'SCHEMA'),
				(TT.REGISTER, 'SERVER'),
				(TT.REGISTER, 'SQLID'),
				(TT.REGISTER, 'TIME'),
				(TT.REGISTER, 'TIMEZONE'),
				(TT.REGISTER, 'USER'),
			]):
				pass
			elif self._match_sequence([
				(TT.REGISTER, 'DECFLOAT'),
				(TT.REGISTER, 'ROUNDING'),
				(TT.REGISTER, 'MODE')
			]):
				pass
			elif self._match_sequence([
				(TT.REGISTER, 'DEFAULT'),
				(TT.REGISTER, 'TRANSFORM'),
				(TT.REGISTER, 'GROUP')
			]):
				pass
			elif self._match((TT.REGISTER, 'EXPLAIN')):
				self._expect_one_of([
					(TT.REGISTER, 'MODE'),
					(TT.REGISTER, 'SNAPSHOT')
				])
			elif self._match_sequence([
				(TT.REGISTER, 'FEDERATED'),
				(TT.REGISTER, 'ASYNCHRONY')
			]):
				pass
			elif self._match_sequence([
				(TT.REGISTER, 'IMPLICIT'),
				(TT.REGISTER, 'XMLPARSE'),
				(TT.REGISTER, 'OPTION')]
			):
				pass
			elif self._match_sequence([
				(TT.REGISTER, 'LOCALE'),
				(TT.REGISTER, 'LC_MESSAGES')
			]):
				pass
			elif self._match_sequence([
				(TT.REGISTER, 'LOCALE'),
				(TT.REGISTER, 'LC_TIME')
			]):
				pass
			elif self._match_sequence([
				(TT.REGISTER, 'LOCK'),
				(TT.REGISTER, 'TIMEOUT')
			]):
				pass
			elif self._match_sequence([
				(TT.REGISTER, 'MAINTAINED'),
				(TT.REGISTER, 'TABLE'),
				(TT.REGISTER, 'TYPES'),
				(TT.REGISTER, 'FOR'),
				(TT.REGISTER, 'OPTIMIZATION')
			]):
				pass
			elif self._match_sequence([
				(TT.REGISTER, 'MDC'),
				(TT.REGISTER, 'ROLLOUT'),
				(TT.REGISTER, 'MODE')
			]):
				pass
			elif self._match_sequence([
				(TT.REGISTER, 'OPTIMIZATION'),
				(TT.REGISTER, 'PROFILE')
			]):
				pass
			elif self._match_sequence([
				(TT.REGISTER, 'PACKAGE'),
				(TT.REGISTER, 'PATH')
			]):
				pass
			elif self._match_sequence([
				(TT.REGISTER, 'QUERY'),
				(TT.REGISTER, 'OPTIMIZATION')
			]):
				pass
			elif self._match_sequence([
				(TT.REGISTER, 'REFRESH'),
				(TT.REGISTER, 'AGE')
			]):
				pass
			else:
				self._expected((TT.REGISTER,))
		elif self._match((TT.REGISTER, 'CLIENT')):
			self._expect_one_of([
				(TT.REGISTER, 'ACCTNG'),
				(TT.REGISTER, 'APPLNAME'),
				(TT.REGISTER, 'USERID'),
				(TT.REGISTER, 'WRKSTNNAME'),
			])
		elif self._match((TT.REGISTER, 'CURRENT_TIMESTAMP')):
			if self._match('('):
				self._expect_sequence([TT.INTEGER, ')'])
		else:
			self._expect_one_of([
				(TT.REGISTER, 'CURRENT_DATE'),
				(TT.REGISTER, 'CURRENT_PATH'),
				(TT.REGISTER, 'CURRENT_SCHEMA'),
				(TT.REGISTER, 'CURRENT_SERVER'),
				(TT.REGISTER, 'CURRENT_TIME'),
				(TT.REGISTER, 'CURRENT_TIMEZONE'),
				(TT.REGISTER, 'CURRENT_USER'),
				(TT.REGISTER, 'SESSION_USER'),
				(TT.REGISTER, 'SYSTEM_USER'),
				(TT.REGISTER, 'USER'),
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
			if self._match((TT.DATATYPE, 'SYSIBM')):
				self._expect('.')
			if self._match((TT.DATATYPE, 'SMALLINT')):
				typename = 'SMALLINT'
			elif self._match_one_of([(TT.DATATYPE, 'INT'), (TT.DATATYPE, 'INTEGER')]):
				typename = 'INTEGER'
			elif self._match((TT.DATATYPE, 'BIGINT')):
				typename = 'BIGINT'
			elif self._match((TT.DATATYPE, 'FLOAT')):
				size = self._parse_size(optional=True)
				if size is None or size > 24:
					typename = 'DOUBLE'
				else:
					typename = 'REAL'
			elif self._match((TT.DATATYPE, 'REAL')):
				typename = 'REAL'
			elif self._match((TT.DATATYPE, 'DOUBLE')):
				self._match((TT.DATATYPE, 'PRECISION'))
				typename = 'DOUBLE'
			elif self._match((TT.DATATYPE, 'DECFLOAT')):
				typename = 'DECFLOAT'
				self._parse_size(optional=True) or DECFLOAT_DEFAULT_SIZE
			elif self._match_one_of([(TT.DATATYPE, 'DEC'), (TT.DATATYPE, 'DECIMAL')]):
				typename = 'DECIMAL'
				size = DECIMAL_DEFAULT_SIZE
				scale = DECIMAL_DEFAULT_SCALE
				if self._match('(', prespace=False):
					size = self._expect(TT.NUMBER).value
					if self._match(','):
						scale = self._expect(TT.NUMBER).value
					self._expect(')')
			elif self._match_one_of([(TT.DATATYPE, 'NUM'), (TT.DATATYPE, 'NUMERIC')]):
				typename = 'NUMERIC'
				size = DECIMAL_DEFAULT_SIZE
				scale = DECIMAL_DEFAULT_SCALE
				if self._match('(', prespace=False):
					size = self._expect(TT.NUMBER).value
					if self._match(','):
						scale = self._expect(TT.NUMBER).value
					self._expect(')')
			elif self._match_one_of([(TT.DATATYPE, 'CHAR'), (TT.DATATYPE, 'CHARACTER')]):
				if self._match((TT.DATATYPE, 'VARYING')):
					typename = 'VARCHAR'
					size = self._parse_size(optional=False, suffix=SUFFIX_KMG)
					self._match_sequence(['FOR', 'BIT', 'DATA'])
				elif self._match_sequence([(TT.DATATYPE, 'LARGE'), (TT.DATATYPE, 'OBJECT')]):
					typename = 'CLOB'
					size = self._parse_size(optional=True, suffix=SUFFIX_KMG) or BLOB_DEFAULT_SIZE
				else:
					typename = 'CHAR'
					size = self._parse_size(optional=True, suffix=SUFFIX_KMG) or CHAR_DEFAULT_SIZE
					self._match_sequence(['FOR', 'BIT', 'DATA'])
			elif self._match((TT.DATATYPE, 'VARCHAR')):
				typename = 'VARCHAR'
				size = self._parse_size(optional=False, suffix=SUFFIX_KMG)
				self._match_sequence(['FOR', 'BIT', 'DATA'])
			elif self._match((TT.DATATYPE, 'VARGRAPHIC')):
				typename = 'VARGRAPHIC'
				size = self._parse_size(optional=False)
			elif self._match_sequence([(TT.DATATYPE, 'LONG'), (TT.DATATYPE, 'VARCHAR')]):
				typename = 'LONG VARCHAR'
			elif self._match_sequence([(TT.DATATYPE, 'LONG'), (TT.DATATYPE, 'VARGRAPHIC')]):
				typename = 'LONG VARGRAPHIC'
			elif self._match((TT.DATATYPE, 'CLOB')):
				typename = 'CLOB'
				size = self._parse_size(optional=True, suffix=SUFFIX_KMG) or BLOB_DEFAULT_SIZE
			elif self._match((TT.DATATYPE, 'BLOB')):
				typename = 'BLOB'
				size = self._parse_size(optional=True, suffix=SUFFIX_KMG) or BLOB_DEFAULT_SIZE
			elif self._match_sequence([(TT.DATATYPE, 'BINARY'), (TT.DATATYPE, 'LARGE'), (TT.DATATYPE, 'OBJECT')]):
				typename = 'BLOB'
				size = self._parse_size(optional=True, suffix=SUFFIX_KMG) or BLOB_DEFAULT_SIZE
			elif self._match((TT.DATATYPE, 'DBCLOB')):
				typename = 'DBCLOB'
				size = self._parse_size(optional=True, suffix=SUFFIX_KMG) or BLOB_DEFAULT_SIZE
			elif self._match((TT.DATATYPE, 'GRAPHIC')):
				typename = 'GRAPHIC'
				size = self._parse_size(optional=True) or CHAR_DEFAULT_SIZE
			elif self._match((TT.DATATYPE, 'NCHAR')):
				typename = 'NCHAR'
				if self._match((TT.DATATYPE, 'VARYING')):
					typename = 'NVARCHAR'
					size = self._parse_size(optional=False)
				else:
					typename = 'NCHAR'
					size = self._parse_size(optional=True) or CHAR_DEFAULT_SIZE
			elif self._match((TT.DATATYPE, 'NATIONAL')):
				self._expect_one_of([(TT.DATATYPE, 'CHAR'), (TT.DATATYPE, 'CHARACTER')])
				if self._match((TT.DATATYPE, 'VARYING')):
					typename = 'NVARCHAR'
					size = self._parse_size(optional=False)
				else:
					typename = 'NCHAR'
					size = self._parse_size(optional=True) or CHAR_DEFAULT_SIZE
			elif self._match((TT.DATATYPE, 'DATE')):
				typename = 'DATE'
			elif self._match((TT.DATATYPE, 'TIME')):
				typename = 'TIME'
			elif self._match((TT.DATATYPE, 'TIMESTAMP')):
				typename = 'TIMESTAMP'
				size = self._parse_size(optional=True) or TIMESTAMP_DEFAULT_SIZE
			elif self._match((TT.DATATYPE, 'DATALINK')):
				typename = 'DATALINK'
				size = self._parse_size(optional=True)
			elif self._match((TT.DATATYPE, 'XML')):
				typename = 'XML'
			elif self._match((TT.DATATYPE, 'DB2SECURITYLABEL')):
				typeschema = 'SYSPROC'
				typename = 'DB2SECURITYLABEL'
			elif self._match((TT.DATATYPE, 'BOOLEAN')):
				typename = 'BOOLEAN'
			elif self._match((TT.DATATYPE, 'CURSOR')):
				typename = 'CURSOR'
			elif self._match((TT.DATATYPE, 'ARRAY')):
				typename = 'ARRAY'
				size = self._parse_size(optional=False, suffix=SUFFIX_KMG)
			else:
				raise ParseBacktrack()
		except ParseError:
			# If that fails, rewind and parse a user-defined type (user defined
			# types do not have a size or scale)
			self._restore_state()
			typeschema = None
			typename = self._expect(TT.DATATYPE).value
			if self._match('.'):
				typeschema = typename
				typename = self._expect(TT.DATATYPE).value
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
			ident = self._expect(TT.IDENTIFIER).value
			# Parse an optional array element suffix
			if self._match('[', prespace=False):
				self._parse_expression()
				self._expect(']')
			result.append(ident)
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
			self._expect(TT.IDENTIFIER)
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
		if self._peek_one_of(['SELECT', 'VALUES']):
			# Parse a full-select
			self._indent()
			self._parse_full_select()
			self._outdent()
		else:
			# Everything else (including a redundantly parenthesized
			# full-select) can be parsed as an expression list
			self._parse_expression_list(allowdefault)

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
					self._expect(TT.NUMBER)
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
				self._expect(TT.STRING)
				if self._match('PASSING'):
					self._match_sequence(['BY', 'REF'])
					while True:
						self._parse_expression()
						self._expect_sequence(['AS', TT.IDENTIFIER])
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
			elif self._match_sequence(['NEXT', 'VALUE', 'FOR']) or self._match_sequence(['NEXTVAL', 'FOR']):
				self._parse_sequence_name()
			elif self._match_sequence(['PREVIOUS', 'VALUE', 'FOR']) or self._match_sequence(['PREVVAL', 'FOR']):
				self._parse_sequence_name()
			elif self._match_sequence(['ROW', 'CHANGE']):
				self._expect_one_of(['TOKEN', 'TIMESTAMP'])
				self._expect('FOR')
				self._parse_table_name()
			elif self._match_one_of([TT.NUMBER, TT.STRING, TT.PARAMETER, 'NULL']): # Literals
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
			'ARRAY_AGG',
			'COUNT',
			'COUNT_BIG',
			'AVG',
			'MAX',
			'MIN',
			'STDDEV',
			'SUM',
			'VARIANCE',
			'VAR',
		]).value
		self._expect('(', prespace=False)
		if aggfunc in ('COUNT', 'COUNT_BIG') and self._match('*'):
			# COUNT and COUNT_BIG can take '*' as a sole parameter
			pass
		elif aggfunc == 'ARRAY_AGG':
			self._parse_expression()
			if self._match_sequence(['ORDER', 'BY']):
				while True:
					self._parse_expression()
					self._match_one_of(['ASC', 'DESC'])
					if not self._match(','):
						break
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
		]).value
		self._expect('(', prespace=False)
		if olapfunc in ('LAG', 'LEAD'):
			self._parse_expression()
			if self._match(','):
				self._expect(TT.NUMBER)
				if sel._match(','):
					self._parse_expression()
					if self._match(','):
						self._expect_one_of([(TT.STRING, 'RESPECT NULLS'), (TT.STRING, 'IGNORE NULLS')])
		elif olapfunc in ('FIRST_VALUE', 'LAST_VALUE'):
			self._parse_expression()
			if self._match(','):
				self._expect_one_of([(TT.STRING, 'RESPECT NULLS'), (TT.STRING, 'IGNORE NULLS')])
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
		]).value
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
					self._expect(TT.IDENTIFIER)
				if not self._match(','):
					break
		elif xmlfunc == 'XMLELEMENT':
			self._expect('NAME')
			self._expect(TT.IDENTIFIER)
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
				self._match_sequence(['AS', TT.IDENTIFIER])
				if not self._match(','):
					break
				if self._match('OPTION'):
					self._parse_xml_value_option()
		elif xmlfunc == 'XMLGROUP':
			while True:
				self._parse_expression()
				if self._match('AS'):
					self._expect(TT.IDENTIFIER)
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
					self._expect(TT.STRING)
				elif self._match('NO'):
					self._expect_sequence(['DEFAULT', TT.STRING])
				else:
					self._expect_sequence([TT.STRING, 'AS', TT.IDENTIFIER])
				if not self._match(','):
					break
		elif xmlfunc == 'XMLPARSE':
			self._expect_sequence(['DOCUMENT', TT.STRING])
			if self._match_one_of(['STRIP', 'PRESERVE']):
				self._expect('WHITESPACE')
		elif xmlfunc == 'XMLPI':
			self._expect_sequence(['NAME', TT.IDENTIFIER])
			if self._match(','):
				self._expect(TT.STRING)
		elif xmlfunc == 'XMLQUERY':
			self._expect(TT.STRING)
			if self._match('PASSING'):
				self._match_sequence(['BY', 'REF'])
				while True:
					self._parse_expression()
					self._expect_sequence(['AS', TT.IDENTIFIER])
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
				self._match_sequence(['AS', TT.IDENTIFIER])
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
					t = t.value
					valid.remove(t)
				else:
					break
				if t == 'VERSION':
					self._expect(TT.STRING)
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
					self._expect(TT.STRING)
				elif self._match('NO'):
					self._expect('NAMESPACE')
				self._match_sequence(['ELEMENT', TT.IDENTIFIER])
		elif xmlfunc == 'XMLTABLE':
			self._parse_expression()
			if self._match(','):
				self._expect(TT.STRING)
			if self._match('PASSING'):
				self._match_sequence(['BY', 'REF'])
				while True:
					self._parse_expression()
					self._expect_sequence(['AS', TT.IDENTIFIER])
					self._match_sequence(['BY', 'REF'])
					if not self._match(','):
						break
			if self._match('COLUMNS'):
				while True:
					self._expect(TT.IDENTIFIER)
					if not self._match_sequence(['FOR', 'ORDINALITY']):
						self._parse_datatype()
						self._match_sequence(['BY', 'REF'])
						if self._match('DEFAULT'):
							self._parse_expression()
						if self._match('PATH'):
							self._expect(TT.STRING)
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
				self._expect(TT.STRING)
			elif self._match('NO'):
				self._expect('NAMESPACE')
			else:
				self._expected_one_of(['ID', 'URI', 'NO'])
			self._match_sequence(['LOCATION', TT.STRING])

	def _parse_xml_row_option(self, allowroot=False):
		"""Parses an XML OPTION suffix for rows in certain XML function calls"""
		# OPTION already matched
		valid = set(['ROW', 'AS'])
		if allowroot:
			valid.add('ROOT')
		while valid:
			t = self._expect_one_of(valid)
			if t:
				t = t.value
				valid.remove(t)
			else:
				break
			if t in ('ROW', 'ROOT'):
				self._expect(TT.IDENTIFIER)
			elif t == 'AS':
				self._expect('ATTRIBUTES')

	def _parse_xml_value_option(self):
		"""Parses an XML OPTION suffix for scalar values in certain XML function calls"""
		# OPTION already matched
		valid = set(['EMPTY', 'NULL', 'XMLBINARY'])
		while valid:
			t = self._expect_one_of(valid)
			if t:
				t = t.value
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
		]).value
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
				self._match(TT.STRING)
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
		elif self._match_one_of(['UNBOUNDED', TT.NUMBER]):
			self._expect_one_of(['PRECEDING', 'FOLLOWING'])
		elif not optional:
			self._expected_one_of(['CURRENT', 'UNBOUNDED', TT.NUMBER])
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
		if not self._match_sequence([TT.IDENTIFIER, '.', '*']):
			self._parse_expression()
			# Parse optional column alias
			if self._match('AS'):
				self._expect(TT.IDENTIFIER)
			# Ambiguity: FROM and INTO can legitimately appear in this
			# position as a KEYWORD (which the IDENTIFIER match below would
			# accept)
			elif not self._peek_one_of(['FROM', 'INTO']):
				self._match(TT.IDENTIFIER)

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
		if self._match_sequence(['GROUP', 'BY']):
			self._indent()
			self._parse_group_by()
			self._outdent()
		if self._match('HAVING'):
			self._indent()
			self._parse_search_condition()
			self._outdent()
		if self._match_sequence(['ORDER', 'BY']):
			self._indent()
			while True:
				self._parse_expression()
				self._match_one_of(['ASC', 'DESC'])
				if not self._match(','):
					break
				else:
					self._newline()
			self._outdent()
		if self._match_sequence(['FETCH', 'FIRST']):
			self._match(TT.NUMBER) # Row count is optional (defaults to 1)
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
				self._expect(TT.IDENTIFIER)
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
					'INNER',
					'JOIN',
					'NATURAL',
					'INTERSECT',
					'ON',
					'ORDER',
					'SET',
					'TABLESAMPLE',
					'UNION',
					'USING',
					'WHERE',
					'WITH',
				]):
				self._expect(TT.IDENTIFIER)
			# Parse optional column aliases
			if self._match('('):
				self._parse_ident_list()
				self._expect(')')

	def _parse_values_expression(self, allowdefault=False, allowinto=False):
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
		if allowinto and self._match('INTO'):
			self._indent()
			self._parse_ident_list(newlines=True)
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

	def _parse_lateral_options(self):
		"""Parses the RETURN DATA UNTIL options of a LATERAL/TABLE reference"""
		if self._match_sequence(['RETURN', 'DATA', 'UNTIL']):
			while True:
				self._expect_sequence(['FEDERATED', 'SQLSTATE'])
				self._match('VALUE')
				self._expect(TT.STRING)
				if self._match('SQLCODE'):
					while True:
						self._expect(TT.NUMBER)
						if not self._match(','):
							break
				if not self._match(','):
					break
			return True
		else:
			return False

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
					self._parse_table_correlation(optional=True)
				except ParseError:
					# If it fails, rewind and try a join expression instead
					self._restore_state()
					if reraise: raise
					self._parse_join_expression()
					self._expect(')')
				else:
					self._forget_state()
			elif self._match('LATERAL'):
				self._parse_lateral_options()
				self._expect('(', prespace=False)
				self._indent()
				self._parse_full_select()
				self._outdent()
				self._expect(')')
				self._parse_table_correlation(optional=True)
			elif self._match('TABLE'):
				lateral = self._parse_lateral_options()
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
					if lateral: raise
					self._parse_function_call()
				else:
					self._forget_state()
				reraise = True
				self._expect(')')
				self._parse_table_correlation(optional=True)
			elif self._match_one_of(['FINAL', 'NEW']):
				self._expect('TABLE')
				self._expect('(', prespace=False)
				self._indent()
				if self._expect_one_of(['INSERT', 'UPDATE']).value == 'INSERT':
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
				if self._expect_one_of(['UPDATE', 'DELETE']).value == 'DELETE':
					self._parse_delete_statement()
				else:
					self._parse_update_statement()
				reraise = True
				self._outdent()
				self._expect(')')
				self._parse_table_correlation(optional=True)
			elif self._match('UNNEST'):
				self._expect('(', prespace=False)
				self._indent()
				while True:
					if self._match('CAST'):
						self._parse_cast_expression()
					else:
						self._expect(TT.IDENTIFIER)
					if not self._match(','):
						break
				self._outdent()
				self._expect(')')
				self._parse_table_correlation(optional=False)
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
			if self._match('TABLESAMPLE'):
				self._expect_one_of(['BERNOULLI', 'SYSTEM'])
				self._expect('(')
				self._parse_expression()
				self._expect(')')
				if self._match('REPEATABLE'):
					self._expect('(')
					self._parse_expression()
					self._expect(')')
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
			self._match(TT.NUMBER) # Row count is optional (defaults to 1)
			self._expect_one_of(['ROW', 'ROWS'])
			self._expect('ONLY')

	def _parse_relation(self, allowdefault=False, allowinto=False):
		"""Parses relation generators (high precedence) in a full-select expression"""
		# XXX Add support for the TABLE statement from the SQL standard
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
			self._parse_values_expression(allowdefault, allowinto)
		else:
			self._expected_one_of(['SELECT', 'VALUES', '('])

	def _parse_query(self, allowdefault=False, allowinto=False):
		"""Parses a full-select with optional common-table-expression"""
		# Parse the optional common-table-expression
		if self._match('WITH'):
			while True:
				self._expect(TT.IDENTIFIER)
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
				if self._match('.'):
					self._expect(TT.IDENTIFIER)
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
						self._expect(TT.NUMBER)
						continue
				elif self._match('SET'):
					t = self._expect_one_of(valid).value
					if t != 'NO': valid.remove(t)
					if t in validno: validno.remove(t)
				else:
					break
			else:
				t = self._match_one_of(valid)
				if t:
					t = t.value
					if t != 'NO': valid.remove(t)
					if t in validno: validno.remove(t)
				else:
					break
			if t == 'START':
				self._expect_sequence(['WITH', TT.NUMBER])
			elif t == 'RESTART':
				if self._match('WITH'):
					self._expect(TT.NUMBER)
			elif t == 'INCREMENT':
				self._expect_sequence(['BY', TT.NUMBER])
			elif t in ('MINVALUE', 'MAXVALUE', 'CACHE'):
				self._expect(TT.NUMBER)
			elif t in ('CYCLE', 'ORDER'):
				pass
			elif t == 'NO':
				t = self._expect_one_of(validno).value
				validno.remove(t)
				valid.remove(t)

	def _parse_column_definition(self, aligntypes=False, alignoptions=False, federated=False):
		"""Parses a column definition in a CREATE TABLE statement"""
		# Parse a column definition
		self._expect(TT.IDENTIFIER)
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
				if self._expect_one_of(['ALWAYS', 'BY']).value == 'BY':
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
				self._expect_sequence(['LENGTH', TT.NUMBER])
			elif self._match('COMPRESS'):
				self._expect_sequence(['SYSTEM', 'DEFAULT'])
			elif self._match('COLUMN'):
				self._expect_sequence(['SECURED', 'WITH', TT.IDENTIFIER])
			elif self._match('SECURED'):
				self._expect_sequence(['WITH', TT.IDENTIFIER])
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
			self._expect(TT.IDENTIFIER)
		# Parse the constraint definition
		if self._match('PRIMARY'):
			self._expect('KEY')
		elif self._match('UNIQUE'):
			pass
		elif self._match('REFERENCES'):
			self._parse_table_name()
			if self._match('(', prespace=False):
				self._expect(TT.IDENTIFIER)
				self._expect(')')
			t = ['DELETE', 'UPDATE']
			for i in xrange(2):
				if self._match('ON'):
					t.remove(self._expect_one_of(t).value)
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
					self._expect(TT.IDENTIFIER)
				self._expect_sequence(['DETERMINED', 'BY'])
				if self._match('('):
					self._parse_ident_list()
					self._expect(')')
				else:
					self._expect(TT.IDENTIFIER)
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
			self._expect(TT.IDENTIFIER)
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
					t.remove(self._expect_one_of(t).value)
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
					self._expect(TT.IDENTIFIER)
				self._expect_sequence(['DETERMINED', 'BY'])
				if self._match('('):
					self._parse_ident_list()
					self._expect(')')
				else:
					self._expect(TT.IDENTIFIER)
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
		self._expect(TT.IDENTIFIER)
		if self._match_one_of(['ENABLE', 'DISABLE']):
			self._expect_sequence(['QUERY', 'OPTIMIZATION'])
		else:
			self._match('NOT')
			self._expect('ENFORCED')

	def _parse_column_alteration(self):
		"""Parses a column-alteration in an ALTER TABLE statement"""
		self._expect(TT.IDENTIFIER)
		if self._match('DROP'):
			if self._match('NOT'):
				self._expect('NULL')
			elif self._match('COLUMN'):
				self._expect('SECURITY')
			else:
				self._expect_one_of([
					'NOT',
					'COLUMN',
					'IDENTITY',
					'DEFAULT',
					'EXPRESSION'
				])
		elif self._match('COMPRESS'):
			if self._match('SYSTEM'):
				self._expect('DEFAULT')
			else:
				self._expect('OFF')
		elif self._match('SECURED'):
			self._expect_sequence(['WITH', TT.IDENTIFIER])
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
					self._expect_sequence(['LENGTH', TT.NUMBER])
				elif self._match('GENERATED'):
					if self._match(['BY', 'ALWAYS']).value == 'BY':
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
				elif self._match('NOT'):
					self._expect('NULL')
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
		self._expect(TT.IDENTIFIER)
		while True:
			if self._match('LOCAL'):
				if self._match('NAME'):
					self._expect(TT.IDENTIFIER)
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
				self._expect(TT.IDENTIFIER)
			if not self._match(','):
				break

	def _parse_grant_revoke(self, grant):
		"""Parses the body of a GRANT or REVOKE statement"""
		# [GRANT|REVOKE] already matched
		# Parse any preamble
		seclabel = False
		if self._match('ROLE'):
			pass
		elif self._match_sequence(['SECURITY', 'LABEL']):
			seclabel = grant
		# Parse the privilege list
		while True:
			priv = self._expect(TT.IDENTIFIER)
			if priv.value in ('REFERENCES', 'UPDATE'):
				if self._match('('):
					self._parse_ident_list()
					self._expect(')')
			elif priv.value == 'DBADM':
				while self._match_one_of(['WITH', 'WITHOUT']):
					self._expect_one_of(['DATAACCESS', 'ACCESSCTRL'])
			elif priv.value == 'DB2LBACWRITEARRAY':
				self._expect_one_of(['WRITEDOWN', 'WRITEUP'])
			elif priv.value == 'ALL':
				self._match('PRIVILEGES')
				break
			if not self._match(','):
				break
		# Parse the target list
		if self._match('OF'):
			self._expect_sequence(['TABLESPACE', TT.IDENTIFIER])
		elif self._match('ON'):
			while True:
				if self._match('DATABASE'):
					break
				elif self._match('RULE'):
					if self._expect_one_of([
						'DB2LBACREADARRAY',
						'DB2LBACREADSET',
						'DB2LBACREADTREE',
						'DB2LBACWRITEARRAY',
						'DB2LBACWRITESET',
						'DB2LBACWRITETREE',
						'ALL'
					]).value == 'DB2LBACWRITEARRAY':
						self._expect_one_of(['WRITEDOWN', 'WRITEUP'])
					self._expect_sequence(['FOR', TT.IDENTIFIER])
					break
				elif self._match('VARIABLE'):
					self._parse_variable_name()
					break
				elif self._match('INDEX'):
					self._parse_index_name()
					break
				elif self._match('MODULE'):
					self._parse_module_name()
					break
				elif self._match_one_of(['PROGRAM', 'PACKAGE']):
					self._parse_subschema_name()
					break
				elif self._match_one_of(['FUNCTION', 'PROCEDURE']):
					# Ambiguity: Can use schema.* or schema.name(prototype) here
					if not self._match('*') and not self._match_sequence([TT.IDENTIFIER, '.', '*']):
						self._parse_routine_name()
						if self._match('(', prespace=False):
							self._parse_datatype_list()
							self._expect(')')
					break
				elif self._match('SPECIFIC'):
					self._expect_one_of(['FUNCTION', 'PROCEDURE'])
					self._parse_routine_name()
					break
				elif self._match('SCHEMA'):
					self._expect(TT.IDENTIFIER)
					break
				elif self._match('SEQUENCE'):
					self._parse_sequence_name()
					break
				elif self._match('SERVER'):
					self._expect(TT.IDENTIFIER)
					break
				elif self._match('USER'):
					self._expect(TT.IDENTIFIER)
				elif self._match('PUBLIC'):
					pass
				elif self._match('TABLE'):
					self._parse_table_name()
					break
				elif self._match('WORKLOAD'):
					self._expect(TT.IDENTIFIER)
					break
				elif self._match('XSROBJECT'):
					self._parse_subschema_name()
					break
				else:
					self._parse_table_name()
					break
				if not self._match(','):
					break
		# Parse the grantee(s)
		# XXX The following is a bit lax, but again, adhering strictly to the
		# syntax results in a ridiculously complex syntax
		self._expect(['FROM', 'TO'][grant])
		self._parse_auth_list()
		if seclabel:
			if self._match('FOR'):
				self._expect_one_of(['ALL', 'READ', 'WRITE'])
				self._expect('ACCESS')
		elif grant:
			if self._match('WITH'):
				self._expect_one_of(['GRANT', 'ADMIN'])
				self._expect('OPTION')
		else:
			self._match_sequence(['BY', 'ALL'])
			self._match('RESTRICT')

	def _parse_tablespace_size_attributes(self):
		"""Parses DMS size attributes in a CREATE TABLESPACE statement"""
		if self._match('AUTORESIZE'):
			self._expect_one_of(['NO', 'YES'])
		if self._match('INTIALSIZE'):
			self._expect(TT.NUMBER)
			self._expect_one_of(['K', 'M', 'G'])
		if self._match('INCREASESIZE'):
			self._expect(TT.NUMBER)
			self._expect_one_of(['K', 'M', 'G', 'PERCENT'])
		if self._match('MAXSIZE'):
			if not self._match('NONE'):
				self._expect(TT.NUMBER)
				self._expect_one_of(['K', 'M', 'G'])

	def _parse_database_container_clause(self, size=True):
		"""Parses a container clause for a DMS tablespace"""
		self._expect('(')
		while True:
			self._expect_one_of(['FILE', 'DEVICE'])
			self._expect(TT.STRING)
			if size:
				self._expect(TT.NUMBER)
				self._match_one_of(['K', 'M', 'G'])
			if not self._match(','):
				break
		self._expect(')')

	def _parse_system_container_clause(self):
		"""Parses a container clause for an SMS tablespace"""
		self._expect('(')
		while True:
			self._expect(TT.STRING)
			if not self._match(','):
				break
		self._expect(')')

	def _parse_db_partition_clause(self):
		"""Parses a DBPARTITIONNUM clause in various statements"""
		if not self._match('GLOBAL'):
			if self._match('AT'):
				self._expect_one_of(['DBPARTITIONNUM', 'NODE'])
				self._expect(TT.NUMBER)

	def _parse_db_partition_list_clause(self, size=False):
		"""Parses an DBPARTITIONNUM clause in various statements"""
		self._expect_one_of([
			'DBPARTITIONNUM',
			'DBPARTITIONNUMS',
			'NODE', # compatibility option
			'NODES', # compatibility option
		])
		self._expect('(')
		while True:
			self._expect(TT.NUMBER)
			self._match_sequence(['TO', TT.NUMBER])
			if size:
				self._expect_sequence(['SIZE', TT.NUMBER])
			if not self._match(','):
				break
		self._expect(')')

	def _parse_db_partitions_clause(self):
		"""Parses a DBPARTITIONNUM list clause in various statements"""
		if self._match('ON'):
			if self._match('ALL'):
				self._expect_one_of(['DBPARTITIONNUMS', 'NODES'])
				if self._match('EXCEPT'):
					self._parse_db_partition_list_clause(size=False)
			else:
				self._parse_db_partition_list_clause(size=False)

	def _parse_function_predicates_clause(self):
		"""Parses the PREDICATES clause in a CREATE FUNCTION statement"""
		# PREDICATES already matched
		# The surrounding parentheses seem to be optional (although the syntax
		# diagram in the DB2 Info Center implies otherwise)
		parens = self._match('(')
		self._expect('WHEN')
		self._match_one_of(['=', '<>', '<', '>', '<=', '>='])
		if self._match('EXPRESSION'):
			self._expect_sequence(['AS', TT.IDENTIFIER])
		else:
			self._parse_expression()
		valid = ['SEARCH', 'FILTER']
		while valid:
			t = self._match_one_of(valid)
			if t:
				t = t.value
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
					self._expect_sequence(['KEY', '(', TT.IDENTIFIER, ')', 'USE', TT.IDENTIFIER, '('])
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
				self._expect(TT.IDENTIFIER)
			else:
				if alter:
					self._match_one_of('ADD', 'SET')
				else:
					self._match('ADD')
				self._expect(TT.IDENTIFIER)
				self._expect(TT.STRING)
			if not self._match(','):
				break
		self._expect(')')

	def _parse_remote_server(self):
		"""Parses a remote server specification"""
		# SERVER already matched
		if self._match('TYPE'):
			self._expect(TT.IDENTIFIER)
			if self._match('VERSION'):
				self._parse_server_version()
				if self._match('WRAPPER'):
					self._expect(TT.IDENTIFIER)
		else:
			self._expect(TT.IDENTIFIER)
			if self._match('VERSION'):
				self._parse_server_version()

	def _parse_server_version(self):
		"""Parses a federated server version"""
		# VERSION already matched
		if self._match(TT.NUMBER):
			if self._match('.'):
				self._expect(TT.NUMBER)
				if self._match('.'):
					self._expect(TT.NUMBER)
		elif self._match(TT.STRING):
			pass
		else:
			self._expected_one_of([TT.NUMBER, TT.STRING])

	def _parse_partition_boundary(self):
		"""Parses a partition boundary in a PARTITION clause"""
		if self._match('STARTING'):
			self._match('FROM')
			if self._match('('):
				while True:
					self._expect_one_of([TT.NUMBER, 'MINVALUE', 'MAXVALUE'])
					if not self._match(','):
						break
				self._expect(')')
			else:
				self._expect_one_of([TT.NUMBER, 'MINVALUE', 'MAXVALUE'])
			self._match_one_of(['INCLUSIVE', 'EXCLUSIVE'])
		self._expect('ENDING')
		self._match('AT')
		if self._match('('):
			while True:
				self._expect_one_of([TT.NUMBER, 'MINVALUE', 'MAXVALUE'])
				if not self._match(','):
					break
			self._expect(')')
		else:
			self._expect_one_of([TT.NUMBER, 'MINVALUE', 'MAXVALUE'])
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
					t = t.value
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
			self._expect(TT.IDENTIFIER)
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
			self._expect_sequence(['>', TT.NUMBER])
		elif self._match('TOTALSCPARTITIONCONNECTIONS'):
			self._expect_sequence(['>', TT.NUMBER])
			if self._match('QUEUEDCONNECTIONS'):
				if self._match('>'):
					self._expect(TT.NUMBER)
				elif self._match('UNBOUNDED'):
					pass
				else:
					self._expected_one_of(['>', 'UNBOUNDED'])
		elif self._match('CONCURRENTDBCOORDACTIVITIES'):
			self._expect_sequence(['>', TT.NUMBER])
			if self._match('QUEUEDACTIVITIES'):
				if self._match('>'):
					self._expect(TT.NUMBER)
				elif self._match('UNBOUNDED'):
					pass
				else:
					self._expected_one_of(['>', 'UNBOUNDED'])
		elif self._match_one_of([
			'CONNECTIONIDLETIME',
			'ACTIVITYTOTALTIME',
		]):
			self._expect_sequence(['>', TT.NUMBER])
			self._expect_one_of([
				'DAY',
				'DAYS',
				'HOUR',
				'HOURS',
				'MINUTE',
				'MINUTES'
			])
		elif self._match('SQLTEMPSPACE'):
			self._expect_sequence(['>', TT.NUMBER])
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
			self._expect_one_of(['SYSDEFAULTHISTOGRAM', TT.IDENTIFIER])

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
			self._expect_sequence(['FROM', TT.NUMBER])
			if self._match('TO'):
				self._expect_one_of(['UNBOUNDED', TT.NUMBER])

	def _parse_routines_in_schema_clause(self, alter=False):
		"""Parses a schema clause in a WORK CLASS definition"""
		# ROUTINES already matched
		if alter and self._match('ALL'):
			pass
		else:
			self._expect_sequence(['IN', 'SCHEMA', TT.IDENTIFIER])

	def _parse_position_clause(self):
		"""Parses a POSITION clause in a WORK CLASS definition"""
		# POSITION already matched
		if self._match('AT'):
			self._expect(TT.NUMBER)
		elif self._match_one_of(['BEFORE', 'AFTER']):
			self._expect(TT.IDENTIFIER)
		elif self._match('LAST'):
			pass
		else:
			self._expected_one_of(['AT', 'BEFORE', 'AFTER', 'LAST'])

	def _parse_connection_attributes(self):
		"""Parses connection attributes in a WORKLOAD"""
		if self._match_one_of([(TT.REGISTER, 'APPLNAME'), (TT.REGISTER, 'SYSTEM_USER')]):
			pass
		elif self._match((TT.REGISTER, 'SESSION_USER')):
			self._match('GROUP')
		elif self._match('CURRENT'):
			self._expect_one_of([
				(TT.REGISTER, 'CLIENT_USERID'),
				(TT.REGISTER, 'CLIENT_APPLNAME'),
				(TT.REGISTER, 'CLIENT_WRKSTNNAME'),
				(TT.REGISTER, 'CLIENT_ACCTNG')
			])
		else:
			self._expected_one_of(['APPLNAME', 'SYSTEM_USER', 'SESSION_USER', 'CURRENT'])
		self._expect('(')
		while True:
			if not self._match(TT.STRING):
				self._expect(')')
				break

	def _parse_audit_policy(self, alter=False):
		"""Parses an AUDIT POLICY definition"""
		valid = set(['CATEGORIES', 'ERROR'])
		while valid:
			t = self._match_one_of(valid)
			if t:
				t = t.value
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
						'SYSADMIN',
						'VALIDATE'
					]).value == 'EXECUTE':
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
			self._expect(TT.IDENTIFIER)
			if self._match('('):
				valid = set(['TABLE', 'IN', 'PCTDEACTIVATE', 'TRUNC', 'INCLUDES', 'EXCLUDES'])
				while valid:
					t = self._match_one_of(valid)
					if t:
						t = t.value
						valid.remove(t)
					else:
						break
					if t == 'TABLE':
						self._parse_table_name()
					elif t == 'IN':
						self._expect(TT.IDENTIFIER)
					elif t == 'PCTDEACTIVATE':
						self._expect(TT.NUMBER)
					elif t == 'TRUNC':
						pass
					elif t == 'INCLUDES' or t == 'EXCLUDES':
						self._expect('(')
						while True:
							self._expect(TT.IDENTIFIER)
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
					t = t.value
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
					self._expect(TT.NUMBER)
				elif t == 'BLOCKED':
					valid.remove('NONBLOCKED')
				elif t == 'NONBLOCKED':
					valid.remove('BLOCKED')
		elif self._match('PIPE'):
			self._expect(TT.STRING)
		elif self._match('FILE'):
			self._expect(TT.STRING)
			valid = set(['MAXFILES', 'MAXFILESIZE', 'BUFFERSIZE', 'BLOCKED', 'NONBLOCKED', 'APPEND', 'REPLACE'])
			while valid:
				t = self._match_one_of(valid)
				if t:
					t = t.value
					valid.remove(t)
				else:
					break
				if t == 'MAXFILES' or t == 'MAXFILESIZE':
					self._expect_one_of(['NONE', TT.NUMBER])
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
				t = t.value
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
				self._expect(TT.NUMBER)
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
		if self._expect_one_of(['ACTIVITIES', 'STATISTICS', 'THRESHOLD']).value == 'THRESHOLD':
			self._expect('VIOLATIONS')
		self._parse_evm_options()

	# STATEMENTS #############################################################

	def _parse_allocate_cursor_statement(self):
		"""Parses an ALLOCATE CURSOR statement in a procedure"""
		# ALLOCATE already matched
		self._expect_sequence([TT.IDENTIFIER, 'CURSOR', 'FOR', 'RESULT', 'SET', TT.IDENTIFIER])

	def _parse_alter_audit_policy_statement(self):
		"""Parses an ALTER AUDIT POLICY statement"""
		# ALTER AUDIT POLICY already matched
		self._expect(IDENTIIER)
		self._parse_audit_policy(alter=True)

	def _parse_alter_bufferpool_statement(self):
		"""Parses an ALTER BUFFERPOOL statement"""
		# ALTER BUFFERPOOL already matched
		self._expect(TT.IDENTIFIER)
		if self._match('ADD'):
			if self._expect_one_of(['NODEGROUP', 'DATABASE']).value == 'DATABASE':
				self._expect_sequence(['PARTITION', 'GROUP'])
			self._expect(TT.IDENTIFIER)
		elif self._match('NUMBLOCKPAGES'):
			self._expect(TT.NUMBER)
			if self._match('BLOCKSIZE'):
				self._expect(TT.NUMBER)
		elif self._match('BLOCKSIZE'):
			self._expect(TT.NUMBER)
		elif self._match('NOT'):
			self._expect_sequence(['EXTENDED', 'STORAGE'])
		elif self._match('EXTENDED'):
			self._expect('STORAGE')
		else:
			self._match_one_of(['IMMEDIATE', 'DEFERRED'])
			if self._match_one_of(['DBPARTITIONNUM', 'NODE']):
				self._expect(TT.NUMBER)
			self._expect('SIZE')
			if self._match(TT.NUMBER):
				self._match('AUTOMATIC')
			else:
				self._expect_one_of([TT.NUMBER, 'AUTOMATIC'])

	def _parse_alter_database_statement(self):
		"""Parses an ALTER DATABASE statement"""
		# ALTER DATABASE already matched
		if not self._match('ADD'):
			self._expect(TT.IDENTIFIER)
			self._expect('ADD')
		self._expect_sequence(['STORAGE', 'ON'])
		while True:
			self._expect(TT.STRING)
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
				self._expect_one_of([TT.STRING, TT.IDENTIFIER])
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
		self._expect(TT.IDENTIFIER)
		while True:
			if self._match('ADD'):
				self._parse_db_partition_list_clause(size=False)
				if self._match('LIKE'):
					self._expect_one_of(['DBPARTITIONNUM', 'NODE'])
					self._expect(TT.NUMBER)
				elif self._match('WITHOUT'):
					self._expect('TABLESPACES')
			elif self._match('DROP'):
				self._parse_db_partition_list_clause(size=False)
			else:
				self._expected_one_of(['ADD', 'DROP'])
			if not self._match(','):
				break

	def _parse_alter_histogram_template_statement(self):
		"""Parses an ALTER HISTOGRAM TEMPLATE statement"""
		# ALTER HISTOGRAM TEMPLATE already matched
		self._expect_sequence([TT.IDENTIFIER, 'HIGH', 'BIN', 'VALUE', TT.NUMBER])

	def _parse_alter_module_statement(self):
		"""Parses an ALTER MODULE statement"""
		# ALTER MODULE already matched
		self._parse_module_name()
		if self._match_one_of(['ADD', 'PUBLISH']):
			self._match_sequence(['OR', 'REPLACE'])
			if self._match('CONDITION'):
				self._expect(TT.IDENTIFIER)
				if self._match('FOR'):
					if self._match('SQLSTATE'):
						self._match('VALUE')
					self._expect(TT.STRING)
			elif self._match('FUNCTION'):
				self._parse_create_function_statement()
			elif self._match('PROCEDURE'):
				self._parse_create_procedure_statement()
			elif self._match('TYPE'):
				self._parse_create_type_statement()
			elif self._match('VARIABLE'):
				self._parse_create_variable_statement()
		elif self._match('DROP'):
			if not self._match('BODY'):
				if self._match('CONDITION'):
					self._expect(TT.IDENTIFIER)
				elif self._match_one_of(['FUNCTION', 'PROCEDURE']):
					self._parse_routine_name()
					if self._match('(', prespace=False):
						self._parse_datatype_list()
						self._expect(')')
				elif self._match('SPECIFIC'):
					self._expect_one_of(['FUNCTION', 'PROCEDURE'])
					self._parse_routine_name()
				elif self._match('TYPE'):
					self._parse_type_name()
				elif self._match('VARIABLE'):
					self._parse_variable_name()
				else:
					self._expected_one_of([
						'BODY',
						'CONDITION',
						'FUNCTION',
						'PROCEDURE',
						'SPECIFIC',
						'TYPE',
						'VARIABLE',
					])
		else:
			self._expected_one_of(['ADD', 'DROP', 'PUBLISH'])

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
					self._expect_sequence(['KEY', TT.IDENTIFIER])
				elif self._match_one_of(['UNIQUE', 'CHECK', 'CONSTRAINT']):
					self._expect(TT.IDENTIFIER)
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
					self._expect([TT.STRING, TT.IDENTIFIER])
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
				self._expect_sequence(['PARAMETER', TT.IDENTIFIER, 'SET', 'DATA', 'TYPE'])
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
		self._expect_sequence(TT.IDENTIFIER, 'ADD', 'ELEMENT', TT.STRING)
		if self._match_one_of(['BEFORE', 'AFTER']):
			self._expect(TT.STRING)
		elif self._match('ROOT'):
			pass
		elif self._match('UNDER'):
			self._expect(TT.STRING)
			if self._match('OVER'):
				while True:
					self._expect(TT.STRING)
					if not self._match(','):
						break
					self._expect('OVER')

	def _parse_alter_security_policy_statement(self):
		"""Parses an ALTER SECURITY POLICY statement"""
		# ALTER SECURITY POLICY
		self._expect(TT.IDENTIFIER)
		while True:
			if self._match('ADD'):
				self._expect_sequence(['SECURITY', 'LABEL', 'COMPONENT', TT.IDENTIFIER])
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
		self._expect(TT.IDENTIFIER)
		if self._match('UNDER'):
			self._expect(TT.IDENTIFIER)
		first = True
		while True:
			if self._match('AGENT'):
				self._expect('PRIORITY')
				self._expect_one_of(['DEFAULT', TT.NUMBER])
			elif self._match('PREFETCH'):
				self._expect('PRIORITY')
				self._expect_one_of(['LOW', 'MEDIUM', 'HIGH', 'DEFAULT'])
			elif self._match('OUTBOUND'):
				self._expect('CORRELATOR')
				self._expect_one_of(['NONE', TT.STRING])
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
				self._expect_sequence(['HISTOGRAM', 'TEMPLATE', TT.IDENTIFIER])
			elif self._match('REQUEST'):
				self._expect_sequence(['EXECUTETIME', 'HISTOGRAM', 'TEMPLATE', TT.IDENTIFIER])
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
						self._match(TT.IDENTIFIER)
						self._parse_partition_boundary()
					except ParseError:
						self._restore_state()
						self._parse_partition_boundary()
					else:
						self._forget_state()
					if self._match('IN'):
						self._expect(TT.IDENTIFIER)
					if self._match('LONG'):
						self._expect('IN')
						self._expect(TT.IDENTIFIER)
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
					self._expect(TT.IDENTIFIER)
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
					self._match(TT.IDENTIFIER)
					self._parse_partition_boundary()
				except ParseError:
					self._restore_state()
					self._parse_partition_boundary()
				else:
					self._forget_state()
				self._expect('FROM')
				self._parse_table_name()
			elif self._match('DETACH'):
				self._expect_sequence(['PARTITION', TT.IDENTIFIER, 'FROM'])
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
			elif self._match('RENAME'):
				self._match('COLUMN')
				self._expect_sequence([TT.IDENTIFIER, 'TO', TT.IDENTIFIER])
			elif self._match('DROP'):
				if self._match('PRIMARY'):
					self._expect('KEY')
				elif self._match('FOREIGN'):
					self._expect_sequence(['KEY', TT.IDENTIFIER])
				elif self._match_one_of(['UNIQUE', 'CHECK', 'CONSTRAINT']):
					self._expect(TT.IDENTIFIER)
				elif self._match('COLUMN'):
					self._expect(TT.IDENTIFIER)
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
					self._expect(TT.IDENTIFIER)
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
				self._expect(TT.NUMBER)
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
				if self._expect_one_of(['NOT', 'VALUE']).value == 'NOT':
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
		self._expect(TT.IDENTIFIER)
		first = True
		while True:
			if self._match('ADD'):
				if self._match('TO'):
					self._expect_sequence(['STRIPE', 'SET', TT.IDENTIFIER])
					self._parse_database_container_clause()
					if self._match('ON'):
						self._parse_db_partition_list_clause(size=False)
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
							self._parse_db_partition_list_clause(size=False)
					except ParseError:
						# If that fails, rewind and try a system container
						# clause
						self._restore_state()
						if reraise: raise
						self._parse_system_container_clause()
						self._parse_db_partition_list_clause(size=False)
					else:
						self._forget_state()
			elif self._match('BEGIN'):
				self._expect_sequence(['NEW', 'STRIPE', 'SET'])
				self._parse_database_container_clause()
				if self._match('ON'):
					self._parse_db_partition_list_clause(size=False)
			elif self._match('DROP'):
				self._parse_database_container_clause(size=False)
				if self._match('ON'):
					self._parse_db_partition_list_clause(size=False)
			elif self._match_one_of(['EXTEND', 'REDUCE']):
				# Ambiguity: could be a Database or ALL containers clause
				reraise = False
				self._save_state()
				try:
					# Try an ALL containers clause first
					self._expect_sequence(['(', 'ALL'])
					reraise = True
					self._match('CONTAINERS')
					self._expect(TT.NUMBER)
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
					self._parse_db_partition_list_clause(size=False)
			elif self._match('PREFETCHSIZE'):
				if not self._match('AUTOMATIC'):
					self._expect(TT.NUMBER)
					self._match_one_of(['K', 'M', 'G'])
			elif self._match('BUFFERPOOL'):
				self._expect(TT.IDENTIFIER)
			elif self._match('OVERHEAD'):
				self._expect(TT.NUMBER)
			elif self._match('TRANSFERRATE'):
				self._expect(TT.NUMBER)
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
				self._expect(TT.NUMBER)
				self._expect_one_of(['K', 'M', 'G', 'PERCENT'])
			elif self._match('MAXSIZE'):
				if not self_match('NONE'):
					self._expect(TT.NUMBER)
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
		self._expect(TT.IDENTIFIER)
		while True:
			if self._match('WHEN'):
				self._parse_threshold_predicate()
				self._parse_threshold_exceeded_actions()
			elif not self._match_one_of(['ENABLE', 'DISABLE']):
				break

	def _parse_alter_trusted_context_statement(self):
		"""Parses an ALTER TRUSTED CONTEXT statement"""
		# ALTER TRUSTED CONTEXT already matched
		self._expect(TT.IDENTIFIER)
		first = True
		while True:
			if self._match('ADD'):
				if self._match('ATTRIBUTES'):
					self._expect('(')
					while True:
						self._expect_sequence(['ADDRESS', TT.STRING])
						if self._match('WITH'):
							self._expect_sequence(['ENCRYPTION', TT.STRING])
						if not self._match(','):
							break
					self._expect(')')
				elif self._match('USE'):
					self._expect('FOR')
					while True:
						if not self._match('PUBLIC'):
							self._expect(TT.IDENTIFIER)
							self._match_sequence(['ROLE', TT.IDENTIFIER])
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
						self._expect_sequence(['ADDRESS', TT.STRING])
						if not self._match(','):
							break
					self._expect(')')
				elif self._match('USE'):
					self._expect('FOR')
					while True:
						if not self._match('PUBLIC'):
							self._expect(TT.IDENTIFIER)
						if not self._match(','):
							break
				else:
					self._expected_one_of(['ATTRIBUTES', 'USE'])
			elif self._match('ALTER'):
				while True:
					if self._match('SYSTEM'):
						self._expect_sequence(['AUTHID', TT.IDENTIFIER])
					elif self._match('ATTRIBUTES'):
						self._expect('(')
						while True:
							self._expect_one_of(['ADDRESS', 'ENCRYPTION'])
							self._expect(TT.STRING)
							if not self._match(','):
								break
						self._expect(')')
					elif self._match('NO'):
						self._expect_sequence(['DEFAULT', 'ROLE'])
					elif self._match('DEFAULT'):
						self._expect_sequence(['ROLE', TT.IDENTIFIER])
					elif not self._match_one_of(['ENABLE', 'DISABLE']):
						break
			elif self._match('REPLACE'):
				self._expect_sequence(['USE', 'FOR'])
				while True:
					if not self._match('PUBLIC'):
						self._expect(TT.IDENTIFIER)
						self._match_sequence(['ROLE', TT.IDENTIFIER])
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
			self._expect_sequence([TT.IDENTIFIER, 'SERVER', TT.IDENTIFIER, 'OPTIONS'])
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
		self._expect(TT.IDENTIFIER)
		first = True
		while True:
			if self._match('ADD'):
				self._match_sequence(['WORK', 'ACTION'])
				self._expect_sequence([TT.IDENTIFIER, 'ON', 'WORK', 'CLASS', TT.IDENTIFIER])
				self._parse_action_types_clause()
				self._parse_histogram_template_clause()
				self._match_one_of(['ENABLE', 'DISABLE'])
			elif self._match('ALTER'):
				self._match_sequence(['WORK', 'ACTION'])
				self._expect(TT.IDENTIFIER)
				while True:
					if self._match('SET'):
						self._expect_sequence(['WORK', 'CLASS', TT.IDENTIFIER])
					elif self._match('ACTIVITY'):
						self._expect_one_of(['LIFETIME', 'QUEUETIME', 'EXECUTETIME', 'ESIMATEDCOST', 'INTERARRIVALTIME'])
						self._expect_sequence(['HISTOGRAM', 'TEMPLATE', TT.IDENTIFIER])
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
				self._expect(TT.IDENTIFIER)
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
		self._expect(TT.IDENTIFIER)
		outer = True
		while True:
			if self._match('ADD'):
				self._match_sequence(['WORK', 'CLASS'])
				self._expect(TT.IDENTIFIER)
				self._parse_work_attributes()
				self._expect('POSITION')
				self._parse_position_clause()
			elif self._match('ALTER'):
				self._match_sequence(['WORK', 'CLASS'])
				self._expect(TT.IDENTIFIER)
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
				self._expect(TT.IDENTIFIER)
			elif outer:
				self._expected_one_of(['ADD', 'ALTER', 'DROP'])
			else:
				break
			outer = False

	def _parse_alter_workload_statement(self):
		"""Parses an ALTER WORKLOAD statement"""
		self._expect(TT.IDENTIFIER)
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
				self._expect_sequence(['CLASS', TT.IDENTIFIER])
				if self._match('UNDER'):
					self._expect(TT.IDENTIFIER)
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
		self._expect(TT.IDENTIFIER)
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
				self._expect(TT.IDENTIFIER)
			elif self._match_one_of(['USER', 'GROUP', 'ROLE']):
				self._expect(TT.IDENTIFIER)
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
			self._expect_sequence(['POLICY', TT.IDENTIFIER])
		elif not self._match_sequence(['REMOVE', 'POLICY']):
			self._expected_one_of(['USING', 'REPLACE', 'REMOVE'])

	def _parse_call_statement(self):
		"""Parses a CALL statement"""
		# CALL already matched
		self._parse_subschema_name()
		if self._match('(', prespace=False):
			if not self._match(')'):
				while True:
					# Try and parse an optional parameter name
					self._save_state()
					try:
						self._expect(TT.IDENTIFIER)
						self._expect('=>')
					except ParseError:
						self._restore_state()
					# Parse the parameter value
					self._parse_expression()
					if not self._match(','):
						break
				self._expect(')')

	def _parse_case_statement(self):
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
				self._parse_compiled_statement()
				self._expect((TT.TERMINATOR, ';'))
				t = self._match_one_of(['WHEN', 'ELSE', 'END'])
				if t:
					self._outdent(-1)
					t = t.value
					break
				else:
					self._newline()
			if t != 'WHEN':
				break
		# Handle ELSE clause (common to both variations)
		if t == 'ELSE':
			self._indent()
			while True:
				self._parse_compiled_statement()
				self._expect((TT.TERMINATOR, ';'))
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
		self._expect(TT.IDENTIFIER)
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
				self._expect(TT.IDENTIFIER)
				self._valign()
				self._expect_sequence(['IS', TT.STRING])
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
					self._expect(TT.IDENTIFIER)
				else:
					self._parse_subschema_name()
			elif self._match('PACKAGE'):
				self._parse_subschema_name()
				self._match('VERSION')
				# XXX Ambiguity: IDENTIFIER will match "IS" below. How to solve
				# this? Only double-quoted identifiers are actually permitted
				# here (or strings)
				self._match_one_of([TT.IDENTIFIER, TT.STRING])
			elif self._match_one_of(['DISTINCT', 'DATA']):
				self._expect('TYPE')
				self._parse_type_name()
			elif self._match_one_of(['COLUMN', 'CONSTRAINT']):
				self._parse_subrelation_name()
			elif self._match_one_of(['SCHEMA', 'TABLESPACE', 'WRAPPER', 'WORKLOAD', 'NODEGROUP', 'ROLE', 'THRESHOLD']):
				self._expect(TT.IDENTIFIER)
			elif self._match_sequence(['DATABASE', 'PARTITION', 'GROUP']):
				self._expect(TT.IDENTIFIER)
			elif self._match_sequence(['AUDIT', 'POLICY']):
				self._expect(TT.IDENTIFIER)
			elif self._match_sequence(['SECURITY', 'POLICY']):
				self._expect(TT.IDENTIFIER)
			elif self._match_sequence(['SECURITY', 'LABEL']):
				self._match('COMPONENT')
				self._expect(TT.IDENTIFIER)
			elif self._match('SERVER'):
				if self._match('OPTION'):
					self._expect_sequence([TT.IDENTIFIER, 'FOR'])
					self._parse_remote_server()
				else:
					self._expect(TT.IDENTIFIER)
			elif self._match('SERVICE'):
				self._expect('CLASS')
				self._expect(TT.IDENTIFIER)
				self._match_sequence(['UNDER', TT.IDENTIFIER])
			elif self._match_sequence(['TRUSTED', 'CONTEXT']):
				self._expect(TT.IDENTIFIER)
			elif self._match_sequence(['HISTOGRAM', 'TEMPLATE']):
				self._expect(TT.IDENTIFIER)
			elif self._match_sequence(['WORK', 'ACTION', 'SET']):
				self._expect(TT.IDENTIFIER)
			elif self._match_sequence(['WORK', 'CLASS', 'SET']):
				self._expect(TT.IDENTIFIER)
			elif self._match('FUNCTION'):
				if self._match('MAPPING'):
					self._expect(TT.IDENTIFIER)
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
			self._expect_sequence(['IS', TT.STRING])
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
		self._expect(TT.IDENTIFIER)
		self._parse_audit_policy()

	def _parse_create_bufferpool_statement(self):
		"""Parses a CREATE BUFFERPOOL statement"""
		# CREATE BUFFERPOOL already matched
		self._expect(TT.IDENTIFIER)
		self._match_one_of(['IMMEDIATE', 'DEFERRED'])
		if self._match('ALL'):
			self._expect('DBPARTITIONNUMS')
		elif self._match('DATABASE'):
			self._expect_sequence(['PARTITION', 'GROUP'])
			self._parse_ident_list()
		elif self._match('NODEGROUP'):
			self._parse_ident_list()
		self._expect('SIZE')
		if self._match(TT.NUMBER):
			self._match('AUTOMATIC')
		elif self._match('AUTOMATIC'):
			pass
		else:
			self._expected_one_of([TT.NUMBER, 'AUTOMATIC'])
		# Parse function options (which can appear in any order)
		valid = set(['NUMBLOCKPAGES', 'PAGESIZE', 'EXTENDED', 'EXCEPT', 'NOT'])
		while valid:
			t = self._match_one_of(valid)
			if t:
				t = t.value
				valid.remove(t)
			else:
				break
			if self._match('EXCEPT'):
				self._expect('ON')
				self._parse_db_partition_list_clause(size=True)
			elif t == 'NUMBLOCKPAGES':
				self._expect(TT.NUMBER)
				if self._match('BLOCKSIZE'):
					self._expect(TT.NUMBER)
			elif t == 'PAGESIZE':
				self._expect(TT.NUMBER)
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
		self._expect(TT.IDENTIFIER)
		if self._match('ON'):
			if self._match('ALL'):
				self._expect_one_of(['DBPARTITIONNUMS', 'NODES'])
			else:
				self._parse_db_partition_list_clause(size=False)

	def _parse_create_event_monitor_statement(self):
		"""Parses a CREATE EVENT MONITOR statement"""
		# CREATE EVENT MONITOR already matched
		self._expect(TT.IDENTIFIER)
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
					self._expect(TT.IDENTIFIER)
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
					t = t.value
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
					self._expect(TT.NUMBER)
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
						self._expect_one_of([TT.STRING, TT.IDENTIFIER])
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
					t = self._expect_one_of(['DBINFO', 'EXTERNAL', 'FINAL', 'SCRATCHPAD']).value
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
						if self._match('('):
							while True:
								self._expect(TT.IDENTIFIER)
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
					self._expect(TT.NUMBER)
				elif t == 'SPECIFIC':
					self._expect(TT.IDENTIFIER)
				elif t == 'STATIC':
					self._expect('DISPATCH')
				elif t == 'THREADSAFE':
					pass
				elif t == 'TRANSFORM':
					self._expect_sequence(['GROUP', TT.IDENTIFIER])
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
		if self._expect_one_of(['BEGIN', 'RETURN']).value == 'BEGIN':
			self._parse_compiled_compound_statement()
		else:
			self._indent()
			self._parse_return_statement()
			self._outdent()

	def _parse_create_function_mapping_statement(self):
		"""Parses a CREATE FUNCTION MAPPING statement"""
		# CREATE FUNCTION MAPPING already matched
		if not self._match('FOR'):
			self._expect_sequence([TT.IDENTIFIER, 'FOR'])
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
		self._expect_sequence([TT.IDENTIFIER, 'HIGH', 'BIN', 'VALUE', TT.NUMBER])

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
			self._expect(TT.IDENTIFIER)
			self._match_one_of(['ASC', 'DESC'])
			if not self._match(','):
				break
			else:
				self._newline()
		self._outdent()
		self._expect(')')
		self._match_sequence(['IN', TT.IDENTIFIER])
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
				t = t.value
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
				self._expect(TT.NUMBER)
			elif t == 'LEVEL2':
				self._expect_sequence(['PCTFREE', TT.NUMBER])
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

	def _parse_create_module_statement(self):
		"""Parses a CREATE MODULE statement"""
		# CREATE MODULE already matched
		self._parse_module_name()

	def _parse_create_nickname_statement(self):
		"""Parses a CREATE NICKNAME statement"""
		# CREATE NICKNAME already matched
		self._parse_nickname_name()
		if self._match('FOR'):
			self._parse_remote_object_name()
		else:
			self._parse_table_definition(aligntypes=True, alignoptions=True, federated=True)
			self._expect_sequence(['FOR', 'SERVER', TT.IDENTIFIER])
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
				self._expect_sequence(['OF', 'PARAMETERS', TT.NUMBER])
			if self._match('UNIQUE'):
				self._expect(TT.STRING)
			self.expect_sequence(['FOR', 'SERVER', TT.IDENTIFIER])
		elif self._match('(', prespace=False):
			if not self._match(')'):
				while True:
					self._match_one_of(['IN', 'OUT', 'INOUT'])
					self._save_state()
					try:
						self._expect(TT.IDENTIFIER)
						self._parse_datatype()
					except ParseError:
						self._restore_state()
						self._parse_datatype()
					else:
						self._forget_state()
					if self._match('DEFAULT'):
						self._parse_expression()
					if not self._match(','):
						break
				self._expect(')')
		self._indent()
		# Parse procedure options (which can appear in any order)
		valid = set([
			'AUTONOMOUS',
			'CALLED',
			'COMMIT',
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
				t = t.value
				# Note that matches aren't removed from valid, because it's
				# simply too complex to figure out what option disallows other
				# options in many cases
			else:
				break
			if t == 'AUTONOMOUS':
				pass
			elif t == 'CALLED':
				self._expect_sequence(['ON', 'NULL', 'INPUT'])
			elif t == 'COMMIT':
				self._expect_sequence(['ON', 'RETURN'])
				self._expect_one_of(['NO', 'YES'])
			elif t == 'CONTAINS':
				self._expect('SQL')
			elif t == 'DBINFO':
				pass
			elif t == 'DETERMINISTIC':
				pass
			elif t == 'DYNAMIC':
				self._expect_sequence(['RESULT', 'SETS', TT.NUMBER])
			elif t == 'EXTERNAL':
				if self._match('NAME'):
					self._expect_one_of([TT.STRING, TT.IDENTIFIER])
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
					]).value
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
				self._expect_sequence(['SETS', TT.NUMBER])
			elif t == 'SPECIFIC':
				self._expect(TT.IDENTIFIER)
			elif t == 'THREADSAFE':
				pass
			elif t == 'WITH':
				self._expect_sequence(['RETURN', 'TO'])
				self._expect_one_of(['CALLER', 'CLIENT'])
				self._expect('ALL')
			self._newline()
		self._outdent()
		self._expect('BEGIN')
		self._parse_compiled_compound_statement()

	def _parse_create_role_statement(self):
		"""Parses a CREATE ROLE statement"""
		# CREATE ROLE already matched
		self._expect(TT.IDENTIFIER)

	def _parse_create_schema_statement(self):
		"""Parses a CREATE SCHEMA statement"""
		# CREATE SCHEMA already matched
		if self._match('AUTHORIZATION'):
			self._expect(TT.IDENTIFIER)
		else:
			self._expect(TT.IDENTIFIER)
			if self._match('AUTHORIZATION'):
				self._expect(TT.IDENTIFIER)
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
		self._expect(TT.IDENTIFIER)
		if self._match('ARRAY'):
			self._expect('[', prespace=False)
			while True:
				self._expect(TT.STRING)
				if not self._match(','):
					break
			self._expect(']')
		elif self._match('SET'):
			self._expect('{', prespace=False)
			while True:
				self._expect(TT.STRING)
				if not self._match(','):
					break
			self._expect('}')
		elif self._match('TREE'):
			self._expect_sequence(['(', TT.STRING, 'ROOT'], prespace=False)
			while self._match(','):
				self._expect_sequence([TT.STRING, 'UNDER', TT.STRING])
			self._expect(')')

	def _parse_create_security_label_statement(self):
		"""Parses a CREATE SECURITY LABEL statement"""
		# CREATE SECURITY LABEL already matched
		self._parse_security_label_name()
		while True:
			self._expect_sequence(['COMPONENT', TT.IDENTIFIER, TT.STRING])
			while self._match_sequence([',', TT.STRING]):
				pass
			if not self._match(','):
				break

	def _parse_create_security_policy_statement(self):
		"""Parses a CREATE SECURITY POLICY statement"""
		# CREATE SECURITY POLICY already matched
		self._expect_sequence([TT.IDENTIFIER, 'COMPONENTS'])
		while True:
			self._expect(TT.IDENTIFIER)
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
		self._expect(TT.IDENTIFIER)
		if self._match('UNDER'):
			self._expect(TT.IDENTIFIER)
		if self._match_sequence(['AGENT', 'PRIORITY']):
			self._expect_one_of(['DEFAULT', TT.NUMBER])
		if self._match_sequence(['PREFETCH', 'PRIORITY']):
			self._expect_one_of(['DEFAULT', 'HIGH', 'MEDIUM', 'LOW'])
		if self._match_sequence(['OUTBOUND', 'CORRELATOR']):
			self._expect_one_of(['NONE', TT.STRING])
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
		self._expect(TT.IDENTIFIER)
		if self._match('TYPE'):
			self._expect(TT.IDENTIFIER)
		if self._match('VERSION'):
			self._parse_server_version()
		if self._match('WRAPPER'):
			self._expect(TT.IDENTIFIER)
		if self._match('AUTHORIZATION'):
			self._expect_sequence([TT.IDENTIFIER, 'PASSWORD', TT.IDENTIFIER])
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
				t = t.value
				valid.remove(t)
			else:
				break
			if t == 'ORGANIZE':
				self._expect('BY')
				if self._match_sequence(['KEY', 'SEQUENCE']):
					self._expect('(')
					while True:
						self._expect(TT.IDENTIFIER)
						if self._match('STARTING'):
							self._match('FROM')
							self._expect(TT.NUMBER)
						self._expect('ENDING')
						self._match('AT')
						self._expect(TT.NUMBER)
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
							self._expect(TT.IDENTIFIER)
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
				self._expect_sequence(['IN', TT.IDENTIFIER])
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
					self._expect(TT.IDENTIFIER)
					if self._match('NULLS'):
						self._expect_one_of(['FIRST', 'LAST'])
					if not self._match(','):
						break
				self._expect_sequence([')', '('])
				while True:
					if self._match('PARTITION'):
						self._expect(TT.IDENTIFIER)
					self._parse_partition_boundary()
					if self._match('IN'):
						self._expect(TT.IDENTIFIER)
					elif self._match('EVERY'):
						if self._match('('):
							self._expect(TT.NUMBER)
							self._parse_duration_label()
							self._expect(')')
						else:
							self._expect(TT.NUMBER)
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
				self._expect_sequence(['POLICY', TT.IDENTIFIER])
			elif t == 'OPTIONS':
				self._parse_federated_options(alter=False)

	def _parse_create_tablespace_statement(self, tbspacetype='REGULAR'):
		"""Parses a CREATE TABLESPACE statement"""
		# CREATE TABLESPACE already matched
		self._expect(TT.IDENTIFIER)
		if self._match('IN'):
			if self._match('DATABASE'):
				self._expect_sequence(['PARTITION', 'GROUP'])
			elif self._match('NODEGROUP'):
				pass
			self._expect(TT.IDENTIFIER)
		if self._match('PAGESIZE'):
			self._expect(TT.NUMBER)
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
						self._parse_db_partition_list_clause(size=False)
					if not self._match('USING'):
						break
				self._parse_tablespace_size_attributes()
			elif self._match('SYSTEM'):
				self._expect('USING')
				while True:
					self._parse_system_container_clause()
					if self._match('ON'):
						self._parse_db_partition_list_clause(size=False)
					if not self._match('USING'):
						break
			else:
				self._expected_one_of(['AUTOMATIC', 'DATABASE', 'SYSTEM'])
		if self._match('EXTENTSIZE'):
			self._expect(TT.NUMBER)
			self._match_one_of(['K', 'M'])
		if self._match('PREFETCHSIZE'):
			self._expect(TT.NUMBER)
			self._match_one_of(['K', 'M', 'G'])
		if self._match('BUFFERPOOL'):
			self._expect(TT.IDENTIFIER)
		if self._match('OVERHEAD'):
			self._expect(TT.NUMBER)
		if self._match('NO'):
			self._expect_sequence(['FILE', 'SYSTEM', 'CACHING'])
		elif self._match('FILE'):
			self._expect_sequence(['SYSTEM', 'CACHING'])
		if self._match('TRANSFERRATE'):
			self._expect(TT.NUMBER)
		if self._match('DROPPED'):
			self._expect_sequence(['TABLE', 'RECOVERY'])
			self._expect_one_of(['ON', 'OFF'])

	def _parse_create_threshold_statement(self):
		"""Parses a CREATE THRESHOLD statement"""
		# CREATE THRESHOLD already matched
		self._expect_sequence([TT.IDENTIFIER, 'FOR'])
		if self._match('SERVICE'):
			self._expect_sequence(['CLASS', TT.IDENTIFIER])
			if self._match('UNDER'):
				self._expect(TT.IDENTIFIER)
		elif self._match('WORKLOAD'):
			self._expect(TT.IDENTIFIER)
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
		if self._match_sequence(['NO', 'CASCADE']):
			self._expect('BEFORE')
		elif self._match('BEFORE'):
			pass
		elif self._match_sequence(['INSTEAD', 'OF']):
			pass
		elif self._match('AFTER'):
			pass
		else:
			self._expected_one_of(['AFTER', 'BEFORE', 'NO', 'INSTEAD'])
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
					t = t.value
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
				self._expect(TT.IDENTIFIER)
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
			label = self._expect(TT.LABEL).value
			self._outdent(-1)
			self._newline()
		except ParseError:
			label = None
		if self._match('BEGIN'):
			if not label: self._outdent(-1)
			self._parse_compiled_compound_statement(label=label)
		else:
			self._parse_compiled_statement()
			if not label: self._outdent()

	def _parse_create_trusted_context_statement(self):
		"""Parses a CREATE TRUSTED CONTEXT statement"""
		# CREATE TRUSTED CONTEXT already matched
		self._expect_sequence([TT.IDENTIFIER, 'BASED', 'UPON', 'CONNECTION', 'USING'])
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
				t = t.value
				valid.remove(t)
			else:
				break
			if t == 'SYSTEM':
				self._expect_sequence(['AUTHID', TT.IDENTIFIER])
			elif t == 'ATTRIBUTES':
				self._expect('(')
				if self._match('ADDRESS'):
					self._expect(TT.STRING)
					if self._match('WITH'):
						self._expect_sequence(['ENCRYPTION', TT.STRING])
				elif self._match('ENCRYPTION'):
					self._expect(TT.STRING)
				if not self._match(','):
					break
				self._expect(')')
			elif t == 'NO':
				valid.remove('DEFAULT')
				self._expect_sequence(['DEFAULT', 'ROLE'])
			elif t == 'DEFAULT':
				valid.remove('NO')
				self._expect_sequence(['ROLE', TT.IDENTIFIER])
			elif t == 'DISABLE':
				valid.remove('ENABLE')
			elif t == 'ENABLE':
				valid.remove('DISABLE')
			elif t == 'WITH':
				self._expect_sequence(['USE', 'FOR'])
				if not self._match('PUBLIC'):
					self._expect(TT.IDENTIFIER)
					if self._match('ROLE'):
						self._expect(TT.IDENTIFIER)
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
			self._match(TT.NUMBER)
			self._expect(']')
		else:
			self._match_sequence(['WITH', 'COMPARISONS'])

	def _parse_create_type_mapping_statement(self):
		"""Parses a CREATE TYPE MAPPING statement"""
		# CREATE TYPE MAPPING already matched
		self._match(TT.IDENTIFIER)
		valid = set(['FROM', 'TO'])
		t = self._expect_one_of(valid).value
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
				self._expect_sequence([TT.NUMBER, '..', TT.NUMBER], interspace=False)
				self._expect(']')
			else:
				self._expect(TT.NUMBER)
			if self._match(','):
				if self._match('['):
					self._expect_sequence([TT.NUMBER, '..', TT.NUMBER], interspace=False)
					self._expect(']')
				else:
					self._expect(TT.NUMBER)
			self._expect(')')
			if self._match('P'):
				self._expect_one_of(['=', '>', '<', '>=', '<=', '<>'])
				self._expect('S')

	def _parse_create_user_mapping_statement(self):
		"""Parses a CREATE USER MAPPING statement"""
		# CREATE USER MAPPING already matched
		self._expect('FOR')
		self._expect_one_of(['USER', TT.IDENTIFIER])
		self._expect_sequence(['SERVER', TT.IDENTIFIER])
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
			t = self._expect_one_of(valid).value
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
		self._expect(TT.IDENTIFIER)
		self._expect('FOR')
		if self._match('SERVICE'):
			self._expect_sequence(['CLASS', TT.IDENTIFIER])
		elif self._match('DATABASE'):
			pass
		else:
			self._expected_one_of(['SERVICE', 'DATABASE'])
		self._expect_sequence(['USING', 'WORK', 'CLASS', 'SET', TT.IDENTIFIER])
		if self._match('('):
			self._indent()
			while True:
				self._expect_sequence(['WORK', 'ACTION', TT.IDENTIFIER, 'ON', 'WORK', 'CLASS', TT.IDENTIFIER])
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
		self._expect(TT.IDENTIFIER)
		if self._match('('):
			self._indent()
			while True:
				self._match_sequence(['WORK', 'CLASS'])
				self._expect(TT.IDENTIFIER)
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
		self._expect(TT.IDENTIFIER)
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
				self._expect(TT.IDENTIFIER)
				self._match_sequence(['UNDER', TT.IDENTIFIER])
		if self._match('POSITION'):
			self._parse_position_clause()
		if self._match_sequence(['COLLECT', 'ACTIVITY', 'DATA']):
			self._parse_collect_activity_data_clause(alter=True)

	def _parse_create_wrapper_statement(self):
		"""Parses a CREATE WRAPPER statement"""
		# CREATE WRAPPER already matched
		self._expect(TT.IDENTIFIER)
		if self._match('LIBRARY'):
			self._expect(TT.STRING)
		if self._match('OPTIONS'):
			self._parse_federated_options(alter=False)

	def _parse_declare_cursor_statement(self):
		"""Parses a top-level DECLARE CURSOR statement"""
		# DECLARE already matched
		self._expect_sequence([TT.IDENTIFIER, 'CURSOR'])
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
				t = t.value
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
				self._expect(TT.IDENTIFIER)
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
			self._expect(TT.IDENTIFIER)
			if self._match('UNDER'):
				self._expect(TT.IDENTIFIER)
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
			self._expect_one_of(['USER', TT.IDENTIFIER])
			self._expect_sequence(['SERVER', TT.IDENTIFIER])
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
			self._expect(TT.IDENTIFIER)
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

	def _parse_execute_statement(self):
		"""Parses an EXECUTE statement in a procedure"""
		# EXECUTE already matched
		self._expect(TT.IDENTIFIER)
		if self._match('INTO'):
			while True:
				self._parse_subrelation_name()
				if self._match('['):
					self._parse_expression()
					self._expect(']')
				if self._match('.'):
					self._expect(TT.IDENTIFIER)
				if not self._match(','):
					break
		if self._match('USING'):
			self._parse_expression_list()

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
		self._match_sequence(['SET', 'QUERYNO', '=', TT.NUMBER])
		self._match_sequence(['SET', 'QUEYRTAG', '=', TT.STRING])
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
		self._expect(TT.IDENTIFIER)
		if self._match('INTO'):
			self._parse_ident_list()
		elif self._match('USING'):
			self._expect('DESCRIPTOR')
			self._expect(TT.IDENTIFIER)
		else:
			self._expected_one_of(['INTO', 'USING'])

	def _parse_flush_optimization_profile_cache_statement(self):
		"""Parses a FLUSH OPTIMIZATION PROFILE CACHE statement"""
		# FLUSH OPTIMIZATION PROFILE CACHE already matched
		if not self._match('ALL'):
			self._parse_subschema_name()

	def _parse_for_statement(self, label=None):
		"""Parses a FOR-loop in a dynamic compound statement"""
		# FOR already matched
		self._expect_sequence([TT.IDENTIFIER, 'AS'])
		reraise = False
		self._indent()
		# Ambiguity: IDENTIFIER vs. select-statement
		self._save_state()
		try:
			self._expect(TT.IDENTIFIER)
			self._match_one_of(['ASENSITIVE', 'INSENSITIVE'])
			self._expect('CURSOR')
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
		self._expect('DO')
		self._indent()
		while True:
			self._parse_compiled_statement()
			self._expect((TT.TERMINATOR, ';'))
			self._newline()
			if self._match('END'):
				break
		self._outdent(-1)
		self._expect('FOR')
		if label:
			self._match((TT.IDENTIFIER, label))

	def _parse_free_locator_statement(self):
		"""Parses a FREE LOCATOR statement"""
		# FREE LOCATOR already matched
		self._parse_ident_list()

	def _parse_get_diagnostics_statement(self):
		"""Parses a GET DIAGNOSTICS statement in a dynamic compound statement"""
		# GET DIAGNOSTICS already matched
		if self._match('EXCEPTION'):
			self._expect((TT.NUMBER, 1))
			while True:
				self._expect_sequence([TT.IDENTIFIER, '='])
				self._expect_one_of(['MESSAGE_TEXT', 'DB2_TOKEN_STRING'])
				if not self._match(','):
					break
		else:
			self._expect_sequence([TT.IDENTIFIER, '='])
			self._expect(['ROW_COUNT', 'DB2_RETURN_STATUS'])

	def _parse_goto_statement(self):
		"""Parses a GOTO statement in a procedure"""
		# GOTO already matched
		self._expect(TT.IDENTIFIER)

	def _parse_grant_statement(self):
		"""Parses a GRANT statement"""
		# GRANT already matched
		self._parse_grant_revoke(grant=True)

	def _parse_if_statement(self):
		"""Parses an IF-conditional in a dynamic compound statement"""
		# IF already matched
		t = 'IF'
		while True:
			if t in ('IF', 'ELSEIF'):
				self._parse_search_condition(newlines=False)
				self._expect('THEN')
				self._indent()
				while True:
					self._parse_compiled_statement()
					self._expect((TT.TERMINATOR, ';'))
					t = self._match_one_of(['ELSEIF', 'ELSE', 'END'])
					if t:
						self._outdent(-1)
						t = t.value
						break
					else:
						self._newline()
			elif t == 'ELSE':
				self._indent()
				while True:
					self._parse_compiled_statement()
					self._expect((TT.TERMINATOR, ';'))
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
		self._match(TT.IDENTIFIER)

	def _parse_leave_statement(self):
		"""Parses a LEAVE statement within a loop"""
		# LEAVE already matched
		self._match(TT.IDENTIFIER)

	def _parse_lock_table_statement(self):
		"""Parses a LOCK TABLE statement"""
		# LOCK TABLE already matched
		self._parse_table_name()
		self._expect('IN')
		self._expect_one_of(['SHARE', 'EXCLUSIVE'])
		self._expect('MODE')

	def _parse_loop_statement(self, label=None):
		"""Parses a LOOP-loop in a procedure"""
		# LOOP already matched
		self._indent()
		while True:
			self._parse_compiled_statement()
			self._expect((TT.TERMINATOR, ';'))
			if self._match('END'):
				self._outdent(-1)
				break
			else:
				self._newline()
		self._expect('LOOP')
		if label:
			self._match((TT.IDENTIFIER, label))

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
		self._expect(TT.IDENTIFIER)
		if self._match('('):
			if not self._match(')'):
				self._parse_expression_list()
				self._expect(')')
		if self._match('USING'):
			self._parse_expression_list()

	def _parse_prepare_statement(self):
		"""Parses a PREPARE statement"""
		# PREPARE already matched
		self._expect(TT.IDENTIFIER)
		if self._match('OUTPUT'):
			self._expect('INTO')
			self._expect(TT.IDENTIFIER)
		elif self._match('INTO'):
			self._expect(TT.IDENTIFIER)
		if self._match('INPUT'):
			self._expect('INTO')
			self._expect(TT.IDENTIFIER)
		self._expect('FROM')
		self._parse_expression()

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
		self._expect(TT.IDENTIFIER)

	def _parse_rename_tablespace_statement(self):
		"""Parses a RENAME TABLESPACE statement"""
		# RENAME TABLESPACE already matched
		self._expect_sequence([TT.IDENTIFIER, 'TO', TT.IDENTIFIER])

	def _parse_rename_statement(self):
		"""Parses a RENAME statement"""
		# RENAME already matched
		if self._match('INDEX'):
			self._parse_index_name()
		else:
			self._match('TABLE')
			self._parse_table_name()
		self._expect_sequence(['TO', TT.IDENTIFIER])

	def _parse_repeat_statement(self, label=None):
		"""Parses a REPEAT-loop in a procedure"""
		# REPEAT already matched
		self._indent()
		while True:
			self._parse_compiled_statement()
			self._expect((TT.TERMINATOR, ';'))
			self._newline()
			if self._match('UNTIL'):
				break
			else:
				self._newline()
		self._outdent(-1)
		self._parse_search_condition()
		self._expect_sequence(['END', 'REPEAT'])
		if label:
			self._match((TT.IDENTIFIER, label))

	def _parse_resignal_statement(self):
		"""Parses a RESIGNAL statement in a dynamic compound statement"""
		# SIGNAL already matched
		if self._match('SQLSTATE'):
			self._match('VALUE')
			self._expect_one_of([TT.IDENTIFIER, TT.STRING])
		else:
			if not self._match(TT.IDENTIFIER):
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
			self._save_state()
			try:
				self._parse_expression()
			except ParseError:
				self._restore_state()
				# If parsing an expression fails, assume it's a parameter-less
				# RETURN (as can be used in a procedure)
			else:
				self._forget_state()
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
			self._match(TT.IDENTIFIER)

	def _parse_savepoint_statement(self):
		"""Parses a SAVEPOINT statement"""
		# SAVEPOINT already matched
		self._expect(TT.IDENTIFIER)
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
				t = t.value
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
				self._expect_sequence(['FOR', TT.NUMBER])
				self._expect_one_of(['ROW', 'ROWS'])
			elif t == 'WITH':
				if self._expect_one_of(['RR', 'RS', 'CS', 'UR']).value in ('RR', 'RS'):
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
				if self._expect_one_of(['DEFERRED', 'IMMEDIATE']).value == 'IMMEDIATE':
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
					t = t.value
					valid.remove(t)
				else:
					break
				if t == 'INCREMENTAL':
					valid.remove('NOT')
				elif t == (TT.KEYWORD, 'NOT'):
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
			self._match(TT.NUMBER)
		elif self._match('NOT'):
			self._expect('WAIT')
		elif self._match('NULL'):
			pass
		elif self._match(TT.NUMBER):
			pass
		else:
			self._expected_one_of(['WAIT', 'NOT', 'NULL', TT.NUMBER])

	def _parse_set_path_statement(self):
		"""Parses a SET PATH statement"""
		# SET [CURRENT] PATH already matched
		self._match('=')
		while True:
			if self._match_sequence([(TT.REGISTER, 'SYSTEM'), (TT.REGISTER, 'PATH')]):
				pass
			elif self._match((TT.REGISTER, 'USER')):
				pass
			elif self._match((TT.REGISTER, 'CURRENT')):
				self._match((TT.REGISTER, 'PACKAGE'))
				self._expect((TT.REGISTER, 'PATH'))
			elif self._match((TT.REGISTER, 'CURRENT_PATH')):
				pass
			else:
				self._expect_one_of([TT.IDENTIFIER, TT.STRING])
			if not self._match(','):
				break

	def _parse_set_schema_statement(self):
		"""Parses a SET SCHEMA statement"""
		# SET [CURRENT] SCHEMA already matched
		self._match('=')
		t = self._expect_one_of([
			(TT.REGISTER, 'USER'),
			(TT.REGISTER, 'SESSION_USER'),
			(TT.REGISTER, 'SYSTEM_USER'),
			(TT.REGISTER, 'CURRENT_USER'),
			TT.IDENTIFIER,
			TT.STRING,
		])
		if t.type in (TT.IDENTIFIER, TT.STRING):
			self.current_schema = t.value

	def _parse_set_session_auth_statement(self):
		"""Parses a SET SESSION AUTHORIZATION statement"""
		# SET SESSION AUTHORIZATION already matched
		self._match('=')
		self._expect_one_of([
			(TT.REGISTER, 'USER'),
			(TT.REGISTER, 'SYSTEM_USER'),
			(TT.REGISTER, 'CURRENT_USER'),
			TT.IDENTIFIER,
			TT.STRING,
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
					TT.STRING,
				])
			if self._match('DEGREE'):
				self._match('=')
				self._expect(TT.STRING)
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
				self._expect_one_of(['ANY', TT.NUMBER])
			elif self._match_sequence(['IMPLICIT', 'XMLPARSE', 'OPTION']):
				self._match('=')
				self._expect(TT.STRING)
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
				if not self._match(TT.STRING) and not self._match('NULL'):
					self._parse_subschema_name()
			elif self._match_sequence(['QUERY', 'OPTIMIZATION']):
				self._match('=')
				self._expect(TT.NUMBER)
			elif self._match_sequence(['REFRESH', 'AGE']):
				self._match('=')
				self._expect_one_of(['ANY', TT.NUMBER])
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
			self._expect(TT.IDENTIFIER)
		elif self._match('ISOLATION'):
			self._parse_set_isolation_statement()
		elif self._match_sequence(['LOCK', 'TIMEOUT']):
			self._parse_set_lock_timeout_statement()
		elif self._match_sequence(['ENCRYPTION', 'PASSWORD']):
			self._match('=')
			self._expect(TT.STRING)
		elif self._match_sequence(['EVENT', 'MONITOR']):
			self._expect(TT.IDENTIFIER)
			self._expect('STATE')
			self._match('=')
			self._expect(TT.NUMBER)
		elif self._match('PASSTHRU'):
			self._expect_one_of(['RESET', TT.IDENTIFIER])
		elif self._match('PATH'):
			self._parse_set_path_statement()
		elif self._match('ROLE'):
			self._match('=')
			self._expect(TT.IDENTIFIER)
		elif self._match('CURRENT_PATH'):
			self._parse_set_path_statement()
		elif self._match('SCHEMA'):
			self._parse_set_schema_statement()
		elif self._match_sequence(['SERVER', 'OPTION']):
			self._expect_sequence([TT.IDENTIFIER, 'TO', TT.STRING, 'FOR', 'SERVER', TT.IDENTIFIER])
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
			self._expect_one_of([TT.IDENTIFIER, TT.STRING])
		else:
			self._expect(TT.IDENTIFIER)
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
			self._expect(TT.IDENTIFIER)
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
			self._expect(TT.IDENTIFIER)
		else:
			self._expect_one_of([
				(TT.REGISTER, 'USER'),
				(TT.REGISTER, 'SESSION_USER'),
				(TT.REGISTER, 'SYSTEM_USER'),
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

	def _parse_while_statement(self, label=None):
		"""Parses a WHILE-loop in a dynamic compound statement"""
		# WHILE already matched
		self._parse_search_condition(newlines=False)
		self._newline()
		self._expect('DO')
		self._indent()
		while True:
			self._parse_compiled_statement()
			self._expect((TT.TERMINATOR, ';'))
			if self._match('END'):
				self._outdent(-1)
				break
			else:
				self._newline()
		self._expect('WHILE')
		if label:
			self._match((TT.IDENTIFIER, label))

	# COMPOUND STATEMENTS ####################################################

	def _parse_compiled_statement(self):
		"""Parses a procedure statement within a procedure body"""
		# XXX Should PREPARE be supported here?
		try:
			label = self._expect(TT.LABEL).value
			self._newline()
		except ParseError:
			label = None
		# Procedure specific statements
		if self._match('ALLOCATE'):
			self._parse_allocate_cursor_statement()
		elif self._match('ASSOCIATE'):
			self._parse_associate_locators_statement()
		elif self._match('BEGIN'):
			self._parse_compiled_compound_statement(label=label)
		elif self._match('CASE'):
			self._parse_case_statement()
		elif self._match('CLOSE'):
			self._parse_close_statement()
		elif self._match_sequence(['EXECUTE', 'IMMEDIATE']):
			self._parse_execute_immediate_statement()
		elif self._match('EXECUTE'):
			self._parse_execute_statement()
		elif self._match('FETCH'):
			self._parse_fetch_statement()
		elif self._match('GOTO'):
			self._parse_goto_statement()
		elif self._match('LOOP'):
			self._parse_loop_statement(label=label)
		elif self._match('PREPARE'):
			self._parse_prepare_statement()
		elif self._match('OPEN'):
			self._parse_open_statement()
		elif self._match('REPEAT'):
			self._parse_repeat_statement(label=label)
		# Dynamic compound specific statements
		elif self._match('FOR'):
			self._parse_for_statement(label=label)
		elif self._match_sequence(['GET', 'DIAGNOSTICS']):
			self._parse_get_diagnostics_statement()
		elif self._match('IF'):
			self._parse_if_statement()
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
			self._parse_while_statement(label=label)
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
			self._match_sequence(['OR', 'REPLACE'])
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

	def _parse_compiled_compound_statement(self, label=None):
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
					self._expect_sequence(['(', (TT.NUMBER, 5), ')'], prespace=False)
					self._match_sequence(['DEFAULT', TT.STRING])
				elif self._match('SQLCODE'):
					reraise = True
					self._expect_one_of(['INT', 'INTEGER'])
					self._match_sequence(['DEFAULT', TT.NUMBER])
				else:
					count = len(self._parse_ident_list())
					if count == 1 and self._match('CONDITION'):
						reraise = True
						self._expect('FOR')
						if self._match('SQLSTATE'):
							self._match('VALUE')
						self._expect(TT.STRING)
					else:
						self._parse_datatype()
						if self._match('DEFAULT'):
							reraise = True
							self._parse_expression()
				self._expect((TT.TERMINATOR, ';'))
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
				self._expect((TT.TERMINATOR, ';'))
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
				self._expect_sequence(['DECLARE', TT.IDENTIFIER, 'CURSOR'])
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
					self._expect(TT.IDENTIFIER)
				else:
					self._forget_state()
				self._expect((TT.TERMINATOR, ';'))
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
				self._save_state()
				try:
					while True:
						if self._match('NOT'):
							self._expect('FOUND')
						else:
							self._expect_one_of(['NOT', 'SQLEXCEPTION', 'SQLWARNING'])
						if not self._match(','):
							break
				except ParseError:
					self._restore_state()
					while True:
						if self._match('SQLSTATE'):
							self._match('VALUE')
							self._expect(TT.STRING)
						else:
							self._expect(TT.IDENTIFIER)
						if not self._match(','):
							break
				else:
					self._forget_state()
				self._parse_compiled_statement()
				self._expect((TT.TERMINATOR, ';'))
				self._newline()
			except ParseError:
				self._restore_state()
				if reraise: raise
				break
			else:
				self._forget_state()
		# Parse procedure statements
		while not self._match('END'):
			self._parse_compiled_statement()
			self._expect((TT.TERMINATOR, ';'))
			self._newline()
		self._outdent(-1)
		if label:
			self._match((TT.IDENTIFIER, label))

	def _parse_statement(self):
		"""Parses a top-level statement in an SQL script"""
		# XXX CREATE EVENT MONITOR
		# If we're reformatting WHITESPACE, add a blank WHITESPACE token to the
		# output - this will suppress leading whitespace in front of the first
		# word of the statement
		self._output.append(Token(TT.WHITESPACE, None, '', 0, 0))
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
			elif self._match('MODULE'):
				self._parse_alter_module_statement()
			else:
				self._expected_one_of([
					'AUDIT',
					'BUFFERPOOL',
					'DATABASE',
					'FUNCTION',
					'HISTOGRAM',
					'MODULE',
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
			self._parse_compiled_compound_statement()
		elif self._match('CALL'):
			self._parse_call_statement()
		elif self._match_sequence(['COMMENT', 'ON']):
			self._parse_comment_statement()
		elif self._match('COMMIT'):
			self._parse_commit_statement()
		elif self._match('CREATE'):
			self._match_sequence(['OR', 'REPLACE'])
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
			elif self._match('TYPE'):
				self._parse_create_type_statement()
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
			elif self._match('MODULE'):
				self._parse_create_module_statement()
			else:
				tbspacetype = self._match_one_of([
					'REGULAR',
					'LONG',
					'LARGE',
					'TEMPORARY',
					'USER',
					'SYSTEM',
				])
				if tbspacetype:
					tbspacetype = tbspacetype.value
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
						'MODULE',
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
		if self._token().type in (TT.COMMENT, TT.WHITESPACE):
			self._index += 1
		self._parse_function_name()
		# Parenthesized parameter list is mandatory
		self._expect('(', prespace=False)
		if not self._match(')'):
			while True:
				self._match_one_of(['IN', 'OUT', 'INOUT'])
				self._save_state()
				try:
					self._expect(TT.IDENTIFIER)
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

Connection = namedtuple('Connection', ('instance', 'database', 'username', 'password'))

class DB2ZOSScriptParser(DB2ZOSParser):
	"""Parser which handles the DB2 UDB CLP dialect.

	This class inherits from the DB2 SQL language parser and as such is capable
	of parsing all the statements that the parent class is capable of. In
	addition, it adds the ability to parse the non-SQL CLP commands (like
	IMPORT, EXPORT, LOAD, CREATE DATABASE, etc).
	"""

	def __init__(self):
		super(DB2ZOSScriptParser, self).__init__()
		self.connections = []
		self.produces = []
		self.consumes = []
		self.current_user = None
		self.current_instance = None
		self.current_connection = None

	def _match_clp_string(self, password=False):
		"""Attempts to match the current tokens as a CLP-style string.

		The _match_clp_string() method is used to match a CLP-style string.
		The "real" CLP has a fundamentally different style of parser to the
		DB2 SQL parser, and includes several behaviours that are difficult
		to replicate in this parser (which was primarily targetted at the
		DB2 SQL dialect). One of these is the CLP's habit of treating an
		unquoted run of non-whitespace tokens as a string, or allowing a
		quoted identifier to be treated as a string.

		When this method is called it will return a STRING token consisting
		of the content of the aforementioned tokens (or None if a CLP-style
		string is not found in the source at the current position).
		"""
		token = self._token()
		if token.type == TT.STRING:
			# STRINGs are treated verbatim
			self._index += 1
		elif token.type == TT.IDENTIFIER and token.source[0] == '"':
			# Double quoted identifier are converted to STRING tokens
			token = Token(TT.STRING, token.value, quote_str(token.value, "'"), token.line, token.column)
			self._index += 1
		elif not token.type in (TT.TERMINATOR, TT.EOF):
			# Otherwise, any run of non-whitepace tokens is converted to a
			# single STRING token
			start = self._index
			self._index += 1
			while True:
				token = self._token()
				if token.type == TT.STRING:
					raise ParseError(self._tokens, token, "Quotes (') not permitted in identifier")
				if token.type == TT.IDENTIFIER and token.source[0] == '"':
					raise ParseError(self._tokens, token, 'Quotes (") not permitted in identifier')
				if token.type in (TT.WHITESPACE, TT.COMMENT, TT.TERMINATOR, TT.EOF):
					break
				self._index += 1
			content = ''.join([token.source for token in self._tokens[start:self._index]])
			token = Token(TT.STRING, content, quote_str(content, "'"), self._tokens[start].line, self._tokens[start].column)
		else:
			token = None
		if token:
			if not (self._output and self._output[-1].type in (TT.INDENT, TT.WHITESPACE)):
				self._output.append(Token(TT.WHITESPACE, None, ' ', 0, 0))
			if password:
				token = Token(TT.PASSWORD, token.value, token.source, token.line, token.column)
			self._output.append(token)
		# Skip WHITESPACE and COMMENTS
		while self._token().type in (TT.COMMENT, TT.WHITESPACE):
			if self._token().type == TT.COMMENT or TT.WHITESPACE not in self.reformat:
				self._output.append(self._token())
			self._index += 1
		return token

	def _expect_clp_string(self, password=False):
		"""Matches the current tokens as a CLP-style string, or raises an error.

		See _match_clp_string() above for details of the algorithm.
		"""
		result = self._match_clp_string(password)
		if not result:
			raise ParseExpectedOneOfError(self._tokens, self._token(), [TT.PASSWORD if password else TT.STRING])
		return result

	# PATTERNS ###############################################################

	def _parse_clp_string_list(self):
		"""Parses a comma separated list of strings.

		This is a common pattern in CLP, for example within the LOBS TO clause of
		the EXPORT command. The method returns the list of strings found.
		"""
		result = []
		while True:
			result.append(self._expect_clp_string().value)
			if not self._match(','):
				break
		return result

	def _parse_number_list(self):
		"""Parses a comma separated list of number.

		This is a common pattern in CLP, for example within the METHOD clause of
		the IMPORT or LOAD commands. The method returns the list of numbers
		found.
		"""
		result = []
		while True:
			result.append(self._expect(TT.NUMBER).value)
			if not self._match(','):
				break
		return result

	def _parse_login(self, optional=True, allowchange=False):
		"""Parses a set of login credentials"""
		username = None
		password = None
		if self._match('USER'):
			username = self._expect_clp_string().value
			if self._match('USING'):
				password = self._expect_clp_string(password=True).value
				if allowchange:
					if self._match('NEW'):
						password = self._expect_clp_string(password=True).value
						self._expect('CONFIRM')
						self._expect_clp_string(password=True)
					else:
						self._match_sequence(['CHANGE', 'PASSWORD'])
		elif not optional:
			self._expected('USER')
		return (username, password)

	# COMMANDS ###############################################################

	def _parse_activate_database_command(self):
		"""Parses an ACTIVATE DATABASE command"""
		# ACTIVATE [DATABASE|DB] already matched
		self._expect_clp_string()
		self._parse_login(optional=True, allowchange=False)

	def _parse_add_contact_command(self):
		"""Parses an ADD CONTACT command"""
		# ADD CONTACT already matched
		self._expect_clp_string()
		self._expect('TYPE')
		if self._expect_one_of(['EMAIL', 'PAGE']).value == 'PAGE':
			if self._match_sequence(['MAXIMUM', 'PAGE', 'LENGTH']) or self._match_sequence(['MAX', 'LEN']):
				self._expect(TT.NUMBER)
		self._expect('ADDRESS')
		self._expect_clp_string()
		if self._match('DESCRIPTION'):
			self._expect_clp_string()

	def _parse_add_contactgroup_command(self):
		"""Parses an ADD CONTACTGROUP command"""
		# ADD CONTACTGROUP already matched
		self._expect_clp_string()
		while True:
			self._expect_one_of(['CONTACT', 'GROUP'])
			self._expect_clp_string()
			if not self_match(','):
				break
		if self._match('DESCRIPTION'):
			self._expect_clp_string()

	def _parse_add_dbpartitionnum_command(self):
		"""Parses an ADD DBPARTITIONNUM command"""
		# ADD DBPARTITIONNUM already matched
		if self._match('LIKE'):
			self._expect_one_of(['DBPARTITIONNUM', 'NODE'])
			self._expect(TT.NUMBER)
		elif self._match('WITHOUT'):
			self._expect('TABLESPACES')

	def _parse_add_xmlschema_document_command(self):
		"""Parses an ADD XMLSCHEMA DOCUMENT command"""
		# ADD XMLSCHEMA DOCUMENT already matched
		self._expect('TO')
		self._parse_subschema_name()
		self._expect('ADD')
		self._expect_clp_string()
		self._expect('FROM')
		self._expect_clp_string()
		if self._match('WITH'):
			self._expect_clp_string()
		if self._match('COMPLETE'):
			if self._match('WITH'):
				self._expect_clp_string()
			self._match_sequence(['ENABLE', 'DECOMPOSITION'])

	def _parse_archive_log_command(self):
		"""Parses an ARCHIVE LOG command"""
		# ARCHIVE LOG already matched
		self._expect('FOR')
		self._expect_one_of(['DATABASE', 'DB'])
		self._expect_clp_string()
		if self._match('USER'):
			self._expect_clp_string()
			if self._match('USING'):
				self._expect_clp_string()
		self._parse_db_partitions_clause()

	def _parse_attach_command(self):
		"""Parses an ATTACH command"""
		# ATTACH already matched
		if self._match('TO'):
			self._expect_clp_string()
		self._parse_login(optional=True, allowchange=True)

	def _parse_autoconfigure_command(self):
		"""Parses an AUTOCONFIGURE command"""
		# AUTOCONFIGURE already matched
		if self._match('USING'):
			while True:
				self._expect(TT.IDENTIFIER)
				self._expect_one_of([TT.NUMBER, TT.STRING, TT.IDENTIFIER])
				if self._match('APPLY'):
					break
		else:
			self._expect('APPLY')
		if self._match('DB'):
			if self._match('AND'):
				self._expect('DBM')
			else:
				self._expect('ONLY')
		elif self._match('NONE'):
			pass
		else:
			self._expected_one_of(['DB', 'NONE'])
		self._match_sequence(['ON', 'CURRENT', 'NODE'])

	def _parse_backup_command(self):
		"""Parses a BACKUP DB command"""
		# BACKUP [DATABASE|DB] already matched
		self._expect_clp_string()
		self._parse_login(optional=True, allowchange=False)
		self._parse_db_partitions_clause()
		if self._match('TABLESPACE'):
			self._expect('(')
			self._parse_ident_list()
			self._expect(')')
		self._match('ONLINE')
		if self._match('INCREMENTAL'):
			self._match('DELTA')
		if self._match('USE'):
			if self._match('SNAPSHOT'):
				if self._match('LIBRARY'):
					self._expect_clp_string()
			elif self._match_one_of(['TSM', 'XBSA']):
				if self._match('OPEN'):
					self._expect(TT.NUMBER)
					self._expect('SESSIONS')
			if self._match('OPTIONS'):
				self._expect_clp_string()
				# XXX Add support for @filename response file
		elif self._match('TO'):
			self._parse_clp_string_list()
		elif self._match('LOAD'):
			self._expect_clp_string()
			if self._match('OPEN'):
				self._expect(TT.NUMBER)
				self._expect('SESSIONS')
			if self._match('OPTIONS'):
				self._expect_clp_string()
				# XXX Add support for @filename response file
		self._match('DEDUP_DEVICE')
		if self._match('WITH'):
			self._expect(TT.NUMBER)
			self._expect('BUFFERS')
		if self._match('BUFFER'):
			self._expect(TT.NUMBER)
		if self._match('PARALLELISM'):
			self._expect(TT.NUMBER)
		if self._match('COMPRESS'):
			if self._match('COMPRLIB'):
				self._expect_clp_string()
				self._match('EXCLUDE')
			if self._match('COMPROPTS'):
				self._expect_clp_string()
		if self._match('UTIL_IMPACT_PRIORITY'):
			self._match(TT.NUMBER)
		if self._match_one_of(['EXCLUDE', 'INCLUDE']):
			self._expect('LOGS')
		if self._match('WITHOUT'):
			self._expect('PROMPTING')

	# XXX Add support for BIND command

	def _parse_catalog_command(self):
		"""Parses a CATALOG command"""
		# CATALOG already matched
		if self._match_one_of(['USER', 'SYSTEM']):
			self._expect('ODBC')
			if self._match_sequence(['DATA', 'SOURCE']):
				self._expect_clp_string()
			else:
				self._expect_sequence(['ALL', 'DATA', 'SOURCES'])
		elif self._match('ODBC'):
			if self._match_sequence(['DATA', 'SOURCE']):
				self._expect_clp_string()
			else:
				self._expect_sequence(['ALL', 'DATA', 'SOURCES'])
		elif self._match_one_of(['DATABASE', 'DB']):
			self._expect_clp_string()
			if self._match('AS'):
				self._expect_clp_string()
			if self._match('ON'):
				self._expect_clp_string()
			elif self._match_sequence(['AT', 'NODE']):
				self._expect_clp_string()
			if self._match('AUTHENTICATION'):
				if self._match_sequence(['KERBEROS', 'TARGET', 'PRINCIPAL']):
					self._expect_clp_string()
				else:
					self._expect_one_of([
						'SERVER',
						'CLIENT',
						'SERVER_ENCRYPT',
						'SERVER_ENCRYPT_AES',
						'KERBEROS',
						'DATA_ENCRYPT',
						'DATA_ENCRYPT_CMP',
						'GSSPLUGIN',
						'DCS',
						'DCS_ENCRYPT',
					])
			if self._match('WITH'):
				self._expect_clp_string()
		elif self._match('DCS'):
			self._expect_one_of(['DATABASE', 'DB'])
			self._expect_clp_string()
			if self._match('AS'):
				self._expect_clp_string()
			if self._match('AR'):
				self._expect_clp_string()
			if self._match('PARMS'):
				self._expect_clp_string()
			if self._match('WITH'):
				self._expect_clp_string()
		elif self._match('LDAP'):
			if self._match_one_of(['DATABASE', 'DB']):
				self._expect_clp_string()
				if self._match('AS'):
					self._expect_clp_string()
				if self._match_sequence(['AT', 'NODE']):
					self._expect_clp_string()
				if self._match('GWNODE'):
					self._expect_clp_string()
				if self._match('PARMS'):
					self._expect_clp_string()
				if self._match('AR'):
					self._expect_clp_string()
				if self._match_sequence(['KERBEROS', 'TARGET', 'PRINCIPAL']):
					self._expect_clp_string()
				else:
					self._expect_one_of([
						'SERVER',
						'CLIENT',
						'SERVER_ENCRYPT',
						'SERVER_ENCRYPT_AES',
						'KERBEROS',
						'DCS',
						'DCS_ENCRYPT',
						'DATA_ENCRYPT',
						'GSSPLUGIN',
					])
				if self._match('WITH'):
					self._expect_clp_string()
			elif self._match('NODE'):
				self._expect_clp_string()
				self._expect('AS')
				self._expect_clp_string()
			else:
				self._expected_one_of(['DATABASE', 'DB', 'NODE'])
			self._parse_login(optional=True, allowchange=False)
		else:
			self._match('ADMIN')
			if self._match_sequence(['LOCAL', 'NODE']):
				self._expect_clp_string()
				if self._match('INSTANCE'):
					self._expect_clp_string()
				if self._match('SYSTEM'):
					self._expect_clp_string()
				if self._match('OSTYPE'):
					self._expect(TT.IDENTIFIER)
				if self._match('WITH'):
					self._expect_clp_string()
			elif self._match_sequence(['NPIPE', 'NODE']):
				self._expect_clp_string()
				self._expect('REMOTE')
				self._expect_clp_string()
				self._expect('INSTANCE')
				self._expect_clp_string()
				if self._match('SYSTEM'):
					self._expect_clp_string()
				if self._match('OSTYPE'):
					self._expect(TT.IDENTIFIER)
				if self._match('WITH'):
					self._expect_clp_string()
			elif self._match_sequence(['NETBIOS', 'NODE']):
				self._expect_clp_string()
				self._expect('REMOTE')
				self._expect_clp_string()
				self._expect('ADAPTER')
				self._expect(TT.NUMBER)
				if self._match('REMOTE_INSTANCE'):
					self._expect_clp_string()
				if self._match('SYSTEM'):
					self._expect_clp_string()
				if self._match('OSTYPE'):
					self._expect(TT.IDENTIFIER)
				if self._match('WITH'):
					self._expect_clp_string()
			elif self._match_one_of(['TCPIP', 'TCPIP4', 'TCPIP6']):
				self._expect('NODE')
				self._expect_clp_string()
				self._expect('REMOTE')
				self._expect_clp_string()
				self._expect('SERVER')
				self._expect_clp_string()
				if self._match('SECURITY'):
					self._match_one_of(['SOCKS', 'SSL'])
				if self._match('REMOTE_INSTANCE'):
					self._expect_clp_string()
				if self._match('SYSTEM'):
					self._expect_clp_string()
				if self._match('OSTYPE'):
					self._expect(TT.IDENTIFIER)
				if self._match('WITH'):
					self._expect_clp_string()
			else:
				self._expected_one_of([
					'LOCAL',
					'NPIPE',
					'NETBIOS',
					'TCPIP',
					'TCPIP4',
					'TCPIP6',
				])

	def _parse_connect_command(self):
		"""Parses a CONNECT command"""
		# CONNECT already matched
		if self._expect_one_of(['TO', 'RESET']).value == 'RESET':
			self.current_connection = None
		else:
			database = self._expect_clp_string().value
			if self._match('IN'):
				if self._expect_one_of(['SHARE', 'EXCLUSIVE']).value == 'EXCLUSIVE':
					self._expect('MODE')
					if self._match('ON'):
						self._expect('SINGLE')
						self._expect_one_of(['DBPARTITIONNUM', 'NODE'])
				else:
					self._expect('MODE')
			(username, password) = self._parse_login(optional=True, allowchange=True)
			self.current_connection = Connection(self.current_instance, database, username, password)
			self.connections.append(self.current_connection)

	def _parse_create_database_command(self):
		"""Parses a CREATE DATABASE command"""

		def parse_tablespace_definition():
			self._expect('MANAGED')
			self._expect('BY')
			if self._match('SYSTEM'):
				self._expect('USING')
				self._parse_system_container_clause()
			elif self._match('DATABASE'):
				self._expect('USING')
				self._parse_database_container_clause()
			elif self._match('AUTOMATIC'):
				self._expect('STORAGE')
			if self._match('EXTENTSIZE'):
				self._expect(TT.NUMBER)
				self._match_one_of(['K', 'M'])
			if self._match('PREFETCHSIZE'):
				self._expect(TT.NUMBER)
				self._match_one_of(['K', 'M', 'G'])
			if self._match('OVERHEAD'):
				self._expect(TT.NUMBER)
			if self._match('TRANSFERRATE'):
				self._expect(TT.NUMBER)
			if self._match('NO'):
				self._expect_sequence(['FILE', 'SYSTEM', 'CACHING'])
			elif self._match('FILE'):
				self._expect_sequence(['SYSTEM', 'CACHING'])
			self._parse_tablespace_size_attributes()

		# CREATE [DATABASE|DB] already matched
		self._expect_clp_string()
		# XXX Implement AT DBPARTITIONNUM? (not for general use, etc.)
		if self._match('AUTOMATIC'):
			self._expect('STORAGE')
			self._expect_one_of(['NO', 'YES'])
		if self._match('ON'):
			self._parse_clp_string_list()
			if self._match('DBPATH'):
				self._expect('ON')
				self._expect_clp_string()
		if self._match('ALIAS'):
			self._expect_clp_string()
		if self._match('USING'):
			self._expect('CODESET')
			self._expect_clp_string()
			if self._match('TERRITORY'):
				self._expect_clp_string()
		if self._match('COLLATE'):
			self._expect('USING')
			self._expect(TT.IDENTIFIER)
		if self._match('PAGESIZE'):
			self._expect(TT.NUMBER)
			self._match('K')
		if self._match('NUMSEGS'):
			self._expect(TT.NUMBER)
		if self._match('DFT_EXTENT_SZ'):
			self._expect(TT.NUMBER)
		self._match('RESTRICTIVE')
		if self._match('CATALOG'):
			self._expect('TABLESPACE')
			parse_tablespace_definition()
		if self._match('USER'):
			self._expect('TABLESPACE')
			parse_tablespace_definition()
		if self._match('TEMPORARY'):
			self._expect('TABLESPACE')
			parse_tablespace_definition()
		if self._match('WITH'):
			self._expect_clp_string()
		if self._match('AUTOCONFIGURE'):
			self._parse_autoconfigure_command()

	def _parse_create_tools_catalog_command(self):
		"""Parses a CREATE TOOLS CATALOG command"""
		# CREATE TOOLS CATALOG already matched
		self._expect_clp_string()
		if self._match('CREATE'):
			self._expect('NEW')
			self._expect('DATABASE')
			self._expect_clp_string()
		elif self._match('USE'):
			self._expect('EXISTING')
			if self._match('TABLESPACE'):
				self._expect(TT.IDENTIFIER)
			self._expect('DATABASE')
			self._expect_clp_string()
		self._match('FORCE')
		if self._match('KEEP'):
			self._expect('INACTIVE')

	def _parse_deactivate_database_command(self):
		"""Parses a DEACTIVATE DATABASE command"""
		# DEACTIVATE [DATABASE|DB] already matched
		self._expect_clp_string()
		self._parse_login(optional=True, allowchange=False)

	def _parse_decompose_xml_document(self):
		"""Parses a DECOMPOSE XML DOCUMENT command"""
		# DECOMPOSE XML DOCUMENT already matched
		self._expect_clp_string()
		self._expect('XMLSCHEMA')
		self._parse_subschema_name()
		self._match('VALIDATE')

	def _parse_decompose_xml_documents(self):
		"""Parses a DECOMPOSE XML DOCUMENTS command"""
		# DECOMPOSE XML DOCUMENTS already matched
		self._expect('IN')
		self._parse_select_statement()
		self._expect('XMLSCHEMA')
		self._parse_subschema_name()
		self._match('VALIDATE')
		if self._match('ALLOW'):
			self._match('NO')
			self._expect('ACCESS')
		if self._match('COMMITCOUNT'):
			self._expect(TT.NUMBER)
		self._match_sequence(['CONTINUE', 'ON', 'ERROR'])
		if self._match('MESSAGES'):
			self._expect_clp_string()

	def _parse_deregister_command(self):
		"""Parses a DEREGISTER command"""
		# DEREGISTER already matched
		self._match_sequence(['DB2', 'SERVER'])
		self._match('IN')
		self._expect_sequence(['LDAP', 'NODE', TT.IDENTIFIER])
		self._parse_login(optional=True, allowchange=False)

	def _parse_describe_command(self):
		"""Parses a DESCRIBE command"""
		# DESCRIBE already matched
		table = True
		if self._match('TABLE'):
			pass
		elif self._match_sequence(['INDEXES', 'FOR', 'TABLE']):
			pass
		elif self._match_sequence(['RELATIONAL', 'DATA']) or self._match_sequence(['XML', 'DATA']) or self._match_sequence(['TEXT', 'SEARCH']):
			self._expect_sequence(['INDEXES', 'FOR', 'TABLE'])
		elif self._match_sequence(['DATA', 'PARTITIONS', 'FOR', 'TABLE']):
			pass
		else:
			table = False
		if table:
			self._parse_table_name()
			self._match_sequence(['SHOW', 'DETAIL'])
		else:
			self._match('OUTPUT')
			self._save_state()
			try:
				self._parse_select_statement()
			except ParseError:
				self._restore_state()
				self._parse_call_statement()
			else:
				self._forget_state()
		# XXX Add support for XQUERY?

	def _parse_detach_command(self):
		"""Parses a DETACH command"""
		# DETACH already matched
		pass

	def _parse_disconnect_command(self):
		"""Parses a DISCONNECT command"""
		# DISCONNECT already matched
		if self._match('ALL'):
			self._match('SQL')
			self.current_connection = None
		elif self._match('CURRENT'):
			self.current_connection = None
		else:
			t = self._expect_clp_string()
			if isinstance(self.current_connection.database, basestring) and s.lower() == t.value.lower():
				self.current_connection = None

	def _parse_drop_contact_command(self):
		"""Parses a DROP CONTACT command"""
		# DROP CONTACT already matched
		self._expect_clp_string()

	def _parse_drop_contactgroup_command(self):
		"""Parses a DROP CONTACTGROUP command"""
		# DROP CONTACTGROUP already matched
		self._expect_clp_string()

	def _parse_drop_database_command(self):
		"""Parses a DROP DATABASE command"""
		# DROP [DATABASE|DB] already matched
		self._expect_clp_string()
		if self._match('AT'):
			self._expect_one_of(['DBPARTITIONNUM', 'NODE'])

	def _parse_drop_dbpartitionnum_verify_command(self):
		"""Parses a DROP DBPARTITIONNUM VERIFY command"""
		# DROP DBPARTITIONNUM VERIFY already matched
		pass

	def _parse_drop_tools_catalog_command(self):
		"""Parses a DROP TOOLS CATALOG command"""
		# DROP TOOLS CATALOG already matched
		self._expect_clp_string()
		self._expect('IN')
		self._expect('DATABASE')
		self._expect_clp_string()
		self._match('FORCE')

	def _parse_echo_command(self):
		"""Parses an ECHO command"""
		# ECHO already matched
		self._match_clp_string()

	def _parse_export_command(self):
		"""Parses a EXPORT command"""
		# EXPORT already matched
		self._expect('TO')
		self.produces.append((self._expect_clp_string().value, self.current_connection))
		self._expect('OF')
		self._expect_one_of(['DEL', 'IXF', 'WSF'])
		if self._match('LOBS'):
			self._expect('TO')
			self._parse_clp_string_list()
		if self._match('LOBFILE'):
			self._parse_clp_string_list()
		if self._match_sequence(['XML', 'TO']):
			self._parse_clp_string_list()
		if self._match('XMLFILE'):
			self._parse_clp_string_list()
		if self._match('MODIFIED'):
			self._expect('BY')
			# The syntax of MODIFIED BY is so incongruous with the parser that
			# we don't even try and parse it, just skip tokens until we find
			# some "normal" syntax again. Unfortunately, this means the error
			# handling becomes rather dumb
			i = self._index
			while True:
				if self._token(i).value in [
					'XMLSAVESCHEMA',
					'METHOD',
					'MESSAGES',
					'HIERARCHY',
					'WITH',
					'SELECT',
					'VALUES',
				]:
					while self._index < i:
						self._output.append(self._token())
						self._index += 1
					break
				if self._token(i).type == TT.EOF:
					raise ParseError("Unable to find end of file-modifiers in EXPORT statement")
				i += 1
		self._match('XMLSAVESCHEMA')
		if self._match('METHOD'):
			self._expect('N')
			self._expect('(')
			self._parse_ident_list()
			self._expect(')')
		if self._match('MESSAGES'):
			self._expect_clp_string()
		if self._match('HIERARCHY'):
			if self._match('STARTING'):
				self._expect(TT.IDENTIFIER)
			else:
				self._expect('(')
				self._parse_ident_list()
				self._expect(')')
			if self._match('WHERE'):
				self._parse_search_condition()
		else:
			self._parse_select_statement()
		# XXX Add support for XQUERY?

	def _parse_force_application_command(self):
		"""Parses a FORCE APPLICATION command"""
		# FORCE APPLICATION already matched
		if self._match('('):
			self._parse_number_list()
			self._expect(')')
		else:
			self._expect('ALL')
		if self._match('MODE'):
			self._expect('ASYNC')

	def _parse_get_admin_cfg_command(self):
		"""Parses a GET ADMIN CFG command"""
		# GET ADMIN [CONFIGURATION|CONFIG|CFG] already matched
		if self._match('FOR'):
			self._expect_sequence(['NODE', TT.IDENTIFIER])
			self._parse_login(optional=True, allowchange=False)

	def _parse_get_alert_cfg_command(self):
		"""Parses a GET ALERT CFG command"""
		# GET ALERT [CONFIGURATION|CONFIG|CFG] already matched
		self._expect('FOR')
		if (
				self._match_sequence(['DATABASE', 'MANAGER'])
				or self._match_sequence(['DB', 'MANAGER'])
				or self._match_one_of(['DBM', 'DATABASES', 'CONTAINERS', 'TABLESPACES'])
			):
			self._match('DEFAULT')
		elif (
				self._match('DATABASE')
				or self._match_sequence(['TABLESPACE', TT.IDENTIFIER])
				or self._match_sequence(['CONTAINER', TT.IDENTIFIER, 'FOR', TT.IDENTIFIER])
			):
			self._expect('ON')
			self._expect_clp_string()
		else:
			self._expected_one_of([
				'DB',
				'DBM',
				'DATABASE',
				'DATABASES',
				'TABLESPACE',
				'TABLESPACES',
				'CONTAINER',
				'CONTAINERS',
			])
		if self._match('USING'):
			self._parse_clp_string_list()

	def _parse_get_cli_cfg_command(self):
		"""Parses a GET CLI CFG command"""
		# GET CLI [CONFIGURATION|CONFIG|CFG] already matched
		self._match_sequence(['AT', 'GLOBAL', 'LEVEL'])
		if self._match_sequence(['FOR', 'SECTION']):
			self._expect_clp_string()

	def _parse_get_connection_state_command(self):
		"""Parses a GET CONNECTION STATE command"""
		# GET CONNECTION STATE already matched
		pass

	def _parse_get_contactgroup_command(self):
		"""Parses a GET CONTACTGROUP command"""
		# GET CONTACTGROUP already matched
		self._expect_clp_string()

	def _parse_get_contactgroups_command(self):
		"""Parses a GET CONTACTGROUPS command"""
		# GET CONTACTGROUPS already matched
		pass

	def _parse_get_contacts_command(self):
		"""Parses a GET CONTACTS command"""
		# GET CONTACTS already matched
		pass

	def _parse_get_db_cfg_command(self):
		"""Parses a GET DB CFG command"""
		# GET [DATABASE|DB] [CONFIGURATION|CONFIG|CFG] already matched
		if self._match('FOR'):
			self._expect_clp_string()
		self._match_sequence(['SHOW', 'DETAIL'])

	def _parse_get_dbm_cfg_command(self):
		"""Parses a GET DBM CFG command"""
		# GET [DATABASE MANAGER|DB MANAGER|DBM] [CONFIGURATION|CONFIG|CFG] already matched
		self._match_sequence(['SHOW', 'DETAIL'])

	def _parse_get_dbm_monitor_switches_command(self):
		"""Parses a GET DBM MONITOR SWITCHES command"""
		# GET [DATABASE MANAGER|DB MANAGER|DBM] MONITOR SWITCHES already matched
		self._parse_db_partition_clause()

	def _parse_get_description_for_health_indicator_command(self):
		"""Parses a GET DESCRIPTION FOR HEALTH INDICATOR command"""
		# GET DESCRIPTION FOR HEALTH INDICATOR already matched
		self._expect_clp_string()

	def _parse_get_notification_list_command(self):
		"""Parses a GET NOTIFICATION LIST command"""
		# GET [HEALTH] NOTIFICATION [CONTACT] LIST already matched
		pass

	def _parse_get_health_snapshot_command(self):
		"""Parses a GET HEALTH SNAPSHOT command"""
		# GET HEALTH SNAPSHOT already matched
		self._expect('FOR')
		if (
				self._match_sequence(['DATABASE', 'MANAGER'])
				or self._match_sequence(['DB', 'MANAGER'])
				or self._match('DBM')
				or self._match_sequence(['ALL', 'DATABASES'])
			):
			pass
		elif self._match_one_of(['ALL', 'DATABASE', 'DB', 'TABLESPACES']):
			self._expect('ON')
			self._expect_clp_string()
		else:
			self._expected_one_of([
				'DB',
				'DATABASE',
				'DBM',
				'ALL',
				'TABLESPACES',
			])
		self._parse_db_partition_clause()
		self._match_sequence(['SHOW', 'DETAIL'])
		self._match_sequence(['WITH', 'FULL', 'COLLECTION'])

	def _parse_get_instance_command(self):
		"""Parses a GET INSTANCE command"""
		# GET INSTANCE already matched
		pass

	def _parse_get_monitor_switches_command(self):
		"""Parses a GET MONITOR SWITCHES command"""
		# GET MONITOR SWITCHES already matched
		self._parse_db_partition_clause()

	def _parse_get_recommendations_for_health_indicator_command(self):
		"""Parses a GET RECOMMENDATIONS FOR HEALTH INDICATOR command"""
		# GET RECOMMENDATIONS FOR HEALTH INDICATOR already matched
		self._expect_clp_string()
		if self._match('FOR'):
			if not self._match('DBM'):
				if self._match('TABLESPACE'):
					self._expect(TT.IDENTIFIER)
				elif self._match('CONTAINER'):
					self._expect_clp_string()
					self._expect_sequence(['FOR', 'TABLESPACE', TT.IDENTIFIER])
				elif self._match('DATABASE'):
					pass
				else:
					self._expected_one_of(['TABLESPACE', 'CONTAINER', 'DATABASE', 'DBM'])
				self._expect('ON')
				self._expect_clp_string()
		self._parse_db_partition_clause()

	def _parse_get_routine_command(self):
		"""Parses a GET ROUTINE command"""
		# GET ROUTINE already matched
		self._expect('INTO')
		self._expect_clp_string()
		self._expect('FROM')
		self._match('SPECIFIC')
		self._expect('PROCEDURE')
		self._parse_routine_name()
		self._match_sequence(['HIDE', 'BODY'])

	def _parse_get_snapshot_command(self):
		"""Parses a GET SNAPSHOT command"""
		# GET SNAPSHOT already matched
		self._expect('FOR')
		if (
				self._match_sequence(['DATABASE', 'MANAGER'])
				or self._match_sequence(['DB', 'MANAGER'])
				or self._match('DBM')
				or self._match_sequence(['ALL', 'DCS', 'DATABASES'])
				or self._match_sequence(['ALL', 'DATABASES'])
				or self._match_sequence(['ALL', 'DCS', 'APPLICATIONS'])
				or self._match_sequence(['ALL', 'APPLICATIONS'])
				or self._match_sequence(['ALL', 'BUFFERPOOLS'])
				or self._match_sequence(['FCM', 'FOR', 'ALL', 'DBPARTITIONNUMS'])
				or self._match_sequence(['FCM', 'FOR', 'ALL', 'NODES'])
				or (self._match_sequence(['DCS', 'APPLICATION', 'APPLID']) and self._match_clp_string())
				or self._match_sequence(['DCS', 'APPLICATION', 'AGENTID', TT.NUMBER])
				or (self._match_sequence(['APPLICATION', 'APPLID']) and self._match_clp_string())
				or self._match_sequence(['APPLICATION', 'AGENTID', TT.NUMBER])
				or (self._match_sequence(['LOCKS', 'FOR', 'APPLICATION', 'APPLID']) and self._match_clp_string())
				or self._match_sequence(['LOCKS', 'FOR', 'APPLICATION', 'AGENTID', TT.NUMBER])
				or self._match_sequence(['ALL', 'REMOTE_DATABASES'])
				or self._match_sequence(['ALL', 'REMOTE_APPLICATIONS'])
			):
			pass
		elif self._match_sequence(['DYNAMIC', 'SQL', 'ON']):
			self._expect_clp_string()
			self._match_sequence(['WRITE', 'TO', 'FILE'])
		elif (
				self._match('ALL')
				or self._match_sequence(['DCS', 'DATABASE'])
				or self._match_sequence(['DCS', 'DB'])
				or self._match_sequence(['DCS', 'APPLICATIONS'])
				or self._match_one_of([
					'DATABASE',
					'APPLICATIONS',
					'TABLES',
					'TABLESPACES',
					'LOCKS',
					'BUFFERPOOLS',
					'REMOTE_DATABASES',
					'REMOTE_APPLICATIONS'
				])
			):
			self._expect('ON')
			self._expect_clp_string()
		else:
			self._expected_one_of([
				'ALL',
				'DCS',
				'DB',
				'DBM',
				'DATABASE',
				'FCM',
				'DYNAMIC',
				'APPLICATION',
				'APPLICATIONS',
				'TABLES',
				'TABLESPACES',
				'LOCKS',
				'BUFFERPOOLS',
				'REMOTE_DATABASES',
				'REMOTE_APPLICATIONS',
			])
		self._parse_db_partition_clause()

	def _parse_import_method(self):
		"""Parses the METHOD clause of an IMPORT/LOAD command"""
		# METHOD already matched
		if self._match('L'):
			self._expect('(')
			while True:
				self._expect(TT.NUMBER) # col start
				self._expect(TT.NUMBER) # col end
				if not self._match(','):
					break
			self._expect(')')
			if self._match('NULL'):
				self._expect('INDICATORS')
				self._expect('(')
				self._parse_number_list()
				self._expect(')')
		elif self._match('N'):
			self._expect('(')
			self._parse_ident_list()
			self._expect(')')
		elif self._match('P'):
			self._expect('(')
			self._parse_number_list()
			self._expect(')')
		else:
			self._expected_one_of(['L', 'N', 'P'])

	def _parse_import_command(self):
		"""Parses a IMPORT command"""
		# IMPORT already matched
		self._expect('FROM')
		self.consumes.append((self._expect_clp_string().value, self.current_connection))
		self._expect('OF')
		self._expect_one_of(['ASC', 'DEL', 'IXF', 'WSF'])
		if self._match('LOBS'):
			self._expect('FROM')
			self._parse_clp_string_list()
		if self._match('XML'):
			self._expect('FROM')
			self._parse_clp_string_list()
		if self._match('MODIFIED'):
			self._expect('BY')
			# See _parse_export_command() above for an explanation...
			i = self._index
			while True:
				if self._token(i).value in [
					'METHOD',
					'COMMITCOUNT',
					'RESTARTCOUNT',
					'SKIPCOUNT',
					'ROWCOUNT',
					'WARNINGCOUNT',
					'NOTIMEOUT',
					'INSERT_UPDATE',
					'REPLACE',
					'REPLACE_CREATE',
					'MESSAGES',
					'INSERT',
					'CREATE',
					'ALLOW',
					'XMLPARSE',
					'XMLVALIDATE',
				]:
					while self._index < i:
						self._output.append(self._token())
						self._index += 1
					break
				if self._token(i).type == TT.EOF:
					raise ParseError("Unable to find end of file-modifiers in IMPORT statement")
				i += 1
		if self._match('METHOD'):
			self._parse_import_method()
		if self._match('XMLPARSE'):
			self._expect_one_of(['STRIP', 'PRESERVE'])
			self._expect('WHITESPACE')
		if self._match('XMLVALIDATE'):
			self._expect('USING')
			if self._match('XDS'):
				if self._match('DEFAULT'):
					self._parse_subschema_name()
				if self._match('IGNORE'):
					self._expect('(')
					while True:
						self._parse_subschema_name()
						if not self._match(','):
							break
					self._expect(')')
				if self._match('MAP'):
					self._expect('(')
					while True:
						self._expect('(')
						self._parse_subschema_name()
						self._expect(',')
						self._parse_subschema_name()
						self._expect(')')
						if not self._match(','):
							break
					self._expect(')')
			elif self._match('SCHEMA'):
				self._parse_subschema_name()
			elif self._match('SCHEMALOCATION'):
				self._expect('HINTS')
		if self._match('ALLOW'):
			self._expect_one_of(['NO', 'WRITE'])
			self._expect('ACCESS')
		if self._match('COMMITCOUNT'):
			self._expect_one_of([TT.NUMBER, 'AUTOMATIC'])
		if self._match_one_of(['RESTARTCOUNT', 'SKIPCOUNT']):
			self._expect(TT.NUMBER)
		if self._match('ROWCOUNT'):
			self._expect(TT.NUMBER)
		if self._match('WARNINGCOUNT'):
			self._expect(TT.NUMBER)
		if self._match('NOTIMEOUT'):
			pass
		if self._match('MESSAGES'):
			self._expect_clp_string()
		# Parse the action (CREATE/INSERT/etc.)
		t = self._expect_one_of([
			'CREATE',
			'INSERT',
			'INSERT_UPDATE',
			'REPLACE',
			'REPLACE_CREATE',
		])
		self._expect('INTO')
		self._parse_table_name()
		if self._match('('):
			self._parse_ident_list()
			self._expect(')')
		if (t.value == 'CREATE') and self._match('IN'):
			self._expect(TT.IDENTIFIER)
			if self._match('INDEX'):
				self._expect('IN')
				self._expect(TT.IDENTIFIER)
			if self._match('LONG'):
				self._expect('IN')
				self._expect(TT.IDENTIFIER)

	def _parse_initialize_tape_command(self):
		"""Parses an INTIALIZE TAPE command"""
		# INITIALIZE TAPE already matched
		if self._match('ON'):
			self._expect_clp_string()
		if self._match('USING'):
			self._expect(TT.NUMBER)

	def _parse_inspect_command(self):
		"""Parses an INSPECT command"""
		# INSPECT already matched
		if self._match('ROWCOMPESTIMATE'):
			self._expect('TABLE')
			if self._match('NAME'):
				self._expect(TT.IDENTIFIER)
				if self._match('SCHEMA'):
					self._expect(TT.IDENTIFIER)
			elif self._match('TBSPACEID'):
				self._expect_sequence([TT.NUMBER, 'OBJECTID', TT.NUMBER])
		elif self._match('CHECK'):
			if self._match('DATABASE'):
				if self._match('BEGIN'):
					self._expect_sequence(['TBSPACEID', TT.NUMBER])
					self._match_sequence(['OBJECTID', TT.NUMBER])
			elif self._match('TABLESPACE'):
				if self._match('NAME'):
					self._expect(TT.IDENTIFIER)
				elif self._match('TBSPACEID'):
					self._expect(TT.NUMBER)
				if self._match('BEGIN'):
					self._expect_sequence(['OBJECTID', TT.NUMBER])
			if self._match('TABLE'):
				if self._match('NAME'):
					self._expect(TT.IDENTIFIER)
					if self._match('SCHEMA'):
						self._expect(TT.IDENTIFIER)
				elif self._match('TBSPACEID'):
					self._expect_sequence([TT.NUMBER, 'OBJECTID', TT.NUMBER])
		else:
			self._expected_one_of(['ROWCOMPESTIMATE', 'CHECK'])
		self._match_sequence(['FOR', 'ERROR', 'STATE', 'ALL'])
		if self._match_sequence(['LIMIT', 'ERROR', 'TO']):
			self._expect_one_of(['DEFAULT', 'ALL', TT.NUMBER])
		if self._match('EXTENTMAP'):
			self._expect_one_of(['NORMAL', 'NONE', 'LOW'])
		if self._match('DATA'):
			self._expect_one_of(['NORMAL', 'NONE', 'LOW'])
		if self._match('BLOCKMAP'):
			self._expect_one_of(['NORMAL', 'NONE', 'LOW'])
		if self._match('INDEX'):
			self._expect_one_of(['NORMAL', 'NONE', 'LOW'])
		if self._match('LONG'):
			self._expect_one_of(['NORMAL', 'NONE', 'LOW'])
		if self._match('LOB'):
			self._expect_one_of(['NORMAL', 'NONE', 'LOW'])
		if self._match('XML'):
			self._expect_one_of(['NORMAL', 'NONE', 'LOW'])
		self._match('INDEXDATA')
		self._expect('RESULTS')
		self._match('KEEP')
		self._expect_clp_string()
		self._parse_db_partitions_clause()

	def _parse_instance_command(self):
		"""Parses the custom (non-CLP) INSTANCE command"""
		# INSTANCE already matched
		self.current_instance = self._expect_clp_string().value
		self.current_connection = None

	def _parse_list_active_databases_command(self):
		"""Parses a LIST ACTIVE DATABASES command"""
		# LIST ACTIVE DATABASES already matched
		self._parse_db_partition_clause()

	def _parse_list_applications_command(self):
		"""Parses a LIST APPLICATIONS command"""
		# LIST APPLICATIONS already matched
		if self._match('FOR'):
			self._expect_one_of(['DATABASE', 'DB'])
			self._expect_clp_string()
		self._parse_db_partition_clause()
		self._match_sequence(['SHOW', 'DETAIL'])

	def _parse_list_command_options_command(self):
		"""Parses a LIST COMMAND OPTIONS command"""
		# LIST COMMAND OPTIONS already matched
		pass

	def _parse_list_db_directory_command(self):
		"""Parses a LIST DB DIRECTORY command"""
		# LIST [DATABASE|DB] DIRECTORY already matched
		if self._match('ON'):
			self._expect_clp_string()

	def _parse_list_database_partition_groups_command(self):
		"""Parses a LIST DATABASE PARTITION GROUPS command"""
		# LIST DATABASE PARTITION GROUPS already matched
		self._match_sequence(['SHOW', 'DETAIL'])

	def _parse_list_nodes_command(self):
		"""Parses a LIST NODES command"""
		# LIST DBPARTITIONNUMS|NODES already matched
		pass

	def _parse_list_dcs_applications_command(self):
		"""Parses a LIST DCS APPLICATIONS command"""
		# LIST DCS APPLICATIONS already matched
		if not self._match('EXTENDED'):
			self._match_sequence(['SHOW', 'DETAIL'])

	def _parse_list_dcs_directory_command(self):
		"""Parses a LIST DCS DIRECTORY command"""
		# LIST DCS DIRECTORY already matched
		pass

	def _parse_list_drda_indoubt_transactions_command(self):
		"""Parses a LIST DRDA INDOUBT TRANSACTIONS command"""
		# LIST DRDA INDOUBT TRANSACTIONS already matched
		self._match_sequence(['WITH', 'PROMPTING'])

	def _parse_list_history_command(self):
		"""Parses a LIST HISTORY command"""
		# LIST HISTORY already matched
		if self._match_one_of(['CREATE', 'ALTER', 'RENAME']):
			self._expect('TABLESPACE')
		elif self._match('ARCHIVE'):
			self._expect('LOG')
		elif self._match('DROPPED'):
			self._expect('TABLE')
		else:
			self._match_one_of(['BACKUP', 'ROLLFORWARD', 'LOAD', 'REORG'])
		if self._match('SINCE'):
			self._expect(TT.NUMBER)
		elif self._match('CONTAINING'):
			self._parse_subschema_name()
		elif not self._match('ALL'):
			self._expected_one_of(['ALL', 'SINCE', 'CONTAINING'])
		self._expect('FOR')
		self._match_one_of(['DATABASE', 'DB'])
		self._expect_clp_string()

	def _parse_list_indoubt_transactions_command(self):
		"""Parses a LIST INDOUBT TRANSACTIONS command"""
		# LIST INDOUBT TRANSACTIONS already matched
		self._match_sequence(['WITH', 'PROMPTING'])

	def _parse_list_node_directory_command(self):
		"""Parses a LIST NODE DIRECTORY command"""
		# LIST [ADMIN] NODE DIRECTORY already matched
		self._match_sequence(['SHOW', 'DETAIL'])

	def _parse_list_odbc_data_sources_command(self):
		"""Parses a LIST ODBC DATA SOURCES command"""
		# LIST [USER|SYSTEM] ODBC DATA SOURCES already matched
		pass

	def _parse_list_tables_command(self):
		"""Parses a LIST TABLES command"""
		# LIST PACKAGES|TABLES already matched
		if self._match('FOR'):
			if self._match('SCHEMA'):
				self._expect(TT.IDENTIFIER)
			elif not self._match_one_of(['USER', 'SYSTEM', 'ALL']):
				self._expected_one_of(['USER', 'SYSTEM', 'ALL', 'SCHEMA'])
		self._match_sequence(['SHOW', 'DETAIL'])

	def _parse_list_tablespace_containers_command(self):
		"""Parses a LIST TABLESPACE CONTAINERS command"""
		# LIST TABLESPACE CONTAINERS already matched
		self._expect_sequence(['FOR', TT.NUMBER])
		self._match_sequence(['SHOW', 'DETAIL'])

	def _parse_list_tablespaces_command(self):
		"""Parses a LIST TABLESPACES command"""
		# LIST TABLESPACES already matched
		self._match_sequence(['SHOW', 'DETAIL'])

	def _parse_list_utilities_command(self):
		"""Parses a LIST UTILITIES command"""
		# LIST UTILITIES already matched
		self._match_sequence(['SHOW', 'DETAIL'])

	def _parse_load_command(self):
		"""Parses a LOAD command"""
		# LOAD already matched
		self._match('CLIENT')
		self._expect('FROM')
		filename = self._expect_clp_string().value
		self._expect('OF')
		if self._expect_one_of(['ASC', 'DEL', 'IXF', 'CURSOR']).value != 'CURSOR':
			self.consumes.append((filename, self.current_connection))
		if self._match('LOBS'):
			self._expect('FROM')
			self._parse_clp_string_list()
		if self._match('XML'):
			self._expect('FROM')
			self._parse_clp_string_list()
		if self._match('MODIFIED'):
			self._expect('BY')
			# See _parse_export_command() above for an explanation...
			i = self._index
			while True:
				if self._token(i)[1] in [
					'INSERT',
					'MESSAGES',
					'METHOD',
					'REPLACE',
					'RESTART',
					'ROWCOUNT',
					'SAVECOUNT',
					'TEMPFILES',
					'TERMINATE',
					'WARNINGCOUNT',
					'XMLPARSE',
					'XMLVALIDATE',
				]:
					while self._index < i:
						self._output.append(self._token())
						self._index += 1
					break
				if self._token(i).type == TT.EOF:
					raise ParseError("Unable to find end of file-modifiers in LOAD statement")
				i += 1
		if self._match('METHOD'):
			self._parse_import_method()
		if self._match('XMLPARSE'):
			self._expect_one_of(['STRIP', 'PRESERVE'])
			self._expect('WHITESPACE')
		if self._match('XMLVALIDATE'):
			self._expect('USING')
			if self._match('XDS'):
				if self._match('DEFAULT'):
					self._parse_subschema_name()
				if self._match('IGNORE'):
					self._expect('(')
					while True:
						self._parse_subschema_name()
						if not self._match(','):
							break
					self._expect(')')
				if self._match('MAP'):
					self._expect('(')
					while True:
						self._expect('(')
						self._parse_subschema_name()
						self._expect(',')
						self._parse_subschema_name()
						self._expect(')')
						if not self._match(','):
							break
					self._expect(')')
			elif self._match('SCHEMA'):
				self._parse_subschema_name()
			elif self._match('SCHEMALOCATION'):
				self._expect('HINTS')
		if self._match('SAVECOUNT'):
			self._expect(TT.NUMBER)
		if self._match('ROWCOUNT'):
			self._expect(TT.NUMBER)
		if self._match('WARNINGCOUNT'):
			self._expect(TT.NUMBER)
		if self._match('MESSAGES'):
			self._expect_clp_string()
		if self._match('TEMPFILES'):
			self._expect('PATH')
			self._expect_clp_string()
		if self._expect_one_of(['INSERT', 'RESTART', 'REPLACE', 'TERMINATE']).value == 'REPLACE':
			self._match_one_of(['KEEPDICTIONARY', 'RESETDICTIONARY'])
		self._expect('INTO')
		self._parse_table_name()
		if self._match('('):
			self._parse_ident_list()
			self._expect(')')
		if self._match('FOR'):
			self._expect('EXCEPTION')
			self._parse_table_name()
			if self._match_one_of(['NORANGEEXC', 'NOUNIQUEEXC']):
				if self._match(','):
					self._expect_one_of(['NORANGEEXC', 'NOUNIQUEEXC'])
		if self._match('STATISTICS'):
			if self._expect_one_of(['NO', 'USE']).value == 'USE':
				self._expect('PROFILE')
		if self._match('COPY'):
			if self._expect_one_of(['NO', 'YES']).value == 'YES':
				if self._match('USE'):
					self._expect('TSM')
					if self._match('OPEN'):
						self._expect_sequence([TT.NUMBER, 'SESSIONS'])
				elif self._match('TO'):
					self._parse_clp_string_list()
				elif self._match('LOAD'):
					self._expect_clp_string()
					if self._match('OPEN'):
						self._expect_sequence([TT.NUMBER, 'SESSIONS'])
				else:
					self._expected_one_of(['USE', 'TO', 'LOAD'])
		elif self._match('NONRECOVERABLE'):
			pass
		if self._match('WITHOUT'):
			self._expect('PROMPTING')
		if self._match('DATA'):
			self._expect('BUFFER')
			self._expect(TT.NUMBER)
		if self._match('SORT'):
			self._expect('BUFFER')
			self._expect(TT.NUMBER)
		if self._match('CPU_PARALLELISM'):
			self._expect(TT.NUMBER)
		if self._match('DISK_PARALLELISM'):
			self._expect(TT.NUMBER)
		if self._match('FETCH_PARALLELISM'):
			self._expect_one_of(['YES', 'NO'])
		if self._match('INDEXING'):
			self._expect('MODE')
			self._expect_one_of(['AUTOSELECT', 'REBUILD', 'INCREMENTAL', 'DEFERRED'])
		if self._match('ALLOW'):
			if self._match_sequence(['READ', 'ACCESS']):
				self._match_sequence(['USE', TT.IDENTIFIER])
			elif self._match_sequence(['NO', 'ACCESS']):
				pass
			else:
				self._expected_one_of(['READ', 'NO'])
		if self._match_sequence(['SET', 'INTEGRITY']):
			self._expect_sequence(['PENDING', 'CASCADE'])
			self._expect_one_of(['DEFERRED', 'IMMEDIATE'])
		if self._match('LOCK'):
			self._expect_sequence(['WITH', 'FORCE'])
		if self._match('SOURCEUSEREXIT'):
			self._expect_clp_string()
			if self._match('REDIRECT'):
				if self._match('INPUT'):
					self._expect('FROM')
					self._expect_one_of(['BUFFER', 'FILE'])
					self._expect_clp_string()
				if self._match('OUTPUT'):
					self._expect_sequence(['TO', 'FILE'])
					self._expect_clp_string()
		self._match_sequence(['PARTITIONED', 'DB', 'CONFIG'])
		while True:
			if self._match('MODE'):
				self._expect_one_of([
					'PARTITION_AND_LOAD',
					'PARTITION_ONLY',
					'LOAD_ONLY',
					'LOAD_ONLY_VERIFY_PART',
					'ANALYZE',
				])
			elif self._match('ISOLATE_PART_ERRS'):
				self._expect_one_of([
					'SETUP_ERRS_ONLY',
					'LOAD_ERRS_ONLY',
					'SETUP_AND_LOAD_ERRS',
					'NO_ISOLATION',
				])
			elif self._match_one_of(['PART_FILE_LOCATION', 'MAP_FILE_INPUT', 'MAP_FILE_OUTPUT', 'DISTFILE']):
				self._expect_clp_string()
			elif self._match_one_of(['OUTPUT_DBPARTNUMS', 'PARTITIONING_DBPARTNUMS']):
				self._expect('(')
				while True:
					self._expect(TT.NUMBER)
					if self._match('TO'):
						self._expect(TT.NUMBER)
					if not self._match(','):
						break
				self._expect(')')
			elif self._match_one_of(['MAXIMUM_PART_AGENTS', 'STATUS_INTERVAL', 'TRACE', 'RUN_STAT_DBPARTNUM']):
				self._expect(TT.NUMBER)
			elif self._match('PORT_RANGE'):
				self._expect_sequence(['(', TT.NUMBER, ',', TT.NUMBER, ')'])
			elif self._match_one_of(['CHECK_TRUNCATION', 'NEWLINE', 'OMIT_HEADER']):
				pass
			else:
				break

	def _parse_load_query_command(self):
		"""Parses a LOAD QUERY command"""
		# LOAD QUERY already matched
		self._expect('TABLE')
		self._parse_table_name()
		if self._match('TO'):
			self._expect_clp_string()
		self._match_one_of(['NOSUMMARY', 'SUMMARYONLY'])
		self._match('SHOWDELTA')

	def _parse_migrate_db_command(self):
		"""Parses a MIGRATE DB command"""
		# MIGRATE [DATABASE|DB] already matched
		self._expect_clp_string()
		self._parse_login(optional=True, allowchange=False)

	def _parse_on_command(self):
		"""Parses the custom (non-CLP) ON SQLCODE|SQLSTATE|ERROR|REGEX command"""
		# ON already matched
		if self._match('SQLCODE'):
			if self._match((TT.OPERATOR, '-')):
				self._expect(TT.NUMBER)
			else:
				self._expect_one_of([TT.STRING, TT.NUMBER])
		elif self._match('SQLSTATE'):
			self._expect(TT.STRING)
		elif self._match('ERROR'):
			pass
		elif self._match('REGEX'):
			self._expect(TT.STRING)
		else:
			self._expected_one_of(['SQLCODE', 'SQLSTATE', 'ERROR', 'REGEX'])
		wait = False
		if self._match('WAIT'):
			wait = True
			self._expect(TT.NUMBER)
			self._expect_one_of(['SECOND', 'SECONDS', 'MINUTE', 'MINUTES', 'HOUR', 'HOURS'])
			self._match('AND')
		retry = False
		if self._match('RETRY'):
			retry = True
			self._expect_one_of(['STATEMENT', 'SCRIPT'])
			if self._match(TT.NUMBER):
				self._expect_one_of(['TIME', 'TIMES'])
			self._match('THEN')
		if wait and not retry:
			self._expected('RETRY')
		self._expect_one_of(['FAIL', 'STOP', 'CONTINUE', 'IGNORE'])

	def _parse_ping_command(self):
		"""Parses a PING command"""
		# PING already matched
		self._expect_clp_string()
		if self._match('REQUEST'):
			self._expect(TT.NUMBER)
		if self._match('RESPONSE'):
			self._expect(TT.NUMBER)
		if self._match(TT.NUMBER):
			self._match_one_of(['TIME', 'TIMES'])

	def _parse_precompile_command(self):
		"""Parses a PRECOMPILE command"""
		# [PREP|PRECOMPILE] already matched
		# XXX Can these parameters be specified in any order?
		self._expect_clp_string()
		if self._match('ACTION'):
			if self._match_one_of(['ADD', 'REPLACE']).value == 'ADD':
				pass
			else:
				if self._match('RETAIN'):
					self._expect_one_of(['YES', 'NO'])
				if self_match('REPLVER'):
					self._expect_clp_string()
		if self._match('APREUSE'):
			self._expect_one_of(['YES', 'NO'])
		if self._match('BINDFILE'):
			if self._match('USING'):
				self._expect_clp_string()
		if self._match('BLOCKING'):
			self._expect_one_of(['UNAMBIG', 'ALL', 'NO'])
		if self._match('COLLECTION'):
			self._expect(TT.IDENTIFIER)
		if self._match('CALL_RESOLUTION'):
			self._expect_one_of(['IMMEDIATE', 'DEFERRED'])
		if self._match('CCSIDG'):
			self._expect(TT.NUMBER)
		if self._match('CCSIDM'):
			self._expect(TT.NUMBER)
		if self._match('CCSIDS'):
			self._expect(TT.NUMBER)
		if self._match('CHARSUB'):
			self._expect_one_of(['DEFAULT', 'BIT', 'MIXED', 'SBCS'])
		if self._match('CNULREQD'):
			self._expect_one_of(['YES', 'NO'])
		if self._match('COLLECTION'):
			self._expect(TT.IDENTIFIER)
		self._match_one_of(['COMPILE', 'PRECOMPILE'])
		if self._match('CONCURRENTACCESSRESOLUTION'):
			if self._expect_one_of(['USE', 'WAIT']).value == 'USE':
				self._expect_sequence(['CURRENTLY', 'COMMITTED'])
			else:
				self._expect_sequence(['FOR', 'OUTCOME'])
		if self._match('CONNECT'):
			self._expect(TT.NUMBER)
		if self._match('DATETIME'):
			self._expect_one_of(['DEF', 'EUR', 'ISO', 'JIS', 'LOC', 'USA'])
		if self._match('DBPROTOCOL'):
			self._expect_one_of(['DRDA', 'PRIVATE'])
		if self._match('DEC'):
			self._expect(TT.NUMBER)
		if self._match('DECDEL'):
			self._expect_one_of(['PERIOD', 'COMMA'])
		if self._match('DEFERRED_PREPARE'):
			self._expect_one_of(['NO', 'ALL', 'YES'])
		if self._match('DEGREE'):
			self._expect_one_of([TT.NUMBER, 'ANY'])
		if self._match('DISCONNECT'):
			self._expect_one_of(['EXPLICIT', 'AUTOMATIC', 'CONDITIONAL'])
		if self._match('DYNAMICRULES'):
			self._expect_one_of(['RUN', 'BIND', 'INVOKERUN', 'INVOKEBIND', 'DEFINERUN', 'DEFINEBIND'])
		if self._match('ENCODING'):
			self._expect_one_of(['ASCII', 'EBCDIC', 'UNICODE', 'CCSID'])
		if self._match('EXPLAIN'):
			self._expect_one_of(['NO', 'ALL', 'ONLY', 'REOPT', 'YES'])
		if self._match('EXPLSNAP'):
			self._expect_one_of(['NO', 'ALL', 'REOPT', 'YES'])
		if self._match('EXTENDEDINDICATOR'):
			self._expect_one_of(['YES', 'NO'])
		if self._match('FEDERATED'):
			self._expect_one_of(['YES', 'NO'])
		if self._match('FEDERATED_ASYNCHRONY'):
			self._expect_one_of([TT.NUMBER, 'ANY'])
		if self._match('FUNCPATH'):
			self._parse_ident_list()
		if self._match('GENERIC'):
			self._expect_clp_string()
		if self._amtch('IMMEDWRITE'):
			self._expect_one_of(['NO', 'YES', 'PH1'])
		if self._match('INSERT'):
			self._expect_one_of(['DEF', 'BUF'])
		if self._match('ISOLATION'):
			self._expect_one_of(['CS', 'NC', 'RR', 'RS', 'UR'])
		if self._match('KEEPDYNAMIC'):
			self._expect_one_of(['YES', 'NO'])
		if self._match('LANGLEVEL'):
			self._expect_one_of(['SAA1', 'MIA', 'SQL92E'])
		if self._match('LEVEL'):
			self._expect(TT.IDENTIFIER)
		if self._match('LONGERROR'):
			self._expect_one_of(['YES', 'NO'])
		if self._match('MESSAGES'):
			self._expect_clp_string()
		if self._match('NOLINEMACRO'):
			pass
		if self._match('OPTHINT'):
			self._expect_clp_string()
		if self._match('OPTLEVEL'):
			self._expect(TT.NUMBER)
		if self._match('OPTPROFILE'):
			self._expect_clp_string()
		if self._match('OS400NAMING'):
			self._expect_one_of(['SYSTEM', 'SQL'])
		if self._match('OUTPUT'):
			self._expect_clp_string()
		if self._match('OWNER'):
			self._expect(TT.IDENTIFIER)
		if self._match('PACKAGE'):
			if self._match('USING'):
				self._expect(TT.IDENTIFIER)
		if self._match('PREPROCESSOR'):
			self._expect_clp_string()
		if self._match('QUALIFIER'):
			self._expect(TT.IDENTIFIER)
		if self._match('QUERYOPT'):
			self._expect(TT.NUMBER)
		if self._match('RELEASE'):
			self._expect_one_of(['COMMIT', 'DEALLOCATE'])
		if self._match('REOPT'):
			self._expect_one_of(['NONE', 'ONCE', 'ALWAYS', 'VARS'])
		if self._match_one_of(['REOPT', 'NOREOPT']):
			self._expect('VARS')
		if self._match('SQLCA'):
			self._expect_one_of(['NONE', 'SAA'])
		if self._match('SQLERROR'):
			self._expect_one_of(['NOPACKAGE', 'CHECK', 'CONTINUE'])
		if self._match('SQLFLAG'):
			self._expect_one_of(['SQL92E', 'MVSDB2V23', 'MVSDB2V31', 'MVSDB2V41'])
			self._expect('SYNTAX')
		if self._match('SORTSEQ'):
			self._expect_one_of(['JOBRUN', 'HEX'])
		if self._match('SQLRULES'):
			self._expect_one_of(['DB2', 'STD'])
		if self._match('SQLWARN'):
			self._expect_one_of(['YES', 'NO'])
		if self._match('STATICREADONLY'):
			self._expect_one_of(['YES', 'NO', 'INSENSITIVE'])
		if self._match('STRDEL'):
			self._expect_one_of(['APOSTROPHE', 'QUOTE'])
		if self._match('SYNCPOINT'):
			self._expect_one_of(['ONEPHASE', 'NONE', 'TWOPHASE'])
		if self._match('SYNTAX'):
			pass
		if self._match('TARGET'):
			self._expect_one_of(['IBMCOB', 'MFCOB', 'ANSI_COBOL', 'C', 'CPLUSPLUS', 'FORTRAN', 'BORLAND_C', 'BORLAND_CPLUSPLUS'])
		if self._match('TEXT'):
			self._expect_clp_string()
		if self._match('TRANSFORM'):
			self._expect('GROUP')
			self._expect(TT.IDENTIFIER)
		if self._match('VALIDATE'):
			self._expect_one_of(['BIND', 'RUN'])
		if self._match('WCHARTYPE'):
			self._expect_one_of(['NOCONVERT', 'CONVERT'])
		if self._match('VERSION'):
			self._expect_clp_string()

	def _parse_prune_history_command(self):
		"""Parses a PRUNE HISTORY command"""
		# PRUNE HISTORY already matched
		self._expect(TT.NUMBER)
		self._match_sequence(['WITH', 'FORCE', 'OPTION'])
		self._match_sequence(['AND', 'DELETE'])

	def _parse_prune_logfile_command(self):
		"""Parses a PRUNE LOGFILE command"""
		# PRUNT LOGFILE already matched
		self._expect_sequence(['PRIOR', 'TO'])
		self._expect_clp_string()

	def _parse_put_routine_command(self):
		"""Parses a PUT ROUTINE command"""
		# PUT ROUTINE already matched
		self._expect('FROM')
		self._expect_clp_string()
		if self._match('OWNER'):
			self._expect(TT.IDENTIFIER)
			self._match_sequence(['USE', 'REGISTERS'])

	def _parse_query_client_command(self):
		"""Parses a QUERY CLIENT command"""
		# QUERY CLIENT already matched
		pass

	def _parse_quiesce_command(self):
		"""Parses a QUIESCE DB / INSTANCE command"""
		# QUIESCE already matched
		if self._match('INSTANCE'):
			self._expect_clp_string()
			if self._match_one_of(['USER', 'GROUP']):
				self._expect(TT.IDENTIFIER)
			self._match_sequence(['RESTRICTED', 'ACCESS'])
		elif self._match_one_of(['DATABASE', 'DB']):
			pass
		else:
			self._expected_one_of(['DATABASE', 'DB', 'INSTANCE'])
		if self._expect_one_of(['IMMEDIATE', 'DEFER'])[1] == 'DEFER':
			if self._match('WITH'):
				self._expect_sequence(['TIMEOUT', TT.NUMBER])
		self._match_sequence(['FORCE', 'CONNECTIONS'])

	def _parse_quiesce_tablespaces_command(self):
		"""Parses a QUIESCE TABLESPACES command"""
		# QUIESCE TABLESPACES already matched
		self._expect_sequence(['FOR', 'TABLE'])
		self._parse_table_name()
		if self._expect_one_of(['SHARE', 'INTENT', 'EXCLUSIVE', 'RESET']).value == 'INTENT':
			self._expect_sequence(['TO', 'UPDATE'])

	def _parse_quit_command(self):
		"""Parses a QUIT command"""
		# QUIT already matched
		pass

	def _parse_rebind_command(self):
		"""Parses a REBIND command"""
		# REBIND already matched
		self._match('PACKAGE')
		self._parse_subschema_name()
		if self._match('VERSION'):
			self._expect_clp_string()
		if self._match('APREUSE'):
			self._expect_one_of(['YES', 'NO'])
		if self._match('RESOLVE'):
			self._expect_one_of(['ANY', 'CONSERVATIVE'])
		if self._match('REOPT'):
			self._expect_one_of(['NONE', 'ONCE', 'ALWAYS'])

	def _parse_recover_db_command(self):
		"""Parses a RECOVER DB command"""
		# RECOVER [DATABASE|DB] already matched
		self._expect_clp_string()
		if self._match('TO'):
			if self._match('END'):
				self._expect_sequence(['OF', 'LOGS'])
				self._parse_db_partitions_clause()
			else:
				self._expect_clp_string()
				if self._match('USING'):
					self._expect_one_of(['LOCAL', 'UTC'])
					self._expect('TIME')
				if self._match('ON'):
					self._expect('ALL')
					self._expect_one_of(['DBPARTITIONNUMS', 'NODES'])
		self._parse_login(optional=True, allowchange=False)
		if self._match('USING'):
			self._expect_sequence(['HISTORY', 'FILE'])
			self._expect('(')
			self._expect_clp_string()
			if self._match(','):
				while True:
					self._expect_clp_string()
					self._expect('ON')
					self._expect_one_of(['DBPARTITIONNUM', 'NODE'])
					self._expect(TT.NUMBER)
					if not self._match(','):
						break
			self._expect(')')
		if self._match('OVERFLOW'):
			self._expect_sequence(['LOG', 'PATH'])
			self._expect('(')
			self._expect_clp_string()
			if self._match(','):
				while True:
					self._expect_clp_string()
					self._expect('ON')
					self._expect_one_of(['DBPARTITIONNUM', 'NODE'])
					self._expect(TT.NUMBER)
					if not self._match(','):
						break
			self._expect(')')
		if self._match('COMPRLIB'):
			self._expect_clp_string()
		if self._match('COMPROPTS'):
			self._expect_clp_string()
		self._match('RESTART')

	def _parse_redistribute_database_partition_group_command(self):
		"""Parses a REDISTRIBUTE DATABASE PARTITION GROUP command"""
		# REDISTRIBUTE DATABASE PARTITION GROUP already matched
		self._expect_clp_string()
		self._match_sequence(['NOT', 'ROLLFORWARD', 'RECOVERABLE'])
		t = self._expect_one_of(['UNIFORM',' USING', 'COTNINUE', 'ABORT']).value
		partitions = False
		if t == 'USING':
			if self._expect_one_of(['DISTFILE', 'TARGETMAP']).value == 'DISTFILE':
				partitions = True
			self._expect_clp_string()
		elif t == 'UNIFORM':
			partitions = True
		if partitions:
			if self._match('ADD'):
				self._parse_db_partition_list_clause(size=False)
			if self._match('DROP'):
				self._parse_db_partition_list_clause(size=False)
		if self._match('TABLE'):
			self._expect('(')
			while True:
				self._parse_table_name()
				if not self._match(','):
					break
			self._expect(')')
			self._match_one_of(['ONCE', 'FIRST'])
		if self._match('INDEXING'):
			self._expect('MODE')
			self._expect_one_of(['REBUILD', 'DEFERRED'])
		elif self._match('DATA'):
			self._expect('BUFFER')
			self._expect(TT.NUMBER)
		elif self._match('STATISTICS'):
			if self._expect_one_of(['USE', 'NONE']).value == 'USE':
				self._expect('PROFILE')
		elif self._match('STOP'):
			self._expect('AT')
			self._expect_clp_string()

	def _parse_refresh_ldap_command(self):
		"""Parses a REFRESH LDAP command"""
		# REFRESH LDAP already matched
		if self._match('CLI'):
			self._expect('CFG')
		elif self._match_one_of(['DB', 'NODE']):
			self._expect('DIR')
		elif self._match('IMMEDIATE'):
			self._match('ALL')
		else:
			self._expected_one_of(['CLI', 'DB', 'NODE', 'IMMEDIATE'])

	def _parse_register_command(self):
		"""Parses a REGISTER command"""
		# REGISTER already matched
		self._match_sequence(['DB2', 'SERVER'])
		self._match('IN')
		self._match('ADMIN')
		self._expect('LDAP')
		self._expect_one_of(['NODE', 'AS'])
		self._expect_clp_string()
		self._expect('PROTOCOL')
		if self._expect_one_of(['TCPIP', 'TCPIP4', 'TCPIP6', 'NPIPE']).value != 'NPIPE':
			if self._match('HOSTNAME'):
				self._expect_clp_string()
			if self._match('SVCENAME'):
				self._expect_clp_string()
			self._match_sequence(['SECURITY', 'SOCKS'])
		if self._match('REMOTE'):
			self._expect_clp_string()
		if self._match('INSTANCE'):
			self._expect_clp_string()
		if self._match('NODETYPE'):
			self._expect_one_of(['SERVER', 'MPP', 'DCS'])
		if self._match('OSTYPE'):
			self._expect_clp_string()
		if self._match('WITH'):
			self._expect_clp_string()
		self._parse_login(optional=True, allowchange=False)

	def _parse_register_xmlschema_command(self):
		"""Parses a REGISTER XMLSCHEMA command"""
		# REGISTER XMLSCHEMA already matched
		self._expect_clp_string()
		self._expect('FROM')
		self._expect_clp_string()
		if self._match('WITH'):
			self._expect_clp_string()
		if self._match('AS'):
			self._parse_subschema_name()
		if self._match('('):
			while True:
				self._expect('ADD')
				self._expect_clp_string()
				self._expect('FROM')
				self._expect_clp_string()
				if self._match('WITH'):
					self._expect_clp_string()
				if self._match(')'):
					break
		if self._match('COMPLETE'):
			if self._match('WITH'):
				self._expect_clp_string()
			if self._match('ENABLE'):
				self._expect('DECOMPOSITION')

	def _parse_register_xsrobject_command(self):
		"""Parses a REGISTER XSROBJECT command"""
		# REGISTER XSROBJECT already matched
		self._expect_clp_string()
		if self._match('PUBLIC'):
			self._expect_clp_string()
		self._expect('FROM')
		self._expect_clp_string()
		if self._match('AS'):
			self._parse_subschema_name()
		if self._match('EXTERNAL'):
			self._expect('ENTITY')
		else:
			self._expect_one_of(['DTD', 'EXTERNAL'])

	def _parse_reorg_command(self):
		"""Parses a REORG command"""

		def parse_table_clause():
			if self._match('INDEX'):
				self._parse_index_name()
			if self._match('INPLACE'):
				if not self._match_one_of(['STOP', 'PAUSE']):
					if self._match('ALLOW'):
						self._expect_one_of(['READ', 'WRITE'])
						self._expect('ACCESS')
					if self._match('NOTRUNCATE'):
						self._expect('TABLE')
					self._match_one_of(['START', 'RESUME'])
			else:
				if self._match('ALLOW'):
					self._expect_one_of(['READ', 'NO'])
					self._expect('ACCESS')
				if self._match('USE'):
					self._expect(TT.IDENTIFIER)
				self._match('INDEXSCAN')
				if self._match('LONGLOBDATA'):
					if self._match('USE'):
						self._expect(TT.IDENTIFIER)
				self._match_one_of(['KEEPDICTIONARY', 'RESETDICTIONARY'])

		def parse_index_clause():
			if self._match('ALLOW'):
				self._expect_one_of(['NO', 'WRITE', 'READ'])
				self._expect('ACCESS')
			if self._match_one_of(['CONVERT', 'CLEANUP']).value == 'CLEANUP':
				self._expect('ONLY')
				self._match_one_of(['ALL', 'PAGES'])

		# REORG already matched
		if self._match('TABLE'):
			self._parse_table_name()
			if self._match('RECLAIM'):
				self._expect_sequence(['EXTENTS', 'ONLY'])
				if self._match('ALLOW'):
					self._expect_one_of(['READ', 'WRITE', 'NO'])
					self._expect('ACCESS')
			else:
				parse_table_clause()
		elif self._match('INDEX'):
			self._parse_index_name()
			if self._match('FOR'):
				self._expect('TABLE')
				self._parse_table_name()
				parse_index_clause()
		elif self._match('INDEXES'):
			self._expect_sequence(['ALL', 'FOR', 'TABLE'])
			self._parse_table_name()
			parse_index_clause()
		else:
			self._expected_one_of(['TABLE', 'INDEX', 'INDEXES'])
		if self._match_sequence(['ON', 'DATA', 'PARTITION']):
			self._expect(TT.IDENTIFIER)
		self._parse_db_partitions_clause()

	def _parse_reorgchk_command(self):
		"""Parses a REORGCHK command"""
		# REORGCHK already matched
		if self._match_one_of(['UPDATE', 'CURRENT']):
			self._expect('STATISTICS')
		if self._match('ON'):
			if self._match('SCHEMA'):
				self._expect(TT.IDENTIFIER)
			elif self._match('TABLE'):
				if not self._match_one_of(['SYSTEM', 'USER', 'ALL']):
					self._parse_table_name()
			else:
				self._expected_one_of(['SCHEMA', 'TABLE'])

	def _parse_reset_admin_cfg_command(self):
		"""Parses a RESET ADMIN CFG command"""
		# RESET ADMIN [CONFIGURATION|CONFIG|CFG] already matched
		if self._match('FOR'):
			self._expect('NODE')
			self._expect_clp_string()
			self._parse_login(optional=True, allowchange=False)

	def _parse_reset_alert_cfg_command(self):
		"""Parses a RESET ALERT CFG command"""
		# RESET ALERT [CONFIGURATION|CONFIG|CFG] already matched
		self._expect('FOR')
		if (
				self._match_sequence(['DATABASE', 'MANAGER'])
				or self._match_sequence(['DB', 'MANAGER'])
				or self._match_one_of(['DBM', 'CONTAINERS', 'DATABASES', 'TABLESPACES'])
			):
			pass
		elif (
				self._match_sequence(['CONTAINER', TT.IDENTIFIER, 'FOR', TT.IDENTIFIER])
				or self._match_sequence('TABLESPACE', TT.IDENTIFIER)
				or self._match('DATABASE')
			):
			self._expect('ON')
			self._expect_clp_string()
			if self._match('USING'):
				self._expect_clp_string()

	def _parse_reset_db_cfg_command(self):
		"""Parses a RESET DB CFG command"""
		# RESET [DATABASE|DB] [CONFIGURATION|CONFIG|CFG] already matched
		self._expect('FOR')
		self._expect_clp_string()
		if self._match_one_of(['DBPARTITIONNUM', 'NODE']):
			self._expect(TT.NUMBER)

	def _parse_reset_dbm_cfg_command(self):
		"""Parses a RESET DBM CFG command"""
		# RESET [DATABASE MANAGER|DB MANAGER|DBM] [CONFIGURATION|CONFIG|CFG] already matched
		pass

	def _parse_reset_monitor_command(self):
		"""Parses a RESET MONITOR command"""
		# RESET MONITOR already matched
		if self._match('ALL'):
			self._match('DCS')
		elif self._match('FOR'):
			self._match('DCS')
			self._expect_one_of(['DATABASE', 'DB'])
			self._expect_clp_string()
		else:
			self._expected_one_of(['ALL', 'FOR'])
		self._parse_db_partition_clause()

	def _parse_restart_db_command(self):
		"""Parses a RESTART DB command"""
		# RESTART [DATABASE|DB] already matched
		self._expect_clp_string()
		self._parse_login(optional=True, allowchange=False)
		if self._match('DROP'):
			self._expect_sequence(['PENDING', 'TABLESPACES'])
			self._expect('(')
			while True:
				self._expect(TT.IDENTIFIER)
				if not self._match(','):
					break
			self._expect(')')
		self._match_sequence(['WRITE', 'RESUME'])

	def _parse_restore_db_command(self):
		"""Parses a RESTORE DB command"""
		# RESTORE [DATABASE|DB] already matched
		self._expect_clp_string()
		if self._match_one_of(['CONTINUE', 'ABORT']):
			pass
		else:
			self._parse_login(optional=True, allowchange=False)
			if self._match('TABLESPACE'):
				self._expect('(')
				self._parse_ident_list()
				self._expect(')')
				if self._match('SCHEMA'):
					if self._match('('):
						self._parse_ident_list()
						self._expect(')')
				self._match('ONLINE')
			elif (
					self._match_sequence(['HISTORY', 'FILE'])
					or self._match_sequence(['COMPRESSION', 'LIBRARY'])
					or self._match('LOGS')
				):
				self._match('ONLINE')
			elif self._match('REBUILD'):
				self._expect('WITH')
				if self._match('ALL'):
					self._expect_sequence(['TABLESPACES', 'IN'])
					self._expect_one_of(['DATABASE', 'IMAGE'])
					if self._match('EXCEPT'):
						self._expect('TABLESPACE')
						self._expect('(')
						self._parse_ident_list()
						self._expect(')')
				else:
					self._expect('TABLESPACE')
					self._expect('(')
					self._parse_ident_list()
					self._expect(')')
			if self._match('INCREMENTAL'):
				self._match_one_of(['AUTO', 'AUTOMATIC', 'ABORT'])
			if self._match('USE'):
				self._match_one_of(['TSM', 'XBSA'])
				if self._match('OPEN'):
					self._expect(TT.NUMBER)
					self._expect('SESSIONS')
				if self._match('OPTIONS'):
					self._expect_clp_string()
					# XXX Add support for @filename response file
			elif self._match('FROM'):
				self._parse_clp_string_list()
			elif self._match('LOAD'):
				self._expect_clp_string()
				if self._match('OPEN'):
					self._expect(TT.NUMBER)
					self._expect('SESSIONS')
				if self._match('OPTIONS'):
					self._expect_clp_string()
					# XXX Add support for @filename response file
			if self._match('TAKEN'):
				self._expect('AT')
				self._expect(TT.NUMBER)
			if self._match('TO'):
				self._expect_clp_string()
			elif self._match('DBPATH'):
				self._expect('ON')
				self._expect_clp_string()
			elif self._match('ON'):
				self._parse_clp_string_list()
				if self._match('DBPATH'):
					self._expect('ON')
					self._expect_clp_string()
			if self._match('INTO'):
				self._expect_clp_string()
			if self._match('LOGTARGET'):
				if self._match_one_of(['INCLUDE', 'EXCLUDE']):
					self._match('FORCE')
				else:
					self._expect_clp_string()
			if self._match('NEWLOGPATH'):
				self._expect_clp_string()
			if self._match('WITH'):
				self._expect(TT.NUMBER)
				self._expect('BUFFERS')
			if self._match('BUFFER'):
				self._expect(TT.NUMBER)
			self._match_sequence(['REPLACE', 'HISTORY', 'FILE'])
			self._match_sequence(['REPLACE', 'EXISTING'])
			if self._match('REDIRECT'):
				if self._match('GENERATE'):
					self._expect('SCRIPT')
					self._expect_clp_string()
			if self._match('PARALLELISM'):
				self._expect(TT.NUMBER)
			if self._match('COMPRLIB'):
				self._expect_clp_string()
			if self._match('COMPROPTS'):
				self._expect_clp_string()
			self._match_sequence(['WITHOUT', 'ROLLING', 'FORWARD'])
			self._match_sequence(['WITHOUT', 'PROMPTING'])

	def _parse_rewind_tape_command(self):
		"""Parses a REWIND TAPE command"""
		# REWIND TAPE already matched
		if self._match('ON'):
			self._expect_clp_string()

	def _parse_rollforward_db_command(self):
		"""Parses a ROLLFORWARD DB command"""
		# ROLLFORWARD [DATABASE|DB] already matched
		self._expect_clp_string()
		self._parse_login(optional=True, allowchange=False)
		if self._match('TO'):
			if self._match('END'):
				self._expect('OF')
				if self._expect_one_of(['LOGS', 'BACKUP']).value == 'BACKUP':
					if self._match('ON'):
						self._expect('ALL')
						self._expect_one_of(['DBPARTITIONNUMS', 'NODES'])
				else:
					self._parse_db_partitions_clause()
			else:
				self._expect(TT.NUMBER)
				if self._match('ON'):
					self._expect('ALL')
					self._expect_one_of(['DBPARTITIONNUMS', 'NODES'])
				if self._match('USING'):
					self._expect_one_of(['UTC', 'LOCAL'])
					self._expect('TIME')
			if self._match('AND'):
				self._expect_one_of(['COMPLETE', 'STOP'])
		elif self._match_one_of(['COMPLETE', 'STOP', 'CANCEL']):
			self._parse_db_partitions_clause()
		elif self._match('QUERY'):
			self._expect('STATUS')
			if self._match('USING'):
				self._expect_one_of(['UTC', 'LOCAL'])
				self._expect('TIME')
			self._parse_db_partitions_clause()
		if self._match('TABLESPACE'):
			if not self._match('ONLINE'):
				self._expect('(')
				self._parse_ident_list()
				self._expect(')')
				self._match('ONLINE')
		if self._match('OVERFLOW'):
			self._expect_sequence(['LOG', 'PATH'])
			self._expect('(')
			self._expect_clp_string()
			if self._match(','):
				while True:
					self._expect_clp_string()
					self._expect('ON')
					self._expect_one_of(['DBPARTITIONNUM', 'NODE'])
					self._expect(TT.NUMBER)
					if not self._match(','):
						break
			self._expect(')')
		self._match('NORETRIEVE')
		if self._match('RECOVER'):
			self._expect_sequence(['DROPPED', 'TABLE'])
			self._expect_clp_string()
			self._expect('TO')
			self._expect_clp_string()

	def _parse_runstats_command(self):
		"""Parses a RUNSTATS command"""

		def parse_index_options():
			"""Parses the indexing clauses of a RUNSTATS command"""
			# FOR/AND already matched
			if self._match('SAMPLED'):
				self._expect('DETAILED')
			else:
				self._match('DETAILED')
			self._expect_one_of(['INDEX', 'INDEXES'])
			if not self._match('ALL'):
				while True:
					self._parse_index_name()
					if not self._match(','):
						break

		def parse_column_options(dist):
			"""Parses column options clauses of a RUNSTATS command"""
			# ON already matched
			if (
					self._match_sequence(['ALL', 'COLUMNS', 'AND', 'COLUMNS'])
					or self._match_sequence(['KEY', 'COLUMNS', 'AND', 'COLUMNS'])
					or self._match('COLUMNS')
				):
				self._expect('(')
				while True:
					if self._match('('):
						self._parse_ident_list()
						self._expect(')')
					else:
						self._expect(TT.IDENTIFIER)
						if self._match('LIKE'):
							self._expect('STATISTICS')
					if dist:
						while self._match_one_of(['NUM_FREQVALUES', 'NUM_QUANTILES']):
							self._expect(TT.NUMBER)
					if not self._match(','):
						break
				self._expect(')')
			else:
				self._expect_one_of(['ALL', 'KEY', 'COLUMNS'])
				self._expect('COLUMNS')

		# RUNSTATS already matched
		self._expect_sequence(['ON', 'TABLE'])
		self._parse_table_name()
		if self._match_one_of(['USE', 'UNSET']):
			self._expect('PROFILE')
		else:
			if self._match('FOR'):
				parse_index_options()
				self._match_sequence(['EXCLUDING', 'XML', 'COLUMNS'])
			else:
				if self._match('ON'):
					parse_column_options(dist=False)
				if self._match('WITH'):
					self._expect('DISTRIBUTION')
					if self._match('ON'):
						parse_column_options(dist=True)
					if self._match('DEFAULT'):
						while self._match_one_of(['NUM_FREQVALUES', 'NUM_QUANTILES']):
							self._expect(TT.NUMBER)
				self._match_sequence(['EXCLUDING', 'XML', 'COLUMNS'])
				if self._match('AND'):
					parse_index_options()
			if self._match('ALLOW'):
				self._expect_one_of(['READ', 'WRITE'])
				self._expect('ACCESS')
			if self._match('TABLESAMPLE'):
				self._expect_one_of(['SYSTEM', 'BERNOULLI'])
				self._expect('(')
				self._expect(TT.NUMBER)
				self._expect(')')
				if self._match('REPEATABLE'):
					self._expect('(')
					self._expect(TT.NUMBER)
					self._expect(')')
			if self._match('SET'):
				self._expect('PROFILE')
				self._match_one_of(['NONE', 'ONLY'])
			elif self._match('UPDATE'):
				self._expect('PROFILE')
				self._match('ONLY')
		if self._match('UTIL_IMPACT_PRIORITY'):
			self._match(TT.NUMBER)

	def _parse_set_client_command(self):
		"""Parses a SET CLIENT command"""
		# SET CLIENT already matched
		if self._match('CONNECT'):
			self._expect(TT.NUMBER)
		if self._match('DISCONNECT'):
			self._expect_one_of(['EXPLICIT', 'CONDITIONAL', 'AUTOMATIC'])
		if self._match('SQLRULES'):
			self._expect_one_of(['DB2', 'STD'])
		if self._match('SYNCPOINT'):
			self._expect_one_of(['ONEPHASE', 'TWOPHASE', 'NONE'])
		if self._match('CONNECT_DBPARTITIONNUM'):
			self._expect_one_of(['CATALOG_DBPARTITIONNUM', TT.NUMBER])
		if self._match('ATTACH_DBPARTITIONNUM'):
			self._expect(TT.NUMBER)

	def _parse_set_runtime_degree_command(self):
		"""Parses a SET RUNTIME DEGREE command"""
		# SET RUNTIME DEGREE already matched
		self._expect('FOR')
		if not self._match('ALL'):
			self._expect('(')
			while True:
				self._expect(TT.NUMBER)
				if not self._match(','):
					break
			self._expect(')')
		self._expect('TO')
		self._expect(TT.NUMBER)

	def _parse_set_serveroutput_command(self):
		"""Parses a SET SERVEROUTPUT command"""
		# SET SERVEROUTPUT already matched
		self._expect_one_of(['OFF', 'ON'])

	def _parse_set_tablespace_containers_command(self):
		"""Parses a SET TABLESPACE CONTAINERS command"""
		# SET TABLESPACE CONTAINERS already matched
		self._expect('FOR')
		self._expect(TT.NUMBER)
		if self._match_one_of(['REPLAY', 'IGNORE']):
			self._expect_sequence(['ROLLFORWARD', 'CONTAINER', 'OPERATIONS'])
		self._expect('USING')
		if not self._match_sequence(['AUTOMATIC', 'STORAGE']):
			self._expect('(')
			while True:
				if self._expect_one_of(['FILE', 'DEVICE', 'PATH']).value == 'PATH':
					self._expect_clp_string()
				else:
					self._expect_clp_string()
					self._expect(TT.NUMBER)
				if not self._match(','):
					break
			self._expect(')')

	def _parse_set_tape_position_command(self):
		"""Parses a SET TAPE POSITION command"""
		# SET TAPE POSITION already matched
		if self._match('ON'):
			self._expect_clp_string()
		self._expect('TO')
		self._expect(TT.NUMBER)

	def _parse_set_util_impact_priority_command(self):
		"""Parses a SET UTIL_IMPACT_PRIORITY command"""
		# SET UTIL_IMPACT_PRIORITY already matched
		self._expect('FOR')
		self._expect(TT.NUMBER)
		self._expect('TO')
		self._expect(TT.NUMBER)

	def _parse_set_workload_command(self):
		"""Parses a SET WORKLOAD command"""
		# SET WORKLOAD already matched
		self._expect('TO')
		self._expect_one_of(['AUTOMATIC', 'SYSDEFAULTADMWORKLOAD'])

	def _parse_set_write_command(self):
		"""Parses a SET WRITE command"""
		# SET WRITE already matched
		self._expect_one_of(['SUSPEND', 'RESUME'])
		self._expect('FOR')
		self._expect_one_of(['DATABASE', 'DB'])

	def _parse_start_dbm_command(self):
		"""Parses a START DBM command"""
		# START [DATABASE MANAGER|DB MANAGER|DBM] already matched
		if self._match('REMOTE'):
			self._match('INSTANCE')
			self._expect_clp_string()
			self._expect_one_of(['ADMINNODE', 'HOSTNAME'])
			self._expect_clp_string()
			self._parse_login(optional=False, allowchange=False)
		if self._match('ADMIN'):
			self._expect('MODE')
			if self._match_one_of(['USER', 'GROUP']):
				self._expect(TT.IDENTIFIER)
			self._match_sequence(['RESTRICTED', 'ACCESS'])
		if self._match('PROFILE'):
			self._expect_clp_string()
		if self._match_one_of(['DBPARTITIONNUM', 'NODE']):
			self._expect(TT.NUMBER)
			if self._match('ADD'):
				self._expect_one_of(['DBPARTITIONNUM', 'NODE'])
				self._expect('HOSTNAME')
				self._expect_clp_string()
				self._expect('PORT')
				self._expect(TT.NUMBER)
				if self._match('COMPUTER'):
					self._expect_clp_string()
				self._parse_login(optional=True, allowchange=False)
				if self._match('NETNAME'):
					self._expect_clp_string()
				if self._match('LIKE'):
					self._expect_one_of(['DBPARTITIONNUM', 'NODE'])
					self._expect(TT.NUMBER)
				elif self._match('WITHOUT'):
					self._expect('TABLESPACES')
			elif self._match('RESTART'):
				if self._match('HOSTNAME'):
					self._expect_clp_string()
				if self._match('PORT'):
					self._expect(TT.NUMBER)
				if self._match('COMPUTER'):
					self._expect_clp_string()
				self._parse_login(optional=True, allowchange=False)
				if self._match('NETNAME'):
					self._expect_clp_string()
			elif self._match('STANDALONE'):
				pass

	def _parse_start_hadr_command(self):
		"""Parses a START HADR command"""
		# START HADR already matched
		self._expect('ON')
		self._expect_one_of(['DATABASE', 'DB'])
		self._expect_clp_string()
		self._parse_login(optional=True, allowchange=False)
		self._expect('AS')
		if self._expect_one_of(['PRIMARY', 'STANDBY']).value == 'PRIMARY':
			self._match_sequence(['BY', 'FORCE'])

	def _parse_stop_dbm_command(self):
		"""Parses a STOP DBM command"""
		# STOP [DATABASE MANAGER|DB MANAGER|DBM] already matched
		if self._match('PROFILE'):
			self._expect_clp_string()
		if self._match('DROP'):
			self._expect_one_of(['DBPARTITIONNUM', 'NODE'])
			self._expect(TT.NUMBER)
		else:
			self._match('FORCE')
			if self._match_one_of(['DBPARTITIONNUM', 'NODE']):
				self._expect(TT.NUMBER)

	def _parse_stop_hadr_command(self):
		"""Parses a STOP HADR command"""
		# STOP HADR already matched
		self._expect('ON')
		self._expect_one_of(['DATABASE', 'DB'])
		self._expect_clp_string()
		self._parse_login(optional=True, allowchange=False)

	def _parse_takeover_hadr_command(self):
		"""Parses a TAKEOVER HADR command"""
		# TAKEOVER HADR already matched
		self._expect('ON')
		self._expect_one_of(['DATABASE', 'DB'])
		self._expect_clp_string()
		self._parse_login(optional=True, allowchange=False)
		if self._match_sequence(['BY', 'FORCE']):
			self._match_sequence(['PEER', 'WINDOW', 'ONLY'])

	def _parse_terminate_command(self):
		"""Parses a TERMINATE command"""
		# TERMINATE already matched
		pass

	def _parse_uncatalog_command(self):
		"""Parses an UNCATALOG command"""
		if self._match_one_of(['DATABASE', 'DB', 'NODE']):
			self._expect_clp_string()
		elif self._match('DCS'):
			self._expect_one_of(['DATABASE', 'DB'])
			self._expect_clp_string()
		elif self._match('LDAP'):
			self._expect_one_of(['DATABASE', 'DB', 'NODE'])
			self._expect_clp_string()
			self._parse_login(optional=True, allowchange=False)
		elif self._match_one_of(['USER', 'SYSTEM']):
			self._expect_sequence(['ODBC', 'DATA', 'SOURCE'])
			self._expect_clp_string()
		elif self._match('ODBC'):
			self._expect_sequence(['DATA', 'SOURCE'])
			self._expect_clp_string()
		else:
			self._expected_one_of([
				'DATABASE',
				'DB',
				'NODE',
				'DCS',
				'LDAP',
				'USER',
				'SYSTEM',
				'ODBC',
			])

	def _parse_unquiesce_command(self):
		"""Parses an UNQUIESCE command"""
		# UNQUIESCE already matched
		if self._match('INSTANCE'):
			self._expect_clp_string()
		elif self._match_one_of(['DATABASE', 'DB']):
			pass
		else:
			self._expected_one_of(['DATABASE', 'DB', 'INSTANCE'])

	def _parse_update_admin_cfg_command(self):
		"""Parses an UPDATE ADMIN CFG command"""
		# UPDATE ADMIN CONFIGURATION|CONFIG|CFG already matched
		self._expect('USING')
		while True:
			self._expect(TT.IDENTIFIER)
			self._expect_one_of([TT.NUMBER, TT.STRING, TT.IDENTIFIER])
			if self._peek_one_of(['FOR', TT.TERMINATOR, TT.EOF]):
				break
		if self._match_sequence(['FOR', 'NODE']):
			self._expect_clp_string()
			self._parse_login(optional=True, allowchange=False)

	def _parse_update_alert_cfg_command(self):
		"""Parses an UPDATE ALERT CFG command"""
		# UPDATE ALERT CONFIGURATION|CONFIG|CFG already matched
		self._expect('FOR')
		if (
				self._match_sequence(['DATABASE', 'MANAGER'])
				or self._match_sequence(['DB', 'MANAGER'])
				or self._match_one_of(['DBM', 'CONTAINERS', 'DATABASES', 'TABLESPACES'])
			):
			pass
		elif (
				self._match_sequence(['CONTAINER', TT.IDENTIFIER, 'FOR', TT.IDENTIFIER])
				or self._match_sequence('TABLESPACE', TT.IDENTIFIER)
				or self._match('DATABASE')
			):
			self._expect('ON')
			self._expect_clp_string()
		if self._match('USING'):
			self._expect_clp_string()
		if self._match('SET'):
			while True:
				self._expect_one_of(['ALARM', 'WARNING', 'SENSITIVITY', 'ACTIONSENABLED', 'THRESHOLDSCHECKED'])
				self._expect_one_of([TT.NUMBER, 'YES', 'NO'])
				if not self._match(','):
					break
		elif self._match('ADD'):
			while True:
				self._expect_one_of(['SCRIPT', 'TASK'])
				self._expect_clp_string()
				self._expect('TYPE')
				if self._match('DB2'):
					if (
							self._match_sequence(['STATEMENT', 'TERMINATION', 'CHARACTER'])
							or self._match_sequence(['STMT', 'TERM', 'CHAR'])
							or self._match_sequence(['TERM', 'CHAR'])
						):
						self._expect_clp_string()
				elif self._match_sequence(['OPERATING', 'SYSTEM']) or self._match('OS'):
					if (
							self._match_sequence(['COMMAND', 'LINE', 'PARAMETERS'])
							or self._match('PARMS')
						):
						self._expect_clp_string()
				else:
					self._expected_one_of(['DB2', 'OS', 'OPERATING'])
				self._expect_sequence(['WORKING', 'DIRECTORY'])
				self._expect_clp_string()
				self._expect('ON')
				if self._expect_one_of(['WARNING', 'ALARM', 'ALLALERT', 'ATTENTION']).value == 'ATTENTION':
					self._expect(TT.NUMBER)
				if self._match('ON'):
					self._expect_clp_string()
				self._parse_login(optional=False, allowchange=False)
				if not self._match(','):
					break
		else:
			if self._expect_one_of(['SET', 'ADD', 'UPDATE', 'DELETE']).value == 'UPDATE':
				update = True
			self._expect('ACTION')
			while True:
				self._expect_one_of(['SCRIPT', 'TASK'])
				self._expect_clp_string()
				self._expect('ON')
				if self._expect_one_of(['WARNING', 'ALARM', 'ALLALERT', 'ATTENTION']).value == 'ATTENTION':
					self._expect(TT.NUMBER)
				if update:
					while True:
						self._expect('SET')
						self._expect_one_of(['ALARM', 'WARNING', 'SENSITIVITY', 'ACTIONSENABLED', 'THRESHOLDSCHECKED'])
						self._expect_one_of([TT.NUMBER, 'YES', 'NO'])
						if not self._match(','):
							break
				if not self._match(','):
					break

	def _parse_update_alternate_server_command(self):
		"""Parses an UPDATE ALTERNATE SERVER command"""
		# UPDATE ALTERNATE SERVER already matched
		self._expect('FOR')
		if self._expect_one_of(['LDAP', 'DATABASE', 'DB']).value == 'LDAP':
			self._expect_one_of(['DATABASE', 'DB'])
			self._expect_clp_string()
			self._expect('USING')
			self._expect_one_of(['NODE', 'GWNODE'])
			self._expect_clp_string()
			self._parse_login(optional=True, allowchange=False)
		else:
			self._expect_clp_string()
			self._expect_sequence(['USING', 'HOSTNAME'])
			self._expect_clp_string()
			self._expect('PORT')
			self._expect_clp_string()

	def _parse_update_cli_cfg_command(self):
		"""Parses an UPDATE CLI CFG command"""
		# UPDATE CLI CONFIGURATION|CONFIG|CFG already matched
		if self._match('AT'):
			self._expect_one_of(['GLOBAL', 'USER'])
			self._expect('LEVEL')
		self._expect_sequence(['FOR', 'SECTION'])
		self._expect_clp_string()
		self._expect('USING')
		while True:
			self._expect(TT.IDENTIFIER)
			self._expect_one_of([TT.NUMBER, TT.STRING, TT.IDENTIFIER])
			if self._peek_one_of([TT.TERMINATOR, TT.EOF]):
				break

	def _parse_update_command_options_command(self):
		"""Parses an UPDATE COMMAND OPTIONS command"""
		# UPDATE COMMAND OPTIONS already matched
		self._expect('USING')
		while True:
			option = self._expect_one_of([
				'A', 'C', 'D', 'E', 'I', 'L', 'M', 'N',
				'O', 'P', 'Q', 'R', 'S', 'V', 'W', 'Z',
			]).value
			value = self._expect_one_of(['ON', 'OFF']).value
			if option in ('E', 'L', 'R', 'Z') and value == 'ON':
				self._expect_clp_string()
			if self._peek_one_of([TT.TERMINATOR, TT.EOF]):
				break

	def _parse_update_contact_command(self):
		"""Parses an UPDATE CONTACT command"""
		# UPDATE CONTACT already matched
		self._expect_clp_string()
		self._expect('USING')
		while True:
			if self._match('ADDRESS'):
				self._expect_clp_string()
			elif self._match('TYPE'):
				self._expect_one_of(['EMAIL', 'PAGE'])
			elif self._match('MAXPAGELEN'):
				self._expect(TT.NUMBER)
			elif self._match('DESCRIPTION'):
				self._expect_clp_string()
			else:
				self._expected_one_of(['ADDRESS', 'TYPE', 'MAXPAGELEN', 'DESCRIPTION'])
			if not self._match(','):
				break

	def _parse_update_contactgroup_command(self):
		"""Parses an UPDATE CONTACTGROUP command"""
		# UPDATE CONTACTGROUP already matched
		self._expect_clp_string()
		self._expect('(')
		while True:
			self._expect_one_of(['ADD', 'DROP'])
			self._expect_one_of(['CONTACT', 'GROUP'])
			self._expect_clp_string()
			if not self._match(','):
				break
		self._expect(')')
		if self._match('DESCRIPTION'):
			self._expect_clp_string()

	def _parse_update_db_cfg_command(self):
		"""Parses an UPDATE DB CFG command"""
		# UPDATE DATABASE|DB CONFIGURATION|CONFIG|CFG already matched
		if self._match('FOR'):
			self._expect_clp_string()
		if self._match_one_of(['DBPARTITIONNUM', 'NODE']):
			self._expect(TT.NUMBER)
		self._expect('USING')
		while True:
			self._expect(TT.IDENTIFIER)
			if self._match_one_of(['AUTOMATIC', 'MANUAL']):
				pass
			else:
				self._expect_one_of([TT.NUMBER, TT.STRING, TT.IDENTIFIER])
				self._match('AUTOMATIC')
			if self._peek_one_of(['IMMEDIATE', 'DEFERRED', TT.TERMINATOR, TT.EOF]):
				break
		self._match_one_of(['IMMEDIATE', 'DEFERRED'])

	def _parse_update_dbm_cfg_command(self):
		"""Parses an UPDATE DBM CFG command"""
		# UPDATE DATABASE MANAGER|DB MANAGER|DBM CONFIGURATION|CONFIG|CFG already matched
		self._expect('USING')
		while True:
			self._expect(TT.IDENTIFIER)
			if self._match_one_of(['AUTOMATIC', 'MANUAL']):
				pass
			else:
				self._expect_one_of([TT.NUMBER, TT.STRING, TT.IDENTIFIER])
				self._match('AUTOMATIC')
			if self._peek_one_of(['IMMEDIATE', 'DEFERRED', TT.TERMINATOR, TT.EOF]):
				break
		self._match_one_of(['IMMEDIATE', 'DEFERRED'])

	def _parse_update_notification_list_command(self):
		"""Parses an UPDATE NOTIFICATION LIST command"""
		# UPDATE [HEALTH] NOTIFICATION [CONTACT] LIST already matched
		first = True
		while True:
			if not self._match_one_of(['ADD', 'DROP']):
				if not first:
					break
				else:
					self._expected_one_of(['ADD', 'DROP'])
			first = False
			self._expect_one_of(['CONTACT', 'GROUP'])
			self._expect_clp_string()

	def _parse_update_history_command(self):
		"""Parses an UPDATE HISTORY command"""
		# UPDATE HISTORY already matched
		self._expect_one_of(['FOR', 'EID'])
		self._expect(TT.NUMBER)
		self._expect('WITH')
		if self._match('LOCATION'):
			self._expect_clp_string()
			self._expect_sequence(['DEVICE', 'TYPE'])
			self._expect_one_of(['D', 'K', 'T', 'A', 'F', 'U', 'P', 'N', 'X', 'Q', 'O'])
		elif self._match('COMMENT'):
			self._expect_clp_string()
		elif self._match('STATUS'):
			self._expect_one_of(['A', 'I', 'E', 'D', 'X'])
		else:
			self._expected_one_of(['LOCATION', 'COMMENT', 'STATUS'])

	def _parse_update_ldap_node_command(self):
		"""Parses an UPDATE LDAP NODE command"""
		# UPDATE LDAP NODE already matched
		self._expect_clp_string()
		if self._match('HOSTNAME'):
			self._expect_clp_string()
		if self._match('SVCENAME'):
			self._expect_clp_string()
		if self._match('WITH'):
			self._expect_clp_string()
		self._parse_login(optional=True, allowchange=False)

	def _parse_update_monitor_switches_command(self):
		"""Parses an UPDATE MONITOR SWITCHES command"""
		# UPDATE MONITOR SWITCHES already matched
		self._expect('USING')
		first = True
		while True:
			if not self._match_one_of(['BUFFERPOOL', 'LOCK', 'SORT', 'STATEMENT', 'TABLE', 'TIMESTAMP', 'UOW']):
				if not first:
					break
				else:
					self._expected_one_of(['BUFFERPOOL', 'LOCK', 'SORT', 'STATEMENT', 'TABLE', 'TIMESTAMP', 'UOW'])
			first = False
			self._expect_one_of(['OFF', 'ON'])
		self._parse_db_partition_clause()

	def _parse_update_xmlschema_command(self):
		"""Parses an UPDATE XMLSCHEMA command"""
		# UPDATE XMLSCHEMA already matched
		self._parse_subschema_name()
		self._expect('WITH')
		self._parse_subschema_name()
		self._match_sequence(['DROP', 'NEW', 'SCHEMA'])

	def _parse_upgrade_db_command(self):
		"""Parses an UPGRADE DB command"""
		# UPGRADE DATABASE|DB already matched
		self._expect_clp_string()
		self._parse_login(optional=True, allowchange=False)

	# COMPOUND COMMANDS ######################################################

	def _parse_command(self):
		"""Parses a top-level CLP command in a DB2 script"""
		# Ambiguity: Some CLP commands start with the same keywords as SQL
		# statements (e.g. CREATE DATABASE and CREATE DATABASE PARTITION
		# GROUP).  Attempt to parse the statement as a CLP statement, rewind
		# and try to parse as an SQL command if that fails. This is one reason
		# for the message "The command was processed as an SQL statement
		# because it was not a valid Command Line Processor command" in DB2;
		# there are two very different and separate parsers, one for CLP which
		# tries to parse a command first, which defers to the secondary SQL
		# parser if it fails.
		self._save_state()
		try:
			if self._match('ACTIVATE'):
				self._expect_one_of(['DATABASE', 'DB'])
				self._parse_activate_database_command()
			elif self._match('ATTACH'):
				self._parse_attach_command()
			elif self._match('AUTOCONFIGURE'):
				self._parse_autoconfigure_command()
			elif self._match('BACKUP'):
				self._expect_one_of(['DATABASE', 'DB'])
				self._parse_backup_command()
			elif self._match('CATALOG'):
				self._parse_catalog_command()
			elif self._match('CONNECT'):
				self._parse_connect_command()
			elif self._match('CREATE'):
				if self._match_one_of(['DATABASE', 'DB']):
					if self._match('PARTITION'):
						raise ParseBacktrack()
					self._parse_create_database_command()
				elif self._match('TOOLS'):
					self._expect('CATALOG')
					self._parse_create_tools_catalog_command()
				else:
					raise ParseBacktrack()
			elif self._match('DEACTIVATE'):
				self._expect_one_of(['DATABASE', 'DB'])
				self._parse_deactivate_database_command()
			elif self._match('DETACH'):
				self._parse_detach_command()
			elif self._match('DISCONNECT'):
				self._parse_disconnect_command()
			elif self._match('DROP'):
				if self._match_one_of(['DATABASE', 'DB']):
					self._parse_drop_database_command()
				elif self._match('TOOLS'):
					self._expect('CATALOG')
					self._parse_drop_tools_catalog_command()
				else:
					raise ParseBacktrack()
			elif self._match('ECHO'):
				self._parse_echo_command()
			elif self._match('EXPORT'):
				self._parse_export_command()
			elif self._match('FORCE'):
				self._expect('APPLICATION')
				self._parse_force_application_command()
			elif self._match('GET'):
				if self._match('ADMIN'):
					self._expect_one_of(['CONFIGURATION', 'CONFIG', 'CFG'])
					self._parse_get_admin_cfg_command()
				elif self._match('ALERT'):
					self._expect_one_of(['CONFIGURATION', 'CONFIG', 'CFG'])
					self._parse_get_alert_cfg_command()
				elif self._match('CLI'):
					self._expect_one_of(['CONFIGURATION', 'CONFIG', 'CFG'])
					self._parse_get_cli_cfg_command()
				elif self._match('CONNECTION'):
					self._expect('STATE')
					self._parse_get_connection_state_command()
				elif self._match('CONTACTGROUP'):
					self._parse_get_contactgroup_command()
				elif self._match('CONTACTGROUPS'):
					self._parse_get_contactgroups_command()
				elif self._match('CONTACTS'):
					self._parse_get_contacts_command()
				elif self._match_one_of(['DATABASE', 'DB']):
					if self._match_one_of(['CONFIGURATION', 'CONFIG', 'CFG']):
						self._parse_get_db_cfg_command()
					elif self._match('MANAGER'):
						if self._match_one_of(['CONFIGURATION', 'CONFIG', 'CFG']):
							self._parse_get_dbm_cfg_command()
						elif self._match_sequence(['MONITOR', 'SWITCHES']):
							self._parse_get_dbm_monitor_switches_command()
						else:
							self._expected_one_of(['CONFIGURATION', 'CONFIG', 'CFG', 'MONITOR'])
				elif self._match('DBM'):
					if self._match_one_of(['CONFIGURATION', 'CONFIG', 'CFG']):
						self._parse_get_dbm_cfg_command()
					elif self._match_sequence(['MONITOR', 'SWITCHES']):
						self._parse_get_dbm_monitor_switches_command()
					else:
						self._expected_one_of(['CONFIGURATION', 'CONFIG', 'CFG', 'MONITOR'])
				elif self._match('DESCRIPTION'):
					self._expect_sequence(['FOR', 'HEALTH', 'INDICATOR'])
					self._parse_get_description_for_health_indicator_command()
				elif self._match('HEALTH'):
					if self._match('NOTIFICATION'):
						self._expect_sequence(['CONTACT', 'LIST'])
						self._parse_get_notification_list_command()
					elif self._match('SNAPSHOT'):
						self._parse_get_health_snapshot_command()
					else:
						self._expected_one_of(['NOTIFICATION', 'SNAPSHOT'])
				elif self._match('INSTANCE'):
					self._parse_get_instance_command()
				elif self._match('MONITOR'):
					self._expect('SWITCHES')
					self._parse_get_monitor_switches_command()
				elif self._match('NOTIFICATION'):
					self._expect('LIST')
					self._parse_get_notification_list_command()
				elif self._match('RECOMMENDATIONS'):
					self._expect_sequence(['FOR', 'HEALTH', 'INDICATOR'])
					self._parse_get_recommendations_for_health_indicator_command()
				elif self._match('ROUTINE'):
					self._parse_get_routine_command()
				elif self._match('SNAPSHOT'):
					self._parse_get_snapshot_command()
				else:
					raise ParseBacktrack()
			elif self._match('IMPORT'):
				self._parse_import_command()
			elif self._match('INITIALIZE'):
				self._expect('TAPE')
				self._parse_initialize_tape_command()
			elif self._match('INSPECT'):
				self._parse_inspect_command()
			elif self._match('INSTANCE'):
				self._parse_instance_command()
			elif self._match('LIST'):
				if self._match('ACTIVE'):
					self._expect('DATABASES')
					self._parse_list_active_databases_command()
				elif self._match('ADMIN'):
					self._expect_sequence(['NODE', 'DIRECTORY'])
					self._parse_list_node_directory_command()
				elif self._match('APPLICATIONS'):
					self._parse_list_applications_command()
				elif self._match('COMMAND'):
					self._expect('OPTIONS')
					self._parse_list_command_options_command()
				elif self._match_one_of(['DATABASE', 'DB']):
					if self._match('DIRECTORY'):
						self._parse_list_db_directory_command()
					elif self._match('PARTITION'):
						self._expect('GROUPS')
						self._parse_list_database_partition_groups_command()
					else:
						self._expected_one_of(['DIRECTORY', 'PARTITION'])
				elif self._match_one_of(['DBPARTITIONNUMS', 'NODES']):
					self._parse_list_nodes_command()
				elif self._match('DCS'):
					if self._match('APPLICATIONS'):
						self._parse_list_dcs_applications_command()
					elif self._match('DIRECTORY'):
						self._parse_list_dcs_directory_command()
					else:
						self._expected_one_of(['APPLICATIONS', 'DIRECTORY'])
				elif self._match('DRDA'):
					self._expect_sequence(['INDOUBT', 'TRANSACTIONS'])
					self._parse_list_drda_indoubt_transactions_command()
				elif self._match('HISTORY'):
					self._parse_list_history_command()
				elif self._match('INDOUBT'):
					self._expect('TRANSACTIONS')
					self._parse_list_indoubt_transactions_command()
				elif self._match('NODE'):
					self._expect('DIRECTORY')
					self._parse_list_node_directory_command()
				elif self._match_one_of(['USER', 'SYSTEM']):
					self._expect_sequence(['ODBC', 'DATA', 'SOURCES'])
					self._parse_list_odbc_data_sources_command()
				elif self._match('ODBC'):
					self._expect_sequence(['DATA', 'SOURCES'])
					self._parse_list_odbc_data_sources_command()
				elif self._match_one_of(['PACKAGES', 'TABLES']):
					self._parse_list_tables_command(self)
				elif self._match('TABLESPACES'):
					if self._match('CONTAINERS'):
						self._parse_list_tablespace_containers_command()
					else:
						self._parse_list_tablespaces_command()
				elif self._match('UTILITIES'):
					self._parse_list_utilities_command()
				else:
					self._expected_one_of([
						'ACTIVE',
						'ADMIN',
						'APPLICATIONS',
						'COMMAND',
						'DATABASE',
						'DB',
						'DBPARTITIONNUMS',
						'DCS',
						'DRDA',
						'HISTORY',
						'INDOUBT',
						'NODE',
						'NODES',
						'ODBC',
						'PACKAGES',
						'SYSTEM',
						'TABLES',
						'TABLESPACES',
						'USER',
						'UTILITIES',
					])
			elif self._match('LOAD'):
				if self._match('QUERY'):
					self._parse_load_query_command()
				else:
					self._parse_load_command()
			elif self._match('MIGRATE'):
				self._expect_one_of(['DATABASE', 'DB'])
				self._parse_migrate_db_command()
			elif self._match('ON'):
				self._parse_on_command()
			elif self._match('PING'):
				self._parse_ping_command()
			elif self._match_one_of(['PRECOMPILE', 'PREP']):
				self._parse_precompile_command()
			elif self._match('PRUNE'):
				if self._match('HISTORY'):
					self._parse_prune_history_command()
				elif self._match('LOGFILE'):
					self._parse_prune_logfile_command()
				else:
					self._expected_one_of(['HISTORY', 'LOGFILE'])
			elif self._match('PUT'):
				self._expect('ROUTINE')
				self._parse_put_routine_command()
			elif self._match('QUERY'):
				self._expect('CLIENT')
				self._parse_query_client_command()
			elif self._match('QUIESCE'):
				if self._match('TABLESPACES'):
					self._parse_quiesce_tablespaces_command()
				else:
					self._parse_quiesce_command()
			elif self._match('QUIT'):
				self._parse_quit_command()
			elif self._match('REBIND'):
				self._parse_rebind_command()
			elif self._match('RECOVER'):
				self._expect_one_of(['DATABASE', 'DB'])
				self._parse_recover_db_command()
			elif self._match('REDISTRIBUTE'):
				self._expect_sequence(['DATABASE', 'PARTITION', 'GROUP'])
				self._parse_redistribute_database_partition_group_command()
			elif self._match('REFRESH'):
				if self._match('LDAP'):
					self._parse_refresh_ldap_command()
				else:
					raise ParseBacktrack()
			elif self._match('REGISTER'):
				if self._match('XMLSCHEMA'):
					self._parse_register_xmlschema_command()
				elif self._match('XSROBJECT'):
					self._parse_register_xsrobject_command()
				else:
					self._parse_register_command()
			elif self._match('REORG'):
				self._parse_reorg_command()
			elif self._match('REORGCHK'):
				self._parse_reorgchk_command()
			elif self._match('RESET'):
				if self._match('ADMIN'):
					self._expect_one_of(['CONFIGURATION', 'CONFIG', 'CFG'])
					self._parse_reset_admin_cfg_command()
				elif self._match('ALERT'):
					self._expect_one_of(['CONFIGURATION', 'CONFIG', 'CFG'])
					self._parse_reset_alert_cfg_command()
				elif self._match_one_of(['DATABASE', 'DB']):
					if self._match('MANAGER'):
						self._expect_one_of(['CONFIGURATION', 'CONFIG', 'CFG'])
						self._parse_reset_dbm_cfg_command()
					else:
						self._expect_one_of(['CONFIGURATION', 'CONFIG', 'CFG'])
						self._parse_reset_db_cfg_command()
				elif self._match('DBM'):
					self._expect_one_of(['CONFIGURATION', 'CONFIG', 'CFG'])
					self._parse_reset_dbm_cfg_command()
				elif self._match('MONITOR'):
					self._parse_reset_monitor_command()
				else:
					self._expected_one_of([
						'ADMIN',
						'ALERT',
						'DATABASE',
						'DB',
						'DBM',
						'MONITOR',
					])
			elif self._match('RESTART'):
				self._expect_one_of(['DATABASE', 'DB'])
				self._parse_restart_db_command()
			elif self._match('RESTORE'):
				self._expect_one_of(['DATABASE', 'DB'])
				self._parse_restore_db_command()
			elif self._match('REWIND'):
				self._expect('TAPE')
				self._parse_rewind_tape_command()
			elif self._match('ROLLFORWARD'):
				self._expect_one_of(['DATABASE', 'DB'])
				self._parse_rollforward_db_command()
			elif self._match('RUNSTATS'):
				self._parse_runstats_command()
			elif self._match('SET'):
				if self._match('CLIENT'):
					self._parse_set_client_command()
				elif self._match('RUNTIME'):
					self._expect('DEGREE')
					self._parse_set_runtime_degree_command()
				elif self._match('SERVEROUTPUT'):
					self._parse_set_serveroutput_command()
				elif self._match('TABLESPACE'):
					self._expect('CONTAINERS')
					self._parse_set_tablespace_containers_command()
				elif self._match('TAPE'):
					self._expect('POSITION')
					self._parse_set_tape_position_command()
				elif self._match('UTIL_IMPACT_PRIORITY'):
					self._parse_set_util_impact_priority_command()
				elif self._match('WORKLOAD'):
					self._parse_set_workload_command()
				else:
					raise ParseBacktrack()
			elif self._match('START'):
				if self._match('HADR'):
					self._parse_start_hadr_command()
				elif self._match_one_of(['DATABASE', 'DB']):
					self._expect('MANAGER')
					self._parse_start_dbm_command()
				elif self._match('DBM'):
					self._parse_start_dbm_command()
				else:
					self._expected_one_of(['HADR', 'DATABASE', 'DB', 'DBM'])
			elif self._match('STOP'):
				if self._match('HADR'):
					self._parse_stop_hadr_command()
				elif self._match_one_of(['DATABASE', 'DB']):
					self._expect('MANAGER')
					self._parse_stop_dbm_command()
				elif self._match('DBM'):
					self._parse_stop_dbm_command()
				else:
					self._expected_one_of(['HADR', 'DATABASE', 'DB', 'DBM'])
			elif self._match('TAKEOVER'):
				self._parse_takeover_hadr_command()
			elif self._match('TERMINATE'):
				self._parse_terminate_command()
			elif self._match('UNCATALOG'):
				self._parse_uncatalog_command()
			elif self._match('UNQUIESCE'):
				self._parse_unquiesce_command()
			elif self._match('UPDATE'):
				if self._match('ADMIN'):
					self._expect_one_of(['CONFIGURATION', 'CONFIG', 'CFG'])
					self._parse_update_admin_cfg_command()
				elif self._match('ALERT'):
					self._expect_one_of(['CONFIGURATION', 'CONFIG', 'CFG'])
					self._parse_update_alert_cfg_command()
				elif self._match_sequence(['ALTERNATE', 'SERVER']):
					self._parse_update_alternate_server_command()
				elif self._match('CLI'):
					self._expect_one_of(['CONFIGURATION', 'CONFIG', 'CFG'])
					self._parse_update_cli_cfg_command()
				elif self._match_sequence(['COMMAND', 'OPTIONS']):
					self._parse_update_command_options_command()
				elif self._match('CONTACT'):
					self._parse_update_contact_command()
				elif self._match('CONTACTGROUP'):
					self._parse_update_contactgroup_command()
				elif self._match_one_of(['DATABASE', 'DB']):
					if self._match('MANAGER'):
						self._expect_one_of(['CONFIGURATION', 'CONFIG', 'CFG'])
						self._parse_update_dbm_cfg_command()
					else:
						self._expect_one_of(['CONFIGURATION', 'CONFIG', 'CFG'])
						self._parse_update_db_cfg_command()
				elif self._match('DBM'):
					self._expect_one_of(['CONFIGURATION', 'CONFIG', 'CFG'])
					self._parse_update_dbm_cfg_command()
				elif (
						self._match_sequence(['HEALTH', 'NOTIFICATION', 'CONTACT', 'LIST'])
						or self._match_sequence(['NOTIFICATION', 'LIST'])
					):
					self._parse_update_notification_list_command()
				elif self._match('HISTORY'):
					self._parse_update_history_command()
				elif self._match_sequence(['LDAP', 'NODE']):
					self._parse_update_ldap_node_command()
				elif self._match_sequence(['MONITOR', 'SWITCHES']):
					self._parse_update_monitor_switches_command()
				elif self._match('XMLSCHEMA'):
					self._parse_update_xmlschema_command()
				else:
					raise ParseBacktrack()
			elif self._match('UPGRADE'):
				self._expect_one_of(['DATABASE', 'DB'])
				self._parse_upgrade_db_command()
			else:
				raise ParseBacktrack()
		except ParseBacktrack:
			self._restore_state()
			self._parse_statement()
		else:
			self._forget_state()

	def _parse_top(self):
		# Override _parse_top to make a CLP command the top of the parse tree
		self._parse_command()

	def _parse_init(self, tokens):
		# Override _parse_init to set up the output lists (produces, consumes,
		# etc.)
		super(DB2ZOSScriptParser, self)._parse_init(tokens)
		self.produces = []
		self.consumes = []
		self.connections = []
		self.current_connection = None
		self.current_user = None

	def _save_state(self):
		# Override _save_state to save the state of the output lists (produces,
		# consumes, etc.)
		self._states.append((
			self._index,
			self._level,
			len(self._output),
			self.current_schema,
			self.current_user,
			self.current_connection,
			len(self.produces),
			len(self.consumes),
			len(self.connections),
		))

	def _restore_state(self):
		# Override _restore_state to restore the state of the output lists
		# (produces, consumes, etc.)
		(
			self._index,
			self._level,
			output_len,
			self.current_schema,
			self.current_user,
			self.current_connection,
			produces_len,
			consumes_len,
			logins_len,
		) = self._states.pop()
		del self.produces[produces_len:]
		del self.consumes[consumes_len:]
		del self.connections[logins_len:]
		del self._output[output_len:]

