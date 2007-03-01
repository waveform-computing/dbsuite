# $Header$
# vim: set noet sw=4 ts=4:

"""Implements a generic class for highlighting SQL with markup.

This unit defines a base class for converting an SQL string into a markup
language, e.g. HTML. Output modules can sub-class this to generate their own
particular markup.

The class utilizes the tokenizer and (optionally) formatter classes from the
sql module to parse the SQL and defines various handler stubs for converting
the result tokens into markup.
"""

from sql.tokenizer import *
from sql.formatter import *

class SQLHighlighter(object):
	def __init__(self):
		"""Initializes an instance of the class."""
		super(SQLHighlighter, self).__init__()
		self.tokenizer = DB2UDBSQLTokenizer()
		self.formatter = SQLFormatter()
	
	def format_line(self, index, line):
		"""Stub handler for a line of tokens"""
		return ''.join([self.format_token(token) for token in line])

	def format_token(self, token):
		"""Stub handler for a token"""
		(_, _, source, _, _) = token
		return source
	
	def parse(self, sql, terminator=';', splitlines=False):
		self.tokenizer.newline_split = splitlines
		tokens = self.formatter.parse(self.tokenizer.parse(sql, terminator))
		if splitlines:
			return [self.format_line(index + 1, line) for (index, line) in enumerate(tokens)]
		else:
			return [self.format_token(token) for token in tokens]
	
	def parse_prototype(self, sql):
		self.tokenizer.newline_split = False
		tokens = self.formatter.parseRoutinePrototype(self.tokenizer.parse(sql))
		return [self.format_token(token) for token in tokens]
	
	def parse_to_string(self, sql, terminator=';', splitlines=False):
		if splitlines:
			return ''.join(self.parse(sql, terminator, True))
		else:
			return ''.join(self.parse(sql, terminator))
	
	def parse_prototype_to_string(self, sql):
		return ''.join(self.parse_prototype(sql))
