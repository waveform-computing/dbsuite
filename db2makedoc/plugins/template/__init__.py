# $Header$
# vim: set noet sw=4 ts=4:

"""Output plugin for kid XML templates."""

import os
import kid
import db2makedoc.plugins

# Constants
TEMPLATE_PATH_OPTION = 'template_path'
STATIC_OPTION = 'static'
DB_TEMPLATE_OPTION = 'db_template'
SCHEMA_TEMPLATE_OPTION = 'schema_template'
TBSPACE_TEMPLATE_OPTION = 'tbspace_template'
TABLE_TEMPLATE_OPTION = 'table_template'
VIEW_TEMPLATE_OPTION = 'view_template'
ALIAS_TEMPLATE_OPTION = 'alias_template'
UKEY_TEMPLATE_OPTION = 'ukey_template'
FKEY_TEMPLATE_OPTION = 'fkey_template'
CHECK_TEMPLATE_OPTION = 'check_template'
INDEX_TEMPLATE_OPTION = 'index_template'
TRIGGER_TEMPLATE_OPTION = 'trigger_template'
FUNC_TEMPLATE_OPTION = 'func_template'
PROC_TEMPLATE_OPTION = 'proc_template'
AUTHOR_NAME_OPTION = 'author_name'
AUTHOR_MAIL_OPTION = 'author_email'
COPYRIGHT_OPTION = 'copyright'
PATH_OPTION = 'path'

# Default output options
DEFAULT_SUFFIX = '.xml'
DEFAULT_METHOD = 'xml'
DEFAULT_FORMAT = 'default'
DEFAULT_ENCODING = 'utf-8'

# Localizable strings
TEMPLATE_PATH_DESC = '''The folder which all template and static files exist
	relative to. If a template filename is blank (all are blank by default),
	nothing will be produced for objects of the associated type'''
STATIC_DESC = 'A space separated list of static files to be copied verbatim into the target directory (optional)'
DB_TEMPLATE_DESC = 'The filename of the template used to transform the Database object (optional)'
SCHEMA_TEMPLATE_DESC = 'The filename of the template used to transform Schema objects (optional)'
TBSPACE_TEMPLATE_DESC = 'The filename of the template used to transform TableSpace objects (optional)'
TABLE_TEMPLATE_DESC = 'The filename of the template used to transform Table objects (optional)'
VIEW_TEMPLATE_DESC = 'The filename of the template used to transform View objects (optional)'
ALIAS_TEMPLATE_DESC = 'The filename of the template used to transform Alias objects (optional)'
UKEY_TEMPLATE_DESC = 'The filename of the template used to transform UniqueKey constraint objects (optional)'
FKEY_TEMPLATE_DESC = 'The filename of the template used to transform ForeignKey constraint objects (optional)'
CHECK_TEMPLATE_DESC = 'The filename of the template used to transform Check constraint objects (optional)'
INDEX_TEMPLATE_DESC = 'The filename of the template used to transform Index objects (optional)'
TRIGGER_TEMPLATE_DESC = 'The filename of the template used to transform Trigger objects (optional)'
FUNC_TEMPLATE_DESC = 'The filename of the template used to transform Function objects (optional)'
PROC_TEMPLATE_DESC = 'The filename of the template used to transform Procedure objects (optional)'
AUTHOR_NAME_DESC = 'The name of the author of the generated documentation (optional)'
AUTHOR_MAIL_DESC = 'The e-mail address of the author of the generated documentation (optional)'
COPYRIGHT_DESC = 'The copyright message to embed in the generated documentation (optional)'
PATH_DESC = 'The folder into which all output files will be written'


class OutputOptions(object):
	"""Class for storing serialization and output formatting options.

	Instances of the class are passed to loaded template modules as a global
	variable named 'output', allowing the template code to edit the attributes.
	This provides a mechanism for the template itself to inform the caller how
	it wishes to be serialized.
	"""

	def __init__(self):
		"""Initializes an instance of the class."""
		super(OutputOptions, self).__init__()
		self.method = DEFAULT_METHOD
		self.format = DEFAULT_FORMAT
		self.extension = DEFAULT_SUFFIX
		self.encoding = DEFAULT_ENCODING


