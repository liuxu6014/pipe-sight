// Business audit timestamps are Beijing wall time, not browser-local instants.
const wallPattern = /^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2})(?::(\d{2})(?:\.\d+)?)?)?$/
const awarePattern = /^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})$/i
const offsetSuffix = /(?:Z|[+-]\d{2}:?\d{2})$/i
const formatter = new Intl.DateTimeFormat('en-CA', {
  timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit',
  hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23'
})

function wallParts(value) {
  const match = value.match(wallPattern)
  if (!match) return null
  const [, year, month, day, hour = '00', minute = '00', second = '00'] = match
  const date = new Date(0)
  date.setUTCFullYear(+year, +month - 1, +day)
  if (date.getUTCFullYear() !== +year || date.getUTCMonth() + 1 !== +month || date.getUTCDate() !== +day || +hour > 23 || +minute > 59 || +second > 59) return null
  return { day: `${year}-${month}-${day}`, time: `${hour}:${minute}:${second}`, hasTime: match[4] !== undefined }
}

export function formatBusinessTime(value) {
  if (value == null || value === '') return ''
  const raw = String(value).trim()
  if (awarePattern.test(raw) || value instanceof Date) {
    if (!(value instanceof Date) && !wallParts(raw.replace(offsetSuffix, ''))) return raw
    const date = value instanceof Date ? value : new Date(raw.replace(' ', 'T'))
    if (!Number.isFinite(date.getTime())) return raw
    const parts = Object.fromEntries(formatter.formatToParts(date).map(part => [part.type, part.value]))
    return `${parts.year}-${parts.month}-${parts.day} ${parts.hour}:${parts.minute}:${parts.second}`
  }
  const parts = wallParts(raw)
  return parts?.hasTime ? `${parts.day} ${parts.time}` : raw
}

export function businessTimeInstant(value) {
  const raw = String(value || '').trim()
  if (awarePattern.test(raw)) return wallParts(raw.replace(offsetSuffix, '')) ? Date.parse(raw.replace(' ', 'T')) : NaN
  const parts = wallParts(raw)
  return parts ? Date.parse(`${parts.day}T${parts.time}+08:00`) : NaN
}

// Walk only response/entity containers. Frozen JSON, prompts and lease/schedule
// instants must retain their original wire representation for later requests.
const containers = new Set(['data', 'rows', 'basket', 'favoriteItems', 'selectedItems', 'images', 'report', 'task', 'run', 'source', 'template'])
const auditFields = new Set(['created_at', 'updated_at', 'createdAt', 'updatedAt'])
export function normalizeBusinessTimes(value) {
  if (Array.isArray(value)) return value.map(normalizeBusinessTimes)
  if (!value || Object.prototype.toString.call(value) !== '[object Object]') return value
  const result = { ...value }
  for (const [key, entry] of Object.entries(value)) {
    if (auditFields.has(key)) result[key] = formatBusinessTime(entry)
    else if (containers.has(key)) result[key] = normalizeBusinessTimes(entry)
  }
  return result
}

// Date-picker Date objects represent a chosen local calendar day, not an
// instant to convert to UTC. Publication years/months must never be padded.
export function calendarDate(value) {
  if (value instanceof Date) {
    if (!Number.isFinite(value.getTime())) return ''
    return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, '0')}-${String(value.getDate()).padStart(2, '0')}`
  }
  const raw = String(value || '').trim()
  if (awarePattern.test(raw) && !Number.isFinite(businessTimeInstant(raw))) return ''
  const parts = wallParts(awarePattern.test(raw) ? formatBusinessTime(raw) : raw)
  return parts?.day || ''
}

export function parseCalendarDate(value) {
  const day = calendarDate(value)
  if (!day) return null
  const [year, month, date] = day.split('-').map(Number)
  const result = new Date(0)
  result.setFullYear(year, month - 1, date)
  result.setHours(0, 0, 0, 0)
  return result
}
