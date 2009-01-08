#!/usr/bin/env python
# vim: set noet sw=4 ts=4:

"""Flexible documentation generator for IBM DB2.

db2makedoc is a command line application for generating documentation
from IBM DB2 databases (although theoretically it could be extended to
support other databases) in a variety of formats. The application is
modular including a plugin framework for input and output."""

import ez_setup
ez_setup.use_setuptools(version='0.6c6') # install setuptools if it isn't already installed

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
		'db2makedoc = db2makedoc.main:db2makedoc_main',
		'db2tidysql = db2makedoc.main:db2tidysql_main',
	]
}

def get_console_scripts():
	import re
	for s in entry_points['console_scripts']:
		print re.match(r'^([^= ]*) ?=.*$', s).group(1)

def main():
	from setuptools import setup, find_packages
	from db2makedoc.main import __version__
	setup(
		name                 = 'db2makedoc',
		version              = __version__,
		description          = 'Flexible documentation generator for IBM DB2',
		long_description     = __doc__,
		author               = 'Dave Hughes',
		author_email         = 'dave_hughes@uk.ibm.com',
		url                  = 'http://faust.hursley.uk.ibm.com/trac/db2makedoc/',
		packages             = find_packages(),
		include_package_data = True,
		platforms            = 'ALL',
		zip_safe             = False,
		entry_points         = entry_points,
		classifiers          = classifiers
	)

if __name__ == '__main__':
	main()
