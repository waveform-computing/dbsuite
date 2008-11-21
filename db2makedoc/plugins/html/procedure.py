# vim: set noet sw=4 ts=4:

from db2makedoc.plugins.html.document import HTMLObjectDocument

access = {
	None: 'No SQL',
	'N':  'No SQL',
	'C':  'Contains SQL',
	'R':  'Read-only SQL',
	'M':  'Modifies SQL',
}

class ProcedureDocument(HTMLObjectDocument):
	def generate_body(self):
		body = super(ProcedureDocument, self).generate_body()
		tag = self.tag
		body.append(
			tag.div(
				tag.h3('Description'),
				tag.p(self.format_prototype(self.dbobject.prototype)),
				tag.p(self.format_comment(self.dbobject.description)),
				# XXX What about the IN/OUT/INOUT state of procedure parameters?
				tag.dl((
					(tag.dt(param.name), tag.dd(self.format_comment(param.description)))
					for param in self.dbobject.param_list
				)),
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
							tag.td(self.site.url_document('sqlaccess.html').link()),
							tag.td(access[self.dbobject.sql_access]),
							tag.td(self.site.url_document('nullcall.html').link()),
							tag.td(self.dbobject.null_call)
						),
						tag.tr(
							tag.td(self.site.url_document('externalaction.html').link()),
							tag.td(self.dbobject.external_action),
							tag.td(self.site.url_document('deterministic.html').link()),
							tag.td(self.dbobject.deterministic)
						),
						tag.tr(
							tag.td(self.site.url_document('specificname.html').link()),
							tag.td(self.dbobject.specific_name, colspan=3)
						)
					),
					summary='Procedure attributes'
				),
				class_='section',
				id='attributes'
			)
		)
		if len(self.dbobject.schema.procedures[self.dbobject.name]) > 1:
			body.append(
				tag.div(
					tag.h3('Overloaded Versions'),
					tag.p_overloads(self.dbobject),
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
							for overload in self.dbobject.schema.procedures[self.dbobject.name]
							if overload is not self.dbobject
						)),
						id='overload-ts',
						summary='Overloaded variants'
					),
					class_='section',
					id='overloads'
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

