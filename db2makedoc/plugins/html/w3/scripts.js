// IE doesn't have a clue (no Node built-in) so we'll define one just for it...
var ELEMENT_NODE = 1;

// Replace the "More items..." link (e) with the items it's hiding
function showItems(e) {
	var n;
	n = e;
	while (n = n.previousSibling)
		if ((n.nodeType == ELEMENT_NODE) && (n.tagName.toLowerCase() == 'a'))
			if (n.style.display == 'none')
				n.style.display = 'block'
			else
				break;
	n = e;
	while (n = n.nextSibling)
		if ((n.nodeType == ELEMENT_NODE) && (n.tagName.toLowerCase() == 'a'))
			if (n.style.display == 'none')
				n.style.display = 'block'
			else
				break;
	e.style.display = 'none';
	return false;
}

var W3_SEARCH = 'http://w3.ibm.com/search/do/search';
var DOC_SEARCH = 'search.php';

// Toggles the target of the masthead search box
function toggleSearch() {
	var searchForm = document.getElementById("search");
	var searchField = document.getElementById("header-search-field");
	if (searchForm.action == W3_SEARCH) {
		searchForm.action = DOC_SEARCH;
		searchField.name = "q";
	}
	else {
		searchForm.action = W3_SEARCH;
		searchField.name = "qt";
	}
}

// Adds a handler to an event
function addEvent(obj, evt, fn) {
	if (obj.addEventListener)
		obj.addEventListener(evt, fn, false);
	else if (obj.attachEvent)
		obj.attachEvent('on' + evt, fn);
}

// Removes a handler from an event
function removeEvent(obj, evt, fn) {
	if (obj.removeEventListener)
		obj.removeEventListener(evt, fn, false);
	else if (obj.detachEvent)
		obj.detachEvent('on' + evt, fn);
}

// Simple class for storing 2D position. Either specify the X and Y coordinates
// to the constructor, or specify an element (or an element ID), or another
// Position object as the only parameter in which case the element's offset
// will be used
function Position(x, y) {
	if (x === undefined) {
		throw Error('must specify two coordinates or an object for Position');
	}
	else if (y === undefined) {
		var obj = x;
		if (typeof obj == 'string')
			obj = document.getElementById(obj);
		if (typeof obj == 'object') {
			if ((typeof obj.x == 'number') && (typeof obj.y == 'number')) {
				this.x = obj.x;
				this.y = obj.y;
			}
			else {
				this.x = this.y = 0;
				do {
					this.x += obj.offsetLeft;
					this.y += obj.offsetTop
				} while (obj = obj.offsetParent);
			}
		}
		else {
			throw Error('invalid object type for Position');
		}
	}
	else {
		this.x = x;
		this.y = y;
	}
}

