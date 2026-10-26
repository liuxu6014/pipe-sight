"""Reflow three SHA-256-bound PDFs as selectable text plus cropped diagrams.

Offline only: PyMuPDF + Pillow. The server needs neither dependency to read HTML.
Layout overrides apply only to the exact verified source documents, never arbitrary PDFs.
"""

# Coordinates and typography thresholds below are measurements of the hash-bound PDFs.
# ruff: noqa: PLR2004
from __future__ import annotations

import base64
import hashlib
import io
import json
import re
import unicodedata
from html import escape
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / 'backend/data/curated/paper-fulltext-previews.json'
PDFS = ROOT / 'output/pdf/paper-fulltext-20261017'
FILES = {
    '10.3390/coatings14030358': 'coatings-14-00358.pdf',
    '10.6047/j.issn.1000-8241.2024.03.001': 'pipeline-inspection-review-2024.pdf',
    '10.6047/j.issn.1000-8241.2020.11.002': 'pipeline-inspection-management-2020.pdf',
}
# Only complex diagrams/tables retain their source appearance, not the body text.
REGIONS = {
    'coatings-14-00358.pdf': {
        11: [(34, 288, 564, 750, 'Table 1', False)],
        12: [
            (298, 237, 564, 268, '公式 1', False),
            (308, 365, 564, 400, '公式 2', False),
            (300, 451, 564, 482, '公式 3', False),
            (298, 584, 564, 617, '公式 4', False),
        ],
        13: [(34, 187, 565, 543, 'Table 2', False)],
    },
    'pipeline-inspection-review-2024.pdf': {
        2: [(89, 574, 506, 780, '图 1 · 内检测技术分类', False)],
        3: [(309, 528, 542, 780, '图 2 · 超声检测原理', False)],
        4: [(60, 441, 290, 602, '图 3 · EMAT 工作原理', False), (308, 80, 540, 234, '图 4 · 涡流检测原理', False)],
        5: [(52, 80, 544, 780, '表 1 · 漏磁内检测技术指标', True)],
        6: [(52, 80, 544, 334, '表 2 · 超声内检测指标', False), (52, 340, 544, 535, '表 3 · 涡流内检测指标', False)],
        8: [(52, 455, 544, 683, '表 4 · 缺陷识别方法对比', False)],
        9: [(52, 80, 544, 364, '表 5 · 缺陷分类方法对比', False)],
    },
}


def reading_order(rows: list[dict], chinese: bool) -> list[dict]:
    """Read each column downwards; spanning text/figures create ordered bands."""
    if not chinese:
        return sorted(rows, key=lambda row: (row['bbox'][1], row['bbox'][0]))
    full = sorted([row for row in rows if row['bbox'][0] < 298 < row['bbox'][2]], key=lambda row: row['bbox'][1])
    pending = [row for row in rows if row not in full]
    result = []
    for boundary in full:
        band = [row for row in pending if row['bbox'][1] < boundary['bbox'][1] - 3]
        result.extend(sorted(band, key=lambda row: (row['bbox'][0] >= 298, row['bbox'][1], row['bbox'][0])))
        pending = [row for row in pending if row not in band]
        result.append(boundary)
    return result + sorted(pending, key=lambda row: (row['bbox'][0] >= 298, row['bbox'][1], row['bbox'][0]))


def join_lines(lines: list[str]) -> str:
    text = ''
    for original_line in lines:
        line = unicodedata.normalize('NFC', original_line).replace('\u00ad', '').strip()
        for ligature, letters in {'ﬁ': 'fi', 'ﬂ': 'fl', 'ﬀ': 'ff', 'ﬃ': 'ffi', 'ﬄ': 'ffl'}.items():
            line = line.replace(ligature, letters)
        if not line:
            continue
        if text.endswith('-') and line[0].islower():
            # Preserve technical compound-word hyphens, remove only word-wrap splits.
            compound = re.search(
                r'\b(?:ultrasonic|guided|non|long|high|low|time|frequency|shear|point|on|short|real|multi|data|fiber|cross|machine|surface)-$',
                text,
                re.I,
            )
            text = (text if compound else text[:-1]) + line
        elif text and re.search(r'[A-Za-z0-9,.;:)]$', text) and re.match(r'[A-Za-z0-9(]', line):
            text += ' ' + line
        else:
            text += line
    return re.sub(r'(?<=[\u4e00-\u9fff]) +(?=[\u4e00-\u9fff])', '', text)


