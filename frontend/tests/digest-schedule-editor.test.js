import test from 'node:test'
import assert from 'node:assert/strict'
import { newScheduleForm, readScheduleForm, schedulePayload, scheduleSummary } from '../src/utils/portal/digestScheduleEditor.js'

test('an independent plan needs configuration, never selected articles or a report task', () => {
  const form = { ...newScheduleForm(), name: '检测周报', frequency: 'weekly', templateId: '31', weekday: 4,
    keywords: [' 管道 ', '腐蚀', '管道'], categories: ['检测'], sources: ['新闻网站'], time: '09:15' }
  const payload = schedulePayload(form, { id: '31', digestCadence: 'weekly', sections: [] })
  assert.equal(payload.scheduleWeekday, 4)
  assert.equal(payload.scheduleTime, '09:15')
  assert.deepEqual(payload.selectionConfig.keywords, ['管道', '腐蚀'])
  assert.deepEqual(payload.selectionConfig.category_names, ['检测'])
  assert.deepEqual(payload.selectionConfig.source_types, ['website'])
  assert.equal(payload.selectedItemIds, undefined)
  assert.equal(payload.reportId, undefined)
  assert.equal(payload.enabled, false)
  assert.deepEqual(schedulePayload({ ...form, holidayDates: null }, { id: '31', digestCadence: 'weekly' }).holidayDates, [])
})

test('editing retains generation preferences, filters and name without alias collisions', () => {
  const row = { id: '99', name: '原计划', reportType: 'monthly', templateId: '31', scheduleTime: '11:45:00',
    scheduleMonthDay: 31, enabled: false, config: { keywords: ['原词'], category_names: ['原类别'], source_types: ['wechat'], limit: 12, holiday_policy: 'skip', holiday_dates: ['2026-10-01'] },
    generationConfig: { requirements: '保留要求', outline: [{ title: '自定章节', words: 400 }], options: { summaryLength: 'short', itemCount: 6 } } }
  const form = readScheduleForm(row)
  form.time = '15:15'
  const payload = schedulePayload(form, { id: '31', digestCadence: 'monthly', sections: [{ title: '默认章节' }] })
  assert.equal(payload.name, '原计划')
  assert.equal(payload.scheduleMonthDay, 31)
  assert.equal(payload.selectionConfig.limit, 12)
  assert.equal(payload.generationConfig.outline, undefined)
  assert.equal(payload.templateId, '31')
  assert.equal(payload.generationConfig.requirements, '保留要求')
  assert.deepEqual(payload.selectionConfig.source_types, ['wechat'])
  assert.equal(payload.selectionConfig.options, undefined)
  assert.equal(payload.holidayPolicy, 'skip')
  assert.match(scheduleSummary(form), /31.*15:15/)
})

test('bad time, missing source and retired daily cadence are rejected before save', () => {
  const form = { ...newScheduleForm(), name: '计划', templateId: '31' }
  const template = { id: '31', digestCadence: 'weekly' }
  for (const delta of [{ time: '24:01' }, { sources: [] }, { name: ' ' }, { keywords: Array(21).fill('词') }]) {
    assert.throws(() => schedulePayload({ ...form, ...delta }, template))
  }
  assert.throws(() => schedulePayload({ ...form, frequency: 'daily' }), /仅支持周报或月报/)
  assert.doesNotThrow(() => schedulePayload(form))
})

 test('fixed-format plans remove legacy template identifiers and overrides while preserving preferences', () => {
  const form = readScheduleForm({ name: '旧计划', reportType: 'weekly', templateId: '31', scheduleTime: '08:00',
    generationConfig: { outline: [{ title: '不应沿用' }], template_prompt: '旧提示词', templateId: '31', requirements: '聚焦检测进展', options: { hotAnalysis: false } } })
  const payload = schedulePayload(form)
  for (const key of ['outline', 'template_prompt', 'templateId']) assert.equal(payload.generationConfig[key], undefined)
  assert.equal(payload.generationConfig.requirements, '聚焦检测进展')
  assert.equal(payload.generationConfig.options.hotAnalysis, false)
})
