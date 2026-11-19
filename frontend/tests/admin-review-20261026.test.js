import { isDigestType } from '../src/views/portal/utils/routing.js'
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { computed, createRenderer, nextTick, onActivated, onBeforeUnmount, onDeactivated, onMounted, reactive, ref, watch } from 'vue'
import { setImmediate } from 'node:timers/promises'

const source = page => readFileSync(new URL(`../src/views/pipeline/${page}.vue`, import.meta.url), 'utf8')
// Execute the real setup handlers with transport/UI boundaries replaced; no server writes.
function setup(page, names, mocks = {}) {
  const script = source(page).match(/<script setup>([\s\S]*?)<\/script>/)[1]
    .replace(/^import[\s\S]*?from ['"][^'"]+['"]\s*$/gm, '')
  const dependencies = { isDigestType, computed, reactive, ref, watch, onMounted() {}, onBeforeUnmount() {}, defineOptions() {}, defineProps: () => ({}), defineEmits: () => () => {},
    ElMessage: { warning() {}, error() {}, success() {}, info() {} },
    checkPermi: () => true, modelsFor: () => [],
    Calendar: {}, Collection: {}, Delete: {}, Document: {}, Files: {}, Plus: {}, Rank: {}, Search: {},
    useRoute: () => ({ query: { id: '18' }, path: `/pipeline/${page.replace(/\/index$/, '')}` }), useRouter: () => ({}),
    useUserStore: () => ({ id: 1 }),
    usePagedResults(load, params) {
      const rows = ref([]), total = ref(0), error = ref(''), loading = ref(false)
      return { rows, total, error, loading, refresh: async () => {
        const response = await load(params.value)
        rows.value = response.data.rows; total.value = response.data.total
      } }
    },
    ...mocks }
  return new Function(...Object.keys(dependencies), `${script}\nreturn { ${names.join(',')} }`)(...Object.values(dependencies))
}

// Readers start work in lifecycle hooks, rather than a manual handler call. Run
// their real setup inside a mounted Vue instance so activation and cleanup guards
// are exercised; the other handler-only legacy cases retain their narrow mocks.
function mountSetup(page, names, mocks = {}) {
  let bindings
  const renderer = createRenderer({
    createElement: () => ({}), createText: () => ({}), createComment: () => ({}),
    insert() {}, remove() {}, setText() {}, setElementText() {}, patchProp() {},
    parentNode: () => null, nextSibling: () => null
  })
  const app = renderer.createApp({
    setup() {
      bindings = setup(page, names, { onMounted, onActivated, onDeactivated, onBeforeUnmount, ...mocks })
      return () => null
    }
  })
  app.mount({})
  return { ...bindings, close: () => app.unmount() }
}

test('A02 download delegates missing permission flags to the authenticated backend', async () => {
  const calls = [], warnings = []
  const page = setup('knowledge/index', ['downloadDocument'], {
    downloadPipelineKnowledgeDocument: async (...args) => calls.push(args),
    ElMessage: { warning: text => warnings.push(text) }
  })
  await page.downloadDocument({ id: '54', name: '资料.pdf' })
  await page.downloadDocument({ id: '55', name: '受限.pdf', allowDownload: false })
  assert.deepEqual(calls, [['54', '资料.pdf']])
  assert.deepEqual(warnings, ['当前资料禁止下载'])
})

test('U03 upload validates 16MB boundary and rejects unsupported DOC', () => {
  const page = setup('knowledge/index', ['validateUploadFile'])
  for (const name of ['资料.pdf', '资料.DOCX', '资料.md', '资料.txt']) {
    assert.equal(page.validateUploadFile({ name, size: 16 * 1024 * 1024 }), '')
    assert.match(page.validateUploadFile({ name, size: 16 * 1024 * 1024 + 1 }), /16MB/)
  }
  assert.ok(page.validateUploadFile({ name: '旧版.doc', size: 200 }))
  assert.ok(page.validateUploadFile({ name: '空.txt', size: 0 }))
})

test('U01/U02 upload sends private scope with no discarded category or tags', async () => {
  const payloads = []
  const page = setup('knowledge/index', ['uploadFiles', 'finishUpload'], {
    uploadPipelineKnowledgeDocument: async data => payloads.push([...data.entries()]),
    listPipelineKnowledgeDocuments: async () => ({ data: { rows: [] } })
  })
  page.uploadFiles.value = [{ name: '资料.txt', size: 3, raw: new Blob(['abc']) }]
  // Element Plus raw File carries name/size; Blob alone lacks name.
  page.uploadFiles.value[0].raw = new File(['abc'], '资料.txt')
  await page.finishUpload()
  assert.equal(payloads.length, 1)
  assert.deepEqual(payloads[0].map(([key]) => key), ['file', 'permissionScope'])
  assert.equal(payloads[0][1][1], 'private')
  const markup = source('knowledge/index').split('<script setup>')[0]
  assert.doesNotMatch(markup, /value="public"|uploadCategory|uploadTags|100MB|\.doc,/)
})

