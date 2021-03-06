# vim: set et sw=4 sts=4:

# Copyright 2012 Dave Hughes.
#
# This file is part of dbsuite.
#
# dbsuite is free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# dbsuite is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# dbsuite.  If not, see <http://www.gnu.org/licenses/>.

"""Input plugin for SQLite."""

from __future__ import (
    unicode_literals,
    print_function,
    absolute_import,
    division,
    )

import logging
import re

import dbsuite.plugins
from dbsuite.plugins.db2 import (
    connect, make_datetime, make_bool, make_int, make_str
)
from dbsuite.tuples import (
    Schema, Datatype, Table, View, Alias, RelationDep, Index, IndexCol,
    RelationCol, UniqueKey, UniqueKeyCol, ForeignKey, ForeignKeyCol, Check,
    CheckCol, Function, Procedure, RoutineParam, Trigger, TriggerDep,
    Tablespace
)


def connect(database=None):
    """Create a connection to the specified database.

    This utility method attempts to connect to the specified database.
    """
    logging.info('Connecting to database "%s"' % database)
    # Try the built-in sqlite3 driver
    try:
        import sqlite3
    except ImportError:
        pass
    else:
        logging.info('Using sqlite3 driver')
        return sqlite3.connect(database)
    raise ImportError('Unable to find a suitable connection framework; please upgrade python to a version that includes sqlite3')


