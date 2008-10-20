require '__XAPIAN__';

# Defaults and limits
$PAGE_DEFAULT = 1;
$PAGE_MIN = 1;
$PAGE_MAX = 0; # Calculated by run_query()
$COUNT_DEFAULT = 10;
$COUNT_MIN = 10;
$COUNT_MAX = 100;

# Globals derived from GET values
$Q = array_key_exists('q', $_GET) ? strval($_GET['q']) : '';
$REFINE = array_key_exists('refine', $_GET) ? intval($_GET['refine']) : 0;
$PAGE = array_key_exists('page', $_GET) ? intval($_GET['page']) : $PAGE_DEFAULT;
$PAGE = max($PAGE_MIN, $PAGE);
$COUNT = array_key_exists('count', $_GET) ? intval($_GET['count']) : $COUNT_DEFAULT;
$COUNT = max($COUNT_MIN, min($COUNT_MAX, $COUNT));

# Extract additional queries when refine is set
$QUERIES[] = $Q;
if ($REFINE) {
	$i = 0;
	while (array_key_exists('q' . strval($i), $_GET)) {
		$QUERIES[] = strval($_GET['q' . strval($i)]);
		$i++;
	}
}

function run_query() {
	global $QUERIES, $PAGE, $COUNT, $PAGE_MAX;

	$db = new XapianDatabase('search');
	$enquire = new XapianEnquire($db);
	$parser = new XapianQueryParser();
	$parser->set_stemmer(new XapianStem('__LANG__'));
	$parser->set_stemming_strategy(XapianQueryParser::STEM_SOME);
	$parser->set_database($db);
	$query = NULL;
	foreach ($QUERIES as $q) {
		$left = $parser->parse_query($q,
			XapianQueryParser::FLAG_BOOLEAN_ANY_CASE |  # Enable boolean operators (with any case)
			XapianQueryParser::FLAG_PHRASE |            # Enable quoted phrases
			XapianQueryParser::FLAG_LOVEHATE |          # Enable + and -
			XapianQueryParser::FLAG_SPELLING_CORRECTION # Enable suggested corrections
		);
		if ($query)
			$query = new XapianQuery(XapianQuery::OP_AND, $left, $query);
		else
			$query = $left;
	}
	$enquire->set_query($query);
	$result = $enquire->get_mset((($PAGE - 1) * $COUNT) + 1, $COUNT);
	$PAGE_MAX = ceil($result->get_matches_estimated() / floatval($COUNT));
	return $result;
}

function limit_search($doc) {
	global $Q, $QUERIES, $COUNT, $REFINE;

	# Generate the first row
	$tr1 = $doc->createElement('tr');
	$td = $doc->createElement('td');
	$td->appendChild(new DOMAttr('class', 'col1'));
	$td->appendChild(new DOMText('Search for'));
	$tr1->appendChild($td);
	$input = $doc->createElement('input');
	$input->appendChild(new DOMAttr('type', 'text'));
	$input->appendChild(new DOMAttr('name', 'q'));
	$input->appendChild(new DOMAttr('value', $Q));
	$td = $doc->createElement('td');
	$td->appendChild(new DOMAttr('class', 'col2'));
	$td->appendChild($input);
	$td->appendChild(new DOMText(' '));
	$input = $doc->createElement('input');
	$input->appendChild(new DOMAttr('type', 'submit'));
	$input->appendChild(new DOMAttr('value', 'Go'));
	$span = $doc->createElement('span');
	$span->appendChild(new DOMAttr('class', 'button-blue'));
	$span->appendChild($input);
	$td->appendChild($span);
	$td->appendChild(new DOMText(' '));
	$a = $doc->createElement('a');
	$a->appendChild(new DOMAttr('href', 'search.html'));
	$a->appendChild(new DOMAttr('onclick', 'javascript:popup("search.html","internal",300,400);return false;'));
	$a->appendChild(new DOMText('Help'));
	$td->appendChild($a);
	$tr1->appendChild($td);
	# Generate the second row
	$tr2 = $doc->createElement('tr');
	$td = $doc->createElement('td');
	$td->appendChild(new DOMAttr('class', 'col1'));
	$td->appendChild(new DOMText(' '));
	$tr2->appendChild($td);
	$input = $doc->createElement('input');
	$input->appendChild(new DOMAttr('type', 'checkbox'));
	$input->appendChild(new DOMAttr('name', 'refine'));
	$input->appendChild(new DOMAttr('value', '1'));
	if ($REFINE) $input->appendChild(new DOMAttr('checked', 'checked'));
	$label = $doc->createElement('label');
	$label->appendChild($input);
	$label->appendChild(new DOMText(' Search within results'));
	$td = $doc->createElement('td');
	$td->appendChild(new DOMAttr('class', 'col2'));
	$td->appendChild($label);
	$tr2->appendChild($td);
	# Stick it all in a table in a form
	$tbody = $doc->createElement('tbody');
	$tbody->appendChild($tr1);
	$tbody->appendChild($tr2);
	$table = $doc->createElement('table');
	$table->appendChild(new DOMAttr('class', 'limit-search'));
	$table->appendChild($tbody);
	$count = $doc->createElement('input');
	$count->appendChild(new DOMAttr('type', 'hidden'));
	$count->appendChild(new DOMAttr('name', 'count'));
	$count->appendChild(new DOMAttr('value', strval($COUNT)));
	$form = $doc->createElement('form');
	$form->appendChild(new DOMAttr('method', 'GET'));
	$form->appendChild($count);
	foreach ($QUERIES as $i => $q) {
		$query = $doc->createElement('input');
		$query->appendChild(new DOMAttr('type', 'hidden'));
		$query->appendChild(new DOMAttr('name', 'q' . strval($i)));
		$query->appendChild(new DOMAttr('value', $q));
		$form->appendChild($query);
	}
	$form->appendChild($table);
	return $form;
}

