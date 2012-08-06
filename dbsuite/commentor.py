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

"""Implements a class for the extraction of comment related statements.

This module provides a utility class which can be used to extract all
statements related to setting comments for database objects from an input
script. Ths class is designed to work with traditional comment systems (i.e.
SYSCAT) and the alternate DOCCAT scheme provided by the contrib scripts
distributed with this utility.
"""

from __future__ import (
    unicode_literals,
    print_function,
    absolute_import,
    division,
    )

import logging

from dbsuite.tokenizer import Token, TokenTypes as TT
from dbsuite.parser import dump


class Error(Exception):
    pass


class TransitionError(Error):
    pass


class State(object):
    """Represents a state in a transition graph.

    The printing attribute indicates whether or not the state prints the
    current token. If True, it is a printing state. If False, it is a
    non-printing state.

    The transitions attribute is a dictionary of token templates which the
    graph matches against the current token and uses to decide the next state.
    If no templates match, the next state is set to the value of the default
    attribute.
    """
    def __init__(self, name, printing):
        super(State, self).__init__()
        self.name = name
        self.printing = printing
        self.default = None
        self.transitions = []
    def __getitem__(self, token):
        if token.type in (TT.WHITESPACE, TT.COMMENT):
            new_state = self
        else:
            new_state = None
            for (template, state) in self.transitions:
                if token[:len(template)] == template:
                    new_state = state
                    break
            if new_state is None:
                raise TransitionError('No valid transition defined from state %s for token %s (%s)' % (self, TT.names[token.type], token.source))
        return new_state
    def __setitem__(self, template, new_state):
        self.transitions.append((template, new_state))
    def __str__(self):
        return self.name


class SetSchemaState(State):
    def __init__(self, name, graph, printing):
        super(SetSchemaState, self).__init__(name, printing)
        self.graph = graph
    def __getitem__(self, token):
        if token.type in (TT.IDENTIFIER, TT.STRING):
            self.graph.schema = token.value
        return super(SetSchemaState, self).__getitem__(token)


class CheckSchemaState(State):
    def __init__(self, name, graph, schema='DOCCAT'):
        super(CheckSchemaState, self).__init__(name, printing=False)
        self.graph = graph
        self.schema = schema
    def __getitem__(self, token):
        if token.type == TT.SCHEMA and token.value == self.schema:
            return self.graph.printing
        elif token.type == TT.RELATION and self.graph.schema == self.schema:
            return self.graph.printing
        else:
            return self.graph.skipping
    def __setitem__(self, template, new_state):
        raise NotImplementedError


class Graph(object):
    """The state transition graph for the DFSA."""
    def __init__(self):
        super(Graph, self).__init__()
        self.schema = None
        # Create all the states up front
        self.start = State('<start>', None)
        self.printing = State('<printing>', True)
        self.skipping = State('<skipping>', False)
        self.connect_reset = State('connect-reset', True)
        self.connect_username = SetSchemaState('connect-username', self, True)
        self.connect_user = State('connect-user', True)
        self.connect_db = State('connect-db', True)
        self.connect_to = State('connect-to', True)
        self.connect = State('connect', True)
        self.disconnect = State('disconnect', True)
        self.comment = State('comment', True)
        self.set = State('set', False)
        self.set_current = State('set-current', False)
        self.set_schema = SetSchemaState('set-schema', self, True)
        self.set_equals = SetSchemaState('set-equals', self, True)
        self.schema_name = State('schema-name', True)
        self.merge = State('merge', False)
        self.merge_into = CheckSchemaState('merge-into', self)
        self.update = CheckSchemaState('update', self)
        # Fill in the transitions for each state
        self.printing[(TT.STATEMENT,)] = self.start
        self.printing[()] = self.printing
        self.skipping[(TT.STATEMENT,)] = self.start
        self.skipping[()] = self.skipping
        self.start[(TT.KEYWORD, 'CONNECT')] = self.connect
        self.start[(TT.KEYWORD, 'DISCONNECT')] = self.disconnect
        self.start[(TT.KEYWORD, 'COMMENT')] = self.comment
        self.start[(TT.KEYWORD, 'SET')] = self.set
        self.start[(TT.KEYWORD, 'MERGE')] = self.merge
        self.start[(TT.KEYWORD, 'UPDATE')] = self.update
        self.start[()] = self.skipping
        self.connect[(TT.KEYWORD, 'RESET')] = self.connect_reset
        self.connect[(TT.KEYWORD, 'TO')] = self.connect_to
        self.connect_reset[(TT.STATEMENT,)] = self.start
        self.connect_to[(TT.STRING,)] = self.connect_db
        self.connect_db[(TT.STATEMENT,)] = self.start
        self.connect_db[(TT.KEYWORD, 'USER')] = self.connect_user
        self.connect_user[(TT.STRING,)] = self.connect_username
        self.connect_username[(TT.STATEMENT,)] = self.start
        self.connect_username[()] = self.printing
        self.disconnect[()] = self.printing
        self.comment[()] = self.printing
        self.set[(TT.KEYWORD, 'SCHEMA')] = self.set_schema
        self.set[(TT.KEYWORD, 'CURRENT')] = self.set_current
        self.set[()] = self.skipping
        self.set_current[(TT.KEYWORD, 'SCHEMA')] = self.set_schema
        self.set_current[()] = self.skipping
        self.set_schema[(TT.IDENTIFIER,)] = self.schema_name
        self.set_schema[(TT.OPERATOR, '=')] = self.set_equals
        self.set_equals[(TT.IDENTIFIER,)] = self.schema_name
        self.schema_name[(TT.STATEMENT,)] = self.start
        self.merge[(TT.KEYWORD, 'INTO')] = self.merge_into

    def parse(self, tokens):
        schema = None
        state = self.start
        printing = False
        statement_start = 0
        result = []
        for index, token in enumerate(tokens):
            state = state[token]
            # If we're at the start of a statement, remember the index in case
            # it's an ambiguous statement where we won't know whether or not to
            # print it until we've at least partially parsed it
            if state == self.start:
                statement_start = index
            # If the state has printing set to "None" leave the current
            # printing state as it is
            if state.printing is not None:
                # If printing changes state to True, print everything from the
                # start of the statement to here
                if state.printing and not printing:
                    for t in tokens[statement_start:index]:
                        result.append(t)
                printing = state.printing
            # Print the current token if required
            if printing and token.type != TT.COMMENT:
                result.append(token)
        return result

class SQLCommentExtractor(object):
    def __init__(self, plugin):
        super(SQLCommentExtractor, self).__init__()
        self.tokenizer = plugin.tokenizer()
        self.formatter = plugin.parser(for_scripts=True)
        self.graph = Graph()

    def parse(self, sql, terminator=';'):
        def excerpt(tokens):
            if len(tokens) > 10:
                excerpt = tokens[:10] + [Token(0, None, '...', 0, 0)]
            else:
                excerpt = tokens
            return ''.join(token.source for token in excerpt)

        self.formatter.terminator = terminator
        tokens = self.formatter.parse(self.tokenizer.parse(sql, terminator))
        # Check for errors in the tokens
        errors = [token for token in tokens if token.type == TT.ERROR]
        if errors:
            # If errors were found, log a warning for each error and return the
            # SQL highlighted from the tokenized stream without reformatting
            logging.warning('While tokenizing %s' % excerpt(tokens))
            for error in errors:
                logging.warning('error %s found at line %d, column %d' % (error.value, error.line, error.column))
        else:
            return ''.join(token.source for token in self.graph.parse(tokens))

