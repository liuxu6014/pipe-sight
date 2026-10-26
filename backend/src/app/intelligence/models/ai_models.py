"""后台统一模型配置，不持久化明文密钥。"""

from datetime import datetime, timezone

from sqlalchemy import JSON, BigInteger, Boolean, CheckConstraint, Column, Identity, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB

from app.business_ids import MAX_BIGINT
from app.business_time import BeijingAuditTime, audit_now, server_now
from config.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AiModels(Base):
    __tablename__ = 'ai_models'
    __table_args__ = (
        CheckConstraint("jsonb_typeof(capabilities)='array'", name='ck_ai_models_capabilities').ddl_if(
            dialect='postgresql'
        ),
        CheckConstraint("jsonb_typeof(parameters)='object'", name='ck_ai_models_parameters').ddl_if(
            dialect='postgresql'
        ),
    )
    id = Column(
        BigInteger,
        Identity(start=1, increment=1, minvalue=1, maxvalue=MAX_BIGINT, cycle=False, cache=1),
        primary_key=True,
    )
    name = Column(String(100), nullable=False)
    provider = Column(String(50), nullable=False)
    code = Column(String(100), nullable=False)
    base_url = Column(Text, nullable=False)
    credential_ref = Column(Text, nullable=False)
    capabilities = Column(JSON().with_variant(JSONB(), 'postgresql'), nullable=False)
    parameters = Column(
        JSON().with_variant(JSONB(), 'postgresql'), nullable=False, default=dict, server_default=text("'{}'")
    )
    is_enabled = Column(Boolean, nullable=False, default=True, server_default='true')
    created_at = Column(BeijingAuditTime(), nullable=False, default=audit_now, server_default=server_now())
    updated_at = Column(
        BeijingAuditTime(),
        nullable=False,
        default=audit_now,
        server_default=server_now(),
        onupdate=audit_now,
    )


__all__ = ['AiModels']
