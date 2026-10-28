export function reportRowActions(row) {
  if (!row?.path) return []
  if (row.kind === 'report') {
    if (!row.hasOutput) return []
    const research = row.path.startsWith('/portal/research/reports/')
    return [{ label: research ? '查看' : '查看简报', path: row.path },
      ...(research && !row.readOnly && row.status !== 'published'
        ? [{ label: '继续编辑', path: `${row.path}?mode=edit`, primary: true }] : [])]
  }
  return [{ label: ({ active: '查看进度', failed: '查看原因 / 重试', cancelled: '查看任务', generated: '查看结果' })[row.status] || '查看任务', path: row.path, primary: row.status === 'failed' }]
}

export function templatePreview(template) {
  const sections = (Array.isArray(template?.sections) ? template.sections : []).map((item, index) => ({
    number: index + 1, title: String(item.title || '未命名章节'),
    description: String(item.description || ''), words: Number.isFinite(Number(item.words)) && Number(item.words) > 0 ? Number(item.words) : 0,
  }))
  return { name: String(template?.name || '模板结构'), description: String(template?.description || ''), sections,
    words: sections.reduce((sum, item) => sum + item.words, 0),
    modelLabel: template?.modelConfigured === true ? '文本模型已就绪' : template?.modelConfigured === false ? '文本模型未就绪' : '文本模型状态待确认' }
}

function taskRow(item) {
  return { ...item, id: item.jobId || item.id, reportType: item.type,
    type: ['daily', 'weekly', 'monthly'].includes(item.type) ? '情报简报' : '科研生成',
    status: item.status || 'queued', progress: Math.max(0, Math.min(100, Number(item.progress) || 0)),
    updatedAt: item.updatedAt || item.updated_at || '' }
}

export function createResearchRefresh({ store, loadJobs, loadReports, waitForHydration }) {
  let pending, stopped = false, generation = 0
  return {
    run() {
      if (stopped) return Promise.resolve()
      if (pending) return pending
      const epoch = store.workspaceEpoch
      const sequence = generation
      pending = (async () => {
        if (store.dataLoading && waitForHydration) await waitForHydration()
        if (stopped || epoch !== store.workspaceEpoch || sequence !== generation) return
        const results = await Promise.allSettled([loadJobs(), loadReports()])
        if (stopped || epoch !== store.workspaceEpoch || sequence !== generation) return
        for (const [index, key] of ['tasks', 'reports'].entries()) {
          const result = results[index]
          const rows = result.status === 'fulfilled' ? result.value?.data?.rows : null
          const valid = Array.isArray(rows) && rows.every(item => item && typeof item === 'object' && !Array.isArray(item))
          store.sectionErrors[key] = valid ? '' : `${key === 'tasks' ? '任务' : '报告'}暂时无法更新，已保留原列表，请重试`
          if (valid && key === 'tasks') store.tasks = rows.map(taskRow)
          if (valid && key === 'reports') store.liveReports = rows
        }
        store.sectionErrors.digests = store.sectionErrors.reports
      })().finally(() => { pending = null })
      return pending
    },
    invalidate() { generation++ },
    stop() { stopped = true; generation++ },
  }
}
