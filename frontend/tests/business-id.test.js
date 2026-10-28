import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { computed, effectScope, ref } from 'vue'
import { normalizeBusinessTimes } from '../src/utils/portal/businessTime.js'
import * as ids from '../src/utils/portal/businessId.js'
import { useBasketSelection, resolveBasketSelection } from '../src/utils/portal/basketSelection.js'
import { verifyEvidence } from '../src/utils/portal/evidenceInput.js'
import { getPortalReportPath } from '../src/views/portal/utils/routing.js'

const large = '9007199254740993'
const next = '9007199254740994'

test('business IDs retain bigint precision and reject rounded numbers, UUIDs and overflow', () => {
  for (const value of [large, next, '9223372036854775807']) assert.equal(ids.requireBusinessId(value), value)
  assert.equal(ids.requireBusinessId(12), '12')
  for (const value of [9007199254740992, '9223372036854775808', '0', '-1', '01', '1e3', 'template-01', 'ac17-uuid']) {
    assert.equal(ids.decimalId(value), '')
    assert.throws(() => ids.requireBusinessId(value), /编号已升级.*重新选择/)
  }
  assert.equal(getPortalReportPath({ id: large, reportType: 'research' }), `/portal/research/reports/${large}`)
})

test('DTO boundary normalizes entity IDs but preserves tokens, text and local outline IDs', () => {
  const token = 'manual:550e8400-e29b-41d4-a716-446655440000'
  const payload = ids.validateBusinessInput({ templateId: large, selectedItemIds: [next, { id: 12, type: 'paper' }], requestId: token, execution_token: token, requirements: '保留正文', outline: [{ id: 1, title: '原章节' }] })
  assert.equal(payload.templateId, large)
  assert.deepEqual(payload.selectedItemIds, [next, { id: '12', type: 'paper' }])
  assert.equal(payload.requestId, token)
  assert.equal(payload.execution_token, token)
  assert.deepEqual(payload.outline, [{ id: 1, title: '原章节' }])
  assert.equal(ids.normalizeBusinessData({ data: [{ modelId: 12 }] }).data[0].modelId, '12')
  assert.equal(ids.normalizeBusinessData({ rows: [{ id: large, parentId: next }] }).rows[0].id, large)
  assert.throws(() => ids.normalizeBusinessData({ id: 9007199254740992 }), /安全整数/)
})

test('cross-page selections distinguish adjacent large IDs and only deselect the current page', () => {
  const scope = effectScope()
  try {
    scope.run(() => {
      const basket = ref([{ id: large }, { id: next }, { id: '42' }])
      const page = ref([basket.value[0]])
      const selection = useBasketSelection(() => basket.value, () => page.value, () => 0)
      selection.toggleVisible(true)
      page.value = [basket.value[1], basket.value[2]]
      selection.toggleVisible(true)
      assert.deepEqual(selection.selectedIds.value, [large, next, '42'])
      selection.toggleVisible(false)
      assert.deepEqual(selection.selectedIds.value, [large])
      assert.equal(computed(() => selection.selectedItems.value.length).value, 1)
    })
  } finally { scope.stop() }
})

test('old UUID selections remain visible with upgrade status and never fetch detail', async () => {
  let calls = 0
  const old = '550e8400-e29b-41d4-a716-446655440000'
  const selection = resolveBasketSelection([{ id: old, title: '原资料' }])
  assert.equal(selection.upgraded, true)
  assert.equal(selection.items[0].id, old)
  const result = await verifyEvidence({ id: old, type: 'article' }, { getIntelligence: () => { calls++ }, getMaterial: () => { calls++ } })
  assert.equal(calls, 0)
  assert.equal(result.ready, false)
  assert.match(result.reason, /编号已升级.*正文已保留/)
})

test('actual request boundary blocks legacy path and payload IDs before network, leaving caller text intact', async () => {
  const calls = []
  const source = readFileSync(new URL('../src/api/pipeline/request.js', import.meta.url), 'utf8').replace(/^import .*\n/gm, '').replace('export default async function pipelineRequest', 'return async function pipelineRequest')
  const request = new Function('request', 'normalizeBusinessTimes', ...Object.keys(ids), source)(async options => { calls.push(options); return { data: { id: large, jobId: next } } }, normalizeBusinessTimes, ...Object.values(ids))
  const result = await request({ url: `/pipeline/research/reports/${large}`, method: 'get' })
  assert.equal(result.data.id, large)
  assert.equal(result.data.jobId, next)
  const form = { templateId: 'template-01', requirements: '用户尚未提交的正文', selectedItemIds: [large] }
  await assert.rejects(request({ url: '/pipeline/research/jobs', method: 'post', data: form }), /编号已升级/)
  await assert.rejects(request({ url: '/pipeline/research/reports/old-uuid', method: 'get' }), /编号已升级/)
  assert.equal(calls.length, 1)
  assert.equal(form.requirements, '用户尚未提交的正文')
  assert.equal(form.templateId, 'template-01')
})

