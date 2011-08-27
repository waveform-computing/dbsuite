# vim: set noet sw=4 ts=4:

import sys
mswindows = sys.platform == "win32"

import os
import subprocess
from dbsuite.compat import *

def get_instance(name=None):
	"""Constructs an instance from an instance name or returns the current instance"""
	result = {}
	if name is None:
		for key in (
			'DB2INSTANCE',
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
	elif mswindows:
		# XXX No idea how to do this on Windows yet
		raise NotImplementedError
	else:
		# Run a shell to source the new instance's DB2 profile
		cmdline = ' '.join([
			'. ~%s/sqllib/db2profile' % name,
			'&& echo DB2INSTANCE=$DB2INSTANCE',
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

