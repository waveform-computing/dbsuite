# vim: set noet sw=4 ts=4:

from db2makedoc.db import Trigger
from db2makedoc.plugins.html.w3.document import W3ObjectDocument, tag

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

class W3TriggerDocument(W3ObjectDocument):
	def __init__(self, site, trigger):
		assert isinstance(trigger, Trigger)
		super(W3TriggerDocument, self).__init__(site, trigger)

	def generate_sections(self):
		result = super(W3TriggerDocument, self).generate_sections()
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
				)
			)
		))
		if self.dbobject.create_sql:
			result.append((
				'sql', 'SQL Definition', [
					tag.p(tag.a('Line #s On/Off', href='#', onclick='javascript:return toggleLineNums("sqldef");', class_='zoom')),
					self.format_sql(self.dbobject.create_sql, number_lines=True, id='sqldef')
				]
			))
		return result

