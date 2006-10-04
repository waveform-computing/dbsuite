# $Header$
# vim: set noet sw=4 ts=4:

# Standard modules
from string import Template

# Application-specific modules
from db.base import DocBase
from db.util import format_ident

class RelationObject(DocBase):
	"""Base class for database objects that belong directly to a relation"""

	def __init__(self, parent, name):
		"""Initializes an instance of the class"""
		super(RelationObject, self).__init__(parent, name)
		self.relation = self.parent
		self.schema = self.parent.parent
	
	def _get_database(self):
		return self.parent.parent.parent
	
class Constraint(RelationObject):
	"""Base class for constraints that belong in a relation (e.g. primary keys, checks, etc.)"""

	def __init__(self, parent, name):
		"""Initializes an instance of the class"""
		super(Constraint, self).__init__(parent, name)
		self.type_name = 'Constraint'
		self.table = self.parent
	
	def _get_identifier(self):
		return "constraint_%s_%s_%s" % (self.relation.name, self.schema.name, self.name)

	def _get_fields(self):
		raise NotImplementedError
	
	def _get_prototype(self):
		raise NotImplementedError
	
	def _get_create_sql(self):
		sql = Template('ALTER TABLE $schema.$table ADD $constdef;')
		return sql.substitute({
			'schema': format_ident(self.table.schema.name),
			'table': format_ident(self.table.name),
			'constdef': self.prototype
		})
	
	def _get_drop_sql(self):
		sql = Template('ALTER TABLE $schema.$table DROP CONSTRAINT $const;')
		return sql.substitute({
			'schema': format_ident(self.table.schema.name),
			'table': format_ident(self.table.name),
			'const': format_ident(self.name)
		})
	
	def _get_parent_list(self):
		return self.table.constraintList

	# Use the lambda trick to allow property getter methods to be overridden
	fields = property(lambda self: self._get_fields(), doc="""The fields constrained by this constraint""")
	prototype = property(lambda self: self._get_prototype(), doc="""The attributes of the constraint formatted for use in an ALTER TABLE or CREATE TABLE statement""")
