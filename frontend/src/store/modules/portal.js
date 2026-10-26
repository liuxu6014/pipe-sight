import { defineStore } from 'pinia'
import { displayId, normalizeBusinessData, requireBusinessId } from '@/utils/portal/businessId'
import { formatBusinessTime } from '@/utils/portal/businessTime'
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
  getPipelineWorkspace,
  listPipelineIntelligence,
  listPipelineKnowledgeDocuments,
  listPipelineResearchJobs,
  listPipelineResearchReports,
  savePipelineWorkspaceItem
} from '@/api/pipeline/intelligence'

const demoDataEnabled = import.meta.env.VITE_PORTAL_DEMO_DATA === 'true'
let hydratePromise = null

const workspaceSnapshotFields = [
  'title', 'titleZh', 'name', 'summary', 'abstract', 'source', 'sourceType', 'category',
  'reportType', 'status', 'statusLabel', 'updatedAt', 'time', 'publishTime', 'journal',
  'year', 'authors', 'institutions', 'tags', 'permission', 'format', 'pages', 'owner',
  'sourceUrl', 'doi', 'publishedDate'
]

function mergeById(fallbackRows, liveRows) {
  const liveMap = new Map(liveRows.map(item => [item.id, item]))
  const merged = fallbackRows.map(item => liveMap.has(item.id) ? { ...item, ...liveMap.get(item.id) } : item)
  const fallbackIds = new Set(fallbackRows.map(item => item.id))
  return [...merged, ...liveRows.filter(item => !fallbackIds.has(item.id))]
}

function resolveRows(fallbackRows, liveRows) {
  return demoDataEnabled ? mergeById(fallbackRows, liveRows) : liveRows
}

function buildWorkspaceSnapshot(item) {
  return workspaceSnapshotFields.reduce((snapshot, field) => {
    if (item?.[field] !== undefined && item?.[field] !== null) snapshot[field] = item[field]
    return snapshot
  }, {})
}

function normalizeSourceType(value) {
  return ({ website: '新闻网站', news: '新闻网站', wechat: '微信公众号', paper: '论文数据库' })[value] || value || '公开来源'
}

export function normalizePortalIntelligence(item) {
  item = normalizeBusinessData(item)
  const publishTime = formatBusinessTime(item.publishedAt || item.published_at || item.publish_time || item.publishTime || item.time || '')
  return {
    ...item,
    time: publishTime,
    publishTime,
    sourceUrl: item.url || item.source_url || item.sourceUrl || item.canonical_url || item.canonicalUrl || '',
    sourceType: normalizeSourceType(item.source_type || item.sourceType),
    importance: Number(item.relevance || 0) >= 90 ? '重点' : '一般',
    category: item.category === 'wechat' || item.category === 'news' ? (item.categoryName || item.tags?.[0] || '未分类') : item.category,
    tags: item.tags || [],
    body: item.body || ((item.contentZh || item.content_zh || item.content) ? [item.contentZh || item.content_zh || item.content] : item.summary ? [item.summary] : [])
  }
}

export function normalizePortalPaper(item) {
  const row = normalizePortalIntelligence(item)
  const publishedDate = item.publishedDate || item.published_date || ''
  const publishedYear = publishedDate.slice(0, 4) || item.year || item.publication_year || item.publicationYear || String(row.publishTime || '').slice(0, 4)
  const { full_text, fullText, full_text_url, fullTextUrl, access, open_access_status, content, content_zh, contentZh, body, ...metadata } = row
  return {
    ...metadata,
    titleZh: item.titleZh || item.title_zh || item.title,
    title: item.title,
    authors: Array.isArray(item.authors) ? item.authors : item.authors ? [item.authors] : [],
    institutions: Array.isArray(item.institutions) ? item.institutions : [],
    journal: item.journal || item.source || '期刊未提供',
    publishedDate,
    year: publishedYear ? Number(publishedYear) || '年份待补充' : '年份待补充',
    doi: item.doi || '',
    citations: item.citations ?? item.citation_count ?? null,
    abstract: item.abstractZh || item.abstract_zh || item.abstract || item.summary || '',
    keywords: item.tags || []
  }
}

