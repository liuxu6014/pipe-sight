import test from 'node:test'
import assert from 'node:assert/strict'
import { createSavedSearchRepository, normalizeSearchFilters, searchFilterChips, applySavedSearchQuery } from '../src/utils/portal/savedSearches.js'

function memory() { const values = new Map(); return { values, getItem: key => values.get(key) || null, setItem: (key, value) => values.set(key, value) } }

test('only allowed controls are saved; account and page scopes stay isolated', () => {
  const storage = memory()
  const repo = createSavedSearchRepository(storage, '7', 'paper')
  repo.save('腐蚀研究', { q: '腐蚀', year: '2024', journals: ['期刊'], page: 8, size: 50, content: '私有正文', apiKey: '不要保存' })
  assert.equal(repo.list().length, 1)
  assert.equal(createSavedSearchRepository(storage, '8', 'paper').list().length, 0)
  assert.equal(createSavedSearchRepository(storage, '7', 'news').list().length, 0)
  const stored = [...storage.values.values()][0]
  assert.ok(!stored.includes('私有正文') && !stored.includes('不要保存'))
  assert.equal(repo.list()[0].filters.q, '腐蚀')
})

test('duplicates update the saved name; exceeding the limit never drops old conditions', () => {
  const repo = createSavedSearchRepository(memory(), '7', 'search')
  for (let i = 0; i < 12; i++) repo.save(`条件${i}`, { q: `关键词${i}` })
  repo.save('重新命名', { q: '关键词0' })
  assert.equal(repo.list().length, 12)
  assert.ok(repo.list().some(item => item.name === '重新命名'))
  assert.throws(() => repo.save('第十三组', { q: '新关键词' }), /12/)
  assert.equal(repo.list().length, 12)
})

test('restore resets filters and page, but preserves page size and display mode', () => {
  const query = { q: '旧', source: '微信公众号', tag: ['旧标签'], category: '全部', view: 'card', size: 50, page: 7 }
  assert.equal(applySavedSearchQuery(query, { q: '管道' }, 'news'), true)
  assert.deepEqual(query, { q: '管道', source: '全部', tag: [], category: '全部', view: 'card', size: 50, page: 1 })
  assert.equal(applySavedSearchQuery(query, { q: '管道' }, 'news'), false)
})

test('invalid data, storage failure, empty filters and unavailable semantic mode never report a saved condition', () => {
  assert.throws(() => normalizeSearchFilters('search', { mode: 'semantic' }), /语义/)
  assert.throws(() => createSavedSearchRepository(memory(), '', 'news'), /登录/)
  const storage = memory()
  const repo = createSavedSearchRepository(storage, '7', 'news')
  assert.throws(() => repo.save('空条件', {}), /筛选/)
  assert.throws(() => repo.save('过长', { q: '字'.repeat(201) }), /200/)
  repo.save('有效', { q: '管道' })
  const key = [...storage.values.keys()][0]
  storage.values.set(key, '{bad json')
  assert.throws(() => repo.save('不能覆盖', { q: '新条件' }), /读取/)
  assert.equal(storage.values.get(key), '{bad json')
  const denied = createSavedSearchRepository({ getItem: () => null, setItem() { throw new Error('blocked') } }, '7', 'news')
  assert.throws(() => denied.save('条件', { q: '管道' }), /保存/)
})

test('chips represent actual filters; removing a saved entry does not delete resources', () => {
  assert.deepEqual(searchFilterChips('paper', { q: '检测', year: '2024', journals: ['期刊A'] }).map(item => item.label), ['关键词：检测', '年份：2024', '期刊：期刊A'])
  const repo = createSavedSearchRepository(memory(), '7', 'knowledge')
  repo.save('待处理', { status: '解析失败' })
  repo.remove(repo.list()[0].id)
  assert.equal(repo.list().length, 0)
})
