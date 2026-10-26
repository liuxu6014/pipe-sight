"""Import source-verified public metadata; dry-run by default, never overwrite rows.

Run from backend: PYTHONPATH=src .venv/bin/python scripts/import_curated_content.py
After a verified database backup, add --apply --backup /absolute/path/to/dump.
Manual publication is an explicit user-authorized exception to the automated
processing workflow. No collector, model call, embedding or external receipt is
fabricated. Original dates and platform publication times remain separate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import psycopg2
from psycopg2 import sql
from psycopg2.extras import Json


DEFAULT_MANIFEST = Path(__file__).resolve().parents[1] / 'data/curated/homepage-real-content-20261014.json'
REASON = '用户授权导入真实公开资料用于首页核对；人工核验来源并发布导读；未进行模型处理或全文采集'
FULL_TEXT_REASON = '用户授权导入完整管网工程文献；核验原始元数据、CC BY/CC0许可、正文参考文献与配图及全文校验和；未调用大模型'


def validate_manifest(manifest):
    """Reject incomplete provenance, duplicate identities and ambiguous dates."""
    if not manifest.get('batch') or not manifest.get('purpose') or not manifest.get('records'):
        raise ValueError('Manifest requires batch, purpose and records')
    if manifest.get('expected_count') is not None and len(manifest['records']) != manifest['expected_count']:
        raise ValueError('Manifest does not yet meet the required complete record count')
    seen = set()
    for item in manifest['records']:
        if item['kind'] not in {'paper', 'news', 'wechat'}:
            raise ValueError('Unsupported content kind')
        if not 0 < len(item['title']) <= 500 or not item.get('summary') or not item.get('source'):
            raise ValueError('Title, summary and source are required')
        parsed = urlparse(item['url'])
        if parsed.scheme != 'https' or not parsed.hostname or len(item['url']) > 1500:
            raise ValueError('Canonical URL must be HTTPS')
        identity = item.get('doi', item['url']).lower()
        if identity in seen:
            raise ValueError('Duplicate identity in manifest')
        seen.add(identity)
        date = item.get('original_date')
        if date:
            datetime.strptime(date, '%Y-%m' if item['kind'] == 'paper' and len(date) == 7 else '%Y-%m-%d')
        if item['kind'] == 'paper' and (not item.get('doi') or not item.get('authors') or item.get('year', 0) < 1600):
            raise ValueError('Paper DOI, authors and year are required')
        full_text = item.get('licensed_full_text')
        if full_text:
            if item['kind'] != 'paper' or not re.fullmatch(r'PMC\d+', full_text.get('asset_key', '')):
                raise ValueError('Invalid licensed paper asset key')
            if not re.fullmatch(r'https://creativecommons\.org/(?:licenses/by/(?:2\.0|3\.0|4\.0)|publicdomain/zero/1\.0)/', full_text.get('license_url', '')):
                raise ValueError('Unverified full-text reuse license')
            directory = Path(__file__).resolve().parents[1] / 'vf_admin/upload_path/licensed_papers' / full_text['asset_key']
            for filename, fingerprint in [('article.html', full_text.get('sha256')), ('source.xml', full_text.get('original_xml_sha256'))]:
                asset = directory / filename
                if not asset.is_file() or hashlib.sha256(asset.read_bytes()).hexdigest() != fingerprint:
                    raise ValueError('Full-text asset missing or checksum mismatch')
            for field in ['original_date', 'journal', 'publisher', 'volume', 'issue', 'pages', 'institutions', 'license_statement']:
                if not item.get(field):
                    raise ValueError('Incomplete full-text bibliography: ' + field)
        if item['kind'] == 'wechat':
            if parsed.hostname != 'mp.weixin.qq.com' or not item.get('verification_url'):
                raise ValueError('WeChat original and verification URLs are required')
            if item.get('repost_date'):
                datetime.strptime(item['repost_date'], '%Y-%m-%d')


def build_row(item, batch, now):
    """Create metadata without inventing original dates, scores or model results."""
    identity = item.get('doi', item['url']).lower()
    content_id = 'curated-' + item['kind'] + '-' + hashlib.sha256(identity.encode()).hexdigest()[:24]
    reason = FULL_TEXT_REASON if item.get('licensed_full_text') else REASON
    metadata = {
        'import_batch': batch, 'ingestion_mode': 'manual_source_verified',
        'llm_used': False, 'embedding_created': False, 'full_text_imported': bool(item.get('licensed_full_text')),
        'summary_kind': item.get('summary_kind', 'editorial_paraphrase'), 'original_date': item.get('original_date'),
        'verification_url': item.get('verification_url', item['url']),
        'verified_at': now.isoformat(), 'repost_date': item.get('repost_date'),
        'license_url': item.get('license'), 'relevance_assessed': False,
        'manual_publication_reason': reason,
    }
    if item.get('licensed_full_text'):
        metadata.update(licensed_full_text=item['licensed_full_text'], institutions=item['institutions'],
                        author_institutions=item.get('author_institutions', []),
                        license_statement=item['license_statement'], pmcid=item['pmcid'],
                        body_characters=item['body_characters'], references_count=item['references_count'])
    summary = item['summary'] if item.get('summary_kind') == 'original_abstract' else '导读摘要（据公开资料整理）：' + item['summary']
    row = dict(title=item['title'], canonical_url=item['url'], source_name=item['source'],
               review_status='approved', reviewed_by=None, reviewed_at=now,
               review_reason=reason, published_at=now, permission_scope='public',
               tags=Json(item['tags']), metadata_json=Json(metadata),
               handoff_status='pending', handoff_result_json=Json({}),
               create_time=now, update_time=now)
    if item['kind'] == 'paper':
        row.update(paper_id=content_id, doi=item['doi'], doi_normalized=item['doi'].lower(),
                   authors='、'.join(item['authors']), authors_json=Json(item['authors']),
                   keywords=Json(item['tags']), journal=item['journal'], publisher=item.get('publisher'),
                   publication_year=item['year'], volume=item.get('volume'), issue=item.get('issue'),
                   pages=item.get('pages'), abstract_text=summary, citation_count=item.get('citation_count', 0),
                   open_access_status='open' if item.get('license') else 'unknown',
                   full_text_status='available' if item.get('licensed_full_text') else 'unknown', full_text_url=item.get('full_text_url'))
        return 'papers', 'paper_id', row
    body = summary + '\n\n原文链接：' + item['url']
    if item['kind'] == 'wechat':
        body += ('\n\n公众号首发日期未核实。发布机构官网明确标注上述微信原文链接；'
                 '官网转载日期：' + item['repost_date'] + '。\n官网核验地址：' + item['verification_url'])
    row.update(article_id=content_id, article_type=item['kind'], summary=summary, body=body,
               published_time=datetime.fromisoformat(item['original_date']) if item.get('original_date') else None,
               discovered_time=now, language='zh-CN', relevance_score=0, version_no=1,
               url_hash=hashlib.sha256(item['url'].encode()).hexdigest())
    return 'news_articles', 'article_id', row


def insert_row(cursor, table, row):
    cursor.execute(sql.SQL('INSERT INTO public.{} ({}) VALUES ({})').format(
        sql.Identifier(table), sql.SQL(',').join(map(sql.Identifier, row)),
        sql.SQL(',').join(sql.Placeholder() for _ in row)), list(row.values()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--backup', type=Path)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    validate_manifest(manifest)
    if args.apply:
        if not args.backup or not args.backup.is_file() or args.backup.stat().st_size == 0:
            raise ValueError('A verified database backup is required before --apply')
    from config.env import DataBaseConfig as config
    if config.db_type != 'postgresql' or (config.db_host, config.db_database) != ('172.16.4.183', 'pipesight'):
        raise ValueError('Refusing unexpected database target')
    now = datetime.now(ZoneInfo('Asia/Shanghai')).replace(tzinfo=None)
    receipt = {'batch': manifest['batch'], 'applied': args.apply, 'added': [], 'skipped': []}
    with psycopg2.connect(host=config.db_host, port=config.db_port, dbname=config.db_database,
                          user=config.db_username, password=config.db_password) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL lock_timeout = '5s'")
            cursor.execute('SELECT pg_advisory_xact_lock(%s)', (2026101409,))
            for item in manifest['records']:
                table, pk, row = build_row(item, manifest['batch'], now)
                if table == 'papers':
                    cursor.execute('SELECT paper_id FROM public.papers WHERE doi_normalized=%s OR canonical_url=%s OR paper_id=%s',
                                   (row['doi_normalized'], item['url'], row[pk]))
                else:
                    cursor.execute('SELECT article_id FROM public.news_articles WHERE url_hash=%s OR canonical_url=%s OR article_id=%s',
                                   (row['url_hash'], item['url'], row[pk]))
                existing = cursor.fetchone()
                if existing:
                    receipt['skipped'].append({'id': existing[0], 'kind': item['kind']})
                    continue
                receipt['added'].append({'id': row[pk], 'kind': item['kind'], 'title': item['title']})
                if not args.apply:
                    continue
                insert_row(cursor, table, row)
                insert_row(cursor, 'content_review_events', dict(
                    event_id='curated-approve-' + hashlib.sha256(row[pk].encode()).hexdigest()[:24],
                    content_type='paper' if table == 'papers' else 'article', content_id=row[pk],
                    from_status='pending', to_status='approved', action='approve', reason=row['review_reason'],
                    operator_id=None, operator_name='用户授权的公开资料导入',
                    snapshot_json=Json({'title': item['title'], 'source_url': item['url'],
                                        'import_batch': manifest['batch'], 'llm_used': False,
                                        'handoff_status': 'pending', 'publication_mode': 'manual'}), create_time=now))
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
