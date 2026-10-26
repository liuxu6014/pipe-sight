import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { setTimeout as delay, setImmediate } from 'node:timers/promises'
import { formatBusinessTime } from '../src/utils/portal/businessTime.js'
import { normalizeBusinessData } from '../src/utils/portal/businessId.js'
import * as vue from 'vue'
import { createMemoryHistory, createRouter, useRoute, useRouter } from 'vue-router'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'
import { materialBasketReason, readListQuery, useListQuery, useListRequest, useListWorkspace, validPage } from '../src/utils/portal/listQuery.js'
import { ownedReports, unfinishedTasks, publicationDate, periodOverlaps } from '../src/views/portal/utils/workspace.js'
import { useBasketSelection } from '../src/utils/portal/basketSelection.js'
import { useBasketParsing } from '../src/utils/portal/basketParsing.js'
import { basketItemLabel, basketItemPath, uploadBasketFile, validateBasketUpload } from '../src/utils/portal/basketItems.js'
import { cleanSummary, cleanResultMeta, combineLatest, newsDate, resultPath } from '../src/utils/portal/discovery.js'
import { buildPersonalReports } from '../src/utils/portal/personalReports.js'
import { sortResearchReports } from '../src/views/portal/utils/reportList.js'

const read = path => readFileSync(new URL(path, import.meta.url), 'utf8')
const normalizerSource = read('../src/store/modules/portal.js')
const normalizers = new Function('normalizeBusinessData', 'formatBusinessTime', `${normalizerSource.slice(normalizerSource.indexOf('function normalizeSourceType'), normalizerSource.indexOf('function normalizeDocument')).replaceAll('export function', 'function')}; return { normalizePortalIntelligence, normalizePortalPaper }`)(normalizeBusinessData, formatBusinessTime)
const names = ['NewsListView', 'PaperListView', 'KnowledgeView', 'SearchView']
const sources = Object.fromEntries(names.map(name => [name, read(`../src/views/portal/pages/${name}.vue`)]))
sources.HomeView = read('../src/views/portal/pages/HomeView.vue')
sources.ResearchWorkbenchView = read('../src/views/portal/pages/ResearchWorkbenchView.vue')
sources.DigestListView = read('../src/views/portal/pages/DigestListView.vue')
sources.MyWorkspaceView = read('../src/views/portal/pages/MyWorkspaceView.vue')
const paths = { NewsListView: '/portal/news', PaperListView: '/portal/papers', KnowledgeView: '/portal/knowledge', SearchView: '/portal/search' }
paths.HomeView = '/portal'
paths.ResearchWorkbenchView = '/portal/research'
paths.DigestListView = '/portal/digests'
paths.MyWorkspaceView = '/portal/basket'
const deferred = () => { let resolve, reject; const promise = new Promise((a, b) => { resolve = a; reject = b }); return { promise, resolve, reject } }
const settle = async () => { await vue.nextTick(); await setImmediate(); await vue.nextTick() }

// Run each real SFC setup with Vue lifecycle and a memory router, without a DOM
// or browser. Network responses are controlled so races and failures are repeatable.
async function mountPage(name, { query = {}, api = {}, documents = [], pageProps = {}, timers = {} } = {}) {
  const messages = []
  const store = vue.reactive({
    workspaceEpoch: 0, basket: [], favorites: [], favoriteItems: [],
    liveDocuments: documents, get knowledgeDocuments() { return this.liveDocuments }, set knowledgeDocuments(rows) { this.liveDocuments = rows }, dataLoading: false, dataLoaded: true, dataError: '',
    researchReports: [], digestReports: [], tasks: [], sectionErrors: {},
    get basketCount() { return this.basket.length },
    isFavorite(id) { return this.favorites.includes(id) },
    async hydrate() {}
  })
  const empty = async () => ({ data: { rows: [], total: 0 } })
  const injected = {
    ...vue, useRoute, useRouter, ...normalizers,
    openPortalContent: (router, path) => router.push(path),
    useListQuery, useListRequest, useListWorkspace, validPage, materialBasketReason, cleanSummary, cleanResultMeta, combineLatest, newsDate, resultPath,
    usePortalStore: () => store, periodOverlaps, useBasketSelection, useBasketParsing,
    basketItemLabel, basketItemPath, uploadBasketFile, validateBasketUpload, Tickets: {},
    useUserStore: () => ({ id: 7 }), ownedReports, unfinishedTasks, publicationDate, buildPersonalReports, sortResearchReports,
    getPortalReportPath: item => `/portal/research/reports/${item.id}`, getPortalTaskPath: item => `/portal/research/tasks/${item.id}`,
    PortalPageHeader: {}, PortalEmptyState: {},
    ElMessage: Object.fromEntries(['success', 'error', 'warning'].map(level => [level, text => messages.push({ level, text })])),
    ElMessageBox: { confirm: async () => {} },
    ...Object.fromEntries(['Collection', 'ChatDotRound', 'Document', 'DocumentAdd', 'Reading', 'Plus', 'Refresh', 'ArrowRight', 'Grid', 'List', 'Search', 'Star', 'StarFilled', 'Filter', 'Close', 'MoreFilled', 'UploadFilled', 'WarningFilled', 'InfoFilled'].map(icon => [icon, {}])),
    listPipelineIntelligence: empty, searchPipelineIntelligence: empty, getPipelinePortalOverview: empty,
    listPipelineTemplates: empty, listPipelineDigestSchedules: empty,
    exportPipelineResearchReport: empty, deletePipelineDigestSchedule: empty, runPipelineDigestSchedule: empty, updatePipelineDigestSchedule: empty,
    savePipelineWorkspaceItem: empty, deletePipelineWorkspaceItem: empty,
    deletePipelineKnowledgeDocument: empty, reparsePipelineKnowledgeDocument: empty, uploadPipelineKnowledgeDocument: empty, listPipelineKnowledgeDocuments: empty,
    ...api, ...timers
  }
  const { descriptor } = parse(sources[name])
  const script = compileScript(descriptor, { id: name }).content
    .replace(/^import[\s\S]*?from ['"][^'"]+['"];?\n?/gm, '')
    .replace('export default', 'return')
  const dependencies = Object.entries(injected).filter(([key]) => key !== 'default' && key !== 'module.exports')
  const component = new Function(...dependencies.map(([key]) => key), script)(...dependencies.map(([, value]) => value))
  let bindings
  const setup = component.setup
  component.setup = (props, context) => { bindings = setup(props, context); return bindings }
  component.render = () => vue.h('div')
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: paths[name], component, props: pageProps }, { path: '/:rest(.*)*', component: { render: () => null } }] })
  const node = type => ({ type, children: [], parent: null })
  const renderer = vue.createRenderer({
    createElement: node, createText: node, createComment: node,
    setText() {}, setElementText() {}, patchProp() {},
    parentNode: child => child.parent, nextSibling: () => null,
    insert(child, parent) { child.parent = parent; parent.children.push(child) },
    remove(child) { if (child.parent) child.parent.children = child.parent.children.filter(item => item !== child) }
  })
  const app = renderer.createApp({ render: () => vue.h(vue.resolveComponent('RouterView')) }).use(router)
  await router.push({ path: paths[name], query })
  app.mount(node('root'))
  await settle()
  return { get page() { return bindings }, store, router, messages, close: () => app.unmount() }
}

