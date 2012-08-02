=========
dbmakedoc
=========

dbmakedoc is a utility for generating documentation from the meta-data
contained in a database. Various plugins are provided for working with
different types of database (mostly DB2 oriented at the moment, but PostgreSQL
and limited SQLite support are in the works), as well as various types of
output (the HTML plugins are the most tested obviously, but plugins also exist
for XML, LaTeX/PDF, and even SQL output). The utility is configured via an
INI-style file which specifies which plugins to use, and configuration
information for those plugins (database name, username, password, output
directory, etc).


Synopsis
========

::

  dbmakedoc [options] configuration...


Description
===========

Generate documentation from the database specified in the configuration, in the
formats specified by the configuration.  At least one *configuration* file (an
INI-style file) must be specified. See the documentation for more information
on the required syntax and content of this file.

.. program:: dbmakedoc

.. option:: --version

    Outputs the application's version number and exits immediately

.. option:: -h, --help

    Outputs the help screen shown above and exits immediately

.. option:: -q, --quiet

    Specifies that only errors are to be displayed on stderr. By default both
    warnings and errors will be displayed

.. option:: -v, --verbose

    Specifies that informational items are to be displayed on stderr in
    addition to warnings and errors

.. option:: -l, --logfile LOGFILE

    Output all messages to LOGFILE. Output to the logfile is not influenced by
    --quiet or --verbose - all messages (informational, warning, and error)
    will always be included

.. option:: -D, --debug

    Run dbmakedoc under PDB, the Python debugger. Generally only useful for
    developers. Also note that in this mode, debug entries will be output to
    stderr as well, which results in a lot of output

.. option:: --list-plugins

    Lists the names of available input and output plugins along with a brief
    description of each

.. option:: --help-plugin PLUGIN

    Displays the full description of PLUGIN along with all available parameters
    (and their default values if any)

.. option:: -n, --dry-run

    Specifies that dbmakedoc should parse the provided configuration file for
    sanity but not actually generate any documentation


Tutorial
========

Basic Configuration
-------------------

As mentioned above, dbmakedoc requires an INI-style configuration file in order
to run, consisting of sections headed by square bracketed titles containing
name=value lines. Section names are arbitrary and can be anything you like, as
long as each section is named uniquely. The ordering of sections, and of values
within sections is also unimportant.

Each section MUST contain a ``plugin`` value which specifies the plugin to use
when processing that section. Blank lines and comments (prefixed by semi-colon)
will be ignored. Continuation lines can be specified by indentation.

At least two sections need to be present in a dbmakedoc configuration file, one
specifying an input plugin and another specifying an output plugin. Each output
section will be processed once for each input section. Hence, if you provide
one input section and one output section, dbmakedoc will produce one set of
documentation; if you provide two input sections and two output sections in a
configuration file, it will produce four sets of documentation (two sets of
output for each input).

Below is presented an example configuration file which will produce plain HTML
documentation for the standard SAMPLE database provided by DB2::

    [input]
    plugin=db2.luw
    ; Read metadata from the SAMPLE database
    database=SAMPLE
    ; Connect as the db2 administrative user
    username=db2inst1
    password=secret

    [output]
    plugin=html.plain
    ; Write output to the web-server's "htdocs" directory
    path=/var/www/htdocs
    ; Specify the author and copyright to include with each page
    author_name=Fred W. Flintstone
    author_email=fred@slaterockandgravel.com
    copyright=Copyright (c) 1960 B.C. Fred Flintstone. All Rights Reserved.

Things to note about this configuration:

 * It includes one input section, and one output section so one set of
   documentation will be produced

 * The names and ordering of the sections are arbitrary; it wouldn't matter if
   the section names were swapped or the orders reversed (although it might
   make the intent of the configuration somewhat confusing!)

 * Several comments have been included with semi-colon prefixes

 * The input plugin is connecting as the db2inst1 user (the usual DB2
   administrative user on Linux/UNIX). However, dbmakedoc (specifically, the
   db2.luw input plugin) doesn't require any special privileges to run - all it
   requires is the ability to SELECT from the views in the standard SYSCAT
   schema.

 * If the username and password options were ommitted, and the database was
   hosted on the same machine that dbmakedoc was running on, it would use an
   "implicit" connection; connecting as the currently logged on user. This is
   the preferable way to use dbmakedoc as it means that you don't need to leave
   passwords lying around in plain-text files. If you do choose to specify a
   username and password in a dbmakedoc configuration file, be careful to
   protect the file with permissions, and/or use an unprivileged
   (non-administrative) user that only has the ability to read the SYSCAT
   views.

If this configuration were stored in a file named sample.ini it could be
executed with the following command line::

    $ dbmakedoc sample.ini

By default, dbmakedoc produces very little console output (unless an error
occurs). If you want to see more information on dbmakedoc's progress, use the
:option:`-v` command line switch::

    $ dbmakedoc -v sample.ini

Advanced Configuration
----------------------

Now for a more complex example. This example again reads data from the SAMPLE
database, but only includes documentation for schemas whose name beings with
"SYS", and the "DB2INST1" schema. It includes the same html.plain output
section as above, but now also includes an additional section using the html.w3
output plugin (which produces documentation in the IBM w3v8 style). The latter
section includes configuration options for producing:

 * diagrams for tables, views, and aliases (relations)

 * alphabetical indexes of all objects, relations, and constraints

 * a full-text search database for searching the documentation

 * a "related links" section containing a link to the DB2 for LUW InfoCenter,
   and

 * several additional navigation links (to BluePages, w3 search engine, and the
   plain documentation generated by the first output section)

 * output in directories named after the input database

