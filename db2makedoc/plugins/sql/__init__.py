# vim: set noet sw=4 ts=4:

"""Output plugin for XML metadata storage."""

import codecs
import re
import logging
import db2makedoc.plugins
from db2makedoc.db import (
	Schema, Datatype, Table, View, Alias, Constraint, Index, Trigger, Function,
	Procedure, Tablespace
)


# XXX Extend this to support unicode strings? Not much point for DB2 given that
# the REMARKS columns in the system catalog are VARCHAR.  They could store
# UTF-8 in a unicode database, but the 254 character limit would make the
# result comments tiny. Still, other engines might store more (e.g. DB2 for
# i5/OS allows 2000 chars!)
hexstr_re = re.compile(r'[\x00-\x1F]+')
def quote(s, q="'"):
	"""Utility routine for quoting strings in SQL."""
	# Double up all quotes in s
	s = s.replace(q, q*2)
	# Replace control characters (e.g. CR, LF) with concatenated hex strings
	s = hexstr_re.sub(lambda m: "' || X'%s' || '" % ''.join('%.2X' % ord(c) for c in m.group()), s)
	return q + s + q


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
			doc="""The filename for the SQL output file (mandatory)""")
		self.add_option('encoding', default='UTF-8',
			doc="""The character encoding to use for the SQL output file (optional)""")
		self.add_option('blanks', default='false', convert=self.convert_bool,
			doc="""If true, include statements for blanking comments on items
			which have no description""")
		self.add_option('terminator', default=';',
			doc="""The statement terminator to append to each statement""")

	def configure(self, config):
		super(OutputPlugin, self).configure(config)
		# Ensure we can find the specified encoding
		codecs.lookup(self.options['encoding'])
		# Ensure the filename was specified
		if not self.options['filename']:
			raise db2makedoc.plugins.PluginConfigurationError('The filename option must be specified')
	
	def execute(self, database):
		super(OutputPlugin, self).execute(database)
		# Construct a dictionary mapping database objects to XML elements
		# representing those objects
		logging.debug('Generating SQL')
		self.script = []
		database.touch(self.comment_object)
		# Encode the SQL with the target encoding
		logging.debug('Converting SQL')
		s = unicode('\n\n'.join(stmt for stmt in self.script))
		s = codecs.getencoder(self.options['encoding'])(s)[0]
		# Finally, write the document to disk
		logging.info('Writing output to "%s"' % self.options['filename'])
		f = open(self.options['filename'], 'w')
		try:
			f.write(s)
		finally:
			f.close()

	def comment_object(self, dbobject):
		method = None
		class_map = {
			Alias:      self.comment_alias,
			Constraint: self.comment_constraint,
			Datatype:   self.comment_datatype,
			Function:   self.comment_function,
			Index:      self.comment_index,
			Procedure:  self.comment_procedure,
			Schema:     self.comment_schema,
			Table:      self.comment_table,
			Tablespace: self.comment_tablespace,
			Trigger:    self.comment_trigger,
			View:       self.comment_table,
		}
		try:
			method = class_map[type(dbobject)]
		except KeyError:
			for dbclass in class_map:
				if isinstance(dbobject, dbclass):
					method = class_map[dbclass]
		if method:
			sql = method(dbobject)
			if sql:
				self.script.append(sql)

	def comment(self, label, name, description):
		if description or self.options['blanks']:
			return 'COMMENT ON %s %s IS %s%s' % (
				label,
				name,
				quote(description or ''),
				self.options['terminator'],
			)
	
	def comment_alias(self, o):
		return self.comment('ALIAS', o.qualified_name, o.description)

	def comment_constraint(self, o):
		return self.comment('CONSTRAINT', o.qualified_name, o.description)

	def comment_datatype(self, o):
		return self.comment('TYPE', o.qualified_name, o.description)

	def comment_function(self, o):
		return self.comment('SPECIFIC FUNCTION', o.qualified_specific_name, o.description)

	def comment_index(self, o):
		return self.comment('INDEX', o.qualified_name, o.description)

	def comment_procedure(self, o):
		return self.comment('SPECIFIC PROCEDURE', o.qualified_specific_name, o.description)

	def comment_schema(self, o):
		return self.comment('SCHEMA', o.qualified_name, o.description)

	def comment_tablespace(self, o):
		return self.comment('TABLESPACE', o.name, o.description)

	def comment_trigger(self, o):
		return self.comment('TRIGGER', o.name, o.description)

	def comment_table(self, o):
		field_comments = ',\n'.join([
			'\t%s IS %s' % (f.name, quote(f.description))
			for f in o.field_list
			if f.description or self.options['blanks']
		])
		if field_comments:
			field_comments = 'COMMENT ON %s (\n%s\n)%s' % (
				o.qualified_name,
				field_comments,
				self.options['terminator']
			)
		if o.description or self.options['blanks']:
			table_comment = self.comment('TABLE', o.qualified_name, o.description)
		else:
			table_comment = ''
		if field_comments and table_comment:
			return '\n'.join([table_comment, field_comments])
		else:
			return table_comment or field_comments
