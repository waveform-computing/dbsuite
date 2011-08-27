# vim: set noet sw=4 ts=4:

import sys
mswindows = sys.platform == "win32"

import os.path
import logging
import threading
import subprocess
try:
	import cPickle as pickle
except ImportError:
	import pickle
from datetime import datetime
from string import Template
from time import sleep
from dbsuite.tokenizer import Token
from dbsuite.parser import TokenTypes as TT
from dbsuite.instance import get_instance, set_instance
from dbsuite.compat import *

# Constants for the SQLScript.state property
(
	SUCCEEDED,  # script executed successfully
	EXECUTING,  # script is currently executing
	EXECUTABLE, # all dependencies satisfied, script is ready to be executed
	WAITING,    # script is waiting for dependencies to be satisfied
	FAILED,     # script, or a dependent script has failed and cannot be retried
) = range(5)

# Declare a simple class to store the attributes associated with an ON statement
class OnState(object):
	def __init__(self, line, delay, retry_mode, retry_count, action):
		super(OnState, self).__init__()
		self.line = line
		self.delay = delay
		self.retry_mode = retry_mode
		self.retry_count = retry_count
		self.action = action

# Create a singleton class to represent arbitrary error states for the ON statement
class ErrorState(object):
	pass
ErrorState = ErrorState()

# Global lock used to ensure output doesn't overlap
output_lock = threading.RLock()

class Error(Exception):
	"""Base class for SQLScript exceptions"""

	def __init__(self, msg=''):
		Exception.__init__(self, msg)
		self.message = msg

	def __repr__(self):
		return self.message

	__str__ = __repr__

class ScriptRuntimeError(Error):
	"""Raised when a script fails at runtime"""

	def __init__(self, msg):
		Error.__init__(self, msg)

class DependencyError(Error):
	"""Base class for dependency errors"""

	def __init__(self, script, msg):
		Error.__init__(self, msg)
		self.filename = script.filename
		self.errors = []

	def append(self, depfile, msg):
		self.errors.append((depfile, msg))
		self.message += '\n%s' % (msg)

class UnresolvedDependencyError(DependencyError):
	"""Raised when a script has an unresolved dependency"""

	def __init__(self, script):
		DependencyError.__init__(self, script,
			'Script has dependencies that cannot be resolved: %s' % script.filename)

class CircularDependencyError(DependencyError):
	"""Raised when a script has an unresolvable circular dependency"""

	def __init__(self, script):
		DependencyError.__init__(self, script,
			'Script has circular dependencies: %s' % script.filename)


def clean_output(s):
	"""Utility routine for cleaning DB2 CLP output.

	On Windows, DB2 CLP tends to output all sorts of weird crap including
	form-feeds, and doubled-CRs in line feeds (\r\r\n). This routine exists to
	apply any platform-specific cleaning that needs to be performed.
	"""
	if mswindows:
		s = s.replace('\f', '')
		s = s.replace('\r\r\n', '\n')
		s = s.replace('\r\n', '\n')
		s = s.replace('\r', '\n')
	return s

def format_rc(rc):
	if rc == 0:
		return 'OK'
	else:
		result = []
		if rc & 1: result.append('No Recs')
		if rc & 2: result.append('Warning')
		if rc & 4: result.append('DB2 Err')
		if rc & 8: result.append('CLP Err')
		return ','.join(result)


