export const ID_UPGRADE_NOTICE = '业务编号已升级，请重新选择资料或模板；已填写的表单和正文已保留。'
const MAX_ID = '9223372036854775807'

// IDs never pass through Number/parseInt: adjacent bigint values must stay distinct.
export function decimalId(value) {
  if (typeof value === 'number') {
    if (!Number.isSafeInteger(value) || value <= 0) return ''
    value = String(value)
  }
  if (typeof value !== 'string' || !/^[1-9]\d*$/.test(value)) return ''
  return value.length < MAX_ID.length || (value.length === MAX_ID.length && value <= MAX_ID) ? value : ''
}

export function requireBusinessId(value) {
  const id = decimalId(value)
  if (!id) throw Object.assign(new Error(ID_UPGRADE_NOTICE), { msg: ID_UPGRADE_NOTICE })
  return id
}

// Retain invalid legacy IDs for an explicit re-selection warning, never submit them.
export function displayId(value) { return decimalId(value) || (value == null ? '' : String(value)) }

const references = new Set(['itemId', 'item_id', 'templateId', 'template_id', 'templateKey', 'sourceId', 'source_id', 'reportId', 'report_id', 'jobId', 'job_id', 'taskId', 'task_id', 'runId', 'run_id', 'parentId', 'parent_id', 'categoryId', 'category_id', 'fileId', 'file_id', 'articleId', 'article_id', 'paperId', 'paper_id', 'assetId', 'asset_id', 'imageModelId', 'image_model_id', 'modelId', 'model_id', 'scheduleId', 'schedule_id'])

export function validateBusinessInput(value, entity = true) {
  if (!value || typeof value !== 'object' || (typeof FormData !== 'undefined' && value instanceof FormData)) return value
  if (Array.isArray(value)) return value.map(item => validateBusinessInput(item, false))
  if (Object.prototype.toString.call(value) !== '[object Object]') return value
  const result = { ...value }
  for (const [key, entry] of Object.entries(value)) {
    if (((entity && key === 'id') || references.has(key)) && entry != null && entry !== '') result[key] = requireBusinessId(entry)
    else if (key === 'selectedItemIds' || key === 'selected_item_ids') {
      result[key] = entry.map(item => typeof item === 'object' ? { ...item, id: requireBusinessId(item.id) } : requireBusinessId(item))
    } else result[key] = validateBusinessInput(entry, false)
  }
  return result
}

export function normalizeBusinessData(value) {
  if (Array.isArray(value)) return value.map(normalizeBusinessData)
  if (!value || typeof value !== 'object') return value
  const result = { ...value }
  for (const [key, entry] of Object.entries(value)) {
    if ((key === 'id' || references.has(key) || key === 'latestRunId' || key === 'latest_run_id') && entry != null) {
      if (typeof entry === 'number' && !Number.isSafeInteger(entry)) throw new Error('接口业务编号超出安全整数范围，请后端以十进制字符串返回')
      result[key] = displayId(entry)
    } else if (['data', 'rows', 'basket', 'favoriteItems', 'selectedItems', 'images'].includes(key)) result[key] = normalizeBusinessData(entry)
    else if (key === 'favorites') result[key] = entry.map(displayId)
  }
  return result
}
