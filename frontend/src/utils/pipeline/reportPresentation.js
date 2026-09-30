const reportStatuses = {
  reviewing: { label: '审核中', type: 'warning' },
  draft: { label: '草稿', type: 'info' },
  planned: { label: '规划中', type: 'primary' }
}

export function formatReportDate(value) {
  const [year, month, day] = String(value || '').slice(0, 10).split('-')
  return year && month && day ? `${year}年${month}月${day}日` : '本期情报'
}

export function getReportStatusMeta(status) {
  return reportStatuses[status] || reportStatuses.draft
}
