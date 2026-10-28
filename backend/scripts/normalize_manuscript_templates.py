"""Replace legacy JSON-as-prompt defaults only, preserving chapters and history."""
import asyncio
import argparse
import json

from sqlalchemy import text
from config.database import async_engine

PROMPTS = {
    27: ('技术路线报告', '围绕明确的业务需求撰写技术路线研究报告。按确认的章节说明现状、关键问题、任务之间的依赖、试验验证与阶段成果。采用完整分析段落，不写操作手册，不虚构成熟度、指标或已完成试验。'),
    28: ('管网科技情报月报', '撰写面向行业研究与管理人员的科技情报月报。按确认的栏目归纳本期事件、技术进展、阶段变化及业务影响。历史资料仅作为背景，不冒充当月新进展。只有充分证据支持时才讨论趋势或风险，避免逐条摘抄与泛泛展望。'),
    29: ('检测技术专题周报', '撰写检测技术专题周报。按确认的栏目组织事实与分析，围绕不同进展的联系、适用场景和局限形成连贯文章，不按来源编号逐篇复述。区分本周事件与历史背景，不从少量报道推断长期趋势。'),
    30: ('科研需求报告', '围绕实际技术问题撰写科研需求研究报告。按照确认的章节连接问题、现状差距、目标、研究任务、验证依据与预期应用。论证使用完整自然段，不填表，不用机械条目替代分析；没有依据的考核数值不得编造。'),
    32: ('管网科技情报日报', '撰写面向行业研究与管理人员的科技情报日报。按确认的栏目直接交代重要事件及业务影响，使用连贯自然段归纳技术进展和适用边界。资料有限时形成短而完整的文章，不把筛选结果或生成过程写进正文，不为达到条数补造内容。'),
}


async def main(apply=False):
    async with async_engine.begin() as db:
        before = await db.scalar(text("SELECT md5(coalesce(jsonb_agg(to_jsonb(r) ORDER BY id)::text,'[]')) FROM reports r"))
        changed = []
        for ident, (name, prompt) in PROMPTS.items():
            row = (await db.execute(text('SELECT id,name,prompt FROM templates WHERE id=:id FOR UPDATE'), {'id': ident})).mappings().one()
            assert row['name'] == name, 'Template identity changed'
            try:
                legacy = json.loads(row['prompt'])
            except ValueError:
                continue  # Preserve custom administrator prose.
            if not isinstance(legacy, dict) or not isinstance(legacy.get('sections'), list):
                continue
            if apply:
                await db.execute(text("UPDATE templates SET prompt=:prompt, updated_at=date_trunc('second', CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Shanghai') WHERE id=:id"), {'prompt': prompt, 'id': ident})
            changed.append(ident)
        after = await db.scalar(text("SELECT md5(coalesce(jsonb_agg(to_jsonb(r) ORDER BY id)::text,'[]')) FROM reports r"))
        assert before == after
        print(json.dumps({'updated_legacy_template_ids': changed, 'reports_unchanged': before}, ensure_ascii=False))
    await async_engine.dispose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Apply after taking an external database backup')
    args, _ = parser.parse_known_args()
    asyncio.run(main(args.apply))
