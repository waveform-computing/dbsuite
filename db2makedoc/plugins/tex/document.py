# vim: set noet sw=4 ts=4:

"""Provides a set of base classes for TeX based output plugins

This package defines a set of utility classes which make it easier to construct
output plugins capable of producing TeX documents.
"""

import pdb
import os
import re
import datetime
import logging

from operator import attrgetter
from itertools import chain
from db2makedoc.main import __version__
from db2makedoc.astex import tex, xml, TeXFactory
from db2makedoc.highlighters import CommentHighlighter, SQLHighlighter
from db2makedoc.hyphenator import hyphenate_word
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

	def handle_quote(self, text):
		self._para.append(self.tag.q(text))

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
			tag._new_environment(
				'SQLlisting',
				preamble=''.join((
					r'\newcounter{SQLlinenum}',
					r'\definecolor{linenum}{rgb}{0.6,0.6,0.6}',
				)),
				prefix=''.join((
					r'\ttfamily\begin{list}{',
					r'\footnotesize{\textcolor{linenum}{\arabic{SQLlinenum}}}',
					r'}{',
					r'\usecounter{SQLlinenum}',
					r'\setlength{\rightmargin}{\leftmargin}',
					r'\setlength{\itemsep}{0mm}',
					r'\setlength{\parsep}{0mm}',
					r'\setlength{\labelsep}{1em}',
					r'}',
				)),
				suffix=r'\end{list}\normalfont'
			)
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
		# Because we're not using {verbatim} environments (because we can't
		# apply highlighting within them) we need to tweak extraneous space so
		# it doesn't get compressed (character U+00A0 is non-breaking space
		# which the TeXFactory class will escape into "~" which is the TeX
		# non-breaking space)
		source = re.sub(' {2,}', lambda m: u' ' + (u'\u00A0' * (len(m.group()) - 1)), source)
		# The TeXListItem class inserts its own line breaks. If we include the
		# original line breaks, we wind up with full paragraphs in each item
		# which causes problems. Hence, we strip line breaks here
		source = source.replace('\n', '')
		if tex_cmd is not None:
			return tex_cmd(source)
		else:
			return source

	def format_line(self, index, line):
		return self.tag.li(self.format_token(token) for token in line)

	def parse(self, sql, terminator=';', line_split=True):
		tokens = super(TeXSQLHighlighter, self).parse(sql, terminator, line_split)
		return self.tag.SQLlisting(tokens)


class TeXPrettierFactory(TeXFactory):
	def _format(self, content):
		"""Reformats content into a human-readable string"""
		if content is None:
			# Format None as 'n/a'
			return 'n/a'
		elif isinstance(content, bool):
			# Format booleans as Yes/No
			return ['No', 'Yes'][content]
		elif isinstance(content, (int, long)):
			# Format integer number with , as a thousand separator
			s = str(content)
			for i in xrange(len(s) - 3, 0, -3):
				s = '%s,%s' % (s[:i], s[i:])
			return s
		elif isinstance(content, datetime.datetime):
			# Format timestamps as dates
			return str(content.date())
		else:
			# Use the default for everything else
			return super(TeXPrettierFactory, self)._format(content)


