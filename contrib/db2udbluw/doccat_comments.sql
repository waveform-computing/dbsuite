-- vim: set noet sw=4 ts=4:

-------------------------------------------------------------------------------
-- Documentation for system objects in IBM DB2 UDB for Linux/UNIX/Windows
--
-- OVERVIEW
-- ========
-- This script creates comments for most system objects in a DB2 database.
-- Specifically, all objects in the SYSCAT and SYSSTAT schemas are covered,
-- including deprecated views, some objects in the SYSIBM schema are covered
-- (such as the ODBC support views), and all routines and parameters in the
-- SYSFUN schema are covered.
--
-- Routines in the SYSIBM schema are not documented as they do not exist in
-- the system catalog tables.
--
-- Finally, the documentation extension objects are covered (objects in the
-- DOCCAT, DOCDATA and DOCTOOLS schemas)
--
-- SYNTAX
-- ======
-- The comments are mostly simple text, but include some minor markup which
-- should be transparent or unobtrusive to most readers. Specifically:
--
--   *Bold* words are enclosed in asterisks
--   /Italic/ words are enclosed in slashes
--   _Underlined_ words are enclosed in underscores
--   Database object names are preceeded by @ (e.g. @SYSCAT.TABLES)
--
-- These conventions can be used by documentation systems to produce marked
-- up output, including links from the comment on an object to another object.
--
-- INSTALLATION
-- ============
-- 1. Connect to the target database
-- 2. Execute this file, using semi-colon (;) as the statement terminator
-------------------------------------------------------------------------------

