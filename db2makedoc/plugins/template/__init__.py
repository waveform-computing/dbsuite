# $Header$
# vim: set noet sw=4 ts=4:

"""Output plugin for kid XML templates.

This output plugin supports generating XML, HTML or plain text output by
filling in "kid" [1] templates which are written in XML. Depending on the
content of the template, output can include syntax highlighted SQL, and visual
diagrams of the schema.

For example, this plugin could be used to generate XHTML web-pages, DocBook
documents, plain text files, or even SVG images.

[1] http://www.kid-templating.org/
"""

import os
import kid

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
TEMPLATE_PATH_DESC = 'The folder which all template and static files exist ' \
	'relative to. If a template filename is blank (all are blank by default), ' \
	'nothing will be produced for objects of the associated type'
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
MISSING_OPTION = 'The "%s" option must be specified'

# Plugin options dictionary
options = {
	TEMPLATE_PATH_OPTION: TEMPLATE_PATH_DESC,
	STATIC_OPTION: STATIC_DESC,
	DB_TEMPLATE_OPTION: DB_TEMPLATE_DESC,
	SCHEMA_TEMPLATE_OPTION: SCHEMA_TEMPLATE_DESC,
	TBSPACE_TEMPLATE_OPTION: TBSPACE_TEMPLATE_DESC,
	TABLE_TEMPLATE_OPTION: TABLE_TEMPLATE_DESC,
	VIEW_TEMPLATE_OPTION: VIEW_TEMPLATE_DESC,
	ALIAS_TEMPLATE_OPTION: ALIAS_TEMPLATE_DESC,
	UKEY_TEMPLATE_OPTION: UKEY_TEMPLATE_DESC,
	FKEY_TEMPLATE_OPTION: FKEY_TEMPLATE_DESC,
	CHECK_TEMPLATE_OPTION: CHECK_TEMPLATE_DESC,
	INDEX_TEMPLATE_OPTION: INDEX_TEMPLATE_DESC,
	TRIGGER_TEMPLATE_OPTION: TRIGGER_TEMPLATE_DESC,
	FUNC_TEMPLATE_OPTION: FUNC_TEMPLATE_DESC,
	PROC_TEMPLATE_OPTION: PROC_TEMPLATE_DESC,
	PATH_OPTION: PATH_DESC,
	AUTHOR_NAME_OPTION: AUTHOR_NAME_DESC,
	AUTHOR_MAIL_OPTION: AUTHOR_MAIL_DESC,
	COPYRIGHT_OPTION: COPYRIGHT_DESC,
}

def Output(database, config):
	# Check the config dictionary for missing stuff
	if not PATH_OPTION in config:
		raise Exception(MISSING_OPTION % PATH_OPTION)
	if not TEMPLATE_PATH_OPTION in config:
		raise Exception(MISSING_OPTION % TEMPLATE_PATH_OPTION)
	# XXX How to deal with STATIC_OPTION here??
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
		if path in config:
			config[path] = os.path.expanduser(os.path.expandvars(config[path]))
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
		if template in config:
			config[template] = os.path.join(config[TEMPLATE_PATH_OPTION], config[template])
	# For all objects in the database hierarchy, run the corresponding template
	# (if one has been specified for objects of that type). The output options
	# (which are not really needed at template instantiation) are passed as
	# attributes of an object to allow the template code to modify their values
	db_template = init_template(config.get(DB_TEMPLATE_OPTION))
	schema_template = init_template(config.get(SCHEMA_TEMPLATE_OPTION))
	table_template = init_template(config.get(TABLE_TEMPLATE_OPTION))
	ukey_template = init_template(config.get(UKEY_TEMPLATE_OPTION))
	fkey_template = init_template(config.get(FKEY_TEMPLATE_OPTION))
	check_template = init_template(config.get(CHECK_TEMPLATE_OPTION))
	view_template = init_template(config.get(VIEW_TEMPLATE_OPTION))
	alias_template = init_template(config.get(ALIAS_TEMPLATE_OPTION))
	index_template = init_template(config.get(INDEX_TEMPLATE_OPTION))
	func_template = init_template(config.get(FUNC_TEMPLATE_OPTION))
	proc_template = init_template(config.get(PROC_TEMPLATE_OPTION))
	trigger_template = init_template(config.get(TRIGGER_TEMPLATE_OPTION))
	tbspace_template = init_template(config.get(TBSPACE_TEMPLATE_OPTION))

	exec_template(db_template, database, config)
	for schema in database.schemas.itervalues():
		exec_template(schema_template, schema, config)
		for table in schema.tables.itervalues():
			exec_template(table_template, table, config)
			for uniquekey in table.unique_keys.itervalues():
				exec_template(ukey_template, uniquekey, config)
			for foreignkey in table.foreign_keys.itervalues():
				exec_template(fkey_template, foreignkey, config)
			for check in table.checks.itervalues():
				exec_template(check_template, check, config)
		for view in schema.views.itervalues():
			exec_template(view_template, view, config)
		for alias in schema.aliases.itervalues():
			exec_template(alias_template, alias, config)
		for index in schema.indexes.itervalues():
			exec_template(index_template, index, config)
		for function in schema.specific_functions.itervalues():
			exec_template(func_template, function, config)
		for procedure in schema.specific_procedures.itervalues():
			exec_template(proc_template, procedure, config)
		for trigger in schema.triggers.itervalues():
			exec_template(trigger_template, trigger, config)
	for tablespace in database.tablespaces.itervalues():
		exec_template(tbspace_template, tablespace, config)

# Class for storing serialization and output formatting options. Instances of
# the class are passed to loaded template modules as a global variable named
# 'output', allowing the template code to edit the attributes. This provides a
# mechanism for the template itself to inform the caller how it wishes to be
# serialized.
class OutputOptions(object):
	def __init__(self):
		self.method = DEFAULT_METHOD
		self.format = DEFAULT_FORMAT
		self.extension = DEFAULT_SUFFIX
		self.encoding = DEFAULT_ENCODING

# Utility routine for loading and configuring a template with an OutputOptions
# instance.
def init_template(filename):
	if filename:
		module = kid.load_template(filename, ns={'output': OutputOptions()})
		return module

# Utility routine for executing a template with a database object and
# configuration values.
def exec_template(module, dbobject, config):
	if module:
		template = module.Template(
			dbobject=dbobject,
			author_name=config.get(AUTHOR_NAME_OPTION),
			author_email=config.get(AUTHOR_MAIL_OPTION),
			copyright=config.get(COPYRIGHT_OPTION))
		template.write(
			file=os.path.join(config[PATH_OPTION], dbobject.identifier + module.output.extension),
			encoding=module.output.encoding,
			output=module.output.method,
			format=module.output.format)
