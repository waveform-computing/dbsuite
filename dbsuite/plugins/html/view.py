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


class ViewDocument(HTMLObjectDocument):
    def generate_body(self):
        tag = self.tag
        body = super(ViewDocument, self).generate_body()
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
                            tag.td(self.site.url_document('colcount.html').link()),
                            tag.td(len(self.dbobject.field_list)),
                            tag.td(self.site.url_document('readonly.html').link()),
                            tag.td(self.dbobject.read_only)
                        ),
                        tag.tr(
                            tag.td(self.site.url_document('dependentrel.html').link()),
                            tag.td(len(self.dbobject.dependent_list)),
                            tag.td(self.site.url_document('dependenciesrel.html').link()),
                            tag.td(len(self.dbobject.dependency_list))
                        ),
                        summary='View attributes'
                        # XXX Include system?
                    )
                ),
                class_='section',
                id='attributes'
            ),
            tag.div(
                tag.h3('Fields'),
                tag.p_relation_fields(self.dbobject),
                tag.table(
                    tag.thead(
                        tag.tr(
                            tag.th('#', class_='nowrap'),
                            tag.th('Name', class_='nowrap'),
                            tag.th('Type', class_='nowrap'),
                            tag.th('Nulls', class_='nowrap'),
                            tag.th('Description', class_='nosort')
                        )
                    ),
                    tag.tbody((
                        tag.tr(
                            tag.td(field.position, class_='nowrap'),
                            tag.td(field.name, class_='nowrap'),
                            tag.td(field.datatype_str, class_='nowrap'),
                            tag.td(field.nullable, class_='nowrap'),
                            tag.td(self.format_comment(field.description, summary=True))
                        ) for field in self.dbobject.field_list
                    )),
                    id='field-ts',
                    summary='View fields'
                ),
                class_='section',
                id='fields'
            ) if len(self.dbobject.field_list) > 0 else '',
            tag.div(
                tag.h3('Triggers'),
                tag.p_triggers(self.dbobject),
                tag.table(
                    tag.thead(
                        tag.tr(
                            tag.th('Name', class_='nowrap'),
                            tag.th('Timing', class_='nowrap'),
                            tag.th('Event', class_='nowrap'),
                            tag.th('Description', class_='nosort')
                        )
                    ),
                    tag.tbody((
                        tag.tr(
                            tag.td(self.site.link_to(trigger), class_='nowrap'),
                            tag.td(times[trigger.trigger_time], class_='nowrap'),
                            tag.td(events[trigger.trigger_event], class_='nowrap'),
                            tag.td(self.format_comment(trigger.description, summary=True))
                        ) for trigger in self.dbobject.trigger_list
                    )),
                    id='trigger-ts',
                    summary='View triggers'
                ),
                class_='section',
                id='triggers'
            ) if len(self.dbobject.trigger_list) > 0 else '',
            tag.div(
                tag.h3('Dependent Relations'),
                tag.p_dependent_relations(self.dbobject),
                tag.table(
                    tag.thead(
                        tag.tr(
                            tag.th('Name', class_='nowrap'),
                            tag.th('Type', class_='nowrap'),
                            tag.th('Description', class_='nosort')
                        )
                    ),
                    tag.tbody((
                        tag.tr(
                            tag.td(self.site.link_to(dep), class_='nowrap'),
                            tag.td(self.site.type_names[dep.__class__], class_='nowrap'),
                            tag.td(self.format_comment(dep.description, summary=True))
                        ) for dep in self.dbobject.dependent_list
                    )),
                    id='rdep-ts',
                    summary='View dependents'
                ),
                class_='section',
                id='dependents'
            ) if len(self.dbobject.dependent_list) > 0 else '',
            tag.div(
                tag.h3('Dependencies'),
                tag.p_dependencies(self.dbobject),
                tag.table(
                    tag.thead(
                        tag.tr(
                            tag.th('Name', class_='nowrap'),
                            tag.th('Type', class_='nowrap'),
                            tag.th('Description', class_='nosort')
                        )
                    ),
                    tag.tbody((
                        tag.tr(
                            tag.td(self.site.link_to(dep), class_='nowrap'),
                            tag.td(self.site.type_names[dep.__class__], class_='nowrap'),
                            tag.td(self.format_comment(dep.description, summary=True))
                        ) for dep in self.dbobject.dependency_list
                    )),
                    id='dep-ts',
                    summary='View dependencies'
                ),
                class_='section',
                id='dependencies'
            ) if len(self.dbobject.dependency_list) > 0 else '',
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

class ViewGraph(GraphObjectDocument):
    def generate(self):
        graph = super(ViewGraph, self).generate()
        view = self.dbobject
        view_node = graph.add_node(view, selected=True)
        for dependent in view.dependent_list:
            dep_node = graph.add_node(dependent)
            dep_edge = graph.add_edge(dep_node, view_node,
                label='<uses>', arrowhead='onormal')
        for dependency in view.dependency_list:
            dep_node = graph.add_node(dependency)
            dep_edge = graph.add_edge(view_node, dep_node,
                label='<uses>', arrowhead='onormal')
        for trigger in view.trigger_list:
            trig_node = graph.add_node(trigger)
            trig_edge = graph.add_edge(view_node, trig_node,
                label=('<%s %s>' % (
                    times[trigger.trigger_time],
                    events[trigger.trigger_event]
                )).lower(),
                arrowhead='vee')
            for dependency in trigger.dependency_list:
                dep_node = graph.add_node(dependency)
                dep_edge = graph.add_edge(trig_node, dep_node,
                    label='<uses>', arrowhead='onormal')
        for trigger in view.trigger_dependent_list:
            trig_node = graph.add_node(trigger)
            rel_node = graph.add_node(trigger.relation)
            trig_edge = graph.add_edge(rel_node, trig_node,
                label=('<%s %s>' % (
                    times[trigger.trigger_time],
                    events[trigger.trigger_event]
                )).lower(),
                arrowhead='vee')
            dep_edge = graph.add_edge(trig_node, view_node,
                label='<uses>', arrowhead='onormal')
        return graph
