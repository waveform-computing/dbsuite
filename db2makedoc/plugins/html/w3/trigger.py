# $Header$
# vim: set noet sw=4 ts=4:

from db2makedoc.db.trigger import Trigger
from db2makedoc.plugins.html.w3.document import W3MainDocument

class W3TriggerDocument(W3MainDocument):
	def __init__(self, site, trigger):
		assert isinstance(trigger, Trigger)
		super(W3TriggerDocument, self).__init__(site, trigger)

	def create_sections(self):
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
		self.section('description', 'Description')
		self.add(self.p(self.format_comment(self.dbobject.description)))
		self.section('attributes', 'Attributes')
		self.add(self.table(
			head=[(
				'Attribute',
				'Value',
				'Attribute',
				'Value'
			)],
			data=[
				(
					self.a(self.site.documents['created.html']),
					self.dbobject.created,
					self.a(self.site.documents['createdby.html']),
					self.dbobject.owner,
				),
				(
					self.a(self.site.documents['triggertiming.html']),
					trigtime[self.dbobject.trigger_time],
					self.a(self.site.documents['triggerevent.html']),
					trigevent[self.dbobject.trigger_event],
				),
				(
					self.a(self.site.documents['granularity.html']),
					granularity[self.dbobject.granularity],
					'Relation',
					self.a_to(self.dbobject.relation, qualifiedname=True),
				),
			]))
		self.section('sql', 'SQL Definition')
		self.add(self.pre(self.format_sql(self.dbobject.create_sql,
			terminator='!'), attrs={'class': 'sql'}))

