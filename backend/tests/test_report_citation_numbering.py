from app.research.services.report_content import number_report_citations


def test_source_ids_become_consecutive_reference_numbers_in_body_and_bibliography() -> None:
    citations = [{'id': 1, 'sourceId': '26'}, {'id': 2, 'sourceId': '18'}, {'id': 3, 'sourceId': '19'}]
    text = '依据[资料18；资料19，新闻正文]以及[资料26]。\n\n[资料26] 论文\n[资料18] 新闻\n[资料19] 装备'
    numbered = number_report_citations(text, citations)
    assert numbered == '依据[2][3]（新闻正文）以及[1]。\n\n[1] 论文\n[2] 新闻\n[3] 装备'
    assert number_report_citations(numbered, citations) == numbered
    assert citations[0]['sourceId'] == '26'


def test_unknown_or_ambiguous_sources_are_not_given_invented_numbers() -> None:
    citations = [{'id': 1, 'sourceId': '18'}, {'id': 2, 'sourceId': '18'}]
    assert number_report_citations('未知[资料999]，歧义[资料18]。', citations) == '未知[资料999]，歧义[资料18]。'


def test_typed_sources_and_large_ids_are_matched_without_numeric_coercion() -> None:
    citations = [{'id': 7, 'sourceId': '9007199254740993', 'type': 'paper'}]
    assert number_report_citations('依据[paper:9007199254740993]。', citations) == '依据[1]。'


def test_evidence_ids_mentioned_in_prose_use_the_same_reference_number() -> None:
    citations = [{'id': 1, 'sourceId': '26'}, {'id': 2, 'sourceId': '18'}]
    assert number_report_citations('资料18、资料26为所选证据。', citations) == '[2]、[1]为所选证据。'
    assert number_report_citations('资料18、26为所选证据。', citations) == '[2]、[1]为所选证据。'
