-- $Header$
-- vim: set noet sw=4 ts=4:

-------------------------------------------------------------------------------
-- Documentation for system objects in IBM DB2 UDB for Linux/UNIX/Windows
--
-- OVERVIEW
-- ========
-- This script creates comments for most system objects in a DB2 database.
-- Specifically, all objects in the SYSCAT and SYSSTAT schemas are covered,
-- including deprecated views.
--
-- Unforunately, SYSFUN routines cannot have comments (due to some bizarre
-- limitation in DB2), and routines SYSIBM don't even exist in the system
-- catalog tables, so they can't be commented on either. Furthermore, routine
-- parameters can't be commented on.
--
-- Finally, most objects in the SYSIBM schema aren't commented upon as IBM
-- doesn't provide documentation for these objects (the SYSCAT and SYSSTAT
-- comments are copied almost verbatim from the DB2 Info Center).
--
-- INSTALLATION
-- ============
-- 1. Connect to the target database
-- 2. Execute this file, using semi-colon (;) as the statement terminator
-------------------------------------------------------------------------------

--	MAXCOMMENTLEN       IS '         1         2         3         4         5         6         7         8         9        10        11        12        13        14        15        16        17        18        19        20        21        22        23        24        25    ',
--	MAXCOMMENTLEN       IS '12345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234',

-------------------------------------------------------------------------------
-- Comments for deprecated views which can be removed as they are removed from
-- the DB2 implementation
-------------------------------------------------------------------------------
COMMENT ON TABLE SYSCAT.FUNCDEP IS 'DEPRECATED: Use the @SYSCAT.ROUTINEDEP view instead';
COMMENT ON TABLE SYSCAT.FUNCPARMS IS 'DEPRECATED: Use the @SYSCAT.ROUTINEPARMS view instead';
COMMENT ON TABLE SYSCAT.PROCPARMS IS 'DEPRECATED: Use the @SYSCAT.ROUTINEPARMS view instead';
COMMENT ON TABLE SYSCAT.FUNCTIONS IS 'DEPRECATED: Use the @SYSCAT.ROUTINES view instead';
COMMENT ON TABLE SYSCAT.PROCEDURES IS 'DEPRECATED: Use the @SYSCAT.ROUTINES view instead';

-------------------------------------------------------------------------------
-- Comments for tables/views in the SYSIBM schema
-------------------------------------------------------------------------------
COMMENT ON SCHEMA SYSIBM IS 'Contains the "base" system catalog tables and views. Use the views in the @SYSCAT schema in preference to these.';

COMMENT ON TABLE SYSIBM.SYSDUMMY1 IS 'Contains one row. This view is available for applications that require compatibility with DB2 Universal Database for z/OS and OS/390.';
COMMENT ON SYSIBM.SYSDUMMY1 (
	IBMREQD             IS 'Y'
);

-------------------------------------------------------------------------------
-- Comments for tables/views in the SYSCAT schema
-------------------------------------------------------------------------------
COMMENT ON SCHEMA SYSCAT IS 'Contains user-friendly views on the base system catalog tables in the @SYSIBM schema. Use these views in preference to those in the @SYSIBM schema.';

COMMENT ON TABLE SYSCAT.ATTRIBUTES IS 'Contains one row for each attribute (including inherited attributes where applicable) that is defined for a user-defined structured data type.';
COMMENT ON SYSCAT.ATTRIBUTES (
	TYPESCHEMA          IS 'Qualified name of the structured data type that includes the attribute.',
	TYPENAME            IS 'Qualified name of the structured data type that includes the attribute.',
	ATTR_NAME           IS 'Attribute name.',
	ATTR_TYPESCHEMA     IS 'Qualified name of the type of the attribute.',
	ATTR_TYPENAME       IS 'Qualified name of the type of the attribute.',
	TARGET_TYPESCHEMA   IS 'Qualified name of the target type, if the type of the attribute is REFERENCE. NULL value if the type of the attribute is not REFERENCE.',
	TARGET_TYPENAME     IS 'Qualified name of the target type, if the type of the attribute is REFERENCE. NULL value if the type of the attribute is not REFERENCE.',
	SOURCE_TYPESCHEMA   IS 'Qualified name of the data type in the data type hierarchy where the attribute was introduced. For non-inherited attributes, these columns are the same as TYPESCHEMA and TYPENAME.',
	SOURCE_TYPENAME     IS 'Qualified name of the data type in the data type hierarchy where the attribute was introduced. For non-inherited attributes, these columns are the same as TYPESCHEMA and TYPENAME.',
	ORDINAL             IS 'Position of the attribute in the definition of the structured data type, starting with zero.',
	LENGTH              IS 'Maximum length of data; 0 for distinct types. The LENGTH column indicates precision for DECIMAL fields.',
	SCALE               IS 'Scale for DECIMAL fields; 0 if not DECIMAL.',
	CODEPAGE            IS 'Code page of the attribute. For character-string attributes not defined with FOR BIT DATA, the value is the database code page. For graphic-string attributes, the value is the DBCS code page implied by the database code page. Otherwise, 0.',
	LOGGED              IS 'Applies only to attributes whose type is LOB or distinct based on LOB; otherwise blank. (Y/N)',
	COMPACT             IS 'Applies only to attributes whose type is LOB or distinct based on LOB; otherwise blank). (Y/N)',
	DL_FEATURES         IS 'Applies to DATALINK type attributes only. Blank for REFERENCE type attributes; otherwise NULL. Encodes various DATALINK features such as linktype, control mode, recovery, and unlink properties.'
);

COMMENT ON TABLE SYSCAT.BUFFERPOOLDBPARTITIONS IS 'Contains a row for each database partition in the buffer pool for which the size of the buffer pool on the database partition is different from the default size in @SYSCAT.BUFFERPOOLS column NPAGES.';
COMMENT ON SYSCAT.BUFFERPOOLDBPARTITIONS (
	BUFFERPOOLID        IS 'Internal buffer pool identifier',
	DBPARTITIONNUM      IS 'Database partition number',
	NPAGES              IS 'Number of pages in this buffer pool on this database partition'
);

COMMENT ON TABLE SYSCAT.BUFFERPOOLS IS 'Contains a row for every buffer pool in every database partition group.';
COMMENT ON SYSCAT.BUFFERPOOLS (
	BPNAME              IS 'Name of the buffer pool',
	BUFFERPOOLID        IS 'Internal buffer pool identifier',
	NGNAME              IS 'Database partition group name (NULL if the buffer pool exists on all database partitions in the database)',
	NPAGES              IS 'Number of pages in the buffer pool',
	PAGESIZE            IS 'Page size for this buffer pool',
	ESTORE              IS 'Y = This buffer pool uses extended storage. (Y/N)'
);

COMMENT ON TABLE SYSCAT.CASTFUNCTIONS IS 'Contains a row for each cast function. It does not include built-in cast functions.';
COMMENT ON SYSCAT.CASTFUNCTIONS (
	FROM_TYPESCHEMA     IS 'Qualified name of the data type of the parameter.',
	FROM_TYPENAME       IS 'Qualified name of the data type of the parameter.',
	TO_TYPESCHEMA       IS 'Qualified name of the data type of the result after casting.',
	TO_TYPENAME         IS 'Qualified name of the data type of the result after casting.',
	FUNCSCHEMA          IS 'Qualified name of the function.',
	FUNCNAME            IS 'Qualified name of the function.',
	SPECIFICNAME        IS 'The name of the function instance.',
	ASSIGN_FUNCTION     IS 'Y = Implicit assignment function. (Y/N)'
);

COMMENT ON TABLE SYSCAT.CHECKS IS 'Contains one row for each CHECK constraint.';
COMMENT ON SYSCAT.CHECKS (
	CONSTNAME           IS 'Name of the check constraint (unique within a table.)',
	DEFINER             IS 'Authorization ID under which the check constraint was defined.',
	TABSCHEMA           IS 'Qualified name of the table to which this constraint applies.',
	TABNAME             IS 'Qualified name of the table to which this constraint applies.',
	CREATE_TIME         IS 'The time at which the constraint was defined. Used in resolving functions that are used in this constraint. No functions will be chosen that were created after the definition of the constraint.',
	QUALIFIER           IS 'Value of the default schema at time of object definition. Used to complete any unqualified references.',
	TYPE                IS 'Type of check constraint (A=System generated, C=Check, F=Func. dependency, O=Object property)',
	FUNC_PATH           IS 'The current SQL path that was used when the constraint was created.',
	TEXT                IS 'The text of the CHECK clause.'
);

COMMENT ON TABLE SYSCAT.COLAUTH IS 'Contains one or more rows for each user or group who is granted a column level privilege, indicating the type of privilege and whether or not it is grantable.';
COMMENT ON SYSCAT.COLAUTH (
	GRANTOR             IS 'Authorization ID of the user who granted the privileges or SYSIBM.',
	GRANTEE             IS 'Authorization ID of the user or group who holds the privileges.',
	GRANTEETYPE         IS 'U = Grantee is an individual user. G = Grantee is a group.',
	TABSCHEMA           IS 'Qualified name of the table or view.',
	TABNAME             IS 'Qualified name of the table or view.',
	COLNAME             IS 'Name of the column to which this privilege applies.',
	COLNO               IS 'Number of this column in the table or view.',
	PRIVTYPE            IS 'Indicates the type of privilege held on the table or view, U = Update privilege, R = Reference privilege.',
	GRANTABLE           IS 'Indicates if the privilege is grantable, G = Grantable, N = Not grantable.'
);

COMMENT ON TABLE SYSCAT.COLCHECKS IS 'Each row represents some column that is referenced by a CHECK constraint.';
COMMENT ON SYSCAT.COLCHECKS (
	CONSTNAME           IS 'Name of the check constraint. (Unique within a table. May be system generated.)',
	TABSCHEMA           IS 'Qualified name of table containing referenced column.',
	TABNAME             IS 'Qualified name of table containing referenced column.',
	COLNAME             IS 'Name of column.',
	USAGE               IS 'D = Functional dependency child, P = Functional dependency parent, R = Column referenced in Check constraint, S = Source column for generated column, T = Target column for generated column'
);

COMMENT ON TABLE SYSCAT.COLDIST IS 'Contains detailed column statistics for use by the optimizer. Each row describes the /n/-th-most-frequent value of some column.';
COMMENT ON SYSCAT.COLDIST (
	TABSCHEMA           IS 'Qualified name of the table to which this entry applies.',
	TABNAME             IS 'Qualified name of the table to which this entry applies.',
	COLNAME             IS 'Name of the column to which this entry applies.',
	TYPE                IS 'F = Frequency (most frequent value), Q = Quantile value 		',
	SEQNO               IS 'If TYPE=F, then N identifies the /n/-th most frequent value. If TYPE=Q, then N identifiers the /n/-th quantile value.',
	COLVALUE            IS 'The data value, as a character literal or a NULL value.',
	VALCOUNT            IS 'If TYPE=F, then the number of occurrences of COLVALUE in the column. If TYPE=Q then the number of rows whose value is less than or equal to COLVALUE.',
	DISTCOUNT           IS 'If TYPE=Q, this column records the number of distinct values that are less than or equal to COLVALUE (NULL if unavailable).'
);

COMMENT ON TABLE SYSCAT.COLGROUPDIST IS 'Contains a row for every value of a column in a column group that makes up the /n/-th most frequent value of the column group or the /n/-th quantile of the column group.';
COMMENT ON SYSCAT.COLGROUPDIST (
	COLGROUPID          IS 'Internal identifier of the column group.',
	TYPE                IS 'F = Frequency value, Q = Quantile value.',
	ORDINAL             IS 'Ordinal number of the column in the group.',
	SEQNO               IS 'Sequence number /n/ representing the /n/-th TYPE value.',
	COLVALUE            IS 'Data value as a character literal or a NULL value.'
);

COMMENT ON TABLE SYSCAT.COLGROUPDISTCOUNTS IS 'Contains a row for the distribution statistics that apply to the /n/-th most frequent value of a column group, or the /n/-th quantile of a column group.';
COMMENT ON SYSCAT.COLGROUPDISTCOUNTS (
	COLGROUPID          IS 'Internal identifier of the column group.',
	TYPE                IS 'F = Frequency value, Q = Quantile value.',
	SEQNO               IS 'Sequence number /n/ representing the /n/-th TYPE value.',
	VALCOUNT            IS 'If TYPE=F, VALCOUNT is the number of occurrences of COLVALUE for the column group with this SEQNO. If TYPE = Q, VALCOUNT is the number of rows whose value is less than or equal to COLVALUE for the column group with this SEQNO.',
	DISTCOUNT           IS 'If TYPE=Q, this column records the number of distinct values that are less than or equal to COLVALUE for the column group with this SEQNO (NULL if unavailable).'
);

COMMENT ON TABLE SYSCAT.COLGROUPS IS 'Contains a row for every column group, and statistics that apply to the entire column group.';
COMMENT ON SYSCAT.COLGROUPS (
	COLGROUPSCHEMA      IS 'Qualified name of the column group.',
	COLGROUPNAME        IS 'Qualified name of the column group.',
	COLGROUPID          IS 'Internal identifier of the column group.',
	COLGROUPCARD        IS 'Cardinality of the column group.',
	NUMFREQ_VALUES      IS 'Number of frequent values collected for the column group.',
	NUMQUANTILES        IS 'Number of quantiles collected for the column group.'
);

