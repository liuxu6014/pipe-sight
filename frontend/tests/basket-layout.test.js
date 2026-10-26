import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { compile, createSSRApp, h } from 'vue'
import { renderToString } from '@vue/server-renderer'
import { parse } from '@vue/compiler-sfc'
import { basketItemLabel, basketItemPath } from '../src/utils/portal/basketItems.js'

const source = fs.readFileSync(new URL('../src/views/portal/pages/MyWorkspaceView.vue', import.meta.url), 'utf8')
const template = parse(source).descriptor.template.content
async function renderBasket(items, visible = items) {
  const Stub = { setup: (_, { slots }) => () => h('div', slots.default?.()) }
  const app = createSSRApp({
    setup: () => ({ mode: 'basket', keyword: '', statusFilter: '', visibleItems: visible, pagedItems: visible.slice(0, 10), currentPage: 1, pageSize: 10, sectionError: '', pageConfig: { title: '资料篮' },
      portalStore: { basketCount: items.length, dataLoaded: true, dataLoading: false },
      basketSelection: { selectedItems: { value: [] }, selectedIds: { value: [] }, allVisible: { value: false }, indeterminate: { value: false }, toggleVisible() {}, toggle() {} },
      basketParsing: { label: () => '', error: { value: '' }, retrying: { value: [] } },
      UploadFilled: Stub, uploadMaterial() {}, uploadVisible: false, uploading: false, uploadError: '', basketItemLabel, itemPath: basketItemPath, basketIcon: () => 'span',
      createFromSelection() {}, emptyAction() {} }),
    render: compile(template)
  })
  for (const name of ['RouterLink', 'ElInput', 'ElSelect', 'ElOption', 'ElButton', 'ElSkeleton', 'ElProgress', 'ElCheckbox', 'ElPagination', 'ElDialog', 'UploadFilled', 'PortalEmptyState', 'ArrowRight']) app.component(name, Stub)
  return renderToString(app)
}

test('empty basket retains upload entry without selection controls', async () => {
  const html = await renderBasket([])
  assert.match(html, /暂无资料/)
  assert.match(html, /上传资料/)
  assert.match(html, /搜索资料篮/)
  assert.doesNotMatch(html, /浏览资讯|全选当前结果|本次编制选材/)
  assert.equal((html.match(/ps-basket-panel/g) || []).length, 1)
})

test('populated and filtered baskets keep toolbar and selection within the same panel', async () => {
  const items = [{ id: 'a', title: '资料 A', type: '资讯' }, { id: 'b', title: '资料 B', type: '论文' }]
  const html = await renderBasket(items)
  assert.match(html, /搜索资料篮/)
  assert.match(html, /新建报告/)
  assert.match(html, /全选当前结果/)
  assert.match(html, /资料 A/)
  assert.match(html, /资料 B/)
  assert.doesNotMatch(html, /暂无资料|浏览资讯/)
  const filtered = await renderBasket(items, [])
  assert.match(filtered, /没有匹配资料/)
  assert.match(filtered, /清除筛选/)
  assert.doesNotMatch(filtered, /浏览资讯/)
})

test('basket keeps pagination inside the list panel and renders readable source labels', async () => {
  const html = (await renderBasket([{ id: '26', title: '论文 A', type: 'paper' }, { id: '18', title: '新闻 B', type: 'article' }])).replace(/<!--[\s\S]*?-->/g, '')
  assert.match(html, /ps-basket-pagination/)
  assert.match(html, /<small>论文<\/small>/)
  assert.match(html, /<small>新闻资讯<\/small>/)
  assert.doesNotMatch(html, /<small>paper<\/small>|<small>article<\/small>/)
  assert.equal((html.match(/aria-label="资料列表分页"/g) || []).length, 1)
  assert.ok(html.indexOf('ps-basket-pagination') < html.indexOf('</section>'))
})
