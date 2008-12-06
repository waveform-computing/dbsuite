/* Utility routine for toggling the URL of the search form at the top of all w3
 * style articles */

var W3_SEARCH = 'http://w3.ibm.com/search/do/search';
var DOC_SEARCH = 'search.php';
$(document).ready(function() {
	$('#search').attr('action', W3_SEARCH);
	$('#header-search-field').attr('name', 'qt');
	$('#header-search-this')
		.removeAttr('checked')
		.click(function() {
			var w3 = $('#search').attr('action') == W3_SEARCH;
			$('#search').attr('action', w3 ? DOC_SEARCH : W3_SEARCH);
			$('#header-search-field').attr('name', w3 ? 'q' : 'qt');
		});
	$('.limiter').children().show();
});

/* Utility routines for using AJAX to add menu items to the left navigation
 * menu after clicking on a "More Items" link */

function addLink(target, div, above) {
	var link = $(document.createElement('a'))
		.attr('href', target.attr('href'))
		.attr('title', target.attr('title'))
		.text(target.attr('label'));
	if (above)
		link.prependTo(div);
	else
		link.appendTo(div);
	return link;
}

var extendBy = 10;
var navDoc = undefined;
function addLinks(node, above) {
	// Find the links in the XML site-map that we wish to add to the tree
	node = $(node);
	var href = (above ? node.next() : node.prev()).attr('href');
	var target = $('[href=' + href + ']', navDoc);
	var links = above ? target.prevAll() : target.nextAll();
	// Limit the number of links we wish to add at once
	if (links.length < extendBy + (extendBy / 2))
		node.slideToggle().hide();
	else
		links = links.slice(0, extendBy);
	// Create a temporary hidden div, add the links to this and insert it
	// before or after the "More Items" node
	var div = $(document.createElement('div')).hide();
	links.each(function() {
		addLink($(this), div, above);
	});
	if (above)
		div.insertAfter(node);
	else
		div.insertBefore(node);
	// Now show the temporary owning div (for one smooth animation), then once
	// the animation is finished, move the contained links out of the div and
	// delete it
	div.slideDown('normal', function() {
		$(this).children().each(function() {
			$(this).insertBefore(div);
		});
		$(this).remove();
	});
}

$(document).ready(function() {
	$('.more-items').click(function() {
		var node = this;
		above = $(this).is(':first-child');
		if (navDoc) {
			addLinks(node, above);
		}
		else {
			$.get('nav.xml', function(data) {
				navDoc = data;
				addLinks(node, above);
			});
		}
		return false;
	});
});

/* Code to customize the appearance of site index documents (slide toggling for
 * top-level definition lists, and Expand All & Collapse All links in the
 * header */

$(document).ready(function() {
	/* Collapse all definition terms and add a click handler to toggle them */
	$('#index-list')
		.children('dd').hide().end()
		.children('dt').addClass('expand-link-dark').click(function() {
			$(this)
				.toggleClass('expand-link-dark')
				.toggleClass('collapse-link-dark')
				.next().slideToggle();
		});
	/* Add the "expand all" and "collapse all" links */
	$('#expand-collapse-links')
		.append(
			$(document.createElement('a'))
				.attr('href', '#')
				.append('Expand all')
				.click(function() {
					$('#index-list')
						.children('dd').show().end()
						.children('dt').removeClass('expand-link-dark').addClass('collapse-link-dark');
					return false;
				})
		)
		.append(' ')
		.append(
			$(document.createElement('a'))
				.attr('href', '#')
				.append('Collapse all')
				.click(function() {
					$('#index-list')
						.children('dd').hide().end()
						.children('dt').removeClass('collapse-link-dark').addClass('expand-link-dark');
					return false;
				})
		);
});
