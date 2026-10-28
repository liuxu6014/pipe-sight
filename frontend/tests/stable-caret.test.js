import test from 'node:test'
import assert from 'node:assert/strict'
import { vStableCaret } from '../src/utils/portal/stableCaret.js'

test('selection survives replacement text nodes, including reverse selection across citations', () => {
  const old = { length: 8 }, text = { length: 4 }, citation = { length: 3 }, tail = { length: 1 }
  let nodes = [old], restored
  const selection = { rangeCount: 1, anchorNode: old, anchorOffset: 8, focusNode: old, focusOffset: 2,
    setBaseAndExtent(...args) { restored = args } }
  const document = { getSelection: () => selection,
    createRange() { let offset; return { selectNodeContents() {}, setEnd(node, value) { offset = value }, toString: () => 'x'.repeat(offset) } },
    createTreeWalker() { let index = 0; return { nextNode: () => nodes[index++] } } }
  const element = { ownerDocument: document, isContentEditable: true, contains: node => node === old }
  document.activeElement = element
  vStableCaret.beforeUpdate(element)
  nodes = [text, citation, tail]
  vStableCaret.updated(element)
  assert.deepEqual(restored, [tail, 1, text, 2])
})

test('unfocused editor does not steal the cursor after a save response', () => {
  const element = { ownerDocument: { getSelection: () => ({ rangeCount: 0 }) }, isContentEditable: true }
  vStableCaret.beforeUpdate(element)
  vStableCaret.updated(element)
})
