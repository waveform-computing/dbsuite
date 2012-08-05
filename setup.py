#!/usr/bin/env python
# vim: set et sw=4 sts=4:

"""Flexible documentation tools for relational databases.

dbsuite is a set of command line applications for documentation related
functions for relational databases (primarily DB2, but in the process of being
expanded to other databases). The applications are modular including an
extensible plugin framework for supporting new sources and output formats."""

try:
    from setuptools import setup, find_packages
except ImportError:
    from ez_setup import use_setuptools
    use_setuptools()
    from setuptools import setup, find_packages

classifiers = [
    'Development Status :: 5 - Production/Stable',
    'Environment :: Console',
    'Environment :: Web Environment',
    'Intended Audience :: System Administrators',
    'Intended Audience :: Developers',
    'Operating System :: Microsoft :: Windows',
    'Operating System :: POSIX',
    'Operating System :: Unix',
    'Programming Language :: Python :: 2.6',
    'Programming Language :: SQL',
    'Programming Language :: JavaScript',
    'Programming Language :: PHP',
    'Topic :: Database',
    'Topic :: Documentation',
    'Topic :: Text Processing :: Markup :: XML',
    'Topic :: Text Processing :: Markup :: HTML',
    'Topic :: Text Processing :: Markup :: LaTeX',
]

entry_points = {
    'console_scripts': [
        'dbmakedoc = dbsuite.main.dbmakedoc:main',
        'dbconvdoc = dbsuite.main.dbconvdoc:main',
        'dbgrepdoc = dbsuite.main.dbgrepdoc:main',
        'dbtidysql = dbsuite.main.dbtidysql:main',
        'dbexec = dbsuite.main.dbexec:main',
    ]
}

def get_console_scripts():
    import re
    for s in entry_points['console_scripts']:
        print re.match(r'^([^= ]*) ?=.*$', s).group(1)

def main():
    from dbsuite.main import __version__
    setup(
        name                 = 'dbsuite',
        version              = __version__,
        description          = 'A suite of tools for maintenance of information warehouses',
        long_description     = __doc__,
        author               = 'Dave Hughes',
        author_email         = 'dave@waveform.org.uk',
        url                  = 'http://www.waveform.org.uk/trac/dbsuite/',
        packages             = find_packages(exclude=['ez_setup']),
        install_requires     = ['Pillow', 'ibm-db', 'pygraphviz'],
        include_package_data = True,
        platforms            = 'ALL',
        zip_safe             = False,
        entry_points         = entry_points,
        classifiers          = classifiers
    )

if __name__ == '__main__':
    main()
