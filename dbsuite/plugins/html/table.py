# vim: set et sw=4 sts=4:

from itertools import chain
from dbsuite.db import Alias, View, ForeignKey, PrimaryKey, UniqueKey, Check
from dbsuite.plugins.html.document import HTMLObjectDocument, GraphObjectDocument

orders = {
    'A': 'Ascending',
    'D': 'Descending',
    'I': 'Include',
}
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

class TableDocument(HTMLObjectDocument):
    def generate_body(self):

        def fields(constraint):
            # Small sub-routine for formatting the fields of constraints
            if isinstance(constraint, ForeignKey):
                return [
                    'References ',
                    self.site.link_to(constraint.ref_table),
                    tag.ol((tag.li('%s -> %s' % (cfield.name, pfield.name)) for (cfield, pfield) in constraint.fields), style=olstyle)
                ]
            elif isinstance(constraint, PrimaryKey) or isinstance(constraint, UniqueKey) or isinstance(constraint, Check):
                return tag.ol((tag.li(cfield.name) for cfield in constraint.fields), style=olstyle)
            else:
                return ''

        olstyle = 'list-style-type: none; padding: 0; margin: 0;'
        if self.dbobject.primary_key is None:
            key_count = 0
        else:
            key_count = len(self.dbobject.primary_key.fields)
        tag = self.tag
        body = super(TableDocument, self).generate_body()
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
                            tag.td(self.site.url_document('laststats.html').link()),
                            tag.td(self.dbobject.last_stats)
                        ),
                        tag.tr(
                            tag.td(self.site.url_document('createdby.html').link()),
                            tag.td(self.dbobject.owner),
                            tag.td(self.site.url_document('cardinality.html').link()),
                            tag.td(self.dbobject.cardinality)
                        ),
                        tag.tr(
                            tag.td(self.site.url_document('keycolcount.html').link()),
                            tag.td(key_count),
                            tag.td(self.site.url_document('colcount.html').link()),
                            tag.td(len(self.dbobject.field_list))
                        ),
                        tag.tr(
                            tag.td(self.site.url_document('dependentrel.html').link()),
                            tag.td(
                                len(self.dbobject.dependents) +
                                sum(len(k.dependent_list) for k in self.dbobject.unique_key_list)
                            ),
                            tag.td(self.site.url_document('size.html').link()),
                            tag.td(self.dbobject.size_str)
                        )
                        # XXX Include system?
                    ),
                    summary='Table attributes'
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
                            tag.th('Key Pos', class_='nowrap'),
                            tag.th('Cardinality', class_='nowrap commas'),
                            tag.th('Description', class_='nosort')
                        )
                    ),
                    tag.tbody((
                        tag.tr(
                            tag.td(field.position, class_='nowrap'),
                            tag.td(field.name, class_='nowrap'),
                            tag.td(field.datatype_str, class_='nowrap'),
                            tag.td(field.nullable, class_='nowrap'),
                            tag.td(field.key_index, class_='nowrap'),
                            tag.td(field.cardinality, class_='nowrap'),
                            tag.td(self.format_comment(field.description, summary=True))
                        ) for field in self.dbobject.field_list
                    )),
                    id='field-ts',
                    summary='Table fields'
                ),
                class_='section',
                id='fields'
            ) if len(self.dbobject.field_list) > 0 else '',
            tag.div(
                tag.h3('Indexes'),
                tag.p("""The following table lists the indexes that apply
                    to this table, whether or not the index enforces a
                    unique rule, and the fields that the index covers.
                    Click on an index name to view the full documentation
                    for that index."""),
                tag.table(
                    tag.thead(
                        tag.tr(
                            tag.th('Name', class_='nowrap'),
                            tag.th('Unique', class_='nowrap'),
                            tag.th('Fields', class_='nosort'),
                            tag.th('Sort Order', class_='nosort'),
                            tag.th('Description', class_='nosort')
                        )
                    ),
                    tag.tbody((
                        tag.tr(
                            tag.td(self.site.link_to(index), class_='nowrap'),
                            tag.td(index.unique, class_='nowrap'),
                            tag.td(tag.ol((tag.li(ixfield.name) for (ixfield, _) in index.field_list), style=olstyle)),
                            tag.td(tag.ol((tag.li(orders[ixorder]) for (_, ixorder) in index.field_list), style=olstyle)),
                            tag.td(self.format_comment(index.description, summary=True))
                        ) for index in self.dbobject.index_list
                    )),
                    id='index-ts',
                    summary='Table indexes'
                ),
                class_='section',
                id='indexes'
            ) if len(self.dbobject.index_list) > 0 else '',
            tag.div(
                tag.h3('Constraints'),
                tag.p("""The following table lists all constraints that
                    apply to this table, including the fields constrained
                    in each case. Click on a constraint's name to view the
                    full documentation for that constraint."""),
                tag.table(
                    tag.thead(
                        tag.tr(
                            tag.th('Name', class_='nowrap'),
                            tag.th('Type', class_='nowrap'),
                            tag.th('Fields', class_='nosort'),
                            tag.th('Description', class_='nosort')
                        )
                    ),
                    tag.tbody((
                        tag.tr(
                            tag.td(self.site.link_to(constraint), class_='nowrap'),
                            tag.td(self.site.type_names[constraint.__class__], class_='nowrap'),
                            tag.td(fields(constraint)),
                            tag.td(self.format_comment(constraint.description, summary=True))
                        ) for constraint in self.dbobject.constraint_list
                    )),
                    id='const-ts',
                    summary='Table constraints'
                ),
                class_='section',
                id='constraints'
            ) if len(self.dbobject.constraint_list) > 0 else '',
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
                    id='trig-ts',
                    summary='Table triggers'
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
                        ) for dep in chain(
                            self.dbobject.dependent_list,
                            (
                                fkey.relation
                                for ukey in self.dbobject.unique_key_list
                                for fkey in ukey.dependent_list
                            )
                        )
                    )),
                    id='dep-ts',
                    summary='Table dependents'
                ),
                class_='section',
                id='dependents'
            ) if len(self.dbobject.dependents) + sum(len(k.dependent_list) for k in self.dbobject.unique_key_list) > 0 else '',
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

