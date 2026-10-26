from config.database import AsyncSessionLocal


def test_async_sessions_do_not_lazy_load_expired_attributes_after_commit() -> None:
    assert AsyncSessionLocal.kw['expire_on_commit'] is False
