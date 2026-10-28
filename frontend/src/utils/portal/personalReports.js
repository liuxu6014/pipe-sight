import { ownedReports, sortByActivity } from '../../views/portal/utils/workspace.js'
import { getPortalReportPath, getPortalTaskPath, isDigestType } from '../../views/portal/utils/routing.js'

export function hasReportOutput(report) {
  return Boolean(String(report?.content || '').trim()
    || (Array.isArray(report?.sections) && report.sections.some(section => String(section.content || '').trim())))
}

export function buildPersonalReports({ reports = [], tasks = [], userId } = {}) {
  const outputs = new Map(ownedReports(reports, tasks, userId).map(report => [String(report.id), report]))
  const completed = new Map(sortByActivity(tasks).filter(task => task.status === 'completed' && task.reportId != null).reverse().map(task => [String(task.reportId), task]))
  const taskPath = task => getPortalTaskPath({ ...task, type: task.reportType || task.type || '科研生成' })
  const rows = [...outputs.values()].flatMap(report => {
    const task = completed.get(String(report.id))
    // A completed task is evidence for legacy list DTOs that omit the body.
    // An explicitly empty body must never be promoted by that fallback.
    const hasOutput = hasReportOutput(report) || (report.content === undefined && !Array.isArray(report.sections) && Boolean(task))
    if (!hasOutput && tasks.some(item => String(item.reportId) === String(report.id))) return []
    const published = ['published', '已发布'].includes(report.status)
    return [{ ...report, key: `report:${report.id}`, kind: 'report', status: hasOutput ? (published ? 'published' : 'generated') : 'unavailable', statusLabel: hasOutput ? (published ? '已发布' : '已生成') : '暂无正文', businessStatus: report.status || '', hasOutput,
      typeLabel: isDigestType(report.reportType || report.type) ? '情报简报' : '科研报告',
      title: report.title || '未命名报告', path: hasOutput ? getPortalReportPath(report) : '', taskPath: task ? taskPath(task) : '',
      updatedAt: report.updatedAt || task?.updatedAt || '', requiresReview: Boolean(task?.requiresReview || report.requiresReview) }]
  })
  for (const task of tasks) {
    if (task.status === 'completed' && rows.some(row => row.kind === 'report' && row.hasOutput && String(row.id) === String(task.reportId))) continue
    const status = ['failed', 'dead_letter'].includes(task.status) ? 'failed' : task.status === 'cancelled' ? 'cancelled' : task.status === 'completed' ? 'generated' : 'active'
    rows.push({ ...task, key: `task:${task.id}`, kind: 'task', status, hasOutput: false,
      statusLabel: ({ active: task.status === 'queued' ? '排队中' : '生成中', failed: '生成失败', cancelled: '已取消', generated: '已生成' })[status],
      typeLabel: isDigestType(task.reportType || task.type) ? '情报简报' : '科研报告',
      title: task.title || '未命名生成任务', path: taskPath(task),
      progress: Math.max(0, Math.min(100, Number(task.progress) || 0)) })
  }
  return sortByActivity(rows)
}
