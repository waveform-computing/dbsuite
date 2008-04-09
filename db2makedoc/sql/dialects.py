# vim: set noet sw=4 ts=4:

# Set of characters valid in unquoted identifiers in ANSI SQL-92. This is the
# list of characters used by the tokenizer to recognize an identifier in input
# text. Hence it should include lowercase characters.
# XXX Is this correct?

sql92_identchars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_0123456789'

# Set of characters valid in unquoted names in ANSI SQL-92. This is the list of
# characters used by the parser to determine when to quote an object's name in
# output text. Hence it should NOT include lowercase characters.
# XXX Is this correct?

sql92_namechars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ_0123456789'

# Set of reserved keywords in ANSI SQL-92. Obtained from
# <http://developer.mimer.com/validator/sql-reserved-words.tml>

sql92_keywords = [
	'ABSOLUTE', 'ACTION', 'ADD', 'ALL', 'ALLOCATE', 'ALTER', 'AND', 'ANY',
	'ARE', 'AS', 'ASC', 'ASSERTION', 'AT', 'AUTHORIZATION', 'AVG', 'BEGIN',
	'BETWEEN', 'BIT', 'BIT_LENGTH', 'BOTH', 'BY', 'CALL', 'CASCADE',
	'CASCADED', 'CASE', 'CAST', 'CATALOG', 'CHAR', 'CHAR_LENGTH', 'CHARACTER',
	'CHARACTER_LENGTH', 'CHECK', 'CLOSE', 'COALESCE', 'COLLATE', 'COLLATION',
	'COLUMN', 'COMMIT', 'CONDITION', 'CONNECT', 'CONNECTION', 'CONSTRAINT',
	'CONSTRAINTS', 'CONTAINS', 'CONTINUE', 'CONVERT', 'CORRESPONDING', 'COUNT',
	'CREATE', 'CROSS', 'CURRENT', 'CURRENT_DATE', 'CURRENT_PATH',
	'CURRENT_TIME', 'CURRENT_TIMESTAMP', 'CURRENT_USER', 'CURSOR', 'DATE',
	'DAY', 'DEALLOCATE', 'DEC', 'DECIMAL', 'DECLARE', 'DEFAULT', 'DEFERRABLE',
	'DEFERRED', 'DELETE', 'DESC', 'DESCRIBE', 'DESCRIPTOR', 'DETERMINISTIC',
	'DIAGNOSTICS', 'DISCONNECT', 'DISTINCT', 'DO', 'DOMAIN', 'DOUBLE', 'DROP',
	'ELSE', 'ELSEIF', 'END', 'ESCAPE', 'EXCEPT', 'EXCEPTION', 'EXEC',
	'EXECUTE', 'EXISTS', 'EXIT', 'EXTERNAL', 'EXTRACT', 'FALSE', 'FETCH',
	'FIRST', 'FLOAT', 'FOR', 'FOREIGN', 'FOUND', 'FROM', 'FULL', 'FUNCTION',
	'GET', 'GLOBAL', 'GO', 'GOTO', 'GRANT', 'GROUP', 'HANDLER', 'HAVING',
	'HOUR', 'IDENTITY', 'IF', 'IMMEDIATE', 'IN', 'INDICATOR', 'INITIALLY',
	'INNER', 'INOUT', 'INPUT', 'INSENSITIVE', 'INSERT', 'INT', 'INTEGER',
	'INTERSECT', 'INTERVAL', 'INTO', 'IS', 'ISOLATION', 'JOIN', 'KEY',
	'LANGUAGE', 'LAST', 'LEADING', 'LEAVE', 'LEFT', 'LEVEL', 'LIKE', 'LOCAL',
	'LOOP', 'LOWER', 'MATCH', 'MAX', 'MIN', 'MINUTE', 'MODULE', 'MONTH',
	'NAMES', 'NATIONAL', 'NATURAL', 'NCHAR', 'NEXT', 'NO', 'NOT', 'NULL',
	'NULLIF', 'NUMERIC', 'OCTET_LENGTH', 'OF', 'ON', 'ONLY', 'OPEN', 'OPTION',
	'OR', 'ORDER', 'OUT', 'OUTER', 'OUTPUT', 'OVERLAPS', 'PAD', 'PARAMETER',
	'PARTIAL', 'PATH', 'POSITION', 'PRECISION', 'PREPARE', 'PRESERVE',
	'PRIMARY', 'PRIOR', 'PRIVILEGES', 'PROCEDURE', 'PUBLIC', 'READ', 'REAL',
	'REFERENCES', 'RELATIVE', 'REPEAT', 'RESIGNAL', 'RESTRICT', 'RETURN',
	'RETURNS', 'REVOKE', 'RIGHT', 'ROLLBACK', 'ROUTINE', 'ROWS', 'SCHEMA',
	'SCROLL', 'SECOND', 'SECTION', 'SELECT', 'SESSION', 'SESSION_USER', 'SET',
	'SIGNAL', 'SIZE', 'SMALLINT', 'SOME', 'SPACE', 'SPECIFIC', 'SQL',
	'SQLCODE', 'SQLERROR', 'SQLEXCEPTION', 'SQLSTATE', 'SQLWARNING',
	'SUBSTRING', 'SUM', 'SYSTEM_USER', 'TABLE', 'TEMPORARY', 'THEN', 'TIME',
	'TIMESTAMP', 'TIMEZONE_HOUR', 'TIMEZONE_MINUTE', 'TO', 'TRAILING',
	'TRANSACTION', 'TRANSLATE', 'TRANSLATION', 'TRIM', 'TRUE', 'UNDO', 'UNION',
	'UNIQUE', 'UNKNOWN', 'UNTIL', 'UPDATE', 'UPPER', 'USAGE', 'USER', 'USING',
	'VALUE', 'VALUES', 'VARCHAR', 'VARYING', 'VIEW', 'WHEN', 'WHENEVER',
	'WHERE', 'WHILE', 'WITH', 'WORK', 'WRITE', 'YEAR', 'ZONE',
]

