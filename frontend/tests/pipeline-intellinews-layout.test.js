import test from 'node:test'
import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import { getPortalReportPath, getPortalTaskPath, isDigestType } from '../src/views/portal/utils/routing.js'

const read = path => readFileSync(new URL(path, import.meta.url), 'utf8')
const dockerEnv = read('../.env.docker')
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
  assert.doesNotMatch(portalShell, /ps-footer|数据仅按当前账号授权范围展示/)
  assert.doesNotMatch(portalShell, /component:\s*Layout/)
})

test('separates business navigation including my reports from account and evidence tools', () => {
  const navigation = read('../src/views/portal/data.js')
  for (const label of ['首页', '新闻资讯', '科研论文', '科研报告', '情报简报']) {
    assert.match(navigation, new RegExp(`label: '${label}'`))
  }
  assert.match(portalHeader, /portalNavigation/)
  assert.doesNotMatch(portalHeader, /command="reports"/)
  assert.doesNotMatch(portalHeader, /我的任务|我的成果/)
  assert.doesNotMatch(portalHeader, /我的收藏/)
  const navigationOnly = navigation.slice(0, navigation.indexOf('export const topics'))
  assert.doesNotMatch(navigationOnly, /label: '(资料库|个人中心|资料篮)'/)
  assert.doesNotMatch(portalHeader, /ps-task-trigger|aria-label="查看任务"/)
  for (const forbidden of ['系统管理', '系统监控', '系统工具', 'AI 管理']) {
    assert.doesNotMatch(portalHeader, new RegExp(forbidden))
    assert.doesNotMatch(portalShell, new RegExp(forbidden))
  }
})

test('basket has its own route and is no longer a personal center tab', () => {
  const workspace = read('../src/views/portal/pages/MyWorkspaceView.vue')
  assert.match(routerConfig, /path: 'basket', name: 'PortalBasket'/)
  assert.match(routerConfig, /path: 'me\/basket', name: 'PortalMyBasket', redirect: '\/portal\/basket'/)
  assert.match(portalHeader, /router.push\('\/portal\/basket'\)/)
  assert.match(workspace, /<nav v-if="mode !== 'basket'"/)
  const tabs = workspace.split('const workspaceTabs = ')[1].split('\n')[0]
  assert.doesNotMatch(tabs, /basket|资料篮/)
  assert.match(workspace, /portalStore.removeFromBasket\(item.id\)/)
})

test('does not offer external handoff for cancelled or empty collection runs', () => {
 const taskView = read('../src/views/pipeline/task/index.vue')
 assert.doesNotMatch(taskView, /handoff|提交处理|同步结果/)
 assert.match(taskView, /stopPipelineCollectionRun/)
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
  assert.match(home, /class="ps-home-search"/)
  assert.match(home, /class="ps-home-modules"/)
  assert.doesNotMatch(home, /class="ps-workflow-strip"/)
  assert.doesNotMatch(home, /class="ps-home-grid ps-home-content-grid"/)
  assert.doesNotMatch(home, /ps-discovery-grid|ps-discovery-workbench|ps-discovery-page/)
  assert.match(home, /title: '科研报告'/)
  assert.match(home, /title: '情报简报'/)
  assert.match(home, /首页搜索结果/)
  assert.doesNotMatch(home, /知识问答/)
  assert.doesNotMatch(home, /热点主题/)
  assert.doesNotMatch(home, /ps-search-suggestions/)
  assert.match(home, /title: '新闻资讯'/)
  assert.match(home, /title: '科研论文'/)
  assert.doesNotMatch(home, /我的进行中任务|我的最近成果/)
  assert.doesNotMatch(home, /dashboardMetrics|待审核数量|授权资料概览/)
  assert.match(home, /searchPipelineIntelligence\(params\)/)
})

test('provides working cross-page basket, favorites and task panel state', () => {
  assert.match(portalStore, /basket: \[\]/)
  assert.match(portalStore, /favorites: \[\]/)
  assert.match(portalStore, /favoriteItems: \[\]/)
  assert.match(portalStore, /tasks: demoDataEnabled \? recentTasks/)
  assert.match(portalStore, /addToBasket\(item\)/)
  assert.match(portalStore, /toggleFavorite\(id\)/)
  assert.match(portalStore, /favoriteItems = normalizeBusinessData\(workspaceResult\.value\?\.data\?\.favoriteItems \|\| \[\]\)/)
  assert.match(portalStore, /openTaskPanel\(\)/)
  assert.match(portalHeader, /store\.basketCount/)
  assert.match(portalHeader, /portalNavigation/)
  assert.match(portalHeader, /数据同步异常/)
})

