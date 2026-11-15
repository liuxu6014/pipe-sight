"""Bounded processing diagnostics, safe for administrator UI and logs."""

PROCESSING_ERRORS = {
    'processing_input_invalid': '文章标题或正文格式无效',
    'processing_input_missing': '缺少论文摘要或新闻正文，无法依据原文处理；请检查来源采集配置',
    'processing_input_limit': '文章内容超过处理上限',
    'processing_model_unavailable': '内容处理模型不可用或身份已变化',
    'processing_model_call_failed': '内容处理模型调用失败或超时',
    'processing_response_invalid': '模型响应为空、格式无效或超过大小限制',
    'processing_json_invalid': '模型未返回合法且字段唯一的 JSON 对象',
    'processing_filter_invalid': '模型缺少有效的过滤结论',
    'processing_exclusion_invalid': '排除结论缺少原文证据',
    'processing_category_invalid': '分类标识或名称不在启用类别范围内',
    'processing_entities_invalid': '核心实体数组缺失或超出类型、数量限制',
    'processing_summary_invalid': '摘要缺失、非中文或长度不符合要求',
    'processing_failed': '请检查内容处理模型及类别规则',
}


def processing_failure_message(code) -> str:
    # Never echo arbitrary candidate/provider values into a persisted message.
    code = code if isinstance(code, str) and code in PROCESSING_ERRORS else 'processing_failed'
    return f'候选条目处理失败（{code}）：{PROCESSING_ERRORS[code]}；请检查后重新试采'
