/* Add a custom parser to the tablesorter plugin to handle sorting numerics
 * with comma thousand separators */

$.tablesorter.addParser({
	id: "digitComma",
	is: function(s, table) {
		var c = table.config;
		return $.tablesorter.isDigit(s.replace(/,/, ''), c);
	},
	format: function(s) {
		return $.tablesorter.formatFloat(s.replace(/,/, ''));
	},
	type: "numeric"
});

