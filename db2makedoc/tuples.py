# vim: set noet sw=4 ts=4:

"""Defines all namedtuple classes used by input plugins to define the structure of their data.

This module defines all the namedtuple classes that are used by input plugins
to wrap the rows they retrieve from their source (e.g. a database), and by the
object hierarchy constructed by the application to represent the database
structure.
"""

from db2makedoc.util import *


__all__ = [
	'ObjectAttr',
	'Schema',
	'SchemaItemId',
	'Tablespace',
	'TablespaceRef',
	'Datatype',
	'DatatypeRef',
	'Relation',
	'RelationRef',
	'RelationItemId',
	'RelationDep',
	'Table',
	'TableRef',
	'TableItemId',
	'View',
	'Alias',
	'RelationCol',
	'Index',
	'IndexRef',
	'IndexItemId',
	'IndexCol',
	'Constraint',
	'ConstraintRef',
	'ConstraintItemId',
	'UniqueKey',
	'UniqueKeyCol',
	'ForeignKey',
	'ForeignKeyCol',
	'Check',
	'CheckCol',
	'RoutineId',
	'Routine',
	'RoutineRef',
	'RoutineItemId',
	'Function',
	'Procedure',
	'RoutineParam',
	'RoutineParamRef',
	'Trigger',
	'TriggerRef',
	'TriggerDep',
]


ObjectAttr = namedtuple('ObjectAttr', (
	'owner',              # Owner of the object
	'system',             # True if the object is system maintained (bool)
	'created',            # When the object was created (datetime)
	'description',        # Descriptive text
))

Schema = namedtuple('Schema', (
	'name',               # The name of the schema
) + ObjectAttr._fields)

SchemaItemId = namedtuple('SchemaItemId', (
	'schema',             # Schema which contains the item
	'name',               # Unique name of the item within the schema
))

Tablespace = namedtuple('Tablespace', (
	'name',               # The name of the tablespace
) + ObjectAttr._fields + (
	'type',               # The type of the tablespace as free text
))

TablespaceRef = namedtuple('TablespaceRef', (
	'tbspace',            # The name of the tablespace
))

Datatype = namedtuple('Datatype', SchemaItemId._fields + ObjectAttr._fields + (
	'variable_size',      # True if the type has a variable length (e.g. VARCHAR) (bool)
	'variable_scale',     # True if the type has a variable scale (e.g. DECIMAL) (bool)
	'source_schema',      # The schema of the base system type of the datatype
	'source_name',        # The name of the base system type of the datatype
	'size',               # The length of the type for character based types or the maximum precision for decimal types
	'scale',              # The maximum scale for decimal types
))

DatatypeRef = namedtuple('DatatypeRef', (
	'type_schema',        # The schema which contains the datatype
	'type_name',          # The name of the datatype
	'size',               # The length of the value for character types, or
	                      # the numeric precision for decimal types (None if
	                      # not a character or decimal type)
	'scale',              # The maximum scale for decimal types (None if not
	                      # a decimal type)
	'codepage',           # The codepage of the value for character types
	                      # (None if not a character type)
))

Relation = namedtuple('Relation', SchemaItemId._fields + ObjectAttr._fields)

RelationRef = namedtuple('RelationRef', (
	'relation_schema',    # The schema which contains the relation
	'relation_name',      # The name of the relation
))

RelationItemId = namedtuple('RelationItemId', RelationRef._fields + (
	'name',               # The name of the item belonging to the relation
))

RelationDep = namedtuple('RelationDep', SchemaItemId._fields + (
	'dep_schema',         # The schema of the relation upon which this relation depends
	'dep_name',           # The name of the relation upon which this relation depends
))

Table = namedtuple('Table', Relation._fields + TablespaceRef._fields + (
	'last_stats',         # When the table's statistics were last calculated (datetime)
	'cardinality',        # The approximate number of rows in the table
	'size',               # The approximate size in bytes of the table
))

TableRef = namedtuple('TableRef', (
	'table_schema',       # The schema which contains the table
	'table_name',         # The name of the table
))

TableItemId = namedtuple('TableItemId', TableRef._fields + (
	'name',               # The name of the item within the table
))

View = namedtuple('View', Relation._fields + (
	'read_only',          # True if the view is not updateable (bool)
	'sql',                # The SQL statement that defined the view
))

Alias = namedtuple('Alias', Relation._fields + (
	'base_schema',        # The schema of the target relation
	'base_name',          # The name of the target relation
))

RelationCol = namedtuple('RelationCol', RelationItemId._fields + DatatypeRef._fields + (
	'identity',           # True if the column is an identity column (bool)
	'nullable',           # True if the column can store NULL (bool)
	'cardinality',        # The approximate number of unique values in the column
	'null_card',          # The approximate number of NULLs in the column
	'generated',          # 'A' = Column is always generated
	                      # 'D' = Column is generated by default
	                      # 'N' = Column is not generated
	'default',            # If generated is 'N', the default value of the
	                      # column (expressed as SQL). Otherwise, the SQL
	                      # expression that generates the column's value (or
	                      # default value). None if the column has no default
	'description',        # Descriptive text
))

