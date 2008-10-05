import sys
import os

def create_launcher(script):
	# Calculate the name of the interpreter we're installing for (can't use
	# sys.executable as it returns the name of the installer at runtime)
	interpreter = os.path.join(sys.prefix, 'python.exe')
	# Calculate the name of the launcher script
	cmd_filename = os.path.join(sys.prefix, 'Scripts', '%s.cmd' % script)
	print >> sys.stdout, 'Creating launcher script %s' % cmd_filename
	cmd_file = open(cmd_filename, 'w')
	try:
		file_created(cmd_filename)
		cmd_file.write("""\
@echo off
rem Stub to allow %(script)s to be called without having to specify Python directly
"%(interpreter)s" "%%~dp0\%(script)s" %%*
""" % {'interpreter': interpreter, 'script': script})
		print >> sys.stdout, 'Launcher script %s created successfully' % script
	finally:
		cmdfile.close()

if __name__ == '__main__':
	create_launcher('db2makedoc')
	create_launcher('db2tidysql')
