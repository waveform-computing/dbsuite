# vim: set et sw=4 sts=4:

# Copyright 2012 Dave Hughes.
#
# This file is part of dbsuite.
#
# dbsuite is free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# dbsuite is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# dbsuite.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import (
    unicode_literals,
    print_function,
    absolute_import,
    division,
    )

import os
import sys
import logging
import re
import ConfigParser
import optparse
try:
    import cPickle as pickle
except ImportError:
    import pickle

import dbsuite.script
import dbsuite.tokenizer
import dbsuite.plugins
import dbsuite.main


class MyConfigParser(ConfigParser.SafeConfigParser):
    """Tweaked version of SaveConfigParser that uses uppercase for keys"""
    def optionxform(self, optionstr):
        return optionstr.upper()


class PickleHandler(logging.Handler):
    """A basic logging handler which dumps LogRecords as pickles on stdout"""
    def emit(self, record):
        pickle.dump(record, sys.stdout, protocol=pickle.HIGHEST_PROTOCOL)


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
            stoponerror=False,
            terminator=';',
            execinternal=False,
            debuginternal=False,
            logscripts='',
        )
        self.parser.add_option(
            '-t', '--terminator', dest='terminator',
            help='specify the statement terminator (default=";")')
        self.parser.add_option(
            '-a', '--auto-commit', dest='autocommit', action='store_true',
            help='automatically COMMIT after each SQL statement in a script')
        self.parser.add_option(
            '-c', '--config', dest='config',
            help='specify the configuration file')
        self.parser.add_option(
            '-d', '--delete-files', dest='deletefiles', action='store_true',
            help='delete files produced by the scripts after execution')
        self.parser.add_option(
            '-n', '--dry-run', dest='test', action='count',
            help="test but don't run the scripts, can be specified multiple "
            "times: 1x=parse, 2x=test file perms, 3x=test db logins")
        self.parser.add_option(
            '-s', '--stop-on-error', dest='stoponerror', action='store_true',
            help='if a script encounters an error stop it immediately')
        self.parser.add_option(
            '-L', '--log-scripts', dest='logscripts',
            help='if specified scripts will each have their own log file '
            'named by the substitution expression (/regexpr/subst)')
        self.parser.add_option(
            '--exec-internal', dest='execinternal', action='store_true',
            help=optparse.SUPPRESS_HELP)
        self.parser.add_option(
            '--debug-internal', dest='debuginternal', action='store_true',
            help=optparse.SUPPRESS_HELP)

    def main(self, options, args):
        super(ExecSqlUtility, self).main(options, args)
        if options.execinternal:
            # We've been called by a parent dbexec instance to execute an SQL
            # script. Here, we tweak the logging configuration set by the
            # superclass: get rid of the console output (unless we're
            # debugging), and add a custom handler to pickle LogRecords and
            # pass them to the parent instance via stdout
            log = logging.getLogger()
            for handler in log.handlers:
                if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler):
                    if options.debuginternal:
                        handler.setLevel(logging.DEBUG)
                    else:
                        log.removeHandler(handler)
                    break
            if not options.logfile:
                log.addHandler(PickleHandler())
            # Reconstruct the pickled SQLScript that's been passed on stdin and
            # run its exec_internal method
            script = pickle.load(sys.stdin)
            return script._exec_internal()
        else:
            if len(args) == 0:
                self.parser.error('you must specify at least one script to execute')
            # This is a normal dbexec run
            config = os.environ.copy()
            if options.config:
                config.update(self.process_config(options.config))
            if options.logscripts:
                # The following confusing expression splits /expr/subst/ up,
                # allowing for a different split character as in ,expr,subst,
                # (as in sed, vim, etc.) and accounting for backslash escaped
                # split characters
                logexpr, logsubst = re.split(r'(?<!\\)%s' % options.logscripts[:1], options.logscripts[1:])[:2]
                logexpr = re.compile(logexpr)
            else:
                logexpr = logsubst = None
            done_stdin = False
            sql_files = []
            for sql_file in args:
                if sql_file == '-':
                    if not done_stdin:
                        done_stdin = True
                        sql_file = sys.stdin
                    else:
                        raise self.parser.error('cannot read input from stdin multiple times')
                else:
                    sql_file = open(sql_file, 'rU')
                sql_files.append(sql_file)
            plugin = dbsuite.plugins.load_plugin('db2.luw')()
            job = dbsuite.script.SQLJob(
                plugin, sql_files, vars=config,
                terminator=options.terminator,
                autocommit=options.autocommit,
                stoponerror=options.stoponerror,
                deletefiles=options.deletefiles,
                logexpr=logexpr, logsubst=logsubst)
            if options.test == 0:
                job.test_connections()
                job.test_permissions()
                job.execute(debug=options.debug)
            else:
                if options.test > 2:
                    job.test_connections()
                if options.test > 1:
                    job.test_permissions()
                logging.info('')
                job.print_dependencies()
                job.print_transfers()
                for script in job.traversal():
                    logging.info('')
                    logging.info(script.filename)
                    # Write SQL to stdout so it can be redirected if necessary
                    sys.stdout.write(script.sql)
                    sys.stdout.write('\n')
                    sys.stdout.flush()
            return 0

    def handle(self, type, value, tb):
        """Exception hook for non-debug mode."""
        if issubclass(type, (dbsuite.script.Error, dbsuite.tokenizer.Error)):
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