-------------------------------------------------------------------------------
-- Comments for the built-in data types
-------------------------------------------------------------------------------
DELETE FROM DOCDATA.DATATYPES;
INSERT INTO DOCDATA.DATATYPES (TYPESCHEMA, TYPENAME, REMARKS)
	VALUES
	('SYSIBM', 'SMALLINT',        'A 16-bit (2-byte) representation of a whole number with a precision of 4-5 significant digits, capable of representing values in the range -32 768 to 32 767.'),
	('SYSIBM', 'INTEGER',         'A 32-bit (4-byte) representation of a whole number with a precision of 9-10 significant digits, capable of representing values in the range -2 147 483 648 to 2 147 483 647.'),
	('SYSIBM', 'BIGINT',          'A 64-bit (8-byte) representation of a whole number with a precision of 18-19 significant digits, capable of representing values in the range -9 223 372 036 854 775 808 to +9 223 372 036 854 775 807.'),
	('SYSIBM', 'REAL',            'A 32-bit (4-byte) /floating/-/point/ approximation of a real number with a precision of 7-8 significant digits, capable of representing values in the range -3.402e+38 to -1.175e-37, or 1.175e-37 to 3.402e+38.'),
	('SYSIBM', 'DOUBLE',          'A 64-bit (8-byte) /floating/-/point/ approximation of a real number with a precision of 15-16 significant digits, capable of representing values in the range -1.79769e+308 to -2.225e-307, or 2.225e-307 to 1.79769e+308.'),
	('SYSIBM', 'DECIMAL',         'A /fixed/-/point/ representation of a rational number with a specified precision (1-31 digits) and scale (0-precision digits). All values in a decimal column have the same precision and scale. The maximum range is -1e31+1 to 1e31-1.'),
	('SYSIBM', 'CHARACTER',       'A /fixed/ length string type capable of storing single-byte (SBCS) strings between 1 and 254 characters long. All values in a fixed-length character column have the same length (the maximum specified when the column was created), and are implicitly padded with blanks.'),
	('SYSIBM', 'VARCHAR',         'A /variable/ length string type capable of storing single-byte (SBCS) strings between 1 and 32 672 characters long. All values in a variable-length character column have distinct lengths (up to the maximum specified when the column was created), and are not implicitly padded.'),
	('SYSIBM', 'LONG VARCHAR',    'A /variable/ length string type capable of storing single-byte (SBCS) strings up to 32 700 characters long. No limit is specified when creating a LONG VARCHAR column (the maximum is fixed). LONG VARCHAR is a ''long'' type (like BLOB and CLOB), and therefore is subject to certain restrictions (see the DB2 UDB Reference for more information).'),
	('SYSIBM', 'CLOB',            'A CLOB (character large object) value can be up to 2 gigabytes (2 147 483 647 bytes) long. A CLOB is used to store large SBCS or mixed (SBCS and MBCS) character-based data (such as documents written with a single character set) and, therefore, has an SBCS or mixed code page associated with it. Long types like CLOB are subject to certain restrictions (see the DB2 UDB Reference for more information).'),
	('SYSIBM', 'GRAPHIC',         'A /fixed/ length string type capable of storing double-byte (DBCS) strings between 1 and 127 characters long. All values in a fixed-length character column have the same length (the maximum specified when the column was created), and are implicitly padded with blanks.'),
	('SYSIBM', 'VARGRAPHIC',      'A /variable/ length string type capable of storing double-byte (DBCS) strings between 1 and 16 336 characters long. All values in a variable-length character column have distinct lengths (up to the maximum specified when the column was created), and are not implicitly padded.'),
	('SYSIBM', 'LONG VARGRAPHIC', 'A /variable/ length string type capable of storing double-byte (DBCS) strings up to 16 350 characters long. No limit is specified when creating a LONG VARGRAPHIC column (the maximum is fixed). LONG VARGRAPHIC is a ''long'' type (like BLOB and DBCLOB), and therefore is subject to certain restrictions (see the DB2 UDB Reference for more information).'),
	('SYSIBM', 'DBCLOB',          'A DBCLOB (double-byte character large object) value can be up to 1 073 741 823 double-byte characters long. A DBCLOB is used to store large DBCS character-based data (such as documents written with a single character set) and, therefore, has a DBCS code page associated with it. Long types like DBCLOB are subject to certain restrictions (see the DB2 UDB Reference for more information).'),
	('SYSIBM', 'BLOB',            'A binary large object is a varying-length binary string that can be up to 2 gigabytes (2 147 483 647 bytes) long. BLOBs can hold structured data for exploitation by user-defined types and user-defined functions. Like FOR BIT DATA character strings, BLOB strings are not associated with a code page.'),
	('SYSIBM', 'DATE',            'A /date/ is a three-part value (year, month, and day). The range of the year part is 0001 to 9999. The range of the month part is 1 to 12. The range of the day part is 1 to /x/, where /x/ depends on the month.'),
	('SYSIBM', 'TIME',            'A /time/ is a three-part value (hour, minute, and second) designating a time of day under a 24-hour clock. The range of the hour part is 0 to 24. The range of the other parts is 0 to 59. If the hour is 24, the minute and second specifications are zero.'),
	('SYSIBM', 'TIMESTAMP',       'A /timestamp/ is a seven-part value (year, month, day, hour, minute, second, and microsecond) designating a date and time as with the DATE and TIME types, except that the time includes a fractional specification of microseconds.'),
	('SYSIBM', 'DATALINK',        'A DATALINK value is an encapsulated value that contains a logical reference from the database to a file stored outside of the database. The attributes of this encapsulated value are: link type, data location, comment. See the DB2 UDB Reference for further information on these elements.');