COMMENT ON TABLE SYSCAT.COLIDENTATTRIBUTES IS 'Contains one row for each identity column that is defined for a table.';
COMMENT ON SYSCAT.COLIDENTATTRIBUTES (
	TABSCHEMA           IS 'Qualified name of the table or view that contains the column.',
	TABNAME             IS 'Qualified name of the table or view that contains the column.',
	COLNAME             IS 'Column name.',
	START               IS 'Starting value.',
	INCREMENT           IS 'Increment value.',
	MINVALUE            IS 'Minimum value.',
	MAXVALUE            IS 'Maximum value.',
	CYCLE               IS 'Whether cycling will occur when a boundary is reached. (Y/N)',
	CACHE               IS 'Number of sequence values to preallocate in memory for faster access. 0 indicates that values are not preallocated.',
	SEQID               IS 'Internal ID of the sequence.'
);

COMMENT ON TABLE SYSCAT.COLOPTIONS IS 'Each row contains column specific option values.';
COMMENT ON SYSCAT.COLOPTIONS (
	TABSCHEMA           IS 'Qualified nickname for the column.',
	TABNAME             IS 'Qualified nickname for the column.',
	COLNAME             IS 'Local column name.',
	OPTION              IS 'Name of the column option.',
	SETTING             IS 'Value for the column option.'
);

COMMENT ON TABLE SYSCAT.COLUMNS IS 'Contains one row for each column (including inherited columns, where applicable) that is defined for a table or view. All of the catalog views have entries in the @SYSCAT.COLUMNS table.';
COMMENT ON SYSCAT.COLUMNS (
	TABSCHEMA           IS 'Qualified name of the table or view that contains the column.',
	TABNAME             IS 'Qualified name of the table or view that contains the column.',
	COLNAME             IS 'Column name.',
	COLNO               IS 'Numerical place of column in table or view, beginning at zero.',
	TYPESCHEMA          IS 'Contains the qualified name of the type, if the data type of the column is distinct. Otherwise TYPESCHEMA contains the value SYSIBM and TYPENAME contains the data type of the column (in long form, for example, CHARACTER).',
	TYPENAME            IS 'Contains the qualified name of the type, if the data type of the column is distinct. Otherwise TYPESCHEMA contains the value SYSIBM and TYPENAME contains the data type of the column (in long form, for example, CHARACTER).',
	LENGTH              IS 'Maximum length of data. 0 for distinct types. The LENGTH column indicates precision for DECIMAL fields.',
	SCALE               IS 'Scale for DECIMAL fields; 0 if not DECIMAL.',
	DEFAULT             IS 'Default value for the column of a table expressed as a constant, special register, or cast-function appropriate for the data type of the column. May also be the keyword NULL. NULL value if a DEFAULT clause was not specified.',
	NULLS               IS 'Indicates if the column is nullable. The value can be N for a view column that is derived from an expression or function. Nevertheless, such a column allows NULLs when the statement using the view is processed with warnings for arithmetic errors.',
	CODEPAGE            IS 'Code page of the column. For character-string columns not defined with the FOR BIT DATA attribute, the value is the database code page. For graphic-string columns, the value is the DBCS code page implied by the database code page. Otherwise, 0.',
	LOGGED              IS 'Applies only to columns whose type is LOB or distinct based on LOB (blank otherwise). (Y/N)',
	COMPACT             IS 'Applies only to columns whose type is LOB or distinct based on LOB (blank otherwise). (Y/N)',
	COLCARD             IS 'Number of distinct values in the column; -1 if statistics are not gathered; -2 for inherited columns and columns of H-tables.',
	HIGH2KEY            IS 'Second highest value of the column. This field is empty if statistics are not gathered, and for inherited columns and columns of H-tables.',
	LOW2KEY             IS 'Second lowest value of the column. This field is empty if statistics are not gathered, and for inherited columns and columns of H-tables.',
	AVGCOLLEN           IS 'Average space required for the column length. -1 if a long field or LOB, or statistics have not been collected; -2 for inherited columns and columns of H-tables.',
	KEYSEQ              IS 'The column''s numerical position within the table''s primary key. This field is NULL for subtables and hierarchy tables.',
	PARTKEYSEQ          IS 'The column''s numerical position within the table''s partitioning key. This field is NULL or 0 if the column is not part of the partitioning key. This field is also NULL for subtables and hierarchy tables.',
	NQUANTILES          IS 'Number of quantile values recorded in @SYSCAT.COLDIST for this column; -1 if no statistics; -2 for inherited columns and columns of H-tables.',
	NMOSTFREQ           IS 'Number of most-frequent values recorded in @SYSCAT.COLDIST for this column; -1 if no statistics; -2 for inherited columns and columns of H-tables.',
	NUMNULLS            IS 'Contains the number of NULLs in a column. -1 if statistics are not gathered.',
	TARGET_TYPESCHEMA   IS 'Qualified name of the target type, if the type of the column is REFERENCE. NULL value if the type of the column is not REFERENCE.',
	TARGET_TYPENAME     IS 'Qualified name of the target type, if the type of the column is REFERENCE. NULL value if the type of the column is not REFERENCE.',
	SCOPE_TABSCHEMA     IS 'Qualified name of the scope (target table), if the type of the column is REFERENCE. NULL value if the type of the column is not REFERENCE or the scope is not defined.',
	SCOPE_TABNAME       IS 'Qualified name of the scope (target table), if the type of the column is REFERENCE. NULL value if the type of the column is not REFERENCE or the scope is not defined.',
	SOURCE_TABSCHEMA    IS 'Qualified name of the table or view in the respective hierarchy where the column was introduced. For non-inherited columns, the values are the same as TBCREATOR and TBNAME. NULL for columns of non-typed tables and views',
	SOURCE_TABNAME      IS 'Qualified name of the table or view in the respective hierarchy where the column was introduced. For non-inherited columns, the values are the same as TBCREATOR and TBNAME. NULL for columns of non-typed tables and views',
	DL_FEATURES         IS 'Applies to DATALINK type columns only. NULL otherwise. See DB2 SQL Reference for character position encodings.',
	SPECIAL_PROPS       IS 'Applies to REFERENCE type columns only. NULL otherwise. Each character position is defined as follows: Object identifier (OID) column (Y for yes, N for no), User generated or system generated (U for user, S for system)',
	HIDDEN              IS 'Type of hidden column. S = System managed hidden column, Blank if column is not hidden ',
	INLINE_LENGTH       IS 'Length of structured type column that can be kept with base table row. 0 if no value explicitly set by ALTER/CREATE TABLE statement.',
	IDENTITY            IS 'Y indicates that the column is an identity column; N indicates that the column is not an identity column.',
	GENERATED           IS 'Type of generated column. A = Column value is always generated; D = Column value is generated by default; Blank if column is not generated ',
	COMPRESS            IS 'S = Compress system default values; O = Compress off',
	TEXT                IS 'Contains the text of the generated column, starting with the keyword AS.',
	REMARKS             IS 'User-supplied comment.',
	AVGDISTINCTPERPAGE  IS 'For future use.',
	PAGEVARIANCERATIO   IS 'For future use.',
	SUB_COUNT           IS 'Average number of sub-elements. Only applicable for character columns.',
	SUB_DELIM_LENGTH    IS 'Average length of each delimiter separating each sub-element. Only applicable for character columns.'
);

COMMENT ON TABLE SYSCAT.COLUSE IS 'Contains a row for every column that participates in the DIMENSIONS clause of the CREATE TABLE statement.';
COMMENT ON SYSCAT.COLUSE (
	TABSCHEMA           IS 'Qualified name of the table containing the column',
	TABNAME             IS 'Qualified name of the table containing the column',
	COLNAME             IS 'Name of the column',
	DIMENSION           IS 'Dimension number, based on the order of dimensions specified in the DIMENSIONS clause (initial position = 0). For a composite dimension, this value will be the same for each component of the dimension.',
	COLSEQ              IS 'Numeric position of the column in the dimension to which it belongs (initial position = 0). The value is 0 for the single column in a noncomposite dimension.',
	TYPE                IS 'Type of dimension. C = clustering/multi-dimensional clustering (MDC)'
);

COMMENT ON TABLE SYSCAT.CONSTDEP IS 'Contains a row for every dependency of a constraint on some other object.';
COMMENT ON SYSCAT.CONSTDEP (
	CONSTNAME           IS 'Name of the constraint.',
	TABSCHEMA           IS 'Qualified name of the table to which the constraint applies.',
	TABNAME             IS 'Qualified name of the table to which the constraint applies.',
	BTYPE               IS 'Type of object that the constraint depends on. Possible values: F = Function instance; I = Index instance; R = Structured type',
	BSCHEMA             IS 'Qualified name of object that the constraint depends on.',
	BNAME               IS 'Qualified name of object that the constraint depends on.'
);

COMMENT ON TABLE SYSCAT.DATATYPES IS 'Contains a row for every data type, including built-in and user-defined types.';
COMMENT ON SYSCAT.DATATYPES (
	TYPESCHEMA          IS 'Qualified name of the data type (for built-in types, TYPESCHEMA is SYSIBM).',
	TYPENAME            IS 'Qualified name of the data type (for built-in types, TYPESCHEMA is SYSIBM).',
	DEFINER             IS 'Authorization ID under which type was created.',
	SOURCESCHEMA        IS 'Qualified name of the source type for distinct types. Qualified name of the builtin type used as the reference type that is used as the representation for references to structured types. NULL for other types.',
	SOURCENAME          IS 'Qualified name of the source type for distinct types. Qualified name of the builtin type used as the reference type that is used as the representation for references to structured types. NULL for other types.',
	METATYPE            IS 'S = System predefined type; T = Distinct type; R = Structured type',
	TYPEID              IS 'The system generated internal identifier of the data type.',
	SOURCETYPEID        IS 'Internal type ID of source type (NULL for built-in types). For user-defined structured types, this is the internal type ID of the reference representation type.',
	LENGTH              IS 'Maximum length of the type. 0 for system predefined parameterized types (for example, DECIMAL and VARCHAR). For user-defined structured types, this indicates the length of the reference representation type.',
	SCALE               IS 'Scale for distinct types or reference representation types based on the system predefined DECIMAL type. 0 for all other types (including DECIMAL itself). For user-defined structured types, this indicates the length of the reference representation type.',
	CODEPAGE            IS 'Code page for character and graphic distinct types or reference representation types; 0 otherwise.',
	CREATE_TIME         IS 'Creation time of the data type.',
	ATTRCOUNT           IS 'Number of attributes in data type.',
	INSTANTIABLE        IS 'Y = Type can be instantiated; N = Type can not be instantiated.',
	WITH_FUNC_ACCESS    IS 'Y = All the methods for this type can be invoked using function notation; N = Methods for this type can not be invoked using function notation.',
	FINAL               IS 'Y = User-defined type can not have subtypes; N = User-defined type can have subtypes.',
	INLINE_LENGTH       IS 'Length of structured type that can be kept with base table row. 0 if no value explicitly set by CREATE TYPE statement.',
	NATURAL_INLINE_LENGTH IS 'System-calculated inline length of the structured type.',
	REMARKS             IS 'User-supplied comment, or NULL.'
);

COMMENT ON TABLE SYSCAT.DBAUTH IS 'Records the database authorities held by users.';
COMMENT ON SYSCAT.DBAUTH (
	GRANTOR             IS 'SYSIBM or authorization ID of the user who granted the privileges.',
	GRANTEE             IS 'Authorization ID of the user or group who holds the privileges.',
	GRANTEETYPE         IS 'U = Grantee is an individual user; G = Grantee is a group.',
	DBADMAUTH           IS 'Whether grantee holds DBADM authority over the database. (Y/N)',
	CREATETABAUTH       IS 'Whether grantee can create tables in the database (CREATETAB). (Y/N)',
	BINDADDAUTH         IS 'Whether grantee can create new packages in the database (BINDADD). (Y/N)',
	CONNECTAUTH         IS 'Whether grantee can connect to the database (CONNECT). (Y/N)',
	NOFENCEAUTH         IS 'Whether grantee holds privilege to create non-fenced functions. (Y/N)',
	IMPLSCHEMAAUTH      IS 'Whether grantee can implicitly create schemas in the database (IMPLICIT_SCHEMA). (Y/N)',
	LOADAUTH            IS 'Whether grantee holds LOAD authority over the database. (Y/N)',
	EXTERNALROUTINEAUTH IS 'Whether grantee can create external routines (CREATE_EXTERNAL_ROUTINE). (Y/N)',
	QUIESCECONNECTAUTH  IS 'Whether grantee can connect to a database (QUIESCE_CONNECT). (Y/N)'
);

COMMENT ON TABLE SYSCAT.DBPARTITIONGROUPDEF IS 'Contains a row for each partition that is contained in a database partition group.';
COMMENT ON SYSCAT.DBPARTITIONGROUPDEF (
	DBPGNAME            IS 'The name of the database partition group that contains the database partition.',
	DBPARTITIONNUM      IS 'The partition number of a partition contained in the database partition group. A valid partition number is between 0 and 999 inclusive.',
	IN_USE              IS 'Status of the database partition. See DB2 SQL Reference for details of the values. (A/D/T/Y)'
);

