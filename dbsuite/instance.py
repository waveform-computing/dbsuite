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
import os
import subprocess


def get_instance(name=None):
    """Constructs an instance from an instance name or returns the current instance"""
    result = {}
    if name is None:
        for key in (
            'DB2INSTANCE',
            'IBM_DB_DIR',
            'IBM_DB_LIB',
            'IBM_DB_INCLUDE',
            'DB2_HOME',
            'DB2LIB',
            'PATH',
            'CLASSPATH',
            'LIBPATH',
            'SHLIB_PATH',
            'LD_LIBRARY_PATH',
            'LD_LIBRARY_PATH_32',
            'LD_LIBRARY_PATH_64',
        ):
            result[key] = os.environ.get(key)
        return result
    elif sys.platform.startswith('win'):
        # XXX No idea how to do this on Windows yet
        raise NotImplementedError
    else:
        # Run a shell to source the new instance's DB2 profile
        cmdline = ' '.join([
            '. ~%s/sqllib/db2profile' % name,
            '&& echo DB2INSTANCE=$DB2INSTANCE',
            '&& echo IBM_DB_DIR=$IBM_DB_DIR',
            '&& echo IBM_DB_LIB=$IBM_DB_LIB',
            '&& echo IBM_DB_INCLUDE=$IBM_DB_INCLUDE',
            '&& echo DB2_HOME=$DB2_HOME',
            '&& echo DB2LIB=$DB2LIB',
            '&& echo PATH=$PATH',
            '&& echo CLASSPATH=$CLASSPATH',
            '&& echo LIBPATH=$LIBPATH',
            '&& echo SHLIB_PATH=$SHLIB_PATH',
            '&& echo LD_LIBRARY_PATH=$LD_LIBRARY_PATH',
            '&& echo LD_LIBRARY_PATH_32=$LD_LIBRARY_PATH_32',
            '&& echo LD_LIBRARY_PATH_64=$LD_LIBRARY_PATH_64'
        ])
        p = subprocess.Popen(
            cmdline,
            shell=True,
            stdin=None,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            close_fds=True
        )
        output = p.communicate()[0]
        if p.returncode != 0:
            raise ValueError(
                'Instance %s does not exist or cannot be sourced' % name)
        for line in output.splitlines():
            var, value = line.split('=', 1)
            result[var] = value
        return result

def set_instance(instance):
    """Restore an instance from an earlier get_instance() call"""
    for key, value in instance.iteritems():
        if value is not None:
            os.environ[key] = value
        elif key in os.environ:
            del os.environ[key]

