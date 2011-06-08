# vim: set noet sw=4 ts=4:

import sys
import logging
import dbsuite.highlighters
import dbsuite.plugins
import dbsuite.main
from dbsuite.compat import *

class TidySqlUtility(dbsuite.main.Utility):
	"""%prog [options] files...

	This utility reformats SQL for human consumption using the same parser that
	the db2makedoc application uses for generating SQL in documentation. Either
	specify the names of files containing the SQL to reformat, or specify - to
	indicate that stdin should be read. The reformatted SQL will be written to
	stdout in either case. The available command line options are listed below.
	"""

	def __init__(self):
		super(TidySqlUtility, self).__init__()
		self.parser.set_defaults(terminator=';')
		self.parser.add_option('-t', '--terminator', dest='terminator',
			help="""specify the statement terminator (default=';')""")

	def main(self, options, args):
		super(TidySqlUtility, self).main(options, args)
		done_stdin = False
		# XXX Add method to select input plugin
		plugin = dbsuite.plugins.load_plugin('db2.luw')()
		highlighter = dbsuite.highlighters.SQLHighlighter(plugin)
		for sql_file in args:
			if sql_file == '-':
				if not done_stdin:
					done_stdin = True
					sql_file = sys.stdin
				else:
					raise IOError('Cannot read input from stdin multiple times')
			else:
				sql_file = open(sql_file, 'rU')
			sql = sql_file.read()
			sql = highlighter.parse_to_string(sql, terminator=options.terminator)
			sys.stdout.write(sql)
			sys.stdout.flush()
		return 0

main = TidySqlUtility()

