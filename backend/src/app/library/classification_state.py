"""Classification state changes shared by API edits, parsing and worker results."""

CLASSIFICATION_CONSENT = 'consented'
SUPERSEDED_MESSAGE = '资料已更新，当前分类结束后可按最新正文重新提交'


def invalidate_classification(row) -> None:
    """Keep an in-flight call's token/capacity until that call settles."""
    row.category_id = None
    if row.classification_status == 'running' and row.classification_token:
        row.classification_error = SUPERSEDED_MESSAGE
    else:
        row.classification_status = 'not_configured'
        row.classification_error = None
        row.classification_token = None