function results_count($doc, $matches) {
	global $Q, $PAGE, $COUNT;

	$found = $matches->get_matches_estimated();
	$page_from = (($PAGE - 1) * $COUNT) + 1;
	$page_to = $page_from + $matches->size() - 1;

	$td = $doc->createElement('td');
	$td->appendChild(new DOMAttr('class', 'results-count'));
	$strong = $doc->createElement('strong');
	$strong->appendChild(new DOMText(strval($found)));
	$td->appendChild($strong);
	$td->appendChild(new DOMText(' results found'));
	$td->appendChild($doc->createElement('br'));
	$td->appendChild(new DOMText('Results '));
	$strong = $doc->createElement('strong');
	$strong->appendChild(new DOMText(strval($page_from)));
	$td->appendChild($strong);
	$td->appendChild(new DOMText(' to '));
	$strong = $doc->createElement('strong');
	$strong->appendChild(new DOMText(strval($page_to)));
	$td->appendChild($strong);
	$td->appendChild(new DOMText(' shown by relevance'));
	return $td;
}

function results_page($doc, $page, $label='') {
	global $Q, $PAGE, $PAGE_MIN, $PAGE_MAX, $COUNT;

	if ($label == '') $label = strval($page);
	if (($page < $PAGE_MIN) || ($page > $PAGE_MAX)) {
		return $doc->createTextNode($label);
	}
	elseif ($page == $PAGE) {
		$strong = $doc->createElement('strong');
		$strong->appendChild(new DOMText($label));
		return $strong;
	}
	else {
		$url = sprintf('?q=%s&page=%d&count=%d', $Q, $page, $COUNT);
		if ($REFINE) {
			$url .= '&refine=1';
			foreach (array_slice($QUERIES, 1) as $i => $q)
				$url .= sprintf('&q%d=%s', $i, $q);
		}
		$a = $doc->createElement('a');
		$a->appendChild(new DOMAttr('href', $url));
		$a->appendChild(new DOMText($label));
		return $a;
	}
}

function results_sequence($doc) {
	global $PAGE, $PAGE_MIN, $PAGE_MAX;

	$from = max($PAGE_MIN + 1, $PAGE - 5);
	$to = min($PAGE_MAX - 1, $from + 8);

	$td = $doc->createElement('td');
	$td->appendChild(new DOMAttr('class', 'results-sequence'));
	$td->appendChild(results_page($doc, $PAGE - 1, '< Previous'));
	$td->appendChild(new DOMText(' | '));
	$td->appendChild(results_page($doc, $PAGE_MIN));
	if ($from > $PAGE_MIN + 1) $td->appendChild(new DOMText(' ...'));
	$td->appendChild(new DOMText(' '));
	for ($i = $from; $i <= $to; ++$i) {
		$td->appendChild(results_page($doc, $i));
		$td->appendChild(new DOMText(' '));
	}
	if ($to < $PAGE_MAX - 1) $td->appendChild(new DOMText('... '));
	$td->appendChild(results_page($doc, $PAGE_MAX));
	$td->appendChild(new DOMText(' | '));
	$td->appendChild(results_page($doc, $PAGE + 1, 'Next >'));
	return $td;
}

