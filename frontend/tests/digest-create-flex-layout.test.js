import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
const styles = readFileSync(new URL('../src/assets/styles/workspace.scss', import.meta.url), 'utf8')
const source = readFileSync(new URL('../src/views/portal/pages/DigestCreateView.vue', import.meta.url), 'utf8')

test('digest creation fills the real viewport with flexible candidates and bounded settings', () => {
  assert.match(styles, /\.ps-portal-main:has\(> \.ps-digest-create-page\) \{[\s\S]*?height: 100dvh/)
  assert.match(styles, /> \.ps-digest-candidates \{ flex: 1 1 0; min-height: 0/)
  assert.match(styles, /\.ps-digest-settings \{ display: flex; flex-direction: column; min-height: 0; max-height: min\(38dvh, 320px\)/)
  assert.match(styles, /\.ps-digest-config-body \{ flex: 1 1 auto; min-height: 0; overflow: auto/)
  assert.match(styles, /\.ps-digest-submit \{ flex-shrink: 0; position: static/)
  assert.match(source, /class="ps-digest-candidate-scroll" tabindex="0" aria-label="简报候选资料滚动区"/)
})
test('small windows can scroll the full form without clipping actions or dates', () => {
  assert.match(styles, /@media \(max-width: 760px\), \(max-height: 640px\)/)
  assert.match(styles, /> \.ps-digest-candidates \{ flex: 1 0 280px; height: 280px/)
  assert.match(styles, /\.ps-digest-settings \{ max-height: none/)
})
