# $Header$
# vim: set noet sw=4 ts=4:

"""Defines the base class for output plugins.

This module defines the base class for output plugins. Output plugins are
expected to generate documentation (in whatever specific format they target)
from the hierarchy of database objects provided to them by the main
application.
"""

import sys
import logging

class OutputPlugin(object):
	"""Base class for output plugins.

	Developers of output plugins should subclass this class (or one of the
	classes in the plugins package) to create their plugins. The new class
	should include a new docstring which will become the description of the
	plugin. It should also override all public methods below (except the few
	cases where the docstring states that the method should NOT be overridden).
	"""

	def __init__(self):
		"""Initializes an instance of the class.

		Plugins derived from this class are expected to set up the options
		that the plugin can accept by calling the add_option() method during
		construction. This allows the main application to present the user with
		a list of possible configuration options when requested.

		Other than setting up the options, the derived constructor is expected
		to do nothing else (other than call the inherited constructor of
		course).

		"""
		super(OutputPlugin, self).__init__()
		self.options = {}

	def add_option(self, name, default=None, doc=None):
		"""Adds a new option to the configuration directory.

		Derived classes should NOT override this method.

		Derived classes are expected to call this method during construction to
		define the configuraiton options expect to receive. Currently, this is
		a very basic mechanism. In future it may be expanded to include some
		rudimentary type checking and validation (currently derived classes
		must perform any validation themselves during the execute() call).

		As such future expansions may result in an extended prototype for this
		function it is strongly recommended that keyword arguments are used
		when calling it.
		"""
		self.options[name] = (default, doc)
	
	def configure(self, config):
		"""Loads the plugin configuration.

		Derived classes should NOT attempt to override this method.

		This method is calling by the main application to load configuration
		information from the file specified by the user.
		"""
		for (name, (default, doc)) in self.options:
			if name in config:
				self.options[name] = config[name]
			else:
				self.options[name] = default
	
	def execute(self, database):
		"""Invokes the plugin to produce documentation.

		This method is called by the main application with the database for
		which the plugin should produce documentation. Derived classes must
		override this method to implement this action, using the configuration
		supplied in the self.options dictionary (which by this point will
		simply map names to values with any documentation stripped out).
		"""
		pass
