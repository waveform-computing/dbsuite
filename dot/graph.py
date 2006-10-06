# $Header$
# vim: set noet sw=4 ts=4:

"""Implements basic classes for generating graphs in the DOT language.

This unit implements a set of simple classes which provide facilities for
creating and performing basic manipulations of graphs in the GraphViz DOT
language. No facilities for parsing existing DOT language files are provided,
only for creating DOT files and image files by passing the DOT output through
GraphViz.

"""

# Standard modules
import sys
mswindows = sys.platform == "win32"
import os
import re
from string import Template
from subprocess import Popen, PIPE, STDOUT
try:
	from cStringIO import StringIO
except ImportError:
	from StringIO import StringIO

# XXX Add some code to check for duplicate graph/node/edge IDs

class GraphObject(object):
	"""Base class for all objects in the module.

	The GraphObject class separates all graphing attributes (shape, style,
	label, etc.) into a separate dictionary of values, which only contains
	entries for those attributes which have been explicitly assigned a new
	value. This helps makes the in memory representation of a graph a bit more
	minimal, and makes extracting the attributes for writing much easier &
	quicker.

	It also provides utility methods for determining when and how to quote
	identifiers in the dot language, for obtaining a formatted list of
	attributes and their values, and for some basic methods for navigating the
	hierarchy of objects.
	"""
	_attributes = frozenset()

	def __init__(self):
		self._attr_values = {}
		super(GraphObject, self).__init__()

	def __getattr__(self, name):
		try:
			return self._attr_values[name]
		except KeyError:
			if name in self._attributes:
				return None
			else:
				raise AttributeError("'%s' object has no attribute '%s'" % (self.__class__.__name__, name))

	def __setattr__(self, name, value):
		if name in self._attributes:
			self.__dict__['_attr_values'][name] = value
		else:
			object.__setattr__(self, name, value)

	dot_alpha_ident = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')
	dot_num_ident = re.compile(r'^-?(\.[0-9]+|[0-9]+(\.[0-9]*)?)$')
	def _quote(self, s):
		"""Internal utility method for quoting identifiers if they need to be"""
		if s == '' or self.dot_alpha_ident.match(s) or self.dot_num_ident.match(s):
			return s
		else:
			s = s.replace('"', '\\"')
			s = s.replace('\n', '\\n')
			s = s.replace('\r', '\\r')
			s = s.replace('\t', '\\t')
			return '"%s"' % s
	
	def _attr_values_str(self):
		"""Internal utility method that returns _attr_values as a formatted string"""
		return ', '.join([
			'%s=%s' % (self._quote(n), self._quote(str(v)))
			for (n, v) in self._attr_values.iteritems()
		])
	
	def _get_graph(self):
		"""Returns the top-level graph that owns the object"""
		o = self
		while o is not None and not isinstance(o, Graph):
			o = o.parent
		if o:
			return o
		else:
			raise Exception('Unable to find top-level Graph object')

	def _get_dot(self):
		"""Returns a string containing the dot-language representation of the object"""
		# Stub to be overridden by child classes
		pass

	graph = property(_get_graph)
	dot = property(lambda self: self._get_dot())

class GraphBase(GraphObject):
	def __init__(self, id):
		super(GraphBase, self).__init__()
		self.children = []
		self.parent = None
		self.id = id

