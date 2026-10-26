import test from 'node:test'
import assert from 'node:assert/strict'
import { combineLatest, newsDate, cleanSummary, cleanResultMeta, resultPath } from '../src/utils/portal/discovery.js'
test('news date formatting removes uncollected zero time but preserves real times and month precision', () => {
  assert.equal(newsDate('2025-12-04 00:00:00'), '2025-12-04')
  assert.equal(newsDate('2025-12-04 14:32:11'), '2025-12-04 14:32:11')
  assert.equal(newsDate('2024-03'), '2024-03')
  assert.equal(newsDate(null), '日期未提供')
  assert.equal(cleanResultMeta('来源 · 2025-12-04 00:00:00'), '来源 · 2025-12-04')
  assert.equal(cleanResultMeta('来源 · '), '来源')
})
test('latest news and papers are combined by actual publication dates without invented dates', () => {
  const rows = combineLatest([{ id: 'n1', publish_time: '2025-12-04' }, { id: 'n2', source_type: 'wechat' }], [{ id: 'p1', publish_time: '2024-03' }])
  assert.deepEqual(rows.map(x => x.id), ['n1', 'p1', 'n2'])
  assert.equal(rows[1].date, '2024-03')
  assert.equal(rows[2].date, '日期未提供')
})
test('search results retain internal detail destinations and remove editorial prefixes', () => {
  assert.equal(resultPath({ type: 'report', id: 'one', report_type: 'weekly' }), '/portal/digests/one')
  assert.equal(resultPath({ path: 'https://example.com/' }), '')
  assert.equal(resultPath({ path: '/portal/news/one' }), '/portal/news/one')
  assert.equal(cleanSummary('导读摘要（据公开资料整理）：正文'), '正文')
})
