import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse } from '@vue/compiler-sfc'
const source = readFileSync(new URL('../src/views/portal/pages/ResearchCreateView.vue', import.meta.url), 'utf8')
const styles = readFileSync(new URL('../src/assets/styles/workspace.scss', import.meta.url), 'utf8')
test('research wizard fills the viewport with independent content and material scrolling', () => {
  assert.match(styles, /\.ps-portal-main:has\(> \.ps-research-create-page\) \{[\s\S]*?height: 100dvh/)
  assert.match(styles, /display: flex; flex-direction: column; flex: 1 1 0; min-width: 0; min-height: 0; gap: 12px/)
  assert.match(styles, /> \.ps-step-card \{ display: flex; flex-direction: column; flex: 1 1 0; min-width: 0; min-height: 0/)
  assert.match(styles, /\.ps-step-content \{ flex: 1 1 0; min-height: 0; min-width: 0; overflow-y: auto/)
  assert.match(styles, /\.ps-material-picker, \.ps-material-source \{ flex: 1 1 0; min-height: 0/)
  assert.match(styles, /\.ps-research-material-scroll \{ flex: 1 1 0; min-height: 0; overflow-y: auto/)
})
test('steps, material pagination and action footer remain outside scrollable contents', () => {
  const { descriptor } = parse(source)
  const has = (node, name) => node.props?.find(p => p.name === 'class')?.value?.content.split(' ').includes(name)
  function walk(node, inside = false) {
    if (has(node, 'ps-create-steps') || has(node, 'ps-step-footer') || has(node, 'ps-material-pagination')) assert.equal(inside, false)
    for (const child of node.children || []) walk(child, inside || has(node, 'ps-step-content'))
  }
  walk(descriptor.template.ast)
  assert.match(styles, /\.ps-material-pagination, \.ps-step-footer \{ flex-shrink: 0/)
  assert.match(styles, /\.ps-outline-row > \.el-input-number \{ grid-column: 2; width: min\(100%, 180px\)/)
  assert.match(styles, /\.ps-create-steps \.el-step__icon \{ width: 22px; height: 22px/)
})
