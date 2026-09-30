import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const styles = readFileSync(new URL('../src/assets/styles/pipeline.scss', import.meta.url), 'utf8')

test('keeps primary text links out of the filled primary button rule', () => {
  assert.match(styles, /\.pipeline-page \.el-button--primary:not\(\.is-link\):not\(\.is-text\) \{/)
  assert.match(styles, /\.pipeline-page \.el-button\.is-link\.el-button--primary,[\s\S]*?\{[\s\S]*?background: transparent;/)
})
