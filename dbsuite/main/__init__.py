# vim: set noet sw=4 ts=4:

import sys
import optparse
import ConfigParser
import logging
import locale
import textwrap
import traceback
from db2makedoc.util import *

__version__ = "1.2.0"

# Use the user's default locale instead of C
locale.setlocale(locale.LC_ALL, '')

# Get the default output encoding from the default locale
ENCODING = locale.getdefaultlocale()[1]

class HelpFormatter(optparse.IndentedHelpFormatter):
	# Customize the width of help output
	def __init__(self):
		width = min(130, terminal_size()[0] - 2)
		optparse.IndentedHelpFormatter.__init__(self, max_help_position=width/3, width=width)

class OptionParser(optparse.OptionParser):
	# Customize error handling to raise an exception (default simply prints an
	# error and terminates execution)
	def error(self, msg):
		raise optparse.OptParseError(msg)

class Utility(object):
	# This class is the abstract base class for each of the command line
	# utility classes defined below. It provides some basic facilities like an
	# option parser, console pretty-printing, logging and exception handling

	def __init__(self, usage=None, version=None, description=None):
		super(Utility, self).__init__()
		self.wrapper = textwrap.TextWrapper()
		self.wrapper.width = min(130, terminal_size()[0] - 2)
		if usage is None:
			usage = self.__doc__.split('\n')[0]
		if version is None:
			version = '%%prog %s' % __version__
		if description is None:
			description = self.wrapper.fill('\n'.join(
				line.lstrip()
				for line in self.__doc__.split('\n')[1:]
				if line.lstrip()
			))
		self.parser = OptionParser(
			usage=usage,
			version=version,
			description=description,
			formatter=HelpFormatter()
		)
		self.parser.set_defaults(
			debug=False,
			logfile='',
			loglevel=logging.WARNING
		)
		self.parser.add_option('-q', '--quiet', dest='loglevel', action='store_const', const=logging.ERROR,
			help="""produce less console output""")
		self.parser.add_option('-v', '--verbose', dest='loglevel', action='store_const', const=logging.INFO,
			help="""produce more console output""")
		self.parser.add_option('-l', '--log-file', dest='logfile',
			help="""log messages to the specified file""")
		self.parser.add_option('-D', '--debug', dest='debug', action='store_true',
			help="""enables debug mode (runs under PDB)""")

	def __call__(self, args=None):
		if args is None:
			args = sys.argv[1:]
		(options, args) = self.parser.parse_args(args)
		console = logging.StreamHandler(sys.stderr)
		console.setFormatter(logging.Formatter('%(message)s'))
		console.setLevel(options.loglevel)
		logging.getLogger().addHandler(console)
		if options.logfile:
			logfile = logging.FileHandler(options.logfile)
			logfile.setFormatter(logging.Formatter('%(asctime)s, %(levelname)s, %(message)s'))
			logfile.setLevel(logging.DEBUG)
			logging.getLogger().addHandler(logfile)
		if options.debug:
			console.setLevel(logging.DEBUG)
			logging.getLogger().setLevel(logging.DEBUG)
		else:
			logging.getLogger().setLevel(logging.INFO)
		if options.debug:
			import pdb
			return pdb.runcall(self.main, options, args)
		else:
			try:
				return self.main(options, args) or 0
			except:
				return self.handle(*sys.exc_info())

	def handle(self, type, value, tb):
		"""Exception hook for non-debug mode."""
		if issubclass(type, (SystemExit, KeyboardInterrupt)):
			# Just ignore system exit and keyboard interrupt errors (after all,
			# they're user generated)
			return 130
		elif issubclass(type, (IOError, db2makedoc.plugins.PluginError)):
			# For simple errors like IOError and PluginError just output the
			# message which should be sufficient for the end user (no need to
			# confuse them with a full stack trace)
			logging.critical(str(value))
			return 1
		elif issubclass(type, (optparse.OptParseError,)):
			# For option parser errors output the error along with a message
			# indicating how the help page can be displayed
			logging.critical(str(value))
			logging.critical('Try the --help option for more information.')
			return 2
		else:
			# Otherwise, log the stack trace and the exception into the log
			# file for debugging purposes
			for line in traceback.format_exception(type, value, tb):
				for s in line.rstrip().split('\n'):
					logging.critical(s)
			return 1

	def pprint(self, s, indent=None, initial_indent='', subsequent_indent=''):
		"""Pretty-print routine for console output.

		This routine exists to provide pretty-printing capabilities for console
		output.  It makes use of a TextWrapper instance which is configured on
		startup with the width of the console to wrap text nicely.

		The s parameter provides the string or list of strings (used as a list
		of paragraphs) to print. The indent, initial_indent and
		subsequent_indent parameters are passed to the TextWrapper instance to
		specify indentations.  Either provide indent alone (which will be used
		as both initial_indent and subsequent_indent), or provide intial_indent
		and subsequent_indent separately.
		"""
		if indent is None:
			self.wrapper.initial_indent = initial_indent
			self.wrapper.subsequent_indent = subsequent_indent
		else:
			self.wrapper.initial_indent = indent
			self.wrapper.subsequent_indent = indent
		if isinstance(s, basestring):
			s = [s]
		first = True
		for para in s:
			if first:
				first = False
			else:
				sys.stdout.write('\n')
			para = self.wrapper.fill(para)
			if isinstance(para, unicode):
				para = para.encode(ENCODING)
			sys.stdout.write(para + '\n')

	def main(self, options, args):
		pass

