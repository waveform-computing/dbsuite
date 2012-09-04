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

from dbsuite.plugins.html.document import HTMLObjectDocument, GraphObjectDocument


times = {
    'A': 'After',
    'B': 'Before',
    'I': 'Instead of',
}

events = {
    'I': 'Insert',
    'U': 'Update',
    'D': 'Delete',
}

granularity = {
    'R': 'Row',
    'S': 'Statement',
}


class TriggerDocument(HTMLObjectDocument):
    def generate_body(self):
        tag = self.tag
        body = super(TriggerDocument, self).generate_body()
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
                            tag.td(self.site.url_document('created.html').link()),
                            tag.td(self.dbobject.created),
                            tag.td(self.site.url_document('createdby.html').link()),
                            tag.td(self.dbobject.owner)
                        ),
                        tag.tr(
                            tag.td(self.site.url_document('triggertiming.html').link()),
                            tag.td(times[self.dbobject.trigger_time]),
                            tag.td(self.site.url_document('triggerevent.html').link()),
                            tag.td(events[self.dbobject.trigger_event])
                        ),
                        tag.tr(
                            tag.td(self.site.url_document('granularity.html').link()),
                            tag.td(granularity[self.dbobject.granularity]),
                            tag.td('Relation'),
                            tag.td(self.site.link_to(self.dbobject.relation))
                        )
                    ),
                    summary='Trigger attributes'
                ),
                class_='section',
                id='attributes'
            ),
            tag.div(
                tag.h3('Diagram'),
                tag.p_diagram(self.dbobject),
                self.site.img_of(self.dbobject),
                class_='section',
                id='diagram'
            ) if self.site.object_graph(self.dbobject) else '',
            tag.div(
                tag.h3('SQL Definition'),
                tag.p_sql_definition(self.dbobject),
                self.format_sql(self.dbobject.create_sql, number_lines=True, id='sql-def'),
                class_='section',
                id='sql'
            ) if self.dbobject.create_sql else ''
        ))
        return body


class TriggerGraph(GraphObjectDocument):
    def generate(self):
        graph = super(TriggerGraph, self).generate()
        trigger = self.dbobject
        relation = trigger.relation
        graph.add_node(trigger, selected=True)
        graph.add_node(relation)
        graph.add_edge(relation, trigger,
            label=('<%s %s>' % (
                times[trigger.trigger_time],
                events[trigger.trigger_event]
            )).lower(),
            arrowhead='vee')
        for dependency in trigger.dependency_list:
            graph.add_node(dependency)
            graph.add_edge(trigger, dependency,
                label='<uses>', arrowhead='onormal')
        return graph
