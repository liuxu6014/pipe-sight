"""Integrity-checked, non-HTML article blocks served after detail access checks."""
import base64
import hashlib
import io
import json
import re
import stat
import warnings
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps

from config.env import UploadConfig

MAX_COVER_SOURCE_BYTES = 20 * 1024 * 1024
MAX_COVER_PIXELS = 20_000_000
MAX_COVER_URI_BYTES = 100_000

def read_authorized_article_cover(metadata: Any) -> str:
    """Read only the first attested photo; never load full blocks for a list card."""
    if not isinstance(metadata, dict):
        return ''
    key, images = metadata.get('asset_key'), metadata.get('images')
    if not isinstance(key, str) or not re.fullmatch(r'curated-(?:news|wechat)-[a-f0-9]{24}', key):
        return ''
    if not isinstance(images, list) or not images or not isinstance(images[0], dict):
        return ''
    filename, digest = images[0].get('file'), images[0].get('sha256')
    if (not isinstance(digest, str) or not re.fullmatch(r'[a-f0-9]{64}', digest)
        or not isinstance(filename, str) or not re.fullmatch(digest + r'\.(?:jpeg|jpg|png|gif|webp)', filename)):
        return ''
    root = Path(UploadConfig.UPLOAD_PATH) / 'authorized_articles'
    directory, limit = root / key, MAX_COVER_SOURCE_BYTES
    path = directory / filename
    try:
        if root.is_symlink() or directory.is_symlink() or path.is_symlink():
            return ''
        info = path.stat()
        if not path.resolve().is_relative_to(root.resolve()) or not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= limit:
            return ''
        with path.open('rb') as stream:
            raw = stream.read(limit + 1)
        if len(raw) > limit or hashlib.sha256(raw).hexdigest() != digest:
            return ''
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as image:
                expected = {'jpeg': 'JPEG', 'jpg': 'JPEG', 'png': 'PNG', 'gif': 'GIF', 'webp': 'WEBP'}[path.suffix[1:]]
                if image.format != expected or image.width * image.height > MAX_COVER_PIXELS:
                    return ''
                image.verify()
            with Image.open(io.BytesIO(raw)) as image:
                thumbnail = ImageOps.exif_transpose(image)
                thumbnail.thumbnail((300, 200), Image.Resampling.LANCZOS)
                output = io.BytesIO()
                thumbnail.convert('RGB').save(output, format='JPEG', quality=80)
        # Re-encoding drops metadata and ensures a raster-only bounded data URI.
        cover = 'data:image/jpeg;base64,' + base64.b64encode(output.getvalue()).decode('ascii')
        return cover if len(cover) <= MAX_COVER_URI_BYTES else ''
    except (OSError, ValueError, RuntimeError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        return ''


def read_authorized_article(metadata):
    if not isinstance(metadata, dict):
        return []
    key = metadata.get('asset_key', '')
    if not isinstance(key, str) or not re.fullmatch(r'curated-(?:news|wechat)-[a-f0-9]{24}', key):
        return []
    try:
        root = Path(UploadConfig.UPLOAD_PATH) / 'authorized_articles'
        directory = root / key
        path = directory / 'article.json'
        if root.is_symlink() or directory.is_symlink() or path.is_symlink():
            return []
        if not path.resolve().is_relative_to(root.resolve()) or not path.is_file() or path.stat().st_size > 50_000_000:
            return []
        with path.open('rb') as stream:
            raw = stream.read(50_000_001)
        if len(raw) > 50_000_000:
            return []
        if hashlib.sha256(raw).hexdigest() != metadata.get('sha256'):
            return []
        blocks = json.loads(raw)
        if not isinstance(blocks, list):
            return []
        for block in blocks:
            if not isinstance(block, dict):
                return []
            if block.get('type') == 'paragraph' and isinstance(block.get('text'), str):
                continue
            if block.get('type') == 'image' and isinstance(block.get('src'), str) and re.fullmatch(r'data:image/(?:png|jpeg|gif|webp);base64,[A-Za-z0-9+/=]+', block['src']):
                continue
            return []
        return blocks
    except (OSError, ValueError, RuntimeError):
        return []
