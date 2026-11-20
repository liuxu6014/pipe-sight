"""Configured PDF fonts must be real, embeddable and cover the document."""

from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from pypdf import PdfReader
from reportlab.pdfbase import pdfmetrics

from app.entrypoints import runtime_check
from app.research.services import digest_export, exporters, pdf_fonts

LATIN_FONT = Path(__file__).resolve().parents[1] / 'assets/font/Arial.ttf'


@pytest.fixture(autouse=True)
def clear_explicit_fonts(monkeypatch):
    monkeypatch.delenv('PDF_CJK_FONT_PATH', raising=False)
    monkeypatch.delenv('PDF_DIGEST_FONT_PATH', raising=False)


@pytest.fixture
def chinese_font():
    candidates = [
        Path.home() / 'Library/Fonts/仿宋_GB2312.ttf',
        *(Path(path) for path, _ in pdf_fonts.DEFAULT_CJK_CANDIDATES),
    ]
    for path in candidates:
        if path.is_file():
            try:
                pdf_fonts.validated_ttf(path, name='FixtureProbe', label='测试环境中文字体')
                return path
            except ValueError:
                continue
    pytest.fail('完整 PDF 验收需安装 deploy/fonts/README.md 指定的可嵌入中文字体')


@pytest.mark.parametrize('payload', [b'', b'not a font', b'OTTO\x00\x00\x00\x00'])
def test_existing_invalid_font_is_rejected_by_real_ttf_parser(tmp_path, payload):
    path = tmp_path / 'FangSong_GB2312.ttf'
    path.write_bytes(payload)
    with pytest.raises(ValueError, match='损坏或不支持'):
        pdf_fonts.validated_ttf(path, name='InvalidFixture', label='PDF_DIGEST_FONT_PATH')


def test_real_latin_font_cannot_pass_chinese_and_punctuation_preflight():
    with pytest.raises(ValueError, match='缺少所需中文或标点字形'):
        pdf_fonts.validate_runtime_fonts(digest_path=str(LATIN_FONT))
    # It is a valid TrueType file; failure is glyph coverage, not extension.
    assert pdf_fonts.validated_ttf(
        LATIN_FONT, name='LatinFixture', label='fixture', required_text='ABC123'
    ).face.charToGlyph[ord('A')]


@pytest.mark.parametrize('kind', ['cjk', 'digest'])
def test_explicit_missing_font_is_not_hidden_by_registered_font_cache(chinese_font, tmp_path, monkeypatch, kind):
    if kind == 'cjk':
        exporters._pdf_font()
        monkeypatch.setenv('PDF_CJK_FONT_PATH', str(tmp_path / 'missing.ttf'))
        with pytest.raises(ValueError, match='PDF_CJK_FONT_PATH'):
            exporters._pdf_font()
    else:
        digest_export._digest_pdf_font('科技情报', exporters._pdf_font())
        monkeypatch.setenv('PDF_DIGEST_FONT_PATH', str(tmp_path / 'missing.ttf'))
        with pytest.raises(ValueError, match='PDF_DIGEST_FONT_PATH'):
            digest_export._digest_pdf_font('科技情报', 'old-fallback')


@pytest.mark.parametrize('kind', ['cjk', 'digest'])
def test_explicit_latin_font_does_not_fall_back_to_another_system_font(monkeypatch, kind):
    key = 'PDF_CJK_FONT_PATH' if kind == 'cjk' else 'PDF_DIGEST_FONT_PATH'
    monkeypatch.setenv(key, str(LATIN_FONT))
    with pytest.raises(ValueError, match=key + ' 缺少'):
        if kind == 'cjk':
            exporters._pdf_font()
        else:
            digest_export._digest_pdf_font('科技情报', 'old-fallback')


def test_explicit_digest_checks_this_document_glyphs_before_falling_back(chinese_font, monkeypatch):
    monkeypatch.setenv('PDF_DIGEST_FONT_PATH', str(chinese_font))
    with pytest.raises(ValueError, match=r'U\+10FFFF'):
        digest_export._digest_pdf_font('科技情报' + chr(0x10FFFF), 'old-fallback')
    # Formatting controls inserted for citation wrapping do not need glyphs.
    assert digest_export._digest_pdf_font('科技情报\u2060[1]', 'old-fallback') != 'old-fallback'


def test_explicit_report_checks_its_actual_text(chinese_font, monkeypatch):
    monkeypatch.setenv('PDF_CJK_FONT_PATH', str(chinese_font))
    report = SimpleNamespace(title='科研报告', content='正文' + chr(0x10FFFF), metadata={}, citations=[])
    with pytest.raises(ValueError, match=r'U\+10FFFF'):
        exporters.build_pdf(report, is_draft=False)


def test_replaced_font_file_cannot_reuse_old_global_face_mapping(chinese_font, tmp_path):
    path = tmp_path / 'configured.ttf'
    original = chinese_font.read_bytes()
    path.write_bytes(original)
    first = pdf_fonts.register_configured_font(str(path), prefix='ReplacementFixture', label='fixture')
    path.write_bytes(original + b'\0\0\0\0')
    second = pdf_fonts.register_configured_font(str(path), prefix='ReplacementFixture', label='fixture')
    assert first != second
    assert pdfmetrics.getFont(first) is not pdfmetrics.getFont(second)
    path.write_bytes(b'corrupt replacement')
    with pytest.raises(ValueError, match='损坏或不支持'):
        pdf_fonts.register_configured_font(str(path), prefix='ReplacementFixture', label='fixture')


def test_valid_configured_font_is_embedded_in_actual_pdf(chinese_font, monkeypatch):
    monkeypatch.setenv('PDF_CJK_FONT_PATH', str(chinese_font))
    report = SimpleNamespace(
        title='科研报告', content='## 行业洞察\n\n技术研究报告，数据来源。', metadata={}, citations=[]
    )
    data = exporters.build_pdf(report, is_draft=False)[2]
    pdf = PdfReader(BytesIO(data))
    assert '技术研究报告，数据来源。' in pdf.pages[0].extract_text()
    fonts = [font.get_object() for font in pdf.pages[0]['/Resources']['/Font'].values()]
    assert all('STSong-Light' not in str(font.get('/BaseFont')) for font in fonts)
    assert any(font.get('/FontDescriptor') and font['/FontDescriptor'].get_object().get('/FontFile2') for font in fonts)


def test_real_startup_preflight_rejects_garbage_font_even_with_live_scanner(tmp_path, monkeypatch):
    path = tmp_path / 'FangSong_GB2312.ttf'
    path.write_bytes(b'synthetic invalid font')
    monkeypatch.setenv('FILE_SCAN_MODE', 'external')
    monkeypatch.setenv('FILE_SCAN_COMMAND', 'pipesight-file-scan')
    monkeypatch.setenv('PDF_DIGEST_FONT_PATH', str(path))
    monkeypatch.setenv('JWT_SECRET_KEY', 'synthetic-font-preflight-test-key-only-123456789')
    monkeypatch.setattr(runtime_check.shutil, 'which', lambda _: '/bin/pipesight-file-scan')
    monkeypatch.setattr(runtime_check, 'scan_file', lambda *_a, **_kw: (0, 'PONG'))
    errors = runtime_check.runtime_errors()
    assert len(errors) == 1 and 'PDF_DIGEST_FONT_PATH' in errors[0] and '损坏' in errors[0]


def test_real_startup_preflight_accepts_valid_font(chinese_font):
    pdf_fonts.validate_runtime_fonts(digest_path=str(chinese_font), cjk_path=str(chinese_font))