class SQLJob(object):
	"""Represents a set of SQL scripts to be executed as a unit.

	On construction an SQLJob object loads the set of scripts given to it, and
	determines the dependencies between those scripts. Various methods are
	defined for testing file permissions, database logins, and of course for
	executing the scripts themselves.
	"""

	def __init__(self, plugin, sql_files, vars={}, terminator=';',
			retrylimit=1, autocommit=False, stoponerror=False,
			deletefiles=False):
		self.scripts = [
			SQLScript(plugin, sql_file, vars, terminator, retrylimit, autocommit, stoponerror, deletefiles)
			for sql_file in sql_files
		]
		for script in self.scripts:
			script.resolve_dependencies(self.scripts)

	def depth_traversal(self, scripts=None):
		"""Return a depth-first traversal of scripts according to execution dependencies"""
		if scripts is None:
			scripts = self.scripts
		result = []
		for script in scripts:
			result.extend(self.depth_traversal(producer for (depfile, producer) in script.depends))
			if script not in result:
				result.append(script)
		return result

	def print_dependencies(self, scripts=None, prefix=""):
		"""Output nodes in an ASCII formatted tree diagram by dependency"""
		if scripts is None:
			# Determine the "top-level" scripts, i.e. those scripts which have
			# no dependents (they may still output files, but no other script
			# consumes those files)
			scripts = [
				script for script in self.scripts
				if not sum(len(consumers) for (depfile, consumers) in script.rdepends)
			]
		i = 0
		for script in scripts:
			i += 1
			if i == len(scripts):
				logging.info("%s'- %s" % (prefix, script.filename))
			else:
				logging.info('%s+- %s' % (prefix, script.filename))
			if script.depends:
				if i == len(scripts):
					new_prefix = prefix + '   '
				else:
					new_prefix = prefix + '|  '
				logging.info(new_prefix + '|')
				self.print_dependencies([producer for (depfile, producer) in script.depends], new_prefix)
			elif i == len(scripts):
				logging.info(prefix.rstrip())

	def print_transfers(self, scripts=None):
		"""Output nodes in a definition list of database transfers performed"""
		if scripts is None:
			scripts = self.scripts
		files = {}
		for script in scripts:
			for (f, source) in script.produces:
				files[f] = (source, [])
		for script in scripts:
			for (f, target) in script.consumes:
				if not f in files:
					files[f] = (None, [target])
				else:
					files[f][1].append(target)
		dbs = {}
		for f in files:
			source = files[f][0]
			for target in files[f][1]:
				if not (source, target) in dbs:
					dbs[(source, target)] = [f]
				else:
					dbs[(source, target)].append(f)
		for ((source, target), files) in dbs.iteritems():
			logging.info('%s -> %s:' % (
				'(missing source)' if source is None else source.database,
				'(missing consumer)' if target is None else target.database,
			))
			for f in sorted(files):
				logging.info(' '*4 + f)
		logging.info('')

	def print_status(self, scripts=None):
		"""Outputs the start time, duration and status of each script."""
		if scripts is None:
			scripts = self.scripts
		# Sort scripts by start time and filename (unstarted scripts are listed
		# last)
		scripts = \
			sorted((script for script in scripts if script.started), key=lambda script: (script.started, script.filename)) + \
			sorted((script for script in scripts if not script.started), key=lambda script: script.filename)
		# Make a list of tuples of (filename, starttime, duration, exitcode)
		data = []
		for script in scripts:
			if script.started:
				duration = (script.finished - script.started).seconds
				duration = '%.2d:%.2d:%.2d' % (duration / 3600, (duration / 60) % 60, duration % 60)
				data.append((
					script.filename,
					script.started.strftime('%H:%M:%S'),
					duration,
					format_rc(script.returncode),
				))
			else:
				data.append((
					script.filename,
					'-',
					'-',
					'Not Run',
				))
		data.insert(0, ('Script', 'Started', 'Duration', 'Status'))
		started = min(script.started for script in scripts if script.started)
		finished = max(script.finished for script in scripts if script.finished)
		data.append((
			'Total',
			started.strftime('%H:%M:%S'),
			'%ds' % (finished - started).seconds,
			'',
		))
		# Calculate the maximum length of each field
		lengths = (
			max(len(x) for (x, _, _, _) in data),
			max(len(x) for (_, x, _, _) in data),
			max(len(x) for (_, _, x, _) in data),
			max(len(x) for (_, _, _, x) in data),
		)
		# Insert separators
		data.insert(1, tuple('-' * l for l in lengths))
		data.insert(-1, tuple('-' * l for l in lengths))
		# Output the data
		for row in data:
			logging.info(' '.join('%-*s' % (l, s) for (l, s) in zip(lengths, row)))

	def test_connection(self, connection):
		"""Utility routine for testing database logins prior to script execution."""
		saved_instance = None
		if connection.instance:
			saved_instance = get_instance()
			set_instance(get_instance(connection.instance))
		try:
			args = [
				'-o', # enable output
				'+p', # disable input prompt
				'-s', # stop on error
				'-t'  # use ; as statement terminator
			]
			cmdline = 'db2 %s' % ' '.join(args)
			if mswindows:
				cmdline = 'db2cmd -i -w -c %s' % cmdline
			p = subprocess.Popen(
				[cmdline],
				shell=True,
				stdin=subprocess.PIPE,
				stdout=subprocess.PIPE,
				stderr=subprocess.STDOUT,
				close_fds=not mswindows
			)
			if connection.username is not None:
				sql = "CONNECT TO '%s' USER '%s' USING '%s';\n" % (connection.database, connection.username, connection.password)
			else:
				sql = "CONNECT TO '%s';\n" % connection.database
			sql += 'CONNECT RESET;\n'
			try:
				output = p.communicate(sql)[0]
			except Exception, e:
				raise ScriptRuntimeError(str(e))
			if p.returncode >= 4:
				raise ScriptRuntimeError(clean_output(output))
		finally:
			if saved_instance:
				set_instance(saved_instance)

	def test_connections(self, scripts=None):
		"""Tests the provided connection details against all databases accessed by all scripts"""
		if scripts is None:
			scripts = self.scripts
		result = True
		connections = set()
		for script in scripts:
			connections |= set(script.connections)
		for connection in connections:
			try:
				self.test_connection(connection)
				logging.info('Test connection to database %s succeeded with username: %s' % (connection.database, connection.username))
			except Exception, e:
				logging.error('Test connection to database %s failed with username: %s. Error:' % (connection.database, connection.username))
				logging.error(str(e))
				result = False
		if not result:
			raise Error('One or more test connections failed')

	def test_permissions(self, scripts=None):
		"""Tests the read and/or write permissions of produced and consumed files"""
		if scripts is None:
			scripts = self.scripts
		filemodesok = True
		filemodes = {}
		for script in scripts:
			for (f, db) in script.produces:
				if os.path.exists(f):
					filemodes[f] = 'a'
				else:
					filemodes[f] = 'w'
			for (f, db) in script.consumes:
				if f in filemodes:
					filemodes[f] = filemodes[f][0] + '+'
				else:
					filemodes[f] = 'r'
		for f in filemodes:
			try:
				action = {
					'r':  'read',
					'a':  'write',
					'a+': 'read/write',
					'w':  'create/write',
					'w+': 'create/read/write',
				}[filemodes[f]]
				mode = filemodes[f]
				if mswindows:
					mode += 'b'
				open(f, mode).close()
				if 'w' in filemodes[f]:
					os.unlink(f)
				logging.info('Test %s for %s succeeded' % (action, f))
			except IOError, e:
				logging.error('Unable to %s file %s. Error:' % (action, f))
				logging.error(str(e))
				filemodesok = False
		if not filemodesok:
			raise Error('One or more file permission tests failed, aborting execution')

	def execute(self, scripts=None):
		if scripts is None:
			scripts = self.scripts
		# Execute the scripts. Break out of the loop if any scripts fail, or once
		# there are no scripts which have not succeeded
		while True:
			for script in [s for s in scripts if s.state == EXECUTABLE]:
				script.execute()
			if [s for s in scripts if s.state == FAILED]:
				break
			if not [s for s in scripts if s.state != SUCCEEDED]:
				break
			sleep(1)
		# Wait for scripts to finish executing
		while [s for s in scripts if s.state == EXECUTING]:
			sleep(1)
		# Provide a summary of script execution times and results
		self.print_status()
		# If one or more scripts failed, raise an exception (i.e. exit now)
		if len([s for s in scripts if s.state == FAILED]) > 0:
			raise ScriptRuntimeError('One or more scripts failed')
		# If requested, delete produced files (note this only happens if all
		# scripts have completed successfully)
		for script in scripts:
			if script.deletefiles:
				for (filename, db) in script.produces:
					if os.path.exists(filename):
						try:
							os.unlink(filename)
						except Exception, e:
							# If we can't delete a file, log the error but
							# don't abort (and don't report an error via the
							# exit code)
							logging.error(str(e))


