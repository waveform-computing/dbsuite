# vim: set noet sw=4 ts=4:

from db2makedoc.db import Trigger
from db2makedoc.plugins.html.plain.document import PlainObjectDocument

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

class PlainTriggerDocument(PlainObjectDocument):
	def __init__(self, site, trigger):
		assert isinstance(trigger, Trigger)
		super(PlainTriggerDocument, self).__init__(site, trigger)

	def generate_sections(self):
		tag = self.tag
		result = super(PlainTriggerDocument, self).generate_sections()
		result.append((
			'description', 'Description',
			tag.p(self.format_comment(self.dbobject.description))
		))
		result.append((
			'attributes', 'Attributes',
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
			)
		))
		if self.dbobject.create_sql:
			result.append((
				'sql', 'SQL Definition',
				self.format_sql(self.dbobject.create_sql, number_lines=True, id='sql-def')
			))
		return result

