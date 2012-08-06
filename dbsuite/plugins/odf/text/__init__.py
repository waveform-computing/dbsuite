# vim: set et sw=4 sts=4:

# Copyright 2012 Dave Hughes.
#
# This file is part of dbsuite.
#
# dbsuite is free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# dbsuite is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# dbsuite.  If not, see <http://www.gnu.org/licenses/>.

"""Output plugin for OpenDocument text (DEVELOPMENT)."""

from __future__ import (
    unicode_literals,
    print_function,
    absolute_import,
    division,
    )

import logging
import zipfile
import datetime
from pkg_resources import resource_string, resource_stream
from string import Template

import dbsuite.plugins
from dbsuite.highlighters import CommentHighlighter, SQLHighlighter
from dbsuite.db import (
    Schema, Datatype, Table, View, Alias, Constraint, Index, Trigger, Function,
    Procedure, Tablespace
)
from dbsuite.parser import quote_str, format_ident
from dbsuite.etree import Element, ElementFactory, indent, tostring, _namespace_map


class ODFElementFactory(ElementFactory):
    def __init__(self):
        super(ODFElementFactory, self).__init__()
        self._odf_namespaces = {
            'anim':         'urn:oasis:names:tc:opendocument:xmlns:anim:1.0',
            'chart':        'urn:oasis:names:tc:opendocument:xmlns:chart:1.0',
            'config':       'urn:oasis:names:tc:opendocument:xmlns:config:1.0',
            'dc':           'http://purl.org/dc/elements/1.1/',
            'dr3d':         'urn:oasis:names:tc:opendocument:xmlns:dr3d:1.0',
            'drawing':      'urn:oasis:names:tc:opendocument:xmlns:drawing:1.0',
            'form':         'urn:oasis:names:tc:opendocument:xmlns:form:1.0',
            'fo':           'urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0',
            'manifest':     'urn:oasis:names:tc:opendocument:xmlns:manifest:1.0',
            'math':         'http://www.w3.org/1998/Math/MathML',
            'meta':         'urn:oasis:names:tc:opendocument:xmlns:meta:1.0',
            'number':       'urn:oasis:names:tc:opendocument:xmlns:number:1.0',
            'office':       'urn:oasis:names:tc:opendocument:xmlns:office:1.0',
            'presentation': 'urn:oasis:names:tc:opendocument:xmlns:presentation:1.0',
            'script':       'urn:oasis:names:tc:opendocument:xmlns:script:1.0',
            'smil':         'urn:oasis:names:tc:opendocument:xmlns:smil-compatible:1.0',
            'style':        'urn:oasis:names:tc:opendocument:xmlns:style:1.0',
            'svg':          'urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0',
            'table':        'urn:oasis:names:tc:opendocument:xmlns:table:1.0',
            'text':         'urn:oasis:names:tc:opendocument:xmlns:text:1.0',
            'xforms':       'http://www.w3.org/2002/xforms',
            'xlink':        'http://www.w3.org/1999/xlink',
        }
        # Update ElementTree's namespace map with the myriad namespaces used by
        # ODF (this isn't strictly necessary but it helps with debugging)
        _namespace_map.update(dict(
            (value, name) for (name, value) in self._odf_namespaces.iteritems()
        ))

    def _element(self, _name, *content, **attrs):
        # ODF relies heavily on lots of namespaces and has a nasty habit of
        # mixing namespaces in elements and attributes. Here, we assume that
        # the first part of any element or attribute name (prior to the first
        # underscore) is a namespace indicator which we can lookup in our ODF
        # namespace dictionary. We also replace any remaining underscores with
        # dash as ODF relies heavily on such names and obviously we can't use
        # dash in Python identifiers
        def ns_conv(name):
            (ns, name) = name.split('_', 1)
            return '{%s}%s' % (self._odf_namespaces[ns], name.replace('_', '-'))
        return super(ODFElementFactory, self)._element(ns_conv(_name), *content, **dict(
            (ns_conv(key), value)
            for (key, value) in attrs.iteritems()
        ))


