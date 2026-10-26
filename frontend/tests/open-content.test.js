import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse } from '@vue/compiler-sfc'
import { baseParse } from '@vue/compiler-dom'
import { openPortalContent, returnFromPaperDetail, returnFromNewsDetail } from '../src/utils/portal/openContent.js'

test('news, paper details and other navigation all stay in place', async () => {
  const opened = [], pushed = []
  const previous = globalThis.window
  globalThis.window = { open: (...args) => opened.push(args) }
  const router = { resolve: path => ({ href: path }), push: path => { pushed.push(path); return Promise.resolve() } }
  try {
    for (const path of ['/portal/news/n1', '/portal/papers/p1?tab=abstract']) await openPortalContent(router, path)
    assert.deepEqual(opened, [])
    for (const path of ['/portal/news', '/portal/basket', '/portal/research/reports/r1']) await openPortalContent(router, path)
    assert.deepEqual(pushed, ['/portal/news/n1', '/portal/papers/p1?tab=abstract', '/portal/news', '/portal/basket', '/portal/research/reports/r1'])
  } finally {
    if (previous === undefined) delete globalThis.window
    else globalThis.window = previous
  }
})

test('news return restores in-app history and falls back to news for a direct visit', async () => {
  const calls = []
  const router = { options: { history: { state: { back: '/portal/news?q=管道&page=2&size=20&view=card' } } }, back: () => calls.push('back'), push: path => calls.push(path) }
  await returnFromNewsDetail(router)
  assert.deepEqual(calls, ['back'])
  for (const back of [null, '/login', 'https://external.example/portal/news']) {
    router.options.history.state.back = back
    await returnFromNewsDetail(router)
  }
  assert.deepEqual(calls.slice(1), Array(3).fill('/portal/news'))
})

test('news title and cover use same-page links and detail exposes Back', () => {
  const list = readFileSync(new URL('../src/views/portal/pages/NewsListView.vue', import.meta.url), 'utf8')
  const detail = readFileSync(new URL('../src/views/portal/pages/NewsDetailView.vue', import.meta.url), 'utf8')
  assert.match(list, /<router-link[^>]*class="ps-news-cover"[^>]*:to=/)
  assert.match(list, /<router-link class="ps-news-title"[^>]*:to=/)
  assert.doesNotMatch(list, /target="_blank"/)
  assert.match(detail, /aria-label="返回"[^>]*@click="returnFromNewsDetail\(router\)"\s*\/>/)
})

test('paper list cards omit access status badges and the retired access filter', () => {
  const source = readFileSync(new URL('../src/views/portal/pages/PaperListView.vue', import.meta.url), 'utf8')
  assert.doesNotMatch(source, /class="ps-paper-access"|accessClass\(/)
  assert.doesNotMatch(source, /全文状态|accessStatus/)
})

test('news and paper place Back to the left of the title in the same row', () => {
  for (const filename of ['NewsDetailView.vue', 'PaperDetailView.vue']) {
    const source = readFileSync(new URL(`../src/views/portal/pages/${filename}`, import.meta.url), 'utf8')
    const { descriptor } = parse(source)
    const root = baseParse(descriptor.template.content)
    const rows = []
    function visit(node) {
      if (node.type === 1 && node.props.some(prop => prop.name === 'class' && prop.value?.content === 'ps-detail-title-row')) rows.push(node)
      for (const child of node.children || []) visit(child)
    }
    visit(root)
    assert.equal(rows.length, 1)
    assert.deepEqual(rows[0].children.filter(child => child.type === 1).map(child => child.tag), ['el-button', 'h1'])
    const button = rows[0].children.find(child => child.type === 1)
    assert.equal(button.children.length, 0)
    assert.ok(button.props.some(prop => prop.name === 'aria-label' && prop.value?.content === '返回'))
    assert.ok(button.props.some(prop => prop.name === 'title' && prop.value?.content === '返回'))
    assert.match(source, /class="[^"]*ps-detail-header[^"]*"/)
    assert.doesNotMatch(source, /class="ps-(news|paper)-back"/)
  }
})

test('paper return preserves in-app list history and falls back for direct or external entry', async () => {
  const calls = []
  const router = { options: { history: { state: { back: '/portal/papers?q=test&page=2&size=20' } } }, back: () => calls.push('back'), push: path => calls.push(path) }
  await returnFromPaperDetail(router)
  assert.deepEqual(calls, ['back'])
  for (const back of [null, '/login', 'https://external.example/portal/papers', '//external.example/portal']) {
    router.options.history.state.back = back
    await returnFromPaperDetail(router)
  }
  assert.deepEqual(calls.slice(1), Array(4).fill('/portal/papers'))
})

test('both detail pages place basket actions beside metadata in the same information row', () => {
  for (const filename of ['NewsDetailView.vue', 'PaperDetailView.vue']) {
    const source = readFileSync(new URL(`../src/views/portal/pages/${filename}`, import.meta.url), 'utf8')
    const { descriptor } = parse(source)
    const rows = []
    function visit(node) {
      if (node.type === 1 && node.props.some(prop => prop.name === 'class' && prop.value?.content === 'ps-detail-info-row')) rows.push(node)
      for (const child of node.children || []) visit(child)
    }
    visit(baseParse(descriptor.template.content))
    assert.equal(rows.length, 1)
    const children = rows[0].children.filter(child => child.type === 1)
    assert.equal(children.length, 2)
    assert.ok(children[0].props.some(prop => ['ps-article-meta', 'ps-paper-detail-meta'].includes(prop.value?.content)))
    assert.ok(children[1].props.some(prop => prop.value?.content === 'ps-article-actions'))
    assert.equal(children[1].children.filter(child => child.type === 1)[0].tag, 'el-button')
  }
})
