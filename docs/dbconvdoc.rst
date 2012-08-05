=========
dbconvdoc
=========

dbconvdoc is a simple utility for extracting comments for the SYSCAT and
SYSSTAT schemas from the IBM DB2 documentation pages available on the Internet.


Synopsis
========

::

  $ dbconvdoc [options] source converter


Description
===========

Extract the documentation from *source* and use *converter* to generate the
output. All output is written to stdout for redirection.

.. program:: dbconvdoc

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

    Run dbconvdoc under PDB, the Python debugger. Generally only useful for
    developers. Also note that in this mode, debug entries will be output to
    stderr as well, which results in a lot of output

.. option:: --list-sources

    list all available sources

.. option:: --help-source=SOURCE

    display more information about the named source

.. option:: --list-converters

    list all available converters

.. option:: --help-converter=CONV

    display more information about the named converter

