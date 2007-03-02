# $Header$
# vim: set noet sw=4 ts=4:

BASE:=$(shell python ../setup.py --fullname)

WININST=$(BASE).win32.exe
RPMS=$(BASE)-1.noarch.rpm $(BASE)-1.src.rpm
SRCTAR=$(BASE).tar.gz
SRCZIP=$(BASE).zip

all: bdist sdist

clean:
	rm -f $(WININST) $(RPMS) $(SRCTAR) $(SRCZIP)

bdist: $(WININST) $(RPMS)

sdist: $(SRCTAR) $(SRCZIP)

$(WININST):
	cd .. &&  python setup.py bdist_wininst

$(RPMS):
	cd .. && python setup.py bdist_rpm

$(SRCTAR):
	cd .. && python setup.py sdist --formats=gztar

$(SRCZIP):
	cd .. && python setup.py sdist --formats=zip

