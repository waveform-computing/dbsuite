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


rules = {
    'C': 'Cascade',
    'N': 'Set NULL',
    'A': 'Raise Error',
    'R': 'Raise Error',
}


class ForeignKeyDocument(HTMLObjectDocument):
    def generate_body(self):
        tag = self.tag
        body = super(ForeignKeyDocument, self).generate_body()
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
                            tag.td('Referenced Table'),
                            tag.td(self.site.link_to(self.dbobject.ref_table)),
                            tag.td('Referenced Key'),
                            tag.td(self.site.link_to(self.dbobject.ref_key))
                        ),
                        tag.tr(
                            tag.td(self.site.url_document('created.html').link()),
                            tag.td(self.dbobject.created),
                            tag.td(self.site.url_document('createdby.html').link()),
                            tag.td(self.dbobject.owner)
                        ),
                        tag.tr(
                            tag.td(self.site.url_document('deleterule.html').link()),
                            tag.td(rules[self.dbobject.delete_rule]),
                            tag.td(self.site.url_document('updaterule.html').link()),
                            tag.td(rules[self.dbobject.update_rule])
                        )
                    ),
                    summary='Foreign key attributes'
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
                            tag.th('#', class_='nowrap'),
                            tag.th('Field', class_='nowrap'),
                            tag.th('Parent', class_='nowrap'),
                            tag.th('Description', class_='nosort')
                        )
                    ),
                    tag.tbody((
                        tag.tr(
                            tag.td(index + 1, class_='nowrap'),
                            tag.td(field1.name, class_='nowrap'),
                            tag.td(field2.name, class_='nowrap'),
                            tag.td(self.format_comment(field1.description, summary=True))
                        ) for (index, (field1, field2)) in enumerate(self.dbobject.fields)
                    )),
                    id='field-ts',
                    summary='Foreign key fields'
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

