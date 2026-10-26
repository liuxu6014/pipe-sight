"""Complete only the six existing user-authorized articles; no new records.

Prepare reads original sources and stores text/image assets. Apply requires a
fresh verified PostgreSQL archive and a six-row, optimistic-lock transaction.
No credentials or source bodies are printed.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

import psycopg2
from psycopg2.extras import Json, RealDictCursor
import requests
from lxml import html
from PIL import Image

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
STAGE = ROOT / '.runtime/authorized-articles-20261014'
ASSETS = BACKEND / 'vf_admin/upload_path/authorized_articles'
MANIFEST = BACKEND / 'data/curated/homepage-real-content-20261014.json'
AUTHORIZATION = '用户于2026-10-14明确确认现有六篇均获授权，允许原站采集并在系统内展示全文'
HOSTS = {'www.pipechina.com.cn', 'www.hoptecchina.com'}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def extract_blocks(node):
    blocks, buffer = [], []
    def flush():
        text = re.sub(r'\s+', ' ', ''.join(buffer)).strip()
        buffer.clear()
        if text:
            blocks.append({'type': 'paragraph', 'text': text})
    def visit(element):
        tag = str(element.tag).lower()
        if tag in {'script', 'style', 'svg'} or not isinstance(element.tag, str):
            return
        boundary = tag in {'p', 'div', 'section', 'article', 'li', 'h1', 'h2', 'h3', 'h4', 'tr'}
        if boundary or tag in {'br', 'img'}:
            flush()
        if tag == 'img':
            source = element.get('data-src') or element.get('src')
            if source:
                blocks.append({'type': 'image', 'source': source, 'alt': element.get('alt', '')})
        else:
            if element.text:
                buffer.append(element.text)
            for child in element:
                visit(child)
                if child.tail:
                    buffer.append(child.tail)
        if boundary or tag == 'br':
            flush()
    visit(node)
    flush()
    return blocks


def fetch(url):
    parsed = urlparse(url)
    if parsed.hostname not in HOSTS or parsed.scheme not in {'http', 'https'}:
        raise ValueError('Unexpected source host')
    response = requests.get(url, timeout=30, headers={'User-Agent': 'PipeSight authorized article import'}, allow_redirects=False)
    response.raise_for_status()
    if 300 <= response.status_code < 400 or len(response.content) > 15_000_000:
        raise ValueError('Unexpected redirect or oversized asset')
    return response


def prepare():
    STAGE.mkdir(parents=True, exist_ok=True)
    records = json.loads(MANIFEST.read_text())['records']
    result = []
    for item in records:
        if item['kind'] == 'paper':
            continue
        key = 'curated-' + item['kind'] + '-' + digest(item['url'].lower().encode())[:24]
        # The publisher's HTTP site remains readable; its HTTPS certificate has
        # expired. No TLS checks are disabled and no private data is transmitted.
        source = item['url'] if item['kind'] == 'news' else item['verification_url'].replace('https://', 'http://', 1)
        response = fetch(source)
        response.encoding = response.apparent_encoding
        document = html.fromstring(response.text)
        title_text = re.sub(r'\s+', '', document.xpath('string(//title)'))
        if re.sub(r'\s+', '', item['title']) not in title_text:
            raise ValueError('Source title mismatch: ' + key)
        if item['kind'] == 'wechat' and item['url'] not in response.text:
            raise ValueError('Publisher does not verify canonical WeChat URL')
        selector = '//div[@class="text content_class"]' if item['kind'] == 'news' else '//article[@class="news-info"]//div[@class="info"]'
        nodes = document.xpath(selector)
        if len(nodes) != 1:
            raise ValueError('Unambiguous full-text container required')
        blocks = extract_blocks(nodes[0])
        plain = '\n\n'.join(b['text'] for b in blocks if b['type'] == 'paragraph')
        source_text = re.sub(r'\s+', '', nodes[0].text_content())
        if re.sub(r'\s+', '', plain) != source_text or len(plain) < 300:
            raise ValueError('Source text completeness check failed: ' + key)
        directory = ASSETS / key
        directory.mkdir(parents=True, exist_ok=True)
        (directory / 'source.html').write_bytes(response.content)
        images = []
        for block in blocks:
            if block['type'] != 'image':
                continue
            url = urljoin(source, block.pop('source'))
            image_response = fetch(url)
            raw = image_response.content
            with Image.open(io.BytesIO(raw)) as image:
                fmt = image.format
                image.verify()
            mime = {'PNG': 'png', 'JPEG': 'jpeg', 'GIF': 'gif', 'WEBP': 'webp'}.get(fmt)
            if not mime:
                raise ValueError('Unsupported source image format')
            sha = digest(raw)
            filename = sha + '.' + mime
            (directory / filename).write_bytes(raw)
            block['src'] = 'data:image/' + mime + ';base64,' + base64.b64encode(raw).decode()
            images.append({'source_url': url, 'sha256': sha, 'file': filename, 'bytes': len(raw)})
        raw = json.dumps(blocks, ensure_ascii=False).encode()
        if len(raw) > 50_000_000:
            raise ValueError('Article assets exceed reader limit')
        (directory / 'article.json').write_bytes(raw)
        result.append({'id': key, 'title': item['title'], 'canonical_url': item['url'], 'body': plain,
                       'asset': {'asset_key': key, 'sha256': digest(raw), 'source_html_sha256': digest(response.content),
                                 'source_url': source, 'canonical_url': item['url'], 'authorization': AUTHORIZATION,
                                 'authorization_basis': 'user_attestation', 'fetched_at': datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
                                 'text_characters': len(plain), 'paragraphs': sum(b['type'] == 'paragraph' for b in blocks),
                                 'images': images, 'transport': urlparse(source).scheme}})
        print(json.dumps({'prepared': key, 'characters': len(plain), 'images': len(images)}, ensure_ascii=False), flush=True)
    if len(result) != 6:
        raise ValueError('Exactly six articles required')
    (STAGE / 'manifest.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))


def target():
    from config.env import DataBaseConfig as config
    if config.db_type != 'postgresql' or (config.db_host, config.db_database) != ('172.16.4.183', 'pipesight'):
        raise ValueError('Unexpected database')
    return dict(host=config.db_host, port=config.db_port, dbname=config.db_database,
                user=config.db_username, password=config.db_password, connect_timeout=8)


def backup_database(config):
    directory = STAGE / datetime.now(ZoneInfo('Asia/Shanghai')).strftime('backup-%Y%m%d-%H%M%S')
    directory.mkdir(mode=0o700)
    dump = directory / 'before.dump'
    env = {**os.environ, 'PGPASSWORD': config['password']}
    with dump.open('wb') as stream:
        process = subprocess.run(['docker', 'run', '--rm', '--env', 'PGPASSWORD', 'postgres:18-alpine',
                                  'pg_dump', '--host', config['host'], '--port', str(config['port']), '--username', config['user'],
                                  '--dbname', config['dbname'], '--format=custom', '--lock-wait-timeout=10000'],
                                 env=env, stdout=stream, stderr=subprocess.PIPE, timeout=120)
    dump.chmod(0o600)
    if process.returncode or dump.stat().st_size == 0:
        raise RuntimeError('Database backup failed; no changes applied')
    with dump.open('rb') as stream:
        listing = subprocess.run(['docker', 'run', '--rm', '-i', 'postgres:18-alpine', 'pg_restore', '--list'],
                                 stdin=stream, capture_output=True, timeout=30)
    if listing.returncode or not listing.stdout:
        raise RuntimeError('Backup verification failed; no changes applied')
    (directory / 'archive-list.txt').write_bytes(listing.stdout)
    return dump


def apply():
    records = json.loads((STAGE / 'manifest.json').read_text())
    if len(records) != 6 or len({r['id'] for r in records}) != 6:
        raise ValueError('Six unique existing records required')
    for row in records:
        asset = row['asset']
        if not re.fullmatch(r'curated-(?:news|wechat)-[a-f0-9]{24}', row['id']) or asset['asset_key'] != row['id']:
            raise ValueError('Invalid asset identity')
        if digest((ASSETS / row['id'] / 'article.json').read_bytes()) != asset['sha256']:
            raise ValueError('Asset checksum mismatch')
    config = target()
    backup = backup_database(config)
    snapshots = []
    with psycopg2.connect(**config) as connection:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("SET LOCAL lock_timeout='5s'")
            cursor.execute('SELECT pg_advisory_xact_lock(%s)', (2026101409,))
            cursor.execute('SELECT * FROM public.news_articles WHERE article_id=ANY(%s) ORDER BY article_id FOR UPDATE', ([r['id'] for r in records],))
            existing = {row['article_id']: dict(row) for row in cursor.fetchall()}
            if len(existing) != 6:
                raise ValueError('Existing article set mismatch')
            for row in records:
                before = existing[row['id']]
                metadata = dict(before['metadata_json'] or {})
                if before['canonical_url'] != row['canonical_url'] or metadata.get('import_batch') != 'homepage-real-content-20261014':
                    raise ValueError('Article provenance mismatch')
                if metadata.get('authorized_full_text'):
                    if metadata['authorized_full_text']['sha256'] == row['asset']['sha256'] and before['body'] == row['body']:
                        continue
                    raise ValueError('Existing full text differs; refusing overwrite')
                if not before['body'].startswith(before['summary']):
                    raise ValueError('Existing body changed; refusing overwrite')
                snapshots.append(before)
                metadata['authorized_full_text'] = row['asset']
                metadata['full_text_imported'] = True
                cursor.execute('UPDATE public.news_articles SET body=%s, metadata_json=%s, version_no=COALESCE(version_no,0)+1, update_time=%s WHERE article_id=%s',
                               (row['body'], Json(metadata), datetime.now(ZoneInfo('Asia/Shanghai')).replace(tzinfo=None), row['id']))
                cursor.execute('SELECT * FROM public.news_articles WHERE article_id=%s', (row['id'],))
                after = dict(cursor.fetchone())
                for field in before:
                    if field not in {'body', 'metadata_json', 'version_no', 'update_time'} and before[field] != after[field]:
                        raise ValueError('Unexpected field change: ' + field)
            (STAGE / 'before-rows.json').write_text(json.dumps(snapshots, ensure_ascii=False, default=str, indent=2))
    receipt = {'backup': str(backup), 'backup_verified': True, 'updated': len(snapshots),
               'articles': [{'id': r['id'], 'characters': len(r['body']), 'images': len(r['asset']['images'])} for r in records]}
    (STAGE / 'receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2))
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    apply() if args.apply else prepare()
