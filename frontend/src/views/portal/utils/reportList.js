import { businessTimeInstant } from '../../../utils/portal/businessTime.js'

// Sorting must never mutate the shared store or turn unknown dates into "now".
export function sortResearchReports(reports, order = 'updated-desc') {
  const timestamp = item => {
    const value = businessTimeInstant(item.updatedAt || item.updated_at || '')
    return Number.isFinite(value) ? value : null
  }
  return [...reports].sort((a, b) => {
    if (order === 'title') return String(a.title || '').localeCompare(String(b.title || ''), 'zh-CN')
    const left = timestamp(a)
    const right = timestamp(b)
    if (left === null) return right === null ? 0 : 1
    if (right === null) return -1
    return order === 'updated-asc' ? left - right : right - left
  })
}
