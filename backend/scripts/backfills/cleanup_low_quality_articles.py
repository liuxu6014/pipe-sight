"""Delete a user-approved list of low-quality / incomplete articles.

The target rows are the result of a review on 2026-11-01 (user-approved). A row
is "low quality / incomplete" when its ``content`` body is a placeholder instead
of an actual article: shorter than 50 chars (WeChat RSS items that only carry
title + footer, or test messages), Lorem-ipsum filler, navigation-only pages
(crawler captured page chrome such as ``此稿件无标签`` instead of the text), or
report pointers (``…点击下方阅读原文``, no body, under 120 chars).

Deletion targets the explicit ``TARGET_IDS`` list below (not a live heuristic),
so it only ever removes the reviewed rows. ``basket_items.article_id`` is
``ON DELETE CASCADE`` and none of these rows are referenced.

Dry-run by default: it only lists what would change. ``--apply`` deletes rows.

Run from backend with the target env set:

    .venv/Scripts/python.exe scripts/backfills/cleanup_low_quality_articles.py          # dry-run
    .venv/Scripts/python.exe scripts/backfills/cleanup_low_quality_articles.py --apply  # delete

Targets only the production DB (172.16.4.183/pipesight); any other host/database is refused.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter

import psycopg2

ADVISORY_LOCK = 2026110104

# User-approved target list (2026-11-01, batch 2: nav/hub/landing + marketing blurb pages).
TARGET_IDS = [
    # A. T.D. Williamson 首页/导航残页（标题仅为公司名，内容为栏目导航）
    68, 123, 182, 188, 190, 195, 199, 259, 266, 270,
    # B. 栏目/列表/落地页（Papers/Webinars/Case Studies/Document library/... 索引页）
    201, 82, 206, 192, 135, 198, 248, 202, 72, 209, 276, 285, 273, 138, 284, 2010,
    # C. onstream-pipeline 服务营销短页（非文章）
    721, 700, 735, 788, 772, 885,
]


def target() -> dict:
    from config.env import DataBaseConfig as config  # noqa: PLC0415

    if config.db_type != 'postgresql':
        raise ValueError('拒绝非 PostgreSQL 目标')
    if (config.db_host, config.db_database) != ('172.16.4.183', 'pipesight'):
        raise ValueError(f'仅允许 172.16.4.183/pipesight，拒绝目标: {config.db_host}/{config.db_database}')
    return {
        'host': config.db_host,
        'port': config.db_port,
        'dbname': config.db_database,
        'user': config.db_username,
        'password': config.db_password,
        'connect_timeout': 8,
    }


def candidates(cursor) -> list[tuple]:
    cursor.execute(
        """
        SELECT a.id, s.name, s.adapter, a.title, length(trim(a.content))
        FROM news_articles a JOIN data_sources s ON s.id = a.source_id
        WHERE a.id = ANY(%s)
        ORDER BY s.adapter, length(trim(a.content)), a.id
        """,
        (TARGET_IDS,),
    )
    return cursor.fetchall()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='删除匹配行；缺省为 dry-run')
    args = parser.parse_args()

    config = target()
    with psycopg2.connect(**config) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL lock_timeout = '5s'")
            cursor.execute('SELECT pg_advisory_xact_lock(%s)', (ADVISORY_LOCK,))
            doomed = candidates(cursor)
            receipt = {
                'apply': args.apply,
                'matched': len(doomed),
                'by_adapter': dict(Counter(r[2] for r in doomed)),
                'rows': [
                    {'id': r[0], 'source': r[1], 'adapter': r[2], 'title': r[3], 'content_len': r[4]}
                    for r in doomed
                ],
            }
            if args.apply and doomed:
                cursor.execute('DELETE FROM news_articles WHERE id = ANY(%s)', (TARGET_IDS,))
                receipt['deleted'] = cursor.rowcount
            else:
                receipt['deleted'] = 0
            cursor.execute('SELECT count(*) FROM news_articles')
            receipt['remaining'] = cursor.fetchone()[0]

    print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