# Set of characters valid in unquoted identifiers and names in ANSI SQL-99 (see
# above)
# XXX Is this correct?

sql99_identchars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_0123456789'
sql99_namechars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ_0123456789'

# Set of reserved keywords in ANSI SQL-99. Obtained from
# <http://developer.mimer.com/validator/sql-reserved-words.tml>

sql99_keywords = [
	'ABSOLUTE', 'ACTION', 'ADD', 'AFTER', 'ALL', 'ALLOCATE', 'ALTER', 'AND',
	'ANY', 'ARE', 'ARRAY', 'AS', 'ASC', 'ASENSITIVE', 'ASSERTION',
	'ASYMMETRIC', 'AT', 'ATOMIC', 'AUTHORIZATION', 'BEFORE', 'BEGIN',
	'BETWEEN', 'BINARY', 'BIT', 'BLOB', 'BOOLEAN', 'BOTH', 'BREADTH', 'BY',
	'CALL', 'CALLED', 'CASCADE', 'CASCADED', 'CASE', 'CAST', 'CATALOG', 'CHAR',
	'CHARACTER', 'CHECK', 'CLOB', 'CLOSE', 'COLLATE', 'COLLATION', 'COLUMN',
	'COMMIT', 'CONDITION', 'CONNECT', 'CONNECTION', 'CONSTRAINT',
	'CONSTRAINTS', 'CONSTRUCTOR', 'CONTINUE', 'CORRESPONDING', 'CREATE',
	'CROSS', 'CUBE', 'CURRENT', 'CURRENT_DATE',
	'CURRENT_DEFAULT_TRANSFORM_GROUP', 'CURRENT_PATH', 'CURRENT_ROLE',
	'CURRENT_TIME', 'CURRENT_TIMESTAMP', 'CURRENT_TRANSFORM_GROUP_FOR_TYPE',
	'CURRENT_USER', 'CURSOR', 'CYCLE', 'DATA', 'DATE', 'DAY', 'DEALLOCATE',
	'DEC', 'DECIMAL', 'DECLARE', 'DEFAULT', 'DEFERRABLE', 'DEFERRED', 'DELETE',
	'DEPTH', 'DEREF', 'DESC', 'DESCRIBE', 'DESCRIPTOR', 'DETERMINISTIC',
	'DIAGNOSTICS', 'DISCONNECT', 'DISTINCT', 'DO', 'DOMAIN', 'DOUBLE', 'DROP',
	'DYNAMIC', 'EACH', 'ELSE', 'ELSEIF', 'END', 'EQUALS', 'ESCAPE', 'EXCEPT',
	'EXCEPTION', 'EXEC', 'EXECUTE', 'EXISTS', 'EXIT', 'EXTERNAL', 'FALSE',
	'FETCH', 'FILTER', 'FIRST', 'FLOAT', 'FOR', 'FOREIGN', 'FOUND', 'FREE',
	'FROM', 'FULL', 'FUNCTION', 'GENERAL', 'GET', 'GLOBAL', 'GO', 'GOTO',
	'GRANT', 'GROUP', 'GROUPING', 'HANDLER', 'HAVING', 'HOLD', 'HOUR',
	'IDENTITY', 'IF', 'IMMEDIATE', 'IN', 'INDICATOR', 'INITIALLY', 'INNER',
	'INOUT', 'INPUT', 'INSENSITIVE', 'INSERT', 'INT', 'INTEGER', 'INTERSECT',
	'INTERVAL', 'INTO', 'IS', 'ISOLATION', 'ITERATE', 'JOIN', 'KEY',
	'LANGUAGE', 'LARGE', 'LAST', 'LATERAL', 'LEADING', 'LEAVE', 'LEFT',
	'LEVEL', 'LIKE', 'LOCAL', 'LOCALTIME', 'LOCALTIMESTAMP', 'LOCATOR', 'LOOP',
	'MAP', 'MATCH', 'METHOD', 'MINUTE', 'MODIFIES', 'MODULE', 'MONTH', 'NAMES',
	'NATIONAL', 'NATURAL', 'NCHAR', 'NCLOB', 'NEW', 'NEXT', 'NO', 'NONE',
	'NOT', 'NULL', 'NUMERIC', 'OBJECT', 'OF', 'OLD', 'ON', 'ONLY', 'OPEN',
	'OPTION', 'OR', 'ORDER', 'ORDINALITY', 'OUT', 'OUTER', 'OUTPUT', 'OVER',
	'OVERLAPS', 'PAD', 'PARAMETER', 'PARTIAL', 'PARTITION', 'PATH',
	'PRECISION', 'PREPARE', 'PRESERVE', 'PRIMARY', 'PRIOR', 'PRIVILEGES',
	'PROCEDURE', 'PUBLIC', 'RANGE', 'READ', 'READS', 'REAL', 'RECURSIVE',
	'REF', 'REFERENCES', 'REFERENCING', 'RELATIVE', 'RELEASE', 'REPEAT',
	'RESIGNAL', 'RESTRICT', 'RESULT', 'RETURN', 'RETURNS', 'REVOKE', 'RIGHT',
	'ROLE', 'ROLLBACK', 'ROLLUP', 'ROUTINE', 'ROW', 'ROWS', 'SAVEPOINT',
	'SCHEMA', 'SCOPE', 'SCROLL', 'SEARCH', 'SECOND', 'SECTION', 'SELECT',
	'SENSITIVE', 'SESSION', 'SESSION_USER', 'SET', 'SETS', 'SIGNAL', 'SIMILAR',
	'SIZE', 'SMALLINT', 'SOME', 'SPACE', 'SPECIFIC', 'SPECIFICTYPE', 'SQL',
	'SQLEXCEPTION', 'SQLSTATE', 'SQLWARNING', 'START', 'STATE', 'STATIC',
	'SYMMETRIC', 'SYSTEM', 'SYSTEM_USER', 'TABLE', 'TEMPORARY', 'THEN', 'TIME',
	'TIMESTAMP', 'TIMEZONE_HOUR', 'TIMEZONE_MINUTE', 'TO', 'TRAILING',
	'TRANSACTION', 'TRANSLATION', 'TREAT', 'TRIGGER', 'TRUE', 'UNDER', 'UNDO',
	'UNION', 'UNIQUE', 'UNKNOWN', 'UNNEST', 'UNTIL', 'UPDATE', 'USAGE', 'USER',
	'USING', 'VALUE', 'VALUES', 'VARCHAR', 'VARYING', 'VIEW', 'WHEN',
	'WHENEVER', 'WHERE', 'WHILE', 'WINDOW', 'WITH', 'WITHIN', 'WITHOUT',
	'WORK', 'WRITE', 'YEAR', 'ZONE',
]

