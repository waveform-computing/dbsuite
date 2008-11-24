# vim: set noet sw=4 ts=4:

"""Output plugin for XML metadata storage."""

import codecs
import logging
import db2makedoc.plugins
from db2makedoc.db import (
	Schema, Datatype, Table, View, Alias, Constraint, Index, Trigger, Function,
	Procedure, Tablespace
)
from db2makedoc.sql.formatter import quote_str, format_ident
from string import Template


class OutputPlugin(db2makedoc.plugins.OutputPlugin):
	"""Output plugin for comment script generation.

	This output plugin generates an SQL script which can be used to apply
	comments to a database. This is particularly useful in the case where a
	database has been commented over time by various different groups, who now
	wish to centralize the source of comments (e.g. in a version control
	repository).
	"""

	def __init__(self):
		super(OutputPlugin, self).__init__()
		self.add_option('filename', default=None, convert=self.convert_path,
			doc="""The path and filename for the SQL output file. Use $db or
			${db} to include the name of the database in the filename. The
			$dblower and $dbupper substitutions are also available, for forced
			lowercase and uppercase versions of the name respectively. To
			include a literal $, use $$""")
		self.add_option('encoding', default='UTF-8',
			doc="""The character encoding to use for the SQL output file""")
		self.add_option('blanks', default='false', convert=self.convert_bool,
			doc="""If true, include statements for blanking comments on items
			which have no description""")
		self.add_option('terminator', default=';',
			doc="""The statement terminator to append to each statement""")
		self.add_option('statement', default='comment', convert=lambda s: s.lower().strip(),
			doc="""The type of statements to generate. If 'comment' (the
			default), generate SQL standard COMMENT ON statements. If 'update',
			or 'merge' generate UPDATE or MERGE statements respectively, which
			target the views in the DOCCAT schema (see the contrib
			sub-directory of the source distribution for the DDL to create
			these views). See also the schema option""")
		self.add_option('schema', default='DOCCAT',
			doc="""The schema containing the DOCCAT views. Only used when the
			statement option is not 'comment'. Please note this parameter is
			case sensitive. If you provide a lowercase value, it will be
			appropriately quoted!""")
		self.add_option('maxlen', default='0', convert=lambda i: self.convert_int(i, minvalue=0),
			doc="""The maximum length for comments. By default, this is 0 which
			indicates no maximum length. If greater than zero, comments longer
			than the specified length will be truncated. See also the ellipsis
			option""")
		self.add_option('ellipsis', default='...',
			doc="""If truncation of long comments is enabled (maxlen > 0),
			truncated comments will have the value of the ellipsis option
			appended to indicate that truncation has occurred (hence comments
			are actually truncated to maxlen - len(ellipsis))""")

	def configure(self, config):
		super(OutputPlugin, self).configure(config)
		# Cache some values for quicker access
		self.blanks = self.options['blanks']
		self.ellipsis = self.options['ellipsis']
		self.maxlen = self.options['maxlen']
		self.schema = self.options['schema']
		self.statement = self.options['statement']
		self.terminator = self.options['terminator']
		# Ensure we can find the specified encoding
		codecs.lookup(self.options['encoding'])
		# Ensure the filename was specified
		if not self.options['filename']:
			raise db2makedoc.plugins.PluginConfigurationError('The filename option must be specified')
		# Ensure the statement value is valid
		valid = set(['comment', 'update', 'merge'])
		if not self.statement in valid:
			raise db2makedoc.plugins.PluginConfigurationError('The statement option must be one of %s' % ', '.join(valid))
		# Ensure the combination of maxlen and ellipsis isn't silly
		if self.maxlen > 0 and len(self.ellipsis) >= self.maxlen:
			raise db2makedoc.plugins.PluginConfigurationError('The ellipsis option is as long or longer than maxlen!')

	def execute(self, database):
		super(OutputPlugin, self).execute(database)
		# Translate any templates in the filename option now that we've got the
		# database
		if not 'filename_template' in self.options:
			self.options['filename_template'] = Template(self.options['filename'])
		self.options['filename'] = self.options['filename_template'].safe_substitute({
			'db': database.name,
			'dblower': database.name.lower(),
			'dbupper': database.name.upper(),
		})
		# Construct the SQL script
		logging.debug('Generating SQL')
		self.script = []
		self.find_cache = {}
		database.touch(self.get_statement)
		s = unicode('\n\n'.join(stmt for stmt in self.script))
		# Finally, write the document to disk
		logging.info('Writing output to "%s"' % self.options['filename'])
		f = open(self.options['filename'], 'w')
		try:
			f.write(s.encode(self.options['encoding']))
		finally:
			f.close()

	def find_method(self, cls):
		# Look for a perfect class match, and if not found, search along each
		# base class' hierarchy for matches
		try:
			return self.find_cache[cls]
		except KeyError:
			method_name = '%s_%s' % (self.statement, cls.__name__.lower())
			if hasattr(self, method_name):
				self.find_cache[cls] = result = getattr(self, method_name)
				return result
			else:
				result = None
				for base in cls.__bases__:
					result = self.find_method(base)
					if result:
						break
				self.find_cache[cls] = result
				return result

	def get_statement(self, dbobject):
		method = self.find_method(type(dbobject))
		if method:
			sql = method(dbobject)
			if sql:
				self.script.append(sql)

	def get_description(self, comment):
		comment = comment or ''
		if self.maxlen > 0 and len(comment) > self.maxlen:
			comment = comment[:self.maxlen - len(self.ellipsis)].rstrip() + self.ellipsis
		return quote_str(comment)

	def comment(self, label, name, description):
		if description or self.blanks:
			return 'COMMENT ON %s %s IS %s%s' % (
				label,
				'.'.join(format_ident(s) for s in name),
				self.get_description(description),
				self.terminator,
			)

	def comment_table(self, o):
		if o.description or self.blanks:
			table_comment = self.comment('TABLE', (o.schema.name, o.name), o.description)
		else:
			table_comment = ''
		field_comments = [
			(format_ident(f.name), self.get_description(f.description))
			for f in o.field_list
			if f.description or self.blanks
		]
		if field_comments:
			max_name_len = max(len(name) for (name, description) in field_comments)
			field_comments = ',\n'.join(
				'\t%-*s IS %s' % (max_name_len, name, description)
				for (name, description) in field_comments
			)
			field_comments = 'COMMENT ON %s.%s (\n%s\n)%s' % (
				format_ident(o.schema.name),
				format_ident(o.name),
				field_comments,
				self.terminator,
			)
		else:
			field_comments = ''
		return '\n'.join(s for s in (table_comment, field_comments) if s)

	comment_schema     = lambda self, o: self.comment('SCHEMA',             (o.name,), o.description)
	comment_tablespace = lambda self, o: self.comment('TABLESPACE',         (o.name,), o.description)
	comment_alias      = lambda self, o: self.comment('ALIAS',              (o.schema.name, o.name), o.description)
	comment_datatype   = lambda self, o: self.comment('TYPE',               (o.schema.name, o.name), o.description)
	comment_index      = lambda self, o: self.comment('INDEX',              (o.schema.name, o.name), o.description)
	comment_trigger    = lambda self, o: self.comment('TRIGGER',            (o.schema.name, o.name), o.description)
	comment_function   = lambda self, o: self.comment('SPECIFIC FUNCTION',  (o.schema.name, o.specific_name), o.description)
	comment_procedure  = lambda self, o: self.comment('SPECIFIC PROCEDURE', (o.schema.name, o.specific_name), o.description)
	comment_constraint = lambda self, o: self.comment('CONSTRAINT',         (o.relation.schema.name, o.relation.name, o.name), o.description)
	comment_view = comment_table

	def get_predicates(self, predicates):
		return ' AND '.join(
			'%s = %s' % (format_ident(key), quote_str(value))
			for (key, value) in predicates.iteritems()
		)

	def update(self, dbobject, table, predicates):
		if dbobject.description or self.blanks:
			return 'UPDATE %s.%s\n\tSET REMARKS = %s\n\tWHERE %s%s' % (
				format_ident(self.schema),
				format_ident(table),
				self.get_description(dbobject.description),
				self.get_predicates(predicates),
				self.terminator,
			)

	def update_table(self, o):
		predicates = {
			'TABSCHEMA': o.schema.name,
			'TABNAME':   o.name,
		}
		if o.description or self.blanks:
			table_comment = self.update(o, 'TABLES', predicates)
		else:
			table_comment = ''
		field_comments = [
			(quote_str(f.name), self.get_description(f.description))
			for f in o.field_list
			if f.description or self.blanks
		]
		if field_comments:
			max_name_len = max(len(name) for (name, description) in field_comments)
			field_comments = [
				'\t\tWHEN %-*s THEN %s' % (max_name_len, name, description)
				for (name, description) in field_comments
			]
			if not self.blanks:
				field_comments.append('\t\tELSE REMARKS')
			field_comments = '\n'.join(field_comments)
			field_comments = 'UPDATE %s.COLUMNS\n\tSET REMARKS = CASE COLNAME\n%s\n\tEND\n\tWHERE %s%s' % (
				format_ident(self.schema),
				field_comments,
				self.get_predicates(predicates),
				self.terminator,
			)
		else:
			field_comments = ''
		return '\n'.join(s for s in (table_comment, field_comments) if s)

	def update_param_type(self, o, type):
		param_comments = [
			(p.position, p.name, self.get_description(p.description))
			for p in o.param_list
			if p.type == type and (p.description or self.blanks)
		]
		predicates = {
			'ROUTINESCHEMA': o.schema.name,
			'SPECIFICNAME':  o.specific_name,
			'ROWTYPE':       {'I': 'P'}.get(type, type),
		}
		if param_comments:
			max_name_len = max(len(name) for (pos, name, description) in param_comments)
			max_pos_len = max(len(str(pos)) for (pos, name, description) in param_comments)
			param_comments = [
				'\t\tWHEN %-*d /* %-*s */ THEN %s' % (max_pos_len, pos, max_name_len, name, description)
				for (pos, name, description) in param_comments
			]
			if not self.blanks:
				param_comments.append('\t\tELSE REMARKS')
			param_comments = '\n'.join(param_comments)
			param_comments = 'UPDATE %s.ROUTINEPARMS\n\tSET REMARKS = CASE ORDINAL\n%s\n\tEND\n\tWHERE %s%s' % (
				format_ident(self.schema),
				param_comments,
				self.get_predicates(predicates),
				self.terminator,
			)
		else:
			param_comments = ''
		return param_comments

	def update_routine(self, o):
		predicates = {
			'ROUTINESCHEMA': o.schema.name,
			'SPECIFICNAME':  o.specific_name,
		}
		if o.description or self.blanks:
			routine_comment = self.update(o, 'ROUTINES', predicates)
		else:
			routine_comment = ''
		return '\n'.join(s for s in (
			routine_comment,
			self.update_param_type(o, 'B'),
			self.update_param_type(o, 'I'),
			self.update_param_type(o, 'O'),
			self.update_param_type(o, 'R')
		) if s)

	update_alias = lambda self, o: self.update(o, 'TABLES', {
		'TABSCHEMA': o.schema.name,
		'TABNAME':   o.name,
	})
	update_constraint = lambda self, o: self.update(o, 'TABCONST', {
		'TABSCHEMA': o.relation.schema.name,
		'TABNAME':   o.relation.name,
		'CONSTNAME': o.name,
	})
	update_datatype = lambda self, o: self.update(o, 'DATATYPES', {
		'TYPESCHEMA': o.schema.name,
		'TYPENAME':   o.name,
	})
	update_index = lambda self, o: self.update(o, 'INDEXES', {
		'INDSCHEMA': o.schema.name,
		'INDNAME':   o.name,
	})
	update_trigger = lambda self, o: self.update(o, 'TRIGGERS', {
		'TRIGSCHEMA': o.schema.name,
		'TRIGNAME':   o.name,
	})
	update_schema = lambda self, o: self.update(o, 'SCHEMATA', {
		'SCHEMANAME': o.name,
	})
	update_tablespace = lambda self, o: self.update(o, 'TABLESPACES', {
		'TBSPACE': o.name,
	})
	update_view = update_table

