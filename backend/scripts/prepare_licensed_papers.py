"""Stage CC BY pipeline papers with verified metadata, JATS and inline assets.

No database writes. Resume from the manifest; reject incomplete source records.
Only Europe PMC's documented open-access APIs are used, without access bypass.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import html
import io
import json
import re
import zipfile
import warnings
from urllib.parse import unquote, urlparse
from datetime import date
from pathlib import Path

import httpx
from lxml import etree
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / '.runtime/licensed-papers-20261014'
ASSETS = ROOT / 'backend/vf_admin/upload_path/licensed_papers'
API = 'https://www.ebi.ac.uk/europepmc/webservices/rest'
QUERY = ('OPEN_ACCESS:Y AND HAS_FT:Y AND FIRST_PDATE:[2015-01-01 TO 2026-10-14] '
         'AND (TITLE:pipeline OR TITLE:pipelines) AND (TITLE:corrosion OR TITLE:inspection '
         'OR TITLE:leak OR TITLE:gas OR TITLE:hydrogen OR TITLE:steel OR TITLE:buried) sort_cited:y')
TOPIC = re.compile(r'corrosion|leak detection|leakage|inspection|hydrogen|pipeline steel|gas pipeline|oil.*pipeline|pipeline.*oil|buried pipeline|subsea|pipeline integrity', re.I)
EXCLUDE = re.compile(r'retract|physician|surgery|academic medicine|racial|gender diversity|volatolomic|bioinformatic|proteomic|metabolomic|clinical|medical education', re.I)
XLINK = '{http://www.w3.org/1999/xlink}href'
CC = re.compile(r'https?://creativecommons\.org/(?:licenses/by/(?:2\.0|3\.0|4\.0)|publicdomain/zero/1\.0)/?$', re.I)


def text(node):
    return ' '.join(''.join(node.itertext()).split()) if node is not None else ''


def eligible_core(record):
    """Exclude non-engineering/retracted records before acquiring assets."""
    flags = json.dumps([record.get(k) for k in ('pubTypeList', 'commentCorrectionList')]).lower()
    return bool(re.fullmatch(r'PMC\d+', record.get('pmcid') or '')
                and record.get('doi') and record.get('license', '').lower() == 'cc by'
                and TOPIC.search(record.get('title', '')) and not EXCLUDE.search(record.get('title', ''))
                and 'retract' not in flags and record.get('isRetracted') not in {'Y', True})


def extract_metadata(raw, core):
    root = etree.fromstring(raw, etree.XMLParser(resolve_entities=False, no_network=True))
    meta = root.find('./front/article-meta')
    if meta is None:
        raise ValueError('missing article metadata')
    license_node = meta.find('./permissions/license')
    urls = [] if license_node is None else [text(e) for e in license_node.iter() if etree.QName(e).localname == 'license_ref']
    if license_node is not None:
        urls += [e.get(XLINK, '') for e in license_node.iter()]
    license_url = next((u.replace('http:', 'https:').rstrip('/') + '/' for u in urls if CC.fullmatch(u)), None)
    if not license_url:
        raise ValueError('no qualifying article-level CC BY/CC0 license')
    doi = next((text(e) for e in meta.findall('article-id') if e.get('pub-id-type') == 'doi'), '')
    pmcid = next((text(e) for e in meta.findall('article-id') if e.get('pub-id-type') in {'pmc', 'pmcid'}), core.get('pmcid', ''))
    if pmcid.isdigit():
        pmcid = 'PMC' + pmcid
    if not re.fullmatch(r'PMC\d+', pmcid) or doi.lower() != core.get('doi', '').lower():
        raise ValueError('source identity mismatch')
    title = text(meta.find('./title-group/article-title'))
    if not TOPIC.search(title) or EXCLUDE.search(title):
        raise ValueError('out of pipeline engineering scope')
    authors = []
    author_affiliation_ids = []
    for e in meta.findall('./contrib-group/contrib'):
        if e.get('contrib-type', e.getparent().get('content-type', 'author')) != 'author':
            continue
        name = e.find('name')
        author = (text(name.find('given-names')) + ' ' + text(name.find('surname'))).strip() if name is not None else text(e.find('collab'))
        if author:
            authors.append(author)
            author_affiliation_ids.append([rid for x in e.findall('xref') if x.get('ref-type') == 'aff' for rid in x.get('rid', '').split()])
    affiliations = [text(e) for e in meta.findall('.//aff') if text(e)]
    affiliation_by_id = {e.get('id'): text(e) for e in meta.findall('.//aff') if e.get('id')}
    author_institutions = [
        ' · '.join(affiliation_by_id[rid] for rid in ids if rid in affiliation_by_id)
        if ids else affiliations[0] if len(affiliations) == 1 else ''
        for ids in author_affiliation_ids
    ]
    publication = None
    dates = meta.findall('pub-date')
    dates.sort(key=lambda d: 0 if d.get('pub-type') == 'epub' or d.get('publication-format') == 'electronic' else 1)
    for e in dates:
        try:
            candidate = date(int(text(e.find('year'))), int(text(e.find('month'))), int(text(e.find('day'))))
            if date(2015, 1, 1) <= candidate <= date(2026, 10, 14):
                publication = candidate
                break
        except (ValueError, TypeError):
            continue
    journal = text(root.find('./front/journal-meta/journal-title-group/journal-title'))
    publisher = text(root.find('./front/journal-meta/publisher/publisher-name'))
    volume, issue = text(meta.find('volume')), text(meta.find('issue'))
    pages = text(meta.find('elocation-id')) or '-'.join(filter(None, [text(meta.find('fpage')), text(meta.find('lpage'))]))
    abstract = ' '.join(text(e) for e in meta.findall('abstract'))
    body = root.find('body')
    references = root.findall('.//ref-list/ref')
    fields = dict(title=title, doi=doi, authors=authors, affiliations=affiliations, publication=publication,
                  journal=journal, publisher=publisher, volume=volume, issue=issue, pages=pages)
    if not all(fields.values()):
        raise ValueError('incomplete fields: ' + ','.join(k for k, v in fields.items() if not v))
    if len(abstract) < 200 or body is None or len(text(body)) < 3000 or not references:
        raise ValueError('incomplete abstract/body/references')
    # Do not redistribute separately credited third-party images without evidence.
    for fig in root.findall('.//fig') + root.findall('.//table-wrap'):
        credit = ' '.join(text(fig.find(tag)) for tag in ('caption', 'attrib', 'permissions', 'table-wrap-foot'))
        if re.search(r'adapted|reproduced|reprinted|permission|copyright|©|modified from|taken from|redrawn', credit, re.I):
            raise ValueError('third-party figure rights require separate verification')
    record = dict(kind='paper', title=title, url=f'https://doi.org/{doi}', doi=doi,
                  source=journal, journal=journal, publisher=publisher, authors=authors,
                  institutions=affiliations, author_institutions=author_institutions,
                  year=publication.year, original_date=publication.isoformat(),
                  volume=volume, issue=issue, pages=pages, summary=abstract, summary_kind='original_abstract',
                  license=license_url, license_statement=text(license_node),
                  copyright_notice=text(meta.find('permissions')),
                  verification_url=f'{API}/{pmcid}/fullTextXML',
                  full_text_url=f'https://europepmc.org/articles/{pmcid}',
                  citation_count=int(core.get('citedByCount') or 0),
                  tags=[text(e) for e in meta.findall('.//kwd') if text(e)][:20] or ['管道工程', '开放许可全文'],
                  pmcid=pmcid, body_characters=len(text(body)), references_count=len(references),
                  original_xml_sha256=hashlib.sha256(raw).hexdigest())
    return root, record


def image_map(raw):
    images = {}
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        if sum(i.file_size for i in archive.infolist()) > 100 * 1024 * 1024:
            raise ValueError('oversize asset archive')
        for info in archive.infolist():
            name = Path(info.filename).name
            ext = Path(name).suffix.lower()
            mime = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png', '.gif': 'image/gif', '.webp': 'image/webp'}.get(ext)
            if mime and info.file_size < 15 * 1024 * 1024:
                content = archive.read(info)
                with warnings.catch_warnings():
                    warnings.simplefilter('error', Image.DecompressionBombWarning)
                    with Image.open(io.BytesIO(content)) as image:
                        image.verify()
                images[name] = 'data:' + mime + ';base64,' + base64.b64encode(content).decode()
    return images


def render_article(root, record, images):
    graphic_count = 0
    # Verify that figure bytes match checksums supplied by the original OA XML.
    for graphic in root.findall('.//graphic') + root.findall('.//inline-graphic'):
        name = Path(graphic.get(XLINK, '')).name
        source = images.get(name)
        if not source:
            raise ValueError('missing inline/figure asset: ' + name)
        checksums = graphic.xpath('processing-instruction("image-md5")')
        expected = (checksums[0].text or '').strip() if checksums else ''
        if re.fullmatch(r'[0-9a-fA-F]{32}', expected):
            actual = hashlib.md5(base64.b64decode(source.split(',', 1)[1])).hexdigest()
            if actual.lower() != expected.lower():
                raise ValueError('source figure checksum mismatch: ' + name)
    mapping = {'sec': 'section', 'title': 'h2', 'p': 'p', 'bold': 'strong', 'italic': 'em',
               'sub': 'sub', 'sup': 'sup', 'list': 'ul', 'list-item': 'li', 'fig': 'figure',
               'caption': 'figcaption', 'table-wrap': 'div', 'table': 'table', 'thead': 'thead',
               'tbody': 'tbody', 'tfoot': 'tfoot', 'tr': 'tr', 'td': 'td', 'th': 'th',
               'ref': 'p', 'ref-list': 'section', 'disp-quote': 'blockquote', 'label': 'strong'}
    math_tags = {'math', 'mrow', 'mi', 'mn', 'mo', 'msub', 'msup', 'msubsup', 'mfrac', 'msqrt',
                 'mroot', 'mfenced', 'mtext', 'mtable', 'mtr', 'mtd', 'mover', 'munder', 'munderover', 'mspace',
                 'ms', 'mstyle', 'mpadded', 'mphantom', 'mmultiscripts', 'mprescripts', 'none', 'merror', 'menclose'}
    math_attributes = {'open', 'close', 'separators', 'mathvariant', 'mathsize', 'display', 'displaystyle',
                       'accent', 'accentunder', 'linethickness', 'scriptlevel', 'columnalign', 'rowalign',
                       'columnspacing', 'rowspacing', 'columnspan', 'rowspan', 'lspace', 'rspace', 'stretchy',
                       'fence', 'separator', 'symmetric', 'maxsize', 'minsize', 'width', 'height', 'depth', 'notation'}
    def render(e):
        nonlocal graphic_count
        if not isinstance(e.tag, str):
            return ''
        tag = etree.QName(e).localname
        if tag in {'graphic', 'inline-graphic'}:
            graphic_count += 1
            name = Path(e.get(XLINK, '')).name
            src = images.get(name)
            if not src:
                raise ValueError('missing inline/figure asset: ' + name)
            return '<img alt="' + html.escape(name, quote=True) + '" src="' + src + '">'
        if tag == 'alternatives':
            preferred = next((c for c in e if isinstance(c.tag, str) and etree.QName(c).localname == 'math'), None)
            return render(preferred) if preferred is not None else ''.join(render(c) + html.escape(c.tail or '') for c in e)
        if tag == 'mfenced':
            # Explicit Core MathML operators preserve absolute-value/norm brackets
            # in browsers where the legacy mfenced element is unsupported.
            opening, closing = e.get('open', '('), e.get('close', ')')
            separators = ''.join(e.get('separators', ',').split())
            children = [c for c in e if isinstance(c.tag, str)]
            terms = []
            for index, child in enumerate(children):
                if index and separators:
                    terms.append('<mo>' + html.escape(separators[min(index - 1, len(separators) - 1)]) + '</mo>')
                terms.append(render(child))
            return '<mrow><mo>' + html.escape(opening) + '</mo>' + ''.join(terms) + '<mo>' + html.escape(closing) + '</mo></mrow>'
        if tag == 'semantics':
            presentation = [c for c in e if isinstance(c.tag, str) and etree.QName(c).localname not in {'annotation', 'annotation-xml'}]
            if presentation:
                return ''.join(render(c) for c in presentation)
        content = html.escape(e.text or '') + ''.join(render(c) + html.escape(c.tail or '') for c in e)
        if tag == 'ext-link':
            url = e.get(XLINK, '')
            if url.startswith('https://'):
                return '<a target="_blank" rel="noopener noreferrer" href="' + html.escape(url, quote=True) + '">' + content + '</a>'
            return content
        list_type = e.get('list-type', '')
        out = 'ol' if tag == 'list' and list_type in {'order', 'alpha-lower', 'alpha-upper', 'roman-lower', 'roman-upper'} else tag if tag in math_tags else mapping.get(tag)
        if not out:
            return content
        attrs = ''
        if out == 'ol':
            attrs += ' type="' + {'alpha-lower': 'a', 'alpha-upper': 'A', 'roman-lower': 'i', 'roman-upper': 'I'}.get(list_type, '1') + '"'
        if tag in math_tags:
            for key, value in e.attrib.items():
                if key in math_attributes and len(value) <= 160:
                    attrs += ' ' + key + '="' + html.escape(value, quote=True) + '"'
        for attr in ('colspan', 'rowspan') if out in {'td', 'th'} else ():
            if re.fullmatch(r'\d{1,2}', e.get(attr, '')):
                attrs += ' ' + attr + '="' + e.get(attr) + '"'
        return '<' + out + attrs + '>' + content + '</' + out + '>'
    # JATS may put every figure/table in a root-level floats-group, not body.
    # Preserve appendices, references, acknowledgments and floats as well.
    article_content = ''.join(render(e) for e in root if isinstance(e.tag, str) and etree.QName(e).localname != 'front')
    abstracts = ''.join(render(e) for e in root.findall('./front/article-meta/abstract'))
    license_link = html.escape(record['license'], quote=True)
    source_link = html.escape(record['full_text_url'], quote=True)
    header = ('<h1>' + html.escape(record['title']) + '</h1><p>' + html.escape(' · '.join(record['authors']))
              + '</p><p>' + html.escape(f"{record['journal']} {record['volume']}({record['issue']}): {record['pages']} · {record['original_date']} · DOI {record['doi']}")
              + '</p><p><a href="' + source_link + '" target="_blank" rel="noopener noreferrer">原始来源</a> · <a href="' + license_link
              + '" target="_blank" rel="noopener noreferrer">开放许可</a></p><p>' + html.escape(record.get('copyright_notice', record['license_statement'])) + '</p>'
              + '<p>' + html.escape(' · '.join(record['institutions'])) + '</p>'
              + '<p>This reading copy was typeset from the publisher-deposited JATS XML; original attribution is retained and layout may differ.</p>'
              + '<h2>Abstract</h2>' + abstracts)
    document = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
                '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; img-src data:; style-src \'unsafe-inline\'; base-uri \'none\'; form-action \'none\'">'
                '<style>body{font:16px/1.85 system-ui,sans-serif;color:#17334d;margin:24px;overflow-wrap:anywhere}h1{font-size:24px}h2{font-size:20px;margin-top:28px}img{max-width:100%;height:auto}table{border-collapse:collapse;display:block;overflow:auto}td,th{border:1px solid #cddde7;padding:8px}figure{margin:24px 0}a{color:#005487}math{max-width:100%}</style></head><body>'
                + header + article_content + '</body></html>')
    if len(document.encode()) > 30 * 1024 * 1024:
        raise ValueError('oversize reader document')
    return document, graphic_count


async def fetch(client, url, *, timeout_seconds=35, **kwargs):
    async def request():
        response = await client.get(url, **kwargs)
        response.raise_for_status()
        return response.content
    return await asyncio.wait_for(request(), timeout=timeout_seconds)


async def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    ASSETS.mkdir(parents=True, exist_ok=True)
    if (OUTPUT / 'import-receipt.json').exists():
        raise RuntimeError('Imported assets are immutable; prepare a new versioned batch instead')
    manifest_path = OUTPUT / 'manifest.json'
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else dict(
        batch='licensed-fulltext-20261014', purpose='用户授权：100条管网工程合法全文及完整元数据；允许调整类别比例', records=[], rejected=[])
    manifest['expected_count'] = 100
    # Revalidate and re-render resumable output, including renderer fixes.
    refreshed = []
    for old in manifest['records']:
        directory = ASSETS / old['pmcid']
        try:
            root, record = extract_metadata((directory / 'source.xml').read_bytes(), {'doi': old['doi'], 'pmcid': old['pmcid'], 'citedByCount': old.get('citation_count', 0)})
            images = image_map((directory / 'source-assets.zip').read_bytes()) if (directory / 'source-assets.zip').is_file() else {}
            document, graphics_count = render_article(root, record, images)
            (directory / 'article.html').write_text(document)
            record['licensed_full_text'] = dict(old['licensed_full_text'], sha256=hashlib.sha256(document.encode()).hexdigest(), graphics_count=graphics_count)
            refreshed.append(record)
        except (ValueError, OSError) as error:
            print(json.dumps({'excluded_during_revalidation': old['pmcid'], 'reason': str(error)}), flush=True)
    manifest['records'] = refreshed
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    prior = {r['pmcid'] for r in manifest['records']}
    manifest['rejected'] = []
    existing_dois = {r.get('doi', '').lower() for r in json.loads((ROOT / 'backend/data/curated/homepage-real-content-20261014.json').read_text())['records']}
    async with httpx.AsyncClient(timeout=60, limits=httpx.Limits(max_connections=3), headers={'User-Agent': 'PipeSight-Curated-Research/1.0'}) as client:
        raw = await fetch(client, API + '/search', params={'query': QUERY, 'format': 'json', 'pageSize': 1000, 'resultType': 'core'})
        metadata = json.loads(raw)
        (OUTPUT / 'search-response.json').write_bytes(raw)
        candidates = [r for r in metadata['resultList']['result'] if eligible_core(r) and r.get('pmcid') not in prior and r.get('doi', '').lower() not in existing_dois]
        print(json.dumps({'candidates': len(candidates), 'resumed': len(manifest['records'])}), flush=True)
        async def prepare(core):
            pmcid = core['pmcid']
            try:
                directory = ASSETS / pmcid
                cache = directory / 'source.xml'
                raw = cache.read_bytes() if cache.is_file() else await fetch(client, f'{API}/{pmcid}/fullTextXML')
                root, record = extract_metadata(raw, core)
                directory.mkdir(exist_ok=True)
                (directory / 'source.xml').write_bytes(raw)
                graphics = root.findall('.//graphic') + root.findall('.//inline-graphic')
                images = {}
                if graphics:
                    cached_archive = directory / 'source-assets.zip'
                    if cached_archive.is_file():
                        archive = cached_archive.read_bytes()
                    else:
                        # Follow only figure URLs actually present in the licensed
                        # article's public PMC page; never guess/bypass protected URLs.
                        urls = set()
                        # Public JATS supplied by the OA API explicitly embeds CDN
                        # asset URNs. Resolve only those supplied identifiers.
                        for pi in root.xpath('//processing-instruction("image-cloudpmc-urn")'):
                            value = (pi.text or '').strip()
                            prefix = 'urn:cdn:blobs/'
                            if value.startswith(prefix) and '..' not in value:
                                urls.add('https://cdn.ncbi.nlm.nih.gov/pmc/blobs/' + value[len(prefix):])
                        if not urls:
                            source_html = await fetch(client, f'https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/')
                            markup = source_html.decode('utf-8')
                            if 'reCAPTCHA' in markup or 'Checking your browser' in markup:
                                raise ValueError('public source requires browser verification; no bypass attempted')
                            (directory / 'source-page.html').write_bytes(source_html)
                            urls = set(html.unescape(u) for u in re.findall(r'https://cdn\.ncbi\.nlm\.nih\.gov/pmc/blobs/[^\s"<>]+', markup))
                        buffer = io.BytesIO()
                        with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED) as bundle:
                            required = {Path(e.get(XLINK, '')).name for e in graphics}
                            for name in required:
                                matching = [u for u in urls if unquote(Path(urlparse(u).path).name).lower() == name.lower()]
                                if not matching:
                                    matching = [u for u in urls if Path(unquote(urlparse(u).path)).stem.lower() == Path(name).stem.lower()]
                                if not matching:
                                    raise ValueError('figure not available from public source: ' + name)
                                image_url = sorted(matching)[0]
                                content = await fetch(client, image_url)
                                extension = Path(urlparse(image_url).path).suffix
                                bundle.writestr(name if Path(name).suffix else name + extension, content)
                        archive = buffer.getvalue()
                    images = image_map(archive)
                    for name in {Path(e.get(XLINK, '')).name for e in graphics}:
                        if name not in images:
                            match = next((v for k, v in images.items() if k.lower() == name.lower() or Path(k).stem.lower() == Path(name).stem.lower()), None)
                            if match:
                                images[name] = match
                    (directory / 'source-assets.zip').write_bytes(archive)
                document, graphic_count = render_article(root, record, images)
                (directory / 'article.html').write_text(document)
                record['licensed_full_text'] = dict(asset_key=pmcid, format='html', language='en',
                    sha256=hashlib.sha256(document.encode()).hexdigest(), license_url=record['license'],
                    source_url=record['full_text_url'], graphics_count=graphic_count,
                    original_xml_sha256=record['original_xml_sha256'])
                return record, None
            except Exception as error:
                return None, dict(pmcid=pmcid, title=core.get('title'), reason=type(error).__name__ + ': ' + str(error)[:250])
        queue = asyncio.Queue()
        for candidate in candidates:
            queue.put_nowait(candidate)
        async def worker():
            while len(manifest['records']) < 100:
                try:
                    core = queue.get_nowait()
                except asyncio.QueueEmpty:
                    return
                record, rejected = await prepare(core)
                if record and len(manifest['records']) < 100:
                    manifest['records'].append(record)
                    print(json.dumps({'accepted': len(manifest['records']), 'pmcid': record['pmcid'], 'title': record['title'], 'graphics': record['licensed_full_text']['graphics_count']}, ensure_ascii=False), flush=True)
                elif rejected:
                    manifest['rejected'].append(rejected)
                    print(json.dumps({'rejected': rejected['pmcid'], 'reason': rejected['reason'][:140]}), flush=True)
                manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
                await asyncio.sleep(.35)
        await asyncio.gather(*(worker() for _ in range(3)))
    print(json.dumps({'accepted': len(manifest['records']), 'rejected': len(manifest['rejected']), 'manifest': str(manifest_path)}), flush=True)


if __name__ == '__main__':
    asyncio.run(main())
