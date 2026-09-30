from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from module_ai.entity.do.ai_chat_do import AiChatConfig
from module_ai.entity.vo.ai_chat_vo import AiChatConfigModel


class AiChatConfigDao:
    """
    AI对话配置数据库操作层
    """

    @classmethod
    async def get_chat_config_detail_by_user_id(cls, db: AsyncSession, user_id: int) -> AiChatConfig | None:
        ai_chat_config = (
            (await db.execute(select(AiChatConfig).where(AiChatConfig.user_id == user_id))).scalars().first()
        )
        return ai_chat_config

    @classmethod
    async def add_chat_config_dao(cls, db: AsyncSession, chat_config: AiChatConfigModel) -> AiChatConfig:
        db_chat_config = AiChatConfig(**chat_config.model_dump(exclude_unset=True))
        db.add(db_chat_config)
        await db.flush()
        return db_chat_config

    @classmethod
    async def edit_chat_config_dao(cls, db: AsyncSession, chat_config: dict) -> None:
        await db.execute(update(AiChatConfig), [chat_config])
