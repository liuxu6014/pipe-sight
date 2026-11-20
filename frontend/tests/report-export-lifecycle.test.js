import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import * as vue from 'vue'
import { createMemoryHistory, createRouter, onBeforeRouteLeave, onBeforeRouteUpdate, useRoute, useRouter } from 'vue-router'
import { isDigestType } from '../src/views/portal/utils/routing.js'

const setup = readFileSync(new URL('../src/views/portal/pages/ReportEditorView.vue', import.meta.url), 'utf8')
  .split('<script setup>')[1].split('</script>')[0].replace(/^import .*\n/gm, '')
const settle = async () => { await vue.nextTick(); await new Promise(resolve => setImmediate(resolve)); await vue.nextTick() }
const deferred = () => { let resolve; const promise = new Promise(yes => { resolve = yes }); return { promise, resolve } }

// Execute the actual editor setup with Vue lifecycle and a real memory router.
async function editor(overrides = {}) {
  const calls = { creates: [], polls: [], downloads: [], messages: [] }, timers = []
  const store = vue.reactive({ workspaceEpoch: 1, researchReports: [], digestReports: [], async hydrate() {} })
  const deps = {
    ...vue, useRoute, useRouter, onBeforeRouteLeave, onBeforeRouteUpdate, isDigestType,
    usePortalStore: () => store, getToken: () => 'active',
    getPipelineResearchReport: async id => ({ data: { id, title: `报告${id}`, sections: [{ id: 1, title: '章节', content: '正文' }] } }),
    createPipelineResearchReportExport: async (id, options) => { calls.creates.push({ id, options }); return { data: { exportId: '90' } } },
    listPipelineResearchReportExports: async id => { calls.polls.push(id); return { data: { rows: [{ exportId: 90, status: 'completed' }] } } },
    downloadPipelineResearchReportExport: async (id, filename) => { calls.downloads.push({ id, filename }) },
    ElMessage: Object.fromEntries(['success', 'warning', 'error', 'info'].map(level => [level, text => calls.messages.push({ level, text })])),
    window: { addEventListener() {}, removeEventListener() {} },
    setTimeout: fn => { timers.push(fn); return timers.length }, clearTimeout() {},
    ...overrides
  }
  let page
  const injected = Object.entries(deps).filter(([key]) => /^[A-Za-z_$][\w$]*$/.test(key) && key !== 'default')
  const createSetup = new Function(...injected.map(([key]) => key), `${setup}\nreturn { report, exportReport, exportRefreshKey, activeRightTab, inspectorVisible };`)
  const component = { setup() { page = createSetup(...injected.map(([, value]) => value)); return page }, render: () => vue.h('div') }
  const router = createRouter({ history: createMemoryHistory(), routes: [
    { path: '/portal/research/reports/:id', component }, { path: '/elsewhere', component: { render: () => null } }
  ] })
  const node = type => ({ type, children: [], parent: null })
  const renderer = vue.createRenderer({
    createElement: node, createText: node, createComment: node, setText() {}, setElementText() {}, patchProp() {},
    parentNode: child => child.parent, nextSibling: () => null,
    insert(child, parent) { child.parent = parent; parent.children.push(child) },
    remove(child) { if (child.parent) child.parent.children = child.parent.children.filter(item => item !== child) }
  })
  const app = renderer.createApp({ render: () => vue.h(vue.resolveComponent('RouterView')) }).use(router)
  await router.push('/portal/research/reports/41')
  app.mount(node('root')); await settle()
  return { get page() { return page }, calls, router, store, async tick() { timers.shift()?.(); await settle() }, close: () => app.unmount() }
}

test('changing reports while export creation is pending polls and downloads the original report only', { timeout: 2000 }, async () => {
  const created = deferred(), ids = []
  const view = await editor({ createPipelineResearchReportExport: id => { ids.push(id); return created.promise } })
  try {
    const pending = view.page.exportReport('pdf')
    await settle()
    await view.router.push('/portal/research/reports/42'); await settle()
    assert.equal(view.page.report.value.id, '42')
    const refreshBefore = view.page.exportRefreshKey.value
    created.resolve({ data: { exportId: '90' } }); await settle(); await view.tick(); await pending
    assert.deepEqual(ids, ['41'])
    assert.deepEqual(view.calls.polls, ['41'])
    assert.deepEqual(view.calls.downloads, [{ id: '90', filename: '报告41.pdf' }])
    assert.equal(view.page.exportRefreshKey.value, refreshBefore)
    assert.ok(view.calls.messages.some(item => item.level === 'success' && item.text.includes('报告41')))
  } finally { view.close() }
})

test('duplicate export clicks create only one task and polling failures retain a resumable record', { timeout: 2000 }, async () => {
  const created = deferred()
  let creates = 0
  const view = await editor({
    createPipelineResearchReportExport: () => { creates++; return created.promise },
    listPipelineResearchReportExports: async () => { throw Error('offline') }
  })
  try {
    const first = view.page.exportReport('pdf'); await settle()
    const second = view.page.exportReport('docx'); await settle()
    assert.equal(creates, 1)
    created.resolve({ data: { exportId: '90' } }); await settle(); await view.tick(); await Promise.all([first, second])
    assert.equal(view.page.activeRightTab.value, '导出记录')
    assert.equal(view.page.inspectorVisible.value, true)
    assert.equal(view.calls.downloads.length, 0)
    assert.ok(view.calls.messages.some(item => /已创建.*导出记录.*无需重复提交/.test(item.text)))
  } finally { view.close() }
})

test('leaving or changing account while export creation is pending stops late downloads', { timeout: 2000 }, async () => {
  for (const action of ['leave', 'account']) {
    const created = deferred()
    const view = await editor({ createPipelineResearchReportExport: () => created.promise })
    try {
      const pending = view.page.exportReport('pdf'); await settle()
      if (action === 'leave') { await view.router.push('/elsewhere'); await settle() }
      else view.store.workspaceEpoch++
      created.resolve({ data: { exportId: '90' } }); await settle(); await view.tick(); await pending
      assert.equal(view.calls.polls.length, 0)
      assert.equal(view.calls.downloads.length, 0)
      assert.deepEqual(view.calls.messages, [])
    } finally { view.close() }
  }
})

test('a status response arriving after an account switch cannot download the previous account file', async () => {
  const status = deferred(), ids = []
  const view = await editor({ listPipelineResearchReportExports: id => { ids.push(id); return status.promise } })
  try {
    const pending = view.page.exportReport('pdf'); await settle(); await view.tick()
    assert.deepEqual(ids, ['41'])
    view.store.workspaceEpoch++
    status.resolve({ data: { rows: [{ exportId: '90', status: 'completed' }] } })
    await pending
    assert.deepEqual(view.calls.downloads, [])
    assert.deepEqual(view.calls.messages, [])
  } finally { view.close() }
})

test('a failed export is attributed to its original report after a route switch', async () => {
  const status = deferred()
  const view = await editor({ listPipelineResearchReportExports: () => status.promise })
  try {
    const pending = view.page.exportReport('pdf'); await settle(); await view.tick()
    await view.router.push('/portal/research/reports/42'); await settle()
    status.resolve({ data: { rows: [{ exportId: '90', status: 'failed', errorMessage: '文件生成失败' }] } })
    await pending
    assert.ok(view.calls.messages.some(item => item.level === 'error' && item.text === '《报告41》文件生成失败'))
    assert.deepEqual(view.calls.downloads, [])
  } finally { view.close() }
})
