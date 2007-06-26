# $Header$
# vim: set noet sw=4 ts=4:

W3_POPUPS = [
	('cardinality.html', 'Cardinality', """
		<p><strong>Tables and Indexes:</strong></p>
		<p>The total number of rows in the table or index as of the last time
		statistics were gathered. The value is n/a if statistics have not been
		gathered.</p>
		<p><strong>Indexes only:</strong></p>
		<p>Additionally lists the cardinalities of up to four partial keys
		depending on the number of fields indexed. For example, if the index is
		defined on three columns, this field will additionally list the
		cardinalities of the first column indexed, the cardinality of the
		combination of the first and second columns indexed, and the
		cardinality of the combination of the first, second, and third columns
		indexed.</p>
		"""),
	('colcount.html', '# Columns', """
		<p>The total number of columns in the table, view or index.</p>
		"""),
	('createdby.html', 'Created By', """
		<p>The ID of the user that created the object. This user <q>owns</q>
		the object and hence, by default, holds all privileges associated with
		the type of object (typically, the CONTROL privilege). In the case of
		system objects, the creator is either SYSIBM or the user that created
		the database.</p>
		"""),
	('created.html', 'Created', """
		<p>The date on which the object was created. Note that this is not
		necessarily the date on which the object was <em>first</em> created. If
		an object is dropped and later re-created, the created date will change
		to reflect the later date.</p>
		"""),
	('deleterule.html', 'Delete Rule', """
		<p>Determines the action that is taken when a row is deleted from the
		table referenced by the foreign key, and the row is the parent of one
		or more rows in the foreign key's table. The following are the possible
		values:</p>
		<dl>
			<dt>Raise Error</dt>
			<dd>The DELETE statement will fail with an integrity violation
			error.</dd>
			<dt>Cascade</dt>
			<dd>The DELETE statement will cascade to the foreign key's table,
			deleting any rows which reference the deleted row.</dd>
			<dt>Set NULL</dt>
			<dd>The DELETE statement will succeed, and rows referencing the
			deleted row in the foreign key's table will have their key values
			set to NULL.</dd>
		</dl>
		"""),
	('dependenciesrel.html', 'Dependencies', """
		<p>The number of relations that this view depends on. Specifically, the
		number of tables, views, etc. that this view references in its SQL
		statement.</p>
		"""),
	('dependentrel.html', 'Dependent Relations', """
		<p>The number of relations that depend on this one. Specifically, the
		number of materialized query tables or views that reference this
		relation in their SQL statements, plus the number of tables that have
		a foreign key that references this relation.</p>
		"""),
	('deterministic.html', 'Deterministic', """
		<p>If True, the routine is deterministic. That is, given the same input
		values, the routine always produces the same output or performs the
		same action (it has no random aspects).</p>
		<p>Not applicable unless the <a href="funcorigin.html">origin</a> is
		user-defined external, or SQL body.</p>
		"""),
	('externalaction.html', 'External Action', """
		<p>If True, the routine has external side effects (indicating that the
		number of invocations of the routine is significant, and hence that the
		optimizer cannot eliminate any otherwise unnecessary routine
		calls).</p>
		<p>Not applicable unless the <a href="funcorigin.html">origin</a> is
		user-defined external, or SQL body.</p>
		"""),
	('functype.html', 'Type', """
		<p>Indicates whether the function returns a single scalar value, a row
		(a tuple of values), or a table.</p>
		"""),
	('granularity.html', 'Trigger Granularity', """
		<p>Indicates how many times the trigger will fire for a given event.
		Possible values are:</p>
		<dl>
			<dt>Row</dt>
			<dd>The trigger will fire once for each row that is inserted,
			updated, or deleted.</dd>
			<dt>Statement</dt>
			<dd>The trigger will fire once for each statement that performs
			an insertion, update, or deletion. Statement granularity triggers
			access a <em>table</em> of old/new values within theie body.</dd>
		</dl>
		"""),
	('indexes.html', '# Indexes', """
		<p>Indicates the number of indexes which store their physical data
		within the tablespace. Note that a table can store it's row data, LOB
		data and index data in separate tablespaces.</p>
		"""),
	('keycolcount.html', '# Key Columns', """
		<p>If the table has a primary key, this indicates the number of fields
		that make up the key. Otherwise, the value is 0. Note that, if the
		value is 0, this does not mean there are no unique keys (or unique
		indexes) defined for the table; only the <em>primary</em> key of a
		table is referred to by this statistics.</p>
		"""),
	('laststats.html', 'Last Statistics', """
		<p>The date on which statistics were last gathered for this object
		(with the RUNSTATS command). Most attributes of the object will only be
		valid as of this date. If statistics have never been gathered, this
		will be n/a.</p>
		"""),
	('nullcall.html', 'Call on NULL', """
		<p>If True, the routine is called when one or more parameters is NULL.
		Otherwise, the optimizer assumes that if one or more parameters is
		NULL, the output will be NULL.</p>
		<p>Not applicable unless the <a href="funcorigin.html">origin</a> is
		user-defined external, or SQL body.</p>
		"""),
	('readonly.html', 'Read Only', """
		<p>If True, the view is not updateable. If False, the view can be
		updated using the INSERT, UPDATE, and DELETE DML statements as one
		would with an ordinary table. To be updateable, the SQL query that
		defines a view must conform to several rules including:</p>
		<ul>
			<li>The outermost SELECT does not reference more than one table</li>
			<li>The outermost SELECT does not include a VALUES clause</li>
			<li>The outermost SELECT does not include a GROUP BY or HAVING clause</li>
			<li>The outermost SELECT does not use aggregation functions</li>
			<li>The outermost SELECT does not use set operators (except UNION ALL)</li>
			<li>The outermost SELECT does not use DISTINCT</li>
		</ul>
		"""),
	('size.html', 'Size', """
		<p>The approximate size on disk of the database object. Note that this
		is an approximation only as it depends on how up to date the statistics
		for the object are. In some cases, other factors affect the accuracy
		of the size (e.g. partially filled or unused pages). This metric is
		intended to give the user a general idea of the size of the object in
		order to provide a hint as to the amount of I/O that may be required
		when accessing it.</p>
		"""),
	('specificname.html', 'Specific Name', """
		<p>The specific name of a routine can be used to identify the routine
		in various statements without resorting to providing the parameter
		prototypes (which can be considerably simpler if the routine includes
		many parameters).</p>
		<p>Note however, that a routine <em>cannot</em> be invoked by its
		specific name.</p>
		"""),
	('sqlaccess.html', 'SQL Access', """
		<p>Indicates the level of access the routine has to SQL statements. The
		possible values are:</p>
		<dl>
			<dt>No SQL</dt>
			<dd>The routine does not use any SQL statements.</dd>
			<dt>Contains SQL</dt>
			<dd>The routine uses SQL statements that do not read or write
			(directly or indirectly) any tables within the database.</dd>
			<dt>Read-only SQL</dt>
			<dd>The routine uses SQL statements that read, but do not write
			(directly or indirectly) tables within the database.</dd>
			<dt>Modifies SQL</dt>
			<dd>The routine can read and write tables within the database.</dd>
		</dl>
		"""),
	('tables.html', '# Tables', """
		<p>Indicates the number of tables which store their physical data
		within the tablespace. Note that a table can store it's row data, LOB
		data and index data in separate tablespaces. Therefore a table may
		count towards the table count of more than one tablespace.</p>
		"""),
	('tbspacetype.html', 'Tablespace Type', """
		<p>Indicates the type of the tablespace. As tablespaces are concepts
		that are very specific to a database engine, this is provided as free
		text. Interpret the content in the context of your database engine.</p>
		"""),
	('triggerevent.html', 'Trigger Event', """
		<p>Indicates what sort of event will fire the trigger. Possible values
		are:</p>
		<dl>
			<dt>Insert</dt>
			<dd>The trigger will fire before, after, or instead of an INSERT
			against the target relation.</dd>
			<dt>Update</dt>
			<dd>The trigger will fire before, after, or instead of an UPDATE
			against the target relation.</dd>
			<dt>Delete</dt>
			<dd>The trigger will fire before, after, or instead of a DELETE
			against the target relation.</dd>
		</dl>
		"""),
	('triggertiming.html', 'Trigger Time', """
		<p>Indicates when the trigger fires in relation to the action that
		activates it. Possible values are:</p>
		<dl>
			<dt>After</dt>
			<dd>The trigger fires after the action that activates it.</dd>
			<dt>Before</dt>
			<dd>The trigger fires before the action that activates it.</dd>
			<dt>Instead of</dt>
			<dd>The action of the trigger replaces the action that activated
			it. INSTEAD OF triggers are typically used to make an read-only
			view definition read-write.</dd>
		</dl>
		"""),
	('unique.html', 'Unique', """
		<p>If True, the index only permits unique combinations of the fields
		that it contains. Unique indexes can also contain <q>include</q> fields
		which are not tracked for uniqueness, but are included in the index for
		performance reasons only.</p>
		"""),
	('updaterule.html', 'Update Rule', """
		<p>Determines the action that is taken when a row is updated in the
		table referenced by the foreign key, which changes the values of the
		unique key that the foreign key references, and the row is the parent
		of one or more rows in the foreign key's table. The following are the
		possible values:</p>
		<dl>
			<dt>Raise Error</dt>
			<dd>The UPDATE statement will fail with an integrity violation
			error.</dd>
			<dt>Cascade</dt>
			<dd>The UPDATE statement will cascade to the foreign key's table,
			updating any rows which reference the updated row. Note: this
			action is not currently supported by DB2.</dd>
			<dt>Set NULL</dt>
			<dd>The UPDATE statement will succeed, and rows referencing the
			updated row in the foreign key's table will have their key values
			set to NULL. Note: This action is not currently supported by
			DB2.</dd>
		</dl>
		"""),
]