class TeXDocumentation(object):
	def __init__(self, database, options):
		super(TeXDocumentation, self).__init__()
		self.database = database
		self.options = options
		self.default_desc = 'No description in the system catalog'
		self.tag = TeXPrettierFactory()
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

	def format_name(self, name):
		# Use the hyphenation algorithm to permit splitting of long capitalized
		# identifiers (which are all too common in the generated documentation)
		result = hyphenate_word(name)
		first = True
		for part in result:
			if not first:
				yield self.tag.hyp()
			first = False
			yield part

	def format_comment(self, comment, summary=False):
		return self.comment_highlighter.parse(comment or self.default_desc, summary)

	def format_sql(self, sql, terminator=';', id=None):
		# XXX Do something with the id
		return self.sql_highlighter.parse(sql, terminator, line_split=True)

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
			tag.toc(level=options['toc_level']) if options['toc'] else '',
			self.generate_db(self.database),
			(self.generate_schema(schema) for schema in self.database.schema_list),
			(self.generate_relation(relation) for schema in self.database.schema_list for relation in schema.relation_list),
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
			self.format_comment(db.description),
			tag.subsection(
				tag.p('The following table contains all schemas (logical object containers) in the database, sorted by schema name.'),
				tag.table(
					tag.col(nowrap=True),
					tag.col(nowrap=False, width='90mm'),
					tag.thead(
						tag.tr(
							tag.th('Name'),
							tag.th('Description')
						)
					),
					tag.tbody(
						tag.tr(
							tag.td(self.format_name(schema.name)),
							tag.td(self.format_comment(schema.description, summary=True))
						) for schema in db.schema_list
					),
					id='tab:schemas'
				),
				title='Schemas'
			),
			tag.subsection(
				tag.p('The following table contains all tablespaces (physical object containers) in the database, sorted by tablespace name.'),
				tag.table(
					tag.col(nowrap=True),
					tag.col(nowrap=False, width='90mm'),
					tag.thead(
						tag.tr(
							tag.th('Name'),
							tag.th('Description')
						)
					),
					tag.tbody(
						tag.tr(
							tag.td(self.format_name(tbspace.name)),
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
			self.format_comment(schema.description),
			tag.subsection(
				tag.p('The following table lists the relations (tables, views, and aliases) that belong to the schema, sorted by relation name.'),
				tag.table(
					tag.col(nowrap=False, width='40mm'),
					tag.col(nowrap=True),
					tag.col(nowrap=False, width='90mm'),
					tag.thead(
						tag.tr(
							tag.th('Name'),
							tag.th('Type'),
							tag.th('Description')
						)
					),
					tag.tbody(
						tag.tr(
							tag.td(self.format_name(relation.name)),
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

	def generate_relation(self, relation):
		return {
			Table: self.generate_table,
			View:  self.generate_view,
			Alias: self.generate_alias,
		}[type(relation)](relation)

	def generate_table(self, table):
		tag = self.tag
		return tag.section(
			self.format_comment(table.description),
			tag.subsection(
				tag.p('The following table briefly lists general attributes of the table.'),
				tag.table(
					tag.col(nowrap=True),
					tag.col(nowrap=True),
					tag.col(nowrap=True),
					tag.col(nowrap=True),
					tag.tbody(
						tag.tr(
							tag.th('Created'),
							tag.td(table.created),
							tag.th('Last Statistics'),
							tag.td(table.last_stats)
						),
						tag.tr(
							tag.th('Created By'),
							tag.td(table.owner),
							tag.th('Cardinality'),
							tag.td(table.cardinality)
						),
						tag.tr(
							tag.th('Key Columns'),
							tag.td(len(table.primary_key.fields) if table.primary_key else 0),
							tag.th('Columns'),
							tag.td(len(table.field_list))
						),
						tag.tr(
							tag.th('Dependent Relations'),
							tag.td(
								len(table.dependents) +
								sum(len(k.dependent_list) for k in table.unique_key_list)
							),
							tag.th('Size'),
							tag.td(table.size_str)
						),
					),
					id='tab:table:attr:%s' % table.identifier
				),
				title='Attributes'
			),
			tag.subsection(
				tag.p('The following two tables list the fields of the table. In the first table, the (sorted) # column lists the 1-based position of the field in the table, the Type column lists the SQL data-type of the field, and Nulls indicates whether or not the field can contain the NULL value. In the second table the Name column is sorted, and the field Description is included.'),
				tag.table(
					tag.col(nowrap=True),
					tag.col(nowrap=False, width='40mm'),
					tag.col(nowrap=True),
					tag.col(nowrap=True),
					tag.col(nowrap=True),
					tag.col(nowrap=True),
					tag.thead(
						tag.tr(
							tag.th('#'),
							tag.th('Name'),
							tag.th('Type'),
							tag.th('Nulls'),
							tag.th('Key Pos'),
							tag.th('Cardinality')
						)
					),
					tag.tbody(
						tag.tr(
							tag.td(field.position),
							tag.td(self.format_name(field.name)),
							tag.td(field.datatype_str),
							tag.td(field.nullable),
							tag.td(field.key_index),
							tag.td(field.cardinality)
						) for field in table.field_list
					),
					id='tab:table:struct:%s' % table.identifier
				),
				tag.table(
					tag.col(nowrap=True),
					tag.col(nowrap=False, width='40mm'),
					tag.col(nowrap=False, width='90mm'),
					tag.thead(
						tag.tr(
							tag.th('#'),
							tag.th('Name'),
							tag.th('Description')
						)
					),
					tag.tbody(
						tag.tr(
							tag.td(field.position),
							tag.td(self.format_name(field.name)),
							tag.td(self.format_comment(field.description, summary=True))
						) for field in sorted(table.field_list, key=attrgetter('name'))
					),
					id='tab:table:desc:%s' % table.identifier
				),
				title='Fields'
			) if len(table.field_list) > 0 else '',
			tag.subsection(
				tag.p('The following table lists the indexes that apply to this table, whether or not the index enforces a unique rule, and the fields that the index covers.'),
				tag.table(
					tag.col(nowrap=False, width='40mm'),
					tag.col(nowrap=True),
					tag.col(nowrap=False, width='40mm'),
					tag.col(nowrap=True),
					tag.thead(
						tag.tr(
							tag.th('Name'),
							tag.th('Unique'),
							tag.th('Fields'),
							tag.th('Order')
						)
					),
					tag.tbody(
						tag.tr(
							tag.td(self.format_name(index.name) if i == 0 else ''),
							tag.td(index.unique if i == 0 else ''),
							tag.td(self.format_name(field.name)),
							tag.td({
								'A': 'Ascending',
								'D': 'Descending',
								'I': 'Include',
							}[order])
						)
						for index in sorted(table.index_list, key=attrgetter('name'))
						for (i, (field, order)) in enumerate(index.field_list)
					),
					id='tab:table:indexes:%s' % table.identifier
				),
				title='Indexes'
			) if len(table.index_list) > 0 else '',
			tag.subsection(
				tag.p('The following table lists all constraints that apply to this table, including the fields constrained in each case.'),
				tag.table(
					tag.col(nowrap=False, width='50mm'),
					tag.col(nowrap=True),
					tag.col(nowrap=False, width='50mm'),
					tag.thead(
						tag.tr(
							tag.th('Name'),
							tag.th('Type'),
							tag.th('Fields')
						)
					),
					tag.tbody(
						tag.tr(
							tag.td(self.format_name(const.name) if i == 0 else ''),
							tag.td(self.type_names[type(const)] if i == 0 else ''),
							tag.td('FIXME')
						)
						for const in table.constraint_list
						for (i, field) in enumerate(const.fields)
					),
					id='tab:table:consts:%s' % table.identifier
				),
				title='Constraints'
			) if len(table.constraint_list) > 0 else '',
			tag.subsection(
				tag.p('The following table lists all triggers that fire in response to changes (insertions, updates, and/or deletions) in this table.'),
				tag.table(
					tag.col(nowrap=False, width='30mm'),
					tag.col(nowrap=True),
					tag.col(nowrap=True),
					tag.col(nowrap=False, width='80mm'),
					tag.thead(
						tag.tr(
							tag.th('Name'),
							tag.th('Timing'),
							tag.th('Event'),
							tag.th('Description')
						)
					),
					tag.tbody(
						tag.tr(
							tag.td(self.format_name(trigger.name)),
							tag.td({
								'A': 'After',
								'B': 'Before',
								'I': 'Instead of',
							}[trigger.trigger_time]),
							tag.td({
								'I': 'Insert',
								'U': 'Update',
								'D': 'Delete',
							}[trigger.trigger_event]),
							tag.td(self.format_comment(trigger.description, summary=True))
						) for trigger in table.trigger_list
					),
					id='tab:table:trig:%s' % table.identifier
				),
				title='Triggers'
			) if len(table.trigger_list) > 0 else '',
			tag.subsection(
				tag.p('The following table lists all relations which depend on this table (e.g. views which reference this table in their defining query).'),
				tag.table(
					tag.col(nowrap=False, width='40mm'),
					tag.col(nowrap=True),
					tag.col(nowrap=False, width='90mm'),
					tag.thead(
						tag.tr(
							tag.th('Name'),
							tag.th('Type'),
							tag.th('Description')
						)
					),
					tag.tbody(
						tag.tr(
							tag.td(self.format_name(dep.qualified_name)),
							tag.td(self.type_names[type(dep)]),
							tag.td(self.format_comment(dep.description, summary=True))
						) for dep in chain(
							table.dependent_list,
							(
								fkey.relation
								for ukey in table.unique_key_list
								for fkey in ukey.dependent_list
							)
						)
					),
					id='tab:table:deps:%s' % table.identifier
				),
				title='Dependent Relations'
			) if len(table.dependent_list) + sum(len(k.dependent_list) for k in table.unique_key_list) > 0 else '',
			tag.subsection(
				tag.p('The SQL used to define the table is given below. Note that, depending on the underlying database implementation, this SQL may not be accurate (in some cases the database does not store the original command, so the SQL is reconstructed from metadata), or even valid for the platform.'),
				self.format_sql(table.create_sql),
				title='SQL Definition'
			),
			title='%s %s' % (self.type_names[type(table)], table.qualified_name),
			id=table.identifier
		)

	def generate_view(self, view):
		return ''

	def generate_alias(self, alias):
		return ''

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

