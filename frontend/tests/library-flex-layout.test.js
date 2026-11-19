import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const styles = readFileSync(new URL('../src/assets/styles/workspace.scss', import.meta.url), 'utf8')
const page = readFileSync(new URL('../src/views/portal/pages/KnowledgeView.vue', import.meta.url), 'utf8')

test('unified library fills the viewport and removes the content width cap', () => {
  const shell = styles.match(/\.ps-portal \.ps-portal-main:has\(> \.ps-basket-page\) \{([^}]+)\}/)[1]
  assert.match(shell, /height: 100dvh/)
  assert.match(shell, /box-sizing: border-box/)
  assert.match(shell, /overflow: hidden/)
  const body = styles.match(/\.ps-portal \.ps-workspace-surface > \.ps-basket-page \{([^}]+)\}/)[1]
  assert.match(body, /width: 100%/)
  assert.match(body, /max-width: none/)
  assert.match(body, /flex: 1 1 0/)
  assert.match(body, /min-height: 0/)
})

test('list alone grows and scrolls, with usable controls on short and narrow screens', () => {
  assert.match(page, /\.ps-material-list \{ flex: 1 1 0; min-width: 0; min-height: 0; overflow: hidden/)
  assert.match(page, /<el-table[^>]+:max-height="listHeight"/)
  assert.match(page, /\.ps-knowledge-page > \.ps-pagination \{[^}]*flex-shrink: 0/)
  assert.match(styles, /@media \(max-height: 540px\)/)
  assert.match(styles, /\.ps-basket-page > \.ps-material-list \{ min-height: 160px/)
  assert.match(page, /\.ps-row-actions :deep\(\.el-button \+ \.el-button\) \{ margin-left: 0/)
  assert.match(page, /@media \(max-width: 760px\)[\s\S]*?\.ps-knowledge-toolbar > \.el-input \{ flex-basis: 100%/)
})

test('library reserves visible desktop actions and uses full-width touch cards on mobile', () => {
  assert.match(page, /label="操作" width="250" fixed="right"/)
  assert.match(page, /class="ps-library-cards" role="list" aria-label="资料卡片列表"/)
  assert.match(page, /@media \(max-width: 760px\)[\s\S]*?\.ps-library-table \{ display: none/)
  assert.match(page, /\.ps-library-card \.ps-row-actions > \.el-button \{ min-height: 44px/)
})