# Set of characters valid in unquoted identifiers and names in ANSI SQL-2003
# (see above)
# XXX Is this correct?

sql2003_identchars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_0123456789'
sql2003_namechars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ_0123456789'

# Set of reserved keywords in ANSI SQL-2003. Obtained from
# <http://developer.mimer.com/validator/sql-reserved-words.tml>

sql2003_keywords = [
	'ADD', 'ALL', 'ALLOCATE', 'ALTER', 'AND', 'ANY', 'ARE', 'ARRAY', 'AS',
	'ASENSITIVE', 'ASYMMETRIC', 'AT', 'ATOMIC', 'AUTHORIZATION', 'BEGIN',
	'BETWEEN', 'BIGINT', 'BINARY', 'BLOB', 'BOOLEAN', 'BOTH', 'BY', 'CALL',
	'CALLED', 'CASCADED', 'CASE', 'CAST', 'CHAR', 'CHARACTER', 'CHECK', 'CLOB',
	'CLOSE', 'COLLATE', 'COLUMN', 'COMMIT', 'CONDITION', 'CONNECT',
	'CONSTRAINT', 'CONTINUE', 'CORRESPONDING', 'CREATE', 'CROSS', 'CUBE',
	'CURRENT', 'CURRENT_DATE', 'CURRENT_DEFAULT_TRANSFORM_GROUP',
	'CURRENT_PATH', 'CURRENT_ROLE', 'CURRENT_TIME', 'CURRENT_TIMESTAMP',
	'CURRENT_TRANSFORM_GROUP_FOR_TYPE', 'CURRENT_USER', 'CURSOR', 'CYCLE',
	'DATE', 'DAY', 'DEALLOCATE', 'DEC', 'DECIMAL', 'DECLARE', 'DEFAULT',
	'DELETE', 'DEREF', 'DESCRIBE', 'DETERMINISTIC', 'DISCONNECT', 'DISTINCT',
	'DO', 'DOUBLE', 'DROP', 'DYNAMIC', 'EACH', 'ELEMENT', 'ELSE', 'ELSEIF',
	'END', 'ESCAPE', 'EXCEPT', 'EXEC', 'EXECUTE', 'EXISTS', 'EXIT', 'EXTERNAL',
	'FALSE', 'FETCH', 'FILTER', 'FLOAT', 'FOR', 'FOREIGN', 'FREE', 'FROM',
	'FULL', 'FUNCTION', 'GET', 'GLOBAL', 'GRANT', 'GROUP', 'GROUPING',
	'HANDLER', 'HAVING', 'HOLD', 'HOUR', 'IDENTITY', 'IF', 'IMMEDIATE', 'IN',
	'INDICATOR', 'INNER', 'INOUT', 'INPUT', 'INSENSITIVE', 'INSERT', 'INT',
	'INTEGER', 'INTERSECT', 'INTERVAL', 'INTO', 'IS', 'ITERATE', 'JOIN',
	'LANGUAGE', 'LARGE', 'LATERAL', 'LEADING', 'LEAVE', 'LEFT', 'LIKE',
	'LOCAL', 'LOCALTIME', 'LOCALTIMESTAMP', 'LOOP', 'MATCH', 'MEMBER', 'MERGE',
	'METHOD', 'MINUTE', 'MODIFIES', 'MODULE', 'MONTH', 'MULTISET', 'NATIONAL',
	'NATURAL', 'NCHAR', 'NCLOB', 'NEW', 'NO', 'NONE', 'NOT', 'NULL', 'NUMERIC',
	'OF', 'OLD', 'ON', 'ONLY', 'OPEN', 'OR', 'ORDER', 'OUT', 'OUTER', 'OUTPUT',
	'OVER', 'OVERLAPS', 'PARAMETER', 'PARTITION', 'PRECISION', 'PREPARE',
	'PRIMARY', 'PROCEDURE', 'RANGE', 'READS', 'REAL', 'RECURSIVE', 'REF',
	'REFERENCES', 'REFERENCING', 'RELEASE', 'REPEAT', 'RESIGNAL', 'RESULT',
	'RETURN', 'RETURNS', 'REVOKE', 'RIGHT', 'ROLLBACK', 'ROLLUP', 'ROW',
	'ROWS', 'SAVEPOINT', 'SCOPE', 'SCROLL', 'SEARCH', 'SECOND', 'SELECT',
	'SENSITIVE', 'SESSION_USER', 'SET', 'SIGNAL', 'SIMILAR', 'SMALLINT',
	'SOME', 'SPECIFIC', 'SPECIFICTYPE', 'SQL', 'SQLEXCEPTION', 'SQLSTATE',
	'SQLWARNING', 'START', 'STATIC', 'SUBMULTISET', 'SYMMETRIC', 'SYSTEM',
	'SYSTEM_USER', 'TABLE', 'TABLESAMPLE', 'THEN', 'TIME', 'TIMESTAMP',
	'TIMEZONE_HOUR', 'TIMEZONE_MINUTE', 'TO', 'TRAILING', 'TRANSLATION',
	'TREAT', 'TRIGGER', 'TRUE', 'UNDO', 'UNION', 'UNIQUE', 'UNKNOWN', 'UNNEST',
	'UNTIL', 'UPDATE', 'USER', 'USING', 'VALUE', 'VALUES', 'VARCHAR',
	'VARYING', 'WHEN', 'WHENEVER', 'WHERE', 'WHILE', 'WINDOW', 'WITH',
	'WITHIN', 'WITHOUT', 'YEAR',
]

