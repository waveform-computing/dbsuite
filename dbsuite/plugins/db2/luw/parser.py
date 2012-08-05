# vim: set et sw=4 sts=4:

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