test('knowledge parsing automatically refreshes without resetting controls and stops when complete', async () => {
  const timers = new Map()
  let token = 0
  let rows = Array.from({ length: 25 }, (_, i) => ({ id: `doc-${i}`, name: `资料${i}`, status: i === 0 ? '解析中' : '已解析', type: '内部文献' }))
  const ctx = await mountPage('KnowledgeView', { documents: rows, query: { q: '资料', page: '2' }, timers: {
    setTimeout: (callback, ms) => { assert.equal(ms, 3000); timers.set(++token, callback); return token }, clearTimeout: id => timers.delete(id)
  }, api: { listPipelineKnowledgeDocuments: async () => ({ data: { rows } }) } })
  try {
    assert.equal(timers.size, 1)
    rows = rows.map(row => ({ ...row, status: '已解析' }))
    const [id, callback] = timers.entries().next().value
    timers.delete(id); callback(); await settle()
    assert.equal(ctx.page.documents.value[0].status, '已解析')
    assert.equal(ctx.page.currentPage.value, 2)
    assert.equal(ctx.page.keyword.value, '资料')
    assert.equal(timers.size, 0)
  } finally { ctx.close() }
})

test('knowledge retry is single-flight and immediately resumes tracking', async () => {
  const doc = { id: 'doc', name: '失败资料', status: '解析失败', canManage: true }
  const pending = deferred()
  let calls = 0
  const ctx = await mountPage('KnowledgeView', { documents: [doc], api: {
    reparsePipelineKnowledgeDocument: async () => { calls++; return pending.promise }
  } })
  try {
    const retry = ctx.page.reparse(doc)
    await ctx.page.reparse(doc)
    assert.equal(calls, 1)
    pending.resolve({ data: { ...doc, status: '解析中', parseStatus: 'queued' } })
    await retry
    assert.equal(ctx.page.documents.value[0].status, '解析中')
    assert.equal(ctx.page.isReparsing('doc'), false)
    assert.ok(ctx.messages.some(message => message.text === '已提交重新解析'))
  } finally { ctx.close() }
})

test('knowledge refresh retains documents on failure and ignores results after unmount', async () => {
  let fail = true
  const pending = deferred()
  const doc = { id: 'doc', name: '资料', status: '解析中' }
  const ctx = await mountPage('KnowledgeView', { documents: [doc], api: {
    listPipelineKnowledgeDocuments: async () => { if (fail) throw new Error('离线'); return pending.promise }
  } })
  try {
    await ctx.page.refreshParsingDocuments()
    assert.equal(ctx.page.documents.value[0].status, '解析中')
    assert.match(ctx.page.parsingRefreshError.value, /自动重试/)
    fail = false
    const refresh = ctx.page.refreshParsingDocuments()
    ctx.close()
    pending.resolve({ data: { rows: [{ ...doc, status: '已解析' }] } })
    await refresh
    assert.equal(ctx.store.liveDocuments[0].status, '解析中')
  } finally { ctx.close() }
})

test('knowledge retry respects ownership and leaves failed documents retryable after a server failure', async () => {
  const doc = { id: 'doc', name: '失败资料', status: '解析失败' }
  let calls = 0
  const ctx = await mountPage('KnowledgeView', { documents: [doc], api: {
    reparsePipelineKnowledgeDocument: async () => { calls++; throw { msg: '解析服务暂不可用' } }
  } })
  try {
    await ctx.page.reparse({ ...doc, canManage: false })
    assert.equal(calls, 0)
    await ctx.page.reparse(doc)
    assert.equal(ctx.page.isReparsing('doc'), false)
    assert.equal(ctx.page.documents.value[0].status, '解析失败')
    assert.ok(ctx.messages.some(message => message.text === '解析服务暂不可用'))
    await ctx.page.reparse(doc)
    assert.equal(calls, 2)
  } finally { ctx.close() }
})

