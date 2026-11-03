"""把一次性导入的 wechat_rss_import 来源迁移为可启停的 wechat_rss 采集源。

此前 `scripts/imports/import_wechat_feeds.py` 用 `adapter='wechat_rss_import'`（未注册进采集器）
写入了 17 个公众号来源，并把 feed 地址同时放在 `url` 列和 `config.feed_url`。它们因此
无法在来源管理中启停/定时采集。

迁移只做两件事（幂等）：
- `adapter` 由 `wechat_rss_import` 改为已注册的 `wechat_rss`；
- `url` 置空——`wechat_rss` 的入口只允许落在 `config.feed_url`，`url` 列仍受全局
  HTTPS 白名单约束，保留 http feed 会导致启用时校验失败。

`config` 原样保留（`feed_url`/`bizid`/`account` 均被适配器接受），文章因 URL 去重
不会重复入库。

缺省 dry-run，只打印将受影响的行；`--apply` 才写库。与其它脚本一致，仅允许
172.16.4.183/pipesight。

Run from backend with the target env set:

    .venv/Scripts/python.exe scripts/migrations/migrate_wechat_rss_sources.py            # dry-run
    .venv/Scripts/python.exe scripts/migrations/migrate_wechat_rss_sources.py --apply    # write
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from zoneinfo import ZoneInfo

import psycopg2

BEIJING = ZoneInfo('Asia/Shanghai')
FROM_ADAPTER = 'wechat_rss_import'
TO_ADAPTER = 'wechat_rss'
ADVISORY_LOCK = 2026110104


def now_beijing() -> datetime:
    return datetime.now(BEIJING).replace(tzinfo=None)


def target() -> dict:
    from config.env import DataBaseConfig as config

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


def list_candidates(cursor) -> list[dict]:
    cursor.execute(
        """
        SELECT id, name, type, config->>'feed_url' AS feed_url, config->>'bizid' AS bizid, is_enabled
        FROM public.data_sources
        WHERE adapter = %s
        ORDER BY id
        """,
        (FROM_ADAPTER,),
    )
    columns = [column.name for column in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def migrate(cursor, updated_at: datetime) -> list[dict]:
    cursor.execute(
        """
        UPDATE public.data_sources
        SET adapter = %s, url = NULL, updated_at = %s
        WHERE adapter = %s
        RETURNING id, name, config->>'feed_url' AS feed_url, config->>'bizid' AS bizid, is_enabled
        """,
        (TO_ADAPTER, updated_at, FROM_ADAPTER),
    )
    columns = [column.name for column in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='写入数据库；缺省为 dry-run')
    args = parser.parse_args()

    config = target()
    with psycopg2.connect(**config) as connection, connection.cursor() as cursor:
        candidates = list_candidates(cursor)
        if not candidates:
            print(json.dumps({'apply': args.apply, 'count': 0, 'message': '无待迁移来源'}, ensure_ascii=False))
            return
        if not args.apply:
            print(json.dumps({'apply': False, 'count': len(candidates), 'rows': candidates}, ensure_ascii=False, indent=2))
            return
        cursor.execute("SET LOCAL lock_timeout = '5s'")
        cursor.execute('SELECT pg_advisory_xact_lock(%s)', (ADVISORY_LOCK,))
        migrated = migrate(cursor, now_beijing())
        print(json.dumps({'apply': True, 'count': len(migrated), 'rows': migrated}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
