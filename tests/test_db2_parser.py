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

from nose.tools import assert_raises
from dbsuite.parser import ParseError
from dbsuite.plugins.db2.luw.tokenizer import DB2LUWTokenizer
from dbsuite.plugins.db2.luw.parser import DB2LUWParser

def check(sql):
    tokenizer = DB2LUWTokenizer()
    parser = DB2LUWParser()
    parser.parse(tokenizer.parse(sql))

def check_fails(sql):
    assert_raises(ParseError, check, sql)

def test_create_index():
    check("CREATE INDEX FOO_PK ON FOO(ID);")
    check("CREATE UNIQUE INDEX FOO_PK ON FOO(ID1, ID2 DESC);")
    check("CREATE INDEX SPEC ON FOO(BAR) SPECIFICATION ONLY;")
    check("CREATE INDEX FOO_TIME ON FOO(BAR ASC, BAZ, BUSINESS_TIME WITHOUT OVERLAPS) COMPRESS YES;")
    check("CREATE INDEX SPACE_CK ON FOO(BAR, BAZ, QUUX) LEVEL2 PCTFREE 5 PCTFREE 20;")
    check("CREATE INDEX STATS ON FOO(BAR) COLLECT SAMPLED DETAILED STATISTICS;")
    check_fails("CREATE INDEX FOO3 ON FOO();")
    check_fails("CREATE INDEX FOO2 ON FOO(ID) PARTITIONED NOT PARTITIONED;")
    check_fails("CREATE INDEX BAR ON BAZ(ID1, ID2) PAGE SPLIT BLAH;")
    check_fails("CREATE INDEX TOO ON FOO(BAR) ALLOW REVERSE SCANS PARTITIONED DISALLOW REVERSE SCANS;")
