# vim: set noet sw=4 ts=4:

from db2makedoc.plugins.html.plain.document import tag

POPUPS = [
	(
		'cardinality.html', 'Cardinality',
		tag.p("""The total number of rows in the table or index as of the last
		time statistics were gathered. The value is n/a if statistics have not
		been gathered.""")
	),
	(
		'colcount.html', '# Columns',
		tag.p(""" The total number of columns in the table, view or index.""")
	),
	(
		'createdby.html', 'Created By',
		tag.p("""The ID of the user that created the object. This user owns the
		object and hence, by default, holds all privileges associated with the
		type of object (typically, the CONTROL privilege). In the case of
		system objects, the creator is either SYSIBM or the user that created
		the database.""")
	),
	(
		'created.html', 'Created',
		tag.p("""The date on which the object was created. Note that this is
		not necessarily the date on which the object was first created. If an
		object is dropped and later re-created, the created date will change to
		reflect the later date.""")
	),
	(
		'deleterule.html', 'Delete Rule',
		[
			tag.p("""Determines the action that is taken when a row is deleted
			from the table referenced by the foreign key, and the row is the
			parent of one or more rows in the foreign key's table. The
			following are the possible values:"""),
			tag.dl(
				tag.dt('Raise Error'),
				tag.dd("""The DELETE statement will fail with an integrity
				violation error"""),
				tag.dt('Cascade'),
				tag.dd("""The DELETE statement will cascade to the foreign
				key's table, deleting any rows which reference the deleted
				row."""),
				tag.dt('Set NULL'),
				tag.dd("""The DELETE statement will succeed, and rows
				referencing the deleted row in the foreign key's table will
				have their key values set to NULL.""")
			)
		]
	),
	(
		'dependenciesrel.html', 'Dependencies',
		tag.p("""The number of relations that this view depends on.
		Specifically, the number of tables, views, etc. that this view
		references in its SQL statement.""")
	),
	(
		'dependentrel.html', 'Dependent Relations',
		tag.p("""The number of relations that depend on this one.
		Specifically, the number of materialized query tables or views that
		reference this relation in their SQL statements, plus the number of
		tables that have a foreign key that references this relation.""")
	),
	(
		'deterministic.html', 'Deterministic',
		tag.p("""If True, the routine is deterministic. That is, given the same
		input values, the routine always produces the same output or performs
		the same action (it has no random aspects).""")
	),
	(
		'externalaction.html', 'External Action',
		tag.p("""If True, the routine has external side effects (indicating
		that the number of invocations of the routine is significant, and hence
		that the optimizer cannot eliminate any otherwise unnecessary routine
		calls).""")
	),
	(
		'functype.html', 'Type',
		tag.p("""Indicates whether the function returns a single scalar value,
		a row (a tuple of values), or a table.""")
	),
	(
		'granularity.html', 'Trigger Granularity',
		[
			tag.p("""Indicates how many times the trigger will fire for a given event.
			Possible values are:"""),
			tag.dl(
				tag.dt('Row'),
				tag.dd("""The trigger will fire once for each row that is
				inserted, updated, or deleted."""),
				tag.dt('Statement'),
				tag.dd("""The trigger will fire once for each statement that
				performs an insertion, update, or deletion. Statement
				granularity triggers access a table of old/new values within
				theie body.""")
			)
		]
	),
	(
		'indexes.html', '# Indexes',
		tag.p("""Indicates the number of indexes which store their physical
		data within the tablespace. Note that a table can store it's row data,
		LOB data and index data in separate tablespaces.""")
	),
	(
		'keycolcount.html', '# Key Columns',
		tag.p("""If the table has a primary key, this indicates the number of
		fields that make up the key. Otherwise, the value is 0. Note that, if
		the value is 0, this does not mean there are no unique keys (or unique
		indexes) defined for the table; only the primary key of a table is
		referred to by this statistic.""")
	),
	(
		'laststats.html', 'Last Statistics',
		tag.p("""The date on which statistics were last gathered for this
		object (with the RUNSTATS command). Most attributes of the object will
		only be valid as of this date. If statistics have never been gathered,
		this will be n/a.""")
	),
	(
		'nullcall.html', 'Call on NULL',
		tag.p("""If True, the routine is called when one or more parameters is
		NULL.  Otherwise, the optimizer assumes that if one or more parameters
		is NULL, the output will be NULL.""")
	),
	(
		'readonly.html', 'Read Only',
		[
			tag.p("""If True, the view is not updateable. If False, the view can be
			updated using the INSERT, UPDATE, and DELETE DML statements as one
			would with an ordinary table. To be updateable, the SQL query that
			defines a view must conform to several rules including:"""),
			tag.ul(
				tag.li('The outermost SELECT does not reference more than one table'),
				tag.li('The outermost SELECT does not include a VALUES clause'),
				tag.li('The outermost SELECT does not include a GROUP BY or HAVING clause'),
				tag.li('The outermost SELECT does not use aggregation functions'),
				tag.li('The outermost SELECT does not use set operators (except UNION ALL'),
				tag.li('The outermost SELECT does not use DISTINCT')
			)
		]
	),
	(
		'size.html', 'Size',
		tag.p("""The approximate size on disk of the database object. Note that
		this is an approximation only as it depends on how up to date the
		statistics for the object are. In some cases, other factors affect the
		accuracy of the size (e.g. partially filled or unused pages). This
		metric is intended to give the user a general idea of the size of the
		object in order to provide a hint as to the amount of I/O that may be
		required when accessing it.""")
	),
	(
		'specificname.html', 'Specific Name',
		[
			tag.p("""The specific name of a routine can be used to identify the
			routine in various statements without resorting to providing the
			parameter prototypes (which can be considerably simpler if the
			routine includes many parameters)."""),
			tag.p("""Note however, that a routine <em>cannot</em> be invoked by
			its specific name.""")
		]
	),
	(
		'sqlaccess.html', 'SQL Access',
		[
			tag.p("""Indicates the level of access the routine has to SQL
			statements. The possible values are:"""),
			tag.dl(
				tag.dt('No SQL'),
				tag.dd("""The routine does not use any SQL statements."""),
				tag.dt('Contains SQL'),
				tag.dd("""The routine uses SQL statements that do not read or
				write (directly or indirectly) any tables within the
				database."""),
				tag.dt('Read-only SQL'),
				tag.dd("""The routine uses SQL statements that read, but do not
				write (directly or indirectly) tables within the database."""),
				tag.dt('Modifies SQL'),
				tag.dd("""The routine can read and write tables within the
				database.""")
			)
		]
	),
	(
		'tables.html', '# Tables',
		tag.p("""Indicates the number of tables which store their physical data
		within the tablespace. Note that a table can store it's row data, LOB
		data and index data in separate tablespaces. Therefore a table may
		count towards the table count of more than one tablespace.""")
	),
	(
		'tbspacetype.html', 'Tablespace Type',
		tag.p("""Indicates the type of the tablespace. As tablespaces are
		concepts that are very specific to a database engine, this is provided
		as free text. Interpret the content in the context of your database
		engine.""")
	),
	(
		'triggerevent.html', 'Trigger Event',
		[
			tag.p("""Indicates what sort of event will fire the trigger.
			Possible values are:"""),
			tag.dl(
				tag.dt('Insert'),
				tag.dd("""The trigger will fire before, after, or instead of an
				INSERT against the target relation."""),
				tag.dt('Update'),
				tag.dd("""The trigger will fire before, after, or instead of an
				UPDATE against the target relation."""),
				tag.dt('Delete'),
				tag.dd("""The trigger will fire before, after, or instead of a
				DELETE against the target relation.""")
			)
		]
	),
	(
		'triggertiming.html', 'Trigger Time',
		[
			tag.p("""Indicates when the trigger fires in relation to the action
			that activates it. Possible values are:"""),
			tag.dl(
				tag.dt('After'),
				tag.dd("""The trigger fires after the action that activates it."""),
				tag.dt('Before'),
				tag.dd("""The trigger fires before the action that activates it."""),
				tag.dt('Instead of'),
				tag.dd("""The action of the trigger replaces the action that
					activated it. INSTEAD OF triggers are typically used to
					make an read-only view definition read-write.""")
			)
		]
	),
	(
		'unique.html', 'Unique',
		tag.p("""If True, the index only permits unique combinations of the
		fields that it contains. Unique indexes can also contain "include"
		fields which are not tracked for uniqueness, but are included in the
		index for performance reasons only.""")
	),
	(
		'updaterule.html', 'Update Rule',
		[
			tag.p("""Determines the action that is taken when a row is updated in the
			table referenced by the foreign key, which changes the values of the
			unique key that the foreign key references, and the row is the parent
			of one or more rows in the foreign key's table. The following are the
			possible values:"""),
			tag.dl(
				tag.dt('Raise Error'),
				tag.dd("""The UPDATE statement will fail with an integrity
				violation error."""),
				tag.dt('Cascade'),
				tag.dd("""The UPDATE statement will cascade to the foreign
				key's table, updating any rows which reference the updated
				row. Note: this action is not currently supported by
				DB2."""),
				tag.dt('Set NULL'),
				tag.dd("""The UPDATE statement will succeed, and rows
				referencing the updated row in the foreign key's table will
				have their key values set to NULL. Note: This action is not
				currently supported by DB2.""")
			)
		]
	),
]
