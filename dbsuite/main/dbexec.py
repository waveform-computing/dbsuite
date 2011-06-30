# vim: set noet sw=4 ts=4:

import sys
import logging
import dbsuite.script
import dbsuite.plugins
import dbsuite.main
import ConfigParser
from dbsuite.compat import *

class MyConfigParser(ConfigParser.SafeConfigParser):
	"""Tweaked version of SaveConfigParser that uses uppercase for keys"""
	def optionxform(self, optionstr):
		return optionstr.upper()

class ExecSqlUtility(dbsuite.main.Utility):
	"""%prog [options] files...

	This utility executes multiple SQL scripts. If possible (based on a files
	produced/consumed analysis) it will run scripts in parallel, reducing
	execution time. Either specify the names of files containing the SQL to
	execute, or specify - to indicate that stdin should be read. List-files
	(prefixed with @) are also accepted as a method of specifying input files.
	"""

	def __init__(self):
		super(ExecSqlUtility, self).__init__()
		self.parser.set_defaults(
			autocommit=False,
			config='',
			deletefiles=False,
			test=0,
			retry=1,
			stoponerror=False,
			terminator=';')
		self.parser.add_option('-t', '--terminator', dest='terminator',
			help="""specify the statement terminator (default=';')""")
		self.parser.add_option("-a", "--auto-commit", dest="autocommit", action="store_true",
			help="""automatically COMMIT after each SQL statement in a script""")
		self.parser.add_option("-c", "--config", dest="config",
			help="""specify the configuration file""")
		self.parser.add_option("-d", "--delete-files", dest="deletefiles", action="store_true",
			help="""delete files produced by the scripts after execution""")
		self.parser.add_option("-n", "--dry-run", dest="test", action="count",
			help="""test but don't run the scripts, can be specified multiple times: 1x=parse, 2x=test file perms, 3x=test db logins""")
		self.parser.add_option("-r", "--retry", dest="retry",
			help="""specify the maximum number of retries after script failure (default: %default)""")
		self.parser.add_option("-s", "--stop-on-error", dest="stoponerror", action="store_true",
			help="""if a script encounters an error stop it immediately""")

	def main(self, options, args):
		super(ExecSqlUtility, self).main(options, args)
		config = {}
		if options.config:
			config = self.process_config(options.config)
		done_stdin = False
		sql_files = []
		for sql_file in args:
			if sql_file == '-':
				if not done_stdin:
					done_stdin = True
					sql_file = sys.stdin
				else:
					raise IOError('Cannot read input from stdin multiple times')
			else:
				sql_file = open(sql_file, 'rU')
			sql_files.append(sql_file)
		plugin = dbsuite.plugins.load_plugin('db2.luw')()
		job = dbsuite.script.SQLJob(plugin, sql_files, vars=config,
			terminator=options.terminator, retrylimit=options.retry,
			autocommit=options.autocommit, stoponerror=options.stoponerror,
			deletefiles=options.deletefiles)
		if options.test == 0:
			job.test_logins()
			job.test_permissions()
			job.execute()
		else:
			if options.test > 2:
				job.test_logins()
			if options.test > 1:
				job.test_permissions()
			logging.info('')
			logging.info('Dependency tree:')
			job.print_dependencies()
			logging.info('Data transfers:')
			job.print_transfers()
			for script in job.depth_traversal():
				logging.info('')
				logging.info(script.filename)
				# Write SQL to stdout so it can be redirected if necessary
				sys.stdout.write(script.sql)
		return 0

	def handle(self, type, value, tb):
		"""Exception hook for non-debug mode."""
		if issubclass(type, (dbsuite.script.Error,)):
			# For script errors, just output the message which should be
			# sufficient for the end user (no need to confuse them with a full
			# stack trace)
			logging.critical(str(value))
			return 3
		else:
			super(ExecSqlUtility, self).handle(type, value, tb)

	def process_config(self, config_file):
		"""Reads and parses an Ini-style configuration file.

		The config_file parameter specifies a configuration filename to
		process. The routine parses the file looking for a section named
		[Substitute]. The contents of this section will be returned as a
		dictionary to the caller.
		"""
		config = MyConfigParser()
		logging.info('Reading configuration file %s' % config_file)
		if not config.read(config_file):
			raise IOError('Unable to read configuration file %s' % config_file)
		if not 'Substitute' in config.sections():
			logging.warning('The configuration file %s has no [Substitute] section' % config_file)
		return dict(config.items('Substitute'))

main = ExecSqlUtility()
