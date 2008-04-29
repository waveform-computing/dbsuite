# vim: set noet sw=4 ts=4:

from db2makedoc.db import Trigger
from db2makedoc.plugins.html.plain.document import PlainMainDocument

class PlainTriggerDocument(PlainMainDocument):
	def __init__(self, site, trigger):
		assert isinstance(trigger, Trigger)
		super(PlainTriggerDocument, self).__init__(site, trigger)

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
					'Created',
					self.dbobject.created,
					'Owner',
					self.dbobject.owner,
				),
				(
					'Time',
					trigtime[self.dbobject.trigger_time],
					'Event',
					trigevent[self.dbobject.trigger_event],
				),
				(
					'Granularity',
					granularity[self.dbobject.granularity],
					'Relation',
					self._a_to(self.dbobject.relation, qualifiedname=True),
				),
			]))
		self._section('sql', 'SQL Definition')
		self._add(self._pre(self._format_sql(self.dbobject.create_sql),
			attrs={'class': 'sql'}))

