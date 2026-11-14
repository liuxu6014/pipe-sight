"""Manual global model bindings for content processing and English translation."""

from datetime import datetime

from sqlalchemy import select

from app.business_ids import parse_business_id, wire_id

TRANSLATION_MODEL_KEY = 'pipeline.translation.modelId'
PROCESSING_MODEL_KEY = 'pipeline.processing.modelId'
GENERATION_PURPOSES = {
    'image': ('pipeline.generation.image.modelId', '图片生成模型', 'image_generate'),
    'digest': ('pipeline.generation.digest.modelId', '简报生成模型', 'text_generate'),
    'research': ('pipeline.generation.research.modelId', '科研报告生成模型', 'text_generate'),
}


async def generation_settings(db, purpose) -> dict:
    key, _name, _capability = GENERATION_PURPOSES[purpose]
    return {'modelId': wire_id(await configured_model_id(db, key))}


async def save_generation_settings(db, purpose, model_id) -> dict:
    key, name, capability = GENERATION_PURPOSES[purpose]
    return await save_model_setting(db, model_id, key, name, capability=capability)


async def configured_model_id(db, key) -> int | None:
    from app.system.models.config import SysConfig  # noqa: PLC0415

    value = (await db.execute(select(SysConfig.value).where(SysConfig.key == key))).scalar_one_or_none()
    return None if value in (None, '') else parse_business_id(value)


async def translation_model_id(db) -> int | None:
    return await configured_model_id(db, TRANSLATION_MODEL_KEY)


async def processing_settings(db) -> dict:
    return {'modelId': wire_id(await configured_model_id(db, PROCESSING_MODEL_KEY))}


async def translation_settings(db) -> dict:
    return {'modelId': wire_id(await translation_model_id(db))}


async def save_translation_settings(db, model_id) -> dict:
    return await save_model_setting(db, model_id, TRANSLATION_MODEL_KEY, '翻译模型')


async def save_processing_settings(db, model_id) -> dict:
    return await save_model_setting(db, model_id, PROCESSING_MODEL_KEY, '内容处理模型')


async def save_model_setting(db, model_id, key, name, *, capability='text_generate') -> dict:
    from app.intelligence.services.collection_translation import (  # noqa: PLC0415
        CollectionTranslationService,
        TranslationConfigurationError,
        _parameters,
    )
    from app.system.models.config import SysConfig  # noqa: PLC0415

    if model_id is not None:
        model_id = parse_business_id(model_id)
        try:
            model = await CollectionTranslationService._model(db, model_id, capability=capability)
            _parameters(model.parameters or {})
        except ValueError as exc:
            raise TranslationConfigurationError(str(exc).replace('翻译模型', name).replace('自动翻译', name)) from exc
    dialect = db.get_bind().dialect.name
    if dialect == 'postgresql':
        from sqlalchemy.dialects.postgresql import insert  # noqa: PLC0415
    elif dialect == 'sqlite':
        from sqlalchemy.dialects.sqlite import insert  # noqa: PLC0415
    else:
        raise ValueError('当前数据库不支持模型用途配置')
    value = wire_id(model_id) or ''
    statement = insert(SysConfig).values(
        key=key,
        name=name,
        value=value,
        type='Y',
        remark='手动选择的全局模型用途配置；空值表示不启用该处理。',
    )
    statement = statement.on_conflict_do_update(
        index_elements=[SysConfig.key],
        set_={'value': value, 'updated_at': datetime.now()},
    )
    try:
        await db.execute(statement)
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return {'modelId': wire_id(model_id)}