function normalizeDocument(item) {
  item = normalizeBusinessData(item)
  const permissionScope = item.permissionScope || item.permission_scope || (
    ['公开', '全员可见', 'public'].includes(item.permission) ? 'public' : 'private'
  )
  const scanStatus = item.scanStatus || item.scan_status || 'clean'
  const parseStatus = ({ ready: '已解析', indexed: '已解析', parsing: '解析中', queued: '待解析', planned: '待解析', failed: '解析失败' })[item.status] || item.status || '待解析'
  const status = ({ pending: '待安全扫描', quarantined: '已隔离', failed: '扫描失败' })[scanStatus] || parseStatus
  return {
    ...item,
    name: item.name,
    type: item.type || '内部文献',
    format: item.format || item.name?.split('.').pop()?.toUpperCase() || 'DOCX',
    pages: Number(item.pages || 0),
    owner: item.owner || '平台知识库',
    permissionScope,
    permission: permissionScope === 'public' ? '全员可见' : '仅自己可见',
    allowDownload: item.allow_download !== false && item.allowDownload !== false,
    allowAiUse: item.allow_ai_use !== false && item.allowAiUse !== false,
    status,
    updatedAt: item.updated_at || item.updatedAt || '最近更新',
    summary: item.summary || item.scenario || '知识库资料',
    tags: item.tags || item.keywords || []
  }
}

function normalizeReport(item) {
  item = normalizeBusinessData(item)
  const typeMap = { daily: '日报', weekly: '周报', monthly: '月报', 'research-demand': '科研需求报告', 'technology-route': '技术路线报告', 'project-demand': '科技项目需求填报表' }
  const statusMap = { reviewing: '审核中', draft: '待复核草稿', planned: '待生成', completed: '已完成', published: '已发布', archived: '已归档' }
  const requiresReview = Boolean(item.requiresReview) || ['draft', 'reviewing'].includes(item.status)
  return {
    ...item,
    reportType: item.reportType || item.type,
    type: typeMap[item.type] || item.type || '科研报告',
    status: statusMap[item.status] || item.status || '草稿',
    statusLabel: item.statusLabel || statusMap[item.status] || item.status || '草稿',
    requiresReview,
    generationMode: item.generationMode || item.metadata?.generationMode || '',
    generationWarning: item.generationWarning || item.metadata?.generationWarning || '',
    version: item.version || item.versionName || '版本待补充',
    progress: item.status === 'completed' ? 100 : item.status === 'reviewing' ? 88 : 20,
    updatedAt: item.updated_at || item.updatedAt || '最近更新',
    words: Number(item.words || 0),
    sources: Number(item.coverage || item.sources || 0),
    period: item.period || String(item.updated_at || '').slice(0, 10)
  }
}

