import test from 'node:test'
import assert from 'node:assert/strict'
import { vEditableText } from '../src/utils/portal/stableCaret.js'

test('native edits do not rebuild editable DOM while external changes still render as safe text', () => {
  let writes = 0, text = ''
  const element = {
    get innerText() { return text },
    set textContent(value) { writes++; text = value },
  }
  vEditableText.mounted(element, { value: '原始正文[1]。' })
  text = '原始正文[1]。\n\n新增一句。'
  vEditableText.beforeUpdate(element, { oldValue: '原始正文[1]。', value: text })
  assert.equal(writes, 1, 'input-owned DOM and its selection must remain untouched')
  vEditableText.beforeUpdate(element, { oldValue: text, value: '<script>外部改写</script>' })
  assert.equal(writes, 2)
  assert.equal(text, '<script>外部改写</script>', 'external content uses textContent, never HTML')
})