function results_header($doc, $matches, $header=True) {
	global $Q, $QUERIES;

	$strong = $doc->createElement('strong');
	$strong->appendChild(new DOMText($Q));
	foreach (array_slice($QUERIES, 1) as $q)
		$strong->appendChild(new DOMText(sprintf(' AND %s', $q)));
	$td = $doc->createElement('td');
	$td->appendChild(new DOMAttr('colspan', '2'));
	$td->appendChild(new DOMText('Results for : '));
	$td->appendChild($strong);
	$tr = $doc->createElement('tr');
	$tr->appendChild($td);
	$tbody = $doc->createElement('tbody');
	$tbody->appendChild($tr);
	$tr = $doc->createElement('tr');
	$tr->appendChild(new DOMAttr('class', 'summary-options'));
	$tr->appendChild(results_count($doc, $matches));
	$tr->appendChild(results_sequence($doc));
	$tbody->appendChild($tr);
	$table = $doc->createElement('table');
	if ($header)
		$table->appendChild(new DOMAttr('class', 'results-header'));
	else
		$table->appendChild(new DOMAttr('class', 'results-footer'));
	$table->appendChild($tbody);
	return $table;
}

function results_table($doc, $matches) {
	$table = $doc->createElement('table');
	$table->appendChild(new DOMAttr('class', 'basic-table search-results'));
	$thead = $doc->createElement('thead');
	$table->appendChild($thead);
	# Generate the header row
	$tr = $doc->createElement('tr');
	$tr->appendChild(new DOMAttr('class', 'blue-dark'));
	foreach (array('Document', 'Relevance') as $content) {
		$th = $doc->createElement('th');
		$th->appendChild(new DOMText($content));
		$tr->appendChild($th);
	}
	$thead->appendChild($tr);
	$tbody = $doc->createElement('tbody');
	$table->appendChild($tbody);
	# Generate the result rows
	$match = $matches->begin();
	while (! $match->equals($matches->end())) {
		list($url, $title, $desc) = explode("\n",
			$match->get_document()->get_data(), 3);
		$relevance = $match->get_percent();
		# Generate the link & relevance row
		$a = $doc->createElement('a');
		$a->appendChild(new DOMAttr('href', $url));
		$a->appendChild(new DOMText($title));
		$td1 = $doc->createElement('td');
		$td1->appendChild($a);
		$td2 = $doc->createElement('td');
		$td2->appendChild(new DOMAttr('class', 'relevance'));
		$td2->appendChild(new DOMText(sprintf('%d%%', $relevance)));
		$tr = $doc->createElement('tr');
		$tr->appendChild(new DOMAttr('class', 'result row1'));
		$tr->appendChild($td1);
		$tr->appendChild($td2);
		$tbody->appendChild($tr);
		# Generate the description row
		$div = $doc->createElement('div');
		$div->appendChild(new DOMAttr('class', 'url'));
		$div->appendChild(new DOMText($url));
		$hr = $doc->createElement('div');
		$hr->appendChild(new DOMAttr('class', 'hrule-dots'));
		$td = $doc->createElement('td');
		$td->appendChild(new DOMAttr('colspan', '2'));
		$td->appendChild(new DOMText($desc));
		$td->appendChild($doc->createElement('br'));
		$td->appendChild($div);
		$td->appendChild($hr);
		$tr = $doc->createElement('tr');
		$tr->appendChild(new DOMAttr('class', 'result row2'));
		$tr->appendChild($td);
		$tbody->appendChild($tr);
		# Next!
		$match->next();
	}
	return $table;
}

$doc = new DOMDocument('1.0', '__ENCODING__');
$matches = run_query();

print($doc->saveXML(limit_search($doc)));
print($doc->saveXML(results_header($doc, $matches, True)));
print($doc->saveXML(results_table($doc, $matches)));
print($doc->saveXML(results_header($doc, $matches, False)));
print($doc->saveXML(limit_search($doc)));
