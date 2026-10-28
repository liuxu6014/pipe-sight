import { requireBusinessId } from './businessId.js'

const clone = value => JSON.parse(JSON.stringify(value || {}))
const terms = values => [...new Set(values.map(value => value.trim()).filter(Boolean))]
export function newScheduleForm() {
  return { name: '', frequency: 'daily', templateId: '', time: '08:00', weekday: 0, monthDay: 1,
    enabled: false, keywords: [], categories: [], sources: ['新闻网站', '微信公众号'],
    holidayPolicy: 'run', holidayDates: [], itemCount: 8, summaryLength: 'normal', hotAnalysis: true,
    duplicateMerge: true, requirements: '', generation: {}, selection: {}, originalTemplateId: '' }
}
export function readScheduleForm(row) {
  const config = clone(row.config), generation = clone(row.generationConfig)
  const options = { ...(config.options || {}), ...(generation.options || {}) }
  return { ...newScheduleForm(), name: row.name, frequency: row.reportType, templateId: String(row.templateId),
    originalTemplateId: String(row.templateId), time: String(row.scheduleTime || '').slice(0, 5),
    weekday: row.scheduleWeekday ?? 0, monthDay: row.scheduleMonthDay ?? 1, enabled: Boolean(row.enabled),
    keywords: config.keywords ?? generation.keywords ?? [], categories: config.category_names ?? options.directions ?? [],
    sources: (config.source_types ?? options.sources ?? ['website', 'wechat']).map(type => ({ website: '新闻网站', news: '新闻网站', wechat: '微信公众号' })[type] || type),
    holidayPolicy: config.holiday_policy ?? options.holidayPolicy ?? 'run',
    holidayDates: config.holiday_dates ?? options.holidayDates ?? [],
    itemCount: options.itemCount ?? 8, summaryLength: options.summaryLength ?? 'normal',
    hotAnalysis: options.hotAnalysis ?? true, duplicateMerge: options.duplicateMerge ?? true,
    requirements: generation.requirements || '', generation, selection: config }
}
export function scheduleSummary(form) {
  const day = form.frequency === 'weekly' ? `每${['周一', '周二', '周三', '周四', '周五', '周六', '周日'][form.weekday]}`
    : form.frequency === 'monthly' ? `每月${form.monthDay}日` : '每天'
  return `${day} ${form.time}（北京时间）`
}
export function schedulePayload(form, template) {
  if (!form.name.trim() || form.name.trim().length > 255) throw new Error('请填写 1 至 255 字的计划名称')
  if (!['daily', 'weekly', 'monthly'].includes(form.frequency)) throw new Error('请选择自动生成频率')
  if (!/^(?:[01]\d|2[0-3]):[0-5]\d$/.test(form.time)) throw new Error('请填写有效的执行时间')
  if (!Number.isInteger(form.weekday) || form.weekday < 0 || form.weekday > 6 || !Number.isInteger(form.monthDay) || form.monthDay < 1 || form.monthDay > 31) throw new Error('请选择有效的生成日期')
  if (!template || String(template.id) !== form.templateId) throw new Error('请选择可用的简报模板')
  if (template.digestCadence !== 'all' && template.digestCadence !== form.frequency) throw new Error('模板与自动计划周期不一致')
  for (const [values, limit, label] of [[form.keywords, 20, '关键词'], [form.categories, 10, '类别']]) {
    if (!Array.isArray(values) || values.length > limit || values.some(term => typeof term !== 'string' || term.length > 200)) throw new Error(`${label}数量或长度超出限制`)
  }
  if (!form.sources.length || form.sources.some(type => !['新闻网站', '微信公众号'].includes(type))) throw new Error('请至少选择一个来源范围')
  if (!Number.isInteger(form.itemCount) || form.itemCount < 3 || form.itemCount > 30) throw new Error('每栏资讯数量须为 3 至 30')
  const keywords = terms(form.keywords), categories = terms(form.categories)
  const selection = { ...clone(form.selection), keywords, category_names: categories,
    source_types: form.sources.map(type => type === '新闻网站' ? 'website' : 'wechat'),
    holiday_policy: form.holidayPolicy, holiday_dates: [...(form.holidayDates || [])] }
  delete selection.options
  const generation = clone(form.generation)
  generation.keywords = keywords
  generation.direction = categories.join('、')
  generation.requirements = form.requirements
  generation.options = { ...generation.options, cadence: form.frequency, sources: [...form.sources], directions: categories,
    summaryLength: form.summaryLength, itemCount: form.itemCount, hotAnalysis: form.hotAnalysis, duplicateMerge: form.duplicateMerge }
  if (!form.originalTemplateId || form.originalTemplateId !== form.templateId) {
    generation.outline = (template.sections || []).map(item => ({ ...item }))
  }
  return { name: form.name.trim(), reportType: form.frequency, templateId: requireBusinessId(form.templateId),
    scheduleTime: form.time, scheduleWeekday: form.weekday, scheduleMonthDay: form.monthDay,
    enabled: form.enabled, timezone: 'Asia/Shanghai', holidayPolicy: form.holidayPolicy,
    holidayDates: [...(form.holidayDates || [])], selectionConfig: selection, generationConfig: generation }
}
