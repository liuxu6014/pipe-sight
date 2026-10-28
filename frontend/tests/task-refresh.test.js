import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import { computed, ref, reactive, watch } from 'vue'
import { getCitationPath } from '../src/utils/portal/citationRouting.js'

function taskPage({ get, retry, cancel, confirm = async () => {} }) {
  const source = readFileSync(new URL('../src/views/portal/pages/ResearchTaskView.vue', import.meta.url), 'utf8')
    .split('<script setup>')[1].split('</script>')[0].replace(/^import .*\n/gm, '')
  let unmount
  const timers = new Set()
  const navigations = []
  let sequence = 0
  const route = reactive({ name: 'PortalResearchTask', params: { id: 'task-a' } })
  const listeners = new Map()
  const document = { hidden: false, addEventListener: (name, fn) => listeners.set(name, fn), removeEventListener: name => listeners.delete(name) }
  const context = vm.createContext({
    computed, ref, watch, document, getCitationPath, onMounted() {}, onUnmounted(callback) { unmount = callback },
    useRoute: () => route, useRouter: () => ({ replace: async path => { navigations.push(path); route.params.id = path.split('/').at(-1) } }), useUserStore: () => ({}), taskStages: [],
    getPipelineResearchJob: get || (async id => ({ data: { id, status: 'queued' } })), retryPipelineResearchJob: retry,
    cancelPipelineResearchJob: cancel, ElMessageBox: { confirm },
    ElMessage: { warning() {}, success() {}, error() {} },
    setInterval() { const id = ++sequence; timers.add(id); return id }, clearInterval(id) { timers.delete(id) }
  })
  vm.runInContext(`${source}\nglobalThis.page = { task, loadTask, retryTask, cancelTask, startRefresh, loadError, stageRows, currentStageLabel, generationModeLabel, logs, materialCounts, canRetry, templateName, progress, taskStateLabel, onVisibilityChange, materialRows }`, context)
  return { state: context.page, timers, navigations, route, document, unmount: () => unmount() }
}

test('successful reload after a temporary error resumes automatic task refresh', async () => {
  let calls = 0
  const view = taskPage({ get: async () => {
    if (++calls === 1) throw new Error('temporarily unavailable')
    return { data: { status: 'running', progress: 40 } }
  } })
  view.state.startRefresh()
  await view.state.loadTask()
  assert.equal(view.timers.size, 0)
  await view.state.loadTask()
  assert.equal(view.state.loadError.value, '')
  assert.equal(view.timers.size, 1)
  view.unmount()
  assert.equal(view.timers.size, 0)
})

test('a delayed retry response cannot restart polling after leaving the task page', async () => {
  let resolve
  const response = new Promise(yes => { resolve = yes })
  const view = taskPage({ retry: () => response })
  view.state.task.value.status = 'failed'
  const pending = view.state.retryTask()
  await Promise.resolve()
  view.unmount()
  resolve({ data: { status: 'queued' } })
  await pending
  assert.equal(view.timers.size, 0)
})

test('completed task never falls back to validating or awaiting result', () => {
  const view = taskPage({})
  view.state.task.value = { status: 'completed', stages: [], logs: [], selectedItems: [{type: 'paper'}, {type: 'article'}, {type: 'file'}] }
  assert.equal(view.state.currentStageLabel.value, '任务完成')
  assert.ok(view.state.stageRows.value.every(row => row.status === 'completed'))
  assert.doesNotMatch(view.state.generationModeLabel.value, /等待/)
  assert.doesNotMatch(view.state.logs.value[0].message, /正在读取/)
  assert.equal(view.state.materialCounts.value.paper, 1)
  assert.equal(view.state.materialCounts.value.news, 1)
  assert.equal(view.state.materialCounts.value.internal, 1)
  assert.equal(view.state.canRetry.value, false)
  view.unmount()
})

test('retry follows the newly created attempt rather than polling the old terminal task', async () => {
  const view = taskPage({ retry: async () => ({ data: { jobId: '78', status: 'queued' } }) })
  view.state.task.value.status = 'failed'
  await view.state.retryTask()
  assert.equal(view.navigations[0], '/portal/research/tasks/78')
  assert.equal(view.timers.size, 1)
  view.unmount()
})

test('late polling cannot overwrite a successful cancel response', async () => {
  let resolve
  const view = taskPage({ get: () => new Promise(yes => { resolve = yes }), cancel: async () => ({ data: { status: 'cancelled' } }) })
  view.state.task.value.status = 'running'
  const pending = view.state.loadTask()
  await view.state.cancelTask()
  resolve({ data: { status: 'running', progress: 40 } })
  await pending
  assert.equal(view.state.task.value.status, 'cancelled')
  assert.equal(view.timers.size, 0)
  view.unmount()
})

