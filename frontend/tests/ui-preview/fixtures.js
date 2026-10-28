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
  else if (name === 'listPipelineResearchReports') data = { rows: [{ ...report, id: '900040', ownerId: '7',
    type: 'research', reportType: 'research', requiresReview: false, generationWarning: '',
    content: sections.map(section => `## ${section.title}\n\n${section.content}`).join('\n\n') }] }
  else if (name === 'listPipelineResearchJobs') data = { rows: [
    { jobId: '900070', reportId: '900040', title: report.title, type: 'research', status: 'completed', progress: 100, updatedAt: '2026-10-27 09:00:00' },
    { jobId: '900071', reportId: '900041', title: '检测方法对比研究（合成任务）', type: 'research', status: 'running', progress: 45, updatedAt: '2026-10-27 09:05:00' },
    { jobId: '900072', reportId: '900042', title: '管网完整性研究（失败展示样本）', type: 'research', status: 'failed', progress: 20, updatedAt: '2026-10-27 09:03:00' },
  ] }
  else if (name === 'getPipelineWorkspace') data = { basket: [], favorites: [] }
  else if (name === 'listPipelineTemplates') data = { rows: (reportTemplates.length ? reportTemplates : [{ id: '900031', name: '项目需求报告（合成模板）', description: '仅用于预览章节结构，不执行生成。', modelConfigured: false }]).map((item, index) => ({ ...item, templateKey: item.id, category: 'research', purpose: 'research', code: `PREVIEW-${index + 1}`, version: 'V1.0（界面样本）', status: 'published', reportType: ['project-demand', 'research-demand', 'technology-route'][index], formats: ['docx'], usage: 0, updatedAt: '2026-10-06', sections: sections.map((section, sectionIndex) => ({ ...section, words: sectionIndex ? 500 : 800, description: '合成章节说明，不包含真实科研结论。' })) })) }
  else if (name === 'listPipelineSources') data = { rows: [{ id: 'preview-source', source_code: 'preview-only', name: '界面验收合成数据源（不执行采集）', type: 'news', status: 'enabled', enabled: true, frequency: '仅预览', last_run_time: '2026-10-06 10:00', success_rate: 100 }], total: 1 }
  else if (name === 'listPipelineIntelligence') {
    const params = args[0] || {}
    if (params.category === 'article' && params.sortBy === 'publication') {
      const candidates = Array.from({ length: 29 }, (_, index) => ({
        id: String(910001 + index), category: index % 2 ? 'wechat' : 'news',
        title: `管网监测资讯 ${String(index + 1).padStart(2, '0')}（合成候选）`,
        summary: '仅用于检索、分页和来源展示的合成摘要，不是真实采集资讯。',
        source: index % 2 ? '合成公众号' : '合成新闻网站', source_type: index % 2 ? 'wechat' : 'news',
        publish_time: '2026-10-27 10:00:00'
      })).filter(item => (!params.source_type || item.source_type === params.source_type) && (!params.keyword || `${item.title}${item.summary}`.includes(params.keyword)))
      const start = ((params.pageNum || 1) - 1) * (params.pageSize || 10)
      return { data: { rows: candidates.slice(start, start + (params.pageSize || 10)), total: candidates.length } }
    }
    const sourceLabel = { news: '新闻网站', wechat: '微信公众号' }[params.source_type]
    const rows = params.category === 'paper'
      ? paperItems.map(item => ({ ...item, title: item.titleZh, summary: item.abstract, open_access_status: 'open' }))
      : newsItems.filter(item => !sourceLabel || item.sourceType === sourceLabel)
    const start = ((params.pageNum || 1) - 1) * (params.pageSize || rows.length)
    data = { rows: rows.slice(start, start + (params.pageSize || rows.length)), total: rows.length }
  }
  else if (name === 'getPipelineIntelligenceDetail') data = args[0] === '900018' ? { ...newsItems[0], id: '900018', title: '管网检测动态（合成新闻）', source: '界面验收合成来源', content: '合成新闻正文，仅供界面验收，不构成真实资讯。' } : newsItems.find(item => item.id === args[0]) || { ...paperItems[0], title: paperItems[0].titleZh }
  else if (name === 'listPipelineKnowledgeDocuments') data = { rows: knowledgeDocuments, total: knowledgeDocuments.length }
  else if (name === 'getPipelineResearchReport') data = ['900050', '900051'].includes(args[0]) ? {
    ...report, id: args[0], reportType: 'weekly', type: '周报', readOnly: args[0] === '900050', requiresReview: false,
    title: args[0] === '900050' ? '管网科技情报周报（合成只读验收）' : '管网科技情报周报（合成导出记录验收）', period: '2026-10-19 至 2026-10-25',
    sections: [{ id: 1, title: '本期动态', content: '本段为界面验收的合成文本，不构成科研结论。引用可进入新闻详情页。[1]', words: 43, citationIds: [1], sources: 1 }],
    citations: [{ id: 1, sourceId: '900018', type: 'article', title: '管网检测动态（合成新闻）', source: { name: '界面验收合成来源' }, quote: '合成摘录，仅用于验证排版和来源入口。' }]
  } : args[0] === 'preview-digest' ? { ...report, id: 'preview-digest', reportType: 'weekly', type: '周报', title: '管网科技情报周报（界面测试）' }
    : args[0] === '900040' ? { ...report, id: '900040', requiresReview: false, generationWarning: '' } : report
  else if (name === 'listPipelineResearchReportExports') data = { rows: [
    { exportId: '900081', reportId: args[0], format: 'docx', status: 'completed', reportVersionNo: 1, createdAt: '2026-10-27 10:00:00' },
    { exportId: '900082', reportId: args[0], format: 'pdf', status: 'failed', reportVersionNo: 1, createdAt: '2026-10-27 10:01:00', errorMessage: '合成失败样例：排版服务暂时不可用，未执行真实导出。' }
  ] }
  else if (name === 'getPipelineResearchJob') data = {
    id: args[0], title: args[0] === '900072' ? '管网完整性研究（失败展示样本）' : report.title,
    status: args[0] === '900072' ? 'failed' : 'completed', progress: args[0] === '900072' ? 35 : 100,
    errorMessage: args[0] === '900072' ? '合成失败原因：文本生成服务暂时不可用，请核对模型配置后再重试。' : '',
    reportId: '900040', reportStatus: args[0] === '900072' ? 'draft' : 'completed', type: 'research', reportType: report.reportType,
    templateName: '项目需求报告（合成模板）', createdAt: '2026-10-27 09:00:00', updatedAt: '2026-10-27 09:03:00',
    attemptCount: 1, outline: sections.map(section => ({ ...section, words: 800 })),
    config: { templateId: 'template-02', templateVersion: 'V2.1', outline: sections }, selectedItems: [
      { id: '900026', type: 'paper', title: '管道监测技术综述（合成论文）', source: { journal: '界面测试期刊' } },
      { id: '900018', type: 'article', title: '管网检测动态（合成新闻）', source: { url: 'https://example.com/preview-only' } },
      { id: '900054', type: 'file', title: '检测方案（合成上传资料）', source: { filename: '检测方案-合成样本.docx' } }
    ],
    stages: taskStages.map((label, index) => ({ key: String(index), label, status: args[0] === '900072' ? index === 0 ? 'completed' : index === 1 ? 'failed' : 'skipped' : 'completed' })),
    logs: [{ time: '2026-10-27 09:03:00', type: args[0] === '900072' ? 'error' : 'success', message: '界面验收合成样例；未调用模型或业务接口。' }]
  }
  else if (!name.startsWith('list') && !name.startsWith('get')) throw new Error('合成数据预览不执行保存、生成、删除或导出操作。')
  return { data }
}