class SQLScript(object):
	"""Represents an SQL script to be executed.

	On construction, an SQLScript object parses the script given to it,
	substituting variable references and cleaning up the SQL (removing
	comments, compressing whitespace, etc). When the execute method is called
	the script is executed by the DB2 CLP in a subprocess, which is tracked by
	a background thread.

	In addition, the object records all output from stdout/stderr, and the
	returncode of the DB2 CLP.
	"""

	def __init__(self, plugin, sql_file, vars={}, terminator=';', retrylimit=1,
			autocommit=False, stoponerror=False, deletefiles=False):
		"""Initializes an instance of the class.

		Parameters:
		plugin -- An InputPlugin which the instance can use to obtain an SQL parser
		sql_file -- The name of the file (or file-like object) containing the SQL script
		vars -- A dictionary of values to substitute into the script
		terminator -- The statement terminator string/character
		retrylimit -- The number of times to retry the script if it fails
		autocommit -- Whether to activate CLP's auto-COMMIT behaviour
		stoponerror -- Whether to terminate script immediately upon error
		deletefiles -- Whether or not to delete all files produced by the script upon successful completion
		"""
		super(SQLScript, self).__init__()
		self.output = []
		self.started = None
		self.finished = None
		self.returncode = None
		self.terminator = terminator
		self.retrylimit = retrylimit
		self.autocommit = autocommit
		self.stoponerror = stoponerror
		self.deletefiles = deletefiles
		if isinstance(sql_file, basestring):
			self.filename = sql_file
			sql_file = open(sql_file, 'rU')
		else:
			if hasattr(sql_file, 'name'):
				self.filename = sql_file.name
			else:
				self.filename = 'stdin'
		self.sql = sql_file.read()
		self.sql = Template(self.sql).safe_substitute(vars)
		tokenizer = plugin.tokenizer()
		parser = plugin.parser(for_scripts=True)
		parser.reformat = set()
		logging.info('Parsing script %s' % self.filename)
		self.tokens = parser.parse(tokenizer.parse(self.sql, terminator=self.terminator))
		self.sql = ''.join(token.source for token in self.tokens)
		# Convert filenames to "canonical" format (resolve all symbolic links,
		# transform to lowercase on Windows, etc.) to allow comparison of
		# filenames which may not actually exist as files yet
		self.produces = [
			(os.path.normcase(os.path.realpath(os.path.expanduser(f))), db)
			for (f, db) in parser.produces
		]
		self.consumes = [
			(os.path.normcase(os.path.realpath(os.path.expanduser(f))), db)
			for (f, db) in parser.consumes
		]
		# Copy the connections list (for use by the job to test connections prior to
		# starting all scripts in parallel)
		self.connections = parser.connections
		# The depends list is set up by resolve_dependencies later
		self.depends = []
		self.rdepends = []

	def resolve_dependencies(self, scripts):
		"""Resolves script dependencies by examining produced and consumed files.

		Once all script objects have been created, this method is called on
		each script object to resolve dependencies between scripts (i.e. an
		IXF file produced by one script and consumed by another implies that
		the latter script relies on the former).
		"""
		logging.info('Calculating dependencies for script %s' % self.filename)
		# Calculate a list of files on which this script depends, and which
		# scripts in the provided list produce these files
		self.depends = [
			(depfile, [
				producer for producer in scripts
				if depfile in [f for (f, db) in producer.produces]
			])
			for depfile in [f for (f, db) in self.consumes]
		]
		# Calculate reverse dependencies
		self.rdepends = [
			(depfile, [
				consumer for consumer in scripts
				if depfile in [f for (f, db) in consumer.consumes]
			])
			for depfile in [f for (f, db) in self.produces]
		]
		# Warn about missing dependencies for which the dependent file does
		# already exist (i.e. the file won't be refreshed: it might be out of
		# date)
		for (depfile, producers) in self.depends:
			if len(producers) == 0 and os.path.exists(depfile):
				logging.warning('Missing dependency: File %s exists, but has no producer' % depfile)
		# Check the reverse dependency list for files which are produced but
		# never consumed and log a warning
		for (depfile, consumers) in self.rdepends:
			if len(consumers) == 0:
				logging.warning('File %s is produced, but never consumed' % depfile)
		# Check the dependency list for missing dependencies and ambiguous
		# dependencies (multiple producers of a file)
		e = None
		for (depfile, producers) in self.depends:
			if len(producers) == 0 and not os.path.exists(depfile):
				if not e: e = UnresolvedDependencyError(self)
				e.append(depfile, 'Missing dependency: File %s does not exist and has no producer' % depfile)
			elif len(producers) > 1:
				if not e: e = UnresolvedDependencyError(self)
				e.append(depfile, 'Ambiguous dependency: %s all produce file %s' % (', '.join([s.filename for s in producers]), depfile))
		if e:
			raise e
		# Change the producers list in each dependency entry into a single
		# value (now that we've confirmed each only consists of one entry, or
		# zero entries but a pre-existing dependency file).  This step also
		# removes all self-referential dependencies (files this script produces
		# and consumes all by itself)
		self.depends = [
			(depfile, producers[0])
			for (depfile, producers) in self.depends
			if len(producers) == 1 and producers[0] is not self
		]
		# Recalculate the reverse dependencies list removing self-referential
		# dependencies
		self.rdepends = [
			(depfile, consumers)
			for (depfile, consumers) in self.rdepends
			if not (len(consumers) == 1 and consumers[0] is self)
		]
		# Check for circular dependencies (this must occur after removing
		# self-referential dependencies for obvious reasons)
		if self.depends_on(self):
			e = CircularDependencyError(self)
			s = self
			while True:
				for (depfile, producer) in s.depends:
					if producer.depends_on(self):
						e.append(depfile, '%s depends on %s' % (s.filename, producer.filename))
						s = producer
						break
				if s == self:
					break
			raise e

	def depends_on(self, script):
		"""Returns True if script is a dependency.

		If script is a direct or indirect dependency of this SQLScript object,
		the method returns True. The method recursively searches the depends
		list for dependencies.
		"""
		for (depfile, producer) in self.depends:
			if (script == producer) or producer.depends_on(script):
				return True
		return False

	def execute(self):
		"""Executes the script in a subprocess tracked by a background thread.

		When this method is called, a new subprocess is created to run the
		DB2 CLP which will execute the script. The script is passed to the
		subprocess via stdin (we can't use the original file as we may have
		substituted variables in the original and the parser may have removed
		incompatible comments, etc).

		A background thread is created (running the _exec_thread method below)
		to send the script to the subprocess, and retrieve any/all output
		produced.
		"""
		assert self.state != EXECUTING
		logging.info('Starting script %s' % self.filename)
		# These variables MUST be set by execute() to guarantee their state by
		# the time the method exits (to ensure our state is consistent). Just
		# because we start the background execution thread, doesn't mean it's
		# been scheduled by the time we exit...
		self.started = datetime.now()
		self.finished = None
		self.returncode = None
		self.output = []
		t = threading.Thread(target=self._exec_thread, args=())
		t.start()

	@property
	def state(self):
		if self.started and not self.finished:
			return EXECUTING
		elif self.returncode is not None and self.returncode < 4:
			return SUCCEEDED
		elif self.retrylimit > 0:
			if len([d for (f, d) in self.depends if d.state != SUCCEEDED]) == 0:
				return EXECUTABLE
			elif len([d for (f, d) in self.depends if d.state == FAILED]) == 0:
				return WAITING
			else:
				return FAILED
		else:
			return FAILED

	def _exec_thread(self):
		"""Target method for the background thread tracking the subprocess.

		This method is used by the execute method as the body of the thread
		that starts, communicates and tracks the subprocess executing the
		script. See the execute method for more details.
		"""
		p = subprocess.Popen(
			[sys.argv[0], '--exec-internal'], # execute ourselves in script mode
			shell=False,
			stdin=subprocess.PIPE,
			stdout=subprocess.PIPE,
			stderr=sys.stderr,
			close_fds=not mswindows
		)
		try:
			# Pickle ourselves and send the result to the subprocess
			s = pickle.dumps(self)
			try:
				output = p.communicate(s)[0]
			except Exception, e:
				logging.error('Script %s failed: %s' % (self.filename, str(e)))
				# An exception is fatal, no retries allowed
				self.retrylimit = 0
			else:
				# The subprocess will send back a pickled array of LogRecord
				# objects on its stdout which we now unpickle
				self.output = pickle.loads(output)
				# Use the global output lock to prevent overlapping output in
				# case of simultaneous script completions
				output_lock.acquire()
				try:
					# Check the return code
					self.returncode = p.returncode
					if self.returncode >= 4:
						self.retrylimit -= 1
						if self.retrylimit > 0:
							logging.warning('Script %s failed with return code %d (retries left: %d)' % (self.filename, self.returncode, self.retrylimit))
						else:
							logging.error('Script %s failed with return code %d (no retries remaining)' % (self.filename, self.returncode))
					else:
						logging.info('Script %s completed successfully with return code %d' % (self.filename, self.returncode))
					logging.info('Script %s output' % self.filename)
					# Pass the LogRecords sent by the subprocess thru to the
					# root logger
					for rec in self.output:
						logging.getLogger().handle(rec)
				finally:
					output_lock.release()
		finally:
			# finished is set last to avoid a race condition. Furthermore, it
			# MUST be set or we will wind up with a process in "limbo" (hence
			# the try..finally section).
			self.finished = datetime.now()

	def _exec_internal(self):
		# Split the tokens into statements, stripping leading whitespace and
		# removing all comments
		self._on_mode = None
		self._on_states = {}
		statement = []
		statements = []
		for token in self.tokens:
			if token.type != TT.COMMENT:
				if statement or token.type != TT.WHITESPACE:
					statement.append(token)
			if token.type == TT.STATEMENT:
				statements.append(statement)
				statement = []
		if statement:
			statement.append(Token(TT.STATEMENT, ';', self.terminator, statement[-1].line, statement[-1].column + 1))
			statements.append(statement)
		# Execute each statement in turn. The returncode of each execution is
		# combined (by bitwise-or) into our final returncode
		returncode = 0
		position = 0
		while position < len(statements):
			statement = statements[position]
			# Log the statement that will run. Hide any passwords or statement
			# terminators, and compress all whitespace, just as the DB2 CLP
			# usually does
			logging.info(''.join(
				"'***'" if token.type == TT.PASSWORD else
				' '     if token.type == TT.WHITESPACE else
				''      if token.type == TT.STATEMENT else
				token.source for token in statement
			))
			if statement[0].value == 'ON':
				rc, state = self._exec_on_statement(statement)
			elif statement[0].value == 'INSTANCE':
				rc, state = self._exec_instance_statement(statement)
			else:
				rc, state = self._exec_statement(statement)
			position += 1
			# Check the dictionary of ON states for a match
			on_state = None
			if state and (state in self._on_states):
				on_state = self._on_states[state]
			elif rc >= 4 and (ErrorState in self._on_states):
				on_state = self._on_states[ErrorState]
			# If we found a match, act on the ON state immediately as it may
			# alter the rc
			if on_state:
				logging.info('ON statement matched at line %d' % on_state.line)
				if on_state.retry_mode:
					if on_state.retry_count == 0:
						logging.warn('All retries exhausted')
					else:
						if on_state.delay:
							logging.warn('Pausing for %d seconds' % on_state.delay)
							sleep(on_state.delay)
						if on_state.retry_count > 0:
							suffix = '(%d retries remaining)' % on_state.retry_count
							on_state.retry_count -= 1
						else:
							suffix = ''
						if on_state.retry_mode == 'SCRIPT':
							logging.warn('Retrying script %s' % suffix)
							position = 0
							self._exec_terminate_statement(statement)
						else:
							logging.warn('Retrying statement %s' % suffix)
							position -= 1
						# In the case that we're retrying something, restart
						# the loop here skipping the ON action and the update
						# of returncode
						continue
				# If not retrying or all retries are exhausted, perform the ON
				# state action
				if on_state.action in ('CONTINUE', 'FAIL'):
					returncode |= rc
				if on_state.action in ('STOP', 'FAIL') and rc >= 4:
					break
			else:
				returncode |= rc
			if self.stoponerror and returncode >= 4:
				break
		return returncode

	def _exec_statement(self, statement):
		# Construct the SQL to execute with @ as statement terminator
		sql = ''.join(
			'@' if token.type == TT.STATEMENT else token.source
			for token in statement
		)
		cmdline = [
			'db2',
			'-o',                          # enable output
			'+p',                          # disable input prompt
			['+c', '-c'][self.autocommit], # enable auto-COMMIT if required
			'-td@'                         # use @ as statement terminator
		]
		if self._on_mode == 'SQLCODE':
			cmdline.append('-ec')          # output the SQLCODE after execution
		elif self._on_mode == 'SQLSTATE':
			cmdline.append('-es')          # output the SQLSTATE after execution
		if mswindows:
			cmdline = ['db2cmd', '-i', '-w', '-c'] + cmdline
		p = subprocess.Popen(
			cmdline,
			shell=False,
			stdin=subprocess.PIPE,
			stdout=subprocess.PIPE,
			stderr=subprocess.STDOUT,
			close_fds=not mswindows
		)
		try:
			output = p.communicate(sql)[0]
		except Exception, e:
			logging.error('Failed to execute at line %d of script %s: %s' % (statement[0].line, self.filename, str(e)))
			return (8, None)
		else:
			output = clean_output(output).splitlines()
			# If we're watching for SQLCODEs or SQLSTATEs, strip off the last
			# line of output as it contains the state
			if self._on_mode:
				state = output[-1].strip()
				output = output[:-1]
				if self._on_mode == 'SQLCODE':
					state = int(state)
			else:
				state = None
			# Log the output of the statement with a level appropriate to
			# the CLP's return code
			if p.returncode == 0:
				log = logging.info
			elif p.returncode < 4:
				log = logging.warn
			else:
				log = logging.error
				log('Statement at line %d of script %s produced the following error:' % (statement[0].line, self.filename))
			for line in output:
				log(line)
			return (p.returncode, state)

	def _exec_on_statement(self, statement):
		# Strip the statement of all junk tokens
		try:
			statement = [t for t in statement if t.type not in (TT.WHITESPACE, TT.COMMENT)]
			i = 1
			# Parse the error condition clause
			mode = statement[i].value
			if mode == 'SQLCODE':
				if self._on_mode and self._on_mode != mode:
					raise Exception('Cannot use ON SQLCODE after ON SQLSTATE')
				i += 1
				if statement[i].type == TT.OPERATOR:
					i += 1
				if statement[i].type == TT.NUMBER:
					state = statement[i].value
				else:
					if not statement[i].value.upper().startswith('SQL'):
						raise Exception('Invalid SQLCODE "%s"; SQLCODEs must being with "SQL"' % statement[i].value)
					if not 7 <= len(statement[i].value) <= 8:
						raise Exception('Invalid SQLCODE "%s"; SQLCODEs must be between 7 and 8 characters long' % statement[i].value)
					try:
						state = int(statement[i].value[3:7])
					except ValueError:
						raise Exception('Invalid SQLCODE "%s"; SQL must be followed by 4 numerals' % statement[i].value)
				if state > 0:
					# Make all SQLCODEs negative
					state = -state
				i += 1
			elif mode == 'SQLSTATE':
				if self._on_mode and self._on_mode != mode:
					raise Exception('Cannot use ON SQLSTATE after ON SQLCODE')
				i += 1
				state = statement[i].value.upper()
				i += 1
			else:
				i += 1
				state = ErrorState
			# Parse the delay clause (if present)
			if statement[i].value == 'WAIT':
				i += 1
				delay = statement[i].value
				i += 1
				if statement[i].value in ('HOUR', 'HOURS'):
					delay *= (60*60)
				elif statement[i].value in ('MINUTE', 'MINUTES'):
					delay *= 60
				i += 1
				if statement[i].value == 'AND':
					i += 1
			else:
				delay = 0
			# Parse the retry clause (if present)
			if statement[i].value == 'RETRY':
				i += 1
				retry_mode = statement[i].value
				i += 1
				if statement[i].type == TT.NUMBER:
					retry_count = statement[i].value
					i += 2
				else:
					retry_count = -1
				if statement[i].value == 'AND':
					i += 1
			else:
				retry_mode = None
				retry_count = 0
			action = statement[i].value
			if (state in self._on_states) and (self._on_states[state].line == statement[0].line):
				# If there's already an entry for this ON statement in the
				# states dictionary we're retrying the script so don't re-write
				# the entry or we'll reset the retry-count and probably wind up
				# in an infinite loop
				pass
			else:
				self._on_states[state] = OnState(statement[0].line, delay, retry_mode, retry_count, action)
			self._on_mode = mode
			logging.info('ON statement processed successfully')
		except Exception, e:
			logging.error('Statement at line %d of script %s produced the following error:' % (statement[0].line, self.filename))
			logging.error(str(e))
			return (8, None)
		else:
			return (0, None)

	def _exec_instance_statement(self, statement):
		try:
			self._exec_terminate_statement(statement)
			# Strip the statement of all junk tokens. Afterward it should have the
			# structure ['INSTANCE', instance-name, ';']
			statement = [t for t in statement if t.type not in (TT.WHITESPACE, TT.COMMENT)]
			set_instance(get_instance(statement[1].value))
		except Exception, e:
			logging.error('Statement at line %d of script %s produced the following error:' % (statement[0].line, self.filename))
			logging.error(str(e))
			return (8, None)
		else:
			logging.info('Switched to instance: %s' % statement[1].value)
			return (0, None)

	def _exec_terminate_statement(self, statement):
		# Construct a TERMINATE statement and run it to kill off any existing
		# DB2 backend process
		term = [
			Token(TT.IDENTIFIER, 'TERMINATE', 'TERMINATE', statement[0].line, statement[0].column),
			statement[-1],
		]
		rc, state = self._exec_statement(term)
		if rc >= 4:
			raise Exception('Implicit TERMINATE statement failed')