test('knowledge refresh cannot overwrite a newer retry with an older list response', async () => {
  const doc = { id: 'doc', name: '资料', status: '解析中' }
  const pending = deferred()
  const ctx = await mountPage('KnowledgeView', { documents: [doc], api: {
    listPipelineKnowledgeDocuments: async () => pending.promise,
    reparsePipelineKnowledgeDocument: async () => ({ data: { ...doc, status: '待解析' } })
  } })
  try {
    const refresh = ctx.page.refreshParsingDocuments()
    await ctx.page.reparse(doc)
    pending.resolve({ data: { rows: [{ ...doc, status: '解析失败' }] } })
    await refresh
    assert.equal(ctx.page.documents.value[0].status, '待解析')
  } finally { ctx.close() }
})

test('server lists default to ten, support twenty and fifty, and discard the old five-item size', async () => {
  for (const name of ['NewsListView', 'PaperListView', 'SearchView']) {
    const calls = []
    const request = async params => { calls.push(params); return { data: { rows: [], total: 130 } } }
    const ctx = await mountPage(name, { query: { size: '5' }, api: { listPipelineIntelligence: request, searchPipelineIntelligence: request } })
    try {
      assert.equal(ctx.page.pageSize.value, 10)
      assert.equal(calls.at(-1).pageSize, 10)
      for (const size of [20, 50]) {
        ctx.page.currentPage.value = 2; await settle()
        ctx.page.pageSize.value = size; await settle()
        assert.equal(calls.at(-1).pageSize, size)
        assert.equal(calls.at(-1).pageNum, 1)
      }
    } finally { ctx.close() }
  }
})

test('research reports use the selected page size and reset or clamp their page', async () => {
  const ctx = await mountPage('ResearchWorkbenchView')
  try {
    ctx.store.researchReports = Array.from({ length: 25 }, (_, i) => ({ id: `r${i}`, ownerId: 7, title: `报告${i}`, type: '科研报告' }))
    await settle()
    assert.equal(ctx.page.pagedReports.value.length, 10)
    ctx.page.currentPage.value = 3; await settle()
    assert.equal(ctx.page.pagedReports.value.length, 5)
    ctx.page.pageSize.value = 20; await settle()
    assert.equal(ctx.page.currentPage.value, 1)
    assert.equal(ctx.page.pagedReports.value.length, 20)
    ctx.page.pageSize.value = 50; await settle()
    assert.equal(ctx.page.pagedReports.value.length, 25)
  } finally { ctx.close() }
})

test('home inline search sends the selected size and resets its page on size change', async () => {
  const calls = []
  const ctx = await mountPage('HomeView', { api: { searchPipelineIntelligence: async params => { calls.push(params); return { data: { rows: [], total: 130 } } } } })
  try {
    ctx.page.keyword.value = '管网'; ctx.page.submitSearch(); await delay(280); await settle()
    assert.equal(calls.at(-1).pageSize, 10)
    for (const size of [20, 50]) {
      ctx.page.searchPage.value = 2; await settle()
      ctx.page.searchPageSize.value = size; await settle()
      assert.equal(calls.at(-1).pageSize, size)
      assert.equal(calls.at(-1).pageNum, 1)
    }
  } finally { ctx.close() }
})

test('digest reports and schedules paginate separately and reset on tab changes', async () => {
  const ctx = await mountPage('DigestListView')
  try {
    ctx.store.digestReports = Array.from({ length: 25 }, (_, i) => ({ id: `d${i}`, title: `简报${i}`, type: '日报' }))
    ctx.page.schedules.value = Array.from({ length: 23 }, (_, i) => ({ id: `s${i}`, name: `计划${i}` }))
    await settle()
    assert.equal(ctx.page.pagedReports.value.length, 10)
    ctx.page.currentPage.value = 3; await settle()
    assert.equal(ctx.page.pagedReports.value.length, 5)
    ctx.page.activeTab.value = '自动任务'; await settle()
    assert.equal(ctx.page.currentPage.value, 1)
    assert.equal(ctx.page.listTotal.value, 23)
    ctx.page.pageSize.value = 20; await settle()
    assert.equal(ctx.page.pagedSchedules.value.length, 20)
    ctx.page.currentPage.value = 2; await settle()
    ctx.page.schedules.value = ctx.page.schedules.value.slice(0, 10); await settle()
    assert.equal(ctx.page.currentPage.value, 1)
    ctx.page.pageSize.value = 50; await settle()
    assert.equal(ctx.page.pagedSchedules.value.length, 10)
  } finally { ctx.close() }
})

