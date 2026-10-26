import { ownedReports, sortByActivity } from '../../views/portal/utils/workspace.js'
import { getPortalReportPath, getPortalTaskPath, isDigestType } from '../../views/portal/utils/routing.js'

export function buildPersonalReports({ reports = [], tasks = [], userId } = {}) {
  const outputs = new Map(ownedReports(reports, tasks, userId).map(report => [String(report.id), report]))
  const completed = new Map(sortByActivity(tasks).filter(task => task.status === 'completed' && task.reportId != null).reverse().map(task => [String(task.reportId), task]))
  const taskPath = task => getPortalTaskPath({ ...task, type: task.reportType || task.type || '科研生成' })
  const rows = [...outputs.values()].map(report => {
    const task = completed.get(String(report.id))
    return { ...report, key: `report:${report.id}`, kind: 'report', status: 'generated', statusLabel: '已生成', businessStatus: report.status || '', hasOutput: true,
      typeLabel: isDigestType(report.reportType || report.type) ? '情报简报' : '科研报告',
      title: report.title || '未命名报告', path: getPortalReportPath(report), taskPath: task ? taskPath(task) : '',
      updatedAt: report.updatedAt || task?.updatedAt || '', requiresReview: Boolean(task?.requiresReview) }
  })
  for (const task of tasks) {
    if (task.status === 'completed' && outputs.has(String(task.reportId))) continue
    const status = ['failed', 'dead_letter'].includes(task.status) ? 'failed' : task.status === 'cancelled' ? 'cancelled' : task.status === 'completed' ? 'generated' : 'active'
    rows.push({ ...task, key: `task:${task.id}`, kind: 'task', status, hasOutput: false,
      statusLabel: ({ active: task.status === 'queued' ? '排队中' : '生成中', failed: '生成失败', cancelled: '已取消', generated: '已生成' })[status],
      typeLabel: isDigestType(task.reportType || task.type) ? '情报简报' : '科研报告',
      title: task.title || '未命名生成任务', path: taskPath(task),
      progress: Math.max(0, Math.min(100, Number(task.progress) || 0)) })
  }
  return sortByActivity(rows)
}
