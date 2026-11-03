import test from 'node:test'
import assert from 'node:assert/strict'
import { adaptersForSource, supportsSourceAdapter } from '../src/utils/pipeline/sourceAdapters.js'

test('source adapter capabilities retain all registered news, paper and WeChat collectors', () => {
  assert.deepEqual(adaptersForSource('wechat').map(item => item.key), ['wechat_rss'])
  assert.equal(supportsSourceAdapter({ type: 'website', adapter: 'pipechina_group_news' }), true)
  assert.equal(supportsSourceAdapter({ type: 'news', adapter_key: 'pipechina_group_news' }), true)
  assert.equal(supportsSourceAdapter({ type: 'paper', adapter: 'crossref_works' }), true)
  assert.equal(supportsSourceAdapter({ type: 'wechat', adapter: 'wechat_rss' }), true)
  assert.equal(supportsSourceAdapter({ type: 'wechat', adapter: 'pipechina_group_news' }), false)
  assert.equal(supportsSourceAdapter({ type: 'paper', adapter: 'pipechina_group_news' }), false)
})
