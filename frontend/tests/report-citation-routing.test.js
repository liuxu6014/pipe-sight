import test from 'node:test'
import assert from 'node:assert/strict'
import { getCitationPath } from '../src/utils/portal/citationRouting.js'

test('paper and news references go to their own detail page, before external URLs', () => {
  assert.equal(getCitationPath({ type: 'paper', sourceId: '26', url: 'https://doi.org/example' }), '/portal/papers/26')
  assert.equal(getCitationPath({ type: 'article', sourceId: '18' }), '/portal/news/18')
  assert.equal(getCitationPath({ type: '论文摘要', source_id: '25' }), '/portal/papers/25')
  assert.equal(getCitationPath({ type: '新闻正文', sourceId: '19' }), '/portal/news/19')
  assert.equal(getCitationPath({ type: 'wechat', sourceId: '19' }), '/portal/news/19')
})

test('only internal documents use knowledge routes; no citation ordinal fallback', () => {
  assert.equal(getCitationPath({ type: 'file', sourceId: '9007199254740993' }), '/portal/knowledge/9007199254740993')
  assert.equal(getCitationPath({ type: 'paper', id: 1 }), null)
  assert.equal(getCitationPath({ type: 'unknown', sourceId: '26' }), null)
  assert.equal(getCitationPath({ type: 'paper', sourceId: '../26' }), null)
})
