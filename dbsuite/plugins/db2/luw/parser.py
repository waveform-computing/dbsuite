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

from dbsuite.plugins.db2.zos.parser import DB2ZOSParser, DB2ZOSScriptParser
from dbsuite.plugins.db2.luw.tokenizer import db2luw_namechars, db2luw_identchars

class DB2LUWParser(DB2ZOSParser):
    def __init__(self):
        super(DB2LUWParser, self).__init__()
        self.namechars = db2luw_namechars
        self.identchars = db2luw_identchars

class DB2LUWScriptParser(DB2ZOSScriptParser):
    def __init__(self):
        super(DB2LUWScriptParser, self).__init__()
        self.namechars = db2luw_namechars
        self.identchars = db2luw_identchars
