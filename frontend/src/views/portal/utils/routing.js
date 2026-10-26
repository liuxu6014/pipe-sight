import { decimalId } from '../../../utils/portal/businessId.js'

const digestTypes = new Set(['daily', 'weekly', 'monthly', '日报', '周报', '月报', '日报周报', '日报周月报', '情报简报', '日报生成', '周报生成', '月报生成'])
const researchTaskTypes = new Set([
  'research-demand',
  'technology-route',
  'project-demand',
  '科研生成',
  '日报周报',
  '日报周月报',
  '情报简报',
  '日报生成',
  '周报生成',
  '月报生成'
])

export function isDigestType(value) {
  return digestTypes.has(String(value || ''))
}

export function getPortalReportPath(report) {
  if (!decimalId(report?.id)) return '/portal/me/reports'
  const type = report.reportType || report.type
  return isDigestType(type) ? `/portal/digests/${report.id}` : `/portal/research/reports/${report.id}`
}

export function getPortalTaskPath(task) {
  if (!decimalId(task?.id)) return '/portal/me/reports'
  const type = task.reportType || task.type
  return researchTaskTypes.has(String(type || '')) || isDigestType(type)
    ? `/portal/research/tasks/${task.id}`
    : '/portal/me/reports'
}