DELETE FROM DOCDATA.ROUTINES;
INSERT INTO DOCDATA.ROUTINES (ROUTINESCHEMA, SPECIFICNAME, REMARKS)
	VALUES
	(
		'SYSFUN',
		'ABS1',
		'Returns the absolute value of the argument. The argument can be any built-in numeric data type.' || x'0A0A' ||
		'The result has the same data type and length attribute as the argument. The result can be NULL; if the argument is NULL, the result is the NULL value. If the argument is the maximum negative value for SMALLINT, INTEGER or BIGINT, the result is an overflow error.'
	),
	(
		'SYSFUN',
		'ACOS',
		'Returns the arccosine of the argument as an angle expressed in radians.' || x'0A0A' ||
		'The argument can be of any built-in numeric data type. It is converted to a double-precision floating-point number for processing by the function.' || x'0A0A' ||
		'The result of the function is a double-precision floating-point number. The result can be null if the argument can be null or the database is configured with DFT_SQLMATHWARN set to YES; the result is the null value if the argument is null.'
	),
	(
		'SYSFUN',
		'APPLICATION_ID',
		'The APPLICATION_ID function returns the application ID of the current connection.' || x'0A0A' ||
		'The value returned by this function is only unique for the period of time during which the client can use the same value again.'
	),
	(
		'SYSFUN',
		'ASCII1',
		'Returns the ASCII code value of the leftmost character of the argument as an integer.' || x'0A0A' ||
		'The argument can be of any built-in character string type. In a Unicode database, if a supplied argument is a graphic string, it is first converted to a character string before the function is executed. For a VARCHAR, the maximum length is 4 000 bytes, and for a CLOB, the maximum length is 1 048 576 bytes. LONG VARCHAR is converted to CLOB for processing by the function.' || x'0A0A' ||
		'The result of the function is always INTEGER. The result can be null; if the argument is null, the result is the null value.'
	),
	(
		'SYSFUN',
		'ASIN',
		'Returns the arcsine on the argument as an angle expressed in radians.' || x'0A0A' ||
		'The argument can be of any built-in numeric type. It is converted to a double-precision floating-point number for processing by the function.' || x'0A0A' ||
		'The result of the function is a double-precision floating-point number. The result can be null if the argument can be null or the database is configured with DFT_SQLMATHWARN set to YES; the result is the null value if the argument is null.'
	),
	(
		'SYSFUN',
		'ATAN',
		'Returns the arctangent of the argument as an angle expressed in radians.' || x'0A0A' ||
		'The argument can be of any built-in numeric data type. It is converted to a double-precision floating-point number for processing by the function.' || x'0A0A' ||
		'The result of the function is a double-precision floating-point number. The result can be null if the argument can be null or the database is configured with DFT_SQLMATHWARN set to YES; the result is the null value if the argument is null.'
	),
	(
		'SYSFUN',
		'ATAN2',
		'Returns the arctangent of x and y coordinates as an angle expressed in radians. The x and y coordinates are specified by the first and second arguments, respectively.' || x'0A0A' ||
		'The first and the second arguments can be of any built-in numeric data type. Both are converted to a double-precision floating-point number for processing by the function.' || x'0A0A' ||
		'The result of the function is a double-precision floating-point number. The result can be null if the argument can be null or the database is configured with DFT_SQLMATHWARN set to YES; the result is the null value if the argument is null.'
	),
	(
		'SYSFUN',
		'CEIL1',
		'Returns the smallest integer value greater than or equal to the argument.' || x'0A0A' ||
		'The argument can be of any built-in numeric type. The result of the function has the same data type and length attribute as the argument except that the scale is 0 if the argument is DECIMAL. For example, an argument with a data type of DECIMAL(5,5) returns DECIMAL(5,0).' || x'0A0A' ||
		'The result can be null if the argument can be null or the database is configured with DFT_SQLMATHWARN set to YES; the result is the null value if the argument is null.'
	),
	(
		'SYSFUN',
		'CHR',
		'Returns the character that has the ASCII code value specified by the argument.' || x'0A0A' ||
		'The argument can be either INTEGER or SMALLINT. The value of the argument should be between 0 and 255; otherwise, the return value is null.' || x'0A0A' ||
		'The result of the function is CHAR(1). The result can be null; if the argument is null, the result is the null value.'
	),
	(
		'SYSFUN',
		'COS',
		'Returns the cosine of the argument, where the argument is an angle expressed in radians.' || x'0A0A' ||
		'The argument can be of any built-in numeric type. It is converted to a double-precision floating-point number for processing by the function.' || x'0A0A' ||
		'The result of the function is a double-precision floating-point number. The result can be null if the argument can be null or the database is configured with DFT_SQLMATHWARN set to YES; the result is the null value if the argument is null.'
	),
	(
		'SYSFUN',
		'COT',
		'Returns the cotangent of the argument, where the argument is an angle expressed in radians.' || x'0A0A' ||
		'The argument can be of any built-in numeric type. It is converted to a double-precision floating-point number for processing by the function.' || x'0A0A' ||
		'The result of the function is a double-precision floating-point number. The result can be null if the argument can be null or the database is configured with DFT_SQLMATHWARN set to YES; the result is the null value if the argument is null.'
	);

COMMIT;