class OutputPlugin(db2makedoc.plugins.OutputPlugin):
	"""Output plugin for kid XML templates.

	This output plugin supports generating XML, HTML or plain text output by
	filling in "kid" [1] templates which are written in XML. Depending on the
	content of the template, output can include syntax highlighted SQL, and
	visual diagrams of the schema.

	For example, this plugin could be used to generate XHTML web-pages, DocBook
	documents, plain text files, or even SVG images.

	[1] http://www.kid-templating.org/
	"""

	def __init__(self):
		"""Initializes an instance of the class."""
		super(OutputPlugin, self).__init__()
		self.add_option(TEMPLATE_PATH_OPTION, default='./templates', doc=TEMPLATE_PATH_DESC)
		self.add_option(PATH_OPTION, default='./public_html', doc=PATH_DESC)
		self.add_option(STATIC_OPTION, default=None, doc=STATIC_DESC)
		self.add_option(DB_TEMPLATE_OPTION, default=None, doc=DB_TEMPLATE_DESC)
		self.add_option(SCHEMA_TEMPLATE_OPTION, default=None, doc=SCHEMA_TEMPLATE_DESC)
		self.add_option(TBSPACE_TEMPLATE_OPTION, default=None, doc=TBSPACE_TEMPLATE_DESC)
		self.add_option(TABLE_TEMPLATE_OPTION, default=None, doc=TABLE_TEMPLATE_DESC)
		self.add_option(VIEW_TEMPLATE_OPTION, default=None, doc=VIEW_TEMPLATE_DESC)
		self.add_option(ALIAS_TEMPLATE_OPTION, default=None, doc=ALIAS_TEMPLATE_DESC)
		self.add_option(UKEY_TEMPLATE_OPTION, default=None, doc=UKEY_TEMPLATE_DESC)
		self.add_option(FKEY_TEMPLATE_OPTION, default=None, doc=FKEY_TEMPLATE_DESC)
		self.add_option(CHECK_TEMPLATE_OPTION, default=None, doc=CHECK_TEMPLATE_DESC)
		self.add_option(INDEX_TEMPLATE_OPTION, default=None, doc=INDEX_TEMPLATE_DESC)
		self.add_option(TRIGGER_TEMPLATE_OPTION, default=None, doc=TRIGGER_TEMPLATE_DESC)
		self.add_option(FUNC_TEMPLATE_OPTION, default=None, doc=FUNC_TEMPLATE_DESC)
		self.add_option(PROC_TEMPLATE_OPTION, default=None, doc=PROC_TEMPLATE_DESC)
		self.add_option(AUTHOR_NAME_OPTION, default=None, doc=AUTHOR_NAME_DESC)
		self.add_option(AUTHOR_MAIL_OPTION, default=None, doc=AUTHOR_MAIL_DESC)
		self.add_option(COPYRIGHT_OPTION, default=None, doc=COPYRIGHT_DESC)

	def configure(self, config):
		"""Loads the plugin configuration."""
		super(OutputPlugin, self).configure(config)
		# Expand any variables or references in the path options
		for path in (
				TEMPLATE_PATH_OPTION,
				STATIC_OPTION,
				DB_TEMPLATE_OPTION,
				SCHEMA_TEMPLATE_OPTION,
				TBSPACE_TEMPLATE_OPTION,
				TABLE_TEMPLATE_OPTION,
				VIEW_TEMPLATE_OPTION,
				ALIAS_TEMPLATE_OPTION,
				UKEY_TEMPLATE_OPTION,
				FKEY_TEMPLATE_OPTION,
				CHECK_TEMPLATE_OPTION,
				INDEX_TEMPLATE_OPTION,
				TRIGGER_TEMPLATE_OPTION,
				FUNC_TEMPLATE_OPTION,
				PROC_TEMPLATE_OPTION,
				PATH_OPTION,
			):
			if self.options[path] is not None:
				self.options[path] = os.path.expanduser(os.path.expandvars(self.options[path]))
		# Transform all relative template paths into absolute paths
		for template in (
				DB_TEMPLATE_OPTION,
				SCHEMA_TEMPLATE_OPTION,
				TBSPACE_TEMPLATE_OPTION,
				TABLE_TEMPLATE_OPTION,
				VIEW_TEMPLATE_OPTION,
				ALIAS_TEMPLATE_OPTION,
				UKEY_TEMPLATE_OPTION,
				FKEY_TEMPLATE_OPTION,
				CHECK_TEMPLATE_OPTION,
				INDEX_TEMPLATE_OPTION,
				TRIGGER_TEMPLATE_OPTION,
				FUNC_TEMPLATE_OPTION,
				PROC_TEMPLATE_OPTION,
			):
			if self.options[template] is not None:
				self.options[template] = os.path.join(self.options[TEMPLATE_PATH_OPTION], self.options[template])
	
	def execute(self, database):
		"""Invokes the plugin to produce documentation."""
		super(OutputPlugin, self).execute(database)
		# XXX How to deal with STATIC_OPTION here??
		# For all objects in the database hierarchy, run the corresponding
		# template (if one has been specified for objects of that type). The
		# output options (which are not really needed at template
		# instantiation) are passed as attributes of an object to allow the
		# template code to modify their values
		db_template = init_template(self.options[DB_TEMPLATE_OPTION])
		schema_template = init_template(self.options[SCHEMA_TEMPLATE_OPTION])
		table_template = init_template(self.options[TABLE_TEMPLATE_OPTION])
		ukey_template = init_template(self.options[UKEY_TEMPLATE_OPTION])
		fkey_template = init_template(self.options[FKEY_TEMPLATE_OPTION])
		check_template = init_template(self.options[CHECK_TEMPLATE_OPTION])
		view_template = init_template(self.options[VIEW_TEMPLATE_OPTION])
		alias_template = init_template(self.options[ALIAS_TEMPLATE_OPTION])
		index_template = init_template(self.options[INDEX_TEMPLATE_OPTION])
		func_template = init_template(self.options[FUNC_TEMPLATE_OPTION])
		proc_template = init_template(self.options[PROC_TEMPLATE_OPTION])
		trigger_template = init_template(self.options[TRIGGER_TEMPLATE_OPTION])
		tbspace_template = init_template(self.options[TBSPACE_TEMPLATE_OPTION])

		exec_template(db_template, database)
		for schema in database.schemas.itervalues():
			exec_template(schema_template, schema)
			for table in schema.tables.itervalues():
				exec_template(table_template, table)
				for uniquekey in table.unique_keys.itervalues():
					exec_template(ukey_template, uniquekey)
				for foreignkey in table.foreign_keys.itervalues():
					exec_template(fkey_template, foreignkey)
				for check in table.checks.itervalues():
					exec_template(check_template, check)
			for view in schema.views.itervalues():
				exec_template(view_template, view)
			for alias in schema.aliases.itervalues():
				exec_template(alias_template, alias)
			for index in schema.indexes.itervalues():
				exec_template(index_template, index)
			for function in schema.specific_functions.itervalues():
				exec_template(func_template, function)
			for procedure in schema.specific_procedures.itervalues():
				exec_template(proc_template, procedure)
			for trigger in schema.triggers.itervalues():
				exec_template(trigger_template, trigger)
		for tablespace in database.tablespaces.itervalues():
			exec_template(tbspace_template, tablespace)

	def init_template(filename):
		"""Utility routine for loading and configuring a template with an OutputOptions instance."""
		if filename:
			module = kid.load_template(filename, ns={'output': OutputOptions()})
			return module

	def exec_template(module, dbobject):
		"""Utility routine for executing a template with a database object and configuration values."""
		if module:
			template = module.Template(
				dbobject=dbobject,
				author_name=self.options[AUTHOR_NAME_OPTION],
				author_email=self.options[AUTHOR_MAIL_OPTION],
				copyright=self.options[COPYRIGHT_OPTION])
			template.write(
				file=os.path.join(self.options[PATH_OPTION], dbobject.identifier + module.output.extension),
				encoding=module.output.encoding,
				output=module.output.method,
				format=module.output.format)