test('basket pagination preserves selected materials across pages and clamps after removal', async () => {
  const ctx = await mountPage('MyWorkspaceView', { pageProps: { mode: 'basket' } })
  try {
    ctx.store.basket = Array.from({ length: 25 }, (_, i) => ({ id: `b${i}`, title: `资料${i}`, type: 'article' }))
    await settle()
    assert.equal(ctx.page.pagedItems.value.length, 10)
    ctx.page.basketSelection.toggle('b0', true)
    ctx.page.currentPage.value = 3; await settle()
    assert.equal(ctx.page.pagedItems.value.length, 5)
    ctx.page.basketSelection.toggle('b24', true)
    assert.equal(ctx.page.basketSelection.selectedItems.value.length, 2)
    ctx.page.pageSize.value = 20; await settle()
    assert.equal(ctx.page.currentPage.value, 1)
    assert.equal(ctx.page.pagedItems.value.length, 20)
    assert.equal(ctx.page.basketSelection.selectedItems.value.length, 2)
    ctx.page.currentPage.value = 2; await settle()
    ctx.store.basket = ctx.store.basket.slice(0, 20); await settle()
    assert.equal(ctx.page.currentPage.value, 1)
  } finally { ctx.close() }
})

test('unified research page includes outputs and unfinished jobs and preserves old status filters', async () => {
  const ctx = await mountPage('ResearchWorkbenchView', { query: { status: 'failed' } })
  try {
    ctx.store.researchReports = [{ id: '3001', ownerId: 7, title: '科研成果', type: '科研报告' }, { id: '3008', ownerId: 8, title: '他人成果' }]
    ctx.store.tasks = [{ id: '3002', status: 'completed', reportId: '3001', title: '已完成任务' }, { id: '3004', status: 'failed', title: '失败任务', reportType: 'research-demand' }, { id: 't3', status: 'running', title: '生成任务', progress: 42, reportType: 'research-demand' }]
    await settle()
    assert.equal(ctx.page.researchReports.value.length, 3)
    assert.deepEqual(ctx.page.filteredReports.value.map(x => x.title), ['失败任务'])
    assert.match(ctx.page.filteredReports.value[0].path, /tasks\/3004/)
    await ctx.router.replace({ path: '/portal/research', query: { status: 'completed' } })
    await settle()
    assert.equal(ctx.page.status.value, 'generated')
    assert.deepEqual(ctx.page.filteredReports.value.map(x => x.title), ['科研成果'])
    ctx.page.status.value = 'active'
    assert.equal(ctx.page.filteredReports.value[0].progress, 42)
    assert.equal(ctx.page.activeView, undefined)
    assert.doesNotMatch(sources.ResearchWorkbenchView, /报告模板|loadReportTemplates|listPipelineTemplates/)
    assert.doesNotMatch(sources.ResearchWorkbenchView, /ps-research-list-heading|<h2>报告列表/)
  } finally { ctx.close() }
})

test('home shows actual scoped metrics and performs explicit inline keyword search', async () => {
  const calls = []
  const searches = []
  const ctx = await mountPage('HomeView', { api: { listPipelineIntelligence: async params => {
    calls.push(params)
    return { data: { rows: [{ id: params.category === 'paper' ? 'p1' : '3018', title: '授权内容', source_type: params.source_type }], total: 25 } }
  }, getPipelinePortalOverview: async () => ({ data: { paperCount: 3, newsCount: 6, wechatCount: 4, todayPaperCount: 2, todayNewsCount: 1, todayWechatCount: 3, todayAddedCount: 6, reportCount: 2 } }),
  searchPipelineIntelligence: async params => { searches.push(params); return { data: { rows: [{ id: '3018', type: 'news', title: '真实结果', path: '/portal/news/3018' }], total: 1 } } } } })
  try {
    assert.equal(calls.length, 2)
    assert.ok(calls.every(params => params.pageSize === 8 && params.sortBy === 'publication'))
    assert.deepEqual(ctx.page.metrics.value.map(x => x.value), [3, 6, 4, 6, 2])
    assert.deepEqual(ctx.page.metrics.value.map(x => x.added), [2, 1, 3, null, null])
    assert.equal(ctx.page.metrics.value.find(x => x.key === 'todayAddedCount').label, '今日新增')
    assert.equal(searches.length, 0)
    ctx.page.keyword.value = '管道腐蚀检测'
    await ctx.page.submitSearch()
    await delay(280); await settle()
    assert.equal(searches[0].keyword, '管道腐蚀检测')
    assert.equal(ctx.router.currentRoute.value.path, '/portal')
    assert.equal(ctx.page.searchResults.value[0].id, '3018')
    ctx.page.clearSearch(); await settle()
    assert.equal(ctx.page.submittedKeyword.value, '')
  } finally { ctx.close() }
})

test('home no longer renders timelines or keeps their unused state', async () => {
  const ctx = await mountPage('HomeView', { api: { listPipelineIntelligence: async params => ({ data: {
    rows: Array.from({ length: 8 }, (_, index) => ({ id: String(index), title: '真实内容', publish_time: index === 0 ? '2024-03' : '2020', publication_year: 2024 })), total: 8
  } }) } })
  try {
    assert.equal(ctx.page.newsItems, undefined)
    assert.equal(ctx.page.paperItems, undefined)
    assert.doesNotMatch(sources.HomeView, /ps-home-timeline|ps-home-content-grid|newsTimeline|paperTimeline/)
    assert.equal(ctx.page.modules.length, 4)
    assert.equal(ctx.page.latestItems.value.length, 8)
  } finally { ctx.close() }
})

test('home metric failures stay unknown rather than becoming fabricated zeros', async () => {
  const ctx = await mountPage('HomeView', { api: { getPipelinePortalOverview: async () => { throw new Error('统计暂不可用') } } })
  try { assert.ok(ctx.page.metrics.value.every(x => x.value === null)); assert.match(ctx.page.overview.loadError.value, /统计/) }
  finally { ctx.close() }
})

