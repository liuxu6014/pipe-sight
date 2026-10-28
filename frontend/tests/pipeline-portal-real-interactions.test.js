import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const read = path => readFileSync(new URL(path, import.meta.url), 'utf8')
const paperList = read('../src/views/portal/pages/PaperListView.vue')
const paperDetail = read('../src/views/portal/pages/PaperDetailView.vue')
const newsDetail = read('../src/views/portal/pages/NewsDetailView.vue')
const knowledge = read('../src/views/portal/pages/KnowledgeView.vue')
const knowledgeDetail = read('../src/views/portal/pages/KnowledgeDetailView.vue')
const digestList = read('../src/views/portal/pages/DigestListView.vue')
const digestEditor = read('../src/views/portal/pages/DigestEditorView.vue')
const reportEditor = read('../src/views/portal/pages/ReportEditorView.vue')
const taskView = read('../src/views/portal/pages/ResearchTaskView.vue')
const researchWorkbench = read('../src/views/portal/pages/ResearchWorkbenchView.vue')
const newsList = read('../src/views/portal/pages/NewsListView.vue')
const diagram = read('../src/views/portal/pages/DiagramEditorView.vue')
const portalStyles = read('../src/assets/styles/portal.scss')

test('paper pages omit citation controls and removed detail tabs', () => {
  assert.doesNotMatch(paperList, /复制引用|copyCitation/)
  for (const page of [paperDetail]) {
    assert.doesNotMatch(page, /复制引用|copyCitation|writeClipboard/)
    assert.doesNotMatch(page, /citationText\(\)|引用信息|关联资料/)
    assert.doesNotMatch(page, /引用导出/)
  }
})

test('opens paper and news sources only when a valid URL is available', () => {
  assert.match(paperList, /<a v-if="doiUrl\(paper\)"[^>]*:href="doiUrl\(paper\)"[^>]*target="_blank" rel="noopener noreferrer"/)
  assert.doesNotMatch(paperList, /查看来源|sourceActionLabel|openPaperSource/)
  assert.match(paperDetail, /<a v-if="doiUrl"[^>]*:href="doiUrl"[^>]*target="_blank" rel="noopener noreferrer"/)
  assert.doesNotMatch(paperDetail, /查看来源|openPaperSource/)
  assert.match(newsDetail, /v-if="articleUrl"/)
  assert.match(newsDetail, /rel="noopener noreferrer"/)
  assert.match(newsDetail, /<h1><a v-if="articleUrl"/)
  assert.match(newsDetail, /<template v-else>\{\{ article.title \}\}<\/template>/)
  assert.doesNotMatch(newsDetail, /查看原文|暂无原文链接/)
  assert.doesNotMatch(newsDetail, /原文链接将在正式数据接入后打开/)
  assert.doesNotMatch(newsDetail, /\|\| portalStore\.newsItems\[0\]/)
  assert.doesNotMatch(paperDetail, /\|\| portalStore\.paperItems\[0\]/)
  assert.match(newsDetail, /资讯不存在/)
  assert.match(paperDetail, /论文不存在/)
})

test('does not show cached intelligence after an unauthorized detail response', () => {
  for (const page of [newsDetail, paperDetail]) {
    assert.match(page, /const detailError = ref\(''\)/)
    assert.match(page, /const detailLoading = ref\(true\)/)
    assert.match(page, /detailError\.value = error\?\.msg/)
    assert.match(page, /v-else-if="detailError"[\s\S]*action-label="重新加载"/)
    assert.doesNotMatch(page, /list cache remains a usable fallback/)
  }
  assert.doesNotMatch(newsDetail, /portalStore\.newsItems\.find\(item => item\.id === route\.params\.itemId\)/)
  assert.doesNotMatch(paperDetail, /portalStore\.paperItems\.find\(item => item\.id === route\.params\.itemId\)/)
})

