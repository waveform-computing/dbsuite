$Header$

db2makedoc
==========

db2makedoc is a command line application for generating documentation from IBM
DB2 databases (although theoretically it could be extended to support other
databases) in a variety of formats. The application is modular including a
plugin framework for input and output. Currently output plugins are provided
for several HTML styles and 'kid' XML templates, and a single input plugin is
provided for IBM DB2 UDB v8+ for Linux/UNIX/Windows.


Requirements:

	* Python 2.4 or above. May work on earlier versions, but this hasn't
	  been tested.

	  	- Python <http://www.python.org/>
	
	* For the db2udbluw input plugin (for reading meta-data from an IBM DB2
	  UDB v8+ for Linux/UNIX/Windows database), one of the following
	  database connection packages must be installed:

		- PyDB2 <http://sourceforge.net/projects/pydb2>
		- PyWin32 <http://sourceforge.net/projects/pywin32>
		- mxODBC <http://www.egenix.com/files/python/mxODBC.html>
	
	* For the template output plugin (for generating XML/HTML output from
	  kid templates) the 'kid' engine must be installed:

	  	- kid <http://www.kid-templating.org/>


Installation (Windows):

	Under Windows, simply run the executable installer and follow the
	prompts. This will install the db2makedoc packages under your Python
	installation's site-packages path and the main application script
	(db2makedoc.py) under your main Python directory (e.g. C:\Python24)
	which should be in your PATH variable. You should then be able to run
	db2makedoc from a CMD window simply by typing db2makedoc.py. For
	example, to receive information on the command line syntax:

		db2makedoc.py --help


Installation (UNIX/Linux):

	Under UNIX/Linux, extract the tarball into a convenient directory and,
	as root, run the following command:

		python setup.py install

	This will install the db2makedoc packages under your main Python
	installation's site-packages path and the main application script
	(db2makedoc.py) under the "bin" directory of Python's "prefix" path,
	typically /usr/bin or /usr/local/bin. You should then be able to run
	db2makedoc from the shell simply by typing db2makedoc.py For example,
	to receive information on the command line syntax:

		db2makedoc.py --help


Usage:

	db2makedoc requires a configuration file in order to run. Configuration
	files are simple INI-style files, consisting of sections headed by
	square bracketed titles containing name=value lines. Section names are
	arbitrary and can be anything you like, as long as each section is
	named uniquely. Each section MUST contain a "plugin" value which
	specifies the plugin to use when processing that section. Blank lines
	and comments (prefixed by semi-colon) will be ignored. Continuation
	lines can be specified by indentation
	
	At least two sections need to be present in a db2makedoc configuration
	file, one specifying an input plugin and another specifying an output
	plugin. To obtain a list of the available input and output plugins, run
	the following command:

		db2makedoc.py --help-plugins
	
	To obtain a list of the values that can be specified with a particular
	plugin, run the following command:

		db2makedoc.py --help-plugin=<plugin-name>
	
	Where <plugin-name> is the name of the plugin you wish to query. For
	example:

		db2makedoc.py --help-plugin=db2udbluw
	
	A section specifying an input plugin is used to tell db2makedoc about a
	database from which you wish to extract meta-data and generate
	documentation. A section specifying an output plugin is used to tell
	db2makedoc the format you wish to output documentation in, and the
	location you wish to write the output. Each output section will be
	processed once for each input section. Hence, if you provide two input
	sections and two output sections in a configuration file, it will
	produce *four* sets of documentation (two sets of output for each
	input).

	An example configuration file is presented below (if used as an actual
	configuration file it would have to be flush with the left margin; the
	indentation here is simply for readability):

		[MyDBInput]
		; Use the IBM DB2 UDB for Linux/UNIX/Windows input plugin
		plugin=db2udbluw
		; Connect to the MYDB database with username "admin" and
		; password "secret"
		database=MYDB
		username=admin
		password=secret

		[JavadocOutput]
		; Use the Javadoc-style HTML output plugin
		plugin=html.javadoc
		; Write all output to the web-server's "htdocs" directory
		path=/var/www/htdocs/
		; Specify author and copyright meta-data
		author=Fred W. Flintstone
		author_email=fred@slaterockandgravel.com
		copyright=Copyright (c) 1960 B.C. Fred Flintstone. All Rights
			Reserved.
	
	This configuration specifies that Javadoc-style HTML documentation will
	be generated for the MYDB database, and placed in the /var/www/htdocs
	directory (presumably the root documents directory of a web-server such
	as Apache). If this configuration were stored in a file called mydb.ini
	it could be executed with the following command line:

		db2makedoc.py mydb.ini

	Multiple configuration files can be specified on the command line.
	Additionally, several command line options are available for logging,
	debugging, verbose output, etc. Use the --help option for a summary of
	the available options.


Known Issues / Bugs:

	None currently known.


Contact Details:

	Dave Hughes <dave@waveform.plus.com>

vim: set noet sw=8 ts=8 tw=79:
