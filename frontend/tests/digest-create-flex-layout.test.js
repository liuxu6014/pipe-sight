import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
const styles = readFileSync(new URL('../src/assets/styles/workspace.scss', import.meta.url), 'utf8')
const source = readFileSync(new URL('../src/views/portal/pages/DigestCreateView.vue', import.meta.url), 'utf8')

test('digest uses the shared wizard viewport and keeps confirmation settings scrollable', () => {
  assert.match(styles, /:has\(> :is\(\.ps-research-create-page, \.ps-digest-create-page\)\)[\s\S]*?height: 100dvh/)
  assert.match(styles, /\.ps-step-content \{ flex: 1 1 0; min-height: 0; min-width: 0; overflow-y: auto/)
  assert.match(source, /class="ps-step-content ps-digest-confirm"[\s\S]*?tabindex="0"/)
})

test('small windows can scroll the full wizard with a constrained calendar', () => {
  assert.match(source, /\(max-width: 760px\), \(max-height: 640px\)/)
  assert.match(source, /\.ps-step-card \{ flex: 0 0 auto;/)
  assert.match(source, /width: min\(350px, calc\(100vw - 24px\)\)/)
})
