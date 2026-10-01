import test from 'node:test'
import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import { getPortalReportPath, getPortalTaskPath, isDigestType } from '../src/views/portal/utils/routing.js'

const read = path => readFileSync(new URL(path, import.meta.url), 'utf8')
const routerConfig = read('../src/router/index.js')
const portalShell = read('../src/views/portal/index.vue')
const portalHeader = read('../src/views/portal/components/PortalHeader.vue')
const portalStore = read('../src/store/modules/portal.js')
const pipelineApi = read('../src/api/pipeline/intelligence.js')
const portalStyles = read('../src/assets/styles/portal.scss')
const loginPage = read('../src/views/login.vue')
const portalAuthConfig = read('../src/utils/portal/auth.js')
const permissionConfig = read('../src/permission.js')
const permissionStore = read('../src/store/modules/permission.js')

const pageFiles = [
  'HomeView.vue', 'SearchView.vue', 'NewsListView.vue', 'NewsDetailView.vue',
  'PaperListView.vue', 'PaperDetailView.vue', 'ResearchWorkbenchView.vue',
  'ResearchCreateView.vue', 'ResearchTaskView.vue', 'ReportEditorView.vue',
  'DiagramEditorView.vue', 'DigestListView.vue', 'DigestCreateView.vue',
  'DigestEditorView.vue', 'KnowledgeView.vue', 'KnowledgeDetailView.vue',
  'MyWorkspaceView.vue'
]

test('exposes the user portal as an authenticated routed application shell', () => {
  assert.match(portalShell, /class="ps-portal pipeline-user-portal portal-app-shell"/)
  assert.match(portalShell, /<PortalHeader \/>/)
  assert.match(portalShell, /<router-view/)
  assert.match(portalShell, /<PortalTaskPanel \/>/)
  assert.match(portalShell, /数据仅按当前账号授权范围展示/)
  assert.doesNotMatch(portalShell, /component:\s*Layout/)
})

test('uses one logical six-item user navigation without backend menu groups', () => {
  const navigation = read('../src/views/portal/data.js')
  for (const label of ['首页', '科技资讯', '论文资料', '科研工作台', '情报简报', '知识库']) {
    assert.match(navigation, new RegExp(`label: '${label}'`))
  }
  assert.match(portalHeader, /portalNavigation/)
  assert.match(portalHeader, /我的任务/)
  assert.match(portalHeader, /我的报告/)
  assert.match(portalHeader, /我的收藏/)
  for (const forbidden of ['系统管理', '系统监控', '系统工具', 'AI 管理']) {
    assert.doesNotMatch(portalHeader, new RegExp(forbidden))
    assert.doesNotMatch(portalShell, new RegExp(forbidden))
  }
})

test('ships every user-facing prototype page as an independent Vue page', () => {
  for (const file of pageFiles) {
    assert.equal(existsSync(new URL(`../src/views/portal/pages/${file}`, import.meta.url)), true, `${file} should exist`)
  }
  assert.match(routerConfig, /path: 'search'/)
  assert.match(routerConfig, /path: 'research\/create'/)
  assert.match(routerConfig, /path: 'research\/tasks\/:id'/)
  assert.match(routerConfig, /path: 'research\/reports\/:id\/diagram'/)
  assert.match(routerConfig, /path: 'digests\/create'/)
  assert.doesNotMatch(routerConfig, /path: 'knowledge\/ask'/)
  assert.match(routerConfig, /path: 'me\/favorites'/)
})

