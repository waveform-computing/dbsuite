# vim: set noet sw=4 ts=4:

import sys
mswindows = sys.platform == "win32"

import os.path
import logging
import threading
import subprocess
from datetime import datetime
from string import Template
from time import sleep
from db2exec.sql.tokenizer import DB2UDBSQLTokenizer
from db2exec.sql.parser import CLPParser

# Constants for the SQLScript.state property
(
	SUCCEEDED,  # script executed successfully
	EXECUTING,  # script is currently executing
	EXECUTABLE, # all dependencies satisfied, script is ready to be executed
	WAITING,    # script is waiting for dependencies to be satisfied
	FAILED,     # script, or a dependent script has failed and cannot be retried
) = range(5)

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
			retrylimit=3, autocommit=False, stoponerror=False,
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

	def test_login(self, database, username, password):
		"""Utility routine for testing database logins prior to script execution."""
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
		if username is not None:
			sql = "CONNECT TO '%s' USER '%s' USING '%s';\n" % (database, username, password)
		else:
			sql = "CONNECT TO '%s';\n" % database
		sql += 'CONNECT RESET;\n'
		try:
			output = p.communicate(sql)[0]
		except Exception, e:
			raise Error(str(e))
		if p.returncode >= 4:
			raise Error(clean_output(output))

	def test_logins(self, scripts=None):
		"""Tests the provided login details against all databases accessed by all scripts"""
		if scripts is None:
			scripts = self.scripts
		result = True
		logins = set()
		for script in scripts:
			logins |= set(script.logins)
		for login in logins:
			try:
				self.test_login(login.database, login.username, login.password)
				logging.info('Test login to database %s succeeded with username: %s' % (login.database, login.username))
			except Exception, e:
				logging.error('Test login to database %s failed with username: %s. Error:' % (login.database, login.username))
				logging.error(str(e))
				result = False
		if not result:
			raise Exception('One or more test logins failed')

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
			raise Exception('One or more file permission tests failed, aborting execution')

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
			raise Exception("One or more scripts failed")
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

	def __init__(self, plugin, sql_file, vars={}, terminator=';', retrylimit=3,
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
		"""
		super(SQLScript, self).__init__()
		self.__retrylimit = retrylimit
		self.__process = None
		self.__thread = None
		self.output = ''
		self.started = None
		self.finished = None
		self.returncode = None
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
		logging.info('Parsing script %s' % self.filename)
		tokens = parser.parse(tokenizer.parse(self.sql, terminator=terminator))
		self.sql = ''.join([token[2] for token in tokens])
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
		# Copy the logins list (for use by the job to test logins prior to
		# starting all scripts in parallel)
		self.logins = parser.connections
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
		logging.info("Calculating dependencies for script %s" % self.filename)
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
				logging.warning("Missing dependency: File %s exists, but has no producer" % (depfile,))
		# Check the reverse dependency list for files which are produced but
		# never consumed and log a warning
		for (depfile, consumers) in self.rdepends:
			if len(consumers) == 0:
				logging.warning("File %s is produced, but never consumed" % (depfile,))
		# Check the dependency list for missing dependencies and ambiguous
		# dependencies (multiple producers of a file)
		e = None
		for (depfile, producers) in self.depends:
			if len(producers) == 0 and not os.path.exists(depfile):
				if not e: e = UnresolvedDependencyError(self)
				e.append(depfile, "Missing dependency: File %s does not exist and has no producer" % (depfile,))
			elif len(producers) > 1:
				if not e: e = UnresolvedDependencyError(self)
				e.append(depfile, "Ambiguous dependency: %s all produce file %s" % (', '.join([s.filename for s in producers]), depfile))
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
						e.append(depfile, "%s depends on %s" % (s.filename, producer.filename))
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

		A background thread is also created (running the __exec_thread method
		below) to send the script to the subprocess, and retrieve any/all
		output produced.
		"""
		assert self.state != EXECUTING
		logging.info("Starting script %s" % (self.filename,))
		# These variables MUST be set by execute() to guarantee their state by
		# the time the method exits (to ensure our state is consistent). Just
		# because we start the background execution thread, doesn't mean it's
		# been scheduled by the time we exit...
		self.started = datetime.now()
		self.finished = None
		self.returncode = None
		self.output = ''
		self.__thread = threading.Thread(target=self.__exec_thread, args=())
		self.__thread.start()
	
	def __exec_thread(self):
		"""Target method for the background thread tracking the subprocess.

		This method is used by the execute method as the body of the thread
		that starts, communicates and tracks the subprocess executing the
		script. See the execute method for more details.
		"""
		args = [
			'-o',                           # enable output
			'-v',                           # verbose output
			'-p-',                          # disable input prompt
			['+s', '-s'][self.stoponerror], # terminate immediately on error
			['+c', '-c'][self.autocommit],  # enable auto-COMMIT
			'-td@'                          # use @ as statement terminator
		]
		cmdline = 'db2 %s' % ' '.join(args)
		if mswindows:
			cmdline = 'db2cmd -i -w -c %s' % cmdline
		self.__process = subprocess.Popen(
			[cmdline],
			shell=True,
			stdin=subprocess.PIPE,
			stdout=subprocess.PIPE,
			stderr=subprocess.STDOUT,
			close_fds=not mswindows
		)
		try:
			try:
				self.output = self.__process.communicate(self.sql)[0]
			except Exception, e:
				self.output = str(e)
				logging.error("Script %s failed: %s" % (self.filename, self.output))
				# An exception is fatal, no retries allowed
				self.__retrylimit = 0
			else:
				self.output = clean_output(self.output)
				# Use the global output lock to prevent overlapping output in
				# case of simultaneous script completions
				output_lock.acquire()
				try:
					# Check the return code
					self.returncode = self.__process.returncode
					if self.returncode >= 4:
						self.__retrylimit -= 1
						if self.__retrylimit > 0:
							logging.warning("Script %s failed with return code %d (retries left: %d)" % (self.filename, self.returncode, self.__retrylimit))
						else:
							logging.error("Script %s failed with return code %d (no retries remaining)" % (self.filename, self.returncode))
					else:
						logging.info("Script %s completed successfully with return code %d" % (self.filename, self.returncode))
					logging.info("Script %s output" % self.filename)
					for line in self.output.splitlines():
						logging.info(line.rstrip())
				finally:
					output_lock.release()
		finally:
			self.__thread = None
			self.__process = None
			# finished is set last to avoid a race condition. Furthermore, it
			# MUST be set or we will wind up with a process in "limbo" (hence
			# the try..finally section).
			self.finished = datetime.now()

	def __get_state(self):
		if self.started and not self.finished:
			return EXECUTING
		elif self.returncode is not None and self.returncode < 4:
			return SUCCEEDED
		elif self.__retrylimit > 0:
			if len([d for (f, d) in self.depends if d.state != SUCCEEDED]) == 0:
				return EXECUTABLE
			elif len([d for (f, d) in self.depends if d.state == FAILED]) == 0:
				return WAITING
			else:
				return FAILED
		else:
			return FAILED

	state = property(__get_state, doc="""The current state of the script""")

