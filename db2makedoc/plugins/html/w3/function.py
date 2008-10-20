# vim: set noet sw=4 ts=4:

from db2makedoc.db import Function
from db2makedoc.plugins.html.w3.document import W3ObjectDocument, tag

functype = {
	'C': 'Column/Aggregate',
	'R': 'Row',
	'T': 'Table',
	'S': 'Scalar',
}
access = {
	None: 'No SQL',
	'N':  'No SQL',
	'C':  'Contains SQL',
	'R':  'Read-only SQL',
	'M':  'Modifies SQL',
}

class W3FunctionDocument(W3ObjectDocument):
	def __init__(self, site, function):
		assert isinstance(function, Function)
		super(W3FunctionDocument, self).__init__(site, function)
	
	def generate_sections(self):
		result = super(W3FunctionDocument, self).generate_sections()
		result.append((
			'description', 'Description', [
				tag.p(self.format_prototype(self.dbobject.prototype)),
				tag.p(self.format_comment(self.dbobject.description)),
				tag.dl((
					(tag.dt(param.name), tag.dd(self.format_comment(param.description)))
					for param in self.dbobject.param_list
				))
			]
		))
		if self.dbobject.type in ('R', 'T'):
			result.append((
				'returns', 'Returns',
				tag.table(
					tag.thead(
						tag.tr(
							tag.th('#'),
							tag.th('Name'),
							tag.th('Type'),
							tag.th('Description')
						)
					),
					tag.tbody(
						tag.tr(
							tag.td(param.position + 1),
							tag.td(param.name, class_='nowrap'),
							tag.td(param.datatype_str, class_='nowrap'),
							tag.td(param.description)
						) for param in self.dbobject.return_list
					)
				)
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
						tag.td(self.site.url_document('functype.html').link()),
						tag.td(functype[self.dbobject.type]),
						tag.td(self.site.url_document('sqlaccess.html').link()),
						tag.td(access[self.dbobject.sql_access])
					),
					tag.tr(
						tag.td(self.site.url_document('externalaction.html').link()),
						tag.td(self.dbobject.external_action),
						tag.td(self.site.url_document('deterministic.html').link()),
						tag.td(self.dbobject.deterministic)
					),
					tag.tr(
						tag.td(self.site.url_document('nullcall.html').link()),
						tag.td(self.dbobject.null_call),
						tag.td(self.site.url_document('specificname.html').link()),
						tag.td(self.dbobject.specific_name)
					)
				)
			)
		))
		if len(self.dbobject.schema.functions[self.dbobject.name]) > 1:
			result.append((
				'overloads', 'Overloaded Versions',
				tag.table(
					tag.thead(
						tag.tr(
							tag.th('Prototype', class_='nosort'),
							tag.th('Specific Name')
						)
					),
					tag.tbody((
						tag.tr(
							tag.td(self.format_prototype(overload.prototype)),
							tag.td(tag.a(overload.specific_name, href=self.site.object_document(overload).url))
						)
						for overload in self.dbobject.schema.functions[self.dbobject.name]
						if overload != self.dbobject
					)),
					id='overload-ts'
				)
			))
		if self.dbobject.create_sql:
			result.append((
				'sql', 'SQL Definition', [
					tag.p(tag.a('Line #s On/Off', href='#', onclick='javascript:return toggleLineNums("sqldef");')),
					self.format_sql(self.dbobject.create_sql, number_lines=True, id='sqldef')
				]
			))
		return result

