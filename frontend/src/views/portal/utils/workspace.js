import { businessTimeInstant, formatBusinessTime } from '../../../utils/portal/businessTime.js'

export function sortByActivity(items = []) {
  const timestamp = item => {
    const value = String(item.updatedAt || item.updated_at || item.publishTime || item.time || '')
    return businessTimeInstant(value) || 0
  }
  return [...items].sort((a, b) => timestamp(b) - timestamp(a))
}

export function unfinishedTasks(tasks = []) {
  return sortByActivity(tasks.filter(task => !['completed', 'cancelled'].includes(task.status)))
}

export function ownedReports(reports = [], tasks = [], userId) {
  const reportIds = new Set(tasks.map(task => task.reportId).filter(Boolean))
  return sortByActivity(reports.filter(report => reportIds.has(report.id)
    || (userId != null && String(userId) !== '' && String(report.ownerId ?? report.userId ?? '') === String(userId))))
}

export function publicationDate(value) {
  const match = formatBusinessTime(value).match(/^(\d{4}(?:-\d{2}(?:-\d{2})?)?)/)
  return match?.[1] || '日期未提供'
}

export function periodOverlaps(report, range) {
  if (!range?.length) return true
  const period = report.metadata?.period || report.period || ''
  const dates = (Array.isArray(period) ? period.join(' ') : String(period)).match(/\d{4}-\d{2}-\d{2}/g) || []
  if (!dates.length) return false
  return dates[0] <= range[1] && dates[dates.length - 1] >= range[0]
}
