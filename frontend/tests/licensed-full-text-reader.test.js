import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import { computed, effectScope, nextTick, reactive, ref, watch } from 'vue'
import { parse, compileTemplate } from '@vue/compiler-sfc'
import { useListWorkspace } from '../src/utils/portal/listQuery.js'

const source = readFileSync(new URL('../src/views/portal/pages/PaperDetailView.vue', import.meta.url), 'utf8')
const { descriptor } = parse(source)
function harness({ translatePipelinePaperTitle, translatePipelinePaperAbstract } = {}) {
  const requests = [], route = reactive({ params: { itemId: '3001' } })
  const store = reactive({ paperItems: [], newsItems: [], basket: [], workspaceEpoch: 0 })
  const saved = [], removed = []
  const context = vm.createContext({
    computed, ref, watch, onBeforeUnmount() {}, onMounted() {}, useRoute: () => route, useRouter: () => ({}),
    usePortalStore: () => store, useListWorkspace,
    savePipelineWorkspaceItem: async payload => { saved.push(payload) },
    deletePipelineWorkspaceItem: async (...args) => { removed.push(args) },
    normalizePortalPaper: row => ({ ...row }), ElMessage: { error() {}, success() {} },
    translatePipelinePaperTitle, translatePipelinePaperAbstract,
    URL,
    getPipelineIntelligenceDetail: () => new Promise((resolve, reject) => requests.push({ resolve, reject }))
  })
  const scope = effectScope()
  scope.run(() => vm.runInContext(descriptor.scriptSetup.content.replace(/^import .*\n/gm, '') +
    '\nglobalThis.reader = { paper, doiUrl, showingTranslation, translating, translationError, visibleAbstract, loadPaper, detailLoading, paperInstitutions, add, inBasket, toggleLanguage, visibleTitle }', context))
  return { ...context.reader, requests, route, store, saved, removed, stop: () => scope.stop() }
}
const response = full_text => ({ data: { id: '3001', category: 'paper', source_url: 'https://europepmc.org/articles/PMC123', full_text } })

test('paper detail can add and cancel basket selection using the real saved item type', async () => {
  const h = harness()
  try {
    const load = h.loadPaper(); h.requests[0].resolve(response(null)); await load
    await h.add()
    assert.equal(h.saved[0].itemType, 'paper')
    assert.equal(h.inBasket(h.paper.value), true)
    await h.add()
    assert.deepEqual(h.removed, [['basket', '3001']])
    assert.equal(h.store.basket.length, 0)
  } finally { h.stop() }
})

test('paper detail uses a compact responsive title without changing other reading pages', () => {
  assert.doesNotMatch(descriptor.template.content, /class="ps-paper-access"/)
  assert.match(descriptor.styles.find(style => style.scoped).content, /\.ps-paper-detail-hero h1\s*\{[^}]*font-size:\s*24px[^}]*line-height:\s*1\.45/)
  assert.match(source, /@media \(max-width: 600px\)[\s\S]*?\.ps-paper-detail-hero h1\s*\{\s*font-size:\s*20px/)
})

test('paper hero displays one title and suppresses placeholder institutions without guessing affiliations', async () => {
  const h = harness()
  try {
    let load = h.loadPaper()
    h.requests[0].resolve({ data: { id: '3001', category: 'paper', titleZh: 'Pipeline Review', title: '  Pipeline  Review ', institutions: ['来源数据库'] } })
    await load
    assert.equal(h.visibleTitle.value.trim(), 'Pipeline  Review')
    assert.equal(h.paperInstitutions.value.length, 0)
    load = h.loadPaper()
    h.requests[1].resolve({ data: { id: '3001', category: 'paper', titleZh: '管道综述', title: 'Pipeline Review', institutions: ['某大学', '某大学', '', '来源数据库', '某研究院'] } })
    await load
    assert.equal(h.visibleTitle.value, 'Pipeline Review')
    await h.toggleLanguage()
    assert.equal(h.visibleTitle.value, '管道综述')
    assert.doesNotMatch(descriptor.template.content, /ps-paper-original-title/)
    assert.deepEqual(Array.from(h.paperInstitutions.value), ['某大学', '某研究院'])
    assert.doesNotMatch(source, /ps-author-map|institutions\[index\]|institutions\[0\]/)
    assert.match(source, /paper\.authors\.join\(' · '\)/)
  } finally { h.stop() }
})

test('saved abstract translation switches without using legacy full text', async () => {
 const h = harness()
 try {
  const load = h.loadPaper()
  h.requests[0].resolve({ data: {
    ...response({ status: 'publisher_preview', html: '<p>Legacy full text</p>' }).data,
    abstractOriginal: 'Original abstract', abstractZh: '已保存的中文摘要'
  } })
  await load
  assert.equal(h.visibleAbstract.value, 'Original abstract')
  await h.toggleLanguage()
  assert.equal(h.visibleAbstract.value, '已保存的中文摘要')
 } finally { h.stop() }
})

