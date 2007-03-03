#!/usr/bin/env python
# $Header$
# vim: set noet sw=4 ts=4:

import sys
from distutils.core import setup

__version__ = '1.0.0pr1'

long_description = \
"""Flexible documentation generator for IBM DB2.

db2makedoc is a command line application for generating documentation from IBM
DB2 databases (although theoretically it could be extended to support other
databases) in a variety of formats. The application is modular including a
plugin framework for input and output. Currently output plugins are provided
for several HTML styles and 'kid' XML templates, and a single input plugin is
provided for IBM DB2 UDB v8+ for Linux/UNIX/Windows"""

packages=[
	'db2makedoc',
	'db2makedoc.db',
	'db2makedoc.dot',
	'db2makedoc.highlighters',
	'db2makedoc.sql',
	'db2makedoc.plugins',
	'db2makedoc.plugins.db2udbluw',
	'db2makedoc.plugins.html',
	'db2makedoc.plugins.html.w3',
	'db2makedoc.plugins.template',
]

classifiers=[
	"Development Status :: 4 - Beta",
	"Environment :: Console",
	"Intended Audience :: System Administrators",
	"Intended Audience :: Developers",
	"Operating System :: Microsoft :: Windows",
	"Operating System :: POSIX",
	"Operating System :: Unix",
	"Programming Language :: Python",
	"Programming Language :: SQL",
	"Topic :: Database",
	"Topic :: Documentation",
]

def main():
	# Patch to support classifiers in earlier Python versions
	if sys.version < '2.2.3':
		from distutils.dist import DistributionMetadata
		DistributionMetadata.classifiers = None
		DistributionMetadata.download_url = None

	setup(
		name='db2makedoc',
		version=__version__,
		description='Flexible documentation generator for IBM DB2',
		long_description=long_description,
		author='Dave Hughes',
		author_email='dave@waveform.plus.com',
		platforms='ALL',
		packages=packages,
		scripts=['db2makedoc.py'],
		classifiers=classifiers
	)

if __name__ == '__main__':
	main()