test('implements a coherent home discovery and continue-work experience', () => {
  const home = read('../src/views/portal/pages/HomeView.vue')
  assert.match(home, /class="ps-home-hero"/)
  assert.match(home, /新建科研报告/)
  assert.match(home, /新建简报/)
  assert.match(home, /上传研究资料/)
  assert.doesNotMatch(home, /知识问答/)
  assert.doesNotMatch(home, /热点主题/)
  assert.doesNotMatch(home, /ps-search-suggestions/)
  assert.match(home, /最新科技资讯/)
  assert.match(home, /最新论文/)
  assert.match(home, /我的工作/)
  assert.match(home, /router\.push\(\{ path: '\/portal\/search'/)
})

test('provides working cross-page basket, favorites and task panel state', () => {
  assert.match(portalStore, /basket: \[\]/)
  assert.match(portalStore, /favorites: \[\]/)
  assert.match(portalStore, /tasks: demoDataEnabled \? recentTasks/)
  assert.match(portalStore, /addToBasket\(item\)/)
  assert.match(portalStore, /toggleFavorite\(id\)/)
  assert.match(portalStore, /openTaskPanel\(\)/)
  assert.match(portalHeader, /store\.basketCount/)
  assert.match(portalHeader, /store\.openTaskPanel\(\)/)
  assert.match(portalHeader, /数据同步异常/)
})

test('routes every generated task and report to its real detail page', () => {
  assert.equal(getPortalTaskPath({ id: 'job-1', type: '科研生成' }), '/portal/research/tasks/job-1')
  assert.equal(getPortalTaskPath({ id: 'job-2', type: '日报周报' }), '/portal/research/tasks/job-2')
  assert.equal(getPortalTaskPath({ id: 'job-3', type: '月报生成' }), '/portal/research/tasks/job-3')
  assert.equal(getPortalTaskPath({ id: 'parse-1', type: '资料解析' }), '/portal/me/tasks')
  assert.equal(getPortalReportPath({ id: 'report-1', reportType: 'research-demand' }), '/portal/research/reports/report-1')
  assert.equal(getPortalReportPath({ id: 'report-2', reportType: 'daily' }), '/portal/digests/report-2')
  assert.equal(getPortalReportPath({ id: 'report-3', reportType: 'monthly' }), '/portal/digests/report-3')
  assert.equal(isDigestType('周报'), true)
  assert.equal(isDigestType('月报'), true)
})

test('hydrates portal pages from pipeline APIs and keeps demo data explicitly opt-in', () => {
  const researchWorkbench = read('../src/views/portal/pages/ResearchWorkbenchView.vue')
  const researchCreate = read('../src/views/portal/pages/ResearchCreateView.vue')
  const digestList = read('../src/views/portal/pages/DigestListView.vue')
  const knowledge = read('../src/views/portal/pages/KnowledgeView.vue')
  for (const apiName of ['getPipelineDashboard', 'listPipelineIntelligence', 'listPipelineKnowledgeDocuments', 'listPipelineReports', 'getPipelineWorkspace', 'createPipelineResearchJob', 'updatePipelineResearchReport']) {
    assert.match(pipelineApi, new RegExp(`export function ${apiName}`))
  }
  assert.match(portalStore, /Promise\.allSettled/)
  assert.match(portalStore, /VITE_PORTAL_DEMO_DATA/)
  assert.match(portalStore, /reportType: item\.type/)
  assert.match(portalStore, /status: item\.status \|\| 'queued'/)
  assert.match(portalStore, /\['queued', 'running', 'generating', 'retrieving'\]/)
  assert.match(portalStore, /return demoDataEnabled \? mergeById\(fallbackRows, liveRows\) : liveRows/)
  assert.match(portalStore, /fallbackNews/)
  assert.match(portalStore, /fallbackDocuments/)
  assert.match(portalStore, /fallbackReports/)
  assert.match(portalHeader, /store\.hydrate\(\)/)
  assert.match(researchWorkbench, /portalStore\.researchReports/)
  assert.match(researchCreate, /portalStore\.knowledgeDocuments/)
  assert.match(digestList, /portalStore\.digestReports/)
  assert.match(knowledge, /portalStore\.knowledgeDocuments/)
  assert.doesNotMatch(knowledge, /知识问答/)
})

test('implements the full research creation and editing workflow', () => {
  const create = read('../src/views/portal/pages/ResearchCreateView.vue')
  const task = read('../src/views/portal/pages/ResearchTaskView.vue')
  const editor = read('../src/views/portal/pages/ReportEditorView.vue')
  const diagram = read('../src/views/portal/pages/DiagramEditorView.vue')
  assert.match(create, /类型与模板/)
  assert.match(create, /选择资料/)
  assert.match(create, /任务参数/)
  assert.match(create, /确认大纲/)
  assert.match(create, /function nextStep\(\)/)
  assert.match(create, /function submitTask\(\)/)
  assert.match(create, /uploadPipelineKnowledgeDocument/)
  assert.doesNotMatch(create, /'doc-001', 'paper-001'/)
  assert.doesNotMatch(create, /ps-breadcrumb/)
  assert.doesNotMatch(create, /PortalPageHeader/)
  assert.match(create, /class="ps-create-context"/)
  assert.match(create, /activeStep \+ 1/)
  assert.equal((create.match(/<h1\b/g) || []).length, 1)
  assert.match(task, /taskStages/)
  assert.match(task, /实时进展/)
  assert.match(task, /cancelPipelineResearchJob/)
  assert.match(task, /retryPipelineResearchJob/)
  assert.match(task, /getPortalReportPath\(\{ id: task\.value\.reportId, reportType: task\.value\.type \}\)/)
  assert.match(task, /重新加入生成队列/)
  assert.match(task, /function startRefresh\(\)/)
  assert.match(task, /\['completed', 'failed', 'cancelled'\]\.includes/)
  assert.match(create, /任务已进入后台生成队列/)
  assert.match(editor, /报告目录/)
  assert.match(editor, /引用来源/)
  assert.doesNotMatch(editor, /askPipelineKnowledge/)
  assert.match(editor, /质量问题/)
  assert.match(editor, /版本记录/)
  assert.doesNotMatch(editor, /askPipelineKnowledge/)
  assert.match(editor, /restorePipelineResearchReportVersion/)
  assert.match(diagram, /节点库/)
  assert.match(diagram, /局部重新生成/)
})

test('implements digest and evidence-grounded knowledge workflows', () => {
  const digestCreate = read('../src/views/portal/pages/DigestCreateView.vue')
  const digestList = read('../src/views/portal/pages/DigestListView.vue')
  const digestEditor = read('../src/views/portal/pages/DigestEditorView.vue')
  const knowledge = read('../src/views/portal/pages/KnowledgeView.vue')
  assert.match(digestCreate, /候选内容预览/)
  assert.match(digestCreate, /数据缺口/)
  assert.match(digestCreate, /const candidateItems = computed/)
  assert.doesNotMatch(digestCreate, /setTimeout\(/)
  assert.match(digestCreate, /portal\/research\/tasks/)
  assert.doesNotMatch(digestCreate, /portal\/digests\/\$\{res\.data\.reportId\}/)
  assert.doesNotMatch(digestCreate, /保存说明/)
  assert.match(digestCreate, /自动保留初始版本/)
  assert.match(digestCreate, /value="月报"/)
  assert.match(digestCreate, /type="month"/)
  assert.match(digestCreate, /reportType: 'monthly'/)
  assert.match(digestCreate, /listPipelineTemplates/)
  assert.match(digestCreate, /publishedOnly: true/)
  assert.match(digestCreate, /new Date\(year, monthIndex \+ 1, 0\)/)
  assert.match(digestList, /'月报'/)
  assert.match(digestList, /'月报': 'monthly'/)
  assert.match(digestEditor, /候选资讯/)
  assert.match(digestEditor, /来源清单/)
  assert.match(digestEditor, /质量检查/)
  assert.match(digestEditor, /getPipelineResearchReport/)
  assert.match(digestEditor, /updatePipelineResearchReport/)
  assert.match(digestEditor, /saveVersion/)
  assert.match(digestEditor, /monthly: '科技情报月报'/)
  assert.match(knowledge, /上传资料/)
  assert.doesNotMatch(knowledge, /知识问答/)
})

test('connects template management and user creation to published template APIs', () => {
  const templatePage = read('../src/views/pipeline/template/index.vue')
  const researchCreate = read('../src/views/portal/pages/ResearchCreateView.vue')
  const digestCreate = read('../src/views/portal/pages/DigestCreateView.vue')
  for (const apiName of ['listPipelineTemplates', 'createPipelineTemplate', 'updatePipelineTemplate', 'publishPipelineTemplate', 'retirePipelineTemplate']) {
    assert.match(templatePage, new RegExp(apiName))
  }
  assert.match(templatePage, /async function loadTemplates\(\)/)
  assert.match(researchCreate, /listPipelineTemplates/)
  assert.match(researchCreate, /publishedOnly: true/)
  assert.match(digestCreate, /listPipelineTemplates/)
  assert.match(digestCreate, /publishedOnly: true/)
})

test('keeps the digest creation page to one clear title context', () => {
  const digestCreate = read('../src/views/portal/pages/DigestCreateView.vue')
  assert.doesNotMatch(digestCreate, /class="ps-breadcrumb"/)
  assert.match(digestCreate, /<PortalPageHeader title="新建简报"\s*\/>/)
})

test('makes global search filters and cross-type result routing functional', () => {
  const search = read('../src/views/portal/pages/SearchView.vue')
  const workspace = read('../src/views/portal/pages/MyWorkspaceView.vue')
  const taskPanel = read('../src/views/portal/components/PortalTaskPanel.vue')
  const home = read('../src/views/portal/pages/HomeView.vue')
  assert.match(search, /function matchesCommonFilters\(item\)/)
  assert.match(search, /source\.value !== 'all'/)
  assert.match(search, /dateRange\.value !== 'all'/)
  assert.match(search, /portalStore\.digestReports\.map/)
  assert.doesNotMatch(search, /耗时 0\.18 秒/)
  assert.match(workspace, /portalStore\.knowledgeDocuments\.map/)
  assert.match(workspace, /portalStore\.digestReports\.map/)
  assert.match(taskPanel, /getPortalTaskPath\(task\)/)
  assert.match(home, /briefSummary/)
  assert.doesNotMatch(home, /近 24 小时新增 24 条/)
})

test('hardens the user knowledge workspace with real document lifecycle states', () => {
  const knowledge = read('../src/views/portal/pages/KnowledgeView.vue')
  const detail = read('../src/views/portal/pages/KnowledgeDetailView.vue')
  for (const apiName of ['getPipelineKnowledgeDocument', 'reparsePipelineKnowledgeDocument', 'deletePipelineKnowledgeDocument']) {
    assert.match(pipelineApi, new RegExp(`export function ${apiName}`))
  }
  assert.match(pipelineApi, /\/pipeline\/knowledge\/documents\/\$\{documentId\}\/retry/)
  assert.match(knowledge, /MAX_FILE_SIZE = 100 \* 1024 \* 1024/)
  assert.match(knowledge, /ALLOWED_EXTENSIONS = new Set/)
  assert.match(knowledge, /可搜索 PDF、DOCX、MD、TXT/)
  assert.doesNotMatch(knowledge, /new Set\(\['pdf', 'doc',/)
  assert.match(knowledge, /handleUploadExceed/)
  assert.match(knowledge, /ElMessageBox\.confirm/)
  assert.match(knowledge, /reparsePipelineKnowledgeDocument/)
  assert.match(knowledge, /portalStore\.dataError/)
  assert.match(detail, /getPipelineKnowledgeDocument/)
  assert.match(detail, /资料不存在或无权访问/)
  assert.doesNotMatch(detail, /portalStore\.knowledgeDocuments\[0\]/)
  assert.match(detail, /document\.status !== '已解析'/)
  assert.match(detail, /downloadPipelineKnowledgeDocument/)
  assert.match(detail, /allowDownload !== false/)
  assert.match(portalStyles, /\.ps-parse-overview/)
  assert.match(portalStyles, /@media \(max-width: 760px\)[\s\S]*?\.ps-knowledge-table > article \{[^}]*grid-template-columns: 40px minmax\(0,1fr\)/)
})

test('keeps user portal headings in Chinese without decorative English labels', () => {
  const portalPages = pageFiles.map(file => read(`../src/views/portal/pages/${file}`)).join('\n')
  const removedDecorativeLabels = [
    'INTELLIGENCE', 'KNOWLEDGE BASE', 'SEARCH', 'ACADEMIC RESEARCH',
    'RESEARCH WORKBENCH', 'DIGESTS', 'CREATE DIGEST', 'CREATE RESEARCH TASK',
    'MY WORKSPACE', 'TRENDING NOW', 'MY WORK', 'LATEST INTELLIGENCE',
    'NEW PAPERS', 'GENERATION PIPELINE', 'LIVE LOG', 'CANDIDATE PREVIEW',
    'RECENT REPORTS', 'MATERIAL BASKET', 'PIPELINE TECHNOLOGY INTELLIGENCE'
  ]
  for (const label of removedDecorativeLabels) {
    assert.doesNotMatch(portalPages, new RegExp(label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')))
  }
  assert.match(portalPages, /管网科技情报简报/)
})

test('keeps primary portal pages concise without repeated explanatory lead text', () => {
  const primaryPages = ['NewsListView.vue', 'PaperListView.vue', 'ResearchWorkbenchView.vue', 'DigestListView.vue', 'KnowledgeView.vue']
    .map(file => read(`../src/views/portal/pages/${file}`))
  for (const page of primaryPages) {
    assert.doesNotMatch(page, /<PortalPageHeader[^>]+description=/)
  }
  const pageHeader = read('../src/views/portal/components/PortalPageHeader.vue')
  assert.match(pageHeader, /'is-compact': !description/)
  assert.match(portalStyles, /\.ps-page-header\.is-compact\s*\{[^}]*min-height:\s*58px/)
})

test('keeps the Calm-style login modal closed until the user clicks an entry', () => {
  assert.match(loginPage, /class="pipeline-user-login calm-login-page calm-homepage-auth"/)
  assert.match(loginPage, /const loginVisible = ref\(false\)/)
  assert.match(loginPage, /@click="revealLogin"/)
  assert.match(loginPage, /@keydown="handleDialogKeydown"/)
  assert.match(loginPage, /document\.body\.style\.overflow/)
  assert.match(loginPage, /document\.getElementById\('login-username'\)\?\.focus\(\)/)
  assert.match(loginPage, /pipechina-emblem\.png/)
  assert.match(loginPage, /https:\/\/www\.pipechina\.com\.cn\/Uploads\/Picture\/2023\/09\/05\/s64f6d50827d73\.png/)
  for (const removed of ['演示账号', 'USER SIGN IN', '管网项目用户端', '统一入口', '新闻资讯、论文资料和日报周报专用工作台', '系统将根据账号权限进入用户端或管理端']) {
    assert.doesNotMatch(loginPage, new RegExp(removed))
  }
})

test('protects every portal route and keeps user and management surfaces separate', () => {
  assert.match(portalAuthConfig, /function isPortalProtectedPath\(path = ''\)/)
  assert.match(portalAuthConfig, /path === '\/portal' \|\| path\.startsWith\('\/portal\/'\)/)
  assert.match(permissionConfig, /isPortalProtectedPath\(to\.path\)/)
  assert.match(permissionConfig, /next\(getLoginRedirect\(to\.fullPath\)\)/)
  assert.match(permissionStore, /const BACKEND_ONLY_ROOTS = new Set\(\['system', 'monitor', 'tool', 'ai'\]\)/)
  assert.match(permissionStore, /filterPipelineUserMenus/)
  assert.match(routerConfig, /path: '\/pipeline\/manuscript'[\s\S]*?component: Layout/)
  assert.match(routerConfig, /path: '\/portal'[\s\S]*?component: \(\) => import\('@\/views\/portal\/index\.vue'\)/)
})

test('uses one responsive design system for desktop, tablet and mobile', () => {
  assert.match(portalStyles, /--ps-blue: #2764e7/)
  assert.match(portalStyles, /--ps-teal: #0b8f87/)
  assert.match(portalStyles, /\.ps-header\s*\{/)
  assert.match(portalStyles, /\.ps-home-hero\s*\{/)
  assert.match(portalStyles, /\.ps-editor-layout\s*\{/)
  assert.match(portalStyles, /@media \(max-width: 1050px\)/)
  assert.match(portalStyles, /@media \(max-width: 760px\)/)
  assert.match(portalStyles, /@media \(prefers-reduced-motion: reduce\)/)
})

test('uses fluid shell widths and content-driven grids on large screens', () => {
  assert.match(portalStyles, /\.ps-header-inner\s*\{[^}]*width: 100%[^}]*padding: 0 16px/)
  assert.match(portalStyles, /\.ps-page\s*\{[^}]*width: min\(2080px, calc\(100% - clamp\(24px, 4vw, 72px\)\)\)/)
  assert.match(portalStyles, /\.ps-home-page\s*\{[^}]*container-type: inline-size/)
  assert.match(portalStyles, /\.ps-home-grid\s*\{[^}]*grid-template-columns: repeat\(2, minmax\(0, 1fr\)\)/)
  assert.match(portalStyles, /@media \(max-width: 760px\)[\s\S]*?\.ps-page \{ width: calc\(100% - 24px\)/)
})

test('anchors the portal brand left and keeps navigation fixed while scrolling', () => {
  assert.match(portalStyles, /\.ps-header\s*\{[^}]*position: fixed[^}]*top: 0[^}]*right: 0[^}]*left: 0[^}]*width: 100%/)
  assert.match(portalStyles, /\.ps-portal-main\s*\{[^}]*padding-top: 70px/)
  assert.match(portalStyles, /@media \(max-width: 760px\)[\s\S]*?\.ps-header-inner \{ height: 62px; padding: 0 12px[^}]*\}[\s\S]*?\.ps-portal-main \{ padding-top: 62px; \}/)
})

test('keeps the home hero light, balanced and readable on image backgrounds', () => {
  assert.match(portalStyles, /\.ps-home-hero\s*\{[\s\S]*?linear-gradient\(104deg, oklch\(98\.5%/)
  assert.match(portalStyles, /url\("\/files\/pipeline-hero\.svg"\)/)
  assert.match(portalStyles, /\.ps-home-page\s*\{[^}]*container-type:\s*inline-size[^}]*padding-top:\s*18px/)
  assert.match(portalStyles, /\.ps-home-hero\s*\{[\s\S]*?min-height: 330px/)
  assert.match(portalStyles, /\.ps-home-welcome h1\s*\{[\s\S]*?color: oklch\(26%/)
  assert.match(portalStyles, /\.ps-home-welcome > p\s*\{[\s\S]*?color: oklch\(46%/)
  assert.match(portalStyles, /\.ps-hero-search input::placeholder\s*\{[\s\S]*?opacity: 1/)
  assert.match(portalStyles, /\.ps-hero-brief\s*\{[\s\S]*?background: oklch\(99%/)
  assert.match(portalStyles, /\.ps-hero-brief > strong\s*\{[\s\S]*?color: oklch\(26%/)
  assert.match(portalStyles, /\.ps-brief-metrics span\s*\{[\s\S]*?color: oklch\(45%/)
  assert.match(portalStyles, /@media \(max-width: 1050px\)[\s\S]*?\.ps-home-hero \{[^}]*grid-template-columns: minmax\(0, 1\.25fr\) minmax\(280px, \.75fr\)/)
  assert.match(portalStyles, /@media \(max-width: 760px\)[\s\S]*?\.ps-home-page \{ padding-top: 14px; \}/)
})

test('uses accessible container focus and circular task progress on the portal home', () => {
  const home = read('../src/views/portal/pages/HomeView.vue')
  assert.match(home, /class="ps-task-progress" :style="\{ '--progress': `\$\{task\.progress\}%` \}"/)
  assert.doesNotMatch(home, /class="ps-task-progress"><i/)
  assert.match(portalStyles, /\.ps-task-progress\s*\{[^}]*border-radius: 50%[^}]*conic-gradient\(var\(--ps-blue\) var\(--progress\)/)
  assert.match(portalStyles, /\.ps-task-progress b\s*\{[^}]*position: relative[^}]*color: var\(--ps-blue\)/)
  assert.match(portalStyles, /\.ps-search-hero input:focus-visible\s*\{\s*outline: none;/)
  assert.match(portalStyles, /\.ps-search-hero:focus-within\s*\{[^}]*border-color:[^}]*box-shadow:/)
})

test('keeps the news side rail balanced with the result list', () => {
  const newsList = read('../src/views/portal/pages/NewsListView.vue')
  assert.match(newsList, /class="ps-panel ps-news-overview"/)
  assert.match(newsList, /const overviewStats = computed\(/)
  assert.match(portalStyles, /\.ps-news-aside\s*\{[^}]*grid-template-rows:\s*repeat\(3, minmax\(220px, auto\)\)[^}]*min-height:\s*clamp\(/)
  assert.match(portalStyles, /\.ps-news-aside \.ps-panel\s*\{[^}]*display:\s*flex[^}]*flex-direction:\s*column/)
  assert.match(portalStyles, /\.ps-overview-stat\s*\{[^}]*display:\s*grid/)
  assert.match(portalStyles, /@media \(max-width: 1050px\)[\s\S]*?\.ps-news-aside[^}]*min-height: 0[^}]*grid-template-rows: none/)
})

test('provides interactive pagination for the news list', () => {
  const newsList = read('../src/views/portal/pages/NewsListView.vue')
  assert.match(newsList, /<PortalPageHeader title="资讯列表"/)
  assert.doesNotMatch(newsList, /<PortalPageHeader title="科技资讯"/)
  assert.match(newsList, /class="ps-pagination"/)
  assert.match(newsList, /v-model:current-page="currentPage"/)
  assert.match(newsList, /v-model:page-size="pageSize"/)
  assert.match(newsList, /:total="filteredNews\.length"/)
  assert.match(newsList, /const pagedNews = computed\(/)
  assert.match(newsList, /watch\(\[keyword, sourceType, importance, activeCategory\]/)
  assert.match(portalStyles, /\.ps-pagination\s*\{[^}]*grid-column:\s*1 \/ -1[^}]*display:\s*flex/)
  assert.match(portalStyles, /\.ps-pagination \.el-pagination\s*\{[^}]*width:\s*auto[^}]*justify-content:\s*center[^}]*gap:\s*8px/)
})

test('keeps news category filtering inside the main filter toolbar', () => {
  const newsList = read('../src/views/portal/pages/NewsListView.vue')
  assert.match(newsList, /class="ps-news-category-select" aria-label="资讯分类"/)
  assert.match(newsList, /<el-option v-for="category in categories"/)
  assert.doesNotMatch(newsList, /ps-category-tabs/)
  assert.match(portalStyles, /\.ps-toolbar\s*\{[^}]*display:\s*flex[^}]*gap:\s*10px/)
})

test('uses the available width for paper metadata without breaking narrow layouts', () => {
  const papers = read('../src/views/portal/pages/PaperListView.vue')
  assert.match(papers, /class="ps-paper-main"/)
  assert.match(papers, /class="ps-paper-meta" aria-label="论文概览"/)
  assert.match(papers, /来源期刊/)
  assert.match(papers, /被引次数/)
  assert.match(portalStyles, /.ps-paper-card\s*\{[\s\S]*?grid-template-columns: minmax\(0, 1fr\) minmax\(220px, \.34fr\)/)
  assert.match(portalStyles, /@media \(max-width: 1050px\)[\s\S]*?\.ps-paper-card\s*\{[\s\S]*?grid-template-columns: 1fr/)
  assert.match(portalStyles, /@media \(max-width: 760px\)[\s\S]*?\.ps-paper-meta \{ grid-template-columns: repeat\(2, minmax\(0, 1fr\)\)/)
})

test('keeps the research workbench lead panel quiet and consistent with the page', () => {
  assert.match(portalStyles, /\.ps-research-lead\s*\{[^}]*background: oklch\(97\.5%/)
  assert.doesNotMatch(portalStyles, /\.ps-research-lead\s*\{[^}]*linear-gradient/)
  assert.match(portalStyles, /\.ps-research-lead h2\s*\{[^}]*color: var\(--ps-ink\)/)
  assert.match(portalStyles, /\.ps-research-lead aside\s*\{[^}]*border-left: 1px[^}]*background: transparent/)
})

test('keeps pipeline backend pages inside the management layout', () => {
  const pipelinePages = [
    '../src/views/pipeline/dashboard/index.vue',
    '../src/views/pipeline/intelligence/index.vue',
    '../src/views/pipeline/source/index.vue',
    '../src/views/pipeline/task/index.vue',
    '../src/views/pipeline/knowledge/index.vue',
    '../src/views/pipeline/report/index.vue',
    '../src/views/pipeline/governance/index.vue',
    '../src/views/pipeline/template/index.vue',
    '../src/views/pipeline/model/index.vue'
  ].map(read)
  for (const page of pipelinePages) {
    assert.match(page, /pipeline-page/)
    assert.doesNotMatch(page, /ps-portal/)
  }
})

test('connects data source management to persistent configuration and real trial runs', () => {
  const sourcePage = read('../src/views/pipeline/source/index.vue')
  const pipelineApi = read('../src/api/pipeline/intelligence.js')
  for (const apiName of ['createPipelineSource', 'updatePipelineSource', 'disablePipelineSource', 'runPipelineTask']) {
    assert.match(pipelineApi, new RegExp(`export function ${apiName}`))
    assert.match(sourcePage, new RegExp(apiName))
  }
  assert.match(sourcePage, /source-form-grid/)
  assert.doesNotMatch(sourcePage, /showSourceTodo|将在下一阶段接入/)
})

test('exposes the InsightHub handoff controls on the collection task page', () => {
  const taskPage = read('../src/views/pipeline/task/index.vue')
  const pipelineApi = read('../src/api/pipeline/intelligence.js')
  assert.match(taskPage, /外部处理/)
  assert.match(taskPage, /提交处理/)
  assert.match(taskPage, /同步结果/)
  assert.match(pipelineApi, /\/pipeline\/tasks\/runs\/\$\{runId\}\/handoff/)
  assert.match(pipelineApi, /\/pipeline\/tasks\/runs\/\$\{runId\}\/handoff\/sync/)
})

test('keeps Monaco workers out of the global build and renders AI code blocks lightly', () => {
  const viteConfig = read('../vite.config.js')
  const vitePlugins = read('../vite/plugins/index.js')
  const aiChat = read('../src/views/ai/chat/index.vue')
  const aiMessage = read('../src/views/ai/chat/components/AiMessage.vue')
  assert.match(viteConfig, /'stream-monaco': path\.resolve\(__dirname, '\.\/src\/shims\/stream-monaco\.js'\)/)
  assert.doesNotMatch(vitePlugins, /vite-plugin-monaco-editor-esm|monacoWorkers/)
  assert.doesNotMatch(aiChat, /getUseMonaco/)
  assert.match(aiMessage, /render-code-blocks-as-pre="true"/)
})
