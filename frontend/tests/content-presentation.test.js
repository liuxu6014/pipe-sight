import test from 'node:test'
import assert from 'node:assert/strict'
import { entityGroups, contentCategory, collectionTime, readingContent, insightSections, paperInsightParagraph } from '../src/utils/portal/contentPresentation.js'

test('six entity groups use only stored evidence and normalize aliases without duplicates', () => {
  const groups = entityGroups([{ type: '人', name: ' 李某 ' }, { type: 'person', name: '李某' }, { type: '机构', name: '某研究院' }, { type: '未知', name: '不可展示' }, { type: '技术', name: {} }])
  assert.deepEqual(groups.map(group => group.label), ['地点', '时间', '政策', '人物', '机构', '技术'])
  assert.deepEqual(groups[3].values, ['李某'])
  assert.deepEqual(groups[4].values, ['某研究院'])
  assert.deepEqual(entityGroups(null).flatMap(group => group.values), [])
})

test('category names are not invented from keywords or resource types', () => {
  assert.equal(contentCategory({ category: 'paper', tags: ['检测'] }), '')
  assert.equal(contentCategory({ category_name: '质能网' }), '质能网')
  assert.equal(contentCategory({ categoryName: '碳氢醇氨储运' }), '碳氢醇氨储运')
  assert.equal(contentCategory({ category: '123' }), '')
})

test('collection time never silently falls back to publication time', () => {
  assert.equal(collectionTime({ published_at: '2026-11-02 10:00:00' }), '')
  assert.equal(collectionTime({ collectedAt: '2026-11-02T02:00:00Z' }), '2026-11-02 10:00:00')
})

test('original and saved Chinese text remain separate and summary is not full text', () => {
  assert.deepEqual(readingContent({ summary: '短摘要', content_original: 'Original body', content_zh: '中文正文' }), { original: ['Original body'], translated: ['中文正文'], hasTranslation: true })
  assert.deepEqual(readingContent({ summary: '只有摘要' }).original, [])
})

test('AI interpretation has four fixed questions and missing evidence stays empty', () => {
  const sections = insightSections({ ai_insight: { institution: '某研究院', research: '研究检测方法', effect: '摘要未给出量化效果', scenario: '管道检测' } }, 'paper')
  assert.equal(sections.length, 4)
  assert.equal(sections[0].content, '某研究院')
  assert.equal(sections[3].content, '管道检测')
  assert.ok(insightSections({}, 'paper').every(section => section.content === ''))
  assert.ok(insightSections({ summary: '只有摘要，不是 AI 解读' }, 'paper').every(section => section.content === ''))
  assert.equal(insightSections({}, 'news').length, 6)
})

test('paper interpretation reads as one paragraph while preserving stored evidence and limitations', () => {
  assert.equal(paperInsightParagraph({ ai_insight: '研究团队综述了导波检测方法。\n\n摘要未报告量化效果。' }), '研究团队综述了导波检测方法。 摘要未报告量化效果。')
  assert.equal(paperInsightParagraph({ ai_insight: {
    institution: '某研究院', research: '研究管道检测方法',
    effect: '效果尚待验证。', scenario: '适用于管道检测',
    limitations: '不能据此推断现场效果。'
  } }), '某研究院； 研究管道检测方法； 效果尚待验证。 适用于管道检测； 不能据此推断现场效果。')
  assert.equal(paperInsightParagraph({ ai_insight: { research: '仅做综述。', summary: '仅做综述。' } }), '仅做综述。')
  assert.equal(paperInsightParagraph({ title: '检测论文', abstract: '原始摘要', summary: '导读摘要' }), '')
})
