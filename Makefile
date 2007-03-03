# $Header$
# vim: set noet sw=4 ts=4:

BASE:=$(shell python setup.py --fullname)
SRCS:=$(shell python setup.py sdist --manifest-only >/dev/null 2>&1 && cat MANIFEST)

WININST=dist/$(BASE).win32.exe
RPMS=dist/$(BASE)-1.noarch.rpm dist/$(BASE)-1.src.rpm
SRCTAR=dist/$(BASE).tar.gz
SRCZIP=dist/$(BASE).zip

all: dist

clean:
	rm -f $(WININST) $(RPMS) $(SRCTAR) $(SRCZIP) MANIFEST README.txt
	rm -fr build/

dist: bdist sdist

bdist: $(WININST) $(RPMS)

sdist: $(SRCTAR) $(SRCZIP)

$(WININST): $(SRCS) README.txt
	python setup.py bdist_wininst

$(RPMS): $(SRCS) README.txt
	python setup.py bdist_rpm

$(SRCTAR): $(SRCS) README.txt
	python setup.py sdist --formats=gztar

$(SRCZIP): $(SRCS) README.txt
	python setup.py sdist --formats=zip

MANIFEST: MANIFEST.in setup.py
	python setup.py sdist --manifest-only

%.txt: %.html
	links -dump $< > $@
