# $Header$
# vim: set noet sw=4 ts=4:

from db2makedoc.db import Trigger
from db2makedoc.plugins.html.w3.document import W3MainDocument

class W3TriggerDocument(W3MainDocument):
	def __init__(self, site, trigger):
		assert isinstance(trigger, Trigger)
		super(W3TriggerDocument, self).__init__(site, trigger)

	def _create_sections(self):
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
		self._section('description', 'Description')
		self._add(self._p(self._format_comment(self.dbobject.description)))
		self._section('attributes', 'Attributes')
		self._add(self._table(
			head=[(
				'Attribute',
				'Value',
				'Attribute',
				'Value'
			)],
			data=[
				(
					self._a(self.site.documents['created.html']),
					self.dbobject.created,
					self._a(self.site.documents['createdby.html']),
					self.dbobject.owner,
				),
				(
					self._a(self.site.documents['triggertiming.html']),
					trigtime[self.dbobject.trigger_time],
					self._a(self.site.documents['triggerevent.html']),
					trigevent[self.dbobject.trigger_event],
				),
				(
					self._a(self.site.documents['granularity.html']),
					granularity[self.dbobject.granularity],
					'Relation',
					self._a_to(self.dbobject.relation, qualifiedname=True),
				),
			]))
		self._section('sql', 'SQL Definition')
		self._add(self._pre(self._format_sql(self.dbobject.create_sql,
			terminator='!'), attrs={'class': 'sql'}))

