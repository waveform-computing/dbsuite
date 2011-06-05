#!/usr/bin/env python
# vim: set noet sw=4 ts=4:

"""Flexible documentation tools for relational databases.

dbsuite is a set of command line applications for documentation related
functions for relational databases (primarily DB2, but in the process of being
expanded to other databases). The applications are modular including an
extensible plugin framework for supporting new sources and output formats."""

import ez_setup
ez_setup.use_setuptools() # install setuptools if it isn't already installed

classifiers = [
	'Development Status :: 5 - Production/Stable',
	'Environment :: Console',
	'Environment :: Web Environment',
	'Intended Audience :: System Administrators',
	'Intended Audience :: Developers',
	'Operating System :: Microsoft :: Windows',
	'Operating System :: POSIX',
	'Operating System :: Unix',
	'Programming Language :: Python :: 2.5',
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
	]
}

def get_console_scripts():
	import re
	for s in entry_points['console_scripts']:
		print re.match(r'^([^= ]*) ?=.*$', s).group(1)

def main():
	from setuptools import setup, find_packages
	from dbsuite.main import __version__
	setup(
		name                 = 'dbsuite',
		version              = __version__,
		description          = 'Flexible documentation tools for relational databases',
		long_description     = __doc__,
		author               = 'Dave Hughes',
		author_email         = 'dave@waveform.org.uk',
		url                  = 'http://www.waveform.org.uk/trac/db2makedoc/',
		packages             = find_packages(),
		include_package_data = True,
		platforms            = 'ALL',
		zip_safe             = False,
		entry_points         = entry_points,
		classifiers          = classifiers
	)

if __name__ == '__main__':
	main()