Index = namedtuple('Index', SchemaItemId._fields + ObjectAttr._fields + TableRef._fields + TablespaceRef._fields + (
	'last_stats',         # When the index statistics were last updated (datetime)
	'cardinality',        # The approximate number of values in the index
	'size',               # The approximate size in bytes of the index
	'unique',             # True if the index contains only unique values (bool)
))

IndexRef = namedtuple('IndexRef', (
	'index_schema',       # The schema which contains the index
	'index_name',         # The name of the index
))

IndexItemId = namedtuple('IndexItemId', IndexRef._fields + (
	'name',               # The name of the item
))

IndexCol = namedtuple('IndexCol', IndexItemId._fields + (
	'order',              # The ordering of the column in the index:
	                      # 'A' = Ascending
	                      # 'D' = Descending
	                      # 'I' = Include (not an index key)
))

Constraint = namedtuple('Constraint', TableItemId._fields + ObjectAttr._fields)

ConstraintRef = namedtuple('ConstraintRef', (
	'const_schema',       # The schema containing the table that contains the constraint
	'const_table',        # The name of the table that contains the constraint
	'const_name',         # The name of the constraint
))

ConstraintItemId = namedtuple('ConstraintItemId', ConstraintRef._fields + (
	'name',               # The name of the item contained by the constraint
))

UniqueKey = namedtuple('UniqueKey', Constraint._fields + (
	'primary',            # True if the unique key is also a primary key (bool)
))

UniqueKeyCol = namedtuple('UniqueKeyCol', ConstraintItemId._fields)

ForeignKey = namedtuple('ForeignKey', Constraint._fields + ConstraintRef._fields + (
	'delete_rule',        # The action to take on deletion of a parent key:
	                      # 'A' = No action
	                      # 'C' = Cascade
	                      # 'N' = Set NULL
	                      # 'R' = Restrict
	'update_rule',        # The action to take on update of a parent key:
	                      # 'A' = No action
	                      # 'C' = Cascade
	                      # 'N' = Set NULL
	                      # 'R' = Restrict
))

ForeignKeyCol = namedtuple('ForeignKeyCol', ConstraintItemId._fields + (
	'ref_name',           # The name of the column that this column references
	                      # in the referenced key
))

Check = namedtuple('Check', Constraint._fields + (
	'sql',                # The SQL expression that the check enforces
))

CheckCol = namedtuple('CheckCol', ConstraintItemId._fields)

RoutineId = namedtuple('RoutineId', (
	'schema',             # The schema which contains the routine
	'specific',           # The unique name of the routine in the schema
	'name',               # The (potentially overloaded) name of the routine
))

Routine = namedtuple('Routine', RoutineId._fields + ObjectAttr._fields + (
	'deterministic',      # True if the routine is deterministic (bool)
	'ext_action',         # True if the routine has an external action
	                      # (affects things outside the database) (bool)
	'null_call',          # True if the routine is called on NULL input (bool)
	'access',             # 'N' if the routine contains no SQL
	                      # 'C' if the routine contains database independent SQL
	                      # 'R' if the routine contains SQL that reads the db
	                      # 'M' if the routine contains SQL that modifies the db
	'sql',                # The SQL statement that defined the routine
))

RoutineRef = namedtuple('RoutineRef', (
	'routine_schema',     # The schema which contains the routine
	'routine_specific',   # The unique name of the routine in the schema
))

RoutineItemId = namedtuple('RoutineItemId', RoutineRef._fields + (
	'name',               # The name of the item belonging to the routine
))

Function = namedtuple('Function', Routine._fields + (
	'func_type',          # The type of the function:
	                      # 'C' = Column/aggregate function
	                      # 'R' = Row function
	                      # 'T' = Table function
	                      # 'S' = Scalar function
))

Procedure = namedtuple('Procedure', Routine._fields)

RoutineParam = namedtuple('RoutineParam', RoutineItemId._fields + DatatypeRef._fields + (
	'direction',          # 'I' = Input parameter
	                      # 'O' = Output parameter
	                      # 'B' = Input & output parameter
	                      # 'R' = Return value/column
	'description',        # Descriptive text
))

RoutineParamRef = namedtuple('RoutineParamRef', (
	'param_schema',       # The name of the schema containing the routine the parameter belongs to
	'param_specific',     # The unique name of the routine the parameter belongs to
	'param_name',         # The name of the parameter
))

Trigger = namedtuple('Trigger', SchemaItemId._fields + ObjectAttr._fields + RelationRef._fields + (
	'when',               # When the trigger is fired:
	                      # 'A' = After the event
	                      # 'B' = Before the event
	                      # 'I' = Instead of the event
	'event',              # What event causes the trigger to fire:
	                      # 'I' = The trigger fires on INSERT
	                      # 'U' = The trigger fires on UPDATE
	                      # 'D' = The trigger fires on DELETE
	'granularity',        # The granularity of trigger executions:
	                      # 'R' = The trigger fires for each row affected
	                      # 'S' = The trigger fires once per activating statement
	'sql',                # The SQL statement that defined the trigger
))

TriggerRef = namedtuple('TriggerRef', (
	'trig_schema',        # The schema that contains the trigger
	'trig_name',          # The name of the trigger
))

TriggerDep = namedtuple('TriggerDep', TriggerRef._fields + (
	'dep_schema',         # The schema containing the relation that the trigger depends on
	'dep_name',           # The name of the relation that the trigger depends on
))

