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

import sys
import logging

import dbsuite.commentor
import dbsuite.plugins
import dbsuite.main
import dbsuite.tokenizer
from dbsuite.compat import *

class GrepDocUtility(dbsuite.main.Utility):
    """%prog [options] source...

    This utility filters source SQL files for only those lines related to
    commenting database objects. For example, given a file which contains
    CONNECT, CREATE TABLE, CREATE INDEX, CREATE VIEW, SET SCHEMA, and COMMENT
    ON statements, the output would include only the CONNECT, SET SCHEMA, and
    COMMENT ON statements as only those are required for commenting on the
    database objects. Either specify the names of files containing the SQL to
    reformat, or specify - to indicate that stdin should be read. The filtered
    SQL will be written to stdout in either case. The available command line
    options are listed below.
    """

    def __init__(self):
        super(GrepDocUtility, self).__init__()
        self.parser.set_defaults(terminator=';')
        self.parser.add_option('-t', '--terminator', dest='terminator',
            help="""specify the statement terminator (default=';')""")

    def main(self, options, args):
        super(GrepDocUtility, self).main(options, args)
        done_stdin = False
        # XXX Add method to select input plugin
        plugin = dbsuite.plugins.load_plugin('db2.luw')()
        extractor = dbsuite.commentor.SQLCommentExtractor(plugin)
        rc = 0
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
            try:
                sql = extractor.parse(sql, terminator=options.terminator)
            except dbsuite.tokenizer.Error, e:
                logging.error('In file %s:' % sql_file.name)
                logging.error(str(e))
                rc = 3
            else:
                sys.stdout.write(sql)
            sys.stdout.flush()
        return rc

main = GrepDocUtility()

