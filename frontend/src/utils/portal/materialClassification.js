export function materialClassificationLabel(item = {}) {
  const state = item.classificationStatus || item.classification_status
  if (!['ready', '已解析', 'indexed'].includes(item.parseStatus || item.status)) return '待分类'
  return ({ queued: '等待分类', running: '分类中', completed: '未命中类别', failed: '分类失败', not_configured: '未分类' })[state] || '待分类'
}

export function canRetryMaterialClassification(item = {}) {
  return ['ready', '已解析', 'indexed'].includes(item.parseStatus || item.status)
    && ['failed', 'not_configured'].includes(item.classificationStatus || item.classification_status)
}