class Graph(GraphBase):
	_attributes = frozenset(('Damping', 'K', 'URL', 'bb', 'bgcolor', 'center',
			'charset', 'clusterrank', 'colorscheme', 'comment', 'compound',
			'concentrate', 'defaultdist', 'dim', 'diredgeconstraints', 'dpi',
			'epsilon', 'esep', 'fontcolor', 'fontname', 'fontpath', 'fontsize',
			'label', 'labeljust', 'labelloc', 'landscape', 'layers',
			'layersep', 'levelsgap', 'lp', 'margin', 'maxiter', 'mclimit',
			'mindist', 'mode', 'model', 'mosek', 'nodesep', 'normalize',
			'nslimit1', 'ordering', 'orientation', 'outputorder', 'overlap',
			'pack', 'packmode', 'page', 'pagedir', 'quantum', 'rankdir',
			'ranksep', 'ratio', 'remincross', 'resolution', 'root', 'rotate',
			'searchsize', 'sep', 'showboxes', 'size', 'splines', 'start',
			'stylesheet', 'target', 'truecolor', 'viewport', 'voro_margin'))

	def __init__(self, id, directed=True, strict=False):
		super(Graph, self).__init__(id)
		self.directed = directed
		self.strict = strict

	def _get_dot(self):
		t = Template("""\
$strict$graph $id {
	graph [$attributes];
	$children
}""")
		return t.safe_substitute({
			'strict': ['', 'strict '][self.strict],
			'graph': ['graph', 'digraph'][self.directed],
			'id': self._quote(str(self.id)),
			'attributes': self._attr_values_str(),
			'children': '\n\t'.join([c.dot + ';' for c in self.children]),
		})
	
	def _call_graphviz(self, output, converter, format, graph_attr, node_attr, edge_attr):
		"""Internal utility method use by the various to_X conversion methods."""
		cmd_line = [converter, '-T%s' % format]
		cmd_line.extend(['-G%s=%s' % (n, v) for (n, v) in graph_attr.iteritems()])
		cmd_line.extend(['-N%s=%s' % (n, v) for (n, v) in node_attr.iteritems()])
		cmd_line.extend(['-E%s=%s' % (n, v) for (n, v) in edge_attr.iteritems()])
		p = Popen(cmd_line, stdin=PIPE, stdout=PIPE, close_fds=not mswindows)
		try:
			output.write(p.communicate(self.dot)[0])
		finally:
			p.wait()

	svg_fix = re.compile(r'(style=".*font-size:\s*[0-9]*(\.[0-9]+)?)(\s*;.*")')
	def to_svg(self, output, converter='dot', graph_attr={}, node_attr={}, edge_attr={}):
		"""Converts the Graph into an SVG image.

		Parameters:
		output -- A file-like object to write the SVG to
		converter -- The path and name of the GraphViz application to use
		graph_attr -- A dictionary of graph attributes to pass on the command line
		node_attr -- A dictionary of node attributes to pass on the command line
		edge_attr -- A dictionary of edge attributes to pass on the command line
		"""
		s = StringIO()
		self._call_graphviz(s, converter, 'svg', graph_attr, node_attr, edge_attr)
		# The regex substitution below is to fix a bug in GraphViz's SVG
		# output; the font-size style element needs a unit, usually px, to
		# work correctly in Firefox, Opera, etc.
		output.write(self.svg_fix.sub(r'\1px\3', s.getvalue()))
	
	def to_ps(self, output, converter='dot', graph_attr={}, node_attr={}, edge_attr={}):
		"""Converts the Graph into a PostScript document.

		Parameters are identical to the to_svg() method above.
		"""
		self._call_graphviz(output, converter, 'ps2', graph_attr, node_attr, edge_attr)
	
	def to_png(self, output_img, output_map=None, converter='dot', graph_attr={}, node_attr={}, edge_attr={}):
		"""Converts the Graph into a PNG image (and optionally a client-side image-map).

		Parameters:
		output_img -- A file-like object to write the PNG to
		output_map -- An optional file-like object to write the image-map to
		converter -- The path and name of the GraphViz application to use
		graph_attr -- A dictionary of graph attributes to pass on the command line
		node_attr -- A dictionary of node attributes to pass on the command line
		edge_attr -- A dictionary of edge attributes to pass on the command line
		"""
		# It'd be nice to let GraphViz generate both formats at once with two
		# -T arguments but when dealing with file-like objects (instead of
		# filenames) that's just not possible to do reliably. If we insisted on
		# filenames instead of file-like objects we're then into the tricky
		# territory of creating temporary files and the caller doesn't have the
		# option of passing a StringIO object. Oh well.
		self._call_graphviz(output_img, converter, 'png', graph_attr, node_attr, edge_attr)
		if output_map is not None:
			self._call_graphviz(output_map, converter, 'cmapx', graph_attr, node_attr, edge_attr)
	
	def to_gif(self, output_img, output_map=None, converter='dot', graph_attr={}, node_attr={}, edge_attr={}):
		"""Converts the Graph into a GIF image (and optionally a client-side image-map).

		Parameters are identical to the to_png() method above.
		"""
		self._call_graphviz(output_img, converter, 'gif', graph_attr, node_attr, edge_attr)
		if output_map is not None:
			self._call_graphviz(output_map, converter, 'cmapx', graph_attr, node_attr, edge_attr)

class Subgraph(GraphBase):
	_attributes = frozenset(('rank'))

	def __init__(self, graph, id):
		super(Subgraph, self).__init__(id)
		assert isinstance(graph, GraphBase)
		self.parent = graph
		graph.children.append(self)

	def _get_dot(self):
		t = Template("""\
subgraph $id {
	graph [$attributes];
	$children
}""")
		return t.safe_substitute({
			'id': self._quote(str(self.id)),
			'attributes': self._attr_values_str(),
			'children': '\n\t'.join([c.dot + ';' for c in self.children]),
		})

class Cluster(Subgraph):
	_attributes = frozenset(('K', 'URL', 'bgcolor', 'color', 'colorscheme',
			'fillcolor', 'fontcolor', 'fontname', 'fontsize', 'label',
			'labeljust', 'labelloc', 'lp', 'nojustify', 'pencolor',
			'peripheries', 'style', 'target', 'tooltip'))

	def __init__(self, graph, id):
		super(Cluster, self).__init__(graph, id)
		# XXX Hmm ... need to ensure id is provided and is unique with cluster_ prefix
	
	def _get_dot(self):
		# A cluster is just a specially named subgraph, so we just rewrite the
		# id temporarily and call the inherited method
		save_id = self.id
		self.id = 'cluster_%s' % self.id
		result = super(Cluster, self)._get_dot()
		self.id = save_id
		return result