async function loadInitialPipelineIntelligence() {
  const response = await listPipelineIntelligence({ category: 'article', pageNum: 1, pageSize: 20 })
  return Array.isArray(response?.data?.rows) ? response.data.rows : []
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
    workspaceEpoch: 0,
    basket: [],
    favorites: [],
    favoriteItems: [],
    tasks: demoDataEnabled ? recentTasks.map(item => ({ ...item })) : [],
    taskPanelVisible: false,
    dashboard: null,
    liveIntelligence: [],
    liveDocuments: [],
    liveReports: [],
    dataLoading: false,
    dataLoaded: false,
    dataError: '',
    sectionErrors: {}
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
      if (this.dataLoading) return hydratePromise
      if (this.dataLoaded && !force) return
      this.dataLoading = true
      this.dataError = ''
      const epoch = this.workspaceEpoch
      const request = (async () => {
        const results = await Promise.allSettled([
          listPipelineIntelligence({ category: 'paper', pageNum: 1, pageSize: 20 }),
          loadInitialPipelineIntelligence(),
          listPipelineKnowledgeDocuments(),
          getPipelineWorkspace(),
          listPipelineResearchJobs(),
          listPipelineResearchReports()
        ])
        if (epoch !== this.workspaceEpoch) return
        const [paperResult, intelligenceResult, documentResult, workspaceResult, jobResult, researchReportResult] = results
        const sectionNames = ['papers', 'news', 'documents', 'workspace', 'tasks', 'reports']
        this.sectionErrors = Object.fromEntries(results.map((result, index) => [
          sectionNames[index], result.status === 'rejected' ? '服务暂时无法加载，请重试' : ''
        ]))
        const previousPapers = this.liveIntelligence.filter(item => item.category === 'paper')
        const previousArticles = this.liveIntelligence.filter(item => item.category !== 'paper')
        this.liveIntelligence = [
          ...(paperResult.status === 'fulfilled' ? paperResult.value?.data?.rows || [] : previousPapers),
          ...(intelligenceResult.status === 'fulfilled' ? intelligenceResult.value || [] : previousArticles)
        ]
        if (documentResult.status === 'fulfilled') this.liveDocuments = documentResult.value?.data?.rows || []
        if (researchReportResult.status === 'fulfilled') this.liveReports = researchReportResult.value?.data?.rows || []
        this.sectionErrors.digests = this.sectionErrors.reports
        if (workspaceResult.status === 'fulfilled') {
          this.basket = normalizeBusinessData(workspaceResult.value?.data?.basket || [])
          this.favorites = (workspaceResult.value?.data?.favorites || []).map(displayId)
          this.favoriteItems = normalizeBusinessData(workspaceResult.value?.data?.favoriteItems || [])
        }
        if (jobResult.status === 'fulfilled') {
          const liveTasks = (jobResult.value?.data?.rows || []).map(item => ({
            id: item.jobId || item.id,
            title: item.title,
            reportType: item.type,
            type: ['daily', 'weekly', 'monthly'].includes(item.type) ? '情报简报' : '科研生成',
            status: item.status || 'queued',
            statusLabel: item.statusLabel || ({ completed: '生成完成', failed: '生成失败', cancelled: '已取消', queued: '排队中', running: '生成中' })[item.status] || '状态待确认',
            progress: Number(item.progress || 0),
            updatedAt: item.updatedAt || item.updated_at || '更新时间待补充',
            reportId: item.reportId,
            reportStatus: item.reportStatus || '',
            requiresReview: Boolean(item.requiresReview),
            generationMode: item.generationMode || '',
            generationWarning: item.generationWarning || ''
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
      })()
      hydratePromise = request
      try {
        return await request
      } finally {
        if (hydratePromise === request) hydratePromise = null
        if (epoch === this.workspaceEpoch) this.dataLoading = false
      }
    },
    reset() {
      this.workspaceEpoch += 1
      hydratePromise = null
      this.basket = []
      this.favorites = []
      this.favoriteItems = []
      this.tasks = demoDataEnabled ? recentTasks.map(item => ({ ...item })) : []
      this.taskPanelVisible = false
      this.dashboard = null
      this.liveIntelligence = []
      this.liveDocuments = []
      this.liveReports = []
      this.dataLoading = false
      this.dataLoaded = false
      this.dataError = ''
      this.sectionErrors = {}
    },
    resolveSavedItemType(id) {
      id = displayId(id)
      if (this.knowledgeDocuments.some(item => item.id === id)) return 'material'
      if (this.paperItems.some(item => item.id === id)) return 'paper'
      if (this.newsItems.some(item => item.id === id)) return 'article'
      if ([...this.researchReports, ...this.digestReports].some(item => item.id === id)) return 'report'
      return 'material'
    },
    addToBasket(item) {
      try { item = { ...item, id: requireBusinessId(item?.id) } } catch (error) { ElMessage.error(error.message); return false }
      if (!item?.id || this.basket.some(entry => entry.id === item.id)) return false
      const epoch = this.workspaceEpoch
      const entry = { id: item.id, title: item.title || item.titleZh || item.name, type: item.type || item.category || '资料' }
      this.basket.push(entry)
      savePipelineWorkspaceItem({ itemId: entry.id, itemType: this.resolveSavedItemType(entry.id), action: 'basket', title: entry.title, snapshot: entry }).catch(() => {
        if (epoch !== this.workspaceEpoch) return
        this.basket = this.basket.filter(current => current.id !== entry.id)
        this.dataError = '资料篮保存失败，本次操作已撤销'
        ElMessage.error(this.dataError)
      })
      return true
    },
    removeFromBasket(id) {
      try { id = requireBusinessId(id) } catch (error) { ElMessage.error(error.message); return false }
      const epoch = this.workspaceEpoch
      const removed = this.basket.find(item => item.id === id)
      this.basket = this.basket.filter(item => item.id !== id)
      deletePipelineWorkspaceItem('basket', id).catch(() => {
        if (epoch !== this.workspaceEpoch) return
        if (removed && !this.basket.some(item => item.id === id)) this.basket.push(removed)
        this.dataError = '移除资料失败，资料已恢复到资料篮'
        ElMessage.error(this.dataError)
      })
    },
    clearBasket() {
      try { this.basket.forEach(item => requireBusinessId(item.id)) } catch (error) { ElMessage.error(error.message); return false }
      const epoch = this.workspaceEpoch
      const previous = [...this.basket]
      this.basket = []
      Promise.allSettled(previous.map(item => deletePipelineWorkspaceItem('basket', item.id))).then(results => {
        if (epoch !== this.workspaceEpoch) return
        const failedItems = previous.filter((item, index) => results[index].status === 'rejected')
        if (!failedItems.length) return
        this.basket = [...this.basket, ...failedItems.filter(item => !this.basket.some(current => current.id === item.id))]
        this.dataError = `${failedItems.length} 条资料移除失败，已恢复`
        ElMessage.error(this.dataError)
      })
    },
    toggleFavorite(id) {
      try { id = requireBusinessId(id) } catch (error) { ElMessage.error(error.message); return false }
      const epoch = this.workspaceEpoch
      if (this.favorites.includes(id)) {
        const removed = this.favoriteItems.find(item => item.id === id)
        this.favorites = this.favorites.filter(item => item !== id)
        this.favoriteItems = this.favoriteItems.filter(item => item.id !== id)
        deletePipelineWorkspaceItem('favorite', id).catch(() => {
          if (epoch !== this.workspaceEpoch) return
          if (!this.favorites.includes(id)) this.favorites.push(id)
          if (removed && !this.favoriteItems.some(item => item.id === id)) this.favoriteItems.push(removed)
          this.dataError = '取消收藏失败，收藏状态已恢复'
          ElMessage.error(this.dataError)
        })
        return
      }
      this.favorites.push(id)
      const item = [...this.newsItems, ...this.paperItems, ...this.knowledgeDocuments, ...this.researchReports, ...this.digestReports].find(entry => entry.id === id)
      const snapshot = buildWorkspaceSnapshot(item)
      this.favoriteItems.push({ ...snapshot, id, title: item?.title || item?.titleZh || item?.name || id, type: this.resolveSavedItemType(id) })
      savePipelineWorkspaceItem({
        itemId: id,
        itemType: this.resolveSavedItemType(id),
        action: 'favorite',
        title: item?.title || item?.titleZh || item?.name || id,
        snapshot
      }).catch(() => {
        if (epoch !== this.workspaceEpoch) return
        this.favorites = this.favorites.filter(itemId => itemId !== id)
        this.favoriteItems = this.favoriteItems.filter(savedItem => savedItem.id !== id)
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
