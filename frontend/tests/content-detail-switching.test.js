import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import * as vue from 'vue'
import { parse, compileTemplate } from '@vue/compiler-sfc'
import { contentCategory, readingContent } from '../src/utils/portal/contentPresentation.js'

const read = name => readFileSync(new URL(`../src/views/portal/${name}`, import.meta.url), 'utf8')
const { descriptor } = parse(read('pages/NewsDetailView.vue'))
function harness() {
  const requests = []
  const route = { params: { itemId: '18' } }
  const context = vm.createContext({ ...vue, onMounted() {}, useRoute: () => route, useRouter: () => ({}),
    usePortalStore: () => ({ newsItems: [], paperItems: [], basket: [] }),
    useListWorkspace: () => ({ inBasket: () => false, busy: () => false, toggleBasket: async () => 'saved' }),
    normalizePortalIntelligence: row => row, contentCategory, readingContent,
    getPipelineIntelligenceDetail: () => new Promise(resolve => requests.push(resolve)),
    savePipelineWorkspaceItem() {}, deletePipelineWorkspaceItem() {},
    window: { location: { origin: 'http://127.0.0.1' } }, URL, ElMessage: { error() {}, success() {} }
  })
  const scope = vue.effectScope()
  scope.run(() => vm.runInContext(descriptor.scriptSetup.content.replace(/^import .*\n/gm, '') + '\nglobalThis.subject = { loadArticle, article, activeTab, language, visibleBody, summaryText, content, detailLoading }', context))
  return { ...context.subject, requests, route, stop: () => scope.stop() }
}

test('news defaults to summary and keeps original text separate from stored translation', async () => {
  const h = harness()
  try {
    const loading = h.loadArticle()
    h.requests[0]({ data: { id: '18', category: 'news', summary: '真实摘要', content_original: 'Original text', content_zh: '已保存的中文' } })
    await loading
    assert.equal(h.activeTab.value, 'summary')
    assert.equal(h.summaryText.value, '真实摘要')
    assert.deepEqual(Array.from(h.visibleBody.value), ['Original text'])
    h.activeTab.value = 'fulltext'; h.language.value = 'zh'
    assert.deepEqual(Array.from(h.visibleBody.value), ['已保存的中文'])
    assert.equal(h.requests.length, 1, 'reading and switching must not request translation')
  } finally { h.stop() }
})

test('late old news response cannot replace the current article or its language state', async () => {
  const h = harness()
  try {
    const old = h.loadArticle()
    h.route.params.itemId = '19'
    const current = h.loadArticle()
    h.requests.at(-1)({ data: { id: '19', category: 'news', summary: '新摘要' } })
    await current
    h.requests[0]({ data: { id: '18', category: 'news', content: '旧正文' } })
    await old
    assert.equal(h.article.value.id, '19')
    assert.equal(h.activeTab.value, 'summary')
    assert.equal(h.language.value, 'original')
    assert.equal(h.detailLoading.value, false)
  } finally { h.stop() }
})

test('news, papers and the shared interpretation components compile', () => {
  for (const name of ['pages/NewsDetailView.vue', 'pages/PaperDetailView.vue', 'components/ContentEntities.vue', 'components/ContentInsights.vue']) {
    const { descriptor } = parse(read(name))
    const compiled = compileTemplate({ source: descriptor.template.content, filename: name, id: name })
    assert.deepEqual(compiled.errors, [])
  }
})