test('honors material ownership and uses the controlled download endpoint', () => {
  assert.match(knowledge, /doc\.canManage !== false/)
  assert.match(knowledgeDetail, /const canManage = computed/)
  assert.match(knowledgeDetail, /downloadPipelineKnowledgeDocument\(document\.value\.id/)
  assert.match(knowledgeDetail, /allowDownload !== false/)
  assert.match(knowledgeDetail, /可搜索 PDF 可直接提取文字/)
})

test('uses real digest export and removes actions without backend support', () => {
  assert.match(digestList, /import \{ exportPipelineResearchReport \}/)
  assert.match(digestList, /await exportPipelineResearchReport\(report\.id,/)
  assert.match(digestList, /new Blob\(\[res\.data\.content\]/)
  assert.match(digestList, /URL\.createObjectURL\(blob\)/)
  assert.match(digestList, /query: \{ panel: 'sources' \}/)
  assert.match(digestEditor, /sources: '来源清单', exports: '导出记录'/)
  for (const placeholder of ['已复制为新草稿', '导出任务已创建', '删除草稿']) {
    assert.doesNotMatch(digestList, new RegExp(placeholder))
  }
})

test('does not expose editor defaults before the real report is loaded', () => {
  for (const editor of [reportEditor, digestEditor]) {
    assert.match(editor, /loading && !loaded/)
    assert.match(editor, /loadError && !loaded/)
    assert.match(editor, /v-else-if="loaded"/)
    assert.match(editor, /loadError\.value = error\?\.msg/)
  }
  assert.doesNotMatch(reportEditor, /reportDepartment|编制部门待补充/)
  assert.doesNotMatch(reportEditor, /完整性技术中心|2026年8月/)
  assert.match(taskView, /loading && !loaded/)
  assert.match(taskView, /loadError && !loaded/)
  assert.match(taskView, /v-else-if="loaded"/)
  assert.match(taskView, /loadError\.value = error\?\.msg/)
})

test('does not present fabricated analysis or bypass published report templates', () => {
  assert.doesNotMatch(newsDetail, /可提升缺陷复核与维修排序效率|统一时空基准与多源特征融合/)
  assert.match(newsDetail, /articleAnalysis/)
  assert.doesNotMatch(newsDetail, /projectInsight|article-insight|结构化项目启示/)
  assert.doesNotMatch(paperDetail, /解决多源检测条件下缺陷识别结果不一致|建立统一评价框架|可用于技术路线选型/)
  assert.match(paperDetail, /aiInterpretation/)
  assert.match(read('../src/views/portal/pages/ResearchCreateView.vue'), /listPipelineTemplates\(\{ category: 'research', publishedOnly: true \}\)/)
  assert.doesNotMatch(researchWorkbench, /listPipelineTemplates|报告模板/)
  assert.doesNotMatch(researchWorkbench, /import \{ reportTemplates \} from '\.\.\/data'/)
  assert.doesNotMatch(researchWorkbench, /默认模板 · 2026版/)
  assert.doesNotMatch(newsList, /sourceStats|ps-news-aside/)
  assert.doesNotMatch(newsList, /能源科技观察|管道技术前沿|国际管道研究中心/)
  assert.doesNotMatch(digestEditor, /本栏目围绕管网科技创新汇总本周期可信信息/)
  assert.match(digestEditor, /当前栏目没有关联来源，暂不能按证据重组/)
  assert.doesNotMatch(paperDetail, /activeTab === '引用信息'|citationText\(\)|activeTab === '关联资料'/)
  assert.doesNotMatch(paperDetail, /该部分将在接入正式论文元数据与授权全文后展示完整内容/)
  assert.match(reportEditor, /report\.requiresReview \? '导出草稿' : '导出报告'/)
  for (const format of ['markdown', 'docx', 'pdf']) assert.match(reportEditor, new RegExp(`command="${format}"`))
  assert.match(reportEditor, /ReportExportHistory/)
  assert.match(reportEditor, /listPipelineResearchReportExports\(report\.value\.id\)/)
  assert.match(reportEditor, /function formatText\(value, tool\)/)
  assert.match(reportEditor, /window\.open\(externalUrl, '_blank', 'noopener,noreferrer'\)/)
  assert.match(digestEditor, /digest\.requiresReview \? '导出草稿' : '导出简报'/)
  for (const format of ['markdown', 'docx', 'pdf']) assert.match(digestEditor, new RegExp(`command="${format}"`))
  assert.match(digestList, /report\.requiresReview \? '导出草稿 Markdown' : '导出 Markdown'/)
})

test('keeps empty and unavailable portal states explicit', () => {
  const home = read('../src/views/portal/pages/HomeView.vue')
  const search = read('../src/views/portal/pages/SearchView.vue')
  assert.match(home, /overview.loadError.value/)
  assert.match(home, /searchRequest.loading.value/)
  assert.doesNotMatch(home, /ps-home-timeline/)
  assert.match(search, /该结果暂未提供可访问的详情路径/)
  assert.match(search, /return counts\.value\[type\] \?\? 0/)
  assert.match(paperList, /const currentYear = new Date\(\)\.getFullYear\(\)/)
  assert.match(paperList, /v-for="item in yearOptions"/)
  assert.doesNotMatch(paperList, /<el-option label="2026"/)
})

test('removes favorite views while preserving legacy snapshots without deleting data', () => {
  const portalStore = read('../src/store/modules/portal.js')
  const workspace = read('../src/views/portal/pages/MyWorkspaceView.vue')
  const knowledge = read('../src/views/portal/pages/KnowledgeView.vue')
  assert.match(portalStore, /favoriteItems: \[\]/)
  assert.match(portalStore, /snapshot\n?\s*\}\)\.catch/)
  assert.doesNotMatch(workspace, /portalStore\.favoriteItems|收藏快照|取消收藏/)
  assert.doesNotMatch(knowledge, /<el-option label="全员可见" value="全员可见" \/>\s*<el-option label="仅自己可见" value="仅自己可见" \/>\s*<el-option label="全员可见" value="全员可见" \/>/)
})

test('shares one in-flight portal hydration request across concurrent refreshes', () => {
  const portalStore = read('../src/store/modules/portal.js')
  assert.match(portalStore, /let hydratePromise = null/)
  assert.match(portalStore, /if \(this\.dataLoading\) return hydratePromise/)
  assert.match(portalStore, /hydratePromise = request/)
  assert.match(portalStore, /if \(hydratePromise === request\) hydratePromise = null/)
})

test('uses backend permission scopes for knowledge upload and filtering', () => {
  const portalStore = read('../src/store/modules/portal.js')
  const knowledge = read('../src/views/portal/pages/KnowledgeView.vue')
  const knowledgeDetail = read('../src/views/portal/pages/KnowledgeDetailView.vue')
  assert.match(portalStore, /const permissionScope = item\.permissionScope \|\| item\.permission_scope/)
  assert.match(portalStore, /permission: permissionScope === 'public' \? '全员可见' : '仅自己可见'/)
  assert.doesNotMatch(knowledge, /value="public"|v-model="uploadPermission"/)
  assert.match(knowledge, /data.append\('permissionScope', 'private'\)/)
  assert.match(knowledgeDetail, /const permissionScope = item\.permissionScope \|\| item\.permission_scope/)
  assert.match(knowledgeDetail, /permission: permissionScope === 'public' \? '全员可见' : '仅自己可见'/)
  assert.doesNotMatch(knowledge, /value="organization"/)
})

test('persists structured diagrams for the signed-in user with a local fallback', () => {
  const assets = read('../src/views/portal/components/ReportImageAssets.vue')
  assert.match(diagram, /ReportImageAssets/)
  assert.match(assets, /getPipelineResearchReportDiagram/)
  assert.match(assets, /getReportImageBlob/)
  assert.match(assets, /retryReportImage/)
  assert.match(assets, /:src="image.imageUrl"/)
  assert.doesNotMatch(diagram, /localStorage|defaultDiagram|updatePipelineResearchReportDiagram|导出 SVG/)
})

test('keeps disabled source actions and the vertical diagram responsive', () => {
  assert.match(portalStyles, /\.ps-disabled-action-wrap/)
  assert.match(portalStyles, /\.ps-source-link\.is-disabled/)
  assert.match(portalStyles, /\.ps-flowchart\.is-tb/)
  assert.match(portalStyles, /@media \(max-width: 760px\)[\s\S]*?\.ps-diagram-topbar \.ps-editor-actions/)
})
