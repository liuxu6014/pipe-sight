#!/usr/bin/env python3
"""Exercise real ClamD and document exports in an isolated Linux container.

Uses a prebuilt local image and an existing private scanner network. No application
configuration, database, model service or user document is read. The authorized
FangSong font is mounted read-only, never copied to an image or the repository.
"""

from __future__ import annotations

import argparse
import ast
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROBE = r"""
import json, re, tempfile
from io import BytesIO
from itertools import pairwise
from pathlib import Path
from types import SimpleNamespace

from docx import Document
from docx.shared import Pt
from pypdf import PdfReader

from app.entrypoints.file_scan import scan_file
from app.research.services.exporters import build_docx, build_pdf

out = Path('/audit-out')
out.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory() as temp:
    path = Path(temp) / 'synthetic.txt'
    path.write_text('Synthetic clean scanning acceptance only.')
    ping = scan_file(None, host='pipesight-clamav', port=3310)
    clean = scan_file(path, host='pipesight-clamav', port=3310)
    path.write_bytes(b'X5O!P%@AP[4\\PZX54(P^)7CC)7}$' + b'EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*')
    infected = scan_file(path, host='pipesight-clamav', port=3310)
    offline = scan_file(path, host='pipesight-clamav', port=1, timeout=1)
    assert (ping[0], clean[0], infected[0], offline[0]) == (0, 0, 1, 2), (ping, clean, infected, offline)

def report(kind='weekly', filler=0, events=1):
    blocks = ['**跨页校验**']
    for event in range(1, events + 1):
        blocks.extend([
            f'### {event}. 第{event}项需与正文保持相邻的事件标题',
            '正文用于覆盖不同页尾位置。' * filler,
            '发布时间：2026-10-21',
            '行业洞察：' + '结论需要运行数据验证，不能由报道直接推断。' * 6,
            '数据源：',
            *[f'[{i}] [第{i}条来源标题：' + '管道运行与试验记录' * 6 + f'](https://example.org/source/{i})' for i in range(1, 5)],
        ])
    return SimpleNamespace(
        title='科技情报' + ('周报' if kind == 'weekly' else '月报'),
        report_type=kind,
        content='\n\n'.join(blocks),
        metadata={'period': ['2026-10-19', '2026-10-25'] if kind == 'weekly' else ['2026-10-01', '2026-10-31']},
        citations=[],
    )

boundaries = []
for kind in ('weekly', 'monthly'):
    for filler in (15, 20, 25, 30, 35, 40, 45, 50):
        pdf = PdfReader(BytesIO(build_pdf(report(kind, filler), is_draft=False)[2]))
        texts = [re.sub(r'\s+', '', page.extract_text()) for page in pdf.pages]
        targets = ['发布时间：2026-10-21', '行业洞察：', '数据源：'] + [f'[{i}]第{i}条来源标题：' for i in range(1, 5)]
        locations = [next(index for index, text in enumerate(texts) if target in text) for target in targets]
        assert len(set(locations)) == 1, (kind, filler, locations)
        links = [annotation.get_object()['/A']['/URI'] for page in pdf.pages for annotation in page.get('/Annots', [])]
        assert set(links) == {f'https://example.org/source/{i}' for i in range(1, 5)}
        boundaries.append({'kind': kind, 'filler': filler, 'metadataPage': locations[0] + 1, 'passed': True})

__HEADING_BEHAVIOR_PROBES__
test_long_body_uses_remaining_page_below_previous_metadata()
for mode in ('long', 'multiple', 'short'):
    test_wrapped_heading_stays_with_initial_body_lines(mode)
test_heading_without_summary_stays_with_following_metadata()
for kind in ('weekly', 'monthly'):
    test_pdf_reference_gutters_and_vertical_group_geometry(kind)

outputs = []
for kind in ('weekly', 'monthly'):
    value = report(kind, 35, events=3)
    pdf_bytes = build_pdf(value, is_draft=False)[2]
    docx_bytes = build_docx(value, is_draft=False)[2]
    pdf_path, docx_path = out / f'{kind}.pdf', out / f'{kind}.docx'
    pdf_path.write_bytes(pdf_bytes)
    docx_path.write_bytes(docx_bytes)
    pdf = PdfReader(BytesIO(pdf_bytes))
    assert len(pdf.pages) > 1
    embedded = {}
    for page in pdf.pages:
        for font in page['/Resources']['/Font'].get_object().values():
            font = font.get_object()
            name = str(font.get('/BaseFont', ''))
            if 'Helvetica' in name:
                continue
            descriptor = font.get('/FontDescriptor')
            assert descriptor is not None, name
            stream = descriptor.get_object().get('/FontFile2')
            assert stream is not None and len(stream.get_object().get_data()) > 0, name
            embedded[name] = len(stream.get_object().get_data())
    assert embedded
    document = Document(BytesIO(docx_bytes))
    for paragraph in document.paragraphs:
        if paragraph.text.startswith(('一、', '1.', '2.', '3.', '发布时间：', '行业洞察：', '数据源：', '[')):
            assert paragraph.paragraph_format.keep_together, paragraph.text
        if paragraph.text.startswith(('发布时间：', '行业洞察：', '数据源：', '[1]', '[2]', '[3]')):
            assert paragraph.paragraph_format.keep_with_next, paragraph.text
    assert document.paragraphs[-1].paragraph_format.keep_with_next is False
    body = next(p for p in document.paragraphs if p.text.startswith('正文用于'))
    assert body.paragraph_format.line_spacing == Pt(18)
    assert body.paragraph_format.first_line_indent == Pt(32)
    outputs.append({'kind': kind, 'pdfPages': len(pdf.pages), 'pdfBytes': len(pdf_bytes), 'docxBytes': len(docx_bytes), 'embeddedFonts': embedded, 'wordLineSpacingPt': 18, 'wordFirstLineIndentPt': 32})

evidence = {'scanner': {'ping': ping[0], 'clean': clean[0], 'eicar': infected[0], 'offline': offline[0]}, 'pageBoundaryCases': boundaries, 'headingBehaviorCases': 5, 'referenceGeometryCases': 2, 'outputs': outputs, 'sourceOverlay': True, 'paidCalls': 0, 'applicationDatabaseAccess': False}
(out / 'evidence.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2))
print(json.dumps(evidence, ensure_ascii=False))
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="pipesight-audit-repair:20261120")
    parser.add_argument("--network", default="pipesight-repair-scan-20261120")
    parser.add_argument("--font", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "output/full-system-audit-20261120/linux-export",
    )
    args = parser.parse_args()
    if not args.font.is_file():
        parser.error("--font must be an authorized local TrueType file")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    # Reuse the same real PDF behavior assertions without adding pytest to the
    # production image or copying compiled host dependencies into Linux.
    functions = []
    for filename, names in [
        ("test_digest_document.py", {"_pagination_report"}),
        (
            "test_digest_layout_parity.py",
            {
                "_page_texts",
                "test_long_body_uses_remaining_page_below_previous_metadata",
                "test_wrapped_heading_stays_with_initial_body_lines",
                "test_heading_without_summary_stays_with_following_metadata",
                "test_pdf_reference_gutters_and_vertical_group_geometry",
            },
        ),
    ]:
        module = ast.parse((ROOT / "backend/tests" / filename).read_text())
        selected = [
            node
            for node in module.body
            if isinstance(node, ast.FunctionDef) and node.name in names
        ]
        if {node.name for node in selected} != names:
            raise RuntimeError(f"Missing Linux acceptance probes in {filename}")
        for node in selected:
            node.decorator_list = []
            functions.append(ast.unparse(node))
    probe = PROBE.replace("__HEADING_BEHAVIOR_PROBES__", "\n\n".join(functions))
    with tempfile.TemporaryDirectory(prefix="pipesight-linux-export-") as temp:
        script = Path(temp) / "probe.py"
        script.write_text(probe)
        command = [
            "docker",
            "run",
            "--rm",
            "--network",
            args.network,
            "--mount",
            f"type=bind,source={ROOT / 'backend/src'},target=/app/src,readonly",
            "--mount",
            f"type=bind,source={script},target=/audit/probe.py,readonly",
            "--mount",
            f"type=bind,source={args.font.resolve()},target=/audit-font/FangSong_GB2312.ttf,readonly",
            "--mount",
            f"type=bind,source={output},target=/audit-out",
            "-e",
            "PYTHONPATH=/app/src:/app",
            "-e",
            "PDF_DIGEST_FONT_PATH=/audit-font/FangSong_GB2312.ttf",
            "--entrypoint",
            "python",
            args.image,
            "/audit/probe.py",
        ]
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=180, check=False
        )
        if result.returncode:
            raise RuntimeError(result.stderr or result.stdout)
        print(result.stdout)


if __name__ == "__main__":
    main()
