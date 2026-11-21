import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import * as Vue from 'vue'
import * as Icons from '@element-plus/icons-vue'
import { renderToString } from '@vue/server-renderer'
import { parse, compileScript } from '@vue/compiler-sfc'
import { compileString } from 'sass-embedded'

const read = path => readFileSync(new URL(path, import.meta.url), 'utf8')

async function renderHeader(basketCount = 12) {
  const { descriptor } = parse(read('../src/views/portal/components/PortalHeader.vue'))
  const compiled = compileScript(descriptor, { id: 'responsive-header', inlineTemplate: true })
  const code = compiled.content
    .replace(/^import \{ (.+) \} from ["']vue["'];?$/gm, (_, names) => `const { ${names.replaceAll(' as ', ': ')} } = Vue`)
    .replace(/^import[^\n]*\n/gm, '')
    .replace('export default', 'return')
  const store = { runningTaskCount: 3, basketCount, libraryCount: 3, dataLoading: false, dataError: '', taskPanelVisible: false, hydrate() {} }
  const route = { path: '/portal/templates', fullPath: '/portal/templates', query: {}, hash: '' }
  const destinations = []
  const router = { options: { history: { state: {} } }, currentRoute: Vue.ref(route), push: path => destinations.push(path) }
  const component = new Function('Vue', 'Icons', 'useRoute', 'useRouter', 'usePortalStore', 'useUserStore', 'portalNavigation', 'PortalUserAvatar', 'SearchView', 'isManagementIdentity', `const { Clock, Collection, Menu, Refresh, Search, Setting, SwitchButton, User } = Icons;\n${code}`)(Vue, Icons, () => route, () => router, () => store, () => ({ id: '7', name: '', nickName: '', roles: [], permissions: [] }), [], Vue.defineComponent(() => () => Vue.h('span', { class: 'test-avatar' })), {}, () => false)
  const buttons = []
  const app = Vue.createSSRApp(component)
  app.component('el-button', Vue.defineComponent({
    inheritAttrs: false,
    props: ['icon', 'circle', 'nativeType', 'autoInsertSpace'],
    setup(props, { attrs, slots }) {
      return () => {
        buttons.push(attrs)
        return Vue.h('button', attrs, slots.default?.())
      }
    }
  }))
  for (const name of ['el-badge', 'el-dropdown', 'el-dropdown-menu', 'el-dropdown-item']) {
    app.component(name, Vue.defineComponent((props, { slots }) => () => Vue.h('div', slots.default?.())))
  }
  app.component('el-dialog', Vue.defineComponent(() => () => null))
  return { html: await renderToString(app), buttons, store, destinations }
}

test('compact header keeps named library and account actions functional without old branding', async () => {
  const { html, buttons, store, destinations } = await renderHeader()
  const library = buttons.find(button => button['aria-label'] === '资料库，12 条资料')
  assert.ok(library)
  library.onClick()
  assert.deepEqual(destinations, ['/portal/basket'])
  assert.ok(buttons.some(button => button['aria-label'] === '用户，账户菜单'))
  assert.ok(buttons.some(button => button['aria-label'] === '打开导航' && button['aria-expanded'] === false))
  assert.doesNotMatch(html, /pipechina|国家管网标识|管网用户/)
  assert.match(html, /科技情报与科研辅助平台/)
})

test('compact library badge bounds long counts while keeping the full accessible count', async () => {
  const { html, buttons } = await renderHeader(1234)
  assert.match(html, /<b>99\+<\/b>/)
  assert.ok(buttons.some(button => button['aria-label'] === '资料库，1234 条资料'))
})

function luminance(hex) {
  const value = hex.replace('#', '')
  const normalized = value.length === 3 ? [...value].map(channel => channel.repeat(2)).join('') : value
  const rgb = normalized.match(/[a-f\d]{2}/gi).map(value => parseInt(value, 16) / 255)
  const linear = rgb.map(value => value <= .04045 ? value / 12.92 : ((value + .055) / 1.055) ** 2.4)
  return linear[0] * .2126 + linear[1] * .7152 + linear[2] * .0722
}

test('template secondary labels and counts have readable contrast on both workspace surfaces', () => {
  const { descriptor } = parse(read('../src/views/pipeline/template/index.vue'))
  const css = compileString(descriptor.styles[0].content).css
  for (const selector of ['.template-metadata dt', '.template-category-count', '.template-result-count']) {
    const rule = css.slice(css.indexOf(`${selector} {`)).split('}')[0]
    const color = rule.match(/color: var\(--ps-muted, (#[a-f\d]{6})\)/i)?.[1]
    assert.ok(color, `${selector} must supply a readable color outside the user shell`)
    for (const surface of ['ffffff', 'f4f6f9']) {
      const ratio = (luminance(surface) + .05) / (luminance(color) + .05)
      assert.ok(ratio >= 4.5, `${selector}: ${ratio.toFixed(2)} on #${surface}`)
    }
  }
  const selectedBackground = css.match(/--el-segmented-item-selected-bg-color: (#[a-f\d]{6})/i)?.[1]
  assert.ok(selectedBackground)
  assert.ok((luminance('ffffff') + .05) / (luminance(selectedBackground) + .05) >= 4.5)
  const successText = css.match(/--el-tag-text-color: (#[a-f\d]{6})/i)?.[1]
  const successBackground = css.match(/--el-tag-bg-color: (#[a-f\d]{6})/i)?.[1]
  assert.ok(successText && successBackground)
  assert.ok((luminance(successBackground) + .05) / (luminance(successText) + .05) >= 4.5)
})
