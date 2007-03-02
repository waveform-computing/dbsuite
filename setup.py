# $Header$
# vim: set noet sw=4 ts=4:

from distutils.core import setup

long_description = \
"""Flexible documentation generator for IBM DB2.

db2makedoc is a command line application for generating documentation for IBM
DB2 databases (although theoretically it could be extended to support other
databases) in a variety of formats. The application is modular including a
plugin framework for input and output. Currently output plugins are provided
for several HTML styles and 'kid' XML templates, and a single input plugin is
provided for IBM DB2 UDB v8+ for Linux/UNIX/Windows"""

def main():
	setup(
		name='db2makedoc',
		version='1.0.0pr1',
		description='Flexible documentation generator for IBM DB2',
		long_description=long_description,
		author='Dave Hughes',
		author_email='dave@waveform.plus.com',
		platforms='ALL',
		packages=[
			'db2makedoc',
			'db2makedoc.db',
			'db2makedoc.dot',
			'db2makedoc.highlighters',
			'db2makedoc.sql',
			'db2makedoc.plugins',
			'db2makedoc.db2udbluw',
			'db2makedoc.plugins.html',
			'db2makedoc.plugins.html.w3',
			'db2makedoc.plugins.template',
		],
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
	)

if __name__ == '__main__':
	main()
