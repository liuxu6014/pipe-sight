import test from 'node:test'
import assert from 'node:assert/strict'
import { adaptersForSource, supportsSourceAdapter } from '../src/utils/pipeline/sourceAdapters.js'

test('source adapter capabilities match the backend builtin registry without promising WeChat collection', () => {
  assert.deepEqual(adaptersForSource('wechat'), [])
  assert.equal(supportsSourceAdapter({ type: 'website', adapter: 'pipechina_group_news' }), true)
  assert.equal(supportsSourceAdapter({ type: 'news', adapter_key: 'pipechina_group_news' }), true)
  assert.equal(supportsSourceAdapter({ type: 'paper', adapter: 'crossref_works' }), true)
  assert.equal(supportsSourceAdapter({ type: 'wechat', adapter: 'pipechina_group_news' }), false)
  assert.equal(supportsSourceAdapter({ type: 'paper', adapter: 'pipechina_group_news' }), false)
})
