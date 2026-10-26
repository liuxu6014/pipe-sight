import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import { computed, effectScope, ref, watch } from 'vue'
import { validateBusinessInput } from '../src/utils/portal/businessId.js'
import { buildReportMarkdown, cleanReportCitationNotes } from '../src/utils/portal/reportDocument.js'

const settled = () => new Promise(resolve => setImmediate(resolve))
function deferred() {
  let resolve, reject
  const promise = new Promise((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}
function editor(page, entityName, update) {
  const source = readFileSync(new URL(`../src/views/portal/pages/${page}.vue`, import.meta.url), 'utf8')
    .split('<script setup>')[1].split('</script>')[0].replace(/^import .*\n/gm, '')
  let timer, leave, updateGuard
  const messages = []
  const scope = effectScope()
  let token = 'active-session'
  const context = vm.createContext({
    buildReportMarkdown, cleanReportCitationNotes,
    computed, ref, watch, onMounted() {}, onBeforeUnmount() {},
    onBeforeRouteLeave(callback) { leave = callback },
    onBeforeRouteUpdate(callback) { updateGuard = callback },
    useRoute: () => ({ params: { id: '9007199254740993' }, query: {} }), useRouter: () => ({}),
    usePortalStore: () => ({ researchReports: [], digestReports: [], newsItems: [] }),
    updatePipelineResearchReport: update,
    listPipelineResearchReportVersions: async () => ({ data: { rows: [] } }),
    getToken: () => token,
    ElMessage: { error(message) { messages.push(message) }, warning() {}, success() {} },
    setTimeout(callback) { timer = callback; return 1 }, clearTimeout() {},
  })
  scope.run(() => vm.runInContext(`${source}\nglobalThis.editor = { entity: ${entityName}, sections, citations, markSaving, handleBeforeUnload, saveVersion, saveState, saving, wait: () => savePromise }`, context))
  context.editor.entity.value = { id: '9007199254740993', title: 'First title', versionNo: 1, revision: 1 }
  context.editor.sections.value = [{ id: 1, title: 'Section', content: 'First body', words: 10 }]
  return { state: context.editor, messages, trigger: () => timer(), leave: () => leave(), updateGuard: () => updateGuard, logOut: () => { token = '' }, close: () => scope.stop() }
}

for (const [page, entity] of [['ReportEditorView', 'report'], ['DigestEditorView', 'digest']]) {
  test(`${page}: a stale cached citation blocks saving with an upgrade message and keeps authored content`, async () => {
    let calls = 0
    const view = editor(page, entity, async (_id, payload) => { validateBusinessInput(payload); calls++; return { data: {} } })
    try {
      view.state.citations.value = [{ id: 1, sourceId: 'old-source-uuid', quote: '用户引用文字' }]
      view.state.markSaving()
      view.trigger()
      await view.state.wait()
      assert.equal(calls, 0)
      assert.equal(view.state.saveState.value, 'error')
      assert.ok(view.messages.some(message => /编号已升级.*正文已保留/.test(message)))
      assert.equal(view.state.entity.value.title, 'First title')
      assert.equal(view.state.sections.value[0].content, 'First body')
      assert.equal(view.state.citations.value[0].quote, '用户引用文字')
      assert.equal(await view.leave(), false)
    } finally { view.close() }
  })
  test(`${page}: a slow save does not overwrite subsequent edits or mutate the sent snapshot`, async () => {
    const first = deferred()
    const payloads = []
    const view = editor(page, entity, (_id, payload) => { payloads.push(payload); return payloads.length === 1 ? first.promise : Promise.resolve({ data: { title: payload.title, revision: 3 } }) })
    try {
      view.state.markSaving()
      view.trigger()
      await settled()
      view.state.entity.value.title = 'Newer title'
      view.state.sections.value[0].content = 'Newer body'
      view.state.markSaving()
      assert.equal(payloads[0].sections[0].content, 'First body')
      first.resolve({ data: { title: 'First title', revision: 2 } })
      await view.state.wait()
      assert.equal(view.state.entity.value.title, 'Newer title')
      assert.equal(view.state.entity.value.revision, 2)
      assert.equal(view.state.saveState.value, 'dirty')
      view.trigger()
      await view.state.wait()
      assert.equal(payloads[1].title, 'Newer title')
      assert.equal(payloads[1].expectedRevision, 2)
      assert.equal(view.state.saveState.value, 'saved')
    } finally { view.close() }
  })

  test(`${page}: in-flight unsaved changes protect browser unload and block navigation on save failure`, async () => {
    const first = deferred()
    let calls = 0
    const view = editor(page, entity, () => ++calls === 1 ? first.promise : Promise.reject(new Error('save failed')))
    try {
      view.state.markSaving()
      view.trigger()
      await settled()
      let prevented = false
      view.state.handleBeforeUnload({ preventDefault() { prevented = true } })
      assert.equal(prevented, true)
      const leaving = view.leave()
      first.reject(new Error('save failed'))
      assert.equal(await leaving, false)
      assert.equal(view.state.saveState.value, 'error')
    } finally { view.close() }
  })

  test(`${page}: switching to another report also checks unsaved changes`, async () => {
    const view = editor(page, entity, () => Promise.reject(new Error('save failed')))
    try {
      view.state.markSaving()
      assert.equal(typeof view.updateGuard(), 'function')
      assert.equal(await view.updateGuard()(), false)
    } finally { view.close() }
  })

  test(`${page}: manual version saving preserves newer edits and prevents duplicate submissions`, async () => {
    const response = deferred()
    const payloads = []
    const view = editor(page, entity, (_id, payload) => { payloads.push(payload); return response.promise })
    try {
      const first = view.state.saveVersion()
      const duplicate = view.state.saveVersion()
      await settled()
      assert.equal(payloads.length, 1)
      assert.equal(payloads[0].saveVersion, true)
      view.state.entity.value.title = 'Edited during manual save'
      view.state.sections.value[0].content = 'Edited during manual save'
      view.state.markSaving()
      assert.equal(payloads[0].sections[0].content, 'First body')
      response.resolve({ data: { title: 'First title', revision: 2, versionNo: 2 } })
      await Promise.all([first, duplicate])
      assert.equal(view.state.entity.value.title, 'Edited during manual save')
      assert.equal(view.state.saveState.value, 'dirty')
    } finally { view.close() }
  })

  test(`${page}: logout can leave private editor state without trying an unauthenticated save`, async () => {
    let calls = 0
    const view = editor(page, entity, () => { calls++; return Promise.reject(new Error('unauthorized')) })
    try {
      view.state.markSaving()
      view.logOut()
      assert.equal(await view.leave(), true)
      assert.equal(calls, 0)
    } finally { view.close() }
  })
}

test('administrator report inspection cannot autosave or create a version for another owner', async () => {
  let calls = 0
  const view = editor('ReportEditorView', 'report', async () => { calls++; return { data: {} } })
  try {
    view.state.entity.value.readOnly = true
    view.state.markSaving()
    await view.state.saveVersion()
    await view.state.wait()
    assert.equal(calls, 0)
    assert.equal(view.state.saving.value, false)
    assert.equal(view.state.saveState.value, 'saved')
  } finally { view.close() }
})