def render_text(rows: list[dict], chinese: bool) -> str:
    result, paragraph = [], []
    previous = None

    def flush() -> None:
        if paragraph:
            result.append('<p>' + escape(join_lines(paragraph)) + '</p>')
            paragraph.clear()

    for row in rows:
        if 'html' in row:
            flush()
            result.append(row['html'])
            previous = None
            continue
        text = row['text'].strip()
        if not text:
            continue
        x, top, _right, _bottom = row['bbox']
        new_paragraph = row.get('reference', False) or (
            previous
            and (
                row.get('block') != previous.get('block')
                if not chinese
                else (
                    top < previous['bbox'][1] - 3
                    or top - previous['bbox'][3] > 12
                    or (75 <= x <= 82)
                    or (325 <= x <= 332)
                    or re.match(r'^[（(]\d+[）)]', text)
                )
            )
        )
        if row.get('heading', False):
            flush()
            result.append('<h2>' + escape(text) + '</h2>')
        else:
            if new_paragraph:
                flush()
            paragraph.append(text)
        previous = row
    flush()
    return ''.join(result)


def extract_page(page: Any, number: int, filename: str) -> tuple[str, dict]:  # noqa: PLR0912, PLR0915 -- fixed-PDF layout branches
    import pymupdf  # noqa: PLC0415 -- optional offline dependency, not a server dependency
    from PIL import Image  # noqa: PLC0415

    chinese = not filename.startswith('coatings')
    blocks = page.get_text('dict')['blocks']
    regions = list(REGIONS.get(filename, {}).get(number, []))
    for block in blocks:
        if block['type'] != 1:
            continue
        x0, y0, x1, y1 = block['bbox']
        # Logos, QR codes and the final Chinese-page advertisement are not figures.
        if x1 - x0 > 60 and y1 - y0 > 25 and y0 > 75 and y1 < 785 and not (chinese and number == 9 and x1 - x0 > 500):
            regions.append((x0, y0, x1, y1, '原文图示', False))
    rows = []
    start = 80
    if number == 1:
        starts = [
            line['bbox'][1]
            for b in blocks
            if b['type'] == 0
            for line in b['lines']
            if ''.join(s['text'] for s in line['spans']).startswith(('摘要', 'Abstract:'))
        ]
        start = min(starts) - 1
    for bid, block in enumerate(blocks):
        if block['type'] != 0:
            continue
        for line in block['lines']:
            rect = pymupdf.Rect(line['bbox'])
            if rect.y0 < start or rect.y1 > 785 or line['dir'] != (1.0, 0.0):
                continue
            if not chinese and number == 1 and rect.x0 < 160:
                continue
            if any(rect.intersects(pymupdf.Rect(r[:4])) for r in regions):
                continue
            spans = line['spans']
            text = ''.join(span['text'] for span in spans).strip()
            if not text:
                continue
            size = max(span['size'] for span in spans)
            heading = (
                bool(re.match(r'^(?:\d+(?:\.\d+){0,3}[.\s\u3000]|References$|参考文献)', text)) and len(text) < 140
            )
            heading = heading and size >= 9.8 and not re.match(r'^\d+\.\s+[A-Z][a-z]+,', text)
            rows.append({'text': text, 'bbox': tuple(rect), 'size': size, 'heading': heading, 'block': bid})
    # Superscripts can split a Chinese baseline into several PDF text blocks.
    merged = []
    for row in sorted(rows, key=lambda r: (r['bbox'][0], r['bbox'][1])):
        candidate = next(
            (
                other
                for other in reversed(merged)
                if min(other['bbox'][3], row['bbox'][3]) - max(other['bbox'][1], row['bbox'][1]) > 3
                and -12 <= row['bbox'][0] - other['bbox'][2] < (8 if chinese else 24)
            ),
            None,
        )
        if candidate is not None:
            candidate['text'] += row['text']
            candidate['bbox'] = (
                candidate['bbox'][0],
                min(candidate['bbox'][1], row['bbox'][1]),
                row['bbox'][2],
                max(candidate['bbox'][3], row['bbox'][3]),
            )
        else:
            merged.append(row)
    if not chinese:
        for row in merged:
            row['reference'] = row['bbox'][0] < 70 and bool(re.match(r'^\d+\.\s*\S', row['text']))
    text_characters = sum(len(row['text']) for row in merged)
    for x0, y0, x1, y1, label, rotated in regions:
        pix = page.get_pixmap(matrix=pymupdf.Matrix(2.5, 2.5), clip=pymupdf.Rect(x0, y0, x1, y1), alpha=False)
        image = Image.open(io.BytesIO(pix.tobytes('png')))
        if rotated:
            image = image.rotate(-90, expand=True)
        output = io.BytesIO()
        image.save(output, 'WEBP', quality=88)
        encoded = base64.b64encode(output.getvalue()).decode('ascii')
        merged.append(
            {
                'bbox': (x0, y0, x1, y1),
                'html': f'<figure><img loading="lazy" src="data:image/webp;base64,{encoded}" alt="{escape(label)}"><figcaption>{escape(label)} · 原文第 {number} 页</figcaption></figure>',
            }
        )
    body = render_text(reading_order(merged, chinese), chinese)
    return f'<section data-source-page="{number}">{body}</section>', {
        'page': number,
        'text_characters': text_characters,
        'figures': len(regions),
    }