# Set of valid characters for unquoted identifiers and names in IBM DB2 UDB
# (see above). Obtained from [1] (see node Reference / SQL / Language Elements)
# [1] http://publib.boulder.ibm.com/infocenter/db2luw/v8/index.jsp

ibmdb2udb_identchars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_$#@0123456789'
ibmdb2udb_namechars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ_$#@0123456789'

# Set of reserved keywords in IBM DB2 UDB. Obtained from
# <http://publib.boulder.ibm.com/infocenter/db2luw/v8/index.jsp> (see node
# Reference / SQL / Reserved schema names and reserved words)

ibmdb2udb_keywords = [
	'ADD', 'AFTER', 'ALIAS', 'ALL', 'ALLOCATE', 'ALLOW', 'ALTER', 'AND', 'ANY',
	'APPLICATION', 'AS', 'ASSOCIATE', 'ASUTIME', 'AUDIT', 'AUTHORIZATION',
	'AUX', 'AUXILIARY', 'BEFORE', 'BEGIN', 'BETWEEN', 'BINARY', 'BUFFERPOOL',
	'BY', 'CACHE', 'CALL', 'CALLED', 'CAPTURE', 'CARDINALITY', 'CASCADED',
	'CASE', 'CAST', 'CCSID', 'CHAR', 'CHARACTER', 'CHECK', 'CLOSE', 'CLUSTER',
	'COLLECTION', 'COLLID', 'COLUMN', 'COMMENT', 'COMMIT', 'CONCAT',
	'CONDITION', 'CONNECT', 'CONNECTION', 'CONSTRAINT', 'CONTAINS', 'CONTINUE',
	'COUNT', 'COUNT_BIG', 'CREATE', 'CROSS', 'CURRENT', 'CURRENT_DATE',
	'CURRENT_LC_CTYPE', 'CURRENT_PATH', 'CURRENT_SERVER', 'CURRENT_TIME',
	'CURRENT_TIMESTAMP', 'CURRENT_TIMEZONE', 'CURRENT_USER', 'CURSOR', 'CYCLE',
	'DATA', 'DATABASE', 'DAY', 'DAYS', 'DB2GENERAL', 'DB2GENRL', 'DB2SQL',
	'DBINFO', 'DECLARE', 'DEFAULT', 'DEFAULTS', 'DEFINITION', 'DELETE',
	'DESCRIPTOR', 'DETERMINISTIC', 'DISALLOW', 'DISCONNECT', 'DISTINCT', 'DO',
	'DOUBLE', 'DROP', 'DSNHATTR', 'DSSIZE', 'DYNAMIC', 'EACH', 'EDITPROC',
	'ELSE', 'ELSEIF', 'ENCODING', 'END', 'END-EXEC', 'END-EXEC1', 'ERASE',
	'ESCAPE', 'EXCEPT', 'EXCEPTION', 'EXCLUDING', 'EXECUTE', 'EXISTS', 'EXIT',
	'EXTERNAL', 'FENCED', 'FETCH', 'FIELDPROC', 'FILE', 'FINAL', 'FOR',
	'FOREIGN', 'FREE', 'FROM', 'FULL', 'FUNCTION', 'GENERAL', 'GENERATED',
	'GET', 'GLOBAL', 'GO', 'GOTO', 'GRANT', 'GRAPHIC', 'GROUP', 'HANDLER',
	'HAVING', 'HOLD', 'HOUR', 'HOURS', 'IDENTITY', 'IF', 'IMMEDIATE', 'IN',
	'INCLUDING', 'INCREMENT', 'INDEX', 'INDICATOR', 'INHERIT', 'INNER',
	'INOUT', 'INSENSITIVE', 'INSERT', 'INTEGRITY', 'INTO', 'IS', 'ISOBID',
	'ISOLATION', 'ITERATE', 'JAR', 'JAVA', 'JOIN', 'KEY', 'LABEL', 'LANGUAGE',
	'LC_CTYPE', 'LEAVE', 'LEFT', 'LIKE', 'LINKTYPE', 'LOCAL', 'LOCALE',
	'LOCATOR', 'LOCATORS', 'LOCK', 'LOCKMAX', 'LOCKSIZE', 'LONG', 'LOOP',
	'MAXVALUE', 'MICROSECOND', 'MICROSECONDS', 'MINUTE', 'MINUTES', 'MINVALUE',
	'MODE', 'MODIFIES', 'MONTH', 'MONTHS', 'NEW', 'NEW_TABLE', 'NO', 'NOCACHE',
	'NOCYCLE', 'NODENAME', 'NODENUMBER', 'NOMAXVALUE', 'NOMINVALUE', 'NOORDER',
	'NOT', 'NULL', 'NULLS', 'NUMPARTS', 'OBID', 'OF', 'OLD', 'OLD_TABLE', 'ON',
	'OPEN', 'OPTIMIZATION', 'OPTIMIZE', 'OPTION', 'OR', 'ORDER', 'OUT',
	'OUTER', 'OVERRIDING', 'PACKAGE', 'PARAMETER', 'PART', 'PARTITION', 'PATH',
	'PIECESIZE', 'PLAN', 'POSITION', 'PRECISION', 'PREPARE', 'PRIMARY',
	'PRIQTY', 'PRIVILEGES', 'PROCEDURE', 'PROGRAM', 'PSID', 'QUERYNO', 'READ',
	'READS', 'RECOVERY', 'REFERENCES', 'REFERENCING', 'RELEASE', 'RENAME',
	'REPEAT', 'RESET', 'RESIGNAL', 'RESTART', 'RESTRICT', 'RESULT',
	'RESULT_SET_LOCATOR', 'RETURN', 'RETURNS', 'REVOKE', 'RIGHT', 'ROLLBACK',
	'ROUTINE', 'ROW', 'ROWS', 'RRN', 'RUN', 'SAVEPOINT', 'SCHEMA',
	'SCRATCHPAD', 'SECOND', 'SECONDS', 'SECQTY', 'SECURITY', 'SELECT',
	'SENSITIVE', 'SET', 'SIGNAL', 'SIMPLE', 'SOME', 'SOURCE', 'SPECIFIC',
	'SQL', 'SQLID', 'STANDARD', 'START', 'STATIC', 'STAY', 'STOGROUP',
	'STORES', 'STYLE', 'SUBPAGES', 'SUBSTRING', 'SYNONYM', 'SYSFUN', 'SYSIBM',
	'SYSPROC', 'SYSTEM', 'TABLE', 'TABLESPACE', 'THEN', 'TO', 'TRANSACTION',
	'TRIGGER', 'TRIM', 'TYPE', 'UNDO', 'UNION', 'UNIQUE', 'UNTIL', 'UPDATE',
	'USAGE', 'USER', 'USING', 'VALIDPROC', 'VALUES', 'VARIABLE', 'VARIANT',
	'VCAT', 'VIEW', 'VOLUMES', 'WHEN', 'WHERE', 'WHILE', 'WITH', 'WLM',
	'WRITE', 'YEAR', 'YEARS',
]

