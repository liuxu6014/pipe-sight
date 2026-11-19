"""复筛结果绑定本人、周期和模板，生成任务冻结已通过的资料标签。"""

import json
from hashlib import sha256
from uuid import uuid4

from redis.exceptions import LockError

from app.business_ids import wire_id
from app.intelligence.services.template_presets import effective_digest_categories
from app.intelligence.services.templates import PipelineTemplateService
from app.research.digest_policy import DIGEST_SELECTION_LIMIT
from app.research.repositories.research_repository import ResearchDao
from app.research.services.digest_document import DEFAULT_DIGEST_SCREENING, DigestScreeningError, digest_material_key
from app.research.services.digest_rules import screening_rule_snapshot
from app.research.services.evidence import ResearchEvidenceService
from app.research.services.model_generation import DIGEST_SCREENING_BATCH_SIZE, ResearchModelGenerationService

BATCH_SIZE = DIGEST_SCREENING_BATCH_SIZE
RESULT_TTL = 3600


def _signature(value) -> str:
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()


def _key(user_id, screening_id) -> str:
    return f'pipeline:digest-screening:{user_id}:{screening_id}'


def _template_signature(template, model) -> str:
    return _signature(
        [
            wire_id(template.id),
            template.prompt,
            getattr(template, 'screening_prompt', None),
            effective_digest_categories(template),
            wire_id(model.id),
            model.provider,
            model.code,
            model.base_url,
            model.parameters,
        ]
    )


async def _read(redis, key) -> dict:
    raw = await redis.get(key) if redis is not None else None
    if not raw:
        raise DigestScreeningError(message='筛选结果已过期，请重新筛选后提交', restart_required=True)
    return json.loads(raw)