class Node(GraphObject):
	_attributes = frozenset(('URL', 'color', 'comment', 'distortion',
			'fillcolor', 'fixedsize', 'fontcolor', 'fontname', 'fontsize',
			'group', 'height', 'label', 'layer', 'margin', 'nojustify',
			'orientation', 'peripheries', 'pin', 'pos', 'rects', 'regular',
			'root', 'samplepoints', 'shape', 'shapefile', 'showboxes', 'sides',
			'skew', 'style', 'target', 'tooltip', 'vertices', 'width', 'z'))

	def __init__(self, graph, id):
		super(Node, self).__init__()
		assert isinstance(graph, GraphBase)
		self.parent = graph
		self.id = id
		graph.children.append(self)
	
	def _get_dot(self):
		return '%s [%s]' % (
			self._quote(str(self.id)),
			self._attr_values_str()
		)

	def connect_to(self, node):
		"""Connects this node to the specified node.

		The connect_to() method creates an Edge object (which it returns) which
		connects the object the method is called on to the node specified in
		the single parameter. If this node is already connected to the
		specified node, the existing connection will be returned instead of
		creating a new one.
		"""
		assert isinstance(node, Node)
		assert self.graph == node.graph
		return self.is_connected_to(node) or Edge(self.graph, self, node)

	def disconnect_from(self, node):
		"""Removes all connections between this node and the specified node.

		The disconnect_from() method searches for all Edge objects connecting
		from the node on which the method is called to the node specified in
		the parameter, and destroys them.  Note that if the graph is directed,
		this will NOT remove connections from the node specified in the
		parameter to the node on which the method is called.
		"""

		def disconnect_sub(subgraph, directed):
			# Recursively search for Edge objects connecting the nodes and
			# destroy them
			assert isinstance(subgraph, GraphBase)
			unlink = []
			for i in subgraph.children:
				if isinstance(i, Edge):
					if i.from_node == self and i.to_node == node:
						unlink.append(i)
					elif not directed and i.to_node == self and i.from_node == node:
						unlink.append(i)
				elif isinstance(i, GraphBase):
					disconnect_sub(i)
			for i in unlink:
				subgraph.children.remove(i)

		assert isinstance(node, Node)
		assert self.graph == node.graph
		disconnect_sub(self.graph, self.graph.directed)
	
	def is_connected_to(self, node):
		"""Determines if this node is connected to the specified node.

		The is_connected_to() method recursively searches the graph for Edge
		objects connecting the from the node on which the method is called to
		the node specified in the parameter. If such an Edge is found it is
		returned. If no such Edge is found, None is returned.
		
		If the graph is undirected, the method also searches for reverse
		connections (from the specified node to this node).
		"""

		def is_connected_sub(subgraph, directed):
			# Recursively search for Edge objects connecting the nodes
			assert isinstance(subgraph, GraphBase)
			for i in subgraph.children:
				if isinstance(i, Edge):
					if i.from_node == self and i.to_node == node:
						return i
					elif not directed and i.to_node == self and i.from_node == node:
						return i
				elif isinstance(i, GraphBase):
					return is_connected_sub(i)
			return None

		assert isinstance(node, Node)
		assert self.graph == node.graph
		return is_connected_sub(self.graph, self.graph.directed)

class Edge(GraphObject):
	_attributes = frozenset(('URL', 'arrowhead', 'arrowsize', 'arrowtail',
			'color', 'comment', 'constraint', 'decorate', 'dir', 'fontcolor',
			'fontname', 'fontsize', 'headURL', 'headclip', 'headhref',
			'headlabel', 'headport', 'headtarget', 'headtooltip', 'href',
			'label', 'labelangle', 'labeldistance', 'labelfloat',
			'labelfontcolor', 'labelfontname', 'labelfontsize', 'layer', 'len',
			'lhead', 'lp', 'ltail', 'minlen', 'nojustify', 'pos', 'samehead',
			'sametail', 'showboxes', 'style', 'tailURL', 'tailclip',
			'tailhref', 'taillabel', 'tailport', 'tailtarget', 'tailtooltip',
			'target', 'tooltip', 'weight'))

	def __init__(self, graph, from_node, to_node):
		super(Edge, self).__init__()
		assert isinstance(graph, GraphBase)
		assert isinstance(from_node, Node)
		assert isinstance(to_node, Node)
		self.parent = graph
		self.from_node = from_node
		self.to_node = to_node
		graph.children.append(self)

	def _get_dot(self):
		return '%s %s %s [%s]' % (
			self._quote(str(self.from_node.id)),
			['--', '->'][self.graph.directed],
			self._quote(str(self.to_node.id)),
			self._attr_values_str(),
		)