test('entity wrappers preserve decimal paths and reject unsafe numbers before interpolation', async () => {
  const cases = [
    ['pipeline/intelligence.js', 'getPipelineIntelligenceDetail'],
    ['pipeline/intelligence.js', 'downloadPipelineKnowledgeDocument'],
    ['pipeline/categories.js', 'deletePipelineCategory'],
    ['pipeline/assets.js', 'getReportImageBlob'],
    ['pipeline/manuscript.js', 'getManuscriptJob'],
    ['ai/model.js', 'getModel']
  ]
  const calls = []
  const network = options => { calls.push(typeof options === 'string' ? options : options.url); return Promise.resolve({ data: {} }) }
  for (const [file, name] of cases) {
    const source = readFileSync(new URL('../src/api/' + file, import.meta.url), 'utf8').replace(/^import .*\n/gm, '').replace(/export /g, '')
    const fn = new Function('request', 'downloadGet', ...Object.keys(ids), source + '; return ' + name)(network, network, ...Object.values(ids))
    await fn(large)
    assert.ok(calls.at(-1).includes(large))
    const count = calls.length
    assert.throws(() => fn(9007199254740992), /编号已升级/)
    assert.throws(() => fn('old-uuid'), /编号已升级/)
    assert.equal(calls.length, count)
  }
})

test('catalog facet and administrator list paths are static routes, not entity IDs', async () => {
  const source = readFileSync(new URL('../src/api/pipeline/request.js', import.meta.url), 'utf8').replace(/^import .*\n/gm, '').replace('export default async function pipelineRequest', 'return async function pipelineRequest')
  const calls = []
  const request = new Function('request', 'requireBusinessId', 'validateBusinessInput', 'normalizeBusinessData', 'normalizeBusinessTimes', source)(async options => { calls.push(options.url); return { data: {} } }, ids.requireBusinessId, ids.validateBusinessInput, ids.normalizeBusinessData, normalizeBusinessTimes)
  await request({ url: '/pipeline/intelligence/filters' })
  await request({ url: '/pipeline/research/admin/reports' })
  assert.deepEqual(calls, ['/pipeline/intelligence/filters', '/pipeline/research/admin/reports'])
  await assert.rejects(request({ url: '/pipeline/intelligence/old-uuid' }), /编号已升级/)
  assert.equal(calls.length, 2)
})

test('nested editor references reject old IDs without treating local section or citation IDs as entity IDs', () => {
  const body = {
    content: '用户正文不能改写',
    sections: [{ id: 'local-section', content: '章节正文', citationIds: [1] }],
    citations: [{ id: 1, sourceId: large, quote: '保留原引用文字' }],
    config: { templateId: next, selected_item_ids: [large], execution_token: 'old-attempt-uuid' }
  }
  const payload = ids.validateBusinessInput(body)
  assert.deepEqual(payload, body)
  body.citations[0].sourceId = 'old-source-uuid'
  assert.throws(() => ids.validateBusinessInput(body), /编号已升级/)
  assert.equal(body.content, '用户正文不能改写')
  assert.equal(body.sections[0].content, '章节正文')
  body.citations[0].sourceId = large
  body.config.templateId = 'template-01'
  assert.throws(() => ids.validateBusinessInput(body), /编号已升级/)
  body.config.templateId = next
  body.config.selected_item_ids = ['old-item-uuid']
  assert.throws(() => ids.validateBusinessInput(body), /编号已升级/)
})

test('JSON-restored numeric selections remain distinct while legacy UUIDs require explicit reselection', () => {
  const cache = JSON.parse(JSON.stringify({ basket: [{ id: large }, { id: next }, { id: 'old-cached-uuid' }], selected: [large, next] }))
  const selection = resolveBasketSelection(cache.basket, cache.selected)
  assert.equal(selection.upgraded, false)
  assert.deepEqual(selection.items.map(item => item.id), [large, next])
  assert.deepEqual(ids.validateBusinessInput({ selectedItemIds: cache.selected }).selectedItemIds, [large, next])
  const old = resolveBasketSelection(cache.basket, 'old-cached-uuid')
  assert.equal(old.upgraded, true)
  assert.equal(old.items[0].id, 'old-cached-uuid')
  assert.throws(() => ids.validateBusinessInput({ selectedItemIds: old.items.map(item => item.id) }), /编号已升级/)
  assert.equal(cache.basket.length, 3)
})
