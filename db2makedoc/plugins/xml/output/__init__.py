# vim: set noet sw=4 ts=4:

"""Output plugin for XML metadata storage."""

import re
import logging
import db2makedoc.plugins
from db2makedoc.etree import fromstring, tostring, indent, Element, SubElement
from db2makedoc.db import (
	Database, Schema, Datatype, Table, View, Alias, Field, UniqueKey,
	PrimaryKey, ForeignKey, Check, Index, Trigger, Function, Procedure,
	Param, Tablespace
)
from string import Template


class OutputPlugin(db2makedoc.plugins.OutputPlugin):
	"""Output plugin for metadata storage (in XML format).

	This output plugin writes all database metadata into an XML file. This is
	intended for use in conjunction with the metadata input plugin, if you want
	metadata extraction and document creation to be performed separately (on
	separate machines or at separate times), or if you wish to use db2makedoc
	to provide metadata in a transportable format for some other application.
	The DTD of the output is not fully documented at the present time. The best
	way to learn it is to try the plugin with a database and check the result
	(which is properly indented for human readability).
	"""

	def __init__(self):
		"""Initializes an instance of the class."""
		super(OutputPlugin, self).__init__()
		self.add_option('filename', default=None, convert=self.convert_path,
			doc="""The path and filename for the XML output file. Use $db or
			${db} to include the name of the database in the filename. The
			$dblower and $dbupper substitutions are also available, for forced
			lowercase and uppercase versions of the name respectively. To
			include a literal $, use $$""")
		self.add_option('encoding', default='UTF-8',
			doc="""The character encoding to use for the XML output file (optional)""")
		self.add_option('indent', default=True, convert=self.convert_bool,
			doc="""If true (the default), the XML will be indented for human readbility""")

	def configure(self, config):
		super(OutputPlugin, self).configure(config)
		# Ensure we can find the specified encoding
		u''.encode(self.options['encoding'])
		# Ensure the filename was specified
		if not self.options['filename']:
			raise db2makedoc.plugins.PluginConfigurationError('The filename option must be specified')
	
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
		# Construct a dictionary mapping database objects to XML elements
		# representing those objects
		logging.debug('Constructing elements')
		self.elements = {}
		database.touch(self.make_element)
		# Stitch together the XML tree by adding each element to its parent
		logging.debug('Constructing element hierarchy')
		for db_object, element in self.elements.iteritems():
			if db_object.parent:
				parent = self.elements[db_object.parent]
				parent.append(element)
		# Find the root document element, convert the document to a string with
		# an appropriate XML PI
		logging.debug('Converting output')
		root = self.elements[database]
		if self.options['indent']:
			indent(root)
		s = unicode(tostring(root))
		s = u'<?xml version="1.0" encoding="%s"?>\n%s' % (self.options['encoding'], s)
		# Check there aren't any silly characters (control characters / binary)
		# lurking in the unicode version. Most codecs will blindly pass these
		# through but they're invalid in XML
		s = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F]+', lambda m: '?'*len(m.group()), s)
		s = s.encode(self.options['encoding'])
		# Finally, write the document to disk
		logging.info('Writing output to "%s"' % self.options['filename'])
		f = open(self.options['filename'], 'w')
		try:
			f.write(s)
		finally:
			f.close()
	
	def make_element(self, db_object):
		logging.debug('Constructing element for %s' % db_object.identifier)
		self.elements[db_object] = {
			Database:   self.make_database,
			Schema:     self.make_schema,
			Datatype:   self.make_datatype,
			Table:      self.make_table,
			View:       self.make_view,
			Alias:      self.make_alias,
			Field:      self.make_field,
			UniqueKey:  self.make_unique_key,
			PrimaryKey: self.make_primary_key,
			ForeignKey: self.make_foreign_key,
			Check:      self.make_check,
			Index:      self.make_index,
			Trigger:    self.make_trigger,
			Function:   self.make_function,
			Procedure:  self.make_procedure,
			Tablespace: self.make_tablespace,
		}[type(db_object)](db_object)
	
	def make_database(self, database):
		result = Element('database')
		result.attrib['id'] = database.identifier
		result.attrib['name'] = database.name
		return result

	def make_schema(self, schema):
		result = Element('schema')
		result.attrib['id'] = schema.identifier
		result.attrib['name'] = schema.name
		if schema.owner:
			result.attrib['owner'] = schema.owner
		if schema.system:
			result.attrib['system'] = 'system'
		if schema.created:
			result.attrib['created'] = schema.created.isoformat()
		if schema.description:
			SubElement(result, 'description').text = schema.description
		return result

	def make_datatype(self, datatype):
		result = Element('datatype')
		result.attrib['id'] = datatype.identifier
		result.attrib['name'] = datatype.name
		if datatype.owner:
			result.attrib['owner'] = datatype.owner
		if datatype.system:
			result.attrib['system'] = 'system'
		if datatype.created:
			result.attrib['created'] = datatype.created.isoformat()
		if datatype.variable_size:
			result.attrib['variable'] = ['size', 'scale'][datatype.variable_scale]
		if datatype.source:
			result.attrib['source'] = datatype.source.identifier
			if datatype.source.variable_size:
				result.attrib['size'] = str(datatype.size)
				if datatype.source.variable_scale:
					result.attrib['scale'] = str(datatype.scale)
		if datatype.description:
			SubElement(result, 'description').text = datatype.description
		return result

	def make_table(self, table):
		result = Element('table')
		result.attrib['id'] = table.identifier
		result.attrib['name'] = table.name
		result.attrib['tablespace'] = table.tablespace.identifier
		if table.owner:
			result.attrib['owner'] = table.owner
		if table.system:
			result.attrib['system'] = 'system'
		if table.created:
			result.attrib['created'] = table.created.isoformat()
		if table.last_stats:
			result.attrib['laststats'] = table.last_stats.isoformat()
		if table.cardinality:
			result.attrib['cardinality'] = str(table.cardinality)
		if table.size:
			result.attrib['size'] = str(table.size)
		if table.description:
			SubElement(result, 'description').text = table.description
		# XXX Add reverse dependencies?
		# XXX Add associated triggers?
		# XXX Add creation SQL?
		return result

	def make_view(self, view):
		result = Element('view')
		result.attrib['id'] = view.identifier
		result.attrib['name'] = view.name
		if view.owner:
			result.attrib['owner'] = view.owner
		if view.system:
			result.attrib['system'] = 'system'
		if view.created:
			result.attrib['created'] = view.created.isoformat()
		if view.read_only:
			result.attrib['readonly'] = 'readonly'
		if view.description:
			SubElement(result, 'description').text = view.description
		SubElement(result, 'sql').text = view.sql
		for dependency in view.dependency_list:
			SubElement(result, 'viewdep').attrib['ref'] = dependency.identifier
		return result

	def make_alias(self, alias):
		result = Element('alias')
		result.attrib['id'] = alias.identifier
		result.attrib['name'] = alias.name
		result.attrib['relation'] = alias.relation.identifier
		if alias.owner:
			result.attrib['owner'] = alias.owner
		if alias.system:
			result.attrib['system'] = 'system'
		if alias.created:
			result.attrib['created'] = alias.created.isoformat()
		if alias.description:
			SubElement(result, 'description').text = alias.description
		# XXX Add creation SQL?
		return result

	def make_field(self, field):
		result = Element('field')
		result.attrib['id'] = field.identifier
		result.attrib['name'] = field.name
		result.attrib['position'] = str(field.position)
		result.attrib['datatype'] = field.datatype.identifier
		if field.datatype.variable_size:
			result.attrib['size'] = str(field.size)
			if field.datatype.variable_scale:
				result.attrib['scale'] = str(field.scale)
		if field.codepage:
			result.attrib['codepage'] = str(field.codepage)
		if field.nullable:
			result.attrib['nullable'] = 'nullable'
			if field.null_cardinality:
				result.attrib['null_cardinality'] = str(field.null_cardinality)
		if field.cardinality:
			result.attrib['cardinality'] = str(field.cardinality)
		if field.identity:
			result.attrib['identity'] = 'identity'
		if field.generated == 'N':
			if field.default:
				result.attrib['default'] = field.default
		else:
			result.attrib['generated'] = {
				'A': 'always',
				'D': 'default',
			}[field.generated]
			if field.default:
				result.attrib['expression'] = field.default
		if field.description:
			SubElement(result, 'description').text = field.description
		# XXX Add key position?
		# XXX Add creation SQL?
		return result

	def make_unique_key(self, key):
		result = Element('uniquekey')
		result.attrib['id'] = key.identifier
		result.attrib['name'] = key.name
		if key.owner:
			result.attrib['owner'] = key.owner
		if key.system:
			result.attrib['system'] = 'system'
		if key.created:
			result.attrib['created'] = key.created.isoformat()
		if key.description:
			SubElement(result, 'description').text = key.description
		for field in key.fields:
			SubElement(result, 'keyfield').attrib['ref'] = field.identifier
		# XXX Include parent keys?
		return result

	def make_primary_key(self, key):
		result = self.make_unique_key(key)
		result.tag = 'primarykey'
		return result

	def make_foreign_key(self, key):
		action_map = {
			'A': 'noaction',
			'C': 'cascade',
			'N': 'setnull',
			'R': 'restrict',
		}
		result = Element('foreignkey')
		result.attrib['id'] = key.identifier
		result.attrib['name'] = key.name
		result.attrib['ondelete'] = action_map[key.delete_rule]
		result.attrib['onupdate'] = action_map[key.update_rule]
		result.attrib['references'] = key.ref_key.identifier
		if key.owner:
			result.attrib['owner'] = key.owner
		if key.system:
			result.attrib['system'] = 'system'
		if key.created:
			result.attrib['created'] = key.created.isoformat()
		if key.description:
			SubElement(result, 'description').text = key.description
		for (field, parent) in key.fields:
			e = SubElement(result, 'fkeyfield')
			e.attrib['sourceref'] = field.identifier
			e.attrib['targetref'] = parent.identifier
		return result

	def make_check(self, check):
		result = Element('check')
		result.attrib['id'] = check.identifier
		result.attrib['name'] = check.name
		if check.owner:
			result.attrib['owner'] = check.owner
		if check.system:
			result.attrib['system'] = 'system'
		if check.created:
			result.attrib['created'] = check.created.isoformat()
		if check.description:
			SubElement(result, 'description').text = check.description
		if check.expression:
			SubElement(result, 'expression').text = check.expression
		for field in check.fields:
			SubElement(result, 'checkfield').attrib['ref'] = field.identifier
		return result

	def make_index(self, index):
		result = Element('index')
		result.attrib['id'] = index.identifier
		result.attrib['name'] = index.name
		result.attrib['table'] = index.table.identifier
		result.attrib['tablespace'] = index.tablespace.identifier
		if index.owner:
			result.attrib['owner'] = index.owner
		if index.system:
			result.attrib['system'] = 'system'
		if index.created:
			result.attrib['created'] = index.created.isoformat()
		if index.last_stats:
			result.attrib['laststats'] = index.last_stats.isoformat()
		if index.cardinality:
			result.attrib['cardinality'] = str(index.cardinality)
		if index.size:
			result.attrib['size'] = str(index.size)
		if index.unique:
			result.attrib['unique'] = 'unique'
		if index.description:
			SubElement(result, 'description').text = index.description
		for (field, order) in index.field_list:
			e = SubElement(result, 'indexfield')
			e.attrib['ref'] = field.identifier
			e.attrib['order'] = {
				'A': 'asc',
				'D': 'desc',
				'I': 'include',
			}[order]
		# XXX Add creation SQL?
		return result

	def make_trigger(self, trigger):
		result = Element('trigger')
		result.attrib['id'] = trigger.identifier
		result.attrib['name'] = trigger.name
		result.attrib['relation'] = trigger.relation.identifier
		result.attrib['time'] = {
			'A': 'after',
			'B': 'before',
			'I': 'instead',
		}[trigger.trigger_time]
		result.attrib['event'] = {
			'I': 'insert',
			'U': 'update',
			'D': 'delete',
		}[trigger.trigger_event]
		result.attrib['granularity'] = {
			'R': 'row',
			'S': 'statement',
		}[trigger.granularity]
		if trigger.owner:
			result.attrib['owner'] = trigger.owner
		if trigger.system:
			result.attrib['system'] = 'system'
		if trigger.created:
			result.attrib['created'] = trigger.created.isoformat()
		if trigger.description:
			SubElement(result, 'description').text = trigger.description
		if trigger.sql:
			SubElement(result, 'sql').text = trigger.sql
		for dependency in trigger.dependency_list:
			SubElement(result, 'trigdep').attrib['ref'] = dependency.identifier
		return result

	def make_function(self, function):
		result = Element('function')
		result.attrib['id'] = function.identifier
		result.attrib['name'] = function.name
		result.attrib['specificname'] = function.specific_name
		result.attrib['type'] = {
			'C': 'column',
			'R': 'row',
			'T': 'table',
			'S': 'scalar',
		}[function.type]
		result.attrib['access'] = {
			None: 'none',
			'N':  'none',
			'C':  'contains',
			'R':  'reads',
			'M':  'modifies',
		}[function.sql_access]
		if function.owner:
			result.attrib['owner'] = function.owner
		if function.system:
			result.attrib['system'] = 'system'
		if function.created:
			result.attrib['created'] = function.created.isoformat()
		if function.deterministic:
			result.attrib['deterministic'] = 'deterministic'
		if function.external_action:
			result.attrib['externalaction'] = 'externalaction'
		if function.null_call:
			result.attrib['nullcall'] = 'nullcall'
		if function.description:
			SubElement(result, 'description').text = function.description
		if function.sql:
			SubElement(result, 'sql').text = function.sql
		for param in function.param_list:
			result.append(self.make_param(param))
		for param in function.return_list:
			result.append(self.make_param(param))
		return result

	def make_procedure(self, procedure):
		result = Element('procedure')
		result.attrib['id'] = procedure.identifier
		result.attrib['name'] = procedure.name
		result.attrib['specificname'] = procedure.specific_name
		result.attrib['access'] = {
			None: 'none',
			'N':  'none',
			'C':  'contains',
			'R':  'reads',
			'M':  'modifies',
		}[procedure.sql_access]
		if procedure.owner:
			result.attrib['owner'] = procedure.owner
		if procedure.system:
			result.attrib['system'] = 'system'
		if procedure.created:
			result.attrib['created'] = procedure.created.isoformat()
		if procedure.deterministic:
			result.attrib['deterministic'] = 'deterministic'
		if procedure.external_action:
			result.attrib['externalaction'] = 'externalaction'
		if procedure.null_call:
			result.attrib['nullcall'] = 'nullcall'
		if procedure.description:
			SubElement(result, 'description').text = procedure.description
		if procedure.sql:
			SubElement(result, 'sql').text = procedure.sql
		for param in procedure.param_list:
			result.append(self.make_param(param))
		return result

	def make_param(self, param):
		result = Element('parameter')
		result.attrib['id'] = param.identifier
		result.attrib['name'] = param.name
		result.attrib['type'] = {
			'I': 'in',
			'O': 'out',
			'B': 'inout',
			'R': 'return',
		}[param.type]
		result.attrib['position'] = str(param.position)
		result.attrib['datatype'] = param.datatype.identifier
		if param.datatype.variable_size:
			if param.size is not None:
				result.attrib['size'] = str(param.size)
			if param.datatype.variable_scale:
				if param.scale is not None:
					result.attrib['scale'] = str(param.scale)
		if param.codepage:
			result.attrib['codepage'] = str(param.codepage)
		if param.description:
			SubElement(result, 'description').text = param.description
		return result

	def make_tablespace(self, tablespace):
		result = Element('tablespace')
		result.attrib['id'] = tablespace.identifier
		result.attrib['name'] = tablespace.name
		result.attrib['type'] = tablespace.type
		if tablespace.owner:
			result.attrib['owner'] = tablespace.owner
		if tablespace.system:
			result.attrib['system'] = 'system'
		if tablespace.created:
			result.attrib['created'] = tablespace.created.isoformat()
		if tablespace.description:
			SubElement(result, 'description').text = tablespace.description
		# XXX Include table and index lists?
		#for table in tablespace.table_list:
		#	SubElement(result, 'containstable').attrib['ref'] = table.identifier
		#for index in tablespace.index_list:
		#	SubElement(result, 'containsindex').attrib['ref'] = index.identifier
		return result
