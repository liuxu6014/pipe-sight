import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { effectScope, nextTick, ref } from 'vue'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'
import { useReportImages } from '../src/utils/portal/reportImages.js'

const settle = async () => { for (let i = 0; i < 5; i++) { await nextTick(); await new Promise(resolve => setImmediate(resolve)) } }
const response = (images, reportId = 'r1') => ({ data: { reportId, images } })
function harness(api) {
  const id = ref('r1'), epoch = ref(0), scheduled = new Map(), created = [], revoked = []
  let seq = 0, state
  const scope = effectScope()
  scope.run(() => { state = useReportImages(() => id.value, api, {
    epoch: () => epoch.value,
    urls: { createObjectURL(blob) { const value = 'blob:image-' + created.length; created.push({ value, blob }); return value }, revokeObjectURL(value) { revoked.push(value) } },
    timers: { setTimeout(fn) { scheduled.set(++seq, fn); return seq }, clearTimeout(key) { scheduled.delete(key) } }
  }) })
  return { ...state, id, epoch, scheduled, created, revoked, close: () => scope.stop(), async tick() {
    const [key, fn] = scheduled.entries().next().value; scheduled.delete(key); await fn(); await settle()
  } }
}

test('canonical report images load actual authenticated image bytes and release object URLs on exit', async () => {
  const requested = []
  const h = harness({ getMetadata: async () => response([{ id: 'a1', status: 'completed', position: '2', url: '/pipeline/research/assets/a1/download', error: '' }]),
    getImage: async id => { requested.push(id); return new Blob(['image bytes'], { type: 'image/png' }) } })
  await settle()
  assert.deepEqual(requested, ['a1'])
  assert.equal(h.images.value[0].imageUrl, 'blob:image-0')
  assert.equal(h.images.value[0].position, '2')
  assert.equal(h.scheduled.size, 0)
  h.close(); assert.deepEqual(h.revoked, ['blob:image-0'])
})

test('queued and running refresh until completed, without fetching a pending file', async () => {
  let status = 'queued', downloads = 0
  const h = harness({ getMetadata: async () => response([{ id: 'a', status, url: status === 'completed' ? '/file' : '' }]),
    getImage: async () => { downloads++; return new Blob(['bytes'], { type: 'image/png' }) } })
  try {
    await settle(); assert.equal(downloads, 0); assert.equal(h.scheduled.size, 1)
    status = 'running'; await h.tick(); assert.equal(downloads, 0)
    status = 'completed'; await h.tick(); assert.equal(downloads, 1); assert.equal(h.scheduled.size, 0)
    await h.load(); assert.equal(downloads, 1)
  } finally { h.close() }
})

test('failed image retry is independent and does not regenerate report text', async () => {
  let status = 'failed', retries = 0
  const h = harness({ getMetadata: async () => response([{ id: 'a', status, error: status === 'failed' ? '图片模型未配置' : '', url: '' }]),
    retry: async id => { retries++; assert.equal(id, 'a'); status = 'queued'; return { data: { id, status } } } })
  try {
    await settle(); assert.equal(h.images.value[0].error, '图片模型未配置')
    await h.retry(h.images.value[0]); assert.equal(retries, 1)
    assert.equal(h.images.value[0].status, 'queued'); assert.equal(h.images.value[0].retrying, false)
    assert.equal(h.scheduled.size, 1)
    await h.retry(h.images.value[0]); assert.equal(retries, 1)
  } finally { h.close() }
})

test('image and retry failures stay visible and return no fake image', async () => {
  let failBlob = true
  const h = harness({ getMetadata: async () => response([{ id: 'a', status: 'completed', url: '/file' }, { id: 'b', status: 'failed', error: '生成失败' }]),
    getImage: async () => { if (failBlob) return new Blob(['{"detail":"denied"}'], { type: 'application/json' }); return new Blob(['bytes'], { type: 'image/png' }) },
    retry: async () => { throw new Error('图片模型未配置') } })
  try {
    await settle(); assert.equal(h.created.length, 0); assert.match(h.images.value[0].imageError, /不是有效图片/)
    await h.retry(h.images.value[1]); assert.equal(h.actionError.value, '图片模型未配置'); assert.equal(h.images.value[1].status, 'failed')
    failBlob = false; await h.reloadImage(h.images.value[0]); assert.equal(h.created.length, 1)
    assert.equal(h.images.value[0].imageError, '')
  } finally { h.close() }
})

test('metadata errors poll for recovery and never substitute a default graph', async () => {
  let failed = true
  const h = harness({ getMetadata: async () => { if (failed) throw new Error('Not Found'); return response([]) } })
  try {
    await settle(); assert.equal(h.loadError.value, 'Not Found'); assert.equal(h.images.value.length, 0)
    failed = false; await h.tick(); assert.equal(h.loadError.value, ''); assert.equal(h.scheduled.size, 0)
  } finally { h.close() }
})

test('account changes and late downloads cannot expose a previous report image', async () => {
  let resolve
  const h = harness({ getMetadata: async id => response(id === 'r1' ? [{ id: 'a', status: 'completed', url: '/file' }] : [], id),
    getImage: () => new Promise(yes => { resolve = yes }) })
  try {
    await settle(); h.id.value = 'r2'; h.epoch.value++; await settle()
    resolve(new Blob(['old bytes'], { type: 'image/png' })); await settle()
    assert.equal(h.images.value.length, 0); assert.equal(h.created.length, 0)
  } finally { h.close() }
})

test('image viewer compiles and legacy graph controls are absent', () => {
  for (const path of ['components/ReportImageAssets.vue', 'pages/DiagramEditorView.vue']) {
    const source = readFileSync(new URL('../src/views/portal/' + path, import.meta.url), 'utf8')
    const { descriptor } = parse(source)
    const script = compileScript(descriptor, { id: path })
    assert.deepEqual(compileTemplate({ source: descriptor.template.content, id: path, filename: path, compilerOptions: { bindingMetadata: script.bindings } }).errors, [])
    assert.doesNotMatch(source, /defaultDiagram|localStorage|节点库|导出 SVG|updatePipelineResearchReportDiagram/)
  }
})
