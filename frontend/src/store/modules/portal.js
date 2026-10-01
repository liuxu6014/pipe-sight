import { defineStore } from 'pinia'
import { ElMessage } from 'element-plus'
import {
  digestReports as fallbackDigests,
  knowledgeDocuments as fallbackDocuments,
  newsItems as fallbackNews,
  paperItems as fallbackPapers,
  recentTasks,
  researchReports as fallbackReports,
  topics as fallbackTopics
} from '@/views/portal/data'
import {
  deletePipelineWorkspaceItem,
  getPipelineDashboard,
  getPipelineWorkspace,
  listPipelineIntelligence,
  listPipelineKnowledgeDocuments,
  listPipelineReports,
  listPipelineResearchJobs,
  listPipelineResearchReports,
  savePipelineWorkspaceItem
} from '@/api/pipeline/intelligence'

const demoDataEnabled = import.meta.env.VITE_PORTAL_DEMO_DATA === 'true'

function mergeById(fallbackRows, liveRows) {
  const liveMap = new Map(liveRows.map(item => [item.id, item]))
  const merged = fallbackRows.map(item => liveMap.has(item.id) ? { ...item, ...liveMap.get(item.id) } : item)
  const fallbackIds = new Set(fallbackRows.map(item => item.id))
  return [...merged, ...liveRows.filter(item => !fallbackIds.has(item.id))]
}

function resolveRows(fallbackRows, liveRows) {
  return demoDataEnabled ? mergeById(fallbackRows, liveRows) : liveRows
}

function normalizeSourceType(value) {
  return ({ news: '新闻网站', wechat: '微信公众号', paper: '论文数据库' })[value] || value || '公开来源'
}

export function normalizePortalIntelligence(item) {
  const publishTime = item.publish_time || item.publishTime || item.time || ''
  return {
    ...item,
    time: publishTime,
    publishTime,
    sourceUrl: item.source_url || item.sourceUrl || item.canonical_url || item.canonicalUrl || '',
    reviewStatus: item.review_status || item.reviewStatus || 'pending',
    sourceType: normalizeSourceType(item.source_type || item.sourceType),
    importance: Number(item.relevance || 0) >= 90 ? '重点' : '一般',
    category: item.category === 'wechat' || item.category === 'news' ? (item.tags?.[0] || '管网安全') : item.category,
    tags: item.tags || [],
    body: item.body || (item.content ? [item.content] : item.summary ? [item.summary] : [])
  }
}

export function normalizePortalPaper(item) {
  const row = normalizePortalIntelligence(item)
  return {
    ...row,
    titleZh: item.title,
    title: item.title,
    authors: item.authors || ['作者信息待补充'],
    institutions: item.institutions || ['来源数据库'],
    journal: item.journal || item.source || '论文数据库',
    year: Number(String(row.publishTime || '').slice(0, 4)) || new Date().getFullYear(),
    doi: item.doi || '待补充',
    access: item.access || (item.open_access_status === 'open' ? '开放获取' : '仅元数据'),
    citations: Number(item.citations ?? item.citation_count ?? 0),
    fullTextUrl: item.full_text_url || item.fullTextUrl || '',
    abstract: item.summary || '',
    keywords: item.tags || []
  }
}

function normalizeDocument(item) {
  return {
    ...item,
    name: item.name,
    type: item.type || '内部文献',
    format: item.format || item.name?.split('.').pop()?.toUpperCase() || 'DOCX',
    pages: Number(item.pages || 0),
    owner: item.owner || '平台知识库',
    permission: item.permission || '仅自己可见',
    allowDownload: item.allow_download !== false && item.allowDownload !== false,
    allowAiUse: item.allow_ai_use !== false && item.allowAiUse !== false,
    status: ({ indexed: '已解析', parsing: '解析中', queued: '待解析', planned: '待解析', failed: '解析失败' })[item.status] || item.status || '待解析',
    updatedAt: item.updated_at || item.updatedAt || '最近更新',
    summary: item.summary || item.scenario || '知识库资料',
    tags: item.tags || item.keywords || []
  }
}

function normalizeReport(item) {
  const typeMap = { daily: '日报', weekly: '周报', monthly: '月报', 'research-demand': '科研需求报告', 'technology-route': '技术路线报告', 'project-demand': '科技项目需求填报表' }
  const statusMap = { reviewing: '待修改', draft: '草稿', planned: '待生成', completed: '已完成' }
  return {
    ...item,
    reportType: item.reportType || item.type,
    type: typeMap[item.type] || item.type || '科研报告',
    status: statusMap[item.status] || item.status || '草稿',
    version: item.version || 'V1.0',
    progress: item.status === 'completed' ? 100 : item.status === 'reviewing' ? 88 : 20,
    updatedAt: item.updated_at || item.updatedAt || '最近更新',
    words: Number(item.words || 0),
    sources: Number(item.coverage || item.sources || 0),
    period: item.period || String(item.updated_at || '').slice(0, 10)
  }
}

