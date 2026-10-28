"""修正已确认的项目需求模板；默认只预览，显式 --apply 才备份并更新一条配置。"""

import argparse
import asyncio
import hashlib
import json
from pathlib import Path

from sqlalchemy import text

from app.research.services.writing_rules import PROJECT_DEMAND_PROMPT
from config.database import create_async_db_engine

SECTIONS = [
    {'id': 1, 'title': '生产需求及技术问题', 'words': 800, 'required': True,
     'description': '场景、主要问题与研究必要性，避免行业新闻流水账。'},
    {'id': 2, 'title': '国内外技术现状分析', 'words': 1000, 'required': True,
     'description': '按技术路线综合比较已有进展及不足，引出研究切入点。'},
    {'id': 3, 'title': '研究目标', 'words': 500, 'required': True,
     'description': '回应具体技术问题，不虚构性能指标。'},
    {'id': 4, 'title': '研究内容', 'words': 900, 'required': True,
     'description': '组织技术路径、关键任务及验证方法，避免复述目标。'},
    {'id': 5, 'title': '预期研究成果', 'words': 500, 'required': True,
     'description': '交代与任务对应的交付物和用途，不虚构已取得成果。'},
    {'id': 6, 'title': '经费需求', 'words': 150, 'required': True,
     'description': '有预算依据才展开；无依据则简短说明测算前提，不枚举财务制度。'},
]


async def run(apply: bool, backup: Path | None) -> None:
    engine = create_async_db_engine(echo=False)
    try:
        async with engine.begin() as connection:
            row = (await connection.execute(text('SELECT * FROM templates WHERE id=31 FOR UPDATE'))).mappings().one()
            if row['name'] != '科技项目需求填报表' or row['purpose'] != 'research':
                raise RuntimeError('模板身份已变化，停止更新')
            old_report = (await connection.execute(text('SELECT content FROM reports WHERE id=40'))).scalar_one()
            digest = hashlib.sha256(old_report.encode()).hexdigest()
            print(json.dumps({'templateId': 31, 'name': row['name'], 'mode': 'apply' if apply else 'preview',
                              'oldWords': sum(s.get('words', 0) for s in row['sections']),
                              'newWords': sum(s['words'] for s in SECTIONS), 'report40Sha256': digest},
                             ensure_ascii=False))
            if not apply:
                return
            if backup is None or not backup.is_absolute():
                raise ValueError('--apply 必须提供绝对路径 --backup；不能覆盖现有备份')
            # 仅备份此模板的完整行；不读取模型凭证，也不备份或更改若依表。
            with backup.open('x', encoding='utf-8') as stream:
                json.dump(dict(row), stream, ensure_ascii=False, default=str, indent=2)
            await connection.execute(text('''UPDATE templates SET prompt=:prompt, sections=CAST(:sections AS jsonb),
                description=:description, updated_at=date_trunc('second', CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Shanghai')
                WHERE id=31'''), {'prompt': PROJECT_DEMAND_PROMPT, 'sections': json.dumps(SECTIONS, ensure_ascii=False),
                                 'description': '围绕生产问题、技术现状和研究路径成文；经费无依据时简要说明，不凑篇幅。'})
            after = (await connection.execute(text('SELECT content FROM reports WHERE id=40'))).scalar_one()
            if hashlib.sha256(after.encode()).hexdigest() != digest:
                raise RuntimeError('历史报告发生变化，回滚')
            print('已更新单条模板配置；报告40正文保持原样。')
    finally:
        await engine.dispose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--backup', type=Path)
    args = parser.parse_args()
    asyncio.run(run(args.apply, args.backup))
