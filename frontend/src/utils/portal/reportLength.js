// Allocate the total across chapters without changing their content or prompts.
export function allocateReportWords(sections, target) {
  const count = sections.length
  if (!count || !Number.isInteger(target) || target < count || target > count * 8000) {
    throw new Error(`总字数须为 ${count || 1} 至 ${count * 8000 || 8000} 的整数`)
  }
  const words = Array(count).fill(1)
  const weights = sections.map(section => Number.isFinite(Number(section.words)) ? Math.max(1, Math.min(8000, Number(section.words))) : 1)
  let remaining = target - count
  let active = sections.map((_, index) => index)
  while (active.length) {
    const weight = active.reduce((sum, index) => sum + weights[index], 0)
    const capped = active.filter(index => remaining * weights[index] / weight >= 7999)
    if (capped.length) {
      for (const index of capped) { words[index] = 8000; remaining -= 7999 }
      active = active.filter(index => !capped.includes(index))
      continue
    }
    const shares = active.map(index => ({ index, exact: remaining * weights[index] / weight }))
    let extra = remaining
    for (const { index, exact } of shares) { words[index] += Math.floor(exact); extra -= Math.floor(exact) }
    shares.sort((a, b) => (b.exact % 1) - (a.exact % 1) || a.index - b.index)
    for (let index = 0; index < extra; index++) words[shares[index].index]++
    break
  }
  return sections.map((section, index) => ({ ...section, words: words[index] }))
}