::

    [input]
    plugin=db2.luw
    database=SAMPLE
    username=db2inst1
    password=secret
    include=SYS*,DB2INST1

    ; NOTE: Output sections must be named uniquely
    [output_plain]
    plugin=html.plain
    ; Output to a "plain" sub-directory under a directory named after the database
    path=/var/www/htdocs/${dblower}/plain
    author_name=Fred W. Flintstone
    author_email=fred@slaterockandgravel.com
    copyright=Copyright (c) 1960 B.C. Fred Flintstone. All Rights Reserved.

    [output_w3]
    plugin=html.w3
    ; Output to a "w3" sub-directory under a directory named after the database
    path=/var/www/htdocs/${dblower}/w3
    author_name=Fred W. Flintstone
    author_email=fred@slaterockandgravel.com
    copyright=Copyright (c) 1960 B.C. Fred Flintstone. All Rights Reserved.
    diagrams=relations
    indexes=all,fields,relations,tables,views,constraints
    search=yes
    home_title=w3 Home
    home_url=http://w3.ibm.com/
    ; This configuration item demonstrates continuation lines for long values.
    ; It specifies the structure of the left-hand navigation menu. The dbmakedoc
    ; documentation appear in the position of the '#' item (w3 Style):
    menu_items=
        BluePages=http://w3.ibm.com/bluepages,
        Plain Style=/plain/db.html,
        w3 Style=#,
        Search w3=http://w3.ibm.com/search
    related_items=
        DB2 9.5 InfoCenter=http://publib.boulder.ibm.com/infocenter/db2luw/v9r5/index.jsp

Note that the path options in output_plain and output_w3 sections include a
substitution variable: ``${dblower}``. This indicates that the name of the
input database, transformed to lowercase, should be substituted in this
location.  Hence the output for the ``[output_plain]`` section will actually be
written to ``/var/www/htdocs/sample/plain/``, and output for the
``[output_w3]`` section will go to ``/var/www/htdocs/sample/w3/``.

This also demonstrates how each output section is executed for each input
section. In the first configuration file there was one input and one output
section, so one set of documentation was produced. In this file there is one
input section, and two output sections, so two sets of documentation will be
produced. If we had a file with two input sections, and three output sections,
6 sets of documentation would be produced, as illustrated in the graph below
(each line represents a set of documentation that would be produced)::

    ,--------.           ,---------.
    | input1 |-------+-->| output1 |
    '--------'\     /    '---------'
               \   /
                \ /      ,---------.
                 X------>| output2 |
                / \      '---------'
               /   \
    ,--------./     \    ,---------.
    | input3 |-------+-->| output2 |
    '--------'           '---------'

As mentioned above, the ordering of sections in the input file is arbitrary,
and likewise so is the order of execution by dbmakedoc. The only rule is
(obviously) that input sections are processed before output sections. Hence,
don't be surprised if dbmakedoc doesn't process sections in the same order as
you place them in the configuration.

Database Comments
-----------------

While the documentation generated by dbmakedoc can be useful even without any
database comments, it is considerably more useful if the database is well
commented (especially when using extended features like the full-text search
database). Commenting a database is not technically difficult, but usually
involves quite a bit of work - especially for existing databases without any
comments! I strongly recommend that developers produce comments for databases
they are desigining while designing them (if only to get into the habit of
updating comments whenever adding / changing structures; this helps avoid
"stale" or incorrect comments in the documentation after changes are made to a
database structure).

Commenting structures in DB2 for LUW is quite simple. For example, to add
comments to the DB2INST1.DEPARTMENT table in the SAMPLE database, one could use
the following SQL::

    CONNECT TO SAMPLE;

    COMMENT ON TABLE  DB2INST1.DEPARTMENT IS 'Contains details of all departments in the company';
    COMMENT ON DB2INST1.DEPARTMENTS (
      DEPTNO   IS 'Department number (unique)',
      DEPTNAME IS 'Name describing general activities of department',
      MGRNO    IS 'Employee number of department manager',
      ADMRDEPT IS 'Department to which this department reports',
      LOCATION IS 'Name of the remote location'
    );

Note that you can specify comments for all columns in a table / view in a
single statement. dbmakedoc allows the use of a rudimentary form of markup in
comments for highlighting and linking. Specifically:

``*bold*``
    Words surrounded by asterisks are rendered in bold

``/italic/``
    Words surrounded by slashes are rendered in italic

``_underline_``
    Words surrounded by underscores are rendered with an underline

``@links``
    Database object names prefixed with an at-symbol become links in documentation formats that support it (e.g. HTML)

As an example, consider the following enhanced version of the comments above::

    CONNECT TO SAMPLE;

    COMMENT ON TABLE  DB2INST1.DEPARTMENT IS 'Contains details of all departments in the company';
    COMMENT ON DB2INST1.DEPARTMENTS (
      DEPTNO   IS 'Department number *unique*',
      DEPTNAME IS 'Name describing general activities of department',
      MGRNO    IS 'Employee number of department manager (see @DB2INST1.EMPLOYEE)',
      ADMRDEPT IS 'Department to which this department reports',
      LOCATION IS 'Name of the /remote/ location'
    );

In this version, the word "unique" in the DEPTNO column's comment will be
rendered in bold, and the word "remote" in the LOCATION comment will be
rendered italic. Finally, the comment for the MGRNO column will include a link
to the documentation for the DB2INST1.EMPLOYEE table.

I recommend keeping comments for database objects together with the DDL for
those objects. This might seem counter-intuitive in that if the DDL is updated
it is rarely run directly to update an existing database, however with the aid
of the dbgrepdoc utility, also provided in this suite, COMMENT statements can
be easily separated from other DDL statements to allow easy maintenance of
documentation.
