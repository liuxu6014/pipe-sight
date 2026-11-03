import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const styles = readFileSync(new URL('../src/assets/styles/pipeline.scss', import.meta.url), 'utf8')

test('management buttons retain the component primary, plain and disabled appearances', () => {
  assert.doesNotMatch(styles, /\.pipeline-page \.el-button--primary[^{}]*\{/)
  assert.doesNotMatch(styles, /\.pipeline-page \.el-button\s*\{[^}]*(?:border-radius|background|box-shadow):/s)
})
