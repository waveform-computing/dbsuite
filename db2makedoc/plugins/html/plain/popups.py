# vim: set noet sw=4 ts=4:

import os
import codecs
from db2makedoc.etree import fromstring
from db2makedoc.plugins.html.plain.document import PlainDocument


class PlainPopupDocument(PlainDocument):
	"""Document class representing a popup help window."""

	def __init__(self, site, url, title, body, width=400, height=300):
		"""Initializes an instance of the class."""
		super(PlainPopupDocument, self).__init__(site, url)
		self.title = title
		self.body = body
		self.width = int(width)
		self.height = int(height)
	
	def generate(self):
		tag = self.tag
		doc = super(PlainPopupDocument, self).generate()
		bodynode = tag._find(doc, 'body')
		del bodynode[:] # Clear any existing body content
		bodynode.append(tag.div(
			tag.h2(self.title),
			self.body,
			tag.div(
				tag.hr(),
				tag.div(
					tag.a('Close Window', href='javascript:close();'),
					tag.a('Print', href='javascript:window.print();'),
					class_='content'
				),
				id='footer'
			)
		))
		return doc

	def link(self):
		# Modify the link to use Thickbox
		return self.tag.a(self.title, class_='thickbox', title=self.title,
			href='%s?TB_iframe=true&width=%d&height=%d' % (self.url, self.width, self.height))


# Declare a routine which, given a site object, will create popups for all
# popups defined in popups.xml which lives in the module's path

def create_popups(site):
	mod_path = os.path.dirname(os.path.abspath(__file__))
	source = os.path.join(mod_path, 'popups.xml')
	popups = fromstring(codecs.open(source, 'r', 'utf-8').read())
	for popup in popups:
		PlainPopupDocument(site,
			url=popup.attrib['filename'],
			title=popup.attrib['title'],
			width=popup.attrib.get('width', '400'),
			height=popup.attrib.get('height', '300'),
			body=list(popup)
		)