test('routes every generated task and report to its real detail page', () => {
  assert.equal(getPortalTaskPath({ id: '3009', type: '科研生成' }), '/portal/research/tasks/3009')
  assert.equal(getPortalTaskPath({ id: '3010', type: '日报周报' }), '/portal/research/tasks/3010')
  assert.equal(getPortalTaskPath({ id: '3011', type: '月报生成' }), '/portal/research/tasks/3011')
  assert.equal(getPortalTaskPath({ id: '3012', type: '资料解析' }), '/portal/me/reports')
  assert.equal(getPortalReportPath({ id: '3013', reportType: 'research-demand' }), '/portal/research/reports/3013')
  assert.equal(getPortalReportPath({ id: '3014', reportType: 'daily' }), '/portal/digests/3014')
  assert.equal(getPortalReportPath({ id: '3015', reportType: 'monthly' }), '/portal/digests/3015')
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
  assert.match(dockerEnv, /VITE_PORTAL_DEMO_DATA=false/)
  assert.match(portalStore, /fallbackNews/)
  assert.match(portalStore, /fallbackDocuments/)
  assert.match(portalStore, /fallbackReports/)
  assert.match(portalHeader, /store\.hydrate\(\)/)
  assert.match(researchWorkbench, /portalStore\.researchReports/)
  assert.match(researchCreate, /searchPipelineResearchMaterials/)
  assert.match(digestList, /portalStore\.digestReports/)
  assert.match(knowledge, /portalStore\.knowledgeDocuments/)
  assert.doesNotMatch(knowledge, /知识问答/)
})

