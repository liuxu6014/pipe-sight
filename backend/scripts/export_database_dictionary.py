"""Export PostgreSQL catalog documentation and fail on undocumented objects.

Uses the normal local environment configuration. Never exports business rows,
passwords, model credentials or application connection strings.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import text

from config.database import async_engine
from config.schema_documentation import (
    APPLICATION_INTERMEDIATE_RENAMES,
    APPLICATION_TABLE_RENAMES,
    PROCESSING_TABLE_RENAMES,
)

CATALOG_SQL = """
SELECT n.nspname AS schema_name,c.relname AS object_name,c.relkind::text AS object_kind,
       obj_description(c.oid,'pg_class') AS object_comment,
       a.attnum AS ordinal,a.attname AS column_name,
       format_type(a.atttypid,a.atttypmod) AS data_type,
       a.attnotnull AS not_null,pg_get_expr(d.adbin,d.adrelid) AS default_value,
       col_description(c.oid,a.attnum) AS column_comment,
       EXISTS(SELECT 1 FROM pg_constraint k WHERE k.conrelid=c.oid AND k.contype='p' AND a.attnum=ANY(k.conkey)) AS primary_key,
       ARRAY(SELECT pg_get_constraintdef(k.oid) FROM pg_constraint k
             WHERE k.conrelid=c.oid AND k.contype='f' AND a.attnum=ANY(k.conkey)) AS foreign_keys
FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
JOIN pg_attribute a ON a.attrelid=c.oid AND a.attnum>0 AND NOT a.attisdropped
LEFT JOIN pg_attrdef d ON d.adrelid=c.oid AND d.adnum=a.attnum
WHERE n.nspname IN ('public','news') AND c.relkind IN ('r','p','v','m')
ORDER BY n.nspname,c.relname,a.attnum
"""


async def inspect_catalog() -> dict[str, Any]:
    """Read comments and types, without selecting any application row values."""
    if async_engine is None:
        raise RuntimeError('数据库引擎未初始化')
    async with async_engine.connect() as connection:
        await connection.execute(text('SET TRANSACTION READ ONLY'))
        database = (await connection.execute(text('SELECT current_database()'))).scalar_one()
        rows = (await connection.execute(text(CATALOG_SQL))).mappings().all()
    objects: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = f'{row["schema_name"]}.{row["object_name"]}'
        item = objects.setdefault(key, {
            'schema': row['schema_name'], 'name': row['object_name'], 'kind': row['object_kind'],
            'comment': row['object_comment'], 'columns': [],
        })
        item['columns'].append({name: row[name] for name in (
            'column_name', 'data_type', 'not_null', 'default_value', 'column_comment', 'primary_key', 'foreign_keys',
        )})
    missing_objects = [key for key, item in objects.items() if not str(item['comment'] or '').strip()]
    missing_columns = [f'{key}.{column["column_name"]}' for key, item in objects.items()
                       for column in item['columns'] if not str(column['column_comment'] or '').strip()]
    legacy_physical = [key for key, item in objects.items() if item['schema'] == 'news'
                       and item['name'] in PROCESSING_TABLE_RENAMES and item['kind'] in ('r', 'p')]
    legacy_physical.extend(key for key, item in objects.items() if item['schema'] == 'public'
                           and item['name'] in (APPLICATION_TABLE_RENAMES | APPLICATION_INTERMEDIATE_RENAMES)
                           and item['kind'] in ('r', 'p'))
    return {
        'database': database, 'exported_at': datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
        'object_count': len(objects), 'column_count': sum(len(item['columns']) for item in objects.values()),
        'missing_object_comments': missing_objects, 'missing_column_comments': missing_columns,
        'legacy_physical_tables': legacy_physical, 'objects': objects,
    }


def markdown_dictionary(report: dict[str, Any]) -> str:
    """Render an editable data dictionary from the actual PostgreSQL catalog."""
    def cell(value: Any) -> str:
        return str(value if value is not None else '—').replace('|', '\\|').replace('\n', ' ')

    output = [
        '# PipeSight PostgreSQL 数据字典', '',
        f'数据库：`{report["database"]}`。导出时间：{report["exported_at"]}。', '',
        '本文件由 `backend/scripts/export_database_dictionary.py` 从实际 catalog 生成，不包含业务记录或连接凭据。', '',
        f'共 {report["object_count"]} 个表/视图、{report["column_count"]} 个字段。',
        f'缺失对象注释 {len(report["missing_object_comments"])} 个，缺失字段注释 {len(report["missing_column_comments"])} 个。', '',
        '## 命名与兼容规则', '',
        '- 若依原生 `sys_*`、`ai_*` 及框架基础设施名称保留兼容。',
        '- `public` 保存应用配置及业务数据，`news` 保存处理收件箱、规则和向量投影。',
        '- 旧处理表名兼容视图已退役；运行代码直接使用规范物理表。现存视图按用途单独列出，不计为额外业务数据副本。',
        '- 应用业务表去掉冗余 `pipeline_` 前缀，使用 `model_routes`、`prompt_versions`、`quality_issues` 等短名称。',
        '- 视图上的主键/非空约束标记不代表底层表没有约束，请按对应物理表核对。',
        '- `timestamp without time zone` 不擅自解释为 UTC，业务时间遵循现有来源/应用约定；`with time zone` 为绝对时间。', '',
        '## 对象总览', '', '| 对象 | 类型 | 说明 | 字段数 |', '| --- | --- | --- | --- |',
    ]
    for key, item in report['objects'].items():
        kind = '视图' if item['kind'] in ('v', 'm') else '物理表'
        output.append(f'| `{key}` | {kind} | {cell(item["comment"])} | {len(item["columns"])} |')
    for key, item in report['objects'].items():
        output.extend(['', f'## {key}', '', cell(item['comment']), '',
                       '| 字段 | PostgreSQL 类型 | 必填 | 主键 | 默认值 | 说明 | 关联外键 |',
                       '| --- | --- | --- | --- | --- | --- | --- |'])
        output.extend('| ' + ' | '.join([
                f'`{column["column_name"]}`', cell(column['data_type']), '是' if column['not_null'] else '否',
                '是' if column['primary_key'] else '否', cell(column['default_value']),
                cell(column['column_comment']), cell('；'.join(column['foreign_keys']) or None),
            ]) + ' |' for column in item['columns'])
    return '\n'.join(output) + '\n'


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env', default='dev')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--audit-json', type=Path)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    try:
        report = await inspect_catalog()
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(markdown_dictionary(report), encoding='utf-8')
        if args.audit_json:
            args.audit_json.parent.mkdir(parents=True, exist_ok=True)
            args.audit_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({key: value for key, value in report.items() if key != 'objects'}, ensure_ascii=False, indent=2))
        if args.check and any(report[key] for key in ('missing_object_comments', 'missing_column_comments', 'legacy_physical_tables')):
            raise SystemExit('数据库命名或注释完整性校验失败')
    finally:
        if async_engine is not None:
            await async_engine.dispose()


if __name__ == '__main__':
    asyncio.run(main())
