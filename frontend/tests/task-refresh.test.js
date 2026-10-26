import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import { computed, ref } from 'vue'

function taskPage({ get, retry }) {
  const source = readFileSync(new URL('../src/views/portal/pages/ResearchTaskView.vue', import.meta.url), 'utf8')
    .split('<script setup>')[1].split('</script>')[0].replace(/^import .*\n/gm, '')
  let unmount
  const timers = new Set()
  const navigations = []
  let sequence = 0
  const context = vm.createContext({
    computed, ref, onMounted() {}, onUnmounted(callback) { unmount = callback },
    useRoute: () => ({ params: { id: 'task-a' } }), useRouter: () => ({ replace: async path => navigations.push(path) }), useUserStore: () => ({}), taskStages: [],
    getPipelineResearchJob: get, retryPipelineResearchJob: retry,
    ElMessage: { warning() {}, success() {}, error() {} },
    setInterval() { const id = ++sequence; timers.add(id); return id }, clearInterval(id) { timers.delete(id) }
  })
  vm.runInContext(`${source}\nglobalThis.page = { task, loadTask, retryTask, startRefresh, loadError, stageRows, currentStageLabel, generationModeLabel, logs, materialCounts, canRetry, templateName }`, context)
  return { state: context.page, timers, navigations, unmount: () => unmount() }
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
  const pending = view.state.retryTask()
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
  await view.state.retryTask()
  assert.equal(view.navigations[0], '/portal/research/tasks/78')
  assert.equal(view.timers.size, 1)
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
