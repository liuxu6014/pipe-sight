export function digestPeriodLabel(period) {
  if (!Array.isArray(period)) return ''
  const dates = [...new Set(period.slice(0, 2).filter(date => /^\d{4}-\d{2}-\d{2}$/.test(date)))]
  return dates.map((date, index) => {
    const [year, month, day] = date.split('-').map(Number)
    const showYear = index === 0 || date.slice(0, 4) !== dates[0].slice(0, 4)
    return `${showYear ? `${year}年` : ''}${month}月${day}日`
  }).join('到')
}

export function digestMasthead(title, period) {
  if (!Array.isArray(period) || period.length !== 2 || !digestPeriodLabel(period)) return title
  const [start, end] = period
  if (title === `管网科技情报周报 ${start} 至 ${end}`) return '管网科技情报周报'
  const month = /^(\d{4})-(\d{2})-01$/.exec(start)
  if (month && title === `管网科技情报月报 ${month[1]}年${Number(month[2])}月`) return '管网科技情报月报'
  return title
}
