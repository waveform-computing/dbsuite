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

from dbsuite.etree import ElementFactory, iselement

def test_element():
    tag = ElementFactory()
    test_tag = tag.a()
    assert iselement(test_tag)
    assert test_tag.tag == 'a'
    assert len(test_tag.attrib) == 0

def test_attributes():
    tag = ElementFactory()
    test_tag = tag.a(foo='a', bar=1, baz=True, quux=False, xyzzy=None, class_='test')
    assert len(test_tag.attrib) == 4
    assert test_tag.attrib['foo'] == 'a'
    assert test_tag.attrib['bar'] == '1'
    assert test_tag.attrib['baz'] != ''
    assert test_tag.attrib['class'] == 'test'
    assert 'quux' not in test_tag.attrib
    assert 'xyzzy' not in test_tag.attrib

def test_content():
    tag = ElementFactory()
    test_doc = tag.a('quux', tag.b('foo'), 'bar', tag.c(tag.d(), 'baz'), 'xyzzy')
    assert len(test_doc) == 2
    assert test_doc.text == 'quux'
    assert not test_doc.tail
    assert test_doc[0].tag == 'b'
    assert test_doc[0].text == 'foo'
    assert test_doc[0].tail == 'bar'
    assert test_doc[1].tag == 'c'
    assert test_doc[1].text == 'baz' or test_doc[1][0].tail == 'baz'
    assert test_doc[1].tail == 'xyzzy'
    assert len(test_doc[1]) == 1
    assert test_doc[1][0].tag == 'd'
    assert not test_doc[1][0].text
    assert len(test_doc[1][0]) == 0

def test_namespaces():
    tag = ElementFactory(namespace='foo')
    test_tag = tag.a(bar=True)
    assert test_tag.tag == '{foo}a'
    assert '{foo}bar' in test_tag.attrib
