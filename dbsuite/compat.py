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

"""Defines general utility methods and functions.

This module backports some built-in functions from later Python versions, in
particular the any() and all() functions from Python 2.5 and namedtuple() from
Python 2.6, and defines some useful generic recipes.
"""

from __future__ import (
    unicode_literals,
    print_function,
    absolute_import,
    division,
    )

import sys

__all__ = ['namedslice', 'cachedproperty']


def namedslice(cls, obj):
    """Copies values from obj into the namedtuple class cls by field name.

    Given a namedtuple object in obj, and a namedtuple class in cls, this
    function returns a namedtuple of type cls with values taken from obj.  This
    is useful when dealing with namedtuple types which are based partly on
    other namedtuple types, for example:

        >>> nt1 = namedtuple('nt1', ('field1', 'field2'))
        >>> nt2 = namedtuple('nt2', ('field3', 'field4'))
        >>> nt3 = namedtuple('nt3', nt1._fields + nt2._fields)
        >>> nt3._fields
        ('field1', 'field2', 'field3', 'field4')
        >>> obj = nt3(1, 2, 3, 4)
        >>> namedslice(nt1, obj)
        nt1(field1=1, field2=2)
        >>> obj = nt2(3, 4)
        >>> namedslice(nt3, obj)
        nt3(field1=None, field2=None, field3=3, field4=4)

    Note that it doesn't matter if the target type has a different number of
    fields to the source object. Fields which exist in the source object but
    not the target class will simply be omitted in the result, while fields
    which exist in the target class but not the source object will be None in
    the result.
    """
    assert isinstance(obj, tuple)
    assert issubclass(cls, tuple)
    assert hasattr(obj, '_fields')
    assert hasattr(cls, '_fields')
    return cls(*(getattr(obj, attr, None) for attr in cls._fields))


class cachedproperty(property):
    """Convert a method into a cached property"""

    def __init__(self, method):
        private = '_' + method.__name__
        def fget(s):
            try:
                return getattr(s, private)
            except AttributeError:
                value = method(s)
                setattr(s, private, value)
                return value
        super(cachedproperty, self).__init__(fget)


__all__.append('terminal_size')
if sys.platform.startswith('win'):
    # ctypes query_console_size() adapted from
    # http://code.activestate.com/recipes/440694/
    import ctypes

    def terminal_size():
        "Returns the size (cols, rows) of the console"

        def get_handle_size(handle):
            "Subroutine for querying terminal size from std handle"
            handle = ctypes.windll.kernel32.GetStdHandle(handle)
            if handle:
                buf = ctypes.create_string_buffer(22)
                if ctypes.windll.kernel32.GetConsoleScreenBufferInfo(
                        handle, buf):
                    (left, top, right, bottom) = struct.unpack(
                        str('hhhhHhhhhhh'), buf.raw)[5:9]
                    return (right - left + 1, bottom - top + 1)
            return None

        stdin, stdout, stderr = -10, -11, -12
        return (
            get_handle_size(stderr) or
            get_handle_size(stdout) or
            get_handle_size(stdin) or
            # Default
            (80, 25)
        )

else:
    import fcntl
    import termios
    import os

    def terminal_size():
        "Returns the size (cols, rows) of the console"

        def get_handle_size(handle):
            "Subroutine for querying terminal size from std handle"
            try:
                buf = fcntl.ioctl(handle, termios.TIOCGWINSZ, '12345678')
                row, col = struct.unpack(str('hhhh'), buf)[0:2]
                return (col, row)
            except IOError:
                return None

        stdin, stdout, stderr = 0, 1, 2
        # Try stderr first as it's the least likely to be redirected
        result = (
            get_handle_size(stderr) or
            get_handle_size(stdout) or
            get_handle_size(stdin)
        )
        if not result:
            fd = os.open(os.ctermid(), os.O_RDONLY)
            try:
                result = get_handle_size(fd)
            finally:
                os.close(fd)
        if not result:
            try:
                result = (os.environ['COLUMNS'], os.environ['LINES'])
            except KeyError:
                # Default
                result = (80, 24)
        return result
