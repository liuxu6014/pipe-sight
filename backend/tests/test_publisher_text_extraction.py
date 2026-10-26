"""The reflowed reader must preserve column order and real, escaped text."""

import importlib.util
import re
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    'publisher_extract', Path(__file__).parents[1] / 'scripts/prepare_publisher_paper_previews.py'
)
extract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(extract)


def line(text: str, x: float, y: float, right: float) -> dict:
    return {'text': text, 'bbox': (x, y, right, y + 10), 'size': 10, 'heading': False}


def test_two_columns_are_read_down_then_across_not_interleaved() -> None:
    rows = [
        line('左栏开始', 57, 100, 288),
        line('右栏开始', 308, 100, 539),
        line('左栏续文', 57, 117, 288),
        line('右栏续文', 308, 117, 539),
    ]
    assert [row['text'] for row in extract.reading_order(rows, True)] == [
        '左栏开始',
        '左栏续文',
        '右栏开始',
        '右栏续文',
    ]


def test_spanning_figure_is_a_column_boundary() -> None:
    rows = [
        line('左栏', 57, 100, 288),
        line('右栏', 308, 100, 539),
        line('全宽图表', 57, 150, 539),
        line('图后左栏', 57, 200, 288),
        line('图后右栏', 308, 200, 539),
    ]
    assert [row['text'] for row in extract.reading_order(rows, True)] == [
        '左栏',
        '右栏',
        '全宽图表',
        '图后左栏',
        '图后右栏',
    ]


def test_wrapped_text_is_rejoined_without_changing_language_or_executing_markup() -> None:
    assert extract.join_lines(['non-destruc-', 'tive testing']) == 'non-destructive testing'
    assert extract.join_lines(['ultrasonic-', 'guided waves']) == 'ultrasonic-guided waves'
    assert extract.join_lines(['frequency-', 'thickness product']) == 'frequency-thickness product'
    assert extract.join_lines(['管道缺陷', '检测方法']) == '管道缺陷检测方法'
    rendered = extract.render_text([line('<script>bad</script>', 57, 100, 288)], chinese=True)
    assert '&lt;script&gt;' in rendered
    assert '<script>' not in rendered


def test_actual_chinese_source_has_correct_abstract_citations_and_subheadings() -> None:
    fitz = pytest.importorskip('pymupdf')
    with fitz.open(extract.PDFS / 'pipeline-inspection-review-2024.pdf') as document:
        first, _ = extract.extract_page(document[0], 1, 'pipeline-inspection-review-2024.pdf')
        assert re.sub('<[^>]+>', '', first).startswith('摘要：【目的】')
        third, _ = extract.extract_page(document[2], 3, 'pipeline-inspection-review-2024.pdf')
        assert '<h2>1.1.1' in third
        assert '国内外油气管道内检测领域的主流检测技术[4-5]。' in third
        fourth, _ = extract.extract_page(document[3], 4, 'pipeline-inspection-review-2024.pdf')
        assert '1.1.3' in fourth and '结果的因素主要有检测频率' in fourth


def test_actual_english_body_is_text_not_full_page_screenshots() -> None:
    fitz = pytest.importorskip('pymupdf')
    with fitz.open(extract.PDFS / 'coatings-14-00358.pdf') as document:
        first, audit = extract.extract_page(document[0], 1, 'coatings-14-00358.pdf')
        assert '<h2>1. Introduction</h2>' in first
        assert '<p>Abstract: This paper presents research' in first
        minimum_body_characters = 3000
        assert audit['text_characters'] > minimum_body_characters
        assert '<img' not in first
