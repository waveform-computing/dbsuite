# $Header$
# vim: set noet sw=4 ts=4:

W3_POPUPS = [
	('append.html', 'Append', """
		<p>Indicates how new rows are inserted into the table. By default this
		is False, indicating that new rows are inserted into any available
		space within the physical table layout, or appended if no space is
		available. If True, new rows are always appended at the end of the
		table's data.</p>
		"""),
	('assignfunc.html', 'Assign Function', """
		<p>Indicates whether the function is an assignment function for a
		user-defined type.</p>
		"""),
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
	('castfunc.html', 'Cast Function', """
		<p>Indicates whether the function is a CAST function for a user defined
		type.</p>
		"""),
	('checkoption.html', 'Check Option', """
		<p>Specifies whether rows that are inserted into an updateable view
		must conform with the view's definition. Not applicable if the view is
		Read Only.</p>
		<p>If the view is not Read Only, the Check Option may be one of the
		following values:</p>
		<dl>
			<dt>NO CHECK</dt>
			<dd>Indicates that new rows inserted into the view need not conform
			to the view's definition</dd>
			<dt>LOCAL CHECK</dt>
			<dd>Indicates that new rows inserted into the view must conform to
			the view's definition, but not the definition of any views that
			this view depends upon</dd>
			<dt>CASCADED CHECK</dt>
			<dd>Indicates that new rows inserted into the view must conform to
			this view's definition, and the definitions of all views upon which
			this view depends (recursively)</dd>
		</dl>
		"""),
	('clustered.html', 'Clustered', """
		<p>If True, the table is a Multi Dimensional Clustering (MDC) table.
		MDC tables are organized physically by <q>dimensions</q> (sets of
		columns), and indexes are automatically maintained for each defined
		dimension.</p>
		"""),
	('clusterratio.html', 'Cluster Ratio', """
		<p>A measurement of the degree of <q>clustering</q> within the index.
		The closer this value is to 1 the better the performance of the
		index.</p>
		<p>A unique index can also be a <q>clustering</q> index, in which case
		when rows are inserted into its associated table the database will
		attempt to insert them in index order, resulting in a high degree of
		clustering for that index. Unless the table is partitioned only one
		index can be the clustering index for a table.</p>
		"""),
	('colcount.html', '# Columns', """
		<p>The total number of columns in the table, view or index.</p>
		"""),
	('compression.html', 'Compression', """
		<p>False by default. If True, the table uses a compressed row format
		that stores certain datatypes (e.g. VARCHAR, LOBs, etc.) more
		efficiently, especially when a column can contain NULLs. However, the
		compressed row format also uses more space for other datatypes (e.g.
		SMALLINT, INTEGER, REAL, etc.) and tends to cause data fragmentation
		when updating values to/from NULL, zero-length values, or
		system-default values.</p>
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
			<dt>NO ACTION or RESTRICT</dt>
			<dd>The DELETE statement will fail with an integrity violation
			error.</dd>
			<dt>CASCADE</dt>
			<dd>The DELETE statement will cascade to the foreign key's table,
			deleting any rows which reference the deleted row.</dd>
			<dt>SET NULL</dt>
			<dd>The DELETE statement will succeed, and rows referencing the
			deleted row in the foreign key's table will have their key values
			set to NULL.</dd>
		</dl>
		"""),
	('density.html', 'Density', """
		<p>The ratio of <a href="sequentialpages.html">sequential pages</a> to
		the number of pages that the index occupies, expressed as a
		percentage.</p>
		"""),
	('dependenciesrel.html', 'Dependencies', """
		<p>The number of relations that this view depends on. Specifically, the
		number of tables, views, etc. that this view references in its SQL
		statement.</p>
		"""),
	('dependentrel.html', 'Dependent Relations', """
		<p>The number of relations that depend on this one. Specifically, the
		number of materialized query tables or views that reference this
		relation in their SQL statements.</p>
		"""),
	('deterministic.html', 'Deterministic', """
		<p>If True, the routine is deterministic. That is, given the same input
		values, the routine always produces the same output or performs the
		same action (it has no random aspects).</p>
		<p>Not applicable unless the <a href="funcorigin.html">origin</a> is
		user-defined external, or SQL body.</p>
		"""),
	('droprecovery.html', 'Drop Recovery', """
		<p>If True, tables that exist in this tablespace can be recovered after
		being dropped with the RECOVER DROPPED TABLE option of the ROLLFORWARD
		DATABASE command.</p>
		"""),
	('enforced.html', 'Enforced', """
		<p>If True, the constraint is enforced by the database. This is the
		usual state for integrity constraints like foreign keys and checks. If
		False, integrity checking has been disabled for this constraint.</p>
		"""),
	('extentsize.html', 'Extent Size', """
		<p>Indicates the size (in pages) of an <q>extent</q> of the tablespace.
		If the tablespace has multiple containers, a complete extent of pages
		will be written to a container before switching to the next container.
		</p>
		"""),
	('externalaction.html', 'External Action', """
		<p>If True, the routine has external side effects (indicating that the
		number of invocations of the routine is significant, and hence that the
		optimizer cannot eliminate any otherwise unnecessary routine
		calls).</p>
		<p>Not applicable unless the <a href="funcorigin.html">origin</a> is
		user-defined external, or SQL body.</p>
		"""),
	('fenced.html', 'Fenced', """
		<p>If True, the routine is <q>fenced</q> which means that it is run in
		a separate process, under a separate user to ensure that any bugs,
		malfunctions or security holes in the routine's implementation are
		considerably less likely to affect the database server. However,
		because of the inter-process communication necessary with fenced
		routines they tend to run slower than unfenced routines.</p>
		"""),
	('funclanguage.html', 'Language', """
		<p>Indicates the language in which the routine is implemented.  The
		possible values are:</p>
		<ul>
			<li>C</li>
			<li>COBOL</li>
			<li>JAVA</li>
			<li>OLE</li>
			<li>OLEDB</li>
			<li>SQL</li>
		</ul>
		<p>If the routine <a href="funcorigin.html">origin</a> is SQL-bodied,
		the language is always SQL. Otherwise, this value is only applicable if
		the routine origin is user-defined external.</p>
		"""),
	('funcorigin.html', 'Origin', """
		<p>Indicates the origin of the function's implementation.  The possible
		values are:</p>
		<ul>
			<li>Built-in</li>
			<li>User-defined external</li>
			<li>User-defined source</li>
			<li>Template</li>
			<li>SQL body</li>
			<li>System generated</li>
			<li>System generated transform</li>
		</ul>
		"""),
	('functype.html', 'Type', """
		<p>Indicates whether the function returns a single scalar value, a row
		(a tuple of values), or a table.</p>
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
	('leafpages.html', 'Leaf Pages', """
		<p>The number of physical pages containing leaf nodes of the index.</p>
		"""),
	('levels.html', 'Levels', """
		<p>The number of levels within the index.</p>
		"""),
	('locksize.html', 'Lock Size', """
		<p>Indicates the preferred lock granularity for the table when accessed
		by DML statements. Possible values are <q>ROW</q> (the default,
		indicating that individual row locks are preferred) and <q>TABLE</q>
		(indicating that the database prefers to lock the entire table during
		updates).</p>
		"""),
	('managedby.html', 'Tablespace Managed By', """
		<p>Indicates whether the storage of the tablespace is managed by the
		database or by the filesystem. Can be one of the following values:</p>
		<dl>
			<dt>SYSTEM</dt>
			<dd>Indicates an SMS tablespace. SMS tablespaces cannot be size
			limited and effectively shrink &amp; grow with their content (an
			SMS tablespace is implemented as an ordinary filesystem directory
			containing several files per table / index).</dd>
			<dt>DATABASE</dt>
			<dd>Indicates a DMS tablespace. DMS tablespaces can be size limited
			in various ways (auto-resize, maximum-size, etc.) and depending on
			various options may automatically grow to accomodate their
			contents, or not (a DMS tablespace is implemented as a large file
			or partition on the disk opaque to the operating system). DMS
			tablespaces generally give superior performance.</dd>
		</dl>
		"""),
	('nullcall.html', 'Call on NULL', """
		<p>If True, the routine is called when one or more parameters is NULL.
		Otherwise, the optimizer assumes that if one or more parameters is
		NULL, the output will be NULL.</p>
		<p>Not applicable unless the <a href="funcorigin.html">origin</a> is
		user-defined external, or SQL body.</p>
		"""),
	('pagesize.html', 'Page Size', """
		<p>Indicates the size (in bytes) of a page in the tablespace. The
		default page size is 4096 bytes, unless a different value was specified
		in the CREATE DATABASE statement that created the database.</p>
		<p>Possible page sizes are 4096 (4K), 8192 (8K), 16384 (16K), and 32768
		(32K).  A page size of 4096 limits the number of columns that can be
		present in a table to 500 (otherwise, a table may have up to 1012
		columns).</p>
		<p>A row cannot span more than one page, hence each page holds a whole
		number of rows. Moreover, a page cannot store more than 255 rows. These
		two factors can mean that for tables with a small number of small
		fields, significant portions of each page may be wasted if the table is
		stored in a tablespace with a large page size.</p>
		"""),
	('parallelcall.html', 'Parallel', """
		<p>If True, the function can be run simultaneously (in parallel) in
		multiple processes. Otherwise, each function call must be serialized
		(typically leading to much slower performance under load).</p>
		<p>Not applicable unless the <a href="funcorigin.html">origin</a> is
		user-defined external.</p>
		"""),
	('prefetchsize.html', 'Prefetch Size', """
		<p>Indicates the number of pages of the tablespace that are read when a
		prefetch operation is performed (when the optimizer determines that to
		do so would be more efficient). If this value is -1, the prefetch size
		is determined automatically.</p>
		"""),
	('queryoptimize.html', 'Query Optimization', """
		<p>Indicates whether or not query optimization is enabled for the
		constraint or relation. If True, the database optimizer will endeavour
		to use knowledge of the constraint or relation to improve the
		performance of queries. This is the usual state for constraints and
		certain types of relation.</p>
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
	('reversescans.html', 'Reverse Scans', """
		<p>If True, the index can be scanned by the database either forwards or
		backwards. Typically, this means that the index can be used to optimize
		a wider variety of queries (for example such an index could be used to
		optimize both MIN() and MAX() aggregate functions instead of just one
		of them depending on the sorting direction of fields within the
		index).</p>
		<p>Reverse scan capable indexes typically take more storage than normal
		indexes, and may take slightly longer to update but the difference is
		usually minimal.</p>
		"""),
	('rowpages.html', 'Row Pages', """
		<p>The total number of tablespace pages on which the rows of the table
		exist. If statistics have not been gathered, the value is n/a.</p>
		"""),
	('sequentialpages.html', 'Sequential Pages', """
		<p>The number of leaf pages located on disk in the key order of the
		index with little or no gap between them. This is a measurement of the
		performance of the index. The <a href="density.html">density</a> value
		puts this value in the context of the size of the index.</p>
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
			<dt>NO SQL</dt>
			<dd>The routine does not use any SQL statements.</dd>
			<dt>CONTAINS SQL</dt>
			<dd>The routine uses SQL statements that do not read or write
			(directly or indirectly) any tables within the database.</dd>
			<dt>READS SQL</dt>
			<dd>The routine uses SQL statements that read, but do not write
			(directly or indirectly) tables within the database.</dd>
			<dt>MODIFIES SQL</dt>
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
		<p>Indicates the type of data that the tablespace stores. Can be one of
		the following values:</p>
		<dl>
			<dt>ANY</dt>
			<dd>The tablespace is a regular tablespace capable of storing any
			kind of <em>permanent</em> data.</dd>
			<dt>LONG/INDEX</dt>
			<dd>The tablespace is dedicated to storing LOB or index data.</dd>
			<dt>SYSTEM TEMPORARY</dt>
			<dd>The tablespace is dedicated to storing system temporary tables
			only.</dd>
			<dt>USER TEMPORARY</dt>
			<dd>The tablespace is dedicated to storing user temporary tables
			only.</dd>
		</dl>
		"""),
	('threadsafe.html', 'Thread Safe', """
		<p>If True, the routine can be run simultaneously (in parallel) in
		multiple threads. Otherwise, each routine call must be serialized
		within a given process.</p>
		<p>Not applicable unless the <a href="funcorigin.html">origin</a> is
		user-defined external.</p>
		"""),
	('totalpages.html', 'Total Pages', """
		<p>The total number of tablespace pages which the table occupies. If
		statistics have not been gathered, the value is n/a.</p>
		"""),
	('triggerevent.html', 'Trigger Event', """
		<p>Indicates what sort of event will fire the trigger. Possible values
		are:</p>
		<dl>
			<dt>INSERT</dt>
			<dd>The trigger will fire before, after, or instead of an INSERT
			against the target relation.</dd>
			<dt>UPDATE</dt>
			<dd>The trigger will fire before, after, or instead of an UPDATE
			against the target relation.</dd>
			<dt>DELETE</dt>
			<dd>The trigger will fire before, after, or instead of a DELETE
			against the target relation.</dd>
		</dl>
		"""),
	('triggertiming.html', 'Trigger Time', """
		<p>Indicates when the trigger fires in relation to the action that
		activates it. Possible values are:</p>
		<dl>
			<dt>AFTER</dt>
			<dd>The trigger fires after the action that activates it.</dd>
			<dt>BEFORE</dt>
			<dd>The trigger fires before the action that activates it.</dd>
			<dt>INSTEAD OF</dt>
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
			<dt>NO ACTION or RESTRICT</dt>
			<dd>The DELETE statement will fail with an integrity violation
			error.</dd>
			<dt>CASCADE</dt>
			<dd>The DELETE statement will cascade to the foreign key's table,
			deleting any rows which reference the deleted row. Note: this
			action is not currently supported by DB2.</dd>
			<dt>SET NULL</dt>
			<dd>The DELETE statement will succeed, and rows referencing the
			deleted row in the foreign key's table will have their key values
			set to NULL. Note: This action is not currently supported by
			DB2.</dd>
		</dl>
		"""),
	('valid.html', 'Valid', """
		<p><strong>Views</strong></p>
		<p>If True, the view is accessible by users with the necessary
		authorization. If False, the view is currently marked inaccessible
		(usually because a table or view that this view references has been
		altered), and needs to be dropped and recreated before users can access
		it.</p>
		<p><strong>Triggers</strong></p>
		<p>If True, the trigger is active and will fire when the associated
		event occurs. If False, the trigger is currently inactive (usually
		because a table, view or routine this trigger relies upon has been
		dropped), and needs to be dropped and recreated to reactivate it.</p>
		"""),
	('volatile.html', 'Volatile', """
		<p>If True, the table's cardinality (the number of rows in the table)
		is liable to change considerably over time.</p>
		"""),
]

