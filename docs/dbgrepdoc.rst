=========
dbgrepdoc
=========

dbgrepdoc is a utility for extracting all statements related to documentation
from an SQL script; that is to say it extracts CONNECT, SET SCHEMA, and COMMENT
statements.


Synopsis
========

::

  $ dbgrepdoc [options] script...


Description
===========

Extract all documentation related statements from *script*, writing them to
stdout. If no script is specified or *script* is ``-`` then the utility will
read SQL from stdin.

.. program:: dbgrepdoc

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

    Run dbgrepdoc under PDB, the Python debugger. Generally only useful for
    developers. Also note that in this mode, debug entries will be output to
    stderr as well, which results in a lot of output

.. option:: -t, --terminator TERMINATOR

    Specify the statement terminator used within the SQL file. If not given,
    this defaults to semi-colon (;).