test('keeps missing live metadata distinguishable from real values', () => {
  assert.match(portalStore, /updatedAt: item\.updatedAt \|\| item\.updated_at \|\| '更新时间待补充'/)
  assert.doesNotMatch(portalStore, /updatedAt: item\.updatedAt \|\| '刚刚'/)
  assert.doesNotMatch(portalStore, /new Date\(\)\.getFullYear\(\)/)
  assert.match(portalStore, /年份待补充/)
  assert.match(read('../src/views/portal/pages/ReportEditorView.vue'), /version: '版本待补充'/)
  assert.match(read('../src/views/portal/pages/DigestEditorView.vue'), /版本待补充/)
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
  assert.match(create, /:active="activeStep"/)
  assert.doesNotMatch(create, /ps-create-progress/)
  assert.equal((create.match(/<h1\b/g) || []).length, 1)
  assert.match(task, /stageRows/)
  assert.doesNotMatch(task, /index === 0 \? 'running' : 'waiting'/)
  assert.match(task, /执行记录/)
  assert.match(task, /cancelPipelineResearchJob/)
  assert.match(task, /retryPipelineResearchJob/)
  assert.match(task, /getPortalReportPath\(\{ id: task\.value\.reportId, reportType: task\.value\.type \}\)/)
  assert.match(task, /重新加入生成队列/)
  assert.doesNotMatch(task, /平台标准模板/)
  assert.doesNotMatch(task, /task\.createdAt \|\| '刚刚'/)
  assert.match(task, /模板名称未记录/)
  assert.match(task, /<dt>使用模板<\/dt><dd>\{\{ templateName \}\}<\/dd>/)
  assert.match(task, /function startRefresh\(\)/)
  assert.match(task, /async function loadTask\(\) \{\n  if \(!active \|\| loading\.value\) return/)
  assert.match(task, /const terminalTaskStatuses = \['completed', 'failed', 'dead_letter', 'cancelled'\]/)
  assert.match(task, /startRefresh\(\)\n      ElMessage\.success\('取消请求已提交，任务将在当前阶段结束后停止'\)/)
  assert.match(task, /ElMessage\.success\('任务已取消'\)/)
  assert.match(task, /terminalTaskStatuses\.includes\(task\.value\.status\)/)
  assert.match(create, /任务已进入后台生成队列/)
  assert.match(create, /任务创建失败，请确认后端已启动并完成业务表初始化/)
  assert.match(create, /verifySelected\(true\)/)
  assert.match(create, /error\?\.msg \|\| '资料上传失败，请检查文件或后端服务'/)
  assert.match(editor, /报告目录/)
  assert.match(editor, /引用来源/)
  assert.doesNotMatch(editor, /askPipelineKnowledge/)
  assert.doesNotMatch(editor, /质量问题/)
  assert.match(editor, /版本记录/)
  assert.match(editor, /导出记录/)
  assert.match(editor, /downloadExportItem/)
  assert.match(editor, /watch\(activeRightTab, tab => \{ if \(tab === '导出记录'\) loadExports\(\) \}\)/)
  assert.match(editor, /@click="applyFormat\(tool\)"/)
  assert.match(editor, /function applyFormat\(tool\)/)
  assert.match(editor, /@click="openCitation\(source\)"/)
  assert.match(editor, /function openCitation\(source\)/)
  assert.match(editor, /:contenteditable="!isReadOnly" aria-label="编辑章节标题" @input="updateSectionTitle\(\$event, section\)"/)
  assert.match(editor, /function updateSectionTitle\(event, section = currentSection.value\)/)
  assert.match(editor, /function moveSection\(offset, sectionId = currentSectionId.value\)/)
  assert.match(editor, /function removeSection\(sectionId = currentSectionId.value\)/)
  assert.match(editor, /function sectionCitationCount\(section\)/)
  assert.doesNotMatch(editor, /const completeness|const incompleteCount/)
  assert.match(editor, /const isReadOnly = computed\(\(\) => Boolean\(report\.value\.readOnly\) \|\| report\.value\.status === 'published'\)/)
  assert.match(editor, /当前报告已正式发布，处于只读状态/)
  assert.match(editor, /:contenteditable="!isReadOnly"/)
  assert.match(editor, /:disabled="isReadOnly" :loading="versionSaving" @click="saveVersion"/)
  assert.match(editor, /if \(isReadOnly\.value\) return/)
  assert.match(editor, /:disabled="isReadOnly">恢复此版本<\/el-dropdown-item>/)
  assert.doesNotMatch(editor, /askPipelineKnowledge/)
  assert.match(editor, /restorePipelineResearchReportVersion/)
  assert.match(diagram, /ReportImageAssets/)
  assert.doesNotMatch(diagram, /defaultDiagram|节点库|导出 SVG/)
})

test('implements digest and evidence-grounded knowledge workflows', () => {
  const digestCreate = read('../src/views/portal/pages/DigestCreateView.vue')
  const digestList = read('../src/views/portal/pages/DigestListView.vue')
  const digestEditor = read('../src/views/portal/pages/DigestEditorView.vue')
  const knowledge = read('../src/views/portal/pages/KnowledgeView.vue')
  assert.match(digestCreate, /<h2>候选资料<\/h2>/)
  assert.doesNotMatch(digestCreate, /候选内容核验与选材|数据缺口与覆盖|来源统计|栏目建议/)
  assert.match(digestCreate, /v-else-if="previewError"[\s\S]*?role="alert"/)
  assert.match(digestCreate, /@change="toggleCandidate\(item.id, \$event\)"/)
  assert.match(digestCreate, /@click="selectCurrentPage">\{\{ currentCandidatePageSelected \? '取消当前页选择' : '全选当前页'/)
  assert.match(digestCreate, /selectedCandidateIds/)
  assert.doesNotMatch(digestCreate, /setTimeout\(/)
  assert.match(digestCreate, /portal\/research\/tasks/)
  assert.doesNotMatch(digestCreate, /portal\/digests\/\$\{res\.data\.reportId\}/)
  assert.doesNotMatch(digestCreate, /保存说明/)
  assert.doesNotMatch(digestCreate, /ps-form-note|<h2>报告配置<\/h2>|ps-step-title|下一步：/)
  assert.match(digestCreate, /创建失败，请确认后端和数据库已启动/)
  assert.match(digestCreate, /value="月报"/)
  assert.match(digestCreate, /type="month"/)
  assert.match(digestCreate, /reportType: 'monthly'/)
  assert.match(digestCreate, /listPipelineTemplates/)
  assert.match(digestCreate, /publishedOnly: true/)
  assert.match(digestCreate, /new Date\(year, monthIndex \+ 1, 0\)/)
  const jobCreateIndex = digestCreate.indexOf('const res = await createPipelineResearchJob')
  const scheduleCreateIndex = digestCreate.indexOf('await createPipelineDigestSchedule')
  assert.ok(jobCreateIndex >= 0 && scheduleCreateIndex > jobCreateIndex, '任务必须先于自动计划创建')
  assert.match(digestCreate, /const requestId = ensureRequestId\(payload\)/)
  assert.match(digestCreate, /requestId,/)
  assert.match(digestCreate, /任务已入队，但自动计划保存失败/)
  assert.match(digestList, /'月报'/)
  assert.match(digestList, /'月报': 'monthly'/)
  assert.match(digestEditor, /候选资讯/)
  assert.match(digestEditor, /来源清单/)
  assert.match(digestEditor, /质量检查/)
  assert.match(digestEditor, /getPipelineResearchReport/)
  assert.match(digestEditor, /updatePipelineResearchReport/)
  assert.match(digestEditor, /saveVersion/)
  assert.match(digestEditor, /monthly: '科技情报月报'/)
  assert.match(digestEditor, /data-placeholder="当前栏目暂无正文，请在此补充。"/)
  assert.match(digestEditor, /class="\{ 'is-empty': !currentSection\.content \}"/)
  assert.match(digestEditor, /v-text="currentSection\.content"/)
  assert.doesNotMatch(digestEditor, /v-text="currentSection\.content \|\| '当前栏目暂无正文，请在此补充。'"/)
  assert.match(digestEditor, /const isReadOnly = computed\(\(\) => digest\.value\.status === 'published'\)/)
  assert.match(digestEditor, /当前简报已正式发布，处于只读状态/)
  assert.match(digestEditor, /:contenteditable="!isReadOnly"/)
  assert.match(digestEditor, /:disabled="isReadOnly" @click="runQualityCheck"/)
  assert.match(digestEditor, /if \(isReadOnly\.value\) return/)
  assert.match(knowledge, /上传资料/)
  assert.doesNotMatch(knowledge, /知识问答/)
})

test('connects template management and user creation to published template APIs', () => {
 const page = read('../src/views/pipeline/template/index.vue')
 assert.match(page, /prompt: item.prompt.trim\(\)/)
 assert.match(page, /modelId: item.modelId \|\| null/)
 assert.match(page, /imageModelId: item.imageModelId \|\| null/)
 assert.doesNotMatch(page, /publishPipelineTemplate|saveAndPublish|发布版本|保存草稿/)
 assert.match(read('../src/views/portal/pages/ResearchCreateView.vue'), /publishedOnly: true/)
})

test('distinguishes dashboard and template service failures from empty business data', () => {
 for (const [path, errorName, handler] of [['dashboard','dashboardError','loadDashboard'],['template','templateError','loadTemplates']]) {
  const page = read('../src/views/pipeline/' + path + '/index.vue')
  assert.ok(page.includes(errorName + '.value = error'))
  assert.ok(page.includes('@click="' + handler + '"'))
 }
})

test('keeps the digest creation page to one clear title context', () => {
  const digestCreate = read('../src/views/portal/pages/DigestCreateView.vue')
  assert.doesNotMatch(digestCreate, /class="ps-breadcrumb"/)
  assert.match(digestCreate, /<h1>新建简报<\/h1>/)
  assert.match(digestCreate, /aria-label="返回情报简报" title="返回情报简报" @click="router.push\('\/portal\/digests'\)"/)
  assert.match(digestCreate, /<Back\s*\/>/)
  assert.match(digestCreate, /grid-template-columns: 44px minmax\(0, 1fr\)/)
})

test('makes global search filters and cross-type result routing functional', () => {
  const search = read('../src/views/portal/pages/SearchView.vue')
  const workspace = read('../src/views/portal/pages/MyWorkspaceView.vue')
  const taskPanel = read('../src/views/portal/components/PortalTaskPanel.vue')
  const home = read('../src/views/portal/pages/HomeView.vue')
  assert.match(search, /searchPipelineIntelligence/)
  assert.match(search, /source: source\.value/)
  assert.match(search, /dateRange: dateRange\.value/)
  assert.match(search, /pageNum: currentPage\.value/)
  assert.match(search, /pageSize: pageSize\.value/)
  assert.doesNotMatch(search, /耗时 0\.18 秒/)
  assert.match(workspace, /portalStore\.basket/)
  assert.doesNotMatch(workspace, /favoriteItems|取消收藏/)
  assert.match(taskPanel, /getPortalTaskPath\(task\)/)
  assert.doesNotMatch(home, /newsTimeline|paperTimeline/)
  assert.doesNotMatch(home, /近 24 小时新增 24 条/)
  assert.doesNotMatch(search, /portalStore\.hotTopics/)
  assert.match(search, /loadError/)
  assert.doesNotMatch(search, /fallbackTopics/)
})

test('hardens the user knowledge workspace with real document lifecycle states', () => {
  const knowledge = read('../src/views/portal/pages/KnowledgeView.vue')
  const detail = read('../src/views/portal/pages/KnowledgeDetailView.vue')
  for (const apiName of ['getPipelineKnowledgeDocument', 'reparsePipelineKnowledgeDocument', 'deletePipelineKnowledgeDocument']) {
    assert.match(pipelineApi, new RegExp(`export function ${apiName}`))
  }
  assert.match(pipelineApi, /\/pipeline\/knowledge\/documents\/\$\{requireBusinessId\(documentId\)\}\/retry/)
  assert.match(knowledge, /MAX_FILE_SIZE = 16 \* 1024 \* 1024/)
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
  const primaryPages = ['ResearchWorkbenchView.vue', 'DigestListView.vue']
    .map(file => read(`../src/views/portal/pages/${file}`))
  for (const page of primaryPages) {
    assert.doesNotMatch(page, /<PortalPageHeader\b|<h1\b/)
    assert.match(page, /class="ps-toolbar ps-(research|digest)-toolbar"/)
    assert.match(page, /搜索.*报告|搜索简报或计划名称/)
    assert.match(page, /新建报告|新建简报/)
  }
  assert.equal((read('../src/views/portal/pages/KnowledgeView.vue').match(/<PortalPageHeader\b/g) || []).length, 1)
  const papers = read('../src/views/portal/pages/PaperListView.vue')
  assert.doesNotMatch(papers, /<PortalPageHeader\b|<h1\b/)
  assert.doesNotMatch(papers, /ps-paper-library-actions/)
  assert.doesNotMatch(portalShell, /PortalWorkflowGuide|ps-route-context/)
  const news = read('../src/views/portal/pages/NewsListView.vue')
  assert.doesNotMatch(news, /PortalPageHeader|<h1\b/)
  assert.doesNotMatch(news, /ps-list-summary|toggleFavorite|已收藏/)
  assert.doesNotMatch(news, /<template #actions>/)
  assert.match(portalHeader, /资料篮/)
  assert.match(news, /加入资料篮/)
  const pageHeader = read('../src/views/portal/components/PortalPageHeader.vue')
  assert.match(pageHeader, /'is-compact': !description/)
  assert.match(portalStyles, /\.ps-page-header\.is-compact\s*\{[^}]*min-height:\s*58px/)
})

test('keeps the Calm-style login modal closed until the user clicks an entry', () => {
  assert.match(loginPage, /class="pipeline-user-login calm-login-page calm-homepage-auth"/)
  assert.match(loginPage, /const loginVisible = ref\(false\)/)
  assert.match(loginPage, /@click="startTrial"/)
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
  assert.match(portalStyles, /--ps-blue: #005487/)
  assert.match(portalStyles, /--ps-teal: #08736d/)
  assert.match(portalStyles, /\.ps-header\s*\{/)
  assert.match(portalStyles, /\.ps-home-hero\s*\{/)
  assert.match(portalStyles, /\.ps-editor-layout\s*\{/)
  assert.match(portalStyles, /@media \(max-width: 1050px\)/)
  assert.match(portalStyles, /@media \(max-width: 760px\)/)
  assert.match(portalStyles, /@media \(prefers-reduced-motion: reduce\)/)
})

test('uses fluid shell widths and content-driven grids on large screens', () => {
  assert.match(portalStyles, /\.ps-header-inner\s*\{[^}]*width: 100%[^}]*padding: 0 16px/)
  assert.match(portalStyles, /\.ps-page\s*\{[^}]*width: min\(1600px, calc\(100% - clamp\(24px, 4vw, 64px\)\)\)/)
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
  assert.match(portalStyles, /\.ps-home-hero\s*\{[\s\S]*?min-height: 250px/)
  assert.match(portalStyles, /\.ps-home-welcome h1\s*\{[\s\S]*?color: oklch\(26%/)
  assert.match(portalStyles, /\.ps-home-welcome > p\s*\{[\s\S]*?color: oklch\(46%/)
  assert.match(portalStyles, /\.ps-hero-search input::placeholder\s*\{[\s\S]*?opacity: 1/)
  assert.match(portalStyles, /\.ps-hero-brief\s*\{[\s\S]*?background: oklch\(99%/)
  assert.match(portalStyles, /\.ps-hero-brief > strong\s*\{[\s\S]*?color: oklch\(26%/)
  assert.match(portalStyles, /\.ps-brief-metrics span\s*\{[\s\S]*?color: oklch\(45%/)
  assert.match(portalStyles, /@media \(max-width: 1050px\)[\s\S]*?\.ps-home-hero \{[^}]*grid-template-columns: minmax\(0, 1\.25fr\) minmax\(280px, \.75fr\)/)
  assert.match(portalStyles, /@media \(max-width: 760px\)[\s\S]*?\.ps-home-page \{ padding-top: 14px; \}/)
})

test('keeps home search accessible without personal task cards', () => {
  const home = read('../src/views/portal/pages/HomeView.vue')
  assert.match(home, /aria-label="搜索研究资料"/)
  assert.match(home, /role="search"/)
  assert.doesNotMatch(home, /activeTasks|recentReports|ps-my-work|ps-home-results/)
  assert.doesNotMatch(home, /class="ps-task-progress"><i/)
  assert.match(portalStyles, /\.ps-task-progress\s*\{[^}]*border-radius: 50%[^}]*conic-gradient\(var\(--ps-blue\) var\(--progress\)/)
  assert.match(portalStyles, /\.ps-task-progress b\s*\{[^}]*position: relative[^}]*color: var\(--ps-blue\)/)
  assert.match(portalStyles, /\.ps-search-hero input:focus-visible\s*\{\s*outline: none;/)
  assert.match(portalStyles, /\.ps-search-hero:focus-within\s*\{[^}]*border-color:[^}]*box-shadow:/)
})

test('news results use the full content width without a redundant side rail', () => {
  const newsList = read('../src/views/portal/pages/NewsListView.vue')
  assert.doesNotMatch(newsList, /overviewStats|ps-news-aside|ps-content-with-aside/)
  assert.match(newsList, /class="ps-news-content"/)
  assert.match(newsList, /class="ps-pagination"/)
})

test('provides interactive pagination for the news list', () => {
  const newsList = read('../src/views/portal/pages/NewsListView.vue')
  assert.doesNotMatch(newsList, /<PortalPageHeader/)
  assert.doesNotMatch(newsList, /<PortalPageHeader title="科技资讯"/)
  assert.match(newsList, /ps-pagination/)
  assert.match(newsList, /v-model:current-page="currentPage"/)
  assert.match(newsList, /v-model:page-size="pageSize"/)
  assert.match(newsList, /:total="total"/)
  assert.doesNotMatch(newsList, /const pagedNews = computed\(/)
  assert.match(newsList, /useListQuery/)
  assert.match(newsList, /useListRequest/)
  assert.match(newsList, /validPage\(total\.value, pageSize\.value, currentPage\.value\)/)
  assert.match(portalStyles, /\.ps-pagination\s*\{[^}]*grid-column:\s*1 \/ -1[^}]*display:\s*flex/)
  assert.match(portalStyles, /\.ps-pagination \.el-pagination\s*\{[^}]*width:\s*100%[^}]*justify-content:\s*flex-start[^}]*gap:\s*12px/)
})

test('portal list pagination shares the original news left-summary right-controls layout', () => {
  const pages = ['NewsListView', 'PaperListView', 'SearchView', 'KnowledgeView', 'ResearchWorkbenchView']
  for (const page of pages) {
    const source = read(`../src/views/portal/pages/${page}.vue`)
    assert.match(source, /class="ps-pagination"/)
    assert.match(source, /:pager-count="5"/)
    assert.match(source, /layout="total,(?: sizes,)? ->, prev, pager, next/)
  }
  assert.match(portalStyles, /\.ps-pagination \.el-pagination\s*\{[^}]*align-items:\s*center[^}]*justify-content:\s*flex-start/)
  assert.match(portalStyles, /\.ps-pagination \.el-pagination \.el-pagination__rightwrapper\s*\{[^}]*margin-left:\s*auto[^}]*float:\s*none/)
  assert.match(portalStyles, /\.ps-pagination \.el-pagination > \*,[\s\S]*?margin:\s*0/)
  assert.match(portalStyles, /\.ps-pagination \.el-pagination__jump\s*\{[^}]*flex-basis:\s*100%[^}]*justify-content:\s*center/)
  const workspace = read('../src/assets/styles/workspace.scss')
  assert.doesNotMatch(workspace, /\.ps-pagination \.el-pagination\s*\{[^}]*justify-content:\s*flex-start/)
})

test('every portal paginated list offers only ten, twenty and fifty items', () => {
  for (const page of ['HomeView', 'NewsListView', 'PaperListView', 'SearchView', 'KnowledgeView', 'ResearchWorkbenchView', 'DigestListView', 'MyWorkspaceView']) {
    const source = read(`../src/views/portal/pages/${page}.vue`)
    assert.match(source, /:page-sizes="\[10, 20, 50\]"/)
    assert.match(source, /v-model:page-size="(?:pageSize|searchPageSize)"/)
    assert.doesNotMatch(source, /size: (?:5|20)\b|\[5, 10, 20\]/)
  }
})

test('paper cards group tags and actions into a compact responsive footer', () => {
  const source = read('../src/views/portal/pages/PaperListView.vue')
  assert.match(source, /class="ps-paper-footer"[\s\S]*?class="ps-tag-row"[\s\S]*?class="ps-paper-actions"/)
  assert.match(source, /\.ps-paper-footer\s*\{[^}]*display:\s*flex[^}]*align-items:\s*center[^}]*flex-wrap:\s*wrap/)
  assert.match(source, /<el-button type="primary" plain[^>]*@click="add\(paper\)"/)
  assert.doesNotMatch(source, /复制引用|copyCitation/)
  assert.match(source, /\.ps-paper-library \.ps-paper-actions\s*\{[^}]*margin:\s*0 0 0 auto[^}]*border:\s*0/)
  assert.doesNotMatch(source, /column-reverse|\{\{\s*paper\.abstract/)
})

test('uses one multi-select tag filter without a duplicate category filter', () => {
  const newsList = read('../src/views/portal/pages/NewsListView.vue')
  const newsDetail = read('../src/views/portal/pages/NewsDetailView.vue')
  assert.doesNotMatch(newsList + newsDetail, /ps-importance|(?:item|article)\.importance|全部等级/)
  assert.doesNotMatch(newsList, /ps-news-category-select|全部分类|v-model="activeCategory"/)
  assert.match(newsList, /v-model="activeTags" multiple[^>]*clearable[^>]*aria-label="资讯标签"/)
  assert.doesNotMatch(newsList, /ps-category-tabs/)
  assert.match(portalStyles, /\.ps-toolbar\s*\{[^}]*display:\s*flex[^}]*gap:\s*10px/)
})

test('uses the available width for paper metadata without breaking narrow layouts', () => {
  const papers = read('../src/views/portal/pages/PaperListView.vue')
  assert.doesNotMatch(papers, /\{\{\s*paper\.abstract\s*\}\}/)
  assert.match(papers, /class="ps-paper-main"/)
  assert.match(papers, /class="ps-paper-meta" aria-label="论文概览"/)
  assert.match(papers, /ps-paper-journal-name/)
  assert.match(papers, /被引次数/)
  assert.doesNotMatch(papers, /<aside|文献概览/)
  assert.doesNotMatch(papers, />查看详情</)
  assert.match(papers, /<router-link class="ps-paper-title" :to="`\/portal\/papers\/\$\{paper\.id\}`"/)
  assert.match(papers, /target="_blank" rel="noopener noreferrer"/)
  assert.match(papers, /paper\.title\.trim\(\) !== paper\.titleZh\?\.trim\(\)/)
  assert.match(papers, /\.ps-paper-library \.ps-paper-card \{ display: block/)
  assert.match(papers, /\.ps-paper-main \.ps-paper-meta \{ display: flex; flex-wrap: wrap/)
  assert.match(papers, /@media \(max-width: 600px\)/)
})

test('image-free news cards use a labelled theme cover without inventing source photography', () => {
  const news = read('../src/views/portal/pages/NewsListView.vue')
  assert.match(news, /item\.cover_image \|\| viewMode === 'card'/)
  assert.match(news, /<img v-if="item\.cover_image" :src="item\.cover_image"/)
  assert.match(news, /v-else class="ps-news-theme-cover" role="img"/)
  assert.match(news, /主题示意 · 非新闻原图/)
  assert.match(news, /\.ps-news-theme-cover \{[^}]*height: 200px/)
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
    '../src/views/pipeline/template/index.vue',
    '../src/views/pipeline/model/index.vue'
  ].map(read)
  for (const page of pipelinePages) {
    assert.match(page, /pipeline-page/)
    assert.doesNotMatch(page, /ps-portal/)
  }
})

test('keeps report management actions connected to real portal flows', () => {
  const reportPage = read('../src/views/pipeline/report/index.vue')
  const digestCreate = read('../src/views/portal/pages/DigestCreateView.vue')
  assert.match(reportPage, /function openReport\(row\)/)
  assert.match(reportPage, /router\.push\(getPortalReportPath\(/)
  assert.match(reportPage, /function openCreate\(title\)/)
  assert.match(reportPage, /path: '\/portal\/digests\/create', query: \{ type: '日报' \}/)
  assert.match(reportPage, /router\.push\('\/portal\/research\/create'\)/)
  assert.doesNotMatch(reportPage, /showComingSoon|将在下一阶段接入/)
  assert.match(digestCreate, /const initialType = \(\{ 日报: '日报', 周报: '周报', 月报: '月报' \}\)\[String\(route\.query\.type \|\| ''\)\]/)
  assert.match(digestCreate, /type: initialType/)
})

test('protects backend report export with its explicit management permission', () => {
 const page = read('../src/views/pipeline/report/index.vue')
 assert.ok(page.includes("pipeline:report:export"))
 assert.match(page, /exportPipelineReport/)
})

test('keeps report reading metadata grounded in persisted records', () => {
  const reportPage = read('../src/views/pipeline/report/index.vue')
  assert.match(reportPage, /const filteredRows = computed\(\(\) =>/)
  assert.match(reportPage, /:data="filteredRows"/)
  assert.match(reportPage, /当前条件下暂无成果/)
  assert.doesNotMatch(reportPage, /系统已完成来源汇聚与结构化处理/)
  assert.doesNotMatch(reportPage, /selectedReport\?\.type \|\| '科技情报日报'/)
  assert.doesNotMatch(reportPage, /selectedReport\?\.owner \|\| '情报研判组'/)
})

test('does not treat model configuration load failures as empty routes', () => {
 const page = read('../src/views/pipeline/model/index.vue')
 assert.match(page, /v-else-if="modelError"/)
 assert.match(page, /categoryError.value = error/)
 assert.match(page, /@click="loadCategories"/)
 assert.doesNotMatch(page, /listPipelineModelRoutes|listPipelinePrompts/)
})

test('shows data-filter readiness before collection can rely on model processing', () => {
 const page = read('../src/views/pipeline/model/index.vue')
 assert.match(page, /categoryPayload\(categoryForm\)/)
 assert.match(page, /modelId: null, appliesTo: 'all', sortOrder: 0, isEnabled: false/)
 assert.match(page, /modelsFor\(models.value, 'text_generate'\)/)
})

test('keeps model and Prompt controls aligned with backend permissions', () => {
 const page = read('../src/views/pipeline/model/index.vue')
 for (const permission of ['ai:model:query','ai:model:add','ai:model:edit']) assert.ok(page.includes(permission))
 assert.match(page, /v-if="canModelAdd"/)
 assert.match(page, /v-if="canCategorySave"/)
 assert.match(page, /v-if="canCategoryDelete"/)
 assert.ok(page.includes("checkRole(['admin'])"))
 assert.doesNotMatch(page, /场景路由|Prompt 版本|调用审计/)
})

test('connects data source management to persistent configuration and real trial runs', () => {
 const page = read('../src/views/pipeline/source/index.vue')
 for (const name of ['createPipelineSource','updatePipelineSource','disablePipelineSource','runPipelineTask']) assert.ok(page.includes(name))
 assert.match(page, /isEnabled: sourceForm.isEnabled/)
 assert.match(page, /adapter: sourceForm.adapterKey/)
 assert.match(page, /来源已停用，排队任务取消/)
 assert.doesNotMatch(page, /handoffMode|processorSourceCode|InsightHub/)
})

test('keeps source and task actions aligned with backend permissions', () => {
 const page = read('../src/views/pipeline/source/index.vue') + read('../src/views/pipeline/task/index.vue')
 for (const permission of ['pipeline:source:list','pipeline:source:save','pipeline:task:list','pipeline:task:run']) assert.ok(page.includes(permission))
 assert.match(page, /!canTaskRun.value \|\|/)
 assert.match(page, /!sourceEnabled\(row\)/)
})

test('does not expose inaccessible management entries from the dashboard', () => {
  const dashboardPage = read('../src/views/pipeline/dashboard/index.vue')
  assert.match(dashboardPage, /import \{ checkPermi \} from '\@\/utils\/permission'/)
  assert.match(dashboardPage, /v-for="item in visibleAdminEntries"/)
  assert.match(dashboardPage, /const visibleAdminEntries = computed\(\(\) => adminEntries\.filter\(item => checkPermi\(\[item\.permission\]\)\)\)/)
  assert.doesNotMatch(dashboardPage, /canReviewList|pending_reviews/)
  for (const permission of ['pipeline:source:list', 'pipeline:task:list', 'pipeline:template:list', 'ai:model:list', 'pipeline:report:list']) {
    assert.match(dashboardPage, new RegExp(permission.replace(':', '\\:')))
  }
})

test('distinguishes collection and report service failures from empty lists', () => {
  const sourcePage = read('../src/views/pipeline/source/index.vue')
  const taskPage = read('../src/views/pipeline/task/index.vue')
  const reportPage = read('../src/views/pipeline/report/index.vue')
  for (const [page, errorName, reloadHandler, rowsName] of [
    [sourcePage, 'sourceError', 'loadSources', 'rows.value = []'],
    [taskPage, 'taskError', 'loadTasks', 'taskError.value = error'],
    [reportPage, 'reportError', 'loadReports', 'rows.value = []']
  ]) {
    assert.match(page, new RegExp(`${errorName} = ref\\(''\\)`))
    assert.match(page, new RegExp(`@click="${reloadHandler}"`))
    assert.match(page, new RegExp(rowsName.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')))
  }
  assert.match(taskPage, /class="table-card"/)
  assert.match(reportPage, /<el-card v-else[^>]*class="table-card report-review-table"/)
})

test('exposes the InsightHub handoff controls on the collection task page', () => {
 const page = read('../src/views/pipeline/task/index.vue')
 assert.doesNotMatch(page, /InsightHub|handoff|提交处理|同步结果/)
 assert.match(page, /停止本次/)
 assert.match(page, /正在停止/)
 assert.match(page, /取消排队/)
})

test('makes failed collection runs inspectable and retryable', () => {
 const page = read('../src/views/pipeline/task/index.vue')
 assert.match(page, /row.status === 'failed'/)
 assert.match(page, /retryPipelineTask\(id\)/)
 assert.match(page, /detail.parentId \|\| detail.parent_id/)
 assert.match(page, /原失败记录保留/)
 assert.match(page, /setTimeout/)
 assert.match(page, /onBeforeUnmount/)
})

test('keeps governance and review results truthful when list requests fail', () => {
 const page = read('../src/views/pipeline/intelligence/index.vue')
 assert.match(page, /loadError = ref\(''\)/)
 assert.match(page, /@click="getList"/)
 assert.doesNotMatch(page, /listPipelineReviews|reviewPipelineContent|待审核队列/)
 assert.equal(existsSync(new URL('../src/views/pipeline/governance/index.vue', import.meta.url)), false)
})

test('retired governance and filter components and business APIs are physically absent', () => {
 for (const path of ['views/pipeline/governance/index.vue', 'views/pipeline/filter/index.vue', 'utils/pipeline/filterResult.js']) assert.equal(existsSync(new URL('../src/' + path, import.meta.url)), false)
 assert.doesNotMatch(read('../src/api/pipeline/intelligence.js'), /getPipelineGovernance|batchUpdatePipelineGovernance|listPipelineDuplicateGroups|reviewPipelineContent|listPipelinePrompts|dispatchPipelineHandoff/)
 const intelligence = read('../src/views/pipeline/intelligence/index.vue')
 assert.doesNotMatch(intelligence, /reviewPipelineContent|reprocessPipelineContent|待审核/)
})

test('keeps Monaco workers out of the global build and renders AI code blocks lightly', () => {
  for (const path of ['views/ai/chat/index.vue', 'views/ai/chat/components/AiMessage.vue', 'api/ai/chat.js', 'shims/stream-monaco.js']) {
    assert.equal(existsSync(new URL('../src/' + path, import.meta.url)), false)
  }
  const config = read('../vite.config.js')
  const pkg = JSON.parse(read('../package.json'))
  assert.doesNotMatch(config, /stream-monaco|monacoWorkers/)
  for (const name of ['markstream-vue', 'stream-markdown', 'stream-monaco', 'mermaid', 'katex', 'shiki', 'uuid', '@antv/infographic', 'vite-plugin-monaco-editor-esm']) {
    assert.equal(pkg.dependencies[name] || pkg.devDependencies[name], undefined, name)
  }
  assert.equal(existsSync(new URL('../src/views/pipeline/model/index.vue', import.meta.url)), true)
})
