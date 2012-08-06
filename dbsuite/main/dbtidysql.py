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

import dbsuite.highlighters
import dbsuite.plugins
import dbsuite.main


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
        self.parser.add_option(
            '-t', '--terminator', dest='terminator',
            help='specify the statement terminator (default=';')')

    def main(self, options, args):
        super(TidySqlUtility, self).main(options, args)
        done_stdin = False
        # XXX Add method to select input plugin
        plugin = dbsuite.plugins.load_plugin('db2.luw')()
        highlighter = dbsuite.highlighters.SQLHighlighter(plugin, for_scripts=True)
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

