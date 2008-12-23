# vim: set noet sw=4 ts=4:

"""Provides a set of base classes for TeX based output plugins

This package defines a set of utility classes which make it easier to construct
output plugins capable of producing TeX documents.
"""

import pdb
import os
import datetime
import logging

from operator import attrgetter
from db2makedoc.main import __version__
from db2makedoc.astex import tex, xml, TeXFactory
from db2makedoc.highlighters import CommentHighlighter, SQLHighlighter
from db2makedoc.graph import Graph, Node, Edge, Cluster
from db2makedoc.sql.formatter import (
	ERROR, COMMENT, KEYWORD, IDENTIFIER, LABEL, DATATYPE, REGISTER,
	NUMBER, STRING, OPERATOR, PARAMETER, TERMINATOR, STATEMENT
)
from db2makedoc.db import (
	DatabaseObject, Relation, Routine, Constraint, Database, Tablespace,
	Schema, Table, View, Alias, Index, Trigger, Function, Procedure, Datatype,
	Field, UniqueKey, PrimaryKey, ForeignKey, Check, Param
)


class TeXCommentHighlighter(CommentHighlighter):
	"""Class which converts simple comment markup to TeX.

	This subclass of the generic comment highlighter class overrides the stub
	methods to convert the comment into TeX. The construction of the TeX
	elements is actually handled by the methods of the TeXFactory tag object
	passed to the constructor as opposed to the methods in this class.
	"""

	def __init__(self, database, tag):
		super(TeXCommentHighlighter, self).__init__()
		self.database = database
		self.tag = tag

	def start_parse(self, summary):
		self._content = []

	def start_para(self):
		self._para = []

	def handle_text(self, text):
		self._para.append(text)

	def handle_strong(self, text):
		self._para.append(self.tag.strong(text))

	def handle_emphasize(self, text):
		self._para.append(self.tag.em(text))

	def handle_underline(self, text):
		self._para.append(self.tag.u(text))

	def find_target(self, name):
		return self.database.find(name)

	def handle_link(self, target):
		# XXX Need to figure out a structure for link ids
		return ''

	def end_para(self):
		self._content.append(self.tag.p(*self._para))

	def end_parse(self, summary):
		if summary:
			return self._para
		else:
			return self._content


class TeXSQLHighlighter(SQLHighlighter):
	"""Class which marks up SQL with TeX.

	This subclass of the generic SQL highlighter class overrides the stub
	methods to markup the SQL with TeX commands. The tex_cmds attribute
	determines the TeX commands used for each type of token. The construction
	of the TeX commands is actually handled by the methods of the TeXFactory
	object passed to the constructor.
	"""

	def __init__(self, tag):
		super(TeXSQLHighlighter, self).__init__()
		self.tag = tag
		if not hasattr(tag, 'SQLerror'):
			# If the provided factory doesn't have custom commands defined for
			# SQL highlighting, then add them
			tag._new_command('SQLerror',      lambda x: tag.strong(tag.font(x, color=0xFF0000)))
			tag._new_command('SQLcomment',    lambda x: tag.em(tag.font(x, color=0x008000)))
			tag._new_command('SQLkeyword',    lambda x: tag.strong(tag.font(x, color=0x0000FF)))
			tag._new_command('SQLidentifier', lambda x: x)
			tag._new_command('SQLlabel',      lambda x: tag.strong(tag.em(tag.font(x, color=0x008080))))
			tag._new_command('SQLdatatype',   lambda x: tag.strong(tag.font(x, color=0x008000)))
			tag._new_command('SQLregister',   lambda x: tag.strong(tag.font(x, color=0x800080)))
			tag._new_command('SQLnumber',     lambda x: tag.font(x, color=0x800000))
			tag._new_command('SQLstring',     lambda x: tag.font(x, color=0x800000))
			tag._new_command('SQLoperator',   lambda x: x)
			tag._new_command('SQLparameter',  lambda x: tag.em(x))
			tag._new_command('SQLterminator', lambda x: x)
		self.tex_cmds = {
			ERROR:      tag.SQLerror,
			COMMENT:    tag.SQLcomment,
			KEYWORD:    tag.SQLkeyword,
			IDENTIFIER: tag.SQLidentifier,
			LABEL:      tag.SQLlabel,
			DATATYPE:   tag.SQLdatatype,
			REGISTER:   tag.SQLregister,
			NUMBER:     tag.SQLnumber,
			STRING:     tag.SQLstring,
			OPERATOR:   tag.SQLoperator,
			PARAMETER:  tag.SQLparameter,
			TERMINATOR: tag.SQLterminator,
			STATEMENT:  tag.SQLterminator,
		}

	def format_token(self, token):
		(token_type, token_value, source, _, _) = token
		try:
			tex_cmd = self.tex_cmds[(token_type, token_value)]
		except KeyError:
			tex_cmd = self.tex_cmds.get(token_type, None)
		# Because we're not using verbatim environments (because we can't apply
		# highlighting within them) we need to tweak extraneous space so it
		# doesn't get compressed (character U+00A0 is non-breaking space which
		# the TeXFactory class will escape into "~" which is the TeX
		# non-breaking space)
		source = re.sub(' {2,}', lambda m: u'\u00A0' * len(m.group()), source)
		if tex_cmd is not None:
			return tex_cmd(source)
		else:
			return source

	def format_line(self, index, line):
		return self.tag.li(self.format_token(token) for token in line)


