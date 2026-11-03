import { sourceEnabled } from './compactContract.js'
import { canCreateSourceType } from './sourceAdapters.js'

// Cron steps restart at field boundaries. Only offer intervals that divide
// those boundaries evenly, never a misleading "every 7 hours" or "every 2 days".
export const sourceIntervalChoices = {
  minute: [1, 2, 3, 4, 5, 6, 10, 12, 15, 20, 30],
  hour: [1, 2, 3, 4, 6, 8, 12],
  day: [1],
  week: [1]
}

export function sourceCron(source = {}) {
  return source.cron ?? source.scheduleCron ?? source.schedule_cron ?? null
}

export function sourceFrequency(cron) {
  const value = (cron || '').trim().replace(/\s+/g, ' ')
  if (!value) return { unit: 'off', amount: 1 }
  if (value === '0 0 * * *') return { unit: 'day', amount: 1 }
  // APScheduler's weekday numbering starts on Monday (0).
  if (value === '0 0 * * 0' || value === '0 0 * * mon') return { unit: 'week', amount: 1 }
  const minute = value.match(/^(\*|\*\/(\d+)) \* \* \* \*$/)
  const hour = value.match(/^0 (\*|\*\/(\d+)) \* \* \*$/)
  const unit = minute ? 'minute' : 'hour'
  const match = minute || hour
  const amount = match ? Number(match[2] || 1) : 0
  if (sourceIntervalChoices[unit].includes(amount)) return { unit, amount }
  return { unit: 'preserve', amount: 1 }
}

export function sourceIntervalCron({ unit, amount }, originalCron = null) {
  if (unit === 'preserve') return originalCron
  if (unit === 'off') return null
  if (!sourceIntervalChoices[unit]?.includes(amount)) throw new Error('请选择可用的采集间隔')
  if (unit === 'minute') return amount === 1 ? '* * * * *' : `*/${amount} * * * *`
  if (unit === 'hour') return amount === 1 ? '0 * * * *' : `0 */${amount} * * *`
  if (unit === 'day') return '0 0 * * *'
  return '0 0 * * mon'
}

export function sourceFrequencyText(cron) {
  const frequency = sourceFrequency(cron)
  if (frequency.unit === 'off') return '未设置定时采集'
  if (frequency.unit === 'day') return '每天 00:00'
  if (frequency.unit === 'week') return '每周一 00:00'
  if (frequency.unit === 'preserve') {
    const daily = (cron || '').trim().match(/^(\d{1,2}) (\d{1,2}) \* \* \*$/)
    if (daily && Number(daily[1]) < 60 && Number(daily[2]) < 24) {
      return `每天 ${daily[2].padStart(2, '0')}:${daily[1].padStart(2, '0')}`
    }
    return '已有指定时间计划'
  }
  return `每 ${frequency.amount} ${frequency.unit === 'minute' ? '分钟' : '小时'}`
}

// PUT requires a full DTO: frequency/status actions must preserve other fields.
export function existingSourcePayload(source, changes = {}) {
  if (Object.keys(changes).some(key => !['cron', 'isEnabled'].includes(key))) throw new Error('仅允许修改频率或启停状态')
  return {
    name: source.name,
    type: (source.type || source.sourceType) === 'news' ? 'website' : (source.type || source.sourceType),
    url: source.url ?? source.endpoint ?? null,
    adapter: source.adapter ?? source.adapterKey ?? source.adapter_key,
    cron: sourceCron(source),
    timezone: source.timezone || 'Asia/Shanghai',
    config: source.config || {},
    modelId: source.modelId ?? source.model_id ?? null,
    isEnabled: sourceEnabled(source),
    ...changes
  }
}

export function newWechatSourcePayload(form, frequency) {
  if (!canCreateSourceType(form.sourceType)) throw new Error('仅支持新增公众号，新闻和论文来源由 Excel 白名单管理')
  const { name, feedUrl } = validateWechatSourceForm(form)
  if (frequency.unit === 'preserve') throw new Error('请选择公众号采集频率')
  return {
    name, type: 'wechat', url: null, adapter: 'wechat_rss',
    cron: sourceIntervalCron(frequency), timezone: 'Asia/Shanghai',
    config: { feed_url: feedUrl, limit: 12 }, modelId: null, isEnabled: true
  }
}

function validateWechatSourceForm(form) {
  const name = (form.name || '').trim()
  const feedUrl = (form.feedUrl || '').trim()
  if (!name || name.length > 255) throw new Error('请填写 255 字以内的公众号名称')
  try {
    const url = new URL(feedUrl)
    if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password) throw new Error()
  } catch {
    throw new Error('请填写有效的公众号 RSS 链接（http 或 https）')
  }
  return { name, feedUrl }
}

export function editedWechatSourcePayload(source, form, frequency) {
  if ((source.type || source.sourceType) !== 'wechat') throw new Error('论文和新闻网站仅支持启停')
  const { name, feedUrl } = validateWechatSourceForm(form)
  return {
    ...existingSourcePayload(source, { cron: sourceIntervalCron(frequency, sourceCron(source)) }),
    name,
    config: { ...source.config, feed_url: feedUrl }
  }
}