test('semantic placeholder never silently executes keyword search and preserves input when switching', async () => {
  const calls = []
  const ctx = await mountPage('SearchView', { query: { mode: 'semantic', q: '如何识别管道腐蚀' }, api: { searchPipelineIntelligence: async params => { calls.push(params); return { data: { rows: [], total: 0 } } } } })
  try {
    assert.equal(calls.length, 0)
    assert.equal(ctx.page.searchMode.value, 'semantic')
    ctx.page.draftKeyword.value = '管道早期腐蚀'
    ctx.page.useKeywordSearch()
    await settle()
    await delay(300)
    assert.equal(calls.at(-1).keyword, '管道早期腐蚀')
    assert.equal(calls.at(-1).mode, undefined)
    assert.equal(ctx.page.searchMode.value, 'keyword')
    assert.equal(ctx.router.currentRoute.value.query.q, '管道早期腐蚀')
  } finally { ctx.close() }
})

test('changing to semantic state invalidates a pending keyword response', async () => {
  const pending = deferred()
  const ctx = await mountPage('SearchView', { api: { searchPipelineIntelligence: () => pending.promise } })
  try {
    ctx.page.searchMode.value = 'semantic'
    await settle()
    pending.resolve({ data: { rows: [{ id: 'old-keyword-result', type: 'news', title: '旧结果' }], total: 1 } })
    await settle()
    assert.equal(ctx.page.filteredResults.value.length, 0)
    assert.equal(ctx.page.searchMode.value, 'semantic')
  } finally { ctx.close() }
})

test('all four real Vue scripts and templates compile and expose distinct retry and empty states', () => {
  for (const name of names) {
    const { descriptor, errors } = parse(sources[name])
    assert.deepEqual(errors, [])
    const script = compileScript(descriptor, { id: name })
    const template = compileTemplate({ id: name, filename: name, source: descriptor.template.content, compilerOptions: { bindingMetadata: script.bindings } })
    assert.deepEqual(template.errors, [])
    if (['NewsListView', 'PaperListView'].includes(name)) assert.doesNotMatch(sources[name], /ps-list-summary/)
    else assert.match(sources[name], /当前条件/)
    assert.match(sources[name], /aria-busy/)
  }
})

test('URL pagination rejects malformed values and caps search at the backend limit', () => {
  const defaults = { q: '', directions: [], page: 1, size: 20 }
  assert.deepEqual(readListQuery({ page: '-1', size: '999', directions: '检测' }, defaults), { ...defaults, directions: ['检测'] })
  assert.equal(readListQuery({ page: '101' }, defaults, { maxPage: 100 }).page, 100)
  assert.equal(readListQuery({ page: '2.2' }, defaults).page, 1)
  assert.equal(validPage(0, 20, 5), 1)
  assert.equal(validPage(25, 20, 5), 2)
})

test('news queries articles only, sends the real source filter, and resets page once for combined changes', async () => {
  const calls = []
  const ctx = await mountPage('NewsListView', { query: { source: '微信公众号', importance: '重点', page: '3', keep: 'yes' }, api: { listPipelineIntelligence: async params => { calls.push(params); return { data: { rows: [], total: 50 } } } } })
  try {
    assert.equal(calls[0].category, 'article')
    assert.equal(calls[0].source_type, 'wechat')
    assert.equal(calls[0].pageNum, 3)
    ctx.page.activeTags.value = ['检测技术', '数字化运维']
    await settle()
    assert.equal(calls.length, 2)
    assert.equal(calls.at(-1).pageNum, 1)
    assert.equal(calls.at(-1).relevanceMin, undefined)
    assert.equal(calls.at(-1).relevanceMax, undefined)
    assert.equal(calls.at(-1).category, 'article')
    assert.deepEqual(JSON.parse(calls.at(-1).tags), ['检测技术', '数字化运维'])
    assert.equal(ctx.router.currentRoute.value.query.keep, 'yes')
    assert.doesNotMatch(sources.NewsListView, /全部等级|ps-importance|item\.importance|v-model="importance"/)
    ctx.page.viewMode.value = 'card'
    await settle()
    assert.equal(calls.length, 2, 'view changes do not refetch')
    ctx.page.resetFilters()
    await settle()
    assert.equal(calls.at(-1).category, 'article')
    assert.equal(calls.at(-1).tags, undefined)
    assert.equal(calls.at(-1).source_type, undefined)
    assert.doesNotMatch(sources.NewsListView, /topics|热门主题|\.heat/)
  } finally { ctx.close() }
})

test('news migrates legacy links into removable multi-tags and restores query-only navigation', async () => {
  const calls = []
  const ctx = await mountPage('NewsListView', { query: { category: '智能巡检', tag: '管道安全' }, api: { listPipelineIntelligence: async params => { calls.push(params); return { data: { rows: [], total: 0 } } } } })
  try {
    assert.deepEqual(ctx.page.activeTags.value, ['智能巡检', '管道安全'])
    assert.equal(calls.at(-1).category, 'article')
    assert.deepEqual(JSON.parse(calls.at(-1).tags), ['智能巡检', '管道安全'])
    ctx.page.toggleTag('智能巡检'); await settle()
    assert.deepEqual(JSON.parse(calls.at(-1).tags), ['管道安全'])
    ctx.page.activeTags.value = []; await settle()
    assert.equal(calls.at(-1).tags, undefined)
    await ctx.router.replace({ path: '/portal/news', query: { category: 'wechat', tag: ['全部', '检测', '检测'] } }); await settle()
    assert.deepEqual(ctx.page.activeTags.value, ['检测'])
    assert.equal(calls.at(-1).source_type, 'wechat')
    assert.deepEqual(JSON.parse(calls.at(-1).tags), ['检测'])
  } finally { ctx.close() }
})

