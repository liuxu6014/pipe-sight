import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { computed, ref } from 'vue'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'

const read = file => fs.readFileSync(new URL(`../src/views/portal/${file}`, import.meta.url), 'utf8')

test('desktop navigation collapse restores and persists independently of mobile menu', () => {
  const { descriptor } = parse(read('index.vue'))
  const script = compileScript(descriptor, { id: 'sidebar-shell-test' })
  assert.deepEqual(compileTemplate({ id: 'sidebar-shell-test', source: descriptor.template.content, compilerOptions: { bindingMetadata: script.bindings } }).errors, [])
  let layout
  const storage = new Map([['ps-portal-navigation-collapsed', 'true']])
  const code = script.content.replace(/^import[^\n]*\n/gm, '').replace('export default', 'return')
  const component = new Function('computed', 'ref', 'provide', 'useRoute', 'localStorage', 'PortalHeader', 'PortalTaskPanel', 'PortalSidebar', code)(computed, ref, (key, value) => { layout = value }, () => ({ name: 'PortalPapers' }), { getItem: key => storage.get(key), setItem: (key, value) => storage.set(key, value) }, {}, {}, {})
  component.setup({}, { expose() {} })
  assert.equal(layout.collapsed.value, true)
  layout.toggle()
  assert.equal(layout.collapsed.value, false)
  assert.equal(storage.get('ps-portal-navigation-collapsed'), 'false')
  layout.toggle()
  assert.equal(layout.collapsed.value, true)
})

test('sidebar is desktop-only and keeps accessible names when collapsed', () => {
  const sidebar = read('components/PortalSidebar.vue')
  const header = read('components/PortalHeader.vue')
  assert.match(sidebar, /\.ps-desktop-sidebar \{ display: none; \}/)
  assert.match(sidebar, /@media \(min-width: 1051px\)/)
  assert.match(sidebar, /:aria-label="item.label"/)
  assert.match(sidebar, /:title="collapsed \? item.label/)
  assert.match(sidebar, /event.metaKey \|\| event.ctrlKey/)
  assert.match(header, /:aria-expanded="mobileOpen"/)
  assert.match(header, /class="ps-mobile-nav"/)
  assert.match(header, /@media \(min-width: 1051px\)/)
  assert.doesNotMatch(header, /ps-desktop-nav-toggle|navigationLayout/)
  assert.match(sidebar, /class="ps-sidebar-toggle"/)
  assert.match(sidebar, /href="\/portal\/basket"/)
  assert.match(sidebar, /store.libraryCount/)
  assert.match(sidebar, /isBasketPath\(route.path\)/)
  assert.match(header, /@media \(min-width: 1051px\)\s*\{\s*\.ps-main-nav, \.ps-basket-button \{ display: none; \}/)
})
