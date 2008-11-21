# vim: set noet sw=4 ts=4:

from db2makedoc.plugins.html.document import HTMLObjectDocument

trigtime = {
	'A': 'After',
	'B': 'Before',
	'I': 'Instead of',
}
trigevent = {
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
		body = super(TriggerDocument, self).generate_body()
		tag = self.tag
		body.append(
			tag.div(
				tag.h3('Description'),
				tag.p(self.format_comment(self.dbobject.description)),
				class_='section',
				id='description'
			)
		)
		body.append(
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
							tag.td(trigtime[self.dbobject.trigger_time]),
							tag.td(self.site.url_document('triggerevent.html').link()),
							tag.td(trigevent[self.dbobject.trigger_event])
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
			)
		)
		if self.dbobject.create_sql:
			body.append(
				tag.div(
					tag.h3('SQL Definition'),
					tag.p_sql_definition(self.dbobject),
					self.format_sql(self.dbobject.create_sql, number_lines=True, id='sql-def'),
					class_='section',
					id='sql'
				)
			)
		return body