test('typing debounces requests and invalidates an old response before debounce finishes', async () => {
  const calls = []
  const first = deferred()
  const ctx = await mountPage('NewsListView', { api: { listPipelineIntelligence: params => { calls.push(params); return calls.length === 1 ? first.promise : Promise.resolve({ data: { rows: [{ id: 'new', title: '最新' }], total: 1 } }) } } })
  try {
    ctx.page.keyword.value = '检测'
    await settle()
    first.resolve({ data: { rows: [{ id: 'old', title: '过期' }], total: 1 } })
    await settle()
    assert.equal(ctx.page.newsItems.value.length, 0)
    assert.equal(ctx.page.loading.value, true)
    ctx.page.keyword.value = '检测技术'
    await settle()
    await delay(280)
    await settle()
    assert.equal(calls.length, 2)
    assert.equal(calls[1].keyword, '检测技术')
    assert.equal(ctx.page.newsItems.value[0].id, 'new')
  } finally { ctx.close() }
})

test('failure can be retried with the same filters and a successful empty result clears the error', async () => {
  let fail = true
  const calls = []
  const ctx = await mountPage('NewsListView', { query: { q: '缺陷' }, api: { listPipelineIntelligence: async params => { calls.push(params); if (fail) throw { msg: '服务暂不可用' }; return { data: { rows: [], total: 0 } } } } })
  try {
    assert.equal(ctx.page.loadError.value, '服务暂不可用')
    fail = false
    await ctx.page.reload()
    await settle()
    assert.equal(ctx.page.loadError.value, '')
    assert.equal(ctx.page.total.value, 0)
    assert.deepEqual(calls[0], calls[1])
  } finally { ctx.close() }
})

test('late success after unmount cannot publish data', async () => {
  const response = deferred()
  const ctx = await mountPage('NewsListView', { api: { listPipelineIntelligence: () => response.promise } })
  ctx.close()
  response.resolve({ data: { rows: [{ id: 'late' }], total: 1 } })
  await settle()
  assert.equal(ctx.page.data.value, null)
})

test('paper default includes old and undated records, with real journal suggestions and honest totals', async () => {
  const calls = []
  const ctx = await mountPage('PaperListView', { api: { listPipelineIntelligence: async params => { calls.push(params); return { data: { rows: [{ id: 'p1', title: '旧论文', publication_year: 1998, journal: '真实期刊' }, { id: 'p2', title: '未标年论文' }], total: 123 } } } } })
  try {
    assert.equal(calls[0].yearFrom, undefined)
    assert.equal(calls[0].yearTo, undefined)
    assert.equal(ctx.page.total.value, 123)
    assert.deepEqual(ctx.page.journalOptions.value, ['真实期刊'])
    assert.equal(ctx.page.filteredPapers.value[1].citationCount, '未提供')
    ctx.page.journals.value = ['自填期刊']
    ctx.page.changeYearRange(['1990', '1999'])
    await settle()
    assert.equal(calls.at(-1).yearFrom, 1990)
    assert.equal(calls.at(-1).journal, '自填期刊')
    ctx.page.changeYearRange(null)
    await settle()
    assert.equal(calls.at(-1).yearFrom, undefined)
    ctx.page.resetFilters()
    await settle()
    assert.equal(calls.at(-1).journal, undefined)
  } finally { ctx.close() }
})

test('paper invalid years show a recoverable error without sending a malformed request', async () => {
  let calls = 0
  const ctx = await mountPage('PaperListView', { query: { year: 'bad-year' }, api: { listPipelineIntelligence: async () => { calls += 1; return { data: { rows: [], total: 0 } } } } })
  try {
    assert.equal(calls, 0)
    assert.match(ctx.page.loadError.value, /有效年份/)
    ctx.page.resetFilters()
    await settle()
    assert.equal(calls, 1)
    assert.equal(ctx.page.loadError.value, '')
  } finally { ctx.close() }
})

test('paper DOI links resolve directly and invalid DOI values never become clickable URLs', async () => {
  const ctx = await mountPage('PaperListView')
  try {
    assert.equal(ctx.page.doiUrl({ doi: '10.3390/coatings14030358' }), 'https://doi.org/10.3390/coatings14030358')
    assert.equal(ctx.page.doiUrl({ doi: ' https://doi.org/10.6047/example ' }), 'https://doi.org/10.6047/example')
    assert.equal(ctx.page.doiUrl({ doi: 'DOI: 10.1234/a?b#c' }), 'https://doi.org/10.1234/a%3Fb%23c')
    for (const doi of ['', '待补充', 'javascript:alert(1)', 'https://example.com', '10.1234/invalid space']) assert.equal(ctx.page.doiUrl({ doi }), '')
  } finally { ctx.close() }
})

