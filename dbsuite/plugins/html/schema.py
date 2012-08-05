# vim: set et sw=4 sts=4:

from dbsuite.db import Table, View, Alias
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

class SchemaDocument(HTMLObjectDocument):
    def generate_body(self):
        tag = self.tag
        body = super(SchemaDocument, self).generate_body()
        tag._append(body, (
            tag.div(
                tag.h3('Description'),
                self.format_comment(self.dbobject.description),
                class_='section',
                id='description'
            ),
            tag.div(
                tag.h3('Relations'),
                tag.p("""The following table lists the relations (tables,
                    views, and aliases) that belong to the schema. Click on
                    a relation's name to view the documentation for that
                    relation."""),
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
                            tag.td(self.site.link_to(relation), class_='nowrap'),
                            tag.td(self.site.type_names[relation.__class__], class_='nowrap'),
                            tag.td(self.format_comment(relation.description, summary=True))
                        ) for relation in self.dbobject.relation_list
                    )),
                    id='relation-ts',
                    summary='Schema relations'
                ),
                class_='section',
                id='relations'
            ) if len(self.dbobject.relation_list) > 0 else '',
            tag.div(
                tag.h3('Indexes'),
                tag.p("""The following table lists the indexes that belong
                    to the schema. Note that an index can apply to a table
                    in a different schema. Click on an index name to view
                    the documentation for that index."""),
                tag.table(
                    tag.thead(
                        tag.tr(
                            tag.th('Name', class_='nowrap'),
                            tag.th('Unique', class_='nowrap'),
                            tag.th('Applies To', class_='nowrap'),
                            tag.th('Description', class_='nosort')
                        )
                    ),
                    tag.tbody((
                        tag.tr(
                            tag.td(self.site.link_to(index), class_='nowrap'),
                            tag.td(index.unique, class_='nowrap'),
                            tag.td(self.site.link_to(index.table), class_='nowrap'),
                            tag.td(self.format_comment(index.description, summary=True))
                        ) for index in self.dbobject.index_list
                    )),
                    id='index-ts',
                    summary='Schema indexes'
                ),
                class_='section',
                id='indexes'
            ) if len(self.dbobject.index_list) > 0 else '',
            tag.div(
                tag.h3('Triggers'),
                tag.p("""The following table lists the triggers that belong
                    to the schema (and the tables and views they apply to).
                    Note that a trigger can apply to a table or view in a
                    different schema. Click on a trigger name to view the
                    documentation for that trigger."""),
                tag.table(
                    tag.thead(
                        tag.tr(
                            tag.th('Name', class_='nowrap'),
                            tag.th('Timing', class_='nowrap'),
                            tag.th('Event', class_='nowrap'),
                            tag.th('Applies To', class_='nowrap'),
                            tag.th('Description', class_='nosort')
                        )
                    ),
                    tag.tbody((
                        tag.tr(
                            tag.td(self.site.link_to(trigger), class_='nowrap'),
                            tag.td(times[trigger.trigger_time], class_='nowrap'),
                            tag.td(events[trigger.trigger_event], class_='nowrap'),
                            tag.td(self.site.link_to(trigger.relation), class_='nowrap'),
                            tag.td(self.format_comment(trigger.description, summary=True))
                        ) for trigger in self.dbobject.trigger_list
                    )),
                    id='trigger-ts',
                    summary='Schema triggers'
                ),
                class_='section',
                id='triggers'
            ) if len(self.dbobject.trigger_list) > 0 else '',
            tag.div(
                tag.h3('Routines'),
                tag.p("""The following table lists the routines (user
                    defined functions and stored procedures) that belong to
                    this schema. Click on a routine's name to view the
                    documentation for that routine."""),
                tag.table(
                    tag.thead(
                        tag.tr(
                            tag.th('Name', class_='nowrap'),
                            tag.th('Specific Name', class_='nowrap'),
                            tag.th('Type', class_='nowrap'),
                            tag.th('Description', class_='nosort')
                        )
                    ),
                    tag.tbody((
                        tag.tr(
                            tag.td(self.site.link_to(routine), class_='nowrap'),
                            tag.td(routine.specific_name, class_='nowrap'),
                            tag.td(self.site.type_names[routine.__class__], class_='nowrap'),
                            tag.td(self.format_comment(routine.description, summary=True))
                        ) for routine in self.dbobject.routine_list
                    )),
                    id='routine-ts',
                    summary='Schema routines'
                ),
                class_='section',
                id='routines'
            ) if len(self.dbobject.routine_list) > 0 else '',
            tag.div(
                tag.h3('Diagram'),
                tag.p_diagram(self.dbobject),
                self.site.img_of(self.dbobject),
                class_='section',
                id='diagram'
            ) if len(self.dbobject.relation_list) > 0 else ''
        ))
        return body

class SchemaGraph(GraphObjectDocument):
    def generate(self):
        graph = super(SchemaGraph, self).generate()
        schema = self.dbobject
        graph.add_subgraph(schema, selected=True)
        for relation in schema.relation_list:
            rel_node = graph.add_node(relation)
            for dependent in relation.dependent_list:
                dep_node = graph.add_node(dependent)
                dep_edge = graph.add_edge(dep_node, rel_node,
                    arrowhead='onormal')
            if isinstance(relation, Table):
                for key in relation.foreign_key_list:
                    key_node = graph.add_node(key.ref_table)
                    key_edge = graph.add_edge(rel_node, key_node,
                        arrowhead='normal')
                for trigger in relation.trigger_list:
                    trig_node = graph.add_node(trigger)
                    trig_edge = graph.add_edge(rel_node, trig_node,
                        arrowhead='vee')
                    for dependency in trigger.dependency_list:
                        dep_node = graph.add_node(dependency)
                        dep_edge = graph.add_edge(trig_node, dep_node,
                            arrowhead='onormal')
            elif isinstance(relation, View):
                for dependency in relation.dependency_list:
                    dep_node = graph.add_node(dependency)
                    dep_edge = graph.add_edge(rel_node, dep_node,
                        arrowhead='onormal')
                for trigger in relation.trigger_list:
                    trig_node = graph.add_node(trigger)
                    trig_edge = graph.add_edge(rel_node, trig_node,
                        arrowhead='vee')
                    for dependency in trigger.dependency_list:
                        dep_node = graph.add_node(dependency)
                        dep_edge = graph.add_edge(trig_node, dep_node,
                            arrowhead='onormal')
            elif isinstance(relation, Alias):
                ref_node = graph.add_node(relation.relation)
                ref_edge = graph.add_edge(rel_node, ref_node,
                    arrowhead='onormal')
        for trigger in schema.trigger_list:
            rel_node = graph.add_node(trigger.relation)
            trig_node = graph.add_node(trigger)
            trig_edge = graph.add_edge(rel_node, trig_node,
                arrowhead='vee')
            for dependency in trigger.dependency_list:
                dep_node = graph.add_node(dependency)
                dep_edge = graph.add_edge(trig_node, dep_node,
                    arrowhead='onormal')
        return graph
