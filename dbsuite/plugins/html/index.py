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

from dbsuite.plugins.html.document import HTMLObjectDocument


class IndexDocument(HTMLObjectDocument):
    def generate_body(self):
        tag = self.tag
        body = super(IndexDocument, self).generate_body()
        tag._append(body, (
            tag.div(
                tag.h3('Description'),
                self.format_comment(self.dbobject.description),
                class_='section',
                id='description'
            ),
            tag.div(
                tag.h3('Attributes'),
                tag.p_attributes(self.dbobject),
                tag.table(
                    tag.thead(
                        tag.tr(
                            tag.th('Attribute'),
                            tag.th('Value'),
                            tag.th('Attribute'),
                            tag.th('Value')
                        )
                    ),
                    tag.tbody(
                        tag.tr(
                            tag.td('Table'),
                            tag.td(self.site.link_to(self.dbobject.table)),
                            tag.td('Tablespace'),
                            tag.td(self.site.link_to(self.dbobject.tablespace))
                        ),
                        tag.tr(
                            tag.td(self.site.url_document('created.html').link()),
                            tag.td(self.dbobject.created),
                            tag.td(self.site.url_document('laststats.html').link()),
                            tag.td(self.dbobject.last_stats)
                        ),
                        tag.tr(
                            tag.td(self.site.url_document('createdby.html').link()),
                            tag.td(self.dbobject.owner),
                            tag.td(self.site.url_document('colcount.html').link()),
                            tag.td(len(self.dbobject.field_list))
                        ),
                        tag.tr(
                            tag.td(self.site.url_document('unique.html').link()),
                            tag.td(self.dbobject.unique),
                            tag.td(self.site.url_document('cardinality.html').link()),
                            tag.td(self.dbobject.cardinality)
                        )
                        # XXX Include size?
                        # XXX Include system?
                    ),
                    summary='Index attributes'
                ),
                class_='section',
                id='attributes'
            ),
            tag.div(
                tag.h3('Fields'),
                tag.p("""The following table lists the fields covered by
                    the index. The # column indicates the position of the
                    field in the index (this is important as suffixes of an
                    index's fields cannot be used to optimize queries).
                    The Order column lists the ordering of the field in the
                    index (note that some indexes are bidirectional, so
                    this value may be irrelevant)."""),
                tag.table(
                    tag.thead(
                        tag.tr(
                            tag.th('#', class_='nowrap'),
                            tag.th('Name', class_='nowrap'),
                            tag.th('Order', class_='nowrap'),
                            tag.th('Description', class_='nosort')
                        )
                    ),
                    tag.tbody((
                        tag.tr(
                            tag.td(position + 1, class_='nowrap'),
                            tag.td(field.name, class_='nowrap'),
                            tag.td(ordering, class_='nowrap'),
                            tag.td(self.format_comment(field.description, summary=True))
                        ) for (position, (field, ordering)) in enumerate(self.dbobject.field_list)
                    )),
                    id='field-ts',
                    summary='Index fields'
                ),
                class_='section',
                id='fields'
            ) if len(self.dbobject.field_list) > 0 else '',
            tag.div(
                tag.h3('SQL Definition'),
                tag.p_sql_definition(self.dbobject),
                self.format_sql(self.dbobject.create_sql, number_lines=True, id='sql-def'),
                class_='section',
                id='sql'
            ) if self.dbobject.create_sql else ''
        ))
        return body

