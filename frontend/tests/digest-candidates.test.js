import test from 'node:test'
import assert from 'node:assert/strict'
import { createDigestCandidateSearch } from '../src/utils/portal/digestCandidates.js'

const article = id => ({ id: String(id), title: `资讯 ${id}`, category: 'news', summary: '摘要' })
test('candidate search queries the full article catalog with server-side pagination and source filters', async () => {
  const calls = []
  const search = createDigestCandidateSearch(async params => { calls.push(params); return { data: { rows: [article(params.pageNum === 1 ? 1 : 21)], total: 36 } } })
  await search.configure({ enabled: true, epoch: 1 })
  assert.equal(calls[0].pageSize, 10)
  assert.equal(calls[0].category, 'article')
  await search.setPage(2)
  assert.equal(calls.at(-1).pageNum, 2)
  assert.equal(search.rows.value[0].id, '21')
  search.query.keyword = '管网'; search.query.source = 'wechat'
  await search.search()
  assert.equal(calls.at(-1).keyword, '管网')
  assert.equal(calls.at(-1).source_type, 'wechat')
  assert.equal(calls.at(-1).pageNum, 1)
  await search.setSize(50)
  assert.equal(calls.at(-1).pageSize, 50)
  search.dispose()
})
test('a late result never replaces newer query results or another account scope', async () => {
  const pending = []
  const search = createDigestCandidateSearch(() => new Promise(resolve => pending.push(resolve)))
  const initial = search.configure({ enabled: true, epoch: 1 })
  search.query.keyword = 'new'
  const next = search.search()
  pending[1]({ data: { rows: [article(2)], total: 1 } }); await next
  pending[0]({ data: { rows: [article(1)], total: 1 } }); await initial
  assert.equal(search.rows.value[0].id, '2')
  const late = search.search()
  await search.configure({ enabled: false, epoch: 2 })
  pending[2]({ data: { rows: [article(3)], total: 1 } }); await late
  assert.equal(search.rows.value.length, 0)
  search.dispose()
})
test('failure and malformed data are not displayed as an empty success or selectable stale results', async () => {
  let calls = 0
  const search = createDigestCandidateSearch(async () => ({ data: ++calls === 1 ? { rows: [article(1)], total: 1 } : { rows: null, total: 0 } }))
  await search.configure({ enabled: true })
  await search.search()
  assert.equal(search.rows.value.length, 0)
  assert.match(search.error.value, /格式/)
  search.dispose()
})
test('a shrinking result set clamps the page and reloads the valid page', async () => {
  let shrink = false
  const calls = []
  const search = createDigestCandidateSearch(async params => { calls.push(params.pageNum); return { data: { rows: shrink && params.pageNum > 1 ? [] : [article(1)], total: shrink ? 1 : 50 } } })
  await search.configure({ enabled: true })
  shrink = true
  await search.setPage(5)
  assert.equal(search.query.page, 1)
  assert.deepEqual(calls, [1, 5, 1])
  search.dispose()
})

test('changing pages retains the known total while loading so pagination cannot reset to page one', async () => {
  let resolve, calls = 0
  const search = createDigestCandidateSearch(() => ++calls === 1 ? Promise.resolve({ data: { rows: [article(1)], total: 29 } }) : new Promise(done => { resolve = done }))
  await search.configure({ enabled: true })
  const pending = search.setPage(3)
  assert.equal(search.loading.value, true)
  assert.equal(search.total.value, 29)
  assert.equal(search.query.page, 3)
  resolve({ data: { rows: [article(21)], total: 29 } })
  await pending
  assert.equal(search.rows.value[0].id, '21')
  search.dispose()
})