class TableGraph(GraphObjectDocument):
    def generate(self):
        graph = super(TableGraph, self).generate()
        table = self.dbobject
        table_node = graph.add_node(table, selected=True)
        for dependent in table.dependent_list:
            dep_node = graph.add_node(dependent)
            dep_edge = graph.add_edge(table_node, dep_node,
                arrowhead='onormal',
                label='<uses>' if isinstance(dependent, View) else
                '<for>' if isinstance(dependent, Alias) else
                '')
        for key in table.foreign_key_list:
            key_node = graph.add_node(key.ref_table)
            key_edge = graph.add_edge(table_node, key_node,
                dbobject=key, arrowhead='normal', label=key.name)
        for key in table.unique_key_list:
            for dependent in key.dependent_list:
                dep_node = graph.add_node(dependent.relation)
                dep_edge = graph.add_edge(dep_node, table_node,
                    dbobject=dependent, label=dependent.name,
                    arrowhead='normal')
        for trigger in table.trigger_list:
            trig_node = graph.add_node(trigger)
            trig_edge = graph.add_edge(table_node, trig_node,
                label=('<%s %s>' % (
                    times[trigger.trigger_time],
                    events[trigger.trigger_event]
                )).lower(),
                arrowhead='vee')
            for dependency in trigger.dependency_list:
                dep_node = graph.add_node(dependency)
                dep_edge = graph.add_edge(trig_node, dep_node,
                    label='<uses>', arrowhead='onormal')
        for trigger in table.trigger_dependent_list:
            trig_node = graph.add_node(trigger)
            rel_node = graph.add_node(trigger.relation)
            trig_edge = graph.add_edge(rel_node, trig_node,
                label=('<%s %s>' % (
                    times[trigger.trigger_time],
                    events[trigger.trigger_event]
                )).lower(),
                arrowhead='vee')
            dep_edge = graph.add_edge(trig_node, table_node,
                label='<uses>', arrowhead='onormal')
        return graph
