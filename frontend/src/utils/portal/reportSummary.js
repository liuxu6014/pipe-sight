import { getPortalReportPath, getPortalTaskPath, isDigestType } from '../../views/portal/utils/routing.js'

export function reportSummaryRow(row) {
  const status = row.listStatus || (row.hasOutput ? 'generated' : 'unavailable')
  const taskPath = row.jobId ? getPortalTaskPath({ id: row.jobId, type: row.reportType || row.type }) : ''
  return { ...row, key: `report:${row.id}`, kind: row.hasOutput ? 'report' : row.jobId ? 'task' : 'report',
    typeLabel: isDigestType(row.reportType || row.type) ? '情报简报' : '科研报告',
    status, statusLabel: ({ generated: '已生成', active: row.status === 'queued' ? '排队中' : '生成中', failed: '生成失败', cancelled: '已取消', unavailable: '暂无正文' })[status],
    path: row.hasOutput ? getPortalReportPath(row) : taskPath, taskPath,
    period: Array.isArray(row.period) ? row.period.join(' 至 ') : row.period,
  }
}
