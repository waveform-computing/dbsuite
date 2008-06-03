#!/usr/bin/env python
# vim: set noet sw=4 ts=4:

import sys
import os
import subprocess
from distutils.core import setup
from db2makedoc.main import __version__

name = 'db2makedoc'

description = 'Flexible documentation generator for IBM DB2'

long_description = \
"""Flexible documentation generator for IBM DB2.

db2makedoc is a command line application for generating documentation
from IBM DB2 databases (although theoretically it could be extended to
support other databases) in a variety of formats. The application is
modular including a plugin framework for input and output."""

packages=[
	'db2makedoc',
	'db2makedoc.sql',
	'db2makedoc.plugins',
	'db2makedoc.plugins.db2',
	'db2makedoc.plugins.db2.luw',
	'db2makedoc.plugins.html',
	'db2makedoc.plugins.html.w3',
	'db2makedoc.plugins.html.plain',
	'db2makedoc.plugins.metadata',
	'db2makedoc.plugins.metadata.input',
	'db2makedoc.plugins.metadata.output',
	'db2makedoc.plugins.template',
]

scripts = ['bin/db2makedoc']

data_files = []

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

	# Horrible hack to add post-installation script and documentation to the
	# Windows installer. This won't work in several places it should, but it'll
	# work with the included Makefile so it'll do for now
	if (len(sys.argv) >= 2 and sys.argv[1] == 'bdist_wininst') or \
		(len(sys.argv) >= 3 and sys.argv[1] == 'bdist' and sys.argv[2] == '--formats=wininst'):
		global scripts
		global data_files
		# Add the post-installation script to the scripts list
		scripts.append('bin/db2makedoc_postinstall.py')
		# If necessary, regenerate the MANIFEST
		if not os.access('MANIFEST', os.F_OK) or \
			os.stat('MANIFEST.in').st_mtime > os.stat('MANIFEST').st_mtime:
			if subprocess.Popen([sys.executable, sys.argv[0], 'sdist', '--manifest-only']).wait() != 0:
				raise Exception('Failed to generate MANIFEST')
		# Read the MANIFEST
		manifest = open('MANIFEST', 'rU')
		try:
			files = set([line.rstrip() for line in manifest])
		finally:
			manifest.close()
		# Filter out scripts, setup stuff, and package modules from the
		# MANIFEST list, leaving documentation files
		files -= set(scripts)
		files.discard(sys.argv[0])
		files.discard('setup.cfg')
		files.discard('MANIFEST.in')
		files.discard('MANIFEST')
		doc_files = set()
		for file in files:
			if not '.'.join(file.split('/')[:-1]) in packages:
				doc_files.add(file)
		# Add the documentation files to the data_files list with an
		# appropriate path for Windows
		doc_paths = {}
		for file in doc_files:
			doc_path = '/'.join(file.split('/')[:-1])
			if not doc_path in doc_paths:
				doc_paths[doc_path] = []
			doc_paths[doc_path].append(file)
		doc_prefix = 'Doc/%s-%s' % (name, __version__)
		for path in doc_paths:
			data_files.append(('%s/%s' % (doc_prefix, path), doc_paths[path]))

	setup(
		name=name,
		version=__version__,
		description=description,
		long_description=long_description,
		author='Dave Hughes',
		author_email='dave_hughes@uk.ibm.com',
		url='http://faust.hursley.uk.ibm.com/trac/db2makedoc/',
		packages=packages,
		scripts=scripts,
		data_files=data_files,
		platforms='ALL',
		classifiers=classifiers
	)

if __name__ == '__main__':
	main()