COMMENT ON TABLE SYSCAT.DBPARTITIONGROUPS IS 'Contains a row for each database partition group.';
COMMENT ON SYSCAT.DBPARTITIONGROUPS (
	DBPGNAME            IS 'Name of the database partition group.',
	DEFINER             IS 'Authorization ID of the database partition group definer.',
	PMAP_ID             IS 'Identifier of the partitioning map in @SYSCAT.PARTITIONMAPS.',
	REDISTRIBUTE_PMAP_ID IS 'Identifier of the partitioning map currently being used for redistribution. Value is -1 if redistribution is currently not in progress.',
	CREATE_TIME         IS 'Creation time of database partition group.',
	REMARKS             IS 'User-provided comment.'
);

COMMENT ON TABLE SYSCAT.EVENTMONITORS IS 'Contains a row for every event monitor that has been defined.';
COMMENT ON SYSCAT.EVENTMONITORS (
	EVMONNAME           IS 'Name of event monitor.',
	DEFINER             IS 'Authorization ID of definer of event monitor.',
	TARGET_TYPE         IS 'The type of target to which event data is written: F = File; P = Pipe; T = Table',
	TARGET              IS 'Name of the target to which event data is written. Absolute pathname of file, or absolute name of pipe.',
	MAXFILES            IS 'Maximum number of event files that this event monitor permits in an event path. NULL if there is no maximum, or if the target-type is not FILE.',
	MAXFILESIZE         IS 'Maximum size (in 4K pages) that each event file can reach before the event monitor creates a new file. NULL if there is no maximum, or if the target-type is not FILE.',
	BUFFERSIZE          IS 'Size of buffers (in 4K pages) used by event monitors with file targets; otherwise NULL.',
	IO_MODE             IS 'Mode of file I/O. B = Blocked; N = Not blocked. NULL if target-type is not FILE.',
	WRITE_MODE          IS 'Indicates how this monitor handles existing event data when the monitor is activated. A = Append; R = Replace. NULL if target-type is not FILE.',
	AUTOSTART           IS 'The event monitor will be activated automatically when the database starts. (Y/N)',
	DBPARTITIONNUM      IS 'The number of the database partition on which the event monitor runs and logs events.',
	MONSCOPE            IS 'Monitoring scope: L = Local; G = Global; T = Per node where table space exists; Blank = valid only for WRITE TO TABLE event monitors.',
	EVMON_ACTIVATES     IS 'The number of times this event monitor has been activated.',
	REMARKS             IS 'Reserved for future use.'
);

COMMENT ON TABLE SYSCAT.EVENTS IS 'Contains a row for every event that is being monitored. An event monitor, in general, monitors multiple events.';
COMMENT ON SYSCAT.EVENTS (
	EVMONNAME           IS 'Name of event monitor that is monitoring this event.',
	TYPE                IS 'Type of event being monitored: DATABASE; CONNECTIONS; TABLES; STATEMENTS; TRANSACTIONS; DEADLOCKS; DETAILDEADLOCKS; TABLESPACES',
	FILTER              IS 'The full text of the WHERE-clause that applies to this event.'
);

COMMENT ON TABLE SYSCAT.EVENTTABLES IS 'Contains a row for every target table of an event monitor that writes to SQL tables.';
COMMENT ON SYSCAT.EVENTTABLES (
	EVMONNAME           IS 'Name of event monitor.',
	LOGICAL_GROUP       IS 'Name of the logical data group. BUFFERPOOL; CONN; CONNHEADER; CONTROL; DB; DEADLOCK; DLCONN; DLLOCK; STMT; SUBSECTION; TABLE; TABLESPACE; XACT ',
	TABSCHEMA           IS 'Qualified name of the target table.',
	TABNAME             IS 'Qualified name of the target table.',
	PCTDEACTIVATE       IS 'A percent value that specifies how full a DMS table space must be before an event monitor automatically deactivates. Set to 100 for SMS table spaces.'
);

COMMENT ON TABLE SYSCAT.FULLHIERARCHIES IS 'Each row represents the relationship between a subtable and a supertable, a subtype and a supertype, or a subview and a superview. All hierarchical relationships, including immediate ones, are included in this view';
COMMENT ON SYSCAT.FULLHIERARCHIES (
	METATYPE            IS 'Encodes the type of relationship: R = Between structured types; U = Between typed tables; W = Between typed views',
	SUB_SCHEMA          IS 'Qualified name of subtype, subtable or subview.',
	SUB_NAME            IS 'Qualified name of subtype, subtable or subview.',
	SUPER_SCHEMA        IS 'Qualified name of supertype, supertable or superview.',
	SUPER_NAME          IS 'Qualified name of supertype, supertable or superview.',
	ROOT_SCHEMA         IS 'Qualified name of the table, view or type that is at the root of the hierarchy.'
);

COMMENT ON TABLE SYSCAT.FUNCMAPOPTIONS IS 'Each row contains function mapping option values.';
COMMENT ON SYSCAT.FUNCMAPOPTIONS (
	FUNCTION_MAPPING    IS 'Function mapping name.',
	OPTION              IS 'Name of the function mapping option.',
	SETTING             IS 'Value of the function mapping option.'
);

COMMENT ON TABLE SYSCAT.FUNCMAPPARMOPTIONS IS 'Each row contains function mapping parameter option values.';
COMMENT ON SYSCAT.FUNCMAPPARMOPTIONS (
	FUNCTION_MAPPING    IS 'Name of function mapping.',
	ORDINAL             IS 'Position of parameter',
	LOCATION            IS 'L = Local; R = Remote',
	OPTION              IS 'Name of the function mapping parameter option.',
	SETTING             IS 'Value of the function mapping parameter option.'
);

COMMENT ON TABLE SYSCAT.FUNCMAPPINGS IS 'Each row contains function mappings.';
COMMENT ON SYSCAT.FUNCMAPPINGS (
	FUNCTION_MAPPING    IS 'Name of function mapping (may be system generated).',
	FUNCSCHEMA          IS 'Function schema. NULL if system built-in function.',
	FUNCNAME            IS 'Name of the local function (built-in or user-defined).',
	FUNCID              IS 'Internally assigned identifier.',
	SPECIFICNAME        IS 'Name of the local function instance.',
	DEFINER             IS 'Authorization ID under which this mapping was created.',
	WRAPNAME            IS 'Wrapper name to which the mapping is applied.',
	SERVERNAME          IS 'Name of the data source.',
	SERVERTYPE          IS 'Type of data source to which mapping is applied.',
	SERVERVERSION       IS 'Version of the server type to which mapping is applied.',
	CREATE_TIME         IS 'Time at which the mapping is created.',
	REMARKS             IS 'User supplied comment, or NULL.'
);

COMMENT ON TABLE SYSCAT.HIERARCHIES IS 'Each row represents the relationship between a subtable and its immediate supertable, a subtype and its immediate supertype, or a subview and its immediate superview. Only immediate hierarchical relationships are included in this view.';
COMMENT ON SYSCAT.HIERARCHIES (
	METATYPE            IS 'Encodes the type of relationship: R = Between structured types; U = Between typed tables; W = Between typed views',
	SUB_SCHEMA          IS 'Qualified name of subtype, subtable, or subview.',
	SUB_NAME            IS 'Qualified name of subtype, subtable, or subview.',
	SUPER_SCHEMA        IS 'Qualified name of supertype, supertable, or superview.',
	SUPER_NAME          IS 'Qualified name of supertype, supertable, or superview.',
	ROOT_SCHEMA         IS 'Qualified name of the table, view or type that is at the root of the hierarchy.',
	ROOT_NAME           IS 'Qualified name of the table, view or type that is at the root of the hierarchy.'
);

COMMENT ON TABLE SYSCAT.INDEXAUTH IS 'Contains a row for every privilege held on an index.';
COMMENT ON SYSCAT.INDEXAUTH (
	GRANTOR             IS 'Authorization ID of the user who granted the privileges.',
	GRANTEE             IS 'Authorization ID of the user or group who holds the privileges.',
	GRANTEETYPE         IS 'U = Grantee is an individual user; G = Grantee is a group.',
	INDSCHEMA           IS 'Qualified name of the index.',
	INDNAME             IS 'Qualified name of the index.',
	CONTROLAUTH         IS 'Whether grantee holds CONTROL privilege over the index. (Y/N)'
);

COMMENT ON TABLE SYSCAT.INDEXCOLUSE IS 'Lists all columns that participate in an index.';
COMMENT ON SYSCAT.INDEXCOLUSE (
	INDSCHEMA           IS 'Qualified name of the index.',
	INDNAME             IS 'Qualified name of the index.',
	COLNAME             IS 'Name of the column.',
	COLSEQ              IS 'Numeric position of the column in the index (initial position = 1).',
	COLORDER            IS 'Order of the values in this column in the index. A = Ascending; D = Descending; I = INCLUDE column (ordering ignored)'
);

COMMENT ON TABLE SYSCAT.INDEXDEP IS 'Each row represents a dependency of an index on some other object.';
COMMENT ON SYSCAT.INDEXDEP (
	INDSCHEMA           IS 'Qualified name of the index that has dependencies on another object.',
	INDNAME             IS 'Qualified name of the index that has dependencies on another object.',
	BTYPE               IS 'Type of object on which the index depends. A = Alias; F = Function instance; O = Privilege dependency; R = Structured type; S = Materialized query table; T = Table; U = Typed table; V = View; W = Typed view; X = Index extension',
	BSCHEMA             IS 'Qualified name of the object on which the index has a dependency.',
	BNAME               IS 'Qualified name of the object on which the index has a dependency.',
	TABAUTH             IS 'If BTYPE = O, S, T, U, V, or W, encodes the privileges on the table or view that are required by the dependent index; otherwise NULL.'
);

COMMENT ON TABLE SYSCAT.INDEXES IS 'Contains one row for each index (including inherited indexes, where applicable) that is defined for a table.';
COMMENT ON SYSCAT.INDEXES (
	INDSCHEMA           IS 'Name of the index.',
	INDNAME             IS 'Name of the index.',
	DEFINER             IS 'User who created the index.',
	TABSCHEMA           IS 'Qualified name of the table or nickname on which the index is defined.',
	TABNAME             IS 'Qualified name of the table or nickname on which the index is defined.',
	COLNAMES            IS 'List of column names, each preceded by + or - to indicate ascending or descending order respectively. DEPRECATED: Use @SYSCAT.INDEXCOLUSE for this information.',
	UNIQUERULE          IS 'Unique rule: D = Duplicates allowed; P = Primary index; U = Unique entries only allowed',
	MADE_UNIQUE         IS 'Y = Index was originally non-unique but was converted to a unique index to support a unique or primary key constraint. If the constraint is dropped, the index will revert to non-unique; N = Index remains as it was created.',
	COLCOUNT            IS 'Number of columns in the key, plus the number of include columns, if any.',
	UNIQUE_COLCOUNT     IS 'The number of columns required for a unique key. Always <=COLCOUNT. < COLCOUNT only if there are include columns. -1 if the index has no unique key (permits duplicates).',
	INDEXTYPE           IS 'Type of index: CLUS = Clustering; REG = Regular; DIM = Dimension block index; BLOK = Block index',
	ENTRYTYPE           IS 'H = An index on a hierarchy table (H-table); L = Logical index on a typed table; Blank if an index on an untyped table',
	PCTFREE             IS 'Percentage of each index leaf page to be reserved during initial building of the index. This space is available for future inserts after the index is built.',
	IID                 IS 'Internal index ID.',
	NLEAF               IS 'Number of leaf pages; -1 if statistics are not gathered.',
	NLEVELS             IS 'Number of index levels; -1 if statistics are not gathered.',
	FIRSTKEYCARD        IS 'Number of distinct first key values; -1 if statistics are not gathered.',
	FIRST2KEYCARD       IS 'Number of distinct keys using the first two columns of the index; -1 if no statistics, or if not applicable.',
	FIRST3KEYCARD       IS 'Number of distinct keys using the first three columns of the index; -1 if no statistics, or if not applicable.',
	FIRST4KEYCARD       IS 'Number of distinct keys using the first four columns of the index; -1 if no statistics, or if not applicable.',
	FULLKEYCARD         IS 'Number of distinct full key values; -1 if statistics are not gathered.',
	CLUSTERRATIO        IS 'Degree of data clustering with the index; -1 if statistics are not gathered, or if detailed index statistics are gathered (in which case, CLUSTERFACTOR will be used instead).',
	CLUSTERFACTOR       IS 'Finer measurement of degree of clustering, or -1 if detailed index statistics have not been gathered, or if the index is defined on a nickname.',
	SEQUENTIAL_PAGES    IS 'Number of leaf pages located on disk in index key order with few or no large gaps between them; -1 if no statistics are available.',
	DENSITY             IS 'Ratio of SEQUENTIAL_PAGES to number of pages in the range of pages occupied by the index, expressed as a percent (integer between 0 and 100; -1 if no statistics are available.)',
	USER_DEFINED        IS '1 if this index was defined by a user and has not been dropped; otherwise 0.',
	SYSTEM_REQUIRED     IS '1 or 2 if required for a primary or unique key constraint, or a dimension block index, or composite block index for an MDC table, and/or required as the index on the (OID) column of a type table. Otherwise, 0',
	CREATE_TIME         IS 'Time when the index was created.',
	STATS_TIME          IS 'Last time when any change was made to recorded statistics for this index. NULL if no statistics available.',
	PAGE_FETCH_PAIRS    IS 'A list of pairs of integers, represented in character form. Each pair represents the number of pages in a hypothetical buffer, and the number of page fetches required to scan the table with this index using said buffer. Blank if no data available.',
	MINPCTUSED          IS 'If not zero, online index defragmentation is enabled, and the value is the threshold of minimum used space before merging pages.',
	REVERSE_SCANS       IS 'Y = Index supports reverse scans; N = Index does not support reverse scans',
	INTERNAL_FORMAT     IS '1 if the index does not have backward pointers; >= 2 if the index has backward pointers; 6 if the index is a composite block index',
	REMARKS             IS 'User-supplied comment, or NULL.',
	IESCHEMA            IS 'Qualified name of index extension. NULL for ordinary indexes.',
	IENAME              IS 'Qualified name of index extension. NULL for ordinary indexes.',
	IEARGUMENTS         IS 'External information of the parameter specified when the index is created. NULL for ordinary indexes.',
	INDEX_OBJECTID      IS 'Index object identifier for the table.',
	NUMRIDS             IS 'Total number of row identifiers (RIDs) in the index.',
	NUMRIDS_DELETED     IS 'Total number of row identifiers in the index that are marked as deleted, excluding those row identifiers on leaf pages on which all row identifiers are as marked deleted.',
	NUM_EMPTY_LEAFS     IS 'Total number of index leaf pages that have all of their row identifiers marked as deleted.',
	AVERAGE_RANDOM_FETCH_PAGES IS 'Average number of random table pages between sequential page accesses when fetching using the index; -1 if it is not known.',
	AVERAGE_RANDOM_PAGES IS 'Average number of random index pages between sequential index page accesses; -1 if it is not known.',
	AVERAGE_SEQUENCE_GAP IS 'Gap between index page sequences. Detected through a scan of index leaf pages, each gap represents the average number of index pages that must be randomly fetched between sequences of index pages; -1 if it is not known.',
	AVERAGE_SEQUENCE_FETCH_GAP IS 'Gap between table page sequences when fetching using the index. Detected through a scan of index leaf pages, each gap represents the average number of table pages that must be randomly fetched between sequences of table pages; -1 if it is not known.',
	AVERAGE_SEQUENCE_PAGES IS 'Average number of index pages accessible in sequence (that is, the number of index pages that the prefetchers would detect as being in sequence); -1 if it is not known.',
	AVERAGE_SEQUENCE_FETCH_PAGES IS 'Average number of table pages accessible in sequence (that is, the number of table pages that the prefetchers would detect as being in sequence) when fetching using the index; -1 if it is not known.',
	TBSPACEID           IS 'Internal identifier for the index table space.'
);

