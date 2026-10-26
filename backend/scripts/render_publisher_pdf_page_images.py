"""Legacy source-page rendering utility; not used by the text reader."""
from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

from PIL import Image
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / 'backend/data/curated/paper-fulltext-previews.json'
PDFS = ROOT / 'output/pdf/paper-fulltext-20261017'
FILES = {
    '10.3390/coatings14030358': 'coatings-14-00358.pdf',
    '10.6047/j.issn.1000-8241.2024.03.001': 'pipeline-inspection-review-2024.pdf',
    '10.6047/j.issn.1000-8241.2020.11.002': 'pipeline-inspection-management-2020.pdf',
}


def main() -> None:
    records = json.loads(MANIFEST.read_text())['records']
    for doi, filename in FILES.items():
        record = records[doi]
        source = PDFS / filename
        if hashlib.sha256(source.read_bytes()).hexdigest() != record['sha256']:
            raise ValueError('Original PDF checksum mismatch')
        reader = PdfReader(source)
        if len(reader.pages) != record['pages'] or doi not in reader.pages[0].extract_text():
            raise ValueError('Original PDF identity/page count mismatch')
        key = 'paper-' + hashlib.sha256(doi.encode()).hexdigest()[:24]
        directory = ROOT / 'backend/vf_admin/upload_path/publisher_paper_previews' / key
        directory.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        with tempfile.TemporaryDirectory(prefix='pipesight-paper-preview-') as temporary:
            subprocess.run(['pdftoppm', '-scale-to', '1800', '-png', str(source), str(Path(temporary) / 'page')], check=True, capture_output=True)
            images = sorted(Path(temporary).glob('page-*.png'), key=lambda path: int(path.stem.split('-')[-1]))
            if len(images) != record['pages']:
                raise ValueError('Incomplete page rendering')
            for number, image in enumerate(images, 1):
                target = directory / f'page-{number:03}.webp'
                with Image.open(image) as page:
                    page.convert('RGB').save(target, 'WEBP', quality=88, method=4)
                digest.update(target.read_bytes())
        print(json.dumps({'doi': doi, 'asset_key': key, 'pages_sha256': digest.hexdigest(), 'pages': len(images)}), flush=True)


if __name__ == '__main__':
    main()
