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
			tag._new_command('SQLlabel',      lambda x: tag.em(tag.font(x, color=0x008080)))
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
					r'\setlength{\leftmargin}{0mm}',
					r'\setlength{\itemsep}{0mm}',
					r'\setlength{\parsep}{0mm}',
					r'\setlength{\labelsep}{1em}',
					r'}',
				)),
				suffix=r'\end{list}\normalfont'
			)
			tag._new_environment(
				'SQLclip',
				prefix=''.join((
					r'\ttfamily\begin{list}{}{',
					r'\setlength{\leftmargin}{0mm}',
					r'\setlength{\itemsep}{0mm}',
					r'\setlength{\parsep}{0mm}',
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

	def parse_prototype(self, sql):
		tokens = super(TeXSQLHighlighter, self).parse_prototype(sql)
		return self.tag.SQLclip(self.tag.li(tokens))


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

	def format_prototype(self, sql):
		return self.sql_highlighter.parse_prototype(sql)

	def generate(self):
		logging.debug('Generating document')
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
			(
				self.generate_schema(schema)
				for schema in self.database.schema_list
				if schema.relation_list
				or schema.trigger_list
				or schema.routine_list
			),
			(
				self.generate_relation(relation)
				for schema in self.database.schema_list
				for relation in schema.relation_list
			),
			(
				self.generate_trigger(trigger)
				for schema in self.database.schema_list
				for trigger in schema.trigger_list
			),
			(
				self.generate_routine(routine)
				for schema in self.database.schema_list
				for routine in schema.routine_list
			),
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
		logging.debug('Generating database section')
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
		logging.debug('Generating schema %s section' % schema.name)
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
							tag.td(tag.a(self.format_name(relation.name), href='sec:%s' % relation.identifier)),
							tag.td(self.type_names[type(relation)]),
							tag.td(self.format_comment(relation.description, summary=True))
						) for relation in schema.relation_list
					),
					id='tab:relations:%s' % schema.identifier
				),
				title='Relations'
			) if len(schema.relation_list) > 0 else '',
			tag.subsection(
				tag.p('The following table lists the triggers that belong to the schema, sorted by trigger name.'),
				tag.table(
					tag.col(nowrap=False, width='40mm'),
					tag.col(nowrap=True),
					tag.col(nowrap=True),
					tag.col(nowrap=False, width='70mm'),
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
							tag.td(tag.a(self.format_name(trigger.name), href='sec:%s' % trigger.identifier)),
							tag.td({
								'B': 'Before',
								'A': 'After',
								'I': 'Instead of',
							}[trigger.trigger_time]),
							tag.td({
								'I': 'Insert',
								'U': 'Update',
								'D': 'Delete',
							}[trigger.trigger_event]),
							tag.td(self.format_comment(trigger.description, summary=True))
						) for trigger in schema.trigger_list
					),
					id='tab:triggers:%s' % schema.identifier
				),
				title='Triggers'
			) if len(schema.trigger_list) > 0 else '',
			tag.subsection(
				tag.p('The following table lists the routines (user defined functions and stored procedures) that belong to the schema, sorted by name.'),
				tag.table(
					tag.col(nowrap=False, width='40mm'),
					tag.col(nowrap=True),
					tag.col(nowrap=False, width='80mm'),
					tag.thead(
						tag.tr(
							tag.th('Name'),
							tag.th('Type'),
							tag.th('Description')
						)
					),
					tag.tbody(
						tag.tr(
							# XXX Find a way to include specific names for overloaded routines only
							tag.td(tag.a(self.format_name(routine.name), href='sec:%s' % routine.identifier)),
							tag.td(self.type_names[type(routine)]),
							tag.td(self.format_comment(routine.description, summary=True))
						) for routine in schema.routine_list
					),
					id='tag:routines:%s' % schema.identifier
				),
				title='Routines'
			) if len(schema.routine_list) > 0 else '',
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
		logging.debug('Generating table %s section' % table.qualified_name)
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
					id='tab:attr:%s' % table.identifier
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
					id='tab:struct:%s' % table.identifier
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
					id='tab:desc:%s' % table.identifier
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
					id='tab:indexes:%s' % table.identifier
				),
				title='Indexes'
			) if len(table.index_list) > 0 else '',
			tag.subsection(
				tag.p('The following table lists all constraints that apply to this table, including the fields constrained in each case.'),
				tag.table(
					tag.col(nowrap=False, width='40mm'),
					tag.col(nowrap=True),
					tag.col(nowrap=False, width='70mm'),
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
							tag.td('FIXME') # XXX FIXME
						)
						for const in table.constraint_list
						for (i, field) in enumerate(const.fields)
					),
					id='tab:consts:%s' % table.identifier
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
							tag.td(tag.a(self.format_name(trigger.name), href='sec:%s' % trigger.identifier)),
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
					id='tab:trig:%s' % table.identifier
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
							tag.td(tag.a(self.format_name(dep.qualified_name), href='sec:%s' % dep.identifier)),
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
					id='tab:dependents:%s' % table.identifier
				),
				title='Dependent Relations'
			) if len(table.dependent_list) + sum(len(k.dependent_list) for k in table.unique_key_list) > 0 else '',
			tag.subsection(
				tag.p('The SQL used to define the table is given below. Note that, depending on the underlying database implementation, this SQL may not be accurate (in some cases the database does not store the original command, so the SQL is reconstructed from metadata), or even valid for the platform.'),
				self.format_sql(table.create_sql),
				title='SQL Definition'
			),
			title='%s %s' % (self.type_names[type(table)], table.qualified_name),
			id='sec:%s' % table.identifier
		)

	def generate_view(self, view):
		logging.debug('Generating view %s section' % view.qualified_name)
		tag = self.tag
		return tag.section(
			self.format_comment(view.description),
			tag.subsection(
				tag.p('The following table briefly lists general attributes of the view.'),
				tag.table(
					tag.col(nowrap=True),
					tag.col(nowrap=True),
					tag.col(nowrap=True),
					tag.col(nowrap=True),
					tag.tbody(
						tag.tr(
							tag.th('Created'),
							tag.td(view.created),
							tag.th('Created By'),
							tag.td(view.owner),
						),
						tag.tr(
							tag.th('Columns'),
							tag.td(len(view.field_list)),
							tag.th('Read Only'),
							tag.td(view.read_only)
						),
						tag.tr(
							tag.th('Dependent Relations'),
							tag.td(len(view.dependent_list)),
							tag.th('Dependencies'),
							tag.td(len(view.dependency_list))
						),
					),
					id='tab:attr:%s' % view.identifier
				),
				title='Attributes'
			),
			tag.subsection(
				tag.p('The following two tables list the fields of the view. In the first table, the (sorted) # column lists the 1-based position of the field in the view, the Type column lists the SQL data-type of the field, and Nulls indicates whether or not the field can contain the NULL value. In the second table the Name column is sorted, and the field Description is included.'),
				tag.table(
					tag.col(nowrap=True),
					tag.col(nowrap=False, width='40mm'),
					tag.col(nowrap=True),
					tag.col(nowrap=True),
					tag.thead(
						tag.tr(
							tag.th('#'),
							tag.th('Name'),
							tag.th('Type'),
							tag.th('Nulls'),
						)
					),
					tag.tbody(
						tag.tr(
							tag.td(field.position),
							tag.td(self.format_name(field.name)),
							tag.td(field.datatype_str),
							tag.td(field.nullable),
						) for field in view.field_list
					),
					id='tab:struct:%s' % view.identifier
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
						) for field in sorted(view.field_list, key=attrgetter('name'))
					),
					id='tab:desc:%s' % view.identifier
				),
				title='Fields'
			) if len(view.field_list) > 0 else '',
			tag.subsection(
				tag.p('The following table lists all triggers that fire in response to changes (insertions, updates, and/or deletions) in this view.'),
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
							tag.td(tag.a(self.format_name(trigger.name), href='sec:%s' % trigger.identifier)),
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
						) for trigger in view.trigger_list
					),
					id='tab:trig:%s' % view.identifier
				),
				title='Triggers'
			) if len(view.trigger_list) > 0 else '',
			tag.subsection(
				tag.p('The following table lists all relations which depend on this view (e.g. views which reference this view in their defining query).'),
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
							tag.td(tag.a(self.format_name(dep.qualified_name), href='sec:%s' % dep.identifier)),
							tag.td(self.type_names[type(dep)]),
							tag.td(self.format_comment(dep.description, summary=True))
						) for dep in view.dependent_list
					),
					id='tab:dependents:%s' % view.identifier
				),
				title='Dependent Relations'
			) if len(view.dependent_list) else '',
			tag.subsection(
				tag.p('The following table lists all relations which this relation depends upon (e.g. tables referenced by this view in its defining query).'),
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
							tag.td(tag.a(self.format_name(dep.qualified_name), href='sec:%s' % dep.identifier)),
							tag.td(self.type_names[type(dep)]),
							tag.td(self.format_comment(dep.description, summary=True))
						) for dep in view.dependency_list
					),
					id='tab:dependencies:%s' % view.identifier
				),
				title='Dependent Relations'
			) if len(view.dependency_list) else '',
			tag.subsection(
				tag.p('The SQL used to define the view is given below. Note that, depending on the underlying database implementation, this SQL may not be accurate (in some cases the database does not store the original command, so the SQL is reconstructed from metadata), or even valid for the platform.'),
				self.format_sql(view.create_sql),
				title='SQL Definition'
			),
			title='%s %s' % (self.type_names[type(view)], view.qualified_name),
			id='sec:%s' % view.identifier
		)

	def generate_alias(self, alias):
		logging.debug('Generating alias %s section' % alias.qualified_name)
		tag = self.tag
		is_table = isinstance(alias.final_relation, Table)
		return tag.section(
			self.format_comment(alias.description),
			tag.subsection(
				tag.p('The following table briefly lists general attributes of the alias.'),
				tag.table(
					tag.col(nowrap=True),
					tag.col(nowrap=True),
					tag.col(nowrap=True),
					tag.col(nowrap=True),
					tag.tbody(
						tag.tr(
							tag.th('Created'),
							tag.td(alias.created),
							tag.th('Created By'),
							tag.td(alias.owner),
						),
						tag.tr(
							tag.th('Alias For'),
							tag.td(tag.a(alias.relation.qualified_name, href='sec:%s' % alias.relation.identifier)),
							tag.th(''),
							tag.td('')
						)
					),
					id='tab:attr:%s' % alias.identifier
				),
				title='Attributes'
			),
			tag.subsection(
				tag.p('The following two tables list the fields of the alias. In the first table, the (sorted) # column lists the 1-based position of the field in the view, the Type column lists the SQL data-type of the field, and Nulls indicates whether or not the field can contain the NULL value. In the second table the Name column is sorted, and the field Description is included.'),
				tag.table(
					tag.col(nowrap=True),
					tag.col(nowrap=False, width='40mm'),
					tag.col(nowrap=True),
					tag.col(nowrap=True),
					tag.col(nowrap=True) if is_table else '',
					tag.col(nowrap=True) if is_table else '',
					tag.thead(
						tag.tr(
							tag.th('#'),
							tag.th('Name'),
							tag.th('Type'),
							tag.th('Nulls'),
							tag.th('Key Pos') if is_table else '',
							tag.th('Cardinality') if is_table else ''
						)
					),
					tag.tbody(
						tag.tr(
							tag.td(field.position),
							tag.td(self.format_name(field.name)),
							tag.td(field.datatype_str),
							tag.td(field.nullable),
							tag.td(field.key_index) if is_table else '',
							tag.td(field.cardinality) if is_table else ''
						) for field in alias.field_list
					),
					id='tab:struct:%s' % alias.identifier
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
						) for field in sorted(alias.field_list, key=attrgetter('name'))
					),
					id='tab:desc:%s' % alias.identifier
				),
				title='Fields'
			) if len(alias.field_list) > 0 else '',
			tag.subsection(
				tag.p('The following table lists all relations which depend on this alias (e.g. views which reference this alias in their defining query).'),
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
							tag.td(tag.a(self.format_name(dep.qualified_name), href='sec:%s' % dep.identifier)),
							tag.td(self.type_names[type(dep)]),
							tag.td(self.format_comment(dep.description, summary=True))
						) for dep in alias.dependent_list
					),
					id='tab:dependents:%s' % alias.identifier
				),
				title='Dependent Relations'
			) if len(alias.dependent_list) else '',
			tag.subsection(
				tag.p('The SQL used to define the alias is given below. Note that, depending on the underlying database implementation, this SQL may not be accurate (in some cases the database does not store the original command, so the SQL is reconstructed from metadata), or even valid for the platform.'),
				self.format_sql(alias.create_sql),
				title='SQL Definition'
			),
			title='%s %s' % (self.type_names[type(alias)], alias.qualified_name),
			id='sec:%s' % alias.identifier
		)

	def generate_trigger(self, trigger):
		logging.debug('Generating trigger %s section' % trigger.qualified_name)
		tag = self.tag
		return tag.section(
			tag.p(self.format_comment(trigger.description)),
			tag.subsection(
				tag.p('The following table briefly lists general attributes of the trigger.'),
				tag.table(
					tag.col(nowrap=True),
					tag.col(nowrap=True),
					tag.col(nowrap=True),
					tag.col(nowrap=True),
					tag.tbody(
						tag.tr(
							tag.th('Created'),
							tag.td(trigger.created),
							tag.th('Created By'),
							tag.td(trigger.owner),
						),
						tag.tr(
							tag.th('Timing'),
							tag.td({
								'A': 'After',
								'B': 'Before',
								'I': 'Instead of',
							}[trigger.trigger_time]),
							tag.th('Event'),
							tag.td({
								'I': 'Insert',
								'U': 'Update',
								'D': 'Delete',
							}[trigger.trigger_event])
						),
						tag.tr(
							tag.th('Granularity'),
							tag.td({
								'R': 'Row',
								'S': 'Statement',
							}[trigger.granularity]),
							tag.th('Relation'),
							tag.td(tag.a(trigger.relation.qualified_name, href='sec:%s' % trigger.relation.identifier))
						)
					),
					id='tab:attr:%s' % trigger.identifier
				),
				title='Attributes'
			),
			tag.subsection(
				tag.p('The SQL used to define the trigger is given below. Note that, depending on the underlying database implementation, this SQL may not be accurate (in some cases the database does not store the original command, so the SQL is reconstructed from metadata), or even valid for the platform.'),
				self.format_sql(trigger.create_sql),
				title='SQL Definition'
			),
			title='%s %s' % (self.type_names[type(trigger)], trigger.qualified_name),
			id='sec:%s' % trigger.identifier
		)

	def generate_routine(self, routine):
		return {
			Function:  self.generate_function,
			Procedure: self.generate_procedure,
		}[type(routine)](routine)

	def generate_function(self, function):
		logging.debug('Generating function %s section' % function.qualified_name)
		tag = self.tag
		return tag.section(
			self.format_prototype(function.prototype),
			self.format_comment(function.description),
			tag.dl(
				tag.di(self.format_comment(param.description, summary=True), term=param.name)
				for param in function.param_list
			) if len(function.param_list) > 0 else '',
			tag.subsection(
				tag.table(
					tag.col(nowrap=True),
					tag.col(nowrap=False, width='40mm'),
					tag.col(nowrap=True),
					tag.col(nowrap=False, width='70mm'),
					tag.thead(
						tag.tr(
							tag.th('#'),
							tag.th('Name'),
							tag.th('Type'),
							tag.th('Description')
						)
					),
					tag.tbody(
						tag.tr(
							tag.td(param.position + 1),
							tag.td(self.format_name(param.name)),
							tag.td(param.datatype_str),
							tag.td(self.format_comment(param.description, summary=True))
						) for param in function.return_list
					),
					id='tab:returns:%s' % function.identifier
				),
				title='Returns'
			) if function.type in ('R', 'T') else '',
			tag.subsection(
				tag.p('The following table briefly lists general attributes of the function.'),
				tag.table(
					tag.col(nowrap=True),
					tag.col(nowrap=True),
					tag.col(nowrap=True),
					tag.col(nowrap=True),
					tag.tbody(
						tag.tr(
							tag.th('Created'),
							tag.td(function.created),
							tag.th('Created By'),
							tag.td(function.owner)
						),
						tag.tr(
							tag.th('Type'),
							tag.td({
								'C': 'Column/Aggregate',
								'R': 'Row',
								'T': 'Table',
								'S': 'Scalar',
							}[function.type]),
							tag.th('SQL Access'),
							tag.td({
								None: 'No SQL',
								'N':  'No SQL',
								'C':  'Contains SQL',
								'R':  'Read-only SQL',
								'M':  'Read-write SQL',
							}[function.sql_access])
						),
						tag.tr(
							tag.th('External Action'),
							tag.td(function.external_action),
							tag.th('Deterministic'),
							tag.td(function.deterministic)
						),
						tag.tr(
							tag.th('Called on NULL'),
							tag.td(function.null_call),
							tag.th('Specific Name'),
							tag.td(function.specific_name)
						)
					),
					id='tab:attr:%s' % function.identifier
				),
				title='Attributes'
			),
			tag.subsection(
				tag.p('The following table lists the overloaded versions of this function, that is other routines with the same name but a different parameter list typically used to provide the same functionality across a range of data types.'),
				tag.table(
					tag.col(nowrap=False, width='70mm'),
					tag.col(nowrap=False, width='40mm'),
					tag.thead(
						tag.tr(
							tag.th('Prototype'),
							tag.th('Specific Name')
						)
					),
					tag.tbody(
						tag.tr(
							tag.td(self.format_prototype(overload.prototype)),
							tag.td(tag.a(self.format_name(overload.specific_name), href='sec:%s' % overload.identifier))
						)
						for overload in function.schema.functions[function.name]
						if overload is not function
					),
					id='tab:overloads:%s' % function.identifier
				),
				title='Overloaded Versions'
			) if len(function.schema.functions[function.name]) > 1 else '',
			tag.subsection(
				tag.p('The SQL used to define the function is given below. Note that, depending on the underlying database implementation, this SQL may not be accurate (in some cases the database does not store the original command, so the SQL is reconstructed from metadata), or even valid for the platform.'),
				self.format_sql(function.create_sql),
				title='SQL Definition'
			),
			title='%s %s' % (self.type_names[type(function)], function.qualified_name),
			id='sec:%s' % function.identifier
		)

	def generate_procedure(self, procedure):
		logging.debug('Generating procedure %s section' % procedure.qualified_name)
		tag = self.tag
		return tag.section(
			self.format_prototype(procedure.prototype),
			self.format_comment(procedure.description),
			tag.dl(
				tag.di(self.format_comment(param.description, summary=True), term=param.name)
				for param in procedure.param_list
			) if len(procedure.param_list) > 0 else '',
			tag.subsection(
				tag.p('The following table briefly lists general attributes of the procedure.'),
				tag.table(
					tag.col(nowrap=True),
					tag.col(nowrap=True),
					tag.col(nowrap=True),
					tag.col(nowrap=True),
					tag.tbody(
						tag.tr(
							tag.th('Created'),
							tag.td(procedure.created),
							tag.th('Created By'),
							tag.td(procedure.owner)
						),
						tag.tr(
							tag.th('SQL Access'),
							tag.td({
								None: 'No SQL',
								'N':  'No SQL',
								'C':  'Contains SQL',
								'R':  'Read-only SQL',
								'M':  'Read-write SQL',
							}[procedure.sql_access]),
							tag.th('Called on NULL'),
							tag.td(procedure.null_call)
						),
						tag.tr(
							tag.th('External Action'),
							tag.td(procedure.external_action),
							tag.th('Deterministic'),
							tag.td(procedure.deterministic)
						),
						tag.tr(
							tag.th('Specific Name'),
							tag.td(procedure.specific_name),
							tag.th(''),
							tag.td('')
						)
					),
					id='tab:attr:%s' % procedure.identifier
				),
				title='Attributes'
			),
			tag.subsection(
				tag.p('The following table lists the overloaded versions of this procedure, that is other routines with the same name but a different parameter list typically used to provide the same functionality across a range of data types.'),
				tag.table(
					tag.col(nowrap=False, width='70mm'),
					tag.col(nowrap=False, width='40mm'),
					tag.thead(
						tag.tr(
							tag.th('Prototype'),
							tag.th('Specific Name')
						)
					),
					tag.tbody(
						tag.tr(
							tag.td(self.format_prototype(overload.prototype)),
							tag.td(tag.a(self.format_name(overload.specific_name), href='sec:%s' % overload.identifier))
						)
						for overload in procedure.schema.procedures[procedure.name]
						if overload is not procedure
					),
					id='tab:overloads:%s' % procedure.identifier
				),
				title='Overloaded Versions'
			) if len(procedure.schema.procedures[procedure.name]) > 1 else '',
			tag.subsection(
				tag.p('The SQL used to define the procedure is given below. Note that, depending on the underlying database implementation, this SQL may not be accurate (in some cases the database does not store the original command, so the SQL is reconstructed from metadata), or even valid for the platform.'),
				self.format_sql(procedure.create_sql),
				title='SQL Definition'
			),
			title='%s %s' % (self.type_names[type(procedure)], procedure.qualified_name),
			id='sec:%s' % procedure.identifier
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