class ODFCommentHighlighter(CommentHighlighter):
    """Class which converts simple comment markup into ODF.

    This subclass of the generic comment highlighter class overrides the stub
    methods to convert the comment into HTML. The construction of the HTML
    elements is actually handled by the methods of the ODFElementFactory object
    passed to the constructor as opposed to the methods in this class.
    """

    def __init__(self, database, tag):
        super(ODFCommentHighlighter, self).__init__()
        self.database = database
        self.tag = tag

    def start_parse(self, summary):
        self._content = []

    def start_para(self):
        self._para = []

    def handle_text(self, text):
        self._para.append(text)

    def handle_strong(self, text):
        self._para.append(self.tag.text_span(text, text_style_name='bold'))

    def handle_emphasize(self, text):
        self._para.append(self.tag.text_span(text, text_style_name='italic'))

    def handle_underline(self, text):
        self._para.append(self.tag.text_span(text, text_style_name='underline'))

    def find_target(self, name):
        return self.database.find(name)

    def handle_link(self, target):
        # XXX Need to figure out a linking method
        return ''

    def end_para(self):
        self._content.append(self.tag.text_p(self._para, text_style_name='text_body'))

    def end_parse(self, summary):
        return self._content


class OutputPlugin(dbsuite.plugins.OutputPlugin):
    """Output plugin for OpenDocument text.

    This output plugin generates documentation in the OpenDocument text
    document (.odt).  It includes syntax highlighted SQL, information on
    various objects in the database (views, tables, etc.) and diagrams of the
    schema.
    """

    def __init__(self):
        super(OutputPlugin, self).__init__()
        self.add_option('filename', default=None, convert=self.convert_path,
            doc="""The path and filename for the output file. Use $db or ${db}
            to include the name of the database in the filename. The $dblower
            and $dbupper substitutions are also available, for forced lowercase
            and uppercase versions of the name respectively. To include a
            literal $, use $$""")
        self.add_option('author_name', default='',
            doc="""The name of the author of the generated document""")
        self.add_option('author_email', default='',
            doc="""The e-mail address of the author of the generated document""")
        self.add_option('copyright', default='',
            doc="""The copyright message to embed in the generated document""")
        self.add_option('title', default = 'Data Dictionary',
            doc="""The title of the generated document. Supports the same
            subsitutions as the filename option""")
        self.add_option('diagrams', default='', convert=self.convert_dbclasses,
            doc="""A comma separated list of the object types for which
            diagrams should be generated, e.g. "schemas, relations". Currently
            only diagrams of schemas and relations (tables, views, and aliases)
            are supported. Note that schema diagrams may require an extremely
            large amount of RAM (1Gb+) to process""")
        self.add_option('index', default='false', convert=self.convert_bool,
            doc="""If true, generate an alphabetical index of all entries at
            the end of the generated document""")

    def configure(self, config):
        super(OutputPlugin, self).configure(config)
        # Ensure the filename was specified
        if not self.options['filename']:
            raise dbsuite.plugins.PluginConfigurationError('The filename option must be specified')

    def execute(self, database):
        super(OutputPlugin, self).execute(database)
        self.encoding = 'UTF-8'
        self.created = datetime.datetime.now().replace(microsecond=0)
        self.database = database
        self.default_desc = 'No description in the system catalog'
        self.tag = ODFElementFactory()
        self.comment_highlighter = ODFCommentHighlighter(self.database, self.tag)
        # Translate any templates in the filename option now that we've got the
        # database
        substitutions = {
            'db': database.name,
            'dblower': database.name.lower(),
            'dbupper': database.name.upper(),
            'dbtitle': database.name.title(),
        }
        if not 'filename_template' in self.options:
            self.options['filename_template'] = Template(self.options['filename'])
        self.options['filename'] = self.options['filename_template'].safe_substitute(substitutions)
        if not 'title_template' in self.options:
            self.options['title_template'] = Template(self.options['title'])
        self.options['title'] = self.options['title_template'].safe_substitute(substitutions)
        # Build a list of dictionary of files to place in the archive, along with attributes
        # of those files
        self.manifest = set()
        self.queue = set()
        self.add_file('content.xml', 'text/xml', self.generate_content)
        self.add_file('meta.xml', 'text/xml', self.generate_meta)
        self.add_file('settings.xml', 'text/xml', self.generate_settings)
        self.add_file('styles.xml', 'text/xml', self.generate_styles)
        # Build the archive. According to the standard, mimetype must be
        # included first, without compression to enable tools to determine the
        # file-type without having to know about the zip structure or
        # decompression algorithm. We must generate the manifest last in case,
        # in the course of generating other content, we cause other files to be
        # added to the document
        f = zipfile.ZipFile(self.options['filename'], 'w')
        f.writestr(self.zip_info('mimetype', compress=False), self.generate_mimetype())
        while self.queue:
            (info, method) = self.queue.pop()
            f.writestr(info, method())
        f.writestr(self.zip_info('META-INF/manifest.xml'), self.generate_manifest())

    def zip_info(self, filename, compress=True, created=None):
        if created is None:
            created = self.created
        info = zipfile.ZipInfo(filename, (
            created.year,
            created.month,
            created.day,
            created.hour,
            created.minute,
            created.second
        ))
        info.compress_type = [zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED][bool(compress)]
        return info

    def add_file(self, filename, mimetype, method, compress=True, created=None):
        info = self.zip_info(filename, compress, created)
        self.manifest.add((info, mimetype))
        self.queue.add((info, method))

    def format_comment(self, comment, summary=False):
        return self.comment_highlighter.parse(comment or self.default_desc)

    def generate_manifest(self):
        tag = self.tag
        doc = tag.manifest_manifest(
            tag.manifest_file_entry(manifest_media_type=self.generate_mimetype(), manifest_full_path='/'),
            (
                tag.manifest_file_entry(manifest_media_type=mimetype, manifest_full_path=info.filename)
                for (info, mimetype) in self.manifest
            )
        )
        doc = u'<?xml version="1.0" encoding="%s"?>%s' % (self.encoding, tostring(doc))
        return doc.encode(self.encoding)

    def generate_meta(self):
        tag = self.tag
        doc = tag.office_document_meta(
            tag.office_meta(
                tag.meta_generator('db2makedoc'), # XXX enhance this a bit ;)
                tag.dc_title(self.options['title']),
                tag.dc_description(''), # XXX fill this in?
                tag.dc_subject(self.database.name),
                tag.dc_creator(self.options['author_name']),
                tag.dc_date(self.created.isoformat()),
                tag.meta_initial_creator(self.options['author_name']),
                tag.meta_creation_date(self.created.isoformat())
            ),
            office_version='1.1'
        )
        doc = unicode(tostring(doc))
        return doc.encode(self.encoding)

    def generate_mimetype(self):
        return 'application/vnd.oasis.opendocument.text'

    def generate_settings(self):
        tag = self.tag
        doc = tag.office_document_settings(
            tag.office_settings(),
            office_version='1.1'
        )
        doc = unicode(tostring(doc))
        return doc.encode(self.encoding)

    def generate_styles(self):
        tag = self.tag
        doc = tag.office_document_styles(
            tag.style_font_face_decls(
                tag.style_font_face(
                    style_font_family_generic=family,
                    svg_font_family='"%s"' % name,
                    style_font_pitch=pitch,
                    style_name=name
                )
                for (family, pitch, name) in (
                    ('roman',  'variable', 'Times New Roman'),
                    ('swiss',  'variable', 'Arial'),
                    ('system', 'variable', 'Arial'),
                )
            ),
            tag.office_master_styles(
                tag.style_master_page(style_name='Standard', style_page_layout_name='pm1')
            ),
            tag.office_automatic_styles(
                tag.style_style(
                    tag.style_text_properties(fo_font_weight='bold'),
                    style_name='bold',
                    style_family='text'
                ),
                tag.style_style(
                    tag.style_text_properties(fo_font_style='italic'),
                    style_name='italic',
                    style_family='text'
                ),
                tag.style_style(
                    tag.style_text_properties(
                        style_text_underline_color='font-color',
                        style_text_underline_style='solid',
                        style_text_underline_width='auto'
                    ),
                    style_name='underline',
                    style_family='text'
                ),
            ),
            tag.office_styles(
                tag.style_default_style(
                    tag.style_paragraph_properties(
                        style_link_break='strict',
                        style_punctuation_wrap='hanging',
                        style_tab_stop_distance='0.25in',
                        style_text_autospace='ideograph-alpha',
                        style_writing_mode='page',
                        fo_hyphenation_ladder_count='no-limit'
                    ),
                    tag.style_text_properties(
                        fo_language='en',
                        fo_country='US',
                        style_font_name='Times New Roman',
                        fo_font_size='12pt',
                        style_letter_kerning='true',
                        fo_hyphenate='false',
                        fo_hyphenation_push_char_count=2,
                        fo_hyphenation_remain_char_count=2,
                        style_use_window_font_color='true',
                        style_script_type='ignore'
                    ),
                    style_family='paragraph'
                ),
                tag.style_default_style(
                    tag.style_table_properties(style_border_model='collapsing'),
                    style_family='table'
                ),
                tag.style_default_style(
                    tag.style_table_row_properties(fo_keep_together='auto'),
                    style_family='table-row'
                ),
                tag.style_default_style(
                    tag.style_table_column_properties(style_use_optimal_column_width='true'),
                    style_family='table-column'
                ),
                tag.style_style(
                    style_name='standard',
                    style_display_name='Standard',
                    style_class='text',
                    style_family='paragraph'
                ),
                tag.style_style(
                    tag.style_paragraph_properties(fo_margin_bottom='0.1in', fo_margin_top='0in'),
                    style_name='text_body',
                    style_display_name='Body Text',
                    style_parent_style_name='standard',
                    style_class='text',
                    style_family='paragraph'
                ),
                tag.style_style(
                    tag.style_paragraph_properties(fo_margin_bottom='0.1in', fo_margin_top='0.2in', fo_keep_with_next='always'),
                    tag.style_text_properties(style_font_name='Arial', fo_font_size='14pt'),
                    style_name='heading',
                    style_parent_style_name='standard',
                    style_next_style_name='text_body',
                    style_class='text',
                    style_family='paragraph'
                ),
                tag.style_style(
                    tag.style_text_properties(fo_font_size='24pt', fo_font_weight='bold'),
                    style_name='doc_title',
                    style_display_name='Document Title',
                    style_parent_style_name='heading',
                    style_next_style_name='text_body',
                    style_class='text',
                    style_family='paragraph'
                ),
                tag.style_style(
                    tag.style_text_properties(fo_font_size='18pt', fo_font_weight='bold'),
                    style_name='heading_1',
                    style_display_name='Heading 1',
                    style_parent_style_name='heading',
                    style_next_style_name='text_body',
                    style_class='text',
                    style_family='paragraph',
                    style_default_outline_level=1
                ),
                tag.style_style(
                    tag.style_text_properties(fo_font_size='14pt', fo_font_weight='bold'),
                    style_name='heading_2',
                    style_display_name='Heading 2',
                    style_parent_style_name='heading',
                    style_next_style_name='text_body',
                    style_class='text',
                    style_family='paragraph',
                    style_default_outline_level=2
                ),
                tag.style_style(
                    tag.style_text_properties(fo_font_size='12pt', fo_font_weight='bold'),
                    style_name='heading_3',
                    style_display_name='Heading 3',
                    style_parent_style_name='heading',
                    style_next_style_name='text_body',
                    style_class='text',
                    style_family='paragraph',
                    style_default_outline_level=3
                ),
                tag.style_style(
                    style_name='list',
                    style_display_name='List',
                    style_parent_style_name='text_body',
                    style_class='list',
                    style_family='paragraph'
                ),
                tag.style_style(
                    tag.style_paragraph_properties(text_line_number=0, text_number_lines='false'),
                    style_name='table_contents',
                    style_display_name='Table Contents',
                    style_parent_style_name='standard',
                    style_class='extra',
                    style_family='paragraph'
                ),
                tag.style_style(
                    tag.style_section_properties(
                        tag.style_columns(fo_column_count=1, fo_column_gap='0in'),
                        tag.style_background_image(),
                        style_editable='false',
                        text_dont_balance_text_columns='false',
                        fo_background_color='transparent'
                    ),
                    style_name='section',
                    style_display_name='Section'
                )
            ),
            office_version='1.1'
        )
        doc = unicode(tostring(doc))
        return doc.encode(self.encoding)

    def generate_content(self):
        tag = self.tag
        doc = tag.office_document_content(
            tag.office_body(
                tag.office_text(
                    tag.text_h(self.options['title'], text_style_name='doc_title'),
                    tag.text_p(text_style_name='text_body'),
                    self.generate_database(self.database),
                    (self.generate_schema(schema) for schema in self.database.schema_list),
                    (self.generate_relation(relation) for schema in self.database.schema_list for relation in schema.relation_list),
                    (self.generate_trigger(trigger) for schema in self.database.schema_list for trigger in schema.trigger_list),
                    (self.generate_routine(routine) for schema in self.database.schema_list for routine in schema.routine_list),
                )
            ),
            office_version='1.1'
        )
        doc = unicode(tostring(doc))
        return doc.encode(self.encoding)

    def generate_index(self):
        return ''

    def generate_database(self, database):
        tag = self.tag
        return tag.text_section(
            tag.text_h('Database %s' % database.name, text_outline_level=1, text_style_name='heading_1'),
            self.format_comment(database.description),
            tag.text_h('Schemas', text_outline_level=2, text_style_name='heading_2'),
            tag.text_p('The following table contains all schemas (logical object containers) in the database.', text_style_name='text_body'),
            tag.table_table(
                tag.table_table_columns(
                    tag.table_table_column(),
                    tag.table_table_column()
                ),
                tag.table_table_header_rows(
                    tag.table_table_row(
                        tag.table_table_cell(tag.text_p('Name')),
                        tag.table_table_cell(tag.text_p('Description'))
                    )
                ),
                tag.table_table_rows(
                    tag.table_table_row(
                        tag.table_table_cell(tag.text_p(schema.name)),
                        tag.table_table_cell(self.format_comment(schema.description, summary=True))
                    )
                    for schema in database.schema_list
                ),
                table_name='schemas'
            ),
            text_name=database.identifier,
            text_style_name='section'
        )

    def generate_schema(self, schema):
        tag = self.tag
        return tag.text_section(
            tag.text_h('Schema %s' % schema.name, text_outline_level=1, text_style_name='heading_1'),
            self.format_comment(schema.description),
            text_name=schema.identifier,
            text_style_name='section'
        )

    def generate_relation(self, relation):
        return {
            Table: self.generate_table,
            View:  self.generate_view,
            Alias: self.generate_alias,
        }[type(relation)](relation)

    def generate_table(self, table):
        tag = self.tag
        return tag.text_section(
            tag.text_h('Table %s' % table.name, text_outline_level=1, text_style_name='heading_1'),
            self.format_comment(table.description),
            text_name=table.identifier,
            text_style_name='section'
        )

    def generate_view(self, view):
        tag = self.tag
        return tag.text_section(
            tag.text_h('View %s' % view.name, text_outline_level=1, text_style_name='heading_1'),
            self.format_comment(view.description),
            text_name=view.identifier,
            text_style_name='section'
        )

    def generate_alias(self, alias):
        tag = self.tag
        return tag.text_section(
            tag.text_h('Alias %s' % alias.name, text_outline_level=1, text_style_name='heading_1'),
            self.format_comment(alias.description),
            text_name=alias.identifier,
            text_style_name='section'
        )

    def generate_trigger(self, trigger):
        tag = self.tag
        return tag.text_section(
            tag.text_h('Trigger %s' % trigger.name, text_outline_level=1, text_style_name='heading_1'),
            self.format_comment(trigger.description),
            text_name=trigger.identifier,
            text_style_name='section'
        )

    def generate_routine(self, routine):
        return {
            Procedure: self.generate_procedure,
            Function:  self.generate_function,
        }[type(routine)](routine)

    def generate_procedure(self, procedure):
        tag = self.tag
        return tag.text_section(
            tag.text_h('Procedure %s' % procedure.name, text_outline_level=1, text_style_name='heading_1'),
            self.format_comment(procedure.description),
            text_name=procedure.identifier,
            text_style_name='section'
        )

    def generate_function(self, function):
        tag = self.tag
        return tag.text_section(
            tag.text_h('Function %s' % function.name, text_outline_level=1, text_style_name='heading_1'),
            self.format_comment(function.description),
            text_name=function.identifier,
            text_style_name='section'
        )
