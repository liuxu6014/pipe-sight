export function screeningRulesError(categories) {
  if (!Array.isArray(categories)) return '筛选类别格式无效'
  if (categories.length > 30) return '最多可设置 30 个类别'

  const names = new Set()
  let total = 0
  for (const [index, row] of categories.entries()) {
    const name = typeof row?.name === 'string' ? row.name.trim() : ''
    const prompt = typeof row?.prompt === 'string' ? row.prompt.trim() : ''
    const label = `第 ${index + 1} 个类别`
    if (!name) return `请填写${label}的名称`
    if ([...name].length > 80) return `${label}的名称最多 80 字`
    if (/[\r\n<>`]|\[[^\]]*\]|\*\*|^#/.test(name)) return `${label}的名称须为单行纯文本`
    if (names.has(name.toLowerCase())) return `类别名称“${name}”重复`
    names.add(name.toLowerCase())
    if (!prompt) return `请填写“${name}”的筛选提示词`
    const length = [...prompt].length
    if (length > 2000) return `“${name}”的筛选提示词最多 2,000 字`
    total += length
  }
  return total > 20000 ? '类别筛选提示词合计最多 20,000 字' : ''
}

export function buildDigestScreeningPrompt(general, categories) {
  const common = (general || '').trim()
  if (!categories.length) return common
  const rules = categories.map(({ name, prompt }, index) => `${index + 1}. ${name.trim()}\n${prompt.trim()}`)
  return [
    common && `通用要求\n${common}`,
    `分类规则\n${rules.join('\n\n')}`,
    '逐篇判断。符合多个类别时选最符合的一个，匹配程度相同则取靠前的类别。没有匹配类别的文章排除。'
  ].filter(Boolean).join('\n\n')
}
