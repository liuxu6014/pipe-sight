"""Read collector-generated, licensed HTML from a fixed local asset location."""

from __future__ import annotations

import hashlib
import json
import re
import stat
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from config.env import UploadConfig

MAX_HTML_BYTES = 30 * 1024 * 1024
MAX_PUBLISHER_PAGES = 100
PUBLISHER_PREVIEW_MANIFEST = Path(__file__).resolve().parents[4] / 'data/curated/paper-fulltext-previews.json'


def read_publisher_pdf_preview(doi: Any) -> dict[str, Any]:
    """Serve integrity-checked extracted text, without implying a reuse license."""
    unavailable = {'status': 'unavailable'}
    if not isinstance(doi, str):
        return unavailable
    try:
        records = json.loads(PUBLISHER_PREVIEW_MANIFEST.read_text(encoding='utf-8'))['records']
        record = records.get(doi.strip().lower())
        if not isinstance(record, dict):
            return unavailable
        url = record['pdf_url']
        parsed = urlsplit(url)
        if (parsed.scheme != 'https' or parsed.netloc not in {'mdpi-res.com', 'yqcy.pipechina.com.cn'}
                or not parsed.path.endswith('.pdf') or parsed.query or parsed.fragment
                or not isinstance(record['pages'], int) or record['pages'] <= 0
                or not re.fullmatch(r'[0-9a-f]{64}', record['sha256'])):
            return unavailable
        key = 'paper-' + hashlib.sha256(doi.strip().lower().encode()).hexdigest()[:24]
        if record.get('asset_key') != key or record['pages'] > MAX_PUBLISHER_PAGES:
            return unavailable
        root = Path(UploadConfig.UPLOAD_PATH) / 'publisher_paper_previews'
        directory = root / key
        if root.is_symlink() or directory.is_symlink():
            return unavailable
        path = directory / 'article.html'
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            return unavailable
        info = path.stat()
        if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= MAX_HTML_BYTES:
            return unavailable
        with path.open('rb') as stream:
            raw = stream.read(MAX_HTML_BYTES + 1)
        if len(raw) > MAX_HTML_BYTES or hashlib.sha256(raw).hexdigest() != record.get('text_sha256'):
            return unavailable
        document = raw.decode('utf-8')
        return {'status': 'publisher_preview', 'reader_kind': 'extracted_text', 'format': 'html', 'source_format': 'pdf', 'source_url': url, 'pages': record['pages'], 'text_characters': record.get('text_characters', 0), 'html': CSP_PREFIX + document}
    except (OSError, ValueError, UnicodeError, RuntimeError, KeyError, TypeError, AttributeError):
        return unavailable

ALLOWED_LICENSES = frozenset(
    f'https://creativecommons.org/licenses/by/{version}/'
    for version in ('1.0', '2.0', '2.5', '3.0', '4.0')
) | {'https://creativecommons.org/publicdomain/zero/1.0/'}
# Precede even a collector-supplied head: subsequent policies cannot relax this one.
CSP_PREFIX = (
    '<!doctype html><meta http-equiv="Content-Security-Policy" content="'
    "default-src 'none'; script-src 'none'; style-src 'unsafe-inline'; "
    "img-src data:; base-uri 'none'; form-action 'none'; frame-src 'none'; "
    "connect-src 'none'; object-src 'none'"
    '"><meta name="referrer" content="no-referrer">'
)


def read_licensed_full_text(metadata: Any) -> dict[str, Any]:
    """Fail closed without leaking disk paths, or substituting an abstract."""
    unavailable = {'status': 'unavailable'}
    if not isinstance(metadata, dict):
        return unavailable
    key = metadata.get('asset_key')
    digest = metadata.get('sha256')
    license_url = metadata.get('license_url')
    source_url = metadata.get('source_url')
    if (
        not isinstance(key, str) or not re.fullmatch(r'PMC[0-9]+', key)
        or not isinstance(digest, str) or not re.fullmatch(r'[0-9a-fA-F]{64}', digest)
        or not isinstance(license_url, str) or license_url not in ALLOWED_LICENSES
        or source_url != f'https://europepmc.org/articles/{key}' or metadata.get('format') != 'html'
    ):
        return unavailable
    # Never consume a path or filename from metadata, including extra fields.
    root = Path(UploadConfig.UPLOAD_PATH) / 'licensed_papers'
    directory = root / key
    path = directory / 'article.html'
    try:
        if root.is_symlink() or directory.is_symlink() or path.is_symlink():
            return unavailable
        if not path.resolve().is_relative_to(root.resolve()):
            return unavailable
        info = path.stat()
        if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= MAX_HTML_BYTES:
            return unavailable
        with path.open('rb') as stream:
            content = stream.read(MAX_HTML_BYTES + 1)
        if len(content) > MAX_HTML_BYTES or hashlib.sha256(content).hexdigest() != digest.lower():
            return unavailable
        html = content.decode('utf-8')
    except (OSError, UnicodeError, ValueError, RuntimeError):
        return unavailable
    if not html.strip():
        return unavailable
    return {
        'status': 'available',
        'html': CSP_PREFIX + html,
        'license_url': license_url,
        'source_url': source_url,
        'format': 'html',
        'language': metadata.get('language') if isinstance(metadata.get('language'), str) else '',
    }
