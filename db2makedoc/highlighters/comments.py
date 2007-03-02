# $Header$
# vim: set noet sw=4 ts=4:

"""Implements a generic class for parsing simple prefix-based markup.

This module defines a base class for converting a simple prefix-based into some
other markup style, e.g. HTML. The class itself only performs recognition of
the markup and defines several handler methods which can be overridden in
descendents to perform the actual conversion. The syntax of the prefix-based
markup is as follows:

* A word surrounded by *asterisks* is strong (e.g. bold).
* A word surrounded by /slash/ is emphasized (e.g. italic).
* A word surrounded by _underscores_ is underlined.
* An identifier, possibly compound, prefixed by @ is a pointer to a database
  object (e.g. @SYSCAT.TABLES).
* A line break (\\n) indicates the end of a paragraph.

As the markup is intended for use in the comments attached to meta-data in the
database (which has extremely limited field sizes), it is designed to be
minimal and unobtrusive to the eye when read prior to conversion.
"""

import re
import logging
from db2makedoc.db.database import Database

class CommentHighlighter(object):

	find_ref = re.compile(r'@([A-Za-z_$#@][\w$#@]*(\.[A-Za-z_$#@][\w$#@]*){0,2})\b')
	find_fmt = re.compile(r'\B([/_*])(\w+)\1\B')

	def handle_text(self, text):
		"""Stub handler for plain text."""
		return text

	def handle_strong(self, text):
		"""Stub handler for strong/bold text."""
		return '*%s*' % text

	def handle_emphasize(self, text):
		"""Stub handler for emphasized/italic text."""
		return '/%s/' % text

	def handle_underline(self, text):
		"""Stub handler for underlined text."""
		return '_%s_' % text

	def handle_link(self, target):
		"""Stub handler for link references."""
		return '@%s' % target.qualified_name

	def start_para(self, summary):
		"""Stub handler for paragraph starts."""
		return ''

	def end_para(self, summary):
		"""Stub handler for paragraph ends."""
		if not summary:
			return '\n\n'
		else:
			return ''
	
	def find_target(self, name):
		"""Stub handler to find a database object given its name."""
		return None
	
	def parse(self, text, summary=False):
		"""Converts the provided text into another markup language.

		The summary parameter, if True, indicates that only the first line of
		the text should be marked up and returned. Note that this base routine
		returns a list of strings (or whatever the handler methods return) as
		opposed to a single string in case overridden descendents wish to
		perform further post-processing on the converted elements.
		"""
		paras = text.split('\n')
		if summary:
			paras = [paras[0]]
		result = []
		for para in paras:
			if len(para) == 0:
				continue
			result.append(self.start_para(summary))
			start = 0
			while True:
				match_ref = self.find_ref.search(para, start)
				match_fmt = self.find_fmt.search(para, start)
				if match_ref is not None and (match_fmt is None or match_fmt.start(0) > match_ref.start(0)):
					result.append(self.handle_text(para[start:match_ref.start(0)]))
					start = match_ref.end(0)
					target = self.find_target(match_ref.group(1))
					if target is None:
						logging.warning('Failed to find database object %s referenced in comment: "%s"' % (match_ref.group(1), text))
						result.append(self.handle_text(match_ref.group(0)))
					else:
						result.append(self.handle_link(target))
				elif match_fmt is not None and (match_ref is None or match_fmt.start(0) < match_ref.start(0)):
					result.append(self.handle_text(para[start:match_fmt.start(0)]))
					start = match_fmt.end(0)
					if match_fmt.group(1) == '*':
						result.append(self.handle_strong(match_fmt.group(2)))
					elif match_fmt.group(1) == '/':
						result.append(self.handle_emphasize(match_fmt.group(2)))
					elif match_fmt.group(1) == '_':
						result.append(self.handle_underline(match_fmt.group(2)))
					else:
						assert False
				else:
					result.append(self.handle_text(para[start:]))
					break
			result.append(self.end_para(summary))
		return result

	def parse_to_string(self, text, summary=False):
		return ''.join(self.parse(text, summary))
