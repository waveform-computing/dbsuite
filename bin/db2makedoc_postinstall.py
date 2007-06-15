import sys
import os

if __name__ == '__main__':
	# Calculate the name of the interpreter we're installing for (can't use
	# sys.executable as it returns the name of the installer at runtime)
	python = os.path.join(sys.prefix, 'python.exe')
	# Calculate the name of the launcher script
	cmdfilename = os.path.join(sys.prefix, 'Scripts', 'db2makedoc.cmd')
	print >> sys.stdout, 'Creating launcher script %s' % cmdfilename
	cmdfile = open(cmdfilename, 'w')
	try:
		file_created(cmdfilename)
		cmdfile.write("""\
@echo off
rem Stub to allow db2makedoc to be called without having to specify Python directly
"%s" "%%~dp0\db2makedoc" %%*
""" % python)
		print >> sys.stdout, 'Launcher script created successfully'
	finally:
		cmdfile.close()