COMMENT ON TABLE SYSCAT.INDEXEXPLOITRULES IS 'Each row represents an index exploitation.';
COMMENT ON SYSCAT.INDEXEXPLOITRULES (
	FUNCID              IS 'Function ID.',
	SPECID              IS 'Number of the predicate specification in the CREATE FUNCTION statement.',
	IESCHEMA            IS 'Qualified name of the index extension.',
	IENAME              IS 'Qualified name of the index extension.',
	RULEID              IS 'Unique exploitation rule ID.',
	SEARCHMETHODID      IS 'The search method ID in the specific index extension.',
	SEARCHKEY           IS 'Key used to exploit index.',
	SEARCHARGUMENT      IS 'Search arguments used in the index exploitation.',
	EXACT               IS 'Indicates whether or not index look-up is exact in terms of predicate evaluation. (Y/N)'
);

COMMENT ON TABLE SYSCAT.INDEXEXTENSIONDEP IS 'Contains a row for each dependency that index extensions have on various database objects.';
COMMENT ON SYSCAT.INDEXEXTENSIONDEP (
	IESCHEMA            IS 'Qualified name of the index extension that has dependencies on another object.',
	IENAME              IS 'Qualified name of the index extension that has dependencies on another object.',
	BTYPE               IS 'Type of object on which the index extension is dependent. See DB2 SQL Reference for definition of values (A/F/J/O/R/S/T/U/V/W/X)',
	BSCHEMA             IS 'Qualified name of the object on which the index extension depends. (If BTYPE=F, this is the specific name of a function.)',
	BNAME               IS 'Qualified name of the object on which the index extension depends. (If BTYPE=F, this is the specific name of a function.)',
	TABAUTH             IS 'If BTYPE=O, T, U, V, or W, encodes the privileges on the table (or view) that are required by a dependent trigger; otherwise NULL.'
);

COMMENT ON TABLE SYSCAT.INDEXEXTENSIONMETHODS IS 'Each row represents a search method. One index extension may include multiple search methods.';
COMMENT ON SYSCAT.INDEXEXTENSIONMETHODS (
	METHODNAME          IS 'Name of search method.',
	METHODID            IS 'Number of the method in the index extension.',
	IESCHEMA            IS 'Qualified name of index extension.',
	IENAME              IS 'Qualified name of index extension.',
	RANGEFUNCSCHEMA     IS 'Qualified name of range-through function.',
	RANGEFUNCNAME       IS 'Qualified name of range-through function.',
	RANGESPECIFICNAME   IS 'Range-through function specific name.',
	FILTERFUNCSCHEMA    IS 'Qualified name of filter function.',
	FILTERFUNCNAME      IS 'Qualified name of filter function.',
	FILTERSPECIFICNAME  IS 'Function specific name of filter function.',
	REMARKS             IS 'User-supplied or NULL.'
);

COMMENT ON TABLE SYSCAT.INDEXEXTENSIONPARMS IS 'Each row represents an index extension instance parameter or source key definition.';
COMMENT ON SYSCAT.INDEXEXTENSIONPARMS (
	IESCHEMA            IS 'Qualified name of index extension.',
	IENAME              IS 'Qualified name of index extension.',
	ORDINAL             IS 'Sequence number of parameter or source key.',
	PARMNAME            IS 'Name of parameter or source key.',
	TYPESCHEMA          IS 'Qualified name of the instance parameter or source key data type.',
	TYPENAME            IS 'Qualified name of the instance parameter or source key data type.',
	LENGTH              IS 'Length of the instance parameter or source key data type.',
	SCALE               IS 'Scale of the instance parameter or source key data type. Zero (0) when not applicable.',
	PARMTYPE            IS 'Type represented by the row: P = index extension parameter; K = key column',
	CODEPAGE            IS 'Code page of the index extension parameter. Zero if not a string type.'
);

COMMENT ON TABLE SYSCAT.INDEXEXTENSIONS IS 'Contains a row for each index extension.';
COMMENT ON SYSCAT.INDEXEXTENSIONS (
	IESCHEMA            IS 'Qualified name of index extension.',
	IENAME              IS 'Qualified name of index extension.',
	DEFINER             IS 'Authorization ID under which the index extension was defined.',
	CREATE_TIME         IS 'Time at which the index extension was defined.',
	KEYGENFUNCSCHEMA    IS 'Qualified name of key generation function.',
	KEYGENFUNCNAME      IS 'Qualified name of key generation function.',
	KEYGENSPECIFICNAME  IS 'Key generation function specific name.',
	TEXT                IS 'The full text of the CREATE INDEX EXTENSION statement.',
	REMARKS             IS 'User-supplied comment, or NULL.'
);

COMMENT ON TABLE SYSCAT.INDEXOPTIONS IS 'Each row contains index specific option values.';
COMMENT ON SYSCAT.INDEXOPTIONS (
	INDSCHEMA           IS 'Schema name of the index.',
	INDNAME             IS 'Local name of the index.',
	OPTION              IS 'Name of the index option.',
	SETTING             IS 'Value.'
);

COMMENT ON TABLE SYSCAT.KEYCOLUSE IS 'Lists all columns that participate in a key (including inherited primary or unique keys where applicable) defined by a unique, primary key, or foreign key constraint.';
COMMENT ON SYSCAT.KEYCOLUSE (
	CONSTNAME           IS 'Name of the constraint (unique within a table).',
	TABSCHEMA           IS 'Qualified name of the table containing the column.',
	TABNAME             IS 'Qualified name of the table containing the column.',
	COLNAME             IS 'Name of the column.',
	COLSEQ              IS 'Numeric position of the column in the key (initial position=1).'
);

COMMENT ON TABLE SYSCAT.NAMEMAPPINGS IS 'Each row represents the mapping between logical objects and the corresponding implementation objects that implement the logical objects.';
COMMENT ON SYSCAT.NAMEMAPPINGS (
	TYPE                IS 'C = Column; I = Index; U = Typed table ',
	LOGICAL_SCHEMA      IS 'Qualified name of the logical object.',
	LOGICAL_NAME        IS 'Qualified name of the logical object.',
	LOGICAL_COLNAME     IS 'If TYPE = C, then the name of the logical column. Otherwise NULL.',
	IMPL_SCHEMA         IS 'Qualified name of the implementation object that implements the logical object.',
	IMPL_NAME           IS 'Qualified name of the implementation object that implements the logical object.',
	IMPL_COLNAME        IS 'If TYPE = C, then the name of the implementation column. Otherwise NULL.'
);

COMMENT ON TABLE SYSCAT.PACKAGEAUTH IS 'Contains a row for every privilege held on a package.';
COMMENT ON SYSCAT.PACKAGEAUTH (
	GRANTOR             IS 'Authorization ID of the user who granted the privileges.',
	GRANTEE             IS 'Authorization ID of the user or group who holds the privileges.',
	GRANTEETYPE         IS 'U = Grantee is an individual user; G = Grantee is a group.',
	PKGSCHEMA           IS 'Name of the package on which the privileges are held.',
	PKGNAME             IS 'Name of the package on which the privileges are held.',
	CONTROLAUTH         IS 'Indicates whether grantee holds CONTROL privilege on the package. (Y/N)',
	BINDAUTH            IS 'Indicates whether grantee holds BIND privilege on the package. (Y/N/G=Grantable)',
	EXECUTEAUTH         IS 'Indicates whether grantee holds EXECUTE privilege on the package. (Y/N/G=Grantable)'
);

COMMENT ON TABLE SYSCAT.PACKAGEDEP IS 'Contains a row for each dependency that packages have on indexes, tables, views, triggers, functions, aliases, types, and hierarchies.';
COMMENT ON SYSCAT.PACKAGEDEP (
	PKGSCHEMA           IS 'Name of the package.',
	PKGNAME             IS 'Name of the package.',
	UNIQUE_ID           IS 'Internal date and time information indicating when the package was first created. Useful for identifying a specific package when multiple packages having the same name exist.',
	PKGVERSION          IS 'Version identifier of the package.',
	BINDER              IS 'Binder of the package.',
	BTYPE               IS 'Type of object BNAME. See DB2 SQL Reference for definitions of values. (A/B/D/F/I/M/N/O/P/R/S/T/U/V/W)',
	BSCHEMA             IS 'Qualified name of an object on which the package depends.',
	BNAME               IS 'Qualified name of an object on which the package depends.',
	TABAUTH             IS 'If BTYPE is O, S, T, U, V or W then it encodes the privileges that are required by this package (SELECT, INSERT, DELETE, UPDATE).'
);