test('an accepted stop request keeps refreshing until the backend reports a terminal state', async () => {
  const view = taskPage({ cancel: async () => ({ data: { status: 'running', cancelRequested: true } }) })
  view.state.task.value.status = 'running'
  await view.state.cancelTask()
  assert.equal(view.state.task.value.cancelRequested, true)
  assert.equal(view.timers.size, 1)
  view.unmount()
})

test('route reuse loads the new task and discards the old response', async () => {
  let resolve
  const calls = []
  const view = taskPage({ get: id => { calls.push(id); return id === 'task-a' ? new Promise(yes => { resolve = yes }) : Promise.resolve({ data: { id, status: 'completed' } }) } })
  const pending = view.state.loadTask()
  view.route.params.id = 'task-b'
  await Promise.resolve()
  resolve({ data: { id: 'task-a', status: 'running' } })
  await pending
  assert.deepEqual(calls, ['task-a', 'task-b'])
  assert.equal(view.state.task.value.id, 'task-b')
  view.unmount()
})

test('leaving for a report never fetches the report ID as a task ID', async () => {
  const calls = []
  const view = taskPage({ get: async id => { calls.push(id); return { data: { id, status: 'running' } } } })
  await view.state.loadTask()
  view.route.name = 'PortalReportEditor'
  view.route.params.id = '76'
  await view.state.loadTask()
  assert.deepEqual(calls, ['task-a'])
  assert.equal(view.timers.size, 0)
  view.unmount()
})

test('retry requires eligibility and confirmation, and never runs after cancelled confirmation', async () => {
  let calls = 0
  const view = taskPage({ retry: async () => { calls++; return { data: {} } }, confirm: async () => { throw 'cancel' } })
  await view.state.retryTask()
  view.state.task.value.status = 'failed'
  await view.state.retryTask()
  assert.equal(calls, 0)
  view.unmount()
})

test('progress is bounded, unknown states are honest, and hidden pages pause polling', () => {
  const view = taskPage({})
  for (const [input, expected] of [[150, 100], [-1, 0], ['bad', 0], [Infinity, 0]]) {
    view.state.task.value.progress = input
    assert.equal(view.state.progress.value, expected)
  }
  view.state.task.value.status = 'mystery'
  assert.equal(view.state.taskStateLabel.value, '状态未记录')
  view.state.task.value.status = 'running'
  view.state.startRefresh()
  view.document.hidden = true
  view.state.onVisibilityChange()
  assert.equal(view.timers.size, 0)
  view.unmount()
})

test('material rows use typed detail routes and readable metadata without claiming validation', () => {
  const view = taskPage({})
  view.state.task.value.selectedItems = [
    { id: '26', type: 'paper', source: { journal: 'Coatings' } },
    { id: '18', type: 'article', source: { url: 'https://www.example.com/news', publisher: '新闻发布机构' } },
    { id: '54', type: 'file', source: { filename: '测试.docx' } },
    { id: '55', type: 'unknown', source: {} }
  ]
  const rows = view.state.materialRows.value
  assert.equal(rows[0].path, '/portal/papers/26')
  assert.equal(rows[0].sourceLabel, 'Coatings')
  assert.equal(rows[1].path, '/portal/news/18')
  assert.equal(rows[1].sourceLabel, '新闻发布机构')
  assert.equal(rows[2].path, '/portal/knowledge/54')
  assert.equal(rows[3].path, null)
  assert.equal(view.state.materialCounts.value.internal, 1)
  assert.equal(view.state.materialCounts.value.other, 1)
  view.unmount()
})

test('failed, cancelled and queued task fallback states are not shown as running', () => {
  const view = taskPage({})
  for (const status of ['failed', 'cancelled', 'queued']) {
    view.state.task.value = { status, stages: [], logs: [] }
    assert.ok(view.state.stageRows.value.every(row => row.status !== 'running'))
    assert.doesNotMatch(view.state.logs.value[0].message, /正在读取/)
  }
  view.unmount()
})

test('task template displays actual name and never falls back to the numeric ID', () => {
  const view = taskPage({})
  view.state.task.value = { templateName: '科技项目需求填报表', config: { template_id: '31' } }
  assert.equal(view.state.templateName.value, '科技项目需求填报表')
  view.state.task.value = { config: { template_id: '31' } }
  assert.equal(view.state.templateName.value, '模板名称未记录')
  view.unmount()
})

test('terminal tasks never animate stale running stages or invent successful stage outcomes', () => {
  const view = taskPage({})
  view.state.task.value = { status: 'completed', stages: [{ label: '生成', status: 'running' }, { label: '导出', status: 'waiting' }] }
  assert.ok(view.state.stageRows.value.every(stage => stage.status === 'unrecorded'))
  view.state.task.value.status = 'cancelled'
  assert.ok(view.state.stageRows.value.every(stage => stage.status === 'cancelled'))
  view.unmount()
})
