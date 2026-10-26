import { newsItems, paperItems, knowledgeDocuments, reportTemplates, topics, taskStages } from '../../src/views/portal/data'

const sections = [
  { id: 1, title: '问题与必要性', content: '本内容为界面测试使用的合成文本，不构成科研结论。\n用于验证正文排版、章节导航、引用和编辑器工具栏在不同屏幕上的布局。', words: 78, citations: 1, citationIds: [1], status: 'complete' },
  { id: 2, title: '研究目标', content: '围绕资料发现、证据组织、研究成果编辑与导出建立清晰工作流程。所有内容仅用于界面预览。', words: 48, citations: 1, citationIds: [1], status: 'draft' }
]
const report = {
  id: 'preview-report', title: '管道应力监测科研需求报告（界面测试）', type: '科研需求报告', reportType: 'research-demand',
  version: 'V1.0', versionNo: 1, revision: 1, status: 'draft', words: 126, updatedAt: '2026-10-06 10:00',
  owner: '预览用户', sections, qualityIssues: [], requiresReview: true,
  generationWarning: '这是合成数据预览，不是模型生成成果。',
  citations: [{ id: 1, sourceId: 'news-001', type: '科技资讯', title: '应力监测方法对比（合成来源）', location: '界面测试样本', quote: '用于检查引用卡片的长文本换行与点击区域。' }]
}
const dashboard = {
  metrics: [{ label: '科技资讯', value: newsItems.length, unit: '条' }, { label: '论文资料', value: paperItems.length, unit: '篇' }, { label: '已解析资料', value: knowledgeDocuments.length, unit: '项' }, { label: '待审核内容', value: 0, unit: '条' }],
  hot_topics: topics, pending_reviews: [],
  collect_status: [{ name: '资料入库', status: 'success', value: 100 }, { name: '文本解析', status: 'success', value: 100 }, { name: '数据过滤', status: 'warning', value: 60 }]
}

export async function fixtureRequest(name, args = []) {
  let data = { rows: [], total: 0 }
  if (name === 'getPipelineDashboard') data = dashboard
  else if (name === 'getPipelineWorkspace') data = { basket: [], favorites: [] }
  else if (name === 'listPipelineTemplates') data = { rows: reportTemplates.map((item, index) => ({ ...item, templateKey: item.id, category: 'research', code: `PREVIEW-${index + 1}`, version: 'V1.0（界面样本）', status: 'published', reportType: ['project-demand', 'research-demand', 'technology-route'][index], formats: ['docx'], usage: 0, updatedAt: '2026-10-06', sections })) }
  else if (name === 'listPipelineSources') data = { rows: [{ id: 'preview-source', source_code: 'preview-only', name: '界面验收合成数据源（不执行采集）', type: 'news', status: 'enabled', enabled: true, frequency: '仅预览', last_run_time: '2026-10-06 10:00', success_rate: 100 }], total: 1 }
  else if (name === 'listPipelineIntelligence') {
    const params = args[0] || {}
    const sourceLabel = { news: '新闻网站', wechat: '微信公众号' }[params.source_type]
    const rows = params.category === 'paper'
      ? paperItems.map(item => ({ ...item, title: item.titleZh, summary: item.abstract, open_access_status: 'open' }))
      : newsItems.filter(item => !sourceLabel || item.sourceType === sourceLabel)
    const start = ((params.pageNum || 1) - 1) * (params.pageSize || rows.length)
    data = { rows: rows.slice(start, start + (params.pageSize || rows.length)), total: rows.length }
  }
  else if (name === 'getPipelineIntelligenceDetail') data = newsItems.find(item => item.id === args[0]) || { ...paperItems[0], title: paperItems[0].titleZh }
  else if (name === 'listPipelineKnowledgeDocuments') data = { rows: knowledgeDocuments, total: knowledgeDocuments.length }
  else if (name === 'getPipelineResearchReport') data = args[0] === 'preview-digest' ? { ...report, id: 'preview-digest', reportType: 'weekly', type: '周报', title: '管网科技情报周报（界面测试）' } : report
  else if (name === 'getPipelineResearchJob') data = {
    id: 'preview-task', title: report.title, status: 'completed', progress: 100, reportId: report.id, reportType: report.reportType,
    config: { templateId: 'template-02', templateVersion: 'V2.1', outline: sections }, selectedItems: [{ ...newsItems[0], type: 'article' }],
    stages: taskStages.map((label, index) => ({ key: String(index), label, status: 'completed' })),
    logs: [{ time: '10:00', type: 'success', message: '界面验收样例已就绪；未调用模型或业务接口。' }]
  }
  else if (!name.startsWith('list') && !name.startsWith('get')) throw new Error('合成数据预览不执行保存、生成、删除或导出操作。')
  return { data }
}