COMMENT ON TABLE SYSCAT.PACKAGES IS 'Contains a row for each package that has been created by binding an application program.';
COMMENT ON SYSCAT.PACKAGES (
	PKGSCHEMA           IS 'Schema qualifier of the package name.',
	PKGNAME             IS 'Unqualified identifier of the package name',
	PKGVERSION          IS 'Version identifier of the package name.',
	BOUNDBY             IS 'Authorization ID (OWNER) of the binder of the package.',
	DEFINER             IS 'User ID under which the package was bound.',
	DEFAULT_SCHEMA      IS 'Default schema (QUALIFIER) name used for unqualified names in static SQL statements.',
	VALID               IS 'Y = Valid; N = Not valid; X = Package is inoperative because some function instance on which it depends has been dropped. Explicit rebind is needed.',
	UNIQUE_ID           IS 'Internal date and time information indicating when the package was first created. Useful for identifying a specific package when multiple packages having the same name exist.',
	TOTAL_SECT          IS 'Total number of sections in the package.',
	FORMAT              IS 'Date and time format associated with the package: 0 = Use format of client territory code; 1 = USA; 2 = EUR; 3 = ISO; 4 = JIS; 5 = LOCAL',
	ISOLATION           IS 'Isolation level: RR = Repeatable read; RS = Read stability; CS = Cursor stability; UR = Uncommitted read',
	BLOCKING            IS 'Cursor blocking option: N = No blocking; U = Block unambiguous cursors; B = Block all cursors',
	INSERT_BUF          IS 'Inserts are buffered during bind. (Y/N)',
	REOPTVAR            IS 'Indicates whether the access path is reoptimized at execution time using input variable values: A = Reoptimized at every OPEN or EXECUTE request; N = Not reoptimized at execute time; O = Reoptimized only at first OPEN or EXECUTE request.',
	OS_PTR_SIZE         IS 'Indicates the word size for the platform on which the package was created: 32 = Package is a 32-bit package; 64 = Package is a 64-bit package.',
	LANG_LEVEL          IS 'LANGLEVEL value used during BIND: 0 = SAA1; 1 = MIA; 2 = SQL92E',
	FUNC_PATH           IS 'The SQL path used by the last BIND command for this package. This is used as the default path for REBIND. SYSIBM for pre-Version 2 packages.',
	QUERYOPT            IS 'Optimization class under which this package was bound. Used for REBIND. The classes are: 0, 1, 3, 5 and 9.',
	EXPLAIN_LEVEL       IS 'Indicates whether Explain was requested using the EXPLAIN or EXPLSNAP bind option: P = Plan Selection level; Blank if "No" Explain requested',
	EXPLAIN_MODE        IS 'Value of EXPLAIN bind option: Y = Yes (static); N = No; A = All (static and dynamic)',
	EXPLAIN_SNAPSHOT    IS 'Value of EXPLSNAP bind option: Y = Yes (static); N = No; A = All (static and dynamic) ',
	SQLWARN             IS 'Are positive SQLCODEs resulting from dynamic SQL statements returned to the application? (Y/N)',
	SQLMATHWARN         IS 'Value of the database configuration parameter DFT_SQLMATHWARN at the time of bind. Are arithmetic errors and retrieval conversion errors in static SQL statements handled as NULLs with a warning? (Y/N)',
	EXPLICIT_BIND_TIME  IS 'The time at which this package was last explicitly bound or rebound. When the package is implicitly rebound, no function instance will be selected that was created later than this time.',
	LAST_BIND_TIME      IS 'Time at which the package last explicitly or implicitly bound or rebound.',
	CODEPAGE            IS 'Application code page at bind time (-1 if not known).',
	DEGREE              IS 'Indicates the limit on intra-partition parallelism (as a bind option) when package was bound: 1 = No intra-partition parallelism; 2-32767 = Degree of intra-partition parallelism; ANY = Degree was determined by the database manager.',
	MULTINODE_PLANS     IS 'Was package bound in a multiple partition environment? (Y/N)',
	INTRA_PARALLEL      IS 'Indicates the use of intra-partition parallelism by static SQL statements within the package. (Y/N/F=Yes, but disabled for use on a system that is not configured for intra-partition parallelism)',
	VALIDATE            IS 'B = All checking must be performed during BIND; R = Reserved',
	DYNAMICRULES        IS 'B = BIND; D = DEFINEBIND; E = DEFINERUN; H = INVOKEBIND; I = INVOKERUN; R = RUN',
	SQLERROR            IS 'Indicates SQLERROR option on the most recent subcommand that bound or rebound the package: C = Reserved; N = No package',
	REFRESHAGE          IS 'Timestamp duration indicating the maximum length of time between when a REFRESH TABLE statement is run for a materialized query table and when the materialized query table is used in place of a base table.',
	TRANSFORMGROUP      IS 'String containing the transform group bind option.',
	REMARKS             IS 'User-supplied comment, or NULL.'
);

COMMENT ON TABLE SYSCAT.PARTITIONMAPS IS 'Contains a row for each partitioning map that is used to distribute table rows among the partitions in a database partition group, based on hashing the table''s partitioning key.';
COMMENT ON SYSCAT.PARTITIONMAPS (
	PMAP_ID             IS 'Identifier of the partitioning map.',
	PARTITIONMAP        IS 'The actual partitioning map, a vector of 4096 two-byte integers for a multiple partition database partition group. For a single partition database partition group, there is one entry denoting the partition number of the single partition.'
);

COMMENT ON TABLE SYSCAT.PASSTHRUAUTH IS 'This catalog view contains information about authorizations to query data sources in pass-through sessions. A constraint on the base table requires that the values in SERVER correspond to the values in the SERVER column of @SYSCAT.SERVERS.';
COMMENT ON SYSCAT.PASSTHRUAUTH (
	GRANTOR             IS 'Authorization ID of the user who granted the privilege.',
	GRANTEE             IS 'Authorization ID of the user or group who holds the privilege.',
	GRANTEETYPE         IS 'A letter that specifies the type of grantee: U = Grantee is an individual user; G = Grantee is a group.',
	SERVERNAME          IS 'Name of the data source that the user or group is being granted authorization to.'
);

COMMENT ON TABLE SYSCAT.PREDICATESPECS IS 'Each row represents a predicate specification.';
COMMENT ON SYSCAT.PREDICATESPECS (
	FUNCSCHEMA          IS 'Qualified name of function.',
	FUNCNAME            IS 'Qualified name of function.',
	SPECIFICNAME        IS 'The name of the function instance.',
	FUNCID              IS 'Function ID.',
	SPECID              IS 'ID of this predicate specification.',
	CONTEXTOP           IS 'Comparison operator is one of the built-in relational operators (=, <, >=, and so on).',
	CONTEXTEXP          IS 'Constant, or an SQL expression.',
	FILTERTEXT          IS 'Text of data filter expression.'
);

COMMENT ON TABLE SYSCAT.PROCOPTIONS IS 'Each row contains procedure specific option values.';
COMMENT ON SYSCAT.PROCOPTIONS (
	PROCSCHEMA          IS 'Qualifier for the stored procedure name or nickname.',
	PROCNAME            IS 'Name or nickname of the stored procedure.',
	OPTION              IS 'Name of the stored procedure option.',
	SETTING             IS 'Value of the stored procedure option.'
);

COMMENT ON TABLE SYSCAT.PROCPARMOPTIONS IS 'Each row contains procedure parameter specific option values.';
COMMENT ON SYSCAT.PROCPARMOPTIONS (
	PROCSCHEMA          IS 'Qualified procedure name or nickname.',
	PROCNAME            IS 'Qualified procedure name or nickname.',
	ORDINAL             IS 'The parameter''s numerical position within the procedure signature.',
	OPTION              IS 'Name of the stored procedure parameter option.',
	SETTING             IS 'Value of the stored procedure parameter option.'
);

COMMENT ON TABLE SYSCAT.REFERENCES IS 'Contains a row for each defined referential constraint.';
COMMENT ON SYSCAT.REFERENCES (
	CONSTNAME           IS 'Name of the constraint.',
	TABSCHEMA           IS 'Qualified name of the table.',
	TABNAME             IS 'Qualified name of the table.',
	DEFINER             IS 'User who created the constraint.',
	REFKEYNAME          IS 'Name of parent key.',
	REFTABSCHEMA        IS 'Qualified name of the parent table.',
	REFTABNAME          IS 'Qualified name of the parent table.',
	COLCOUNT            IS 'Number of columns in the foreign key.',
	DELETERULE          IS 'Delete rule: A = NO ACTION; C = CASCADE; N = SET NULL; R = RESTRICT',
	UPDATERULE          IS 'Update rule: A = NO ACTION; R = RESTRICT',
	CREATE_TIME         IS 'The timestamp when the referential constraint was defined.',
	FK_COLNAMES         IS 'List of foreign key column names. DEPRECATED: Use @SYSCAT.KEYCOLUSE for this information.',
	PK_COLNAMES         IS 'List of parent key column names. DEPRECATED: Use @SYSCAT.KEYCOLUSE for this information.'
);

COMMENT ON TABLE SYSCAT.REVTYPEMAPPINGS IS 'Each row contains reverse data type mappings (mappings from data types defined locally to data source data types). No data in this version. Defined for possible future use with data type mappings.';
COMMENT ON SYSCAT.REVTYPEMAPPINGS (
	TYPE_MAPPING        IS 'Name of the reverse type mapping (may be system-generated).',
	TYPESCHEMA          IS 'Schema name of the type. NULL for system built-in types.',
	TYPENAME            IS 'Name of the local type in a reverse type mapping.',
	TYPEID              IS 'Type identifier.',
	SOURCETYPEID        IS 'Source type identifier.',
	DEFINER             IS 'Authorization ID under which this type mapping was created.',
	LOWER_LEN           IS 'Lower bound of the length/precision of the local type.',
	UPPER_LEN           IS 'Upper bound of the length/precision of the local type. If NULL then the system determines the best length/precision attribute.',
	LOWER_SCALE         IS 'Lower bound of the scale for local decimal data types.',
	UPPER_SCALE         IS 'Upper bound of the scale for local decimal data types. If NULL, then the system determines the best scale attribute.',
	S_OPR_P             IS 'Relationship between local scale and local precision. Basic comparison operators can be used. A NULL indicates that no specific relationship is required.',
	BIT_DATA            IS 'Y = Type is for bit data; N = Type is not for bit data; NULL = This is not a character data type or that the system determines the bit data attribute.',
	WRAPNAME            IS 'Mapping applies to this data access protocol.',
	SERVERNAME          IS 'Name of the data source.',
	SERVERTYPE          IS 'Mapping applies to this type of data source.',
	SERVERVERSION       IS 'Mapping applies to this version of SERVERTYPE.',
	REMOTE_TYPESCHEMA   IS 'Schema name of the remote type.',
	REMOTE_TYPENAME     IS 'Name of the data type as defined on the data source(s).',
	REMOTE_META_TYPE    IS 'S = Remote type is a system built-in type; T = Remote type is a distinct type.',
	REMOTE_LENGTH       IS 'Maximum number of digits for remote decimal type, and maximum number of characters for remote character type. Otherwise NULL.',
	REMOTE_SCALE        IS 'Maximum number of digits allowed to the right of the decimal point (for remote decimal types). Otherwise NULL.',
	REMOTE_BIT_DATA     IS 'Y = Type is for bit data; N = Type is not for bit data; NULL = This is not a character data type or that the system determines the bit data attribute.',
	USER_DEFINED        IS 'Defined by user.',
	CREATE_TIME         IS 'Time when this mapping was created.',
	REMARKS             IS 'User supplied comments, or NULL.'
);

COMMENT ON TABLE SYSCAT.ROUTINEAUTH IS 'Contains one or more rows for each user or group who is granted EXECUTE privilege on a particular routine in the database.';
COMMENT ON SYSCAT.ROUTINEAUTH (
	GRANTOR             IS 'Authorization ID of the user who granted the privilege or SYSIBM.',
	GRANTEE             IS 'Authorization ID of the user or group who holds the privilege.',
	GRANTEETYPE         IS 'U = Grantee is an individual user; G = Grantee is a group.',
	SCHEMA              IS 'Qualifier of the routine.',
	SPECIFICNAME        IS 'Specific name of the routine. If SPECIFICNAME is NULL, the privilege applies to all routines in SCHEMA (ROUTINETYPE<>M), or methods in the schema TYPESCHEMA (ROUTINETYPE=M)',
	TYPESCHEMA          IS 'Qualifier of the type name for the method. If ROUTINETYPE is not M, TYPESCHEMA is NULL.',
	TYPENAME            IS 'Type name for the method. If ROUTINETYPE is not M, TYPENAME is NULL. If TYPENAME is NULL and ROUTINETYPE is M, the privilege applies to subject types in the schema TYPESCHEMA.',
	ROUTINETYPE         IS 'Type of routine: F = Function; M = Method; P = Procedure',
	EXECUTEAUTH         IS 'Indicates whether grantee holds EXECUTE privilege on the function or method. (Y/N/G=Grantable)',
	GRANT_TIME          IS 'Time at which the EXECUTE privilege is granted.'
);

COMMENT ON TABLE SYSCAT.ROUTINEDEP IS 'Each row represents a dependency of a routine on some other object.';
COMMENT ON SYSCAT.ROUTINEDEP (
	ROUTINESCHEMA       IS 'Qualified name of the routine that has dependencies on another object.',
	ROUTINENAME         IS 'Qualified name of the routine that has dependencies on another object.',
	BTYPE               IS 'Type of object on which the routine depends. See DB2 SQL Reference for definition of values. (A/F/O/R/S/T/U/V/W/X)',
	BSCHEMA             IS 'Qualified name of the object on which the function or method depends (if BTYPE = F, this is the specific name of a routine).',
	BNAME               IS 'Qualified name of the object on which the function or method depends (if BTYPE = F, this is the specific name of a routine).',
	TABAUTH             IS 'If BTYPE = O, S, T, U, V or W, it encodes the privileges on the table or view that are required by the dependent routine. Otherwise NULL.'
);