async function loadAllPipelineIntelligence() {
  const pageSize = 100
  const first = await listPipelineIntelligence({ pageNum: 1, pageSize })
  const firstData = first?.data || {}
  const rows = Array.isArray(firstData.rows) ? firstData.rows : []
  const total = Number(firstData.total || rows.length)
  const pageCount = Math.ceil(total / pageSize)
  if (pageCount <= 1) return rows
  const rest = await Promise.all(
    Array.from({ length: pageCount - 1 }, (_, index) => listPipelineIntelligence({ pageNum: index + 2, pageSize }))
  )
  return rows.concat(rest.flatMap(result => Array.isArray(result?.data?.rows) ? result.data.rows : []))
}

function normalizeDigestReport(item) {
  const row = normalizeReport(item)
  const statusMap = { reviewing: '待审核', draft: '草稿', planned: '运行中', completed: '已完成' }
  return {
    ...row,
    title: item.title,
    status: statusMap[item.status] || row.status,
    period: item.period || String(item.updated_at || item.updatedAt || '').slice(0, 10)
  }
}

const usePortalStore = defineStore('portal-workspace', {
  state: () => ({
    basket: [],
    favorites: [],
    tasks: demoDataEnabled ? recentTasks.map(item => ({ ...item })) : [],
    taskPanelVisible: false,
    dashboard: null,
    liveIntelligence: [],
    liveDocuments: [],
    liveReports: [],
    dataLoading: false,
    dataLoaded: false,
    dataError: ''
  }),
  getters: {
    basketCount: state => state.basket.length,
    runningTaskCount: state => state.tasks.filter(item => ['queued', 'running', 'generating', 'retrieving'].includes(item.status)).length,
    isFavorite: state => id => state.favorites.includes(id),
    newsItems: state => resolveRows(fallbackNews, state.liveIntelligence.filter(item => item.category !== 'paper').map(normalizePortalIntelligence)),
    paperItems: state => resolveRows(fallbackPapers, state.liveIntelligence.filter(item => item.category === 'paper').map(normalizePortalPaper)),
    knowledgeDocuments: state => resolveRows(fallbackDocuments, state.liveDocuments.map(normalizeDocument)),
    researchReports: state => resolveRows(fallbackReports, state.liveReports.filter(item => !['daily', 'weekly', 'monthly'].includes(item.type)).map(normalizeReport)),
    digestReports: state => resolveRows(fallbackDigests, state.liveReports.filter(item => ['daily', 'weekly', 'monthly'].includes(item.type)).map(normalizeDigestReport)),
    hotTopics: state => {
      const liveTopics = state.dashboard?.hot_topics || state.dashboard?.hotTopics || []
      return liveTopics.length
        ? liveTopics.map(item => ({ ...item, trend: item.trend || '持续关注' }))
        : (demoDataEnabled ? fallbackTopics : [])
    },
    dashboardMetrics: state => state.dashboard?.metrics || [],
    hasLiveData: state => state.liveIntelligence.length > 0 || state.liveDocuments.length > 0 || state.liveReports.length > 0
  },
  actions: {
    async hydrate(force = false) {
      if (this.dataLoading || (this.dataLoaded && !force)) return
      this.dataLoading = true
      this.dataError = ''
      const results = await Promise.allSettled([
        getPipelineDashboard(),
        loadAllPipelineIntelligence(),
        listPipelineKnowledgeDocuments(),
        listPipelineReports(),
        getPipelineWorkspace(),
        listPipelineResearchJobs(),
        listPipelineResearchReports()
      ])
      const [dashboardResult, intelligenceResult, documentResult, reportResult, workspaceResult, jobResult, researchReportResult] = results
      if (dashboardResult.status === 'fulfilled') this.dashboard = dashboardResult.value?.data || null
      if (intelligenceResult.status === 'fulfilled') this.liveIntelligence = intelligenceResult.value || []
      if (documentResult.status === 'fulfilled') this.liveDocuments = documentResult.value?.data?.rows || []
      const reportRows = reportResult.status === 'fulfilled' ? reportResult.value?.data?.rows || [] : []
      const researchReportRows = researchReportResult.status === 'fulfilled' ? researchReportResult.value?.data?.rows || [] : []
      if (reportResult.status === 'fulfilled' || researchReportResult.status === 'fulfilled') {
        const reportsById = new Map([...reportRows, ...researchReportRows].map(item => [item.id, item]))
        this.liveReports = [...reportsById.values()]
      }
      if (workspaceResult.status === 'fulfilled') {
        this.basket = workspaceResult.value?.data?.basket || []
        this.favorites = workspaceResult.value?.data?.favorites || []
      }
      if (jobResult.status === 'fulfilled') {
        const liveTasks = (jobResult.value?.data?.rows || []).map(item => ({
          id: item.jobId || item.id,
          title: item.title,
          reportType: item.type,
          type: ['daily', 'weekly', 'monthly'].includes(item.type) ? '情报简报' : '科研生成',
          status: item.status || 'queued',
          statusLabel: item.statusLabel || (item.status === 'completed' ? '已完成' : '生成中'),
          progress: Number(item.progress || 0),
          updatedAt: item.updatedAt || '刚刚',
          reportId: item.reportId
        }))
        this.tasks = demoDataEnabled ? mergeById(recentTasks, liveTasks) : liveTasks
      }
      const failedCount = results.filter(item => item.status === 'rejected').length
      if (failedCount) {
        this.dataError = failedCount === results.length
          ? (demoDataEnabled ? '实时数据暂不可用，当前为显式演示模式' : '实时数据暂不可用，请检查后端服务')
          : `部分实时数据暂不可用（${failedCount}/${results.length}）`
      }
      this.dataLoaded = true
      this.dataLoading = false
    },
    reset() {
      this.basket = []
      this.favorites = []
      this.tasks = demoDataEnabled ? recentTasks.map(item => ({ ...item })) : []
      this.taskPanelVisible = false
      this.dashboard = null
      this.liveIntelligence = []
      this.liveDocuments = []
      this.liveReports = []
      this.dataLoading = false
      this.dataLoaded = false
      this.dataError = ''
    },
    resolveSavedItemType(id) {
      if (this.knowledgeDocuments.some(item => item.id === id)) return 'material'
      if (this.paperItems.some(item => item.id === id)) return 'paper'
      if (this.newsItems.some(item => item.id === id)) return 'article'
      if ([...this.researchReports, ...this.digestReports].some(item => item.id === id)) return 'report'
      return 'material'
    },
    addToBasket(item) {
      if (!item?.id || this.basket.some(entry => entry.id === item.id)) return false
      const entry = { id: item.id, title: item.title || item.titleZh || item.name, type: item.type || item.category || '资料' }
      this.basket.push(entry)
      savePipelineWorkspaceItem({ itemId: entry.id, itemType: this.resolveSavedItemType(entry.id), action: 'basket', title: entry.title, snapshot: entry }).catch(() => {
        this.basket = this.basket.filter(current => current.id !== entry.id)
        this.dataError = '资料篮保存失败，本次操作已撤销'
        ElMessage.error(this.dataError)
      })
      return true
    },
    removeFromBasket(id) {
      const removed = this.basket.find(item => item.id === id)
      this.basket = this.basket.filter(item => item.id !== id)
      deletePipelineWorkspaceItem('basket', id).catch(() => {
        if (removed && !this.basket.some(item => item.id === id)) this.basket.push(removed)
        this.dataError = '移除资料失败，资料已恢复到资料篮'
        ElMessage.error(this.dataError)
      })
    },
    clearBasket() {
      const previous = [...this.basket]
      this.basket = []
      Promise.allSettled(previous.map(item => deletePipelineWorkspaceItem('basket', item.id))).then(results => {
        const failedItems = previous.filter((item, index) => results[index].status === 'rejected')
        if (!failedItems.length) return
        this.basket = [...this.basket, ...failedItems.filter(item => !this.basket.some(current => current.id === item.id))]
        this.dataError = `${failedItems.length} 条资料移除失败，已恢复`
        ElMessage.error(this.dataError)
      })
    },
    toggleFavorite(id) {
      if (this.favorites.includes(id)) {
        this.favorites = this.favorites.filter(item => item !== id)
        deletePipelineWorkspaceItem('favorite', id).catch(() => {
          if (!this.favorites.includes(id)) this.favorites.push(id)
          this.dataError = '取消收藏失败，收藏状态已恢复'
          ElMessage.error(this.dataError)
        })
        return
      }
      this.favorites.push(id)
      const item = [...this.newsItems, ...this.paperItems, ...this.knowledgeDocuments, ...this.researchReports, ...this.digestReports].find(entry => entry.id === id)
      savePipelineWorkspaceItem({
        itemId: id,
        itemType: this.resolveSavedItemType(id),
        action: 'favorite',
        title: item?.title || item?.titleZh || item?.name || id,
        snapshot: {}
      }).catch(() => {
        this.favorites = this.favorites.filter(itemId => itemId !== id)
        this.dataError = '收藏保存失败，本次操作已撤销'
        ElMessage.error(this.dataError)
      })
    },
    openTaskPanel() {
      this.taskPanelVisible = true
    }
  }
})

export default usePortalStore
