"""Authorized article assets stay integrity checked and detail-only."""

import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

from lxml import html

from app.intelligence.services.authorized_article import read_authorized_article
from config.env import UploadConfig

spec = importlib.util.spec_from_file_location(
    'authorized_import', Path(__file__).parents[1] / 'scripts/complete_authorized_articles.py'
)
importer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(importer)


def test_extract_preserves_paragraph_and_image_order():
    node = html.fromstring(
        '<div><p>第一段<strong>强调</strong><img src="/one.png"/>图注</p><p>末段<br/>尾句</p><script>bad()</script></div>'
    )
    blocks = importer.extract_blocks(node)
    assert blocks == [
        {'type': 'paragraph', 'text': '第一段强调'},
        {'type': 'image', 'source': '/one.png', 'alt': ''},
        {'type': 'paragraph', 'text': '图注'},
        {'type': 'paragraph', 'text': '末段'},
        {'type': 'paragraph', 'text': '尾句'},
    ]


def test_assets_require_matching_checksum_and_safe_key(tmp_path, monkeypatch):
    monkeypatch.setattr(UploadConfig, 'UPLOAD_PATH', str(tmp_path))
    key = 'curated-news-' + 'a' * 24
    path = tmp_path / 'authorized_articles' / key / 'article.json'
    path.parent.mkdir(parents=True)
    blocks = [
        {'type': 'paragraph', 'text': '真实正文'},
        {'type': 'image', 'src': 'data:image/png;base64,AAAA', 'alt': '图'},
    ]
    raw = json.dumps(blocks).encode()
    path.write_bytes(raw)
    meta = {'asset_key': key, 'sha256': hashlib.sha256(raw).hexdigest()}
    assert read_authorized_article(meta) == blocks
    path.write_bytes(b'changed')
    assert read_authorized_article(meta) == []
    assert read_authorized_article({**meta, 'asset_key': '../escape'}) == []


def test_unsafe_images_are_not_returned(tmp_path, monkeypatch):
    monkeypatch.setattr(UploadConfig, 'UPLOAD_PATH', str(tmp_path))
    key = 'curated-wechat-' + 'b' * 24
    path = tmp_path / 'authorized_articles' / key / 'article.json'
    path.parent.mkdir(parents=True)
    raw = json.dumps([{'type': 'image', 'src': 'javascript:alert(1)'}]).encode()
    path.write_bytes(raw)
    assert read_authorized_article({'asset_key': key, 'sha256': hashlib.sha256(raw).hexdigest()}) == []


def test_catalog_does_not_load_full_text_for_lists(monkeypatch):
    from app.intelligence.services import catalog

    article = SimpleNamespace(
        id=1001,
        source=SimpleNamespace(type='website', name='来源'),
        category=None,
        category_id=None,
        title='标题',
        published_at=None,
        content='正文',
        content_zh=None,
        url='https://example.test',
        author=None,
        is_pushed=False,
    )
    assert 'body_blocks' not in catalog.IntelligenceCatalogService.article_dict(article, date_formatter=str)
    assert not hasattr(catalog, 'read_authorized_article')
    row = catalog.IntelligenceCatalogService.article_dict(article, detail=True, date_formatter=str)
    assert row['content'] == '正文'
    assert 'body_blocks' not in row