class TeXDocumentation(object):
	def __init__(self, database, options):
		super(TeXDocumentation, self).__init__()
		self.database = database
		self.options = options
		self.default_desc = 'No description in the system catalog'
		self.tag = TeXFactory()
		self.comment_highlighter = TeXCommentHighlighter(self.database, self.tag)
		self.sql_highlighter = TeXSQLHighlighter(self.tag)
		self.type_names = {
			Alias:          'Alias',
			Check:          'Check Constraint',
			Constraint:     'Constraint',
			Database:       'Database',
			DatabaseObject: 'Object',
			Datatype:       'Data Type',
			Field:          'Field',
			ForeignKey:     'Foreign Key',
			Function:       'Function',
			Index:          'Index',
			Param:          'Parameter',
			PrimaryKey:     'Primary Key',
			Procedure:      'Procedure',
			Relation:       'Relation',
			Routine:        'Routine',
			Schema:         'Schema',
			Tablespace:     'Tablespace',
			Table:          'Table',
			Trigger:        'Trigger',
			UniqueKey:      'Unique Key',
			View:           'View',
		}

	def format_comment(self, comment, summary=False):
		return self.comment_highlighter.parse(comment or self.default_desc, summary)

	def format_sql(self, sql, terminator=';', id=None):
		tokens = self.sql_highlighter.parse(sql, terminator, line_split=True)
		return self.tag.ol(tokens, id=id)

	def generate(self):
		# Generate the document
		tag = self.tag
		options = self.options
		return tag.document(
			tag.topmatter(
				title=options['doc_title'],
				author_name=options['author_name'],
				author_email=options['author_email'],
				date=datetime.date.today()
			),
			tag.toc() if options['toc'] else '',
			self.generate_db(self.database),
			(self.generate_schema(schema) for schema in self.database.schema_list),
			tag.index() if options['index'] else '',
			# XXX Where's copyright meant to go?!
			doc_title=options['doc_title'],
			encoding=options['encoding'],
			bookmarks=options['bookmarks'],
			author_name=options['author_name'],
			author_email=options['author_email'],
			paper_size=options['paper_size'],
			binding_size=options['binding_size'],
			margin_size=options['margin_size'],
			landscape=options['landscape'],
			twoside=options['two_side'],
			font_packages=options['font_packages'],
			font_size=options['font_size'],
			creator='db2makedoc %s' % __version__
		)

	def generate_db(self, db):
		tag = self.tag
		return tag.section(
			tag.subsection(
				tag.p('The following table contains all schemas (logical object containers) in the database.'),
				tag.table(
					tag.caption('Database schemas'),
					tag.col(nowrap=True),
					tag.col(nowrap=False, width='25em'),
					tag.thead(
						tag.tr(
							tag.th('Name'),
							tag.th('Description')
						)
					),
					tag.tbody(
						tag.tr(
							tag.td(schema.name),
							tag.td(self.format_comment(schema.description, summary=True))
						) for schema in db.schema_list
					),
					id='tab:schemas'
				),
				title='Schemas'
			),
			tag.subsection(
				tag.p('The following table contains all tablespaces (physical object containers) in the database.'),
				tag.table(
					tag.caption('Database tablespaces'),
					tag.col(nowrap=True),
					tag.col(nowrap=False, width='25em'),
					tag.thead(
						tag.tr(
							tag.th('Name'),
							tag.th('Description')
						)
					),
					tag.tbody(
						tag.tr(
							tag.td(tbspace.name),
							tag.td(self.format_comment(tbspace.description, summary=True))
						) for tbspace in db.tablespace_list
					),
					id='tab:tablespaces'
				),
				title='Tablespaces'
			),
			title='%s %s' % (self.type_names[type(db)], db.name),
			id=db.identifier
		)

	def generate_schema(self, schema):
		tag = self.tag
		return tag.section(
			tag.subsection(
				self.format_comment(schema.description),
				title='Description'
			),
			tag.subsection(
				tag.p('The following table lists the relations (tables, views, and aliases) that belong to the schema.'),
				tag.table(
					tag.caption('%s relations' % schema.name),
					tag.col(nowrap=False, width='10em'),
					tag.col(nowrap=True),
					tag.col(nowrap=False, width='30em'),
					tag.thead(
						tag.tr(
							tag.th('Name'),
							tag.th('Type'),
							tag.th('Description')
						)
					),
					tag.tbody(
						tag.tr(
							tag.td(relation.name),
							tag.td(self.type_names[type(relation)]),
							tag.td(self.format_comment(relation.description, summary=True))
						) for relation in schema.relation_list
					),
					id='tab:relations:%s' % schema.identifier
				),
				title='Relations'
			) if len(schema.relation_list) > 0 else '',
			title='%s %s' % (self.type_names[type(schema)], schema.name),
			id=schema.identifier
		)

	def serialize(self, content):
		return tex(content)

	def write(self):
		filename = self.options['filename']
		logging.debug('Writing %s' % filename)
		f = open(filename, 'wb')
		try:
			f.write(self.serialize(self.generate()))
		finally:
			f.close()

