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


functype = {
    'C': 'Column/Aggregate',
    'R': 'Row',
    'T': 'Table',
    'S': 'Scalar',
}

access = {
    None: 'No SQL',
    'N':  'No SQL',
    'C':  'Contains SQL',
    'R':  'Read-only SQL',
    'M':  'Read-write SQL',
}


class FunctionDocument(HTMLObjectDocument):
    def generate_body(self):
        tag = self.tag
        body = super(FunctionDocument, self).generate_body()
        tag._append(body, (
            tag.div(
                tag.h3('Description'),
                tag.p(self.format_prototype(self.dbobject.prototype)),
                self.format_comment(self.dbobject.description),
                tag.dl((
                    (tag.dt(param.name), tag.dd(self.format_comment(param.description, summary=True)))
                    for param in self.dbobject.param_list
                )),
                class_='section',
                id='description'
            ),
            tag.div(
                tag.h3('Returns'),
                tag.table(
                    tag.thead(
                        tag.tr(
                            tag.th('#', class_='nowrap'),
                            tag.th('Name', class_='nowrap'),
                            tag.th('Type', class_='nowrap'),
                            tag.th('Description', class_='nosort')
                        )
                    ),
                    tag.tbody(
                        tag.tr(
                            tag.td(param.position + 1, class_='nowrap'),
                            tag.td(param.name, class_='nowrap'),
                            tag.td(param.datatype_str, class_='nowrap'),
                            tag.td(param.description)
                        ) for param in self.dbobject.return_list
                    ),
                    id='return-ts',
                    summary='Function returned row/table structure'
                ),
                class_='section',
                id='returns'
            ) if self.dbobject.type in ('R', 'T') else '',
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
                            tag.td(self.site.url_document('created.html').link()),
                            tag.td(self.dbobject.created),
                            tag.td(self.site.url_document('createdby.html').link()),
                            tag.td(self.dbobject.owner)
                        ),
                        tag.tr(
                            tag.td(self.site.url_document('functype.html').link()),
                            tag.td(functype[self.dbobject.type]),
                            tag.td(self.site.url_document('sqlaccess.html').link()),
                            tag.td(access[self.dbobject.sql_access])
                        ),
                        tag.tr(
                            tag.td(self.site.url_document('externalaction.html').link()),
                            tag.td(self.dbobject.external_action),
                            tag.td(self.site.url_document('deterministic.html').link()),
                            tag.td(self.dbobject.deterministic)
                        ),
                        tag.tr(
                            tag.td(self.site.url_document('nullcall.html').link()),
                            tag.td(self.dbobject.null_call),
                            tag.td(self.site.url_document('specificname.html').link()),
                            tag.td(self.dbobject.specific_name)
                        )
                    ),
                    summary='Function attributes'
                ),
                class_='section',
                id='attributes'
            ),
            tag.div(
                tag.h3('Overloaded Versions'),
                tag.p_overloads(self.dbobject),
                tag.table(
                    tag.thead(
                        tag.tr(
                            tag.th('Prototype', class_='nosort'),
                            tag.th('Specific Name', class_='nowrap')
                        )
                    ),
                    tag.tbody((
                        tag.tr(
                            tag.td(self.format_prototype(overload.prototype)),
                            tag.td(tag.a(overload.specific_name, href=self.site.object_document(overload).url), class_='nowrap')
                        )
                        for overload in self.dbobject.schema.functions[self.dbobject.name]
                        if overload is not self.dbobject
                    )),
                    id='overload-ts',
                    summary='Overloaded variants'
                ),
                class_='section',
                id='overloads'
            ) if len(self.dbobject.schema.functions[self.dbobject.name]) > 1 else '',
            tag.div(
                tag.h3('SQL Definition'),
                tag.p_sql_definition(self.dbobject),
                self.format_sql(self.dbobject.create_sql, number_lines=True, id='sql-def'),
                class_='section',
                id='sql'
            ) if self.dbobject.create_sql.strip() else ''
        ))
        return body

