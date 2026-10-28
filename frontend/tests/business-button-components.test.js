import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { parse } from '@vue/compiler-sfc'
import { baseParse } from '@vue/compiler-dom'

const root = fileURLToPath(new URL('../src/views/', import.meta.url))
function files(dir) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap(entry => entry.isDirectory()
    ? files(path.join(dir, entry.name)) : entry.name.endsWith('.vue') ? [path.join(dir, entry.name)] : [])
}
test('business operation buttons use bordered UI components without text/link variants', () => {
  for (const file of [...files(path.join(root, 'portal')), ...files(path.join(root, 'pipeline'))]) {
    const { descriptor, errors } = parse(fs.readFileSync(file, 'utf8'))
    assert.equal(errors.length, 0, file)
    if (!descriptor.template) continue
    const visit = node => {
      if (node.type === 1 && node.tag === 'el-button') {
        assert.ok(!node.props.some(prop => prop.type === 6 && ['text', 'link'].includes(prop.name)), file)
      }
      for (const child of node.children || []) visit(child)
    }
    visit(baseParse(descriptor.template.content))
  }
})
test('shared action spacing wraps table operations and preserves component borders', () => {
  const styles = fs.readFileSync(new URL('../src/assets/styles/workspace.scss', import.meta.url), 'utf8')
  assert.match(styles, /\.el-button\.ps-ui-action\s*\{[^}]*border: 1px solid var\(--el-button-border-color\)/s)
  assert.match(styles, /\.cell:has\(> \.el-button\)\s*\{[^}]*flex-wrap: wrap[^}]*gap: 8px/s)
})
