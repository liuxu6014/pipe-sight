import test from 'node:test'
import assert from 'node:assert/strict'
import { allocateReportWords } from '../src/utils/portal/reportLength.js'

test('word targets retain chapter identities, prompts and an exact proportional total without mutation', () => {
  const sections = [{ id: 1, words: 1000, prompt: '作者意图' }, { id: 2, words: 2000, description: '参考要求' }, { id: 3, words: 1700 }]
  const original = JSON.stringify(sections)
  const result = allocateReportWords(sections, 7100)
  assert.equal(result.reduce((sum, section) => sum + section.words, 0), 7100)
  assert.equal(result[0].prompt, '作者意图')
  assert.equal(result[1].description, '参考要求')
  assert.deepEqual(result.map(section => section.id), [1, 2, 3])
  assert.equal(JSON.stringify(sections), original)
  assert.ok(Math.abs(result[1].words / result[0].words - 2) < .01)
})
test('allocation respects chapter limits and small or maximum totals', () => {
  for (const target of [3, 4, 500, 12000, 16001, 24000]) {
    const result = allocateReportWords([{ words: 8000 }, { words: 1 }, { words: 100 }], target)
    assert.equal(result.reduce((sum, section) => sum + section.words, 0), target)
    assert.ok(result.every(section => Number.isInteger(section.words) && section.words >= 1 && section.words <= 8000))
  }
})
test('empty outlines and invalid totals cannot rewrite chapter budgets', () => {
  for (const target of [null, 0, 1.5, NaN, -1, 8001]) assert.throws(() => allocateReportWords([{ words: 1000 }], target))
  assert.throws(() => allocateReportWords([], 1000))
})