# Set of valid characters for unquoted identifiers and names in IBM DB2 UDB for
# z/OS (see above). Equivalent to IBM DB2 UDB for Linux/Unix/Windows

ibmdb2zos_identchars = ibmdb2udb_identchars
ibmdb2zos_namechars = ibmdb2udb_namechars

# Set of reserved keywords in IBM DB2 UDB for z/OS. Obtained from
# <http://publib.boulder.ibm.com/infocenter/dzichelp/v2r2/topic/com.ibm.db2.doc/db2prodhome.htm>
# (see node DB2 UDB for z/OS Version 8 / DB2 reference information / DB2 SQL /
# Additional information for DB2 SQL / Reserved schema names and reserved words /
# Reserved words)

ibmdb2zos_keywords = [
	'ADD', 'AFTER', 'ALL', 'ALLOCATE', 'ALLOW', 'ALTER', 'AND', 'ANY', 'AS',
	'ASENSITIVE', 'ASSOCIATE', 'ASUTIME', 'AUDIT', 'AUX', 'AUXILIARY',
	'BEFORE', 'BEGIN', 'BETWEEN', 'BUFFERPOOL', 'BY', 'CALL', 'CAPTURE',
	'CASCADED', 'CASE', 'CAST', 'CCSID', 'CHAR', 'CHARACTER', 'CHECK', 'CLOSE',
	'CLUSTER', 'COLLECTION', 'COLLID', 'COLUMN', 'COMMENT', 'COMMIT', 'CONCAT',
	'CONDITION', 'CONNECT', 'CONNECTION', 'CONSTRAINT', 'CONTAINS', 'CONTINUE',
	'CREATE', 'CURRENT', 'CURRENT_DATE', 'CURRENT_LC_CTYPE', 'CURRENT_PATH',
	'CURRENT_TIME', 'CURRENT_TIMESTAMP', 'CURSOR', 'DATA', 'DATABASE', 'DAY',
	'DAYS', 'DBINFO', 'DECLARE', 'DEFAULT', 'DELETE', 'DESCRIPTOR',
	'DETERMINISTIC', 'DISALLOW', 'DISTINCT', 'DO', 'DOUBLE', 'DROP', 'DSSIZE',
	'DYNAMIC', 'EDITPROC', 'ELSE', 'ELSEIF', 'ENCODING', 'ENCRYPTION', 'END',
	'ENDING', 'END-EXEC', 'ERASE', 'ESCAPE', 'EXCEPT', 'EXCEPTION', 'EXECUTE',
	'EXISTS', 'EXIT', 'EXPLAIN', 'EXTERNAL', 'FENCED', 'FETCH', 'FIELDPROC',
	'FINAL', 'FOR', 'FREE', 'FROM', 'FULL', 'FUNCTION', 'GENERATED', 'GET',
	'GLOBAL', 'GO', 'GOTO', 'GRANT', 'GROUP', 'HANDLER', 'HAVING', 'HOLD',
	'HOUR', 'HOURS', 'IF', 'IMMEDIATE', 'IN', 'INCLUSIVE', 'INDEX', 'INHERIT',
	'INNER', 'INOUT', 'INSENSITIVE', 'INSERT', 'INTO', 'IS', 'ISOBID',
	'ITERATE', 'JAR', 'JOIN', 'KEY', 'LABEL', 'LANGUAGE', 'LC_CTYPE', 'LEAVE',
	'LEFT', 'LIKE', 'LOCAL', 'LOCALE', 'LOCATOR', 'LOCATORS', 'LOCK',
	'LOCKMAX', 'LOCKSIZE', 'LONG', 'LOOP', 'MAINTAINED', 'MATERIALIZED',
	'MICROSECOND', 'MICROSECONDS', 'MINUTE', 'MINUTES', 'MODIFIES', 'MONTH',
	'MONTHS', 'NEXTVAL', 'NO', 'NONE', 'NOT', 'NULL', 'NULLS', 'NUMPARTS',
	'OBID', 'OF', 'ON', 'OPEN', 'OPTIMIZATION', 'OPTIMIZE', 'OR', 'ORDER',
	'OUT', 'OUTER', 'PACKAGE', 'PARAMETER', 'PART', 'PADDED', 'PARTITION',
	'PARTITIONED', 'PARTITIONING', 'PATH', 'PIECESIZE', 'PLAN', 'PRECISION',
	'PREPARE', 'PREVVAL', 'PRIQTY', 'PRIVILEGES', 'PROCEDURE', 'PROGRAM',
	'PSID', 'QUERY', 'QUERYNO', 'READS', 'REFERENCES', 'REFRESH', 'RESIGNAL',
	'RELEASE', 'RENAME', 'REPEAT', 'RESTRICT', 'RESULT', 'RESULT_SET_LOCATOR',
	'RETURN', 'RETURNS', 'REVOKE', 'RIGHT', 'ROLLBACK', 'ROWSET', 'RUN',
	'SAVEPOINT', 'SCHEMA', 'SCRATCHPAD', 'SECOND', 'SECONDS', 'SECQTY',
	'SECURITY', 'SEQUENCE', 'SELECT', 'SENSITIVE', 'SET', 'SIGNAL', 'SIMPLE',
	'SOME', 'SOURCE', 'SPECIFIC', 'STANDARD', 'STATIC', 'STAY', 'STOGROUP',
	'STORES', 'STYLE', 'SUMMARY', 'SYNONYM', 'SYSFUN', 'SYSIBM', 'SYSPROC',
	'SYSTEM', 'TABLE', 'TABLESPACE', 'THEN', 'TO', 'TRIGGER', 'UNDO', 'UNION',
	'UNIQUE', 'UNTIL', 'UPDATE', 'USER', 'USING', 'VALIDPROC', 'VALUE',
	'VALUES', 'VARIABLE', 'VARIANT', 'VCAT', 'VIEW', 'VOLATILE', 'VOLUMES',
	'WHEN', 'WHENEVER', 'WHERE', 'WHILE', 'WITH', 'WLM', 'XMLELEMENT', 'YEAR',
	'YEARS',
]