class DigestScreeningService:
    @staticmethod
    async def classify_batch(db, model, scope, materials, *, prompt, request_id) -> dict:
        model_snapshot = {
            'id': wire_id(model.id),
            'provider': model.provider,
            'code': model.code,
            'base_url': model.base_url,
            'parameters': model.parameters or {},
        }
        return await ResearchModelGenerationService.classify_digest(
            db, model_snapshot, scope, materials, prompt=prompt, request_id=request_id
        )

    @staticmethod
    async def _model(db, user_id, report_type, template_id) -> tuple:
        template = await PipelineTemplateService.get_digest_for_run(db, report_type, user_id, template_id)
        model_id, _ = await PipelineTemplateService.generation_model_ids(db, 'digest', template, required=True)
        model = await PipelineTemplateService.validate_models(db, model_id)
        return template, model

    @classmethod
    async def begin(cls, db, redis, user_id, body) -> dict:
        candidates, total = await ResearchDao.search_digest_candidates(db, body, all_candidates=True)
        if not total:
            return {'total': 0, 'processed': 0, 'rows': []}
        template, model = await cls._model(db, user_id, body.report_type, body.template_id)
        screening_id = uuid4().hex
        scope = body.model_dump(mode='json', exclude={'page_num', 'page_size', 'screening_prompt'})
        categories = scope.pop('screening_categories', None)
        # Older clients could supply a complete free-form rule without a category list.
        if categories is None and body.screening_prompt and getattr(template, 'screening_categories', None) is None:
            categories = []
        state = {
            'scope': scope,
            **screening_rule_snapshot(template, general_prompt=body.screening_prompt, categories=categories),
            'signature': _template_signature(template, model),
            'ids': [wire_id(row.id) for row in candidates],
            'rows': [],
            'hashes': {},
        }
        await db.commit()
        await redis.set(_key(user_id, screening_id), json.dumps(state, ensure_ascii=False), ex=RESULT_TTL)
        return {'screeningId': screening_id, 'total': total, 'processed': 0}

    @classmethod
    async def advance(cls, db, redis, user_id, screening_id) -> dict:
        key = _key(user_id, screening_id)
        try:
            async with redis.lock(key + ':batch', timeout=180, blocking_timeout=1):
                state = await _read(redis, key)
                scope, rows = state['scope'], state['rows']
                total, offset = len(state['ids']), len(rows)
                if offset < total:
                    template, model = await cls._model(db, user_id, scope['report_type'], scope['template_id'])
                    if _template_signature(template, model) != state['signature']:
                        raise DigestScreeningError(
                            message='简报模板或模型配置已变化，请重新筛选', restart_required=True
                        )
                    materials = []
                    for item_id in state['ids'][offset : offset + BATCH_SIZE]:
                        article = await ResearchDao.load_content(db, 'article', item_id)
                        if article is None:
                            raise DigestScreeningError(message='候选资料已变化，请重新筛选', restart_required=True)
                        materials.append(ResearchEvidenceService.article_evidence(article))
                    # Release the default template's transaction lock while the model runs.
                    await db.commit()
                    try:
                        decisions = await cls.classify_batch(
                            db,
                            model,
                            {**scope, 'screening_categories': state.get('categories', [])},
                            materials,
                            prompt=state.get('prompt') or template.screening_prompt or DEFAULT_DIGEST_SCREENING,
                            request_id=f'digest:{screening_id}:{offset}:{uuid4().hex}',
                        )
                    finally:
                        await db.commit()
                    for item in materials:
                        decision = decisions[digest_material_key(item)]
                        rows.append(
                            {
                                'id': item['id'],
                                'title': item['title'],
                                'publisher': item['source'].get('publisher'),
                                'publishedAt': item['source'].get('published_at'),
                                **decision,
                            }
                        )
                        if decision['keep']:
                            state['hashes'][item['id']] = _signature(item)
                    await redis.set(key, json.dumps(state, ensure_ascii=False), ex=RESULT_TTL)
                return {
                    'screeningId': screening_id,
                    'total': total,
                    'processed': len(rows),
                    **({'rows': rows} if len(rows) == total else {}),
                }
        except LockError as exc:
            raise DigestScreeningError(message='本批资料正在复筛，请稍后继续') from exc

    @staticmethod
    async def approved(db, redis, user_id, data, template, model) -> tuple[list[dict], dict]:
        state = await _read(redis, _key(user_id, data['screening_id']))
        scope = state['scope']
        options = data.get('options') or {}
        if (
            len(state['rows']) != len(state['ids'])
            or data.get('report_type') != scope['report_type']
            or data.get('period') != scope['period']
            or (data.get('keywords') or []) != scope['keywords']
            or ('sources' in options and options['sources'] != scope['sources'])
            or (options.get('directions') or []) != scope['directions']
            or _template_signature(template, model) != state['signature']
        ):
            raise DigestScreeningError(message='周期、模板或筛选条件不匹配，请重新筛选', restart_required=True)
        passed = {row['id']: row for row in state['rows'] if row['keep']}
        if not passed:
            raise DigestScreeningError(message='没有通过筛选的文章，请调整提示词后重新筛选', restart_required=True)
        if len(passed) > DIGEST_SELECTION_LIMIT:
            raise DigestScreeningError(
                message=f'通过筛选的文章有 {len(passed)} 篇，超过每份简报的 {DIGEST_SELECTION_LIMIT} 篇上限，请收紧提示词后重新筛选',
                restart_required=True,
            )
        materials = await ResearchEvidenceService.resolve(
            db, user_id, [{'type': 'article', 'id': item_id} for item_id in passed]
        )
        if any(state['hashes'].get(item['id']) != _signature(item) for item in materials):
            raise DigestScreeningError(message='通过筛选的资料正文已更新，请重新筛选', restart_required=True)
        return materials, {
            'candidate_count': len(state['rows']),
            'passed_count': len(passed),
            'prompt': state.get('prompt') or template.screening_prompt or DEFAULT_DIGEST_SCREENING,
            'general_prompt': state.get('general_prompt', state.get('prompt', '')),
            'categories': state.get('categories', []),
            'retained_ids': [digest_material_key(item) for item in materials],
            'labels': {
                f'article:{row["id"]}': {field: row[field] for field in ('keep', 'category', 'tags', 'reason')}
                for row in state['rows']
            },
        }
