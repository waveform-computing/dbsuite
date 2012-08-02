============
Installation
============

dbsuite is distributed in several formats. The following sections detail
installation on a variety of platforms.


Download
========

You can find pre-built binary packages for several platforms available from
the `dbsuite development site
<http://www.waveform.org.uk/trac/dbsuite/wiki/Download>`_. Installation
instructions for specific platforms are included in the sections below.

If your platform is *not* covered by one of the sections below, rastools is
also available from PyPI and can therefore be installed with the ``pip`` or
``easy_install`` tools::

   $ pip install dbsuite

   $ easy_install dbsuite


Pre-requisites
==============

dbsuite's dependencies are dictated largely by which relational databases you
wish to use it with. The packages required (and their associated functionality)
are as follows:

 * SQLite support is built into the Python core libraries

 * ibm_db - required for IBM DB2 support

 * psycopg2 or pg8000 - required for PostgreSQL support

 * pygraphviz is required for most HTML-based output


Ubuntu Linux
============

For Ubuntu Linux it is simplest to install from the PPA as follows::

    $ sudo add-apt-repository ppa://waveform/ppa
    $ sudo apt-get update
    $ sudo apt-get install dbsuite

Development
-----------

If you wish to develop rastools, you can install the pre-requisites, construct
a virtualenv sandbox, and check out the source code from subversion with the
following command lines::

   # Install the pre-requisites
   $ sudo apt-get install python-pygraphviz python-virtualenv python-sphinx make subversion

   # Construct and activate a sandbox with access to the packages we just
   # installed
   $ virtualenv --system-site-packages sandbox
   $ source sandbox/bin/activate

   # Check out the source code and install it in the sandbox for development and testing
   $ svn co http://www.waveform.org.uk/svn/dbsuite/trunk dbsuite
   $ cd dbsuite
   $ make develop


Microsoft Windows
=================

XXX To be written


Apple Mac OS X
==============

XXX To be written

