import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { setImmediate } from 'node:timers/promises'
import * as vue from 'vue'
import { createMemoryHistory, createRouter, RouterView, useRoute, useRouter } from 'vue-router'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'
import { returnToPreviousPage } from '../src/utils/portal/openContent.js'

const filename = new URL('../src/views/pipeline/intelligence/detail.vue', import.meta.url)
const { descriptor } = parse(readFileSync(filename, 'utf8'))
const settle = async () => { await vue.nextTick(); await setImmediate(); await vue.nextTick() }
const deferred = () => {
  let resolve, reject
  const promise = new Promise((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}

async function mountDetail(load, { initial = '/pipeline/intelligence/detail?id=20', cached = true } = {}) {
  const imports = {
    ...vue, useRoute, useRouter, getPipelineIntelligenceDetail: load, returnToPreviousPage,
    formatBusinessTime: value => value || '', collectionTime: () => '',
    ContentEntities: {}, ContentInsights: {}, Back: {}
  }
  const script = compileScript(descriptor, { id: 'management-intelligence-detail' }).content
    .replace(/^import[\s\S]*?from ['"][^'"]+['"];?\n?/gm, '')
    .replace('export default', 'return')
  const entries = Object.entries(imports).filter(([key]) => !['default', 'module.exports'].includes(key))
  const Detail = new Function(...entries.map(([key]) => key), script)(...entries.map(([, value]) => value))
  const instances = []
  const setup = Detail.setup
  Detail.setup = (props, context) => { const bindings = setup(props, context); instances.push(bindings); return bindings }
  Detail.render = () => vue.h('div')
  const List = { name: 'PipelineIntelligence', render: () => vue.h('div') }
  const router = createRouter({ history: createMemoryHistory(), routes: [
    { path: '/pipeline/intelligence/detail', name: 'PipelineIntelligenceDetail', component: Detail },
    { path: '/pipeline/intelligence', name: 'PipelineIntelligence', component: List },
    { path: '/pipeline/model', component: List }
  ] })
  const node = type => ({ type, children: [], parent: null })
  const renderer = vue.createRenderer({
    createElement: node, createText: node, createComment: node,
    setText() {}, setElementText() {}, patchProp() {},
    parentNode: child => child.parent,
    nextSibling: child => child.parent?.children[child.parent.children.indexOf(child) + 1] || null,
    insert(child, parent, anchor) {
      if (child.parent) child.parent.children.splice(child.parent.children.indexOf(child), 1)
      child.parent = parent
      const index = parent.children.indexOf(anchor)
      parent.children.splice(index < 0 ? parent.children.length : index, 0, child)
    },
    remove(child) { if (child.parent) child.parent.children.splice(child.parent.children.indexOf(child), 1) }
  })
  const app = renderer.createApp({ render: () => vue.h(RouterView, null, {
    default: ({ Component }) => cached ? vue.h(vue.KeepAlive, null, [Component]) : Component
  }) }).use(router)
  await router.push(initial)
  app.mount(node('root'))
  await settle()
  return { router, instances, get view() { return instances.at(-1) }, close: () => app.unmount() }
}

test('management intelligence reader and retry state compile', () => {
  const script = compileScript(descriptor, { id: 'management-intelligence-detail' })
  const template = compileTemplate({ source: descriptor.template.content, filename: filename.pathname,
    id: 'management-intelligence-detail', compilerOptions: { bindingMetadata: script.bindings } })
  assert.deepEqual(template.errors, [])
})

test('changing query ID reloads the cached reader and clears old content', async () => {
  const second = deferred(), calls = []
  const ctx = await mountDetail(id => {
    calls.push(id)
    return id === '20' ? Promise.resolve({ data: { id: '20', title: '资讯20', category: 'news', tags: ['旧标签'] } }) : second.promise
  })
  try {
    const first = ctx.view
    assert.equal(first.detail.value.title, '资讯20')
    assert.deepEqual(calls, ['20'], 'initial KeepAlive activation must not duplicate the request')
    await ctx.router.push('/pipeline/intelligence/detail?id=268')
    assert.equal(ctx.instances.length, 1, 'query-only navigation reuses the real Vue component')
    assert.equal(first.detail.value.title, undefined)
    assert.equal(first.loading.value, true)
    second.resolve({ data: { id: '268', title: '论文268', category: 'paper', tags: null } })
    await settle()
    assert.deepEqual(calls, ['20', '268'])
    assert.equal(first.detail.value.title, '论文268')
    assert.deepEqual(first.detail.value.tags, [])
  } finally { ctx.close() }
})

test('a late response or failure cannot overwrite a newer intelligence item', async () => {
  for (const failOld of [false, true]) {
    const first = deferred(), second = deferred()
    const ctx = await mountDetail(id => id === '20' ? first.promise : second.promise)
    try {
      await ctx.router.push('/pipeline/intelligence/detail?id=268')
      second.resolve({ data: { id: '268', title: '当前论文', category: 'paper' } })
      await settle()
      if (failOld) first.reject(new Error('旧请求失败'))
      else first.resolve({ data: { id: '20', title: '旧资讯' } })
      await settle()
      assert.equal(ctx.view.detail.value.title, '当前论文')
      assert.equal(ctx.view.loadError.value, '')
      assert.equal(ctx.view.loading.value, false)
    } finally { ctx.close() }
  }
})

test('a deactivated cached reader does not fetch list query IDs and reloads when reopened', async () => {
  const first = deferred(), calls = []
  const ctx = await mountDetail(id => {
    calls.push(id)
    return id === '20' ? first.promise : Promise.resolve({ data: { id, title: '重新打开的论文', category: 'paper' } })
  })
  try {
    const view = ctx.view
    await ctx.router.push('/pipeline/intelligence?id=99&page=2')
    await ctx.router.push('/pipeline/model?id=100')
    await view.loadDetail()
    first.resolve({ data: { id: '20', title: '离开后的旧资讯' } })
    await settle()
    assert.deepEqual(calls, ['20'])
    assert.equal(view.detail.value.title, undefined)
    assert.equal(view.loading.value, false)
    await ctx.router.push('/pipeline/intelligence/detail?id=268')
    await settle()
    assert.equal(ctx.instances.length, 1)
    assert.deepEqual(calls, ['20', '268'])
    assert.equal(view.detail.value.title, '重新打开的论文')
  } finally { ctx.close() }
})

test('unmount invalidates outstanding details and prevents manual reloads', async () => {
  const pending = deferred(), calls = []
  const ctx = await mountDetail(id => { calls.push(id); return pending.promise }, { cached: false })
  const view = ctx.view
  ctx.close()
  pending.resolve({ data: { id: '20', title: '卸载后的资讯' } })
  await settle()
  await view.loadDetail()
  assert.equal(view.detail.value.title, undefined)
  assert.equal(view.loading.value, false)
  assert.deepEqual(calls, ['20'])
})

test('missing ID never requests data, failures remain retryable, and wrong IDs are rejected', async () => {
  let calls = 0
  const ctx = await mountDetail(async id => {
    calls++
    if (calls === 1) throw new Error('网络不可用')
    return { data: { id: calls === 2 ? '21' : id, title: '恢复后的资讯', category: 'news' } }
  }, { initial: '/pipeline/intelligence/detail' })
  try {
    assert.equal(calls, 0)
    assert.match(ctx.view.loadError.value, /缺少情报编号/)
    assert.equal(ctx.view.loading.value, false)
    await ctx.router.push('/pipeline/intelligence/detail?id=20')
    await settle()
    assert.match(ctx.view.loadError.value, /暂时无法获取/)
    assert.equal(ctx.view.detail.value.title, undefined)
    await ctx.view.loadDetail()
    assert.match(ctx.view.loadError.value, /暂时无法获取/)
    assert.equal(ctx.view.detail.value.title, undefined)
    await ctx.view.loadDetail()
    assert.equal(ctx.view.loadError.value, '')
    assert.equal(ctx.view.detail.value.title, '恢复后的资讯')
  } finally { ctx.close() }
})

test('reader Back returns to the previous management list with its filters intact', async () => {
  const ctx = await mountDetail(async id => ({ data: { id, title: '资讯' } }), { initial: '/pipeline/intelligence?page=2&keyword=检测' })
  try {
    await ctx.router.push('/pipeline/intelligence/detail?id=20')
    await settle()
    // Memory history has no browser state.back field; supply that browser contract
    // while exercising the real router's previous entry and cached lifecycle.
    returnToPreviousPage(ctx.router, '/pipeline/intelligence', '/pipeline/intelligence?page=2&keyword=检测')
    await settle()
    assert.equal(ctx.router.currentRoute.value.path, '/pipeline/intelligence')
    assert.deepEqual(ctx.router.currentRoute.value.query, { page: '2', keyword: '检测' })
  } finally { ctx.close() }
})