def main() -> None:
    import pymupdf  # noqa: PLC0415 -- optional offline dependency

    manifest = json.loads(MANIFEST.read_text())
    for doi, filename in FILES.items():
        record = manifest['records'][doi]
        source = PDFS / filename
        if hashlib.sha256(source.read_bytes()).hexdigest() != record['sha256']:
            raise ValueError('Original PDF checksum mismatch')
        document = pymupdf.open(source)
        if len(document) != record['pages'] or doi not in document[0].get_text():
            raise ValueError('Original PDF identity/page count mismatch')
        sections, audit = [], []
        for number, page in enumerate(document, 1):
            html, stats = extract_page(page, number, filename)
            if stats['text_characters'] < 20 and not stats['figures']:
                raise ValueError(f'Empty extraction on page {number}')
            sections.append(html)
            audit.append(stats)
        language = 'en' if filename.startswith('coatings') else 'zh-CN'
        styles = 'body{margin:0;padding:12px 20px 32px;color:#24364b;background:#fff;font:16px/1.9 system-ui,-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;overflow-wrap:anywhere}article{max-width:860px;margin:auto}p{margin:0 0 16px;text-align:justify}h2{font-size:19px;line-height:1.55;margin:26px 0 12px;color:#143b61}figure{margin:24px 0;text-align:center}img{max-width:100%;height:auto}figcaption,footer{font-size:12px;color:#718096}footer{margin-top:28px;border-top:1px solid #e5ebf1;padding-top:12px}@media(max-width:600px){body{padding:8px;font-size:15px}h2{font-size:17px}}'
        html = (
            '<html lang="'
            + language
            + '"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>'
            + styles
            + '</style></head><body><article>'
            + ''.join(sections)
            + '<footer>文字提取自期刊原文 · DOI '
            + escape(doi)
            + '</footer></article></body></html>'
        )
        raw = html.encode()
        directory = ROOT / 'backend/vf_admin/upload_path/publisher_paper_previews' / record['asset_key']
        directory.mkdir(parents=True, exist_ok=True)
        (directory / 'article.html').write_bytes(raw)
        (directory / 'extraction-audit.json').write_text(
            json.dumps({'doi': doi, 'source_sha256': record['sha256'], 'pages': audit}, ensure_ascii=False, indent=2)
        )
        record['text_sha256'] = hashlib.sha256(raw).hexdigest()
        record['text_characters'] = sum(row['text_characters'] for row in audit)
        record['reader_kind'] = 'extracted_text'
        print(
            json.dumps(
                {
                    'doi': doi,
                    'pages': len(audit),
                    'text_characters': record['text_characters'],
                    'figures': sum(row['figures'] for row in audit),
                    'html_bytes': len(raw),
                }
            ),
            flush=True,
        )
    manifest['purpose'] = (
        '用户请求的三篇论文文字阅读版；从校验过的官方PDF提取正文，复杂图表保留局部原图；不变更转载或AI使用权限，不修改论文记录。'
    )
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    main()
