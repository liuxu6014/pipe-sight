import test from 'node:test'
import assert from 'node:assert/strict'
import { makeRewriteDraft, applyRewriteDraft, rewriteRequest } from '../src/utils/portal/reportRewrite.js'

test('rewrite replaces only the selected passage and preserves other chapters', () => {
  const sections = [{ id: 1, content: '开头。原文[1]。结尾。' }, { id: 2, content: '另一章' }]
  const draft = makeRewriteDraft(sections[0], '原文[1]。')
  applyRewriteDraft(sections, draft, '精简正文[1]。')
  assert.equal(sections[0].content, '开头。精简正文[1]。结尾。')
  assert.equal(sections[1].content, '另一章')
})

test('changed chapter and ambiguous selection cannot be overwritten', () => {
  assert.throws(() => makeRewriteDraft({ id: 1, content: '相同。相同。' }, '相同。'))
  const sections = [{ id: 1, content: '原始正文' }]
  const draft = makeRewriteDraft(sections[0], '原始正文')
  sections[0].content = '刚修改的正文'
  assert.throws(() => applyRewriteDraft(sections, draft, '建议正文'))
  assert.equal(sections[0].content, '刚修改的正文')
})

test('citation changes or an empty result cannot be applied', () => {
  for (const value of ['改写[2]。', '改写。', '改写[1][1]。', '']) {
    const sections = [{ id: 1, content: '原文[1]。' }]
    const draft = makeRewriteDraft(sections[0], sections[0].content)
    assert.throws(() => applyRewriteDraft(sections, draft, value))
    assert.equal(sections[0].content, '原文[1]。')
  }
})

test('request offsets count Unicode codepoints, not UTF16 units', () => {
  const draft = makeRewriteDraft({ id: 1, content: '😀开头正文[1]。' }, '正文[1]。')
  const request = rewriteRequest(draft, { versionNo: 2, revision: 'opaque' }, 'shorten')
  assert.equal(request.start, 3)
  assert.equal(request.end, 9)
  assert.equal(request.expectedRevision, 'opaque')
})
