"""Validate embeddable fonts before PDF rendering or production startup."""

import hashlib
import struct
import unicodedata
from io import BytesIO
from pathlib import Path

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFError, TTFont

CJK_REQUIRED_TEXT = (
    '科技情报周月报研究报告行业洞察数据来源年月日至零一二三四五六七八九十'
    '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
    '，。；：！？（）【】《》“”‘’、—…·-+/%[]'
)
MAX_FONT_BYTES = 128 * 1024 * 1024
DEFAULT_CJK_CANDIDATES = (
    # Songti's first collection face is Black; retain the regular SC face.
    ('/System/Library/Fonts/Supplemental/Songti.ttc', 6),
    ('C:/Windows/Fonts/simsun.ttc', 0),
    ('/usr/local/share/fonts/simsun.ttf', 0),
    ('/usr/share/fonts/truetype/arphic-gbsn00lp/gbsn00lp.ttf', 0),
    ('/System/Library/Fonts/Supplemental/Arial Unicode.ttf', 0),
    ('/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc', 0),
    ('/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf', 0),
)


def require_glyphs(font: TTFont, text: str, *, label: str) -> None:
    glyphs = font.face.charToGlyph
    missing = sorted(
        {
            ord(character)
            for character in text
            if not character.isspace() and unicodedata.category(character) != 'Cf' and not glyphs.get(ord(character))
        }
    )
    if missing:
        codes = '、'.join(f'U+{value:04X}' for value in missing[:8])
        raise ValueError(f'{label} 缺少所需中文或标点字形（{codes}），请提供覆盖报告内容的可嵌入字体')


def validated_ttf(
    path: Path, *, name: str, label: str, face_index: int = 0, required_text: str = CJK_REQUIRED_TEXT
) -> TTFont:
    """Always parse the selected file; registration caches must not hide errors."""
    return _read_ttf(path, name=name, label=label, face_index=face_index, required_text=required_text)[0]


def _read_ttf(
    path: Path, *, name: str, label: str, face_index: int = 0, required_text: str = CJK_REQUIRED_TEXT
) -> tuple[TTFont, str]:
    try:
        if not path.is_file() or not 0 < path.stat().st_size <= MAX_FONT_BYTES:
            raise ValueError('missing or oversized font')
        with path.open('rb') as stream:
            content = stream.read(MAX_FONT_BYTES + 1)
        if not 0 < len(content) <= MAX_FONT_BYTES:
            raise ValueError('empty or oversized font')
        # Parse and identify the same byte snapshot if a mounted font changes
        # concurrently with an export.
        font = TTFont(name, BytesIO(content), subfontIndex=face_index)
    except (TTFError, OSError, ValueError, TypeError, KeyError, IndexError, EOFError, struct.error) as exc:
        raise ValueError(f'{label} 字体文件不存在、损坏或不支持嵌入 TrueType，请检查配置') from exc
    require_glyphs(font, required_text, label=label)
    return font, hashlib.sha256(content).hexdigest()[:16]


def register_configured_font(path: str, *, prefix: str, label: str, required_text: str = CJK_REQUIRED_TEXT) -> str:
    """A changed explicit file cannot reuse a previously registered font."""
    selected = Path(path)
    # Validate even when the same name has already been registered. The file
    # may have been removed or replaced since an earlier successful export.
    font, digest = _read_ttf(selected, name=prefix, label=label, required_text=required_text)
    name = f'{prefix}_{digest}'
    if name not in pdfmetrics.getRegisteredFontNames():
        # Give each exact file its own family, avoiding stale global mappings.
        font.fontName = name
        # ReportLab also deduplicates dynamic fonts by their internal face
        # name. Two files with the same name must not alias an old outline.
        font.face.name = name.encode('ascii')
        pdfmetrics.registerFont(font)
        pdfmetrics.registerFontFamily(name, normal=name, bold=name, italic=name, boldItalic=name)
    return name


def validate_runtime_fonts(*, digest_path: str, cjk_path: str = '') -> None:
    """Check production file format and baseline Chinese/punctuation coverage."""
    if not digest_path.strip():
        raise ValueError('PDF_DIGEST_FONT_PATH 必须指向已授权的仿宋字体文件，参见 deploy/fonts/README.md')
    validated_ttf(Path(digest_path), name='PipeSightDigestPreflight', label='PDF_DIGEST_FONT_PATH')
    if cjk_path.strip():
        validated_ttf(Path(cjk_path), name='PipeSightCJKPreflight', label='PDF_CJK_FONT_PATH')
        return
    for filename, face_index in DEFAULT_CJK_CANDIDATES:
        try:
            validated_ttf(Path(filename), name='PipeSightCJKPreflight', label='中文正文', face_index=face_index)
            return
        except ValueError:  # noqa: PERF203 - seven local candidates, only during startup.
            continue
    raise ValueError('缺少可嵌入的中文字体，请配置 PDF_CJK_FONT_PATH 或安装部署文档指定字体')
