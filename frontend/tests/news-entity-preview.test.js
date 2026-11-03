import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import { computed, reactive } from 'vue'
import { Location, Clock, Document, User, OfficeBuilding, Cpu } from '@element-plus/icons-vue'
import { entityGroups } from '../src/utils/portal/contentPresentation.js'

test('core entity display uses populated types only and preserves the saved selection without quotas', () => {
  const props = reactive({ compact: true, entities: [{ type: '机构', name: '研究中心' }, { type: '技术', name: '超声检测' }] })
  const source = readFileSync(new URL('../src/views/portal/components/ContentEntities.vue', import.meta.url), 'utf8')
    .split('<script setup>')[1].split('</script>')[0].replace(/^import .*\n/gm, '')
  const context = vm.createContext({ computed, entityGroups, Location, Clock, Document, User, OfficeBuilding, Cpu, defineProps: () => props })
  vm.runInContext(`${source}\nglobalThis.view = { visibleGroups, hasEntities }`, context)
  const view = context.view
  assert.deepEqual(Array.from(view.visibleGroups.value, group => group.label), ['机构', '技术'])
  assert.equal(view.visibleGroups.value.reduce((n, group) => n + group.values.length, 0), 2)
  props.compact = false
  assert.equal(view.visibleGroups.value.length, 2)
  props.entities = []
  assert.equal(view.hasEntities.value, false)
  assert.equal(view.visibleGroups.value.length, 0)
})
