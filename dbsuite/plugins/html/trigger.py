# vim: set et sw=4 sts=4:

from dbsuite.plugins.html.document import HTMLObjectDocument

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
        trig_node = graph.add_node(trigger, selected=True)
        rel_node = graph.add_node(trigger.relation)
        rel_edge = graph.add_edge(rel_node, trig_node,
            label=('<%s %s>' % (
                times[trigger.trigger_time],
                events[trigger.trigger_event]
            )).lower(),
            arrowhead='vee')
        for dependency in trigger.dependency_list:
            dep_node = graph.add_node(dependency)
            dep_edge = graph.add_edge(trig_node, dep_node,
                label='<uses>', arrowhead='onormal')
        return graph
