"""No network: conservative source rights, complete records and safe JATS rendering."""
import importlib.util
from pathlib import Path

import pytest
from lxml import etree

spec = importlib.util.spec_from_file_location('prepare_papers', Path(__file__).parents[1] / 'scripts/prepare_licensed_papers.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def source(license_url='https://creativecommons.org/licenses/by/4.0/'):
    return ('<article xmlns:xlink="http://www.w3.org/1999/xlink"><front><journal-meta>'
            '<journal-title-group><journal-title>Test Journal</journal-title></journal-title-group>'
            '<publisher><publisher-name>Test Publisher</publisher-name></publisher></journal-meta>'
            '<article-meta><article-id pub-id-type="pmcid">PMC123</article-id><article-id pub-id-type="doi">10.1234/test</article-id>'
            '<title-group><article-title>Pipeline corrosion inspection</article-title></title-group>'
            '<contrib-group content-type="author"><contrib><name><given-names>Ada</given-names><surname>Example</surname></name></contrib></contrib-group>'
            '<aff>Engineering Institute</aff><pub-date pub-type="epub"><year>2024</year><month>3</month><day>18</day></pub-date>'
            '<volume>14</volume><issue>3</issue><elocation-id>358</elocation-id><abstract><p>' + 'Original abstract. ' * 30 + '</p></abstract>'
            '<permissions><license><license-p><ext-link xlink:href="' + license_url + '">License</ext-link></license-p></license></permissions>'
            '</article-meta></front><body><sec><title>Methods</title><p>' + 'Complete body paragraph. ' * 200 + '</p></sec></body>'
            '<back><ref-list><ref>Source reference</ref></ref-list></back></article>').encode()


def test_metadata_handles_author_group_without_contrib_type():
    _, record = module.extract_metadata(source(), {'doi': '10.1234/test'})
    assert record['authors'] == ['Ada Example']
    assert record['original_date'] == '2024-03-18'
    assert record['references_count'] == 1


def test_no_redistribution_license_or_incomplete_body_is_rejected():
    with pytest.raises(ValueError, match='license'):
        module.extract_metadata(source('https://creativecommons.org/licenses/by-nc-nd/4.0/'), {'doi': '10.1234/test'})
    with pytest.raises(ValueError, match='incomplete'):
        module.extract_metadata(source().replace(b'<issue>3</issue>', b''), {'doi': '10.1234/test'})


def test_third_party_figure_rights_are_not_assumed():
    raw = source().replace(b'</body>', b'<fig><caption>Reproduced with permission</caption></fig></body>')
    with pytest.raises(ValueError, match='third-party'):
        module.extract_metadata(raw, {'doi': '10.1234/test'})


def test_reader_preserves_body_references_and_never_emits_source_scripts():
    root, record = module.extract_metadata(source(), {'doi': '10.1234/test'})
    etree.SubElement(root.find('body'), 'script').text = 'alert("unsafe")'
    document, count = module.render_article(root, record, {})
    assert '<script' not in document
    assert 'Complete body paragraph.' in document and 'Source reference' in document
    assert 'Content-Security-Policy' in document
    assert count == 0


def test_missing_figure_asset_is_a_rejection_not_an_incomplete_fulltext():
    root, record = module.extract_metadata(source(), {'doi': '10.1234/test'})
    graphic = etree.SubElement(root.find('body'), 'graphic')
    graphic.set(module.XLINK, 'missing.png')
    with pytest.raises(ValueError, match='missing inline/figure asset'):
        module.render_article(root, record, {})


def test_root_floats_math_delimiters_and_ordered_steps_are_preserved():
    root, record = module.extract_metadata(source(), {'doi': '10.1234/test'})
    floats = etree.SubElement(root, 'floats-group')
    fig = etree.SubElement(floats, 'fig')
    etree.SubElement(fig, 'caption').text = 'Figure stored outside body'
    body = root.find('body')
    math = etree.SubElement(body, '{http://www.w3.org/1998/Math/MathML}math')
    fence = etree.SubElement(math, '{http://www.w3.org/1998/Math/MathML}mfenced', open='|', close='|', separators='')
    etree.SubElement(fence, '{http://www.w3.org/1998/Math/MathML}mi', mathvariant='bold').text = 'x'
    steps = etree.SubElement(body, 'list', attrib={'list-type': 'order'})
    etree.SubElement(steps, 'list-item').text = 'First step'
    document, _ = module.render_article(root, record, {})
    assert 'Figure stored outside body' in document
    assert '<mo>|</mo>' in document and 'mathvariant="bold"' in document
    assert '<ol type="1">' in document and 'First step' in document


def test_adapted_third_party_figures_require_separate_rights_evidence():
    raw = source().replace(b'</body>', b'<fig><caption>Diagram adapted from [31]</caption></fig></body>')
    with pytest.raises(ValueError, match='third-party'):
        module.extract_metadata(raw, {'doi': '10.1234/test'})


def test_candidate_filter_excludes_retracted_and_non_article_records():
    core = dict(pmcid='PMC123', doi='10.1234/test', title='Pipeline corrosion inspection', license='cc by')
    assert module.eligible_core(core)
    assert not module.eligible_core({**core, 'commentCorrectionList': {'commentCorrection': [{'type': 'RetractionIn'}]}})
    assert not module.eligible_core({**core, 'pmcid': None})
    assert not module.eligible_core({**core, 'title': 'Antiracism in Academic Medicine: Leak in the Physician Pipeline'})
