# vim: set noet sw=4 ts=4:

"""Output plugin for XML data storage."""

import codecs
import logging
import db2makedoc.plugins
from db2makedoc.etree import fromstring, tostring, Element, SubElement
from db2makedoc.db import (
	Database, Schema, Datatype, Table, View, Alias, Field, UniqueKey,
	PrimaryKey, ForeignKey, Check, Index, Trigger, Function, Procedure,
	Param, Tablespace
)


FILENAME_OPTION = 'filename'
ENCODING_OPTION = 'encoding'
INDENT_OPTION = 'indent'

FILENAME_DESC = """The filename for the XML output file (mandatory)"""
ENCODING_DESC = """The character encoding to use for the XML output file (optional)"""
INDENT_DESC = """If true (the default), the XML will be indented for human readability"""


def indent(elem, level=0):
	"""Pretty prints XML with indentation.

	This is a small utility routine adapted from the ElementTree website which
	indents XML (in-place) to enable easier reading by humans.
	"""
	i = '\n' + '\t' * level
	if len(elem):
		if not elem.text or not elem.text.strip():
			elem.text = i + '\t'
		for child in elem:
			indent(child, level + 1)
		if not child.tail or not child.tail.strip():
			child.tail = i
		if not elem.tail or not elem.tail.strip():
			elem.tail = i
	else:
		if level and (not elem.tail or not elem.tail.strip()):
			elem.tail = i


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
		self.add_option(FILENAME_OPTION, default=None, doc=FILENAME_DESC,
			convert=self.convert_path)
		self.add_option(ENCODING_OPTION, default='UTF-8', doc=ENCODING_DESC)
		self.add_option(INDENT_OPTION, default=True, doc=INDENT_DESC,
			convert=self.convert_bool)
	
	def configure(self, config):
		super(OutputPlugin, self).configure(config)
		codecs.lookup(self.options[ENCODING_OPTION])
	
	def execute(self, database):
		super(OutputPlugin, self).execute(database)
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
		# an appropriate XML PI and the specific encoding
		logging.debug('Converting output')
		root = self.elements[database]
		if self.options[INDENT_OPTION]:
			indent(root)
		s = unicode(tostring(root))
		s = u'''\
<?xml version="1.0" encoding="%(encoding)s"?>
%(content)s''' % {
			'encoding': self.options[ENCODING_OPTION],
			'content': s,
		}
		s = codecs.getencoder(self.options[ENCODING_OPTION])(s)[0]
		# Finally, write the document to disk
		logging.debug('Writing %s' % self.options[FILENAME_OPTION])
		f = open(self.options[FILENAME_OPTION], 'w')
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
		if datatype.source:
			# XXX DB2 specific?
			result.attrib['source'] = datatype.source.identifier
			if datatype.source.variable_size:
				result.attrib['size'] = str(datatype.size)
				if datatype.source.variable_scale:
					result.attrib['scale'] = str(datatype.scale)
		SubElement(result, 'description').text = datatype.description
		return result

	def make_table(self, table):
		result = Element('table')
		result.attrib['id'] = table.identifier
		result.attrib['name'] = table.name
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
		result.attrib['tablespace'] = table.tablespace.identifier
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
		SubElement(result, 'description').text = view.description
		SubElement(result, 'sql').text = view.sql
		for dependency in view.dependency_list:
			SubElement(result, 'viewdep').attrib['ref'] = dependency.identifier
		return result

	def make_alias(self, alias):
		result = Element('alias')
		result.attrib['id'] = alias.identifier
		result.attrib['name'] = alias.name
		if alias.owner:
			result.attrib['owner'] = alias.owner
		if alias.system:
			result.attrib['system'] = 'system'
		if alias.created:
			result.attrib['created'] = alias.created.isoformat()
		result.attrib['relation'] = alias.relation.identifier
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
		result = Element('foreignkey')
		result.attrib['id'] = key.identifier
		result.attrib['name'] = key.name
		if key.owner:
			result.attrib['owner'] = key.owner
		if key.system:
			result.attrib['system'] = 'system'
		if key.created:
			result.attrib['created'] = key.created.isoformat()
		action_map = {
			'A': 'noaction',
			'C': 'cascade',
			'N': 'setnull',
			'R': 'restrict',
		}
		result.attrib['ondelete'] = action_map[key.delete_rule]
		result.attrib['onupdate'] = action_map[key.update_rule]
		result.attrib['references'] = key.ref_key.identifier
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
		result.attrib['expression'] = check.expression
		SubElement(result, 'description').text = check.description
		for field in check.fields:
			SubElement(result, 'checkfield').attrib['ref'] = field.identifier
		return result

	def make_index(self, index):
		result = Element('index')
		result.attrib['id'] = index.identifier
		result.attrib['name'] = index.name
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
		result.attrib['table'] = index.table.identifier
		result.attrib['tablespace'] = index.tablespace.identifier
		SubElement(result, 'description').text = 'description'
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
		if trigger.owner:
			result.attrib['owner'] = trigger.owner
		if trigger.system:
			result.attrib['system'] = 'system'
		if trigger.created:
			result.attrib['created'] = trigger.created.isoformat()
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
		SubElement(result, 'description').text = trigger.description
		SubElement(result, 'sql').text = trigger.sql
		for dependency in trigger.dependency_list:
			SubElement(result, 'trigdep').attrib['ref'] = dependency.identifier
		return result

	def make_function(self, function):
		result = Element('function')
		result.attrib['id'] = function.identifier
		result.attrib['name'] = function.name
		result.attrib['specificname'] = function.specific_name
		if function.owner:
			result.attrib['owner'] = function.owner
		if function.system:
			result.attrib['system'] = 'system'
		if function.created:
			result.attrib['created'] = function.created.isoformat()
		result.attrib['type'] = {
			'C': 'column',
			'R': 'row',
			'T': 'table',
			'S': 'scalar',
		}[function.type]
		if function.deterministic:
			result.attrib['deterministic'] = 'deterministic'
		if function.external_action:
			result.attrib['externalaction'] = 'externalaction'
		if function.null_call:
			result.attrib['nullcall'] = 'nullcall'
		if function.sql_access:
			result.attrib['access'] = {
				'N': 'none',
				'C': 'contains',
				'R': 'reads',
				'M': 'modifies',
			}[function.sql_access]
		SubElement(result, 'description').text = function.description
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
		if procedure.sql_access:
			result.attrib['access'] = {
				'N': 'none',
				'C': 'contains',
				'R': 'reads',
				'M': 'modifies',
			}[procedure.sql_access]
		SubElement(result, 'description').text = procedure.description
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
			result.attrib['size'] = str(param.size)
			if param.datatype.variable_scale:
				result.attrib['scale'] = str(param.scale)
		if param.codepage:
			result.attrib['codepage'] = str(param.codepage)
		SubElement(result, 'description').text = param.description
		return result

	def make_tablespace(self, tablespace):
		result = Element('tablespace')
		result.attrib['id'] = tablespace.identifier
		result.attrib['name'] = tablespace.name
		if tablespace.owner:
			result.attrib['owner'] = tablespace.owner
		if tablespace.system:
			result.attrib['system'] = 'system'
		if tablespace.created:
			result.attrib['created'] = tablespace.created.isoformat()
		result.attrib['type'] = tablespace.type
		SubElement(result, 'description').text = tablespace.description
		# XXX Include table and index lists?
		#for table in tablespace.table_list:
		#	SubElement(result, 'containstable').attrib['ref'] = table.identifier
		#for index in tablespace.index_list:
		#	SubElement(result, 'containsindex').attrib['ref'] = index.identifier
		return result
