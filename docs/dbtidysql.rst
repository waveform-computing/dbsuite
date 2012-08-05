=========
dbtidysql
=========

dbtidysql is a utility for re-indenting and formatting SQL to improve its
readability.


Synopsis
========

::

  $ dbtidysql [options] files...


Description
===========

Parse each file given, reformatting it for readability. All output is written
to stdout for redirection.

.. program:: dbtidysql

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

    Run dbtidysql under PDB, the Python debugger. Generally only useful for
    developers. Also note that in this mode, debug entries will be output to
    stderr as well, which results in a lot of output

.. option:: -t, --terminator TERMINATOR

    Specify the statement terminator used within the SQL file. If not given,
    this defaults to semi-colon (;).