test('query restoration retains filters and page across detail navigation and query-only updates', async () => {
  const ctx = await mountPage('PaperListView', { query: { q: 'pipeline', journals: ['A', 'B'], page: '4', size: '20' }, api: { listPipelineIntelligence: async () => ({ data: { rows: [], total: 200 } }) } })
  try {
    assert.equal(ctx.page.currentPage.value, 4)
    await ctx.router.push('/portal/papers/p1')
    await ctx.router.back()
    await settle()
    assert.equal(ctx.page.currentPage.value, 4)
    assert.deepEqual([...ctx.page.journals.value], ['A', 'B'])
    await ctx.router.replace({ path: '/portal/papers', query: { q: 'new', page: '2' } })
    await settle()
    assert.equal(ctx.page.keyword.value, 'new')
    assert.equal(ctx.page.currentPage.value, 2)
  } finally { ctx.close() }
})

test('knowledge paginates filtered real data and returns to a valid page after deletion', async () => {
  const documents = Array.from({ length: 23 }, (_, index) => ({ id: `d${index}`, name: `资料${index}`, type: '内部文献', permissionScope: index % 2 ? 'private' : 'public', status: '已解析', scanStatus: 'clean' }))
  const ctx = await mountPage('KnowledgeView', { documents, query: { page: '3' } })
  try {
    assert.equal(ctx.page.pagedDocuments.value.length, 3)
    ctx.store.knowledgeDocuments.splice(20)
    await settle()
    assert.equal(ctx.page.currentPage.value, 2)
    ctx.page.permission.value = 'public'
    await settle()
    assert.equal(ctx.page.currentPage.value, 1)
    assert.equal(ctx.page.filteredDocuments.value.length, 10)
    assert.match(sources.KnowledgeView, /title="研究资料"/)
    assert.doesNotMatch(sources.KnowledgeView, /value="项目组可见"|value="受限"/)
  } finally { ctx.close() }
})

test('knowledge rejects unsafe, unfinished or AI-disallowed materials before saving', async () => {
  let saves = 0
  const ctx = await mountPage('KnowledgeView', { api: { savePipelineWorkspaceItem: async () => { saves += 1 } } })
  try {
    for (const doc of [
      { id: '1', status: '已解析', scanStatus: 'quarantined' },
      { id: '2', status: '解析中', scanStatus: 'clean' },
      { id: '3', status: '已解析', allowAiUse: false }
    ]) await ctx.page.add(doc)
    assert.equal(saves, 0)
    assert.equal(ctx.messages.filter(item => item.level === 'warning').length, 3)
  } finally { ctx.close() }
})

test('knowledge clamps restored pages and distinguishes its own loading error from unrelated sections', async () => {
  const ctx = await mountPage('KnowledgeView', { query: { page: '99' }, documents: [{ id: '3005', name: '资料', status: '已解析' }] })
  try {
    assert.equal(ctx.page.currentPage.value, 1)
    ctx.store.sectionErrors = { reports: '报告失败', documents: '' }
    ctx.store.dataError = '部分数据加载失败'
    assert.equal(ctx.page.documentsError.value, '')
    ctx.store.sectionErrors.documents = '资料获取失败'
    assert.equal(ctx.page.documentsError.value, '资料获取失败')
  } finally { ctx.close() }
})

test('late failure on an old news page cannot erase a newer successful page', async () => {
  const old = deferred()
  const calls = []
  const ctx = await mountPage('NewsListView', { api: { listPipelineIntelligence: params => {
    calls.push(params)
    return params.pageNum === 1 ? old.promise : Promise.resolve({ data: { rows: [{ id: 'page2' }], total: 20 } })
  } } })
  try {
    ctx.page.currentPage.value = 2
    await settle()
    old.reject({ msg: '旧页请求失败' })
    await settle()
    assert.equal(ctx.page.newsItems.value[0].id, 'page2')
    assert.equal(ctx.page.loadError.value, '')
    assert.equal(ctx.page.loading.value, false)
  } finally { ctx.close() }
})

test('basket saves later-page types explicitly, prevents duplicate submits and waits for acknowledgement', async () => {
  const saved = deferred()
  const payloads = []
  const ctx = await mountPage('PaperListView', { api: { savePipelineWorkspaceItem: params => { payloads.push(params); return saved.promise } } })
  try {
    const paper = { id: '3016', titleZh: '真实题名', journal: '真实期刊', doi: '10.example/3019' }
    const pending = ctx.page.add(paper)
    await ctx.page.add(paper)
    assert.equal(payloads.length, 1)
    assert.equal(payloads[0].itemType, 'paper')
    assert.equal(payloads[0].snapshot.doi, '10.example/3019')
    assert.equal(ctx.store.basket.length, 0)
    assert.equal(ctx.page.busy(paper), true)
    saved.resolve({ data: { saved: true } })
    await pending
    assert.equal(ctx.store.basket[0].type, 'paper')
    assert.equal(ctx.page.inBasket(paper), true)
  } finally { ctx.close() }
})

test('basket failure and account changes never show a false saved state', async () => {
  const response = deferred()
  let fail = true
  const ctx = await mountPage('NewsListView', { api: { savePipelineWorkspaceItem: () => fail ? Promise.reject({ msg: '保存失败' }) : response.promise } })
  try {
    await ctx.page.addToBasket({ id: '3019', title: '资讯' })
    assert.equal(ctx.store.basket.length, 0)
    assert.equal(ctx.messages.at(-1).level, 'error')
    fail = false
    const pending = ctx.page.addToBasket({ id: '3020', title: '另一个账号的旧请求' })
    ctx.store.workspaceEpoch += 1
    response.resolve({ data: {} })
    await pending
    assert.equal(ctx.store.basket.length, 0)
    assert.equal(ctx.messages.some(item => item.level === 'success'), false)
  } finally { ctx.close() }
})