// Global zoom object. Implements properties and methods used to control
// draggable zoom boxes over a reduced size image. This code is a modified
// version of PPK's excellent "Drag and drop" script. The original can be
// found at: http://www.quirksmode.org/js/dragdrop.html
zoom = {
	// Configuration variables
	keySpeed: 10, // pixels per keypress event
	defaultTitle: 'Zoom', // title bar of normal zoom box
	mouseTitle: undefined, // title bar of zoom box during mouse drag
	keyTitle: 'Keys: \\u2191\\u2193\\u2190\\u2192 \\u21B5', // title bar of zoom box during keypress drag
	keyLink: 'Keys', // title of the key link

	// Internal variables - do not alter
	startMouse: undefined,
	startElem: undefined,
	min: undefined,
	max: undefined,
	ratioX: undefined,
	ratioY: undefined,
	dXKeys: undefined,
	dYKeys: undefined,
	box: undefined,

	toggle: function (thumb, src, map) {
		if (typeof thumb == 'string')
			thumb = document.getElementById(thumb);
		if (thumb._zoom)
			zoom.done(thumb)
		else
			zoom.init(thumb, src, map);
		return false;
	},

	init: function (thumb, src, map) {
		if (typeof thumb == 'string')
			thumb = document.getElementById(thumb);
		// Create the zoom box
		var box = document.createElement('div');
		var image = document.createElement('img');
		var link = document.createElement('a');
		var title = document.createElement('div');
		image._box = box;
		image.src = src;
		if (map) image.useMap = map;
		link._box = box;
		link.appendChild(document.createTextNode(zoom.keyLink));
		link.href = '#';
		title._box = box;
		title.appendChild(document.createTextNode(zoom.defaultTitle));
		box._thumb = thumb;
		box._title = title;
		box._link = link;
		box._image = image;
		box.className = 'zoom';
		var startPos = new Position(thumb);
		box.style.left = startPos.x + 'px';
		box.style.top = startPos.y + 'px';
		// Place the elements into the document tree
		box.appendChild(title);
		box.appendChild(link);
		box.appendChild(image);
		document.body.appendChild(box);
		thumb._zoom = box;
		// Attach the drag event handlers
		link.onclick = zoom.startDragKeys;
		title.onmousedown = zoom.startDragMouse;
		// Return the top-level <div> in case the caller wants to customize
		// the content
		return box;
	},

	done: function(thumb) {
		if (zoom.box) zoom.endDrag();
		if (typeof thumb == 'string')
			thumb = document.getElementById(thumb);
		// Break all the reference cycles we've setup just in case the JS
		// implementation has shite gc
		var box = thumb._zoom;
		box._image._box = undefined;
		box._image = undefined;
		box._link._box = undefined;
		box._link = undefined;
		box._title = undefined;
		box._thumb = undefined;
		thumb._zoom = undefined;
		// Remove the generated box
		document.body.removeChild(box);
		return false;
	},

	startDragMouse: function (e) {
		if (zoom.mouseTitle !== undefined)
			this._box._title.lastChild.data = zoom.mouseTitle;
		zoom.startDrag(this._box);
		if (!e) var e = window.event;
		zoom.startMouse = new Position(e.clientX, e.clientY);
		addEvent(document, 'mousemove', zoom.dragMouse);
		addEvent(document, 'mouseup', zoom.endDrag);
		return false;
	},

	startDragKeys: function () {
		if (zoom.keyTitle !== undefined)
			this._box._title.lastChild.data = zoom.keyTitle;
		this._box._link.style.display = 'none';
		zoom.startDrag(this._box);
		zoom.dXKeys = zoom.dYKeys = 0;
		addEvent(document, 'keydown', zoom.dragKeys);
		addEvent(document, 'keypress', zoom.switchKeyEvents);
		this.blur();
		return false;
	},

	switchKeyEvents: function () {
		// for Opera and Safari 1.3
		removeEvent(document, 'keydown', zoom.dragKeys);
		removeEvent(document, 'keypress', zoom.switchKeyEvents);
		addEvent(document, 'keypress', zoom.dragKeys);
	},

	startDrag: function (obj) {
		if (zoom.box) zoom.endDrag();
		var thumbW = obj._thumb.offsetWidth - obj.offsetWidth;
		var thumbH = obj._thumb.offsetHeight - obj.offsetHeight;
		var imageW = obj._image.offsetWidth - obj.offsetWidth;
		var imageH = obj._image.offsetHeight - obj.offsetHeight;
		zoom.startElem = new Position(obj);
		zoom.min = new Position(obj._thumb);
		zoom.max = new Position(zoom.min);
		zoom.max.x += thumbW;
		zoom.max.y += thumbH;
		zoom.ratioX = imageW / thumbW;
		zoom.ratioY = imageH / thumbH;
		zoom.box = obj;
		obj.className += ' dragged';
	},

	endDrag: function() {
		removeEvent(document, 'mousemove', zoom.dragMouse);
		removeEvent(document, 'mouseup', zoom.endDrag);
		removeEvent(document, 'keypress', zoom.dragKeys);
		removeEvent(document, 'keypress', zoom.switchKeyEvents);
		removeEvent(document, 'keydown', zoom.dragKeys);
		zoom.box.className = zoom.box.className.replace(/ *dragged/, '');
		zoom.box._link.style.display = 'block';
		zoom.box._title.lastChild.data = zoom.defaultTitle;
		zoom.saveTitle = undefined;
		zoom.startMouse = undefined;
		zoom.startElem = undefined;
		zoom.min = undefined;
		zoom.max = undefined;
		zoom.ratioX = undefined;
		zoom.ratioY = undefined;
		zoom.box = undefined;
	},

	dragMouse: function (e) {
		if (!e) var e = window.event;
		var dX = e.clientX - zoom.startMouse.x;
		var dY = e.clientY - zoom.startMouse.y;
		zoom.setPosition(dX, dY);
		return false;
	},

	dragKeys: function(e) {
		if (!e) var e = window.event;
		switch (e.keyCode) {
			case 37:	// left
			case 63234:
				if (zoom.startElem.x + zoom.dXKeys > zoom.min.x)
					zoom.dXKeys -= zoom.keySpeed;
				break;
			case 38:	// up
			case 63232:
				if (zoom.startElem.y + zoom.dYKeys > zoom.min.y)
					zoom.dYKeys -= zoom.keySpeed;
				break;
			case 39:	// right
			case 63235:
				if (zoom.startElem.x + zoom.dXKeys < zoom.max.x)
					zoom.dXKeys += zoom.keySpeed;
				break;
			case 40:	// down
			case 63233:
				if (zoom.startElem.y + zoom.dYKeys < zoom.max.y)
					zoom.dYKeys += zoom.keySpeed;
				break;
			case 13:	// enter
			case 27:	// escape
				zoom.endDrag();
				return false;
			default:
				return true;
		}
		zoom.setPosition(zoom.dXKeys, zoom.dYKeys);
		if (e.preventDefault) e.preventDefault();
		return false;
	},

	setPosition: function (dx, dy) {
		var newBoxPos = new Position(
			Math.min(Math.max(zoom.startElem.x + dx, zoom.min.x), zoom.max.x),
			Math.min(Math.max(zoom.startElem.y + dy, zoom.min.y), zoom.max.y)
		);
		var newImagePos = new Position(
			(newBoxPos.x - zoom.min.x) * zoom.ratioX,
			(newBoxPos.y - zoom.min.y) * zoom.ratioY
		);
		zoom.box.style.left = newBoxPos.x + 'px';
		zoom.box.style.top = newBoxPos.y + 'px';
		zoom.box._image.style.left = -newImagePos.x + 'px';
		zoom.box._image.style.top = -newImagePos.y + 'px';
	}
}
