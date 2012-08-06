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


class UniqueKeyDocument(HTMLObjectDocument):
    def generate_body(self):
        tag = self.tag
        body = super(UniqueKeyDocument, self).generate_body()
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
                            tag.td(self.site.url_document('createdby.html').link()),
                            tag.td(self.dbobject.owner),
                            tag.td(self.site.url_document('colcount.html').link()),
                            tag.td(len(self.dbobject.fields))
                        )
                    ),
                    summary='Unique key attributes'
                ),
                class_='section',
                id='attributes'
            ),
            tag.div(
                tag.h3('Fields'),
                tag.p_constraint_fields(self.dbobject),
                tag.table(
                    tag.thead(
                        tag.tr(
                            tag.th('Field', class_='nowrap'),
                            tag.th('Description', class_='nosort')
                        )
                    ),
                    tag.tbody((
                        tag.tr(
                            tag.td(field.name, class_='nowrap'),
                            tag.td(self.format_comment(field.description, summary=True))
                        ) for field in self.dbobject.fields
                    )),
                    id='field-ts',
                    summary='Unique key fields'
                ),
                class_='section',
                id='fields'
            ) if len(self.dbobject.fields) > 0 else '',
            tag.div(
                tag.h3('SQL Definition'),
                tag.p_sql_definition(self.dbobject),
                self.format_sql(self.dbobject.create_sql, number_lines=True, id='sql-def'),
                class_='section',
                id='sql'
            ) if self.dbobject.create_sql else ''
        ))
        return body

