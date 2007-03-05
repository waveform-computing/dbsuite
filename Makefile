# $Header$
# vim: set noet sw=4 ts=4:

BASE:=$(shell python setup.py --fullname)
SRCS:=$(shell \
	python setup.py sdist --manifest-only >/dev/null 2>&1 && \
	cat MANIFEST && \
	rm MANIFEST)
DOCS:=$(wildcard *.html)
TXT:=$(DOCS:%.html=%.txt)

WININST=dist/$(BASE).win32.exe
RPMS=dist/$(BASE)-1.noarch.rpm dist/$(BASE)-1.src.rpm
SRCTAR=dist/$(BASE).tar.gz
SRCZIP=dist/$(BASE).zip

all: dist

clean:
	rm -f $(WININST) $(RPMS) $(SRCTAR) $(SRCZIP) $(TXT) MANIFEST
	rm -fr build/

dist: bdist sdist

bdist: $(WININST) $(RPMS)

sdist: $(SRCTAR) $(SRCZIP)

$(WININST): $(SRCS) $(TXT)
	python setup.py bdist_wininst

$(RPMS): $(SRCS) $(TXT)
	python setup.py bdist_rpm

$(SRCTAR): $(SRCS) $(TXT)
	python setup.py sdist --formats=gztar

$(SRCZIP): $(SRCS) $(TXT)
	python setup.py sdist --formats=zip

MANIFEST: MANIFEST.in setup.py $(TXT)
	python setup.py sdist --manifest-only

%.txt: %.html
	links -dump $< > $@