test('one action translates both fields, retries just the missing one, and switches without extra requests', async () => {
  const calls = []
  let rejectAbstract = true
  const h = harness({
    translatePipelinePaperTitle: async id => {
      calls.push(['title', id])
      return { data: { titleZh: '管道综述' } }
    },
    translatePipelinePaperAbstract: async id => {
      calls.push(['abstract', id])
      if (rejectAbstract) throw new Error('翻译暂时失败')
      return { data: { abstractZh: '中文摘要。' } }
    }
  })
  try {
    const load = h.loadPaper()
    h.requests[0].resolve({ data: {
      ...response(null).data, title: 'Pipeline Review', abstractOriginal: 'Original abstract'
    } })
    await load
    const translation = h.toggleLanguage()
    assert.equal(h.translating.value, true)
    await h.toggleLanguage()
    await translation
    assert.equal(h.translationError.value, '翻译暂时失败')
    assert.equal(h.visibleTitle.value, 'Pipeline Review')
    assert.equal(h.visibleAbstract.value, 'Original abstract')

    rejectAbstract = false
    await h.toggleLanguage()
    assert.equal(h.visibleTitle.value, '管道综述')
    assert.equal(h.visibleAbstract.value, '中文摘要。')
    await h.toggleLanguage()
    assert.equal(h.visibleTitle.value, 'Pipeline Review')
    assert.equal(h.visibleAbstract.value, 'Original abstract')
    await h.toggleLanguage()
    assert.equal(h.visibleTitle.value, '管道综述')
    assert.equal(h.visibleAbstract.value, '中文摘要。')
    assert.deepEqual(calls, [['title', '3001'], ['abstract', '3001'], ['abstract', '3001']])
  } finally { h.stop() }
})

test('detail DOI resolves to the publisher independently of the licensed reading source', async () => {
  const h = harness()
  try {
    const load = h.loadPaper()
    h.requests[0].resolve({ data: { ...response({ html: '<p>Text</p>', source_url: 'https://europepmc.org/articles/PMC123' }).data, doi: '10.3390/coatings14030358' } })
    await load
    assert.equal(h.doiUrl.value, 'https://doi.org/10.3390/coatings14030358')
    h.paper.value.doi = 'https://doi.org/10.1234/example'
    assert.equal(h.doiUrl.value, 'https://doi.org/10.1234/example')
    for (const doi of ['', '待补充', 'javascript:alert(1)', 'https://example.com']) {
      h.paper.value.doi = doi
      assert.equal(h.doiUrl.value, '')
    }
    assert.doesNotMatch(descriptor.template.content, /复制引用|查看来源|@click="openPaperSource"/)
  } finally { h.stop() }
})

test('unavailable full text keeps summary distinct and does not invent a DOI link', async () => {
  const h = harness()
  try {
    const load = h.loadPaper()
    h.requests[0].resolve(response({ status: 'unavailable' }))
    await load
    assert.equal(h.visibleAbstract.value, '')
    assert.equal(h.doiUrl.value, '')
  } finally { h.stop() }
})

test('route changes reset the paper language and ignore stale responses', async () => {
  const h = harness()
  try {
    const oldLoad = h.loadPaper()
    h.showingTranslation.value = true
    h.route.params.itemId = '3002'
    await nextTick()
    assert.equal(h.showingTranslation.value, false)
    h.requests[1].resolve({ data: { id: '3002', category: 'paper' } })
    await new Promise(resolve => setImmediate(resolve))
    h.requests[0].resolve(response({ html: '<p>Old private text</p>' }))
    await oldLoad
    assert.equal(h.paper.value.id, '3002')
  } finally { h.stop() }
})

test('paper reader compiles and retains safe links to its source', () => {
 const compiled = compileTemplate({ source: descriptor.template.content, filename: 'PaperDetailView.vue', id: 'reader' })
 assert.deepEqual(compiled.errors, [])
 assert.doesNotMatch(descriptor.template.content, /iframe|srcdoc|full_text|获取全文|全文预览/)
 assert.doesNotMatch(descriptor.template.content, /平台仅展示|论文来源页面|关联科技资讯/)
 assert.match(descriptor.template.content, /其他新闻资讯/)
 assert.match(descriptor.template.content, /rel="noopener noreferrer"/)
 assert.match(descriptor.template.content, /aria-label="返回"[^>]*@click="returnFromPaperDetail\(router\)"/)
})
