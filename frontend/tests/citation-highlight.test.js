import test from 'node:test'
import assert from 'node:assert/strict'
import { citationSentenceBounds } from '../src/utils/portal/citationHighlight.js'

for (const [text, expected] of [
  ['前一句。当前有证据的判断[2]。后一句。', '当前有证据的判断[2]。'],
  ['前一句。当前有证据的判断。[2]后一句。', '当前有证据的判断。[2]'],
  ['前一句。指标为3.5，已有研究支持[1][2]。后一句。', '指标为3.5，已有研究支持[1][2]。'],
  ['Prior sentence. Supported finding[2]. Next sentence.', 'Supported finding[2].'],
]) test(`locates only the cited sentence: ${text}`, () => {
  const start = text.indexOf('[2]')
  const bounds = citationSentenceBounds(text, start, start + 3)
  assert.equal(text.slice(bounds.start, bounds.end), expected)
})