class InputPlugin(dbsuite.plugins.InputPlugin):
    """Input plugin for SQLite.

    This input plugin supports extracting documentation information from
    SQLite databases.
    """

    def __init__(self):
        super(InputPlugin, self).__init__()
        self.add_option('database', default='',
            doc="""The filename of the database to connect to""")

    def configure(self, config):
        """Loads the plugin configuration."""
        super(InputPlugin, self).configure(config)
        # Check for missing stuff
        if not self.options['database']:
            raise dbsuite.plugins.PluginConfigurationError('The database option must be specified')

    def open(self):
        """Opens the database connection for data retrieval."""
        super(InputPlugin, self).open()
        self.connection = connect(self.options['database'])
        self.name = self.options['database']

    def close(self):
        """Closes the database connection and cleans up any resources."""
        super(InputPlugin, self).close()
        self.connection.close()
        del self.connection

    def get_schemas(self):
        """Retrieves the details of schemas stored in the database.

        Override this function to return a list of Schema tuples containing
        details of the schemas defined in the database. Schema tuples have the
        following named fields:

        name         -- The name of the schema
        owner*       -- The name of the user who owns the schema
        system       -- True if the schema is system maintained (bool)
        created*     -- When the schema was created (datetime)
        description* -- Descriptive text

        * Optional (can be None)
        """
        for row in super(InputPlugin, self).get_schemas():
            yield row
        yield Schema('', '', False, None, 'SQLite has no concept of schemas - this is a placeholder')

    def get_datatypes(self):
        """Retrieves the details of datatypes stored in the database.

        Override this function to return a list of Datatype tuples containing
        details of the datatypes defined in the database (including system
        types). Datatype tuples have the following named fields:

        schema         -- The schema of the datatype
        name           -- The name of the datatype
        owner*         -- The name of the user who owns the datatype
        system         -- True if the type is system maintained (bool)
        created*       -- When the type was created (datetime)
        description*   -- Descriptive text
        variable_size  -- True if the type has a variable length (e.g. VARCHAR)
        variable_scale -- True if the type has a variable scale (e.g. DECIMAL)
        source_schema* -- The schema of the base system type of the datatype
        source_name*   -- The name of the base system type of the datatype
        size*          -- The length of the type for character based types or
                          the maximum precision for decimal types
        scale*         -- The maximum scale for decimal types

        * Optional (can be None)
        """
        for row in super(InputPlugin, self).get_datatypes():
            yield row

    def get_tables(self):
        """Retrieves the details of tables stored in the database.

        Override this function to return a list of Table tuples containing
        details of the tables (NOT views) defined in the database (including
        system tables). Table tuples contain the following named fields:

        schema        -- The schema of the table
        name          -- The name of the table
        owner*        -- The name of the user who owns the table
        system        -- True if the table is system maintained (bool)
        created*      -- When the table was created (datetime)
        description*  -- Descriptive text
        tbspace       -- The name of the primary tablespace containing the table
        last_stats*   -- When the table's statistics were last calculated (datetime)
        cardinality*  -- The approximate number of rows in the table
        size*         -- The approximate size in bytes of the table

        * Optional (can be None)
        """
        for row in super(InputPlugin, self).get_tables():
            yield row
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT
                ''    AS tabschema,
                name  AS tabname,
                NULL  AS owner,
                0     AS system,
                NULL  AS created,
                NULL  AS description,
                ''    AS tbspace,
                NULL  AS last_stats,
                NULL  AS cardinality,
                NULL  AS size
            FROM
                sqlite_master
            WHERE
                type = 'table'
        """)
        for row in self.fetch_some(cursor):
            yield Table(*row)

    def get_views(self):
        """Retrieves the details of views stored in the database.

        Override this function to return a list of View tuples containing
        details of the views defined in the database (including system views).
        View tuples contain the following named fields:

        schema        -- The schema of the view
        name          -- The name of the view
        owner*        -- The name of the user who owns the view
        system        -- True if the view is system maintained (bool)
        created*      -- When the view was created (datetime)
        description*  -- Descriptive text
        read_only*    -- True if the view is not updateable (bool)
        sql*          -- The SQL statement that defined the view

        * Optional (can be None)
        """
        for row in super(InputPlugin, self).get_views():
            yield row
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT
                ''    AS viewschema,
                name  AS viewname,
                NULL  AS owner,
                0     AS system,
                NULL  AS created,
                NULL  AS description,
                1     AS readonly,
                sql   AS sql
            FROM
                sqlite_master
            WHERE
                type = 'view'
        """)
        for row in self.fetch_some(cursor):
            yield View(*row)

    def get_view_dependencies(self):
        """Retrieves the details of view dependencies.

        Override this function to return a list of RelationDep tuples
        containing details of the relations upon which views depend (the tables
        and views that a view references in its query). RelationDep tuples
        contain the following named fields:

        schema       -- The schema of the view
        name         -- The name of the view
        dep_schema   -- The schema of the relation upon which the view depends
        dep_name     -- The name of the relation upon which the view depends
        """
        for row in super(InputPlugin, self).get_view_dependencies():
            yield row
        # XXX Use the parser to deconstruct the view SQL and determine the
        # dependencies

    def get_indexes(self):
        """Retrieves the details of indexes stored in the database.

        Override this function to return a list of Index tuples containing
        details of the indexes defined in the database (including system
        indexes). Index tuples contain the following named fields:

        schema        -- The schema of the index
        name          -- The name of the index
        owner*        -- The name of the user who owns the index
        system        -- True if the index is system maintained (bool)
        created*      -- When the index was created (datetime)
        description*  -- Descriptive text
        table_schema  -- The schema of the table the index belongs to
        table_name    -- The name of the table the index belongs to
        tbspace       -- The name of the tablespace which contains the index
        last_stats*   -- When the index statistics were last updated (datetime)
        cardinality*  -- The approximate number of values in the index
        size*         -- The approximate size in bytes of the index
        unique        -- True if the index contains only unique values (bool)

        * Optional (can be None)
        """
        for row in super(InputPlugin, self).get_indexes():
            yield row
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT
                ''       AS indschema,
                name     AS indname,
                NULL     AS owner,
                0        AS system,
                NULL     AS created,
                NULL     AS description,
                ''       AS tabschema,
                tbl_name AS tabname,
                NULL     AS laststats,
                NULL     AS cardinality,
                NULL     AS size,
                CASE
                    WHEN sql IS NULL THEN 1
                    WHEN sql LIKE '% unique %' THEN 1
                    ELSE 0
                END      AS unique
            FROM
                sqlite_master
            WHERE
                type = 'index'
        """)
        for row in self.fetch_some(cursor):
            yield Index(*row)

    def get_index_cols(self):
        """Retrieves the list of columns belonging to indexes.

        Override this function to return a list of IndexCol tuples detailing
        the columns that belong to each index in the database (including system
        indexes).  IndexCol tuples contain the following named fields:

        index_schema -- The schema of the index
        index_name   -- The name of the index
        name         -- The name of the column
        order        -- The ordering of the column in the index:
                        'A' = Ascending
                        'D' = Descending
                        'I' = Include (not an index key)

        Note that the each tuple details one column belonging to an index. It
        is important that the list of tuples is in the order that each column
        is declared in an index.
        """
        for row in super(InputPlugin, self).get_index_cols():
            yield row
        cursor = self.connection.cursor()
        for index in self.indexes:
            cursor.execute("PRAGMA index_info(?)", index.name)
            cols = sorted(cursor.fetchall(), itemgetter(0))
            for col in cols:
                yield IndexCol(index.schema.name, index.name, col[2], 'A')

    def get_relation_cols(self):
        """Retrieves the list of columns belonging to relations.

        Override this function to return a list of RelationCol tuples detailing
        the columns that belong to each relation (table, view, etc.) in the
        database (including system relations). RelationCol tuples contain the
        following named fields:

        relation_schema  -- The schema of the table
        relation_name    -- The name of the table
        name             -- The name of the column
        type_schema      -- The schema of the column's datatype
        type_name        -- The name of the column's datatype
        size*            -- The length of the column for character types, or the
                            numeric precision for decimal types (None if not a
                            character or decimal type)
        scale*           -- The maximum scale for decimal types (None if not a
                            decimal type)
        codepage*        -- The codepage of the column for character types (None
                            if not a character type)
        identity*        -- True if the column is an identity column (bool)
        nullable*        -- True if the column can store NULL (bool)
        cardinality*     -- The approximate number of unique values in the column
        null_card*       -- The approximate number of NULLs in the column
        generated        -- 'A' = Column is always generated
                            'D' = Column is generated by default
                            'N' = Column is not generated
        default*         -- If generated is 'N', the default value of the column
                            (expressed as SQL). Otherwise, the SQL expression that
                            generates the column's value (or default value). None
                            if the column has no default
        description*     -- Descriptive text

        Note that each tuple details one column belonging to a relation. It is
        important that the list of tuples is in the order that each column is
        declared in a relation.

        * Optional (can be None)
        """
        for row in super(InputPlugin, self).get_relation_cols():
            yield row
        type_re = re.compile('(?P=<type>[^(]*)(?:\((?P=<size>[0-9]*)(?:,(?P=<scale>[0-9]*))?\))?')
        cursor = self.connection.cursor()
        for relation in self.relations:
            cursor.execute("PRAGMA table_info(?)", relation.name)
            cols = sorted(cursor.fetchall(), itemgetter(0))
            for col in cols:
                type_match = type_re.match(col[2])
                yield RelationCol(
                    relation.schema.name,
                    relation.name,
                    col[1],
                    '',
                    type_match.group('type'),
                    int(type_match.group('size')) if type_match.group('size') else None,
                    int(type_match.group('scale')) if type_match.group('scale') else None,
                    None,
                    False,
                    not col[3],
                    None,
                    None,
                    'N',
                    col[4],
                    None
                )

    def get_unique_keys(self):
        """Retrieves the details of unique keys stored in the database.

        Override this function to return a list of UniqueKey tuples containing
        details of the unique keys defined in the database. UniqueKey tuples
        contain the following named fields:

        table_schema  -- The schema of the table containing the key
        table_name    -- The name of the table containing the key
        name          -- The name of the key
        owner*        -- The name of the user who owns the key
        system        -- True if the key is system maintained (bool)
        created*      -- When the key was created (datetime)
        description*  -- Descriptive text
        primary       -- True if the unique key is also a primary key (bool)

        * Optional (can be None)
        """
        for row in super(InputPlugin, self).get_unique_keys():
            yield row
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT
                nsp.nspname                               AS tabname,
                cls.relname                               AS tabname,
                con.conname                               AS keyname,
                own.rolname                               AS owner,
                CASE
                    WHEN nsp.nspname LIKE 'pg_%' THEN true
                    WHEN nsp.nspname = 'information_schema' THEN true
                    ELSE false
                END                                       AS system,
                CAST(NULL AS TIMESTAMP)                   AS created,
                obj_description(con.oid, 'pg_constraint') AS description,
                CASE contype
                    WHEN 'p' THEN true
                    ELSE false
                END                                       AS primary
            FROM
                pg_catalog.pg_constraint con
                INNER JOIN pg_catalog.pg_class cls
                    ON con.conrelid = cls.oid
                INNER JOIN pg_catalog.pg_namespace nsp
                    ON cls.relnamespace = nsp.oid
                INNER JOIN pg_catalog.pg_authid own
                    ON cls.relowner = own.oid
            WHERE
                cls.relkind = 'r'
                AND con.contype IN ('p', 'u')
                AND NOT pg_is_other_temp_schema(nsp.oid)
        """)
        for (
                schema,
                name,
                keyname,
                owner,
                system,
                created,
                desc,
                primary,
            ) in self.fetch_some(cursor):
            yield UniqueKey(
                make_str(schema),
                make_str(name),
                make_str(keyname),
                make_str(owner),
                make_bool(system),
                make_datetime(created),
                make_str(desc),
                make_bool(primary),
            )

    def get_unique_key_cols(self):
        """Retrieves the list of columns belonging to unique keys.

        Override this function to return a list of UniqueKeyCol tuples
        detailing the columns that belong to each unique key in the database.
        The tuples contain the following named fields:

        const_schema -- The schema of the table containing the key
        const_table  -- The name of the table containing the key
        const_name   -- The name of the key
        name         -- The name of the column
        """
        for row in super(InputPlugin, self).get_unique_key_cols():
            yield row
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT
                nsp.nspname      AS tabschema,
                cls.relname      AS tabname,
                con.conname      AS keyname,
                att.attname      AS colname
            FROM
                (
                    SELECT
                        generate_subscripts(c.conkey, 1) AS i, c.*
                    FROM
                        pg_catalog.pg_constraint c
                ) AS con
                INNER JOIN pg_catalog.pg_class cls
                    ON con.conrelid = cls.oid
                INNER JOIN pg_catalog.pg_namespace nsp
                    ON cls.relnamespace = nsp.oid
                INNER JOIN pg_catalog.pg_attribute att
                    ON att.attrelid = cls.oid
                    AND att.attnum = con.conkey[con.i]
            WHERE
                con.conrelid <> 0
                AND cls.relkind = 'r'
                AND con.contype IN ('p', 'u')
                AND NOT pg_is_other_temp_schema(nsp.oid)
            ORDER BY
                nsp.nspname,
                cls.relname,
                con.conname,
                con.i
        """)
        for row in self.fetch_some(cursor):
            yield UniqueKeyCol(*row)

    def get_foreign_keys(self):
        """Retrieves the details of foreign keys stored in the database.

        Override this function to return a list of ForeignKey tuples containing
        details of the foreign keys defined in the database. ForeignKey tuples
        contain the following named fields:

        table_schema      -- The schema of the table containing the key
        table_name        -- The name of the table containing the key
        name              -- The name of the key
        owner*            -- The name of the user who owns the key
        system            -- True if the key is system maintained (bool)
        created*          -- When the key was created (datetime)
        description*      -- Descriptive text
        const_schema      -- The schema of the table the key references
        const_table       -- The name of the table the key references
        const_name        -- The name of the unique key that the key references
        delete_rule       -- The action to take on deletion of a parent key:
                             'A' = No action
                             'C' = Cascade
                             'N' = Set NULL
                             'D' = Set DEFAULT
                             'R' = Restrict
        update_rule       -- The action to take on update of a parent key:
                             'A' = No action
                             'C' = Cascade
                             'N' = Set NULL
                             'D' = Set DEFAULT
                             'R' = Restrict

        * Optional (can be None)
        """
        for row in super(InputPlugin, self).get_foreign_keys():
            yield row
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT
                nsp.nspname                               AS tabname,
                cls.relname                               AS tabname,
                con.conname                               AS keyname,
                own.rolname                               AS owner,
                CASE
                    WHEN nsp.nspname LIKE 'pg_%' THEN true
                    WHEN nsp.nspname = 'information_schema' THEN true
                    ELSE false
                END                                       AS system,
                CAST(NULL AS TIMESTAMP)                   AS created,
                obj_description(con.oid, 'pg_constraint') AS description,
                rnsp.nspname                              AS reftabschema,
                rcls.relname                              AS reftabname,
                rcon.conname                              AS refkeyname,
                con.confdeltype                           AS deleterule,
                con.confupdtype                           AS updaterule
            FROM
                pg_catalog.pg_constraint con
                INNER JOIN pg_catalog.pg_class cls
                    ON con.conrelid = cls.oid
                INNER JOIN pg_catalog.pg_namespace nsp
                    ON cls.relnamespace = nsp.oid
                INNER JOIN pg_catalog.pg_authid own
                    ON cls.relowner = own.oid
                INNER JOIN pg_catalog.pg_constraint rcon
                    ON con.confrelid = rcon.conrelid
                    AND con.confkey @> rcon.conkey
                    AND con.confkey <@ rcon.conkey
                INNER JOIN pg_catalog.pg_class rcls
                    ON rcon.conrelid = rcls.oid
                INNER JOIN pg_catalog.pg_namespace rnsp
                    ON rcls.relnamespace = rnsp.oid
            WHERE
                cls.relkind = 'r'
                AND rcls.relkind = 'r'
                AND con.contype = 'f'
                AND NOT pg_is_other_temp_schema(nsp.oid)
                AND NOT pg_is_other_temp_schema(rnsp.oid)
        """)
        for row in self.fetch_some(cursor):
            yield ForeignKey(*row)

    def get_foreign_key_cols(self):
        """Retrieves the list of columns belonging to foreign keys.

        Override this function to return a list of ForeignKeyCol tuples
        detailing the columns that belong to each foreign key in the database.
        ForeignKeyCol tuples contain the following named fields:

        const_schema -- The schema of the table containing the key
        const_table  -- The name of the table containing the key
        const_name   -- The name of the key
        name         -- The name of the column in the key
        ref_name     -- The name of the column that this column references in
                        the referenced key
        """
        for row in super(InputPlugin, self).get_foreign_key_cols():
            yield row
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT
                nsp.nspname      AS tabschema,
                cls.relname      AS tabname,
                con.conname      AS keyname,
                att.attname      AS colname,
                ratt.attname     AS refcolname
            FROM
                (
                    SELECT
                        generate_subscripts(c.conkey, 1) AS i, c.*
                    FROM
                        pg_catalog.pg_constraint c
                ) AS con
                INNER JOIN pg_catalog.pg_class cls
                    ON con.conrelid = cls.oid
                INNER JOIN pg_catalog.pg_namespace nsp
                    ON cls.relnamespace = nsp.oid
                INNER JOIN pg_catalog.pg_attribute att
                    ON att.attrelid = cls.oid
                    AND att.attnum = con.conkey[con.i]
                INNER JOIN pg_catalog.pg_class rcls
                    ON con.confrelid = rcls.oid
                INNER JOIN pg_catalog.pg_namespace rnsp
                    ON rcls.relnamespace = rnsp.oid
                INNER JOIN pg_catalog.pg_attribute ratt
                    ON ratt.attrelid = rcls.oid
                    AND ratt.attnum = con.confkey[con.i]
            WHERE
                con.conrelid <> 0
                AND cls.relkind = 'r'
                AND rcls.relkind = 'r'
                AND con.contype = 'f'
                AND NOT pg_is_other_temp_schema(nsp.oid)
                AND NOT pg_is_other_temp_schema(rnsp.oid)
            ORDER BY
                nsp.nspname,
                cls.relname,
                con.conname,
                con.i
        """)
        for row in self.fetch_some(cursor):
            yield ForeignKeyCol(*row)

    def get_checks(self):
        """Retrieves the details of checks stored in the database.

        Override this function to return a list of Check tuples containing
        details of the checks defined in the database. Check tuples contain the
        following named fields:

        table_schema  -- The schema of the table containing the check
        table_name    -- The name of the table containing the check
        name          -- The name of the check
        owner*        -- The name of the user who owns the check
        system        -- True if the check is system maintained (bool)
        created*      -- When the check was created (datetime)
        description*  -- Descriptive text
        sql*          -- The SQL expression that the check enforces

        * Optional (can be None)
        """
        for row in super(InputPlugin, self).get_checks():
            yield row
        cursor = self.connection.cursor()
        cursor.execute(r"""
            SELECT
                nsp.nspname                               AS tabname,
                cls.relname                               AS tabname,
                con.conname                               AS checkname,
                own.rolname                               AS owner,
                CASE
                    WHEN nsp.nspname LIKE 'pg_%' THEN true
                    WHEN nsp.nspname = 'information_schema' THEN true
                    ELSE false
                END                                       AS system,
                CAST(NULL AS TIMESTAMP)                   AS created,
                obj_description(con.oid, 'pg_constraint') AS description,
                regexp_replace(
                    pg_get_constraintdef(con.oid),
                    E'^CHECK\\s*\\((.*)\\)$', E'\\1')     AS sql
            FROM
                pg_catalog.pg_constraint con
                INNER JOIN pg_catalog.pg_class cls
                    ON con.conrelid = cls.oid
                INNER JOIN pg_catalog.pg_namespace nsp
                    ON cls.relnamespace = nsp.oid
                INNER JOIN pg_catalog.pg_authid own
                    ON cls.relowner = own.oid
            WHERE
                cls.relkind = 'r'
                AND con.contype = 'c'
                AND NOT pg_is_other_temp_schema(nsp.oid)
        """)
        for row in self.fetch_some(cursor):
            yield Check(*row)

    def get_check_cols(self):
        """Retrieves the list of columns belonging to checks.

        Override this function to return a list of CheckCol tuples detailing
        the columns that are referenced by each check in the database. CheckCol
        tuples contain the following named fields:

        const_schema -- The schema of the table containing the check
        const_table  -- The name of the table containing the check
        const_name   -- The name of the check
        name         -- The name of the column
        """
        for row in super(InputPlugin, self).get_check_cols():
            yield row
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT
                nsp.nspname      AS tabschema,
                cls.relname      AS tabname,
                con.conname      AS keyname,
                att.attname      AS colname
            FROM
                (
                    SELECT
                        generate_subscripts(c.conkey, 1) AS i, c.*
                    FROM
                        pg_catalog.pg_constraint c
                ) AS con
                INNER JOIN pg_catalog.pg_class cls
                    ON con.conrelid = cls.oid
                INNER JOIN pg_catalog.pg_namespace nsp
                    ON cls.relnamespace = nsp.oid
                INNER JOIN pg_catalog.pg_attribute att
                    ON att.attrelid = cls.oid
                    AND att.attnum = con.conkey[con.i]
            WHERE
                con.conrelid <> 0
                AND cls.relkind = 'r'
                AND con.contype = 'c'
                AND NOT pg_is_other_temp_schema(nsp.oid)
        """)
        for row in self.fetch_some(cursor):
            yield CheckCol(*row)

    def get_functions(self):
        """Retrieves the details of functions stored in the database.

        Override this function to return a list of Function tuples containing
        details of the functions defined in the database (including system
        functions). Function tuples contain the following named fields:

        schema         -- The schema of the function
        specific       -- The unique name of the function in the schema
        name           -- The (potentially overloaded) name of the function
        owner*         -- The name of the user who owns the function
        system         -- True if the function is system maintained (bool)
        created*       -- When the function was created (datetime)
        description*   -- Descriptive text
        deterministic* -- True if the function is deterministic (bool)
        ext_action*    -- True if the function has an external action (affects
                          things outside the database) (bool)
        null_call*     -- True if the function is called on NULL input (bool)
        access*        -- 'N' if the function contains no SQL
                          'C' if the function contains database independent SQL
                          'R' if the function contains SQL that reads the db
                          'M' if the function contains SQL that modifies the db
        sql*           -- The SQL statement that defined the function
        func_type      -- The type of the function:
                          'C' = Column/aggregate function
                          'R' = Row function
                          'T' = Table function
                          'S' = Scalar function

        * Optional (can be None)
        """
        for row in super(InputPlugin, self).get_functions():
            yield row
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT
                nsp.nspname                         AS funcschema,
                pro.proname || pro.oid              AS funcspecname,
                pro.proname                         AS funcname,
                own.rolname                         AS owner,
                CASE
                    WHEN nsp.nspname LIKE 'pg_%' THEN true
                    WHEN nsp.nspname = 'information_schema' THEN true
                    ELSE false
                END                                 AS system,
                CAST(NULL AS TIMESTAMP)             AS created,
                obj_description(pro.oid, 'pg_proc') AS description,
                CASE pro.provolatile
                    WHEN 'v' THEN false
                    ELSE true
                END                                 AS deterministic,
                CASE pro.provolatile
                    WHEN 'v' then true
                    ELSE false
                END                                 AS extaction,
                pro.proisstrict                     AS nullcall,
                'M'                                 AS access,
                CASE pro.proisagg
                    WHEN true THEN NULL
                    ELSE pg_get_functiondef(pro.oid)
                END                                 AS sql,
                CASE pro.proretset
                    WHEN true THEN 'T'
                    ELSE
                        CASE pro.proisagg
                            WHEN true THEN 'C'
                            ELSE 'S'
                        END
                END                                 AS functype
            FROM
                pg_catalog.pg_proc pro
                INNER JOIN pg_catalog.pg_namespace nsp
                    ON pro.pronamespace = nsp.oid
                INNER JOIN pg_catalog.pg_authid own
                    ON pro.proowner = own.oid
            WHERE
                NOT pg_is_other_temp_schema(nsp.oid)
        """)
        for row in self.fetch_some(cursor):
            yield Function(*row)

    def get_procedures(self):
        """Retrieves the details of stored procedures in the database.

        Override this function to return a list of Procedure tuples containing
        details of the procedures defined in the database (including system
        procedures). Procedure tuples contain the following named fields:

        schema         -- The schema of the procedure
        specific       -- The unique name of the procedure in the schema
        name           -- The (potentially overloaded) name of the procedure
        owner*         -- The name of the user who owns the procedure
        system         -- True if the procedure is system maintained (bool)
        created*       -- When the procedure was created (datetime)
        description*   -- Descriptive text
        deterministic* -- True if the procedure is deterministic (bool)
        ext_action*    -- True if the procedure has an external action (affects
                          things outside the database) (bool)
        null_call*     -- True if the procedure is called on NULL input
        access*        -- 'N' if the procedure contains no SQL
                          'C' if the procedure contains database independent SQL
                          'R' if the procedure contains SQL that reads the db
                          'M' if the procedure contains SQL that modifies the db
        sql*           -- The SQL statement that defined the procedure

        * Optional (can be None)
        """
        for row in super(InputPlugin, self).get_procedures():
            yield row
        # PostgreSQL doesn't distinguish between functions and procedures.
        # Easier to treat all routines as functions for our purposes

    def get_routine_params(self):
        """Retrieves the list of parameters belonging to routines.

        Override this function to return a list of RoutineParam tuples
        detailing the parameters that are associated with each routine in the
        database. RoutineParam tuples contain the following named fields:

        routine_schema   -- The schema of the routine
        routine_specific -- The unique name of the routine in the schema
        param_name       -- The name of the parameter
        type_schema      -- The schema of the parameter's datatype
        type_name        -- The name of the parameter's datatype
        size*            -- The length of the parameter for character types, or
                            the numeric precision for decimal types (None if not
                            a character or decimal type)
        scale*           -- The maximum scale for decimal types (None if not a
                            decimal type)
        codepage*        -- The codepage of the parameter for character types
                            (None if not a character type)
        direction        -- 'I' = Input parameter
                            'O' = Output parameter
                            'B' = Input & output parameter
                            'V' = Variadic parameter
                            'R' = Return value/column
        description*     -- Descriptive text

        Note that the each tuple details one parameter belonging to a routine.
        It is important that the list of tuples is in the order that each
        parameter is declared in the routine.

        This is slightly complicated by the fact that the return column(s) of a
        routine are also considered parameters (see the direction field above).
        It does not matter if parameters and return columns are interspersed in
        the result provided that, taken separately, each set of parameters or
        columns is in the correct order.

        * Optional (can be None)
        """
        for row in super(InputPlugin, self).get_routine_params():
            yield row
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT
                nsp.nspname                     AS routineschema,
                pro.proname || pro.oid          AS routinespecname,
                COALESCE(NULLIF(pro.proargnames[pro.i], ''), 'p' || pro.i) AS parmname,
                tns.nspname                     AS typeschema,
                typ.typname                     AS typename,
                CAST(NULL AS INTEGER)           AS size,
                CAST(NULL AS INTEGER)           AS scale,
                CASE pro.proallargtypes[pro.i]
                    WHEN 1042 THEN pg_encoding_to_char(db.encoding)
                    WHEN 1043 THEN pg_encoding_to_char(db.encoding)
                END                             AS codepage,
                UPPER(
                    CASE pro.proargmodes[pro.i]
                        WHEN 't' THEN 'o'
                        ELSE pro.proargmodes[pro.i]
                    END
                )                               AS direction,
                CAST(NULL AS TEXT)              AS description
            FROM
                (
                    SELECT
                        generate_subscripts(p.proallargtypes, 1) AS i, p.*
                    FROM
                        (
                            SELECT
                                oid,
                                proname,
                                pronamespace,
                                COALESCE(
                                    proallargtypes,
                                    ('{0}'::oid[] || proargtypes::oid[])[2:array_length(proargtypes, 1) + 1]
                                ) AS proallargtypes,
                                COALESCE(
                                    proargnames,
                                    array_fill(''::text, array[array_length(COALESCE(proallargtypes, proargtypes), 1)])
                                ) AS proargnames,
                                COALESCE(
                                    proargmodes::char[],
                                    array_fill('i'::char, array[array_length(proargtypes, 1)])
                                ) AS proargmodes
                            FROM
                                pg_catalog.pg_proc
                        ) AS p
                ) AS pro
                INNER JOIN pg_catalog.pg_namespace nsp
                    ON pro.pronamespace = nsp.oid
                INNER JOIN pg_catalog.pg_type typ
                    ON pro.proallargtypes[pro.i] = typ.oid
                INNER JOIN pg_catalog.pg_namespace tns
                    ON typ.typnamespace = tns.oid
                INNER JOIN pg_catalog.pg_database db
                    ON db.datname = current_database()
            WHERE
                NOT pg_is_other_temp_schema(nsp.oid)
            ORDER BY
                nsp.nspname,
                pro.proname || pro.oid,
                pro.i
        """)
        for row in self.fetch_some(cursor):
            yield RoutineParam(*row)
        # XXX Need to deal with "return" parameters, in particular how a
        # set-function (aka a table function) deals with its return columns

    def get_triggers(self):
        """Retrieves the details of table triggers in the database.

        Override this function to return a list of Trigger tuples containing
        details of the triggers defined in the database (including system
        triggers). Trigger tuples contain the following named fields:

        schema          -- The schema of the trigger
        name            -- The unique name of the trigger in the schema
        owner*          -- The name of the user who owns the trigger
        system          -- True if the trigger is system maintained (bool)
        created*        -- When the trigger was created (datetime)
        description*    -- Descriptive text
        relation_schema -- The schema of the relation that activates the trigger
        relation_name   -- The name of the relation that activates the trigger
        when            -- When the trigger is fired:
                           'A' = After the event
                           'B' = Before the event
                           'I' = Instead of the event
        event           -- What statement fires the trigger:
                           'I' = The trigger fires on INSERT
                           'U' = The trigger fires on UPDATE
                           'D' = The trigger fires on DELETE
        granularity     -- The granularity of trigger executions:
                           'R' = The trigger fires for each row affected
                           'S' = The trigger fires once per activating statement
        sql*            -- The SQL statement that defined the trigger

        * Optional (can be None)
        """
        for row in super(InputPlugin, self).get_triggers():
            yield row
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT
                RTRIM(TRIGSCHEMA)  AS TRIGSCHEMA,
                RTRIM(TRIGNAME)    AS TRIGNAME,
                RTRIM(%(owner)s)   AS OWNER,
                CHAR('N')          AS SYSTEM,
                CHAR(CREATE_TIME)  AS CREATED,
                REMARKS            AS DESCRIPTION,
                RTRIM(TABSCHEMA)   AS TABSCHEMA,
                RTRIM(TABNAME)     AS TABNAME,
                TRIGTIME           AS TRIGTIME,
                TRIGEVENT          AS TRIGEVENT,
                GRANULARITY        AS GRANULARITY,
                TEXT               AS SQL
            FROM
                %(schema)s.TRIGGERS
            WHERE
                VALID <> 'X'
            WITH UR""" % self.query_subst)
        for (
                schema,
                name,
                owner,
                system,
                created,
                desc,
                tabschema,
                tabname,
                trigtime,
                trigevent,
                granularity,
                sql,
            ) in self.fetch_some(cursor):
            yield Trigger(
                make_str(schema),
                make_str(name),
                make_str(owner),
                make_bool(system),
                make_datetime(created),
                make_str(desc),
                make_str(tabschema),
                make_str(tabname),
                make_str(trigtime),
                make_str(trigevent),
                make_str(granularity),
                make_str(sql),
            )

    def get_trigger_dependencies(self):
        """Retrieves the details of trigger dependencies.

        Override this function to return a list of TriggerDep tuples containing
        details of the relations upon which triggers depend (the tables that a
        trigger references in its body). TriggerDep tuples contain the
        following named fields:

        trig_schema  -- The schema of the trigger
        trig_name    -- The name of the trigger
        dep_schema   -- The schema of the relation upon which the trigger depends
        dep_name     -- The name of the relation upon which the trigger depends
        """
        for row in super(InputPlugin, self).get_trigger_dependencies():
            yield row
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT
                RTRIM(TD.TRIGSCHEMA) AS TRIGSCHEMA,
                RTRIM(TD.TRIGNAME)   AS TRIGNAME,
                RTRIM(TD.BSCHEMA)    AS DEPSCHEMA,
                RTRIM(TD.BNAME)      AS DEPNAME
            FROM
                %(schema)s.TRIGDEP TD
                INNER JOIN %(schema)s.TRIGGERS T
                    ON TD.TRIGSCHEMA = T.TRIGSCHEMA
                    AND TD.TRIGNAME = T.TRIGNAME
            WHERE
                TD.BTYPE IN ('A', 'N', 'T', 'V')
                AND T.VALID <> 'X'
                AND NOT (TD.BSCHEMA = T.TABSCHEMA AND TD.BNAME = T.TABNAME)
            WITH UR""" % self.query_subst)
        for (
                schema,
                name,
                depschema,
                depname
            ) in self.fetch_some(cursor):
            yield TriggerDep(
                make_str(schema),
                make_str(name),
                make_str(depschema),
                make_str(depname),
            )

    def get_tablespaces(self):
        """Retrieves the details of the tablespaces in the database.

        Override this function to return a list of Tablespace tuples containing
        details of the tablespaces defined in the database (including system
        tablespaces). Tablespace tuples contain the following named fields:

        tbspace       -- The tablespace name
        owner*        -- The name of the user who owns the tablespace
        system        -- True if the tablespace is system maintained (bool)
        created*      -- When the tablespace was created (datetime)
        description*  -- Descriptive text
        type*         -- The type of the tablespace as free text

        * Optional (can be None)
        """
        for row in super(InputPlugin, self).get_tablespaces():
            yield row
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT
                RTRIM(TBSPACE)    AS TBSPACE,
                RTRIM(%(owner)s)  AS OWNER,
                CASE TBSPACE
                    WHEN 'SYSCATSPACE' THEN 'Y'
                    WHEN 'SYSTOOLSPACE' THEN 'Y'
                    ELSE 'N'
                END               AS SYSTEM,
                CHAR(CREATE_TIME) AS CREATED,
                REMARKS           AS DESCRIPTION,
                CASE DATATYPE
                    WHEN 'A' THEN 'Regular'
                    WHEN 'L' THEN 'Long'
                    WHEN 'T' THEN 'System temporary'
                    WHEN 'U' THEN 'User temporary'
                    ELSE 'Unknown'
                END ||
                ' ' ||
                CASE TBSPACETYPE
                    WHEN 'D' THEN 'DMS'
                    WHEN 'S' THEN 'SMS'
                    ELSE 'unknown'
                END ||
                ' tablespace with ' ||
                RTRIM(CHAR(PAGESIZE / 1024)) ||
                'k page size' ||
                CASE DROP_RECOVERY
                    WHEN 'Y' THEN ' and drop recovery'
                    ELSE ''
                END               AS TYPE
            FROM
                %(schema)s.TABLESPACES

            UNION ALL

            SELECT
                'NICKNAMESPACE',
                'SYSIBM',
                'N',
                CHAR(CREATE_TIME),
                'Fake tablespace which contains all nicknames in the database',
                'Fake tablespace'
            FROM
                %(schema)s.TABLESPACES
            WHERE
                TBSPACE = 'SYSCATSPACE'
                AND EXISTS (
                    SELECT 1
                    FROM SYSCAT.TABLES
                    WHERE TYPE = 'N'
                    FETCH FIRST 1 ROW ONLY
                )
            WITH UR""" % self.query_subst)
        for (
                tbspace,
                owner,
                system,
                created,
                desc,
                tstype,
            ) in self.fetch_some(cursor):
            yield Tablespace(
                make_str(tbspace),
                make_str(owner),
                make_bool(system),
                make_datetime(created),
                make_str(desc),
                make_str(tstype),
            )

