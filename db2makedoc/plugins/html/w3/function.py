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
		overloads = self.dbobject.schema.functions[self.dbobject.name]
		params = list(self.dbobject.param_list) # Take a copy of the parameter list
		if self.dbobject.type in ['R', 'T']:
			# Extend the list with return parameters if the function is a ROW
			# or TABLE function (and hence, returns multiple named params)
			params.extend(self.dbobject.return_list)
		result.append((
			'description', 'Description', [
				tag.p(self.format_prototype(self.dbobject.prototype)),
				tag.p(self.format_comment(self.dbobject.description)),
				tag.dl((
					(tag.dt(param.name), tag.dd(self.format_comment(param.description)))
					for param in params
				))
			]
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
		if len(overloads) > 1:
			result.append((
				'overloads', 'Overloaded Versions',
				tag.table(
					tag.thead(
						tag.tr(
							tag.th('Prototype'),
							tag.th('Specific Name')
						)
					),
					tag.tbody((
						tag.tr(
							tag.td(self.format_prototype(overload.prototype)),
							tag.td(tag.a(overload.specific_name, href=self.site.object_document(overload).url))
						) for overload in overloads if overload != self.dbobject
					))
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