COMMENT ON TABLE SYSCAT.ROUTINEPARMS IS 'Contains a row for every parameter or result of a routine defined in @SYSCAT.ROUTINES.';
COMMENT ON SYSCAT.ROUTINEPARMS (
	ROUTINESCHEMA       IS 'Qualified routine name.',
	ROUTINENAME         IS 'Qualified routine name.',
	SPECIFICNAME        IS 'The name of the routine instance (may be system-generated).',
	PARMNAME            IS 'Name of parameter or result column, or NULL if no name exists.',
	ROWTYPE             IS 'B = Both input and output parameter; C = Result after casting; O = Output parameter; P = Input parameter; R = Result before casting ',
	ORDINAL             IS 'If ROWTYPE = B, O, or P, the parameter''s numerical position within the routine signature. If ROWTYPE = R, and the routine is a table function, the column''s numerical position within the result table. Otherwise 0.',
	TYPESCHEMA          IS 'Qualified name of data type of parameter or result.',
	TYPENAME            IS 'Qualified name of data type of parameter or result.',
	LOCATOR             IS 'Parameter or result is passed in the form of a locator. (Y/N)',
	LENGTH              IS 'Length of parameter or result. 0 if parameter or result is a distinct type. See Note 1.',
	SCALE               IS 'Scale of parameter or result. 0 if parameter or result is a distinct type. See Note 1.',
	CODEPAGE            IS 'Code page of parameter or result. 0 denotes either not applicable, or a parameter or result for character data declared with the FOR BIT DATA attribute.',
	CAST_FUNCSCHEMA     IS 'Qualified name of the function used to cast an argument or a result. Applies to sourced and external functions; NULL otherwise.',
	CAST_FUNCSPECIFIC   IS 'Qualified name of the function used to cast an argument or a result. Applies to sourced and external functions; NULL otherwise.',
	TARGET_TYPESCHEMA   IS 'Qualified name of the target type, if the type of the parameter or result is REFERENCE. NULL value if the type of the parameter or result is not REFERENCE.',
	TARGET_TYPENAME     IS 'Qualified name of the target type, if the type of the parameter or result is REFERENCE. NULL value if the type of the parameter or result is not REFERENCE.',
	SCOPE_TABSCHEMA     IS 'Qualified name of the scope (target table), if the type of the parameter or result is REFERENCE. NULL value if the type of the parameter or result is not REFERENCE, or the scope is not defined.',
	SCOPE_TABNAME       IS 'Qualified name of the scope (target table), if the type of the parameter or result is REFERENCE. NULL value if the type of the parameter or result is not REFERENCE, or the scope is not defined.',
	TRANSFORMGRPNAME    IS 'Name of transform group for a structured type parameter or result.',
	REMARKS             IS 'Parameter remarks.'
);

COMMENT ON TABLE SYSCAT.ROUTINES IS 'Contains a row for each user-defined function (scalar, table, or source), system-generated method, user-defined method, or procedure. Does not include built-in functions.';
COMMENT ON SYSCAT.ROUTINES (
	ROUTINESCHEMA       IS 'Qualified routine name.',
	ROUTINENAME         IS 'Qualified routine name.',
	ROUTINETYPE         IS 'F = Function; M = Method; P = Procedure.',
	DEFINER             IS 'Authorization ID of routine definer.',
	SPECIFICNAME        IS 'The name of the routine instance (may be system-generated).',
	ROUTINEID           IS 'Internally-assigned routine ID.',
	RETURN_TYPESCHEMA   IS 'Qualified name of the return type for a scalar function or method.',
	RETURN_TYPENAME     IS 'Qualified name of the return type for a scalar function or method.',
	ORIGIN              IS 'B = Built-in; E = User-defined, external; M = Template; Q = SQL-bodied; U = User-defined, based on a source; S = System-generated; T = System-generated transform',
	FUNCTIONTYPE        IS 'C = Column function; R = Row function; S = Scalar function or method; T = Table function; Blank = Procedure ',
	PARM_COUNT          IS 'Number of parameters.',
	LANGUAGE            IS 'Implementation language of routine body. Possible values are C, COBOL, JAVA, OLE, OLEDB, or SQL. Blank if ORIGIN is not E or Q.',
	SOURCESCHEMA        IS 'If ORIGIN = U and the routine is a user-defined function, contains the qualified name of the source function. If ORIGIN = U and the source function is built-in, SOURCESCHEMA is ''SYSIBM'' and SOURCESPECIFIC is ''N/A for built-in''. NULL if ORIGIN is not U.',
	SOURCESPECIFIC      IS 'If ORIGIN = U and the routine is a user-defined function, contains the qualified name of the source function. If ORIGIN = U and the source function is built-in, SOURCESCHEMA is ''SYSIBM'' and SOURCESPECIFIC is ''N/A for built-in''. NULL if ORIGIN is not U.',
	DETERMINISTIC       IS 'Y = Deterministic (results are consistent for the same inputs); N = Non-deterministic (results may differ); Blank if ORIGIN is not E or Q.',
	EXTERNAL_ACTION     IS 'E = Function has external side-effects (number of invocations is important); N = No side-effects; Blank if ORIGIN is not E or Q.',
	NULLCALL            IS 'Y = CALLED ON NULL INPUT; N = RETURNS NULL ON NULL INPUT (result is implicitly NULL if operand(s) are NULL); Blank if ORIGIN is not E or Q.',
	CAST_FUNCTION       IS 'The function is a CAST function. (Y/N)',
	ASSIGN_FUNCTION     IS 'The function is an implicit assignment function. (Y/N)',
	SCRATCHPAD          IS 'Y = This routine has a scratch pad; N = This routine does not have a scratch pad; Blank if ORIGIN is not E or ROUTINETYPE is P.',
	SCRATCHPAD_LENGTH   IS '/n/ = Length of the scratch pad in bytes; 0 = SCRATCHPAD is N; -1 = LANGUAGE is OLEDB',
	FINALCALL           IS 'Y = Final call is made to this function at runtime end-of-statement; N = No final call is made; Blank if ORIGIN is not E.',
	PARALLEL            IS 'Y = Function can be executed in parallel; N = Function cannot be executed in parallel; Blank if ORIGIN is not E.',
	PARAMETER_STYLE     IS 'Indicates the parameter style declared when the routine was created. DB2SQL; SQL; DB2GENRL; GENERAL; JAVA; DB2DARI; GNRLNULL; Blank if ORIGIN is not E.',
	FENCED              IS 'Y = Fenced; N = Not fenced; Blank if ORIGIN is not E. ',
	SQL_DATA_ACCESS     IS 'C = CONTAINS SQL: only SQL that does not read or modify SQL data is allowed; M = MODIFIES SQL DATA: all SQL allowed in routines is allowed; N = NO SQL: SQL is not allowed; R = READS SQL DATA: only SQL that reads SQL data is allowed.',
	DBINFO              IS 'DBINFO is passed. (Y/N)',
	PROGRAMTYPE         IS 'M = Main; S = Subroutine',
	COMMIT_ON_RETURN    IS 'N = Changes are not committed after the procedure completes; Blank if ROUTINETYPE is not P.',
	RESULT_SETS         IS 'Estimated upper limit of returned result sets.',
	SPEC_REG            IS 'I = INHERIT SPECIAL REGISTERS: special registers start with their values from the invoking statement; Blank if ORIGIN is not E or Q.',
	FEDERATED           IS 'Not used.',
	THREADSAFE          IS 'Y = Routine can run in the same process as other routines; N = Routine must be run in a separate process from other routines; Blank if ORIGIN is not E.',
	VALID               IS 'Y = SQL procedure is valid; N = SQL procedure is invalid; X = SQL procedure is inoperative because some object it requires has been dropped. The SQL procedure must be explicitly dropped and recreated; Blank if ORIGIN is not Q.',
	METHODIMPLEMENTED   IS 'Y = Method is implemented; N = Method specification without an implementation; Blank if ROUTINETYPE is not M.',
	METHODEFFECT        IS 'MU = Mutator method; OB = Observer method; CN = Constructor method; Blank if FUNCTIONTYPE is not T.',
	TYPE_PRESERVING     IS 'Y = Return type is governed by a "type-preserving" parameter. All system-generated mutator methods are type-preserving; N = Return type is the declared return type of the method; Blank if ROUTINETYPE is not M.',
	WITH_FUNC_ACCESS    IS 'Y = This method can be invoked by using functional notation; N = This method cannot be invoked by using functional notation; Blank if ROUTINETYPE is not M.',
	OVERRIDDEN_METHODID IS 'Reserved for future use.',
	SUBJECT_TYPESCHEMA  IS 'Subject type for method.',
	SUBJECT_TYPENAME    IS 'Subject type for method.',
	CLASS               IS 'If LANGUAGE = JAVA, identifies the class that implements this routine. NULL otherwise.',
	JAR_ID              IS 'If LANGUAGE = JAVA, identifies the jar file that implements this routine. NULL otherwise.',
	JARSCHEMA           IS 'If LANGUAGE = JAVA, identifies the schema of the jar file that implements this routine. NULL otherwise.',
	JAR_SIGNATURE       IS 'If LANGUAGE = JAVA, identifies the signature of the Java method that implements this routine. NULL otherwise.',
	CREATE_TIME         IS 'Timestamp of routine creation. Set to 0 for Version 1 functions.',
	ALTER_TIME          IS 'Timestamp of most recent routine alteration. If the routine has not been altered, set to CREATE_TIME.',
	FUNC_PATH           IS 'SQL path at the time the routine was defined.',
	QUALIFIER           IS 'Value of default schema at object definition time.',
	IOS_PER_INVOC       IS 'Estimated number of I/Os per invocation; -1 if not known (0 default).',
	INSTS_PER_INVOC     IS 'Estimated number of instructions per invocation; -1 if not known (450 default).',
	IOS_PER_ARGBYTE     IS 'Estimated number of I/Os per input argument byte; -1 if not known (0 default).',
	INSTS_PER_ARGBYTE   IS 'Estimated number of instructions per input argument byte; -1 if not known (0 default).',
	PERCENT_ARGBYTES    IS 'Estimated average percent of input argument bytes that the routine will actually read; -1 if not known (100 default).',
	INITIAL_IOS         IS 'Estimated number of I/Os performed the first/last time the routine is invoked; -1 if not known (0 default).',
	INITIAL_INSTS       IS 'Estimated number of instructions executed the first/last time the routine is invoked; -1 if not known (0 default).',
	CARDINALITY         IS 'The predicted cardinality of a table function; -1 if not known, or if the routine is not a table function.',
	SELECTIVITY         IS 'Used for user-defined predicates; -1 if there are no user-defined predicates.',
	RESULT_COLS         IS 'For a table function (ROUTINETYPE = F and TYPE = T) contains the number of columns in the result table. For other functions and methods (ROUTINETYPE = F or M), contains 1. For procedures (ROUTINETYPE = P), contains 0.',
	IMPLEMENTATION      IS 'If ORIGIN = E, identifies the path/module/function that implements this function. If ORIGIN = U and the source function is built-in, this column contains the name and signature of the source function. NULL otherwise.',
	LIB_ID              IS 'Reserved for future use.',
	TEXT_BODY_OFFSET    IS 'If LANGUAGE = SQL, the offset to the start of the SQL procedure body in the full text of the CREATE statement; -1 if LANGUAGE is not SQL.',
	TEXT                IS 'If LANGUAGE = SQL, the text of the CREATE FUNCTION, CREATE METHOD, or CREATE PROCEDURE statement.',
	NEWSAVEPOINTLEVEL   IS 'Indicates whether the routine initiates a new savepoint level when it is invoked. (Y/N/Blank if ORIGIN is not E or Q)',
	DEBUG_MODE          IS 'Debugging is active for this routine. (ON/OFF)',
	TRACE_LEVEL         IS 'Reserved for future use.',
	DIAGNOSTIC_LEVEL    IS 'Reserved for future use.',
	CHECKOUT_USERID     IS 'User ID of the user who performed a checkout of the object. NULL if not checked out.',
	PRECOMPILE_OPTIONS  IS 'Precompile options specified for the routine.',
	COMPILE_OPTIONS     IS 'Compile options specified for the routine.',
	REMARKS             IS 'User-supplied comment, or NULL.'
);

COMMENT ON TABLE SYSCAT.SCHEMAAUTH IS 'Contains one or more rows for each user or group who is granted a privilege on a particular schema in the database. All schema privileges for a single schema granted by a specific grantor to a specific grantee appear in a single row.';
COMMENT ON SYSCAT.SCHEMAAUTH (
	GRANTOR             IS 'Authorization ID of the user who granted the privileges or SYSIBM.',
	GRANTEE             IS 'Authorization ID of the user or group who holds the privileges.',
	GRANTEETYPE         IS 'U = Grantee is an individual user; G = Grantee is a group.',
	SCHEMANAME          IS 'Name of the schema.',
	ALTERINAUTH         IS 'Indicates whether grantee holds ALTERIN privilege on the schema. (Y/N/G=Grantable)',
	CREATEINAUTH        IS 'Indicates whether grantee holds CREATEIN privilege on the schema. (Y/N/G=Grantable)',
	DROPINAUTH          IS 'Indicates whether grantee holds DROPIN privilege on the schema. (Y/N/G=Grantable)'
);

COMMENT ON TABLE SYSCAT.SCHEMATA IS 'Contains a row for each schema.';
COMMENT ON SYSCAT.SCHEMATA (
	SCHEMANAME          IS 'Name of the schema.',
	OWNER               IS 'Authorization id of the schema. The value for implicitly created schemas is SYSIBM.',
	DEFINER             IS 'User who created the schema.',
	CREATE_TIME         IS 'Timestamp indicating when the object was created.',
	REMARKS             IS 'User-provided comment.'
);

