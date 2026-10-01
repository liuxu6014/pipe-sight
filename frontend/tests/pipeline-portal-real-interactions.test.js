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
const diagram = read('../src/views/portal/pages/DiagramEditorView.vue')
const portalStyles = read('../src/assets/styles/portal.scss')

test('copies paper citations through the Clipboard API with a browser fallback', () => {
  for (const page of [paperList, paperDetail]) {
    assert.match(page, /navigator\.clipboard\?\.writeText/)
    assert.match(page, /document\.execCommand\('copy'\)/)
    assert.match(page, /引用信息已复制到剪贴板/)
    assert.doesNotMatch(page, /引用导出/)
  }
})

test('opens paper and news sources only when a valid URL is available', () => {
  assert.match(paperList, /:disabled="!paperUrl\(paper\)"/)
  assert.match(paperDetail, /:disabled="!paperUrl"/)
  assert.match(paperList, /window\.open\(target\.href, '_blank', 'noopener,noreferrer'\)/)
  assert.match(paperDetail, /window\.open\(target\.href, '_blank', 'noopener,noreferrer'\)/)
  assert.match(newsDetail, /v-if="articleUrl"/)
  assert.match(newsDetail, /rel="noopener noreferrer"/)
  assert.match(newsDetail, /暂无原文链接/)
  assert.doesNotMatch(newsDetail, /原文链接将在正式数据接入后打开/)
  assert.doesNotMatch(newsDetail, /\|\| portalStore\.newsItems\[0\]/)
  assert.doesNotMatch(paperDetail, /\|\| portalStore\.paperItems\[0\]/)
  assert.match(newsDetail, /资讯不存在/)
  assert.match(paperDetail, /论文不存在/)
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
  assert.match(digestList, /await exportPipelineResearchReport\(report\.id\)/)
  assert.match(digestList, /new Blob\(\[res\.data\.content\]/)
  assert.match(digestList, /URL\.createObjectURL\(blob\)/)
  assert.match(digestList, /query: \{ panel: 'sources' \}/)
  assert.match(digestEditor, /route\.query\.panel === 'sources'/)
  for (const placeholder of ['已复制为新草稿', '导出任务已创建', '删除草稿']) {
    assert.doesNotMatch(digestList, new RegExp(placeholder))
  }
})

test('persists structured diagrams for the signed-in user with a local fallback', () => {
  assert.match(diagram, /getPipelineResearchReportDiagram/)
  assert.match(diagram, /updatePipelineResearchReportDiagram/)
  assert.match(diagram, /await updatePipelineResearchReportDiagram\(String\(route\.params\.id\)/)
  assert.match(diagram, /await getPipelineResearchReportDiagram\(String\(route\.params\.id\)\)/)
  assert.match(diagram, /localStorage\.setItem\(storageKey\.value/)
  assert.match(diagram, /localStorage\.getItem\(storageKey\.value\)/)
  assert.match(diagram, /schemaVersion: 1/)
  assert.match(diagram, /function undo\(\)/)
  assert.match(diagram, /function redo\(\)/)
  assert.match(diagram, /history\.value = history\.value\.slice/)
  assert.match(diagram, /type: 'image\/svg\+xml;charset=utf-8'/)
  assert.match(diagram, /link\.download = `技术路线图-/)
  assert.match(diagram, /requestFullscreen/)
  assert.doesNotMatch(diagram, /SVG 导出任务已创建/)
  assert.doesNotMatch(diagram, /图形已保存为结构化版本/)
  assert.doesNotMatch(diagram, /保存到本机/)
})

test('keeps disabled source actions and the vertical diagram responsive', () => {
  assert.match(portalStyles, /\.ps-disabled-action-wrap/)
  assert.match(portalStyles, /\.ps-source-link\.is-disabled/)
  assert.match(portalStyles, /\.ps-flowchart\.is-tb/)
  assert.match(portalStyles, /@media \(max-width: 760px\)[\s\S]*?\.ps-diagram-topbar \.ps-editor-actions/)
})
