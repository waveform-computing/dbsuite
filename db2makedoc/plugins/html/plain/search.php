require '__XAPIAN__';

# Defaults and limits
$PAGE_DEFAULT = 1;
$PAGE_MIN = 1;
$PAGE_MAX = 0; # Calculated by run_query()
$COUNT_DEFAULT = 20;
$COUNT_MIN = 10;
$COUNT_MAX = 100;

# Globals derived from GET values
$Q = array_key_exists('q', $_GET) ? strval($_GET['q']) : '';
$PAGE = array_key_exists('page', $_GET) ? intval($_GET['page']) : $PAGE_DEFAULT;
$PAGE = max($PAGE_MIN, $PAGE);
$COUNT = array_key_exists('count', $_GET) ? intval($_GET['count']) : $COUNT_DEFAULT;
$COUNT = max($COUNT_MIN, min($COUNT_MAX, $COUNT));

function run_query() {
	global $Q, $PAGE, $COUNT, $PAGE_MAX;

	$db = new XapianDatabase('search');
	$enquire = new XapianEnquire($db);
	$parser = new XapianQueryParser();
	$parser->set_stemmer(new XapianStem('__LANG__'));
	$parser->set_stemming_strategy(XapianQueryParser::STEM_SOME);
	$parser->set_database($db);
	$query = $parser->parse_query($Q,
		XapianQueryParser::FLAG_BOOLEAN_ANY_CASE |  # Enable boolean operators (with any case)
		XapianQueryParser::FLAG_PHRASE |            # Enable quoted phrases 
		XapianQueryParser::FLAG_LOVEHATE |          # Enable + and -
		XapianQueryParser::FLAG_SPELLING_CORRECTION # Enable suggested corrections
	);
	$enquire->set_query($query);
	$result = $enquire->get_mset((($PAGE - 1) * $COUNT) + 1, $COUNT);
	$PAGE_MAX = ceil($result->get_matches_estimated() / floatval($COUNT));
	return $result;
}

function result_header($doc, $matches) {
	global $Q, $PAGE, $COUNT;

	$page_from = (($PAGE - 1) * $COUNT) + 1;
	$page_to = $page_from + $matches->size() - 1;
	$label = sprintf('Showing results %d to %d of about %d for "%s"',
		$page_from, $page_to, $matches->get_matches_estimated(), $Q);
	$result = $doc->createElement('p');
	$result->appendChild(new DOMText($label));
	return $result;
}

function result_table($doc, $matches) {
	$result = $doc->createElement('table');
	$result->appendChild(new DOMAttr('class', 'searchresults'));
	# Write the header row
	$row = $doc->createElement('tr');
	foreach (array('Relevance', 'Link') as $content) {
		$cell = $doc->createElement('th');
		$cell->appendChild(new DOMText($content));
		$row->appendChild($cell);
	}
	$result->appendChild($row);
	# Write the result rows
	$i = $matches->begin();
	while (! $i->equals($matches->end())) {
		list($url, $data) = explode("\n", $i->get_document()->get_data(), 2);
		$relevance = new DOMText(sprintf('%d%%', $i->get_percent()));
		$link = $doc->createElement('a');
		$link->appendChild(new DOMAttr('href', $url));
		$link->appendChild(new DOMText($data));
		$row = $doc->createElement('tr');
		foreach (array($relevance, $link) as $content) {
			$cell = $doc->createElement('td');
			$cell->appendChild($content);
			$row->appendChild($cell);
		}
		$result->appendChild($row);
		$i->next();
	}
	return $result;
}

function result_page_link($doc, $page, $label='') {
	global $Q, $PAGE, $PAGE_MIN, $PAGE_MAX, $COUNT;

	if ($label == '') $label = strval($page);
	if (($page == $PAGE) || ($page < $PAGE_MIN) || ($page > $PAGE_MAX)) {
		$result = $doc->createTextNode($label);
	}
	else {
		$result = $doc->createElement('a');
		$result->appendChild(new DOMAttr('href',
			sprintf('?q=%s&page=%d&count=%d', $Q, $page, $COUNT)));
		$result->appendChild(new DOMText($label));
	}
	return $result;
}

function result_pages($doc) {
	global $PAGE, $PAGE_MIN, $PAGE_MAX;

	$result = $doc->createElement('p');
	$result->appendChild(new DOMAttr('class', 'search-pages'));
	$result->appendChild(result_page_link($doc, $PAGE - 1, '< Previous'));
	$result->appendChild(new DOMText(' '));
	for ($i = $PAGE_MIN; $i <= $PAGE_MAX; $i++) {
		$result->appendChild(result_page_link($doc, $i));
		$result->appendChild(new DOMText(' '));
	}
	$result->appendChild(result_page_link($doc, $PAGE + 1, 'Next >'));
	return $result;
}

try {
	$doc = new DOMDocument('1.0', '__ENCODING__');
	$root = $doc->createElement('div');
	$doc->appendChild($root);
	$matches = run_query();
	$root->appendChild(result_header($doc, $matches));
	$root->appendChild(result_pages($doc));
	$root->appendChild(result_table($doc, $matches));
	print($doc->saveXML($doc->documentElement));
}
catch (Exception $e) {
	print(htmlspecialchars($e->getMessage() . "\n"));
}