test('saved items can be removed from paper, news and search lists after server acknowledgement', async () => {
  for (const [name, action, type] of [['PaperListView', 'add', 'paper'], ['NewsListView', 'addToBasket', 'article'], ['SearchView', 'add', 'paper']]) {
    const response = deferred()
    const removed = []
    const ctx = await mountPage(name, { api: { deletePipelineWorkspaceItem: (...args) => { removed.push(args); return response.promise } } })
    try {
      const item = { id: '3017', title: '选材', type }
      ctx.store.basket.push(item)
      const pending = ctx.page[action](item)
      await ctx.page[action](item)
      assert.deepEqual(removed, [['basket', item.id]])
      assert.equal(ctx.page.busy(item), true)
      assert.equal(ctx.store.basket.length, 1)
      response.resolve({ data: {} }); await pending
      assert.equal(ctx.store.basket.length, 0)
      assert.equal(ctx.page.busy(item), false)
      assert.equal(ctx.messages.at(-1).text, '已取消加入资料篮')
    } finally { ctx.close() }
  }
})

test('failed or stale basket cancellation never removes a saved item from the current account', async () => {
  const response = deferred()
  let reject = true
  const ctx = await mountPage('PaperListView', { api: { deletePipelineWorkspaceItem: () => reject ? Promise.reject({ msg: '取消失败' }) : response.promise } })
  try {
    const item = { id: '3017', title: '原资料' }
    ctx.store.basket.push(item)
    await ctx.page.add(item)
    assert.equal(ctx.store.basket.length, 1)
    assert.equal(ctx.messages.at(-1).level, 'error')
    reject = false
    const pending = ctx.page.add(item)
    ctx.store.workspaceEpoch += 1
    ctx.store.basket = [{ id: item.id, title: '新账号资料' }]
    response.resolve({ data: {} }); await pending
    assert.equal(ctx.store.basket[0].title, '新账号资料')
    assert.equal(ctx.messages.some(message => message.level === 'success'), false)
  } finally { ctx.close() }
})

test('search keeps cursor context, resets size and filters, and caps displayed pagination', async () => {
  const calls = []
  const ctx = await mountPage('SearchView', { api: { searchPipelineIntelligence: async params => { calls.push(params); return { data: { rows: [], total: 2500, counts: { all: 2500 }, nextCursor: `cursor-${params.pageNum}` } } } } })
  try {
    assert.equal(ctx.page.pageLimitExceeded.value, true)
    ctx.page.currentPage.value = 2
    await settle()
    assert.equal(calls.at(-1).cursor, 'cursor-1')
    ctx.page.pageSize.value = 50
    await settle()
    assert.equal(calls.at(-1).pageNum, 1)
    assert.equal(calls.at(-1).cursor, undefined)
    ctx.page.directions.value.push('检测技术')
    await settle()
    assert.equal(calls.at(-1).directions, '检测技术')
    assert.equal(calls.at(-1).cursor, undefined)
    assert.match(sources.SearchView, /:total="Math.min\(total, pageSize \* maxPageNum\)"/)
  } finally { ctx.close() }
})

test('search separates draft and submitted keywords, resubmits unchanged text, and preserves other filters', async () => {
  const calls = []
  const ctx = await mountPage('SearchView', { query: { q: '旧词', type: 'paper', date: 'week' }, api: { searchPipelineIntelligence: async params => { calls.push(params); return { data: { rows: [], total: 0 } } } } })
  try {
    ctx.page.draftKeyword.value = '新词'
    await settle()
    assert.equal(calls.length, 1)
    ctx.page.applyKeyword()
    await delay(280)
    await settle()
    assert.equal(calls.at(-1).keyword, '新词')
    assert.equal(ctx.router.currentRoute.value.query.type, 'paper')
    assert.equal(ctx.router.currentRoute.value.query.date, 'week')
    const count = calls.length
    ctx.page.applyKeyword()
    await settle()
    assert.equal(calls.length, count + 1)
  } finally { ctx.close() }
})

test('search opens correct detail routes and checks internal materials before basket selection', async () => {
  let saves = 0
  const ctx = await mountPage('SearchView', { api: { savePipelineWorkspaceItem: async () => { saves += 1 }, searchPipelineIntelligence: async () => ({ data: { total: 1, rows: [{ id: 'daily1', type: 'report', report_type: 'daily' }] } }) } })
  try {
    assert.equal(ctx.page.filteredResults.value[0].path, '/portal/digests/daily1')
    await ctx.page.add({ id: 'doc1', type: 'document', path: '/portal/knowledge/doc1' })
    await settle()
    assert.equal(saves, 0)
    assert.equal(ctx.router.currentRoute.value.path, '/portal/knowledge/doc1')
  } finally { ctx.close() }
})

test('search provides basket selection instead of favorite actions', async () => {
  const payloads = []
  const ctx = await mountPage('SearchView', { api: { savePipelineWorkspaceItem: async params => { payloads.push(params) } } })
  try {
    assert.equal(ctx.page.favorite, undefined)
    assert.doesNotMatch(sources.SearchView, /favorite\(result\)|isFavorite\(result.id\)/)
    await ctx.page.add({ id: '3018', title: '搜索命中资讯', type: 'news' })
    assert.equal(payloads[0].itemType, 'article')
    assert.equal(ctx.store.basket[0].title, '搜索命中资讯')
    assert.equal(ctx.store.favoriteItems.length, 0)
  } finally { ctx.close() }
})