COMMENT ON TABLE SYSCAT.SEQUENCEAUTH IS 'Contains a row for each authorization ID that can be used to use or to alter a sequence.';
COMMENT ON SYSCAT.SEQUENCEAUTH (
	GRANTOR             IS 'SYSIBM or authorization ID that granted the privilege.',
	GRANTEE             IS 'Authorization ID that holds the privilege.',
	GRANTEETYPE         IS 'U = grantee is an individual user ',
	SEQSCHEMA           IS 'Qualified name of the sequence.',
	SEQNAME             IS 'Qualified name of the sequence.',
	USAGEAUTH           IS 'Indicates whether grantee can use the sequence. (Y/N/G=Grantable)',
	ALTERAUTH           IS 'Indicates whether grantee can alter the sequence. (Y/N/G=Grantable)'
);

COMMENT ON TABLE SYSCAT.SEQUENCES IS 'Contains a row for each sequence or identity column defined in the database.';
COMMENT ON SYSCAT.SEQUENCES (
	SEQSCHEMA           IS 'Qualified name of the sequence (generated by DB2 for an identity column).',
	SEQNAME             IS 'Qualified name of the sequence (generated by DB2 for an identity column).',
	DEFINER             IS 'Definer of the sequence.',
	OWNER               IS 'Owner of the sequence.',
	SEQID               IS 'Internal ID of the sequence.',
	SEQTYPE             IS 'Sequence type: S = Regular sequence; I = Identity sequence',
	INCREMENT           IS 'Increment value.',
	START               IS 'Starting value.',
	MAXVALUE            IS 'Maximal value.',
	MINVALUE            IS 'Minimum value.',
	CYCLE               IS 'Whether cycling will occur when a boundary is reached. (Y/N)',
	CACHE               IS 'Number of sequence values to preallocate in memory for faster access. 0 indicates that values are not preallocated.',
	ORDER               IS 'Whether or not the sequence numbers must be generated in order of request. (Y/N)',
	DATATYPEID          IS 'For built-in types, the internal ID of the built-in type. For distinct types, the internal ID of the distinct type.',
	SOURCETYPEID        IS 'For a built-in type, this has a value of 0. For a distinct type, this is the internal ID of the built-in type that is the source type for the distinct type.',
	CREATE_TIME         IS 'Time when the sequence was created.',
	ALTER_TIME          IS 'Time when the last ALTER SEQUENCE statement was executed for this sequence.',
	PRECISION           IS 'The precision of the data type of the sequence. Values are: 5 for a SMALLINT, 10 for INTEGER, and 19 for BIGINT. For DECIMAL, it is the precision of the specified DECIMAL data type.',
	ORIGIN              IS 'Sequence Origin: U = User generated sequence; S = System generated sequence',
	REMARKS             IS 'User supplied comments, or NULL.'
);

COMMENT ON TABLE SYSCAT.SERVEROPTIONS IS 'Each row contains configuration options at the server level.';
COMMENT ON SYSCAT.SERVEROPTIONS (
	WRAPNAME            IS 'Wrapper name.',
	SERVERNAME          IS 'Name of the server.',
	SERVERTYPE          IS 'Server type.',
	SERVERVERSION       IS 'Server version.',
	CREATE_TIME         IS 'Time when entry is created.',
	OPTION              IS 'Name of the server option.',
	SETTING             IS 'Value of the server option.',
	SERVEROPTIONKEY     IS 'Uniquely identifies a row.',
	REMARKS             IS 'User supplied comments, or NULL.'
);

COMMENT ON TABLE SYSCAT.SERVERS IS 'Each row represents a data source. Catalog entries are not necessary for tables that are stored in the same instance that contains this catalog table.';
COMMENT ON SYSCAT.SERVERS (
	WRAPNAME            IS 'Wrapper name.',
	SERVERNAME          IS 'Name of data source as it is known to the system.',
	SERVERTYPE          IS 'Type of data source (always uppercase).',
	SERVERVERSION       IS 'Version of data source.',
	REMARKS             IS 'User supplied comments, or NULL.'
);

COMMENT ON TABLE SYSCAT.STATEMENTS IS 'Contains one or more rows for each SQL statement in each package in the database.';
COMMENT ON SYSCAT.STATEMENTS (
	PKGSCHEMA           IS 'Name of the package.',
	PKGNAME             IS 'Name of the package.',
	UNIQUE_ID           IS 'Internal date and time information indicating when the package was first created. Useful for identifying a specific package when multiple packages having the same name exist.',
	STMTNO              IS 'Line number of the SQL statement in the source module of the application program.',
	SECTNO              IS 'Number of the package section containing the SQL statement.',
	SEQNO               IS 'Always 1.',
	TEXT                IS 'Text of the SQL statement.',
	VERSION             IS 'Version identifier of the package.'
);

COMMENT ON TABLE SYSCAT.TABAUTH IS 'Contains one or more rows for each user or group who is granted a privilege on a particular table or view in the database. All the table privileges for a single table or view granted by a specific grantor to a specific grantee appear in a single row.';
COMMENT ON SYSCAT.TABAUTH (
	GRANTOR             IS 'Authorization ID of the user who granted the privileges or SYSIBM.',
	GRANTEE             IS 'Authorization ID of the user or group who holds the privileges.',
	GRANTEETYPE         IS 'U = Grantee is an individual user; G = Grantee is a group.',
	TABSCHEMA           IS 'Qualified name of the table or view.',
	TABNAME             IS 'Qualified name of the table or view.',
	CONTROLAUTH         IS 'Indicates whether grantee holds CONTROL privilege on the table or view. (Y/N)',
	ALTERAUTH           IS 'Indicates whether grantee holds ALTER privilege on the table. (Y/N/G=Grantable)',
	DELETEAUTH          IS 'Indicates whether grantee holds DELETE privilege on the table or view. (Y/N/G=Grantable)',
	INDEXAUTH           IS 'Indicates whether grantee holds INDEX privilege on the table. (Y/N/G=Grantable)',
	INSERTAUTH          IS 'Indicates whether grantee holds INSERT privilege on the table or view. (Y/N/G=Grantable)',
	SELECTAUTH          IS 'Indicates whether grantee holds SELECT privilege on the table or view. (Y/N/G=Grantable)',
	REFAUTH             IS 'Indicates whether grantee holds REFERENCE privilege on the table or view. (Y/N/G=Grantable)',
	UPDATEAUTH          IS 'Indicates whether grantee holds UPDATE privilege on the table or view. (Y/N/G=Grantable)'
);

COMMENT ON TABLE SYSCAT.TABCONST IS 'Each row represents a table constraint of type CHECK, UNIQUE, PRIMARY KEY, or FOREIGN KEY.';
COMMENT ON SYSCAT.TABCONST (
	CONSTNAME           IS 'Name of the constraint (unique within a table).',
	TABSCHEMA           IS 'Qualified name of the table to which this constraint applies.',
	TABNAME             IS 'Qualified name of the table to which this constraint applies.',
	DEFINER             IS 'Authorization ID under which the constraint was defined.',
	TYPE                IS 'Indicates the constraint type: F = Foreign key; I = Functional dependency; K = Check; P = Primary key; U = Unique',
	REMARKS             IS 'User-supplied comment, or NULL.',
	ENFORCED            IS 'Is the constraint enforced by the database? (Y/N)',
	CHECKEXISTINGDATA   IS 'D = Defer checking of existing data; I = Immediately check existing data; N = Never check existing data',
	ENABLEQUERYOPT      IS 'Query optimization is enabled? (Y/N)'
);

COMMENT ON TABLE SYSCAT.TABDEP IS 'Contains a row for every dependency of a view or a materialized query table on some other object. Also encodes how privileges on this view depend on privileges on underlying tables and views.';
COMMENT ON SYSCAT.TABDEP (
	TABSCHEMA           IS 'Name of the view or materialized query table with dependencies on a base table.',
	TABNAME             IS 'Name of the view or materialized query table with dependencies on a base table.',
	DTYPE               IS 'S = Materialized query table; V = View (untyped); W = Typed view',
	DEFINER             IS 'Authorization ID of the creator of the view.',
	BTYPE               IS 'Type of object BNAME. See DB2 SQL Reference for definition of values. (A/F/N/O/I/R/S/T/U/V/W)',
	BSCHEMA             IS 'Qualified name of the object on which the view depends.',
	BNAME               IS 'Qualified name of the object on which the view depends.',
	TABAUTH             IS 'If BTYPE = N, O, S, T, U, V, W, encodes the privileges on the underlying table or view on which this table depends. Otherwise NULL.'
);

COMMENT ON TABLE SYSCAT.TABLES IS 'Contains one row for each table, view, nickname or alias that is created. All of the catalog tables and views have entries in the @SYSCAT.TABLES catalog view.';
COMMENT ON SYSCAT.TABLES (
	TABSCHEMA           IS 'Qualified name of the table, view, nickname, or alias.',
	TABNAME             IS 'Qualified name of the table, view, nickname, or alias.',
	DEFINER             IS 'User who created the table, view, nickname or alias.',
	TYPE                IS 'The type of object: A = Alias; H = Hierarchy table; N = Nickname; S = Materialized query table; T = Table; U = Typed table; V = View; W = Typed view',
	STATUS              IS 'The check pending status of the object: N = Normal table, view, alias or nickname; C = Check pending on table or nickname; X = Inoperative view or nickname',
	DROPRULE            IS 'N = No rule; R = Restrict rule applies on drop',
	BASE_TABSCHEMA      IS 'If TYPE = A, these columns identify the table, view, alias, or nickname that is referenced by this alias; otherwise they are NULL.',
	BASE_TABNAME        IS 'If TYPE = A, these columns identify the table, view, alias, or nickname that is referenced by this alias; otherwise they are NULL.',
	ROWTYPESCHEMA       IS 'Contains the qualified name of the rowtype of this table, where applicable. NULL otherwise.',
	ROWTYPENAME         IS 'Contains the qualified name of the rowtype of this table, where applicable. NULL otherwise.',
	CREATE_TIME         IS 'The timestamp indicating when the object was created.',
	STATS_TIME          IS 'Last time when any change was made to recorded statistics for this table. NULL if no statistics available.',
	COLCOUNT            IS 'Number of columns in the table.',
	TABLEID             IS 'Internal table identifier.',
	TBSPACEID           IS 'Internal identifier of primary table space for this table.',
	CARD                IS 'Total number of rows in the table. For tables in a table hierarchy, the number of rows at the given level of the hierarchy; -1 if statistics are not gathered, or the row describes a view or alias; -2 for hierarchy tables (H-tables).',
	NPAGES              IS 'Total number of pages on which the rows of the table exist; -1 if statistics are not gathered, or the row describes a view or alias; -2 for subtables or H-tables.',
	FPAGES              IS 'Total number of pages; -1 if statistics are not gathered, or the row describes a view or alias; -2 for subtables or H-tables.',
	OVERFLOW            IS 'Total number of overflow records in the table; -1 if statistics are not gathered, or the row describes a view or alias; -2 for subtables or H-tables.',
	TBSPACE             IS 'Name of primary table space for the table. If no other table space is specified, all parts of the table are stored in this table space. NULL for aliases and views.',
	INDEX_TBSPACE       IS 'Name of table space that holds all indexes created on this table. NULL for aliases and views, or if the INDEX IN clause was omitted or specified with the same value as the IN clause of the CREATE TABLE statement.',
	LONG_TBSPACE        IS 'Name of table space that holds all long data (LONG or LOB column types) for this table. NULL for aliases and views, or if the LONG IN clause was omitted or specified with the same value as the IN clause of the CREATE TABLE statement.',
	PARENTS             IS 'Number of parent tables of this table (the number of referential constraints in which this table is a dependent).',
	CHILDREN            IS 'Number of dependent tables of this table (the number of referential constraints in which this table is a parent).',
	SELFREFS            IS 'Number of self-referencing referential constraints for this table (the number of referential constraints in which this table is both a parent and a dependent).',
	KEYCOLUMNS          IS 'Number of columns in the primary key of the table.',
	KEYINDEXID          IS 'Index ID of the primary index. This field is NULL or 0 if there is no primary key.',
	KEYUNIQUE           IS 'Number of unique constraints (other than primary key) defined on this table.',
	CHECKCOUNT          IS 'Number of check constraints defined on this table.',
	DATACAPTURE         IS 'Y = Table participates in data replication; N = Does not participate; L = Table participates in data replication, including replication of LONG VARCHAR and LONG VARGRAPHIC columns',
	CONST_CHECKED       IS 'Bitmap of Y/U/N/W/F values indicating the status of constraint checking on the table. See DB2 SQL Reference for more information and definition of values.',
	PMAP_ID             IS 'Identifier of the partitioning map used by this table. NULL for aliases and views.',
	PARTITION_MODE      IS 'Mode used for tables in a partitioned database: H = Hash on the partitioning key; R = Table replicated across database partitions; Blank for aliases, views and tables in single partition database partition groups with no partitioning key defined.',
	LOG_ATTRIBUTE       IS '0 = Default logging; 1 = Table created not logged initially',
	PCTFREE             IS 'Percentage of each page to be reserved for future inserts. Can be changed by ALTER TABLE.',
	APPEND_MODE         IS 'Controls how rows are inserted on pages: N = New rows are inserted into existing spaces if available; Y = New rows are appended at end of data',
	REFRESH             IS 'Refresh mode: D = Deferred; I = Immediate; O = Once; Blank if not a materialized query table',
	REFRESH_TIME        IS 'For REFRESH = D or O, timestamp of the REFRESH TABLE statement that last refreshed the data. Otherwise NULL.',
	LOCKSIZE            IS 'Indicates preferred lock granularity for tables when accessed by DML statements. Only applies to tables. Possible values are: R = Row; T = Table; Blank if not applicable',
	VOLATILE            IS 'C = Cardinality of the table is volatile; Blank if not applicable',
	ROW_FORMAT          IS 'Not used.',
	PROPERTY            IS 'Properties for the table. A single blank indicates that the table has no properties.',
	STATISTICS_PROFILE  IS 'RUNSTATS command used to register a statistical profile of the table.',
	COMPRESSION         IS 'V = Value compression is activated, and a row format that supports compression is used; N = No compression. A row format that does not support compression is used',
	ACCESS_MODE         IS 'Access mode of the object. This access mode is used in conjunction with the STATUS field to represent one of four states. Possible values are: N = No access (STATUS=C); R = Read-only (STATUS=C); D = No data movement (STATUS=N); F = Full access (STATUS=N)',
	CLUSTERED           IS 'Y = multi-dimensional clustering (MDC) table; NULL for a non-MDC table',
	ACTIVE_BLOCKS       IS 'Total number of in-use blocks in an MDC table; -1 if statistics are not gathered.',
	MAXFREESPACESEARCH  IS 'Reserved for future use.',
	REMARKS             IS 'User-provided comment.'
);