test('A03 queue counts and filtering compare parseStatus codes despite translated labels', () => {
  const page = setup('knowledge/index', ['documents', 'statusFilter', 'processingCount', 'filteredDocuments', 'statusCount'])
  page.documents.value = [
    { id: '1', parseStatus: 'queued', status: '等待解析' },
    { id: '2', parseStatus: 'parsing', status: '解析中' },
    { id: '3', parseStatus: 'ready', status: '已解析' },
    { id: '4', parseStatus: 'failed', status: '解析失败' }
  ]
  assert.equal(page.processingCount.value, 2)
  page.statusFilter.value = 'queued'
  assert.deepEqual(page.filteredDocuments.value.map(row => row.id), ['1'])
  assert.equal(page.statusCount('ready'), 1)
})

test('A06 retire does not PUT the disabled model config; enable keeps full validation payload', async () => {
  const retired = [], updated = []
  const item = { id: '17', name: ' 模板 ', prompt: ' 提示词 ', isEnabled: true, modelId: '8', sections: [] }
  const page = setup('template/index', ['toggleTemplate'], {
    retirePipelineTemplate: async id => retired.push(id),
    updatePipelineTemplate: async (...args) => updated.push(args),
    listPipelineTemplates: async () => ({ data: { rows: [], total: 0 } }),
    getPipelineTemplate: async id => { assert.equal(id, item.id); return { data: item } }
  })
  await page.toggleTemplate(item)
  assert.deepEqual(retired, ['17'])
  assert.deepEqual(updated, [])
  await page.toggleTemplate({ ...item, isEnabled: false })
  assert.equal(updated.length, 1)
  assert.equal(updated[0][1].isEnabled, true)
  assert.equal(updated[0][1].modelId, '8')
})

test('A07 history requests selected page/size/filters and uses the server total beyond 20 rows', async () => {
  const calls = []
  const page = setup('manuscript/index', ['pageNum', 'pageSize', 'jobKeyword', 'jobStatus', 'jobsTotal', 'jobs', 'loadJobs', 'searchJobs'], {
    listManuscriptJobs: async query => { calls.push(query); return { data: { rows: [{ job_id: '51' }], total: 73 } } },
    getManuscriptJob: async () => ({ data: { job_id: '51', content: '' } })
  })
  page.pageNum.value = 3
  page.pageSize.value = 10
  page.jobKeyword.value = '监测'
  page.jobStatus.value = 'failed'
  await page.loadJobs()
  assert.deepEqual(calls[0], { pageNum: 3, pageSize: 10, keyword: '监测', status: 'failed' })
  assert.equal(page.jobsTotal.value, 73)
  for (const size of [20, 50]) {
    page.pageSize.value = size
    await page.searchJobs()
    assert.equal(calls.at(-1).pageNum, 1)
    assert.equal(calls.at(-1).pageSize, size)
  }
  assert.match(source('manuscript/index'), /:total="jobsTotal"/)
})

test('A05 detail failures show retry state and the next success clears it', async () => {
  let failing = true
  const page = mountSetup('intelligence/detail', ['loadDetail', 'loadError', 'detail'], {
    getPipelineIntelligenceDetail: async () => {
      if (failing) throw new Error('offline')
      return { data: { id: '18', title: '情报', category_name: '检测', tags: [] } }
    }
  })
  try {
    await nextTick(); await setImmediate(); await nextTick()
    assert.ok(page.loadError.value)
    failing = false
    await page.loadDetail()
    assert.equal(page.loadError.value, '')
    assert.equal(page.detail.value.category_name, '检测')
    const markup = source('intelligence/detail').split('<script setup>')[0]
    assert.match(markup, /detail.category_name/)
    assert.match(markup, /ContentEntities :entities="detail.entities/)
    assert.doesNotMatch(markup, /detail\.(timeline|related_topics|relevance|categoryName)/)
  } finally { page.close() }
})

test('A04 dashboard shows source names and counts without a fabricated percentage', () => {
  const markup = source('dashboard/index').split('<script setup>')[0]
  assert.doesNotMatch(markup, /el-progress|:percentage/)
  for (const field of ['fetched_count', 'saved_count', 'failed_count']) assert.ok(markup.includes(`item.${field}`))
})

test('A01 report management uses the dedicated admin transport', async () => {
  let calls = 0
  const page = setup('report/index', ['loadReports', 'pagedRows'], {
    listPipelineAdminReports: async params => {
      calls++
      assert.deepEqual(params, { pageNum: 1, pageSize: 10, keyword: '', status: '', kind: 'research' })
      return { data: { rows: [{ id: '2', owner: '其他作者' }], total: 1 } }
    }
  })
  await page.loadReports()
  assert.equal(calls, 1)
  assert.equal(page.pagedRows.value[0].owner, '其他作者')
})

test('L03 chapter row reserves one track per chapter control', () => {
  const tracks = source('template/index').match(/\.template-section-row\s*\{[^}]*grid-template-columns:\s*([^;]+)/)[1]
  assert.equal(tracks.match(/minmax\([^)]*\)|[^\s]+/g).length, 5)
})
