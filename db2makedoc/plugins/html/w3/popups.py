# vim: set noet sw=4 ts=4:

from db2makedoc.plugins.html.w3.document import tag

POPUPS = [
	(
		'cardinality.html', 'Cardinality',
		tag.p("""The total number of rows in the table or index as of the last
		time statistics were gathered. The value is """, tag.q('n/a'), """ if
		statistics have not been gathered.""")
	),
	(
		'colcount.html', '# Columns',
		tag.p("""The total number of columns in the table, view or index.""")
	),
	(
		'createdby.html', 'Created By',
		tag.p("""The ID of the user that created the object. This user """,
		tag.q('owns'), """ the object and hence, by default, holds all
		privileges associated with the type of object (typically, the """,
		tag.code('CONTROL'), """ privilege). In the case of system objects, the
		creator is either SYSIBM or the user that created the database.""")
	),
	(
		'created.html', 'Created',
		tag.p("""The date on which the object was created. Note that this is
		not necessarily the date on which the object was """, tag.em('first'),
		""" created. If an object is dropped and later re-created, the created
		date will change to reflect the later date.""")
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
				tag.dd('The ', tag.code('DELETE'), """ statement will fail with
				an integrity violation error"""),
				tag.dt('Cascade'),
				tag.dd('The ', tag.code('DELETE'), """ statement will cascade
				to the foreign key\'s table, deleting any rows which reference
				the deleted row."""),
				tag.dt('Set NULL'),
				tag.dd('The ', tag.code('DELETE'), """ statement will succeed,
				and rows referencing the deleted row in the foreign key\'s
				table will have their key values set to """, tag.code('NULL'),
				'.')
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
		reference this relation in their SQL statements, plus (for tables) the
		number of tables that have a foreign key that references this
		table.""")
	),
	(
		'deterministic.html', 'Deterministic',
		tag.p("""Indicates whether the routine is deterministic. If a routine
		is deterministic, given the same input values, the routine always
		produces the same output or performs the same action (it has no random
		aspects). The results of deterministic routines can be cached and
		re-used by the database engine.""")
	),
	(
		'externalaction.html', 'External Action',
		tag.p("""Indicates whether the routine has external side effects. If a
		routine has external actions then the number of invocations of the
		routine is significant, and hence that the optimizer cannot eliminate
		any otherwise unnecessary calls.""")
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
				granularity triggers access a """, tag.em('table'), """ of
				old/new values within theie body.""")
			)
		]
	),
	(
		'indexes.html', '# Indexes',
		tag.p("""Indicates the number of indexes which store their physical
		data within the tablespace. Note that a table can store its row data,
		LOB data and index data in separate tablespaces.""")
	),
	(
		'keycolcount.html', '# Key Columns',
		tag.p("""If the table has a primary key, this indicates the number of
		fields that make up the key. Otherwise, the value is 0. Note that, if
		the value is 0, this does not mean there are no """, tag.em('unique'),
		""" keys (or unique indexes) defined for the table; only the """,
		tag.em('primary'), """ key of a table is referred to by this
		statistic.""")
	),
	(
		'laststats.html', 'Last Statistics',
		tag.p("""The date on which statistics were last gathered for this
		object (with the """, tag.code('RUNSTATS'), """ command). Most
		attributes of the object will only be valid as of this date. If
		statistics have never been gathered, this will be """, tag.q('n/a'),
		'.')
	),
	(
		'nullcall.html', 'Call on NULL',
		tag.p("""Indicates if the routine is called when one or more parameters
		is """, tag.code('NULL'), """. If not, the optimizer can assume that if
		one or more parameters is """, tag.code('NULL'), """, the output will
		be too and hence a call to the routine can be avoided.""")
	),
	(
		'readonly.html', 'Read Only',
		[
			tag.p("""Indicates if the view is updateable. Read-only views will
			only accept """, tag.code('SELECT'), """ statements, whereas
			updateable views can be the target of """, tag.code('INSERT'), ', ',
			tag.code('UPDATE'), ', and ', tag.code('DELETE'), """ statements
			just like an ordinary table.  To be updateable, the query that
			defines a view must conform to several rules including:"""),
			tag.ul(
				tag.li('The outermost ', tag.code('SELECT'), ' does not reference more than one table'),
				tag.li('The outermost ', tag.code('SELECT'), ' does not include a ', tag.code('VALUES'), ' clause'),
				tag.li('The outermost ', tag.code('SELECT'), ' does not include a ', tag.code('GROUP BY'), ' or ', tag.code('HAVING'), ' clause'),
				tag.li('The outermost ', tag.code('SELECT'), ' does not use aggregation functions'),
				tag.li('The outermost ', tag.code('SELECT'), ' does not use set operators (except ', tag.code('UNION ALL'), ')'),
				tag.li('The outermost ', tag.code('SELECT'), ' does not use ', tag.code('DISTINCT'))
			)
		]
	),
	(
		'search.html', 'Search Queries',
		[
			tag.p("""The local search engine accepts the following operators in queries:"""),
			tag.dl(
				tag.dt('AND'),
				tag.dd(tag.code(tag.em('expression'), ' AND ', tag.em('expression')),
					""" matches documents which contain both expressions."""),
				tag.dt('OR'),
				tag.dd(tag.code(tag.em('expression'), ' OR ', tag.em('expression')),
					""" matches documents which contain either expression."""),
				tag.dt('NOT'),
				tag.dd(tag.code(tag.em('expression'), ' NOT ', tag.em('expression')),
					""" matches documents which contain the first expression,
					but not the second. This can also be written """,
					tag.code(tag.em('expression'), """ AND NOT """, tag.em('expression')), '.'),
				tag.dt('XOR'),
				tag.dd(tag.code(tag.em('expression'), ' XOR ', tag.em('expression')),
					""" matches documents which contain the first expression,
					or the second, but not both (this is probably a bit esoteric)."""),
				tag.dt('(expression)'),
				tag.dd("""You can control the precedence of the boolean operators using parentheses. In the query """,
					tag.code("""one OR two AND three"""), """ the AND takes precedence, so this is the same as """,
					tag.code("""one OR (two AND three)"""), """. You can override the precedence using """,
					tag.code("""(one OR two) AND three"""), '.'),
				tag.dt('+ and -'),
				tag.dd("""A group of terms with some marked with + and - will
					match documents containing all of the + terms, but none of
					the - terms. Terms not marked with + or - contribute
					towards the document rankings. You can also use + and - on
					phrases and on bracketed expressions."""),
				tag.dt('Capitalized Words'),
				tag.dd("""Lower-case search terms are "stemmed" when searching,
					e.g. """, tag.code('country'), """ will match the words
					"country" and "countries". Capitalized words like """,
					tag.code('Country'), """ will not be stemmed and result in
					considerably fewer matches."""),
				tag.dt('"Phrase Searches"'),
				tag.dd("""A phrase surrounded with double quotes ("") matches
					documents containing that exact phrase. Hyphenated words
					are also treated as phrases.""")
			),
			tag.p('Below are presented some variations on a search for "syscat" and "tables":'),
			tag.ul(
				tag.li(tag.code('syscat'), """ will find documents containing
					the word "syscat"."""),
				tag.li(tag.code('syscat tables'), """ will find documents
					containing either "syscat" or "tables". Documents
					containing both will be ranked higher."""),
				tag.li(tag.code('syscat OR tables'), """ will also find
					documents containing either "syscat" or "tables"."""),
				tag.li(tag.code('syscat AND tables'), """ will find documents
					containing both "syscat" and "tables"."""),
				tag.li(tag.code('+syscat +tables'), """ will also find
					documents containing both "syscat" and "tables"."""),
				tag.li(tag.code('+syscat tables'), """ will find documents
					containing "syscat". Documents which also contain "tables"
					will be ranked higher."""),
				tag.li(tag.code('+syscat -tables'), """ will find documents
					containing "syscat", but not "tables"."""),
				tag.li(tag.code('syscat AND NOT tables'), """ will also find
					documents containing "syscat", but not "tables"."""),
				tag.li(tag.code('"syscat.tables"'), """ will search for
					documents containing the exact phrase "syscat.tables".""")
			),
			tag.p("""Note that in the examples above, the word "tables" will be
				stemmed and will therefore match both "table" and "tables".
				If capitalized, it would match only the word "tables"."""),
			tag.p("""Checking the """, tag.strong('Search within results'), """
				box will implicitly AND your new query with your existing
				query."""),
			tag.p("""For example, if you perform a search for "syscat", then on
				the results page checked """, tag.strong('Search within results'),
				""" and entered "tables" in the search box, submitting the form
				would result in the search """, tag.code('syscat AND tables'), '.'),
			tag.p("""You can refine your search in this way as many times as
				you like (although eventually you are likely to reduce the result
				set to 0 items).""")
		]
	),
	(
		'size.html', 'Size',
		tag.p('The ', tag.em('approximate'), """ size on disk of the database
		object. Note that this is an approximation only as it depends on how up
		to date the statistics for the object are. In some cases, other factors
		affect the accuracy of the size (e.g. partially filled or unused
		pages). This metric is intended to give the user a general idea of the
		size of the object in order to provide a hint as to the amount of I/O
		that may be required when accessing it.""")
	),
	(
		'specificname.html', 'Specific Name',
		[
			tag.p("""The specific name of a routine can be used to identify the
			routine in various statements without resorting to providing the
			parameter prototypes (which can be considerably simpler if the
			routine includes many parameters)."""),
			tag.p("""Note however, that a routine """, tag.em('cannot'), """ be
			invoked by its specific name.""")
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
				tag.dd('The trigger will fire before, after, or instead of an ', tag.code('INSERT'), ' against the target relation.'),
				tag.dt('Update'),
				tag.dd('The trigger will fire before, after, or instead of an ', tag.code('UPDATE'), ' against the target relation.'),
				tag.dt('Delete'),
				tag.dd('The trigger will fire before, after, or instead of a ', tag.code('DELETE'), ' against the target relation.')
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
				tag.dd('The trigger fires after the action that activates it.'),
				tag.dt('Before'),
				tag.dd('The trigger fires before the action that activates it.'),
				tag.dt('Instead of'),
				tag.dd("""The action of the trigger replaces the action that
					activated it. """, tag.code('INSTEAD OF'), """ triggers are
					typically used to make an read-only view definition
					read-write.""")
			)
		]
	),
	(
		'unique.html', 'Unique',
		tag.p("""Indicates if the index only permits unique combinations of the
		fields that it contains. Unique indexes can also contain """,
		tag.q('include'), """ fields which are not tracked for uniqueness, but
		are included in the index for performance reasons only.""")
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
				tag.dd('The ', tag.code('UPDATE'), """ statement will fail with
				an integrity violation error."""),
				tag.dt('Cascade'),
				tag.dd('The ', tag.code('UPDATE'), """ statement will cascade
				to the foreign key's table, updating any rows which reference
				the updated row. """, tag.strong('Note:'), """ this action is
				not currently supported by DB2."""),
				tag.dt('Set NULL'),
				tag.dd('The ', tag.code('UPDATE'), """ statement will succeed,
				and rows referencing the updated row in the foreign key's table
				will have their key values set to NULL. """,
				tag.strong('Note:'), """ This action is not currently supported
				by DB2.""")
			)
		]
	),
]
