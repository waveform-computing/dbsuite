# $Header$
# vim: set noet sw=4 ts=4:

# External utilities
PYTHON=python
PYFLAGS=
#LYNX=lynx
#LYNXFLAGS=-nonumbers -justify
#LYNX=links
#LYNXFLAGS=
LYNX=elinks
LYNXFLAGS=-no-numbering -no-references

# Calculate the base name of the distribution, the location of all source files
# and documentation files
BASE:=$(shell $(PYTHON) $(PYFLAGS) setup.py --fullname)
SRCS:=$(shell \
	$(PYTHON) $(PYFLAGS) setup.py sdist --manifest-only >/dev/null 2>&1 && \
	cat MANIFEST && \
	rm MANIFEST)
DOCS:=$(wildcard *.html)
TXT:=$(DOCS:%.html=%.txt)

# Calculate the name of all distribution archives / installers
WININST=dist/$(BASE).win32.exe
RPMS=dist/$(BASE)-1.noarch.rpm dist/$(BASE)-1.src.rpm
SRCTAR=dist/$(BASE).tar.gz
SRCZIP=dist/$(BASE).zip

# Default target
build:
	$(PYTHON) $(PYFLAGS) setup.py build

install:
	$(PYTHON) $(PYFLAGS) setup.py install

test:
	echo No tests currently implemented
	#cd examples && ./runtests.sh

clean:
	$(PYTHON) $(PYFLAGS) setup.py clean
	rm -f $(WININST) $(RPMS) $(SRCTAR) $(SRCZIP) $(TXT) MANIFEST
	rm -fr build/

dist: bdist sdist

bdist: $(WININST) $(RPMS)

sdist: $(SRCTAR) $(SRCZIP)

$(WININST): $(SRCS) $(TXT)
	$(PYTHON) $(PYFLAGS) setup.py bdist --formats=wininst

$(RPMS): $(SRCS) $(TXT)
	$(PYTHON) $(PYFLAGS) setup.py bdist --formats=rpm

$(SRCTAR): $(SRCS) $(TXT)
	$(PYTHON) $(PYFLAGS) setup.py sdist --formats=gztar

$(SRCZIP): $(SRCS) $(TXT)
	$(PYTHON) $(PYFLAGS) setup.py sdist --formats=zip

MANIFEST: MANIFEST.in setup.py $(TXT)
	$(PYTHON) $(PYFLAGS) setup.py sdist --manifest-only

%.txt: %.html
	links -dump $< > $@