COMMENT ON TABLE SYSCAT.TABLESPACES IS 'Contains a row for each table space.';
COMMENT ON SYSCAT.TABLESPACES (
	TBSPACE             IS 'Name of the table space.',
	DEFINER             IS 'Authorization ID of the table space definer.',
	CREATE_TIME         IS 'Creation time of the table space.',
	TBSPACEID           IS 'Internal table space identifier.',
	TBSPACETYPE         IS 'The type of table space: S = System managed space; D = Database managed space',
	DATATYPE            IS 'The type of data that can be stored: A = All types of permanent data; L = Large data - long data or index data; T = System temporary tables only; U = Declared temporary tables only',
	EXTENTSIZE          IS 'Size of extent, in pages of size PAGESIZE. This many pages are written to one container in the table space before switching to the next container.',
	PREFETCHSIZE        IS 'Number of pages of size PAGESIZE to be read when prefetch is performed; -1 if prefetch size is AUTOMATIC.',
	OVERHEAD            IS 'Controller overhead and disk seek and latency time, in milliseconds.',
	TRANSFERRATE        IS 'Time to read one page of size PAGESIZE into the buffer.',
	PAGESIZE            IS 'Size (in bytes) of pages in the table space.',
	DBPGNAME            IS 'Name of the database partition group for the table space.',
	BUFFERPOOLID        IS 'ID of buffer pool used by this table space; 1 indicates the default buffer pool.',
	DROP_RECOVERY       IS 'Table is recoverable after a DROP TABLE statement? (Y/N)',
	REMARKS             IS 'User-provided comment.'
);

COMMENT ON TABLE SYSCAT.TABOPTIONS IS 'Each row contains option associated with a remote table.';
COMMENT ON SYSCAT.TABOPTIONS (
	TABSCHEMA           IS 'Qualified name of table, view, alias or nickname.',
	TABNAME             IS 'Qualified name of table, view, alias or nickname.',
	OPTION              IS 'Name of the table, view, alias or nickname option.',
	SETTING             IS 'Value.'
);

COMMENT ON TABLE SYSCAT.TBSPACEAUTH IS 'Contains one row for each user or group who is granted USE privilege on a particular table space in the database.';
COMMENT ON SYSCAT.TBSPACEAUTH (
	GRANTOR             IS 'Authorization ID of the user who granted the privileges or SYSIBM.',
	GRANTEE             IS 'Authorization ID of the user or group who holds the privileges.',
	GRANTEETYPE         IS 'U = Grantee is an individual user; G = Grantee is a group.',
	TBSPACE             IS 'Name of the table space.',
	USEAUTH             IS 'Indicates whether grantee holds USE privilege on the table space. (Y/N/G=Grantable)'
);

COMMENT ON TABLE SYSCAT.TRANSFORMS IS 'Contains a row for each transform function type within a user-defined type contained in a named transform group.';
COMMENT ON SYSCAT.TRANSFORMS (
	TYPEID              IS 'Internal type ID as defined in @SYSCAT.DATATYPES',
	TYPESCHEMA          IS 'Qualified name of the given user-defined structured type.',
	TYPENAME            IS 'Qualified name of the given user-defined structured type.',
	GROUPNAME           IS 'Transform group name.',
	FUNCID              IS 'Internal routine ID for the associated transform function, as defined in @SYSCAT.ROUTINES. NULL only for internal system functions.',
	FUNCSCHEMA          IS 'Qualified name of the associated transform functions.',
	FUNCNAME            IS 'Qualified name of the associated transform functions.',
	SPECIFICNAME        IS 'Function specific (instance) name.',
	TRANSFORMTYPE       IS 'FROM SQL = Transform function transforms a structured type from SQL; TO SQL = Transform function transforms a structured type to SQL',
	FORMAT              IS 'U = User defined ',
	MAXLENGTH           IS 'Maximum length (in bytes) of output from the FROM SQL transform. NULL for TO SQL transforms.',
	ORIGIN              IS 'O = Original transform group (user- or system-defined); R = Redefined',
	REMARKS             IS 'User-supplied comment or NULL.'
);

COMMENT ON TABLE SYSCAT.TRIGDEP IS 'Contains a row for every dependency of a trigger on some other object.';
COMMENT ON SYSCAT.TRIGDEP (
	TRIGSCHEMA          IS 'Qualified name of the trigger.',
	TRIGNAME            IS 'Qualified name of the trigger.',
	BTYPE               IS 'Type of object BNAME: A = Alias; B = Trigger; F = Function instance; N = Nickname; O = Privilege dependency; R = Structured type; S = Materialized query table; T = Table; U = Typed table; V = View; W = Typed view; X = Index extension',
	BSCHEMA             IS 'Qualified name of object depended on by a trigger.',
	BNAME               IS 'Qualified name of object depended on by a trigger.',
	TABAUTH             IS 'If BTYPE= O, S, T, U, V or W encodes the privileges on the table or view that are required by this trigger; otherwise NULL.'
);

COMMENT ON TABLE SYSCAT.TRIGGERS IS 'Contains one row for each trigger. For table hierarchies, each trigger is recorded only at the level of the hierarchy where it was created.';
COMMENT ON SYSCAT.TRIGGERS (
	TRIGSCHEMA          IS 'Qualified name of the trigger.',
	TRIGNAME            IS 'Qualified name of the trigger.',
	DEFINER             IS 'Authorization ID under which the trigger was defined.',
	TABSCHEMA           IS 'Qualified name of the table or view to which this trigger applies.',
	TABNAME             IS 'Qualified name of the table or view to which this trigger applies.',
	TRIGTIME            IS 'Time when triggered actions are applied to the base table, relative to the event that fired the trigger: A = Trigger applied after event; B = Trigger applied before event; I = Trigger applied instead of event',
	TRIGEVENT           IS 'Event that fires the trigger: I = Insert; D = Delete; U = Update',
	GRANULARITY         IS 'Trigger is executed once per: S = Statement; R = Row',
	VALID               IS 'Y = Trigger is valid; X = Trigger is inoperative; must be re-created.',
	CREATE_TIME         IS 'Time at which the trigger was defined. Used in resolving functions and types.',
	QUALIFIER           IS 'Contains value of the default schema at the time of object definition.',
	FUNC_PATH           IS 'Function path at the time the trigger was defined. Used in resolving functions and types.',
	TEXT                IS 'The full text of the CREATE TRIGGER statement, exactly as typed.',
	REMARKS             IS 'User-supplied comment, or NULL.'
);

COMMENT ON TABLE SYSCAT.TYPEMAPPINGS IS 'Each row contains a user-defined mapping of a remote built-in data type to a local built-in data type.';
COMMENT ON SYSCAT.TYPEMAPPINGS (
	TYPE_MAPPING        IS 'Name of the type mapping (may be system-generated).',
	TYPESCHEMA          IS 'Schema name of the type. NULL for system built-in types.',
	TYPENAME            IS 'Name of the local type in a data type mapping.',
	TYPEID              IS 'Type identifier.',
	SOURCETYPEID        IS 'Source type identifier.',
	DEFINER             IS 'Authorization ID under which this type mapping was created.',
	LENGTH              IS 'Maximum length or precision of the data type. If NULL, the system determines the best length/precision.',
	SCALE               IS 'Scale for DECIMAL fields. If NULL, the system determines the best scale attribute.',
	BIT_DATA            IS 'Y = Type is for bit data; N = Type is not for bit data; NULL = This is not a character data type or that the system determines the bit data attribute.',
	WRAPNAME            IS 'Mapping applies to this wrapper.',
	SERVERNAME          IS 'Name of the data source.',
	SERVERTYPE          IS 'Mapping applies to this type of data source.',
	SERVERVERSION       IS 'Mapping applies to this version of data source with type specified in SERVERTYPE.',
	REMOTE_TYPESCHEMA   IS 'Schema name of the remote type.',
	REMOTE_TYPENAME     IS 'Name of the data type as defined on the data source(s).',
	REMOTE_META_TYPE    IS 'S = Remote type is a system built-in type; T = Remote type is a distinct type.',
	REMOTE_LOWER_LEN    IS 'Lower bound of the length or precision of the remote decimal type. For character data types, indicates the number of characters. -1 indicates that the default length or precision is used, or that the remote type does not have a length or precision.',
	REMOTE_UPPER_LEN    IS 'Upper bound of the length or precision of the remote decimal type. For character data types, indicates the number of characters. -1 indicates that the default length or precision is used, or that the remote type does not have a length or precision.',
	REMOTE_LOWER_SCALE  IS 'Lower bound of the scale of the remote type.',
	REMOTE_UPPER_SCALE  IS 'Upper bound of the scale of the remote type.',
	REMOTE_S_OPR_P      IS 'Relationship between remote scale and remote precision. Basic comparison operators can be used. A NULL value indicates that no specific relationship is required.',
	REMOTE_BIT_DATA     IS 'Y = Type is for bit data; N = Type is not for bit data; NULL = This is not a character data type, or the system will determine the bit data attribute.',
	USER_DEFINED        IS 'Definition supplied by user.',
	CREATE_TIME         IS 'Time at which this mapping was created.',
	REMARKS             IS 'User supplied comments, or NULL.'
);

COMMENT ON TABLE SYSCAT.USEROPTIONS IS 'Each row contains server specific option values.';
COMMENT ON SYSCAT.USEROPTIONS (
	AUTHID              IS 'Local authorization ID (always uppercase)',
	SERVERNAME          IS 'Name of the server for which the user is defined.',
	OPTION              IS 'Name of the user options.',
	SETTING             IS 'Value.'
);

COMMENT ON TABLE SYSCAT.VIEWS IS 'Contains one or more rows for each view that is created.';
COMMENT ON SYSCAT.VIEWS (
	VIEWSCHEMA          IS 'Qualified name of a view or the qualified name of a table that is used to define a materialized query table or a staging table.',
	VIEWNAME            IS 'Qualified name of a view or the qualified name of a table that is used to define a materialized query table or a staging table.',
	DEFINER             IS 'Authorization ID of the creator of the view.',
	SEQNO               IS 'Always 1.',
	VIEWCHECK           IS 'States the type of view checking: N = No check option; L = Local check option; C = Cascaded check option',
	READONLY            IS 'Y = View is read-only because of its definition; N = View is not read-only.',
	VALID               IS 'Y = View or materialized query table definition is valid; X = View or materialized query table definition is inoperative; must be re-created.',
	QUALIFIER           IS 'Contains value of the default schema at the time of object definition.',
	FUNC_PATH           IS 'The SQL path of the view creator at the time the view was defined. When the view is used in data manipulation statements, this path must be used to resolve function calls in the view. SYSIBM for views created before Version 2.',
	TEXT                IS 'Text of the CREATE VIEW statement.'
);

COMMENT ON TABLE SYSCAT.WRAPOPTIONS IS 'Each row contains wrapper specific options.';
COMMENT ON SYSCAT.WRAPOPTIONS (
	WRAPNAME            IS 'Wrapper name.',
	OPTION              IS 'Name of wrapper option.',
	SETTING             IS 'Value.'
);

COMMENT ON TABLE SYSCAT.WRAPPERS IS 'Each row contains information on the registered wrapper.';
COMMENT ON SYSCAT.WRAPPERS (
	WRAPNAME            IS 'Wrapper name.',
	WRAPTYPE            IS 'N = Non-relational; R = Relational',
	WRAPVERSION         IS 'Version of the wrapper.',
	LIBRARY             IS 'Name of the file that contains the code used to communicate with the data sources associated with this wrapper.',
	REMARKS             IS 'User supplied comment, or NULL.'
);

