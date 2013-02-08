#!/usr/bin/env python
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

from __future__ import (
    unicode_literals,
    print_function,
    absolute_import,
    division,
    )

import os
from setuptools import setup, find_packages
from utils import description, get_version, require_python

HERE = os.path.abspath(os.path.dirname(__file__))

# Workaround <http://bugs.python.org/issue10945>
import codecs
try:
    codecs.lookup('mbcs')
except LookupError:
    ascii = codecs.lookup('ascii')
    func = lambda name, enc=ascii: {True: enc}.get(name=='mbcs')
    codecs.register(func)

require_python(0x020600f0)

REQUIRES = [
    'PIL',
    'pygraphviz',
    ]

EXTRA_REQUIRES = {
    'db2': ['ibm-db'],
    'pgsql': ['pg8000'],
    'completion': ['optcomplete'],
    }

CLASSIFIERS = [
    'Development Status :: 5 - Production/Stable',
    'Environment :: Console',
    'Environment :: Web Environment',
    'Intended Audience :: System Administrators',
    'Intended Audience :: Developers',
    'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
    'Operating System :: Microsoft :: Windows',
    'Operating System :: POSIX',
    'Operating System :: Unix',
    'Programming Language :: Python :: 2.6',
    'Programming Language :: Python :: 2.7',
    'Programming Language :: SQL',
    'Programming Language :: JavaScript',
    'Programming Language :: PHP',
    'Topic :: Database',
    'Topic :: Documentation',
    'Topic :: Text Processing :: Markup :: XML',
    'Topic :: Text Processing :: Markup :: HTML',
    'Topic :: Text Processing :: Markup :: LaTeX',
    ]

ENTRY_POINTS = {
    'console_scripts': [
        'dbmakedoc = dbsuite.main.dbmakedoc:main',
        'dbconvdoc = dbsuite.main.dbconvdoc:main',
        'dbgrepdoc = dbsuite.main.dbgrepdoc:main',
        'dbtidysql = dbsuite.main.dbtidysql:main',
        'dbexec = dbsuite.main.dbexec:main',
        ]
    }


def main():
    setup(
        name                 = 'dbsuite',
        version              = get_version(os.path.join(HERE, 'dbsuite/__init__.py')),
        description          = 'A suite of tools for maintenance of information warehouses',
        long_description     = description(os.path.join(HERE, 'README.rst')),
        classifiers          = CLASSIFIERS,
        author               = 'Dave Hughes',
        author_email         = 'dave@waveform.org.uk',
        url                  = 'http://www.waveform.org.uk/trac/dbsuite/',
        keywords             = 'database documentation',
        packages             = find_packages(exclude=['distribute_setup', 'utils']),
        include_package_data = True,
        platforms            = 'ALL',
        install_requires     = REQUIRES,
        extras_require       = EXTRA_REQUIRES,
        zip_safe             = False,
        test_suite           = 'dbsuite',
        entry_points         = ENTRY_POINTS,
        )

if __name__ == '__main__':
    main()
