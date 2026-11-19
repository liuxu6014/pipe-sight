import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'
import { sortResearchReports } from '../src/views/portal/utils/reportList.js'

test('research reports use a full-width Element Plus table with actions and an independent pager', () => {
  const source = readFileSync(new URL('../src/views/portal/pages/ResearchWorkbenchView.vue', import.meta.url), 'utf8')
  const { descriptor } = parse(source)
  const script = compileScript(descriptor, { id: 'research-table' })
  const compiled = compileTemplate({ source: descriptor.template.content, filename: 'ResearchWorkbenchView.vue', id: 'research-table', compilerOptions: { bindingMetadata: script.bindings } })
  assert.deepEqual(compiled.errors, [])
  assert.match(source, /<el-table :data="pagedReports" row-key="key" :max-height="listHeight" style="width: 100%"/)
  for (const label of ['报告名称', '状态', '更新时间', '操作']) assert.match(source, new RegExp(`<el-table-column[^>]*label="${label}"`))
  assert.match(source, /show-overflow-tooltip/)
  assert.match(source, /reportRowActions\(report\)/)
  assert.match(source, /<\/el-table>[\s\S]*?<el-pagination/)
  assert.doesNotMatch(source, /<article v-for="report|ps-report-list-row/)
})

test('portal spacing is compact without changing management, reading typography or paper canvas sizing', () => {
  const styles = readFileSync(new URL('../src/assets/styles/workspace.scss', import.meta.url), 'utf8')
  assert.match(styles, /\.ps-portal \.ps-workspace-surface > \.ps-page \{[^}]*padding-block: var\(--ws-page-space\) 12px;/)
  assert.match(styles, /\.ps-management-shell \.ps-workspace-surface[^}]*padding: 12px 16px;/)
  assert.match(styles, /\.ps-page-header \{ min-height: 44px; margin-bottom: 12px;/)
  assert.match(styles, /\.ps-report-main > \.ps-empty-state \{[^}]*min-height: 180px;/)
  assert.match(styles, /\.ps-digest-list \{ margin-top: 12px; min-height: 0;/)
  assert.match(styles, /\.ps-report-main \{ min-height: 0;/)
  assert.match(styles, /\.ps-editor-page \{ height: calc\(100dvh - 70px\)/)
})

test('research creation shrinks to content while keeping long steps scrollable', () => {
  const styles = readFileSync(new URL('../src/assets/styles/workspace.scss', import.meta.url), 'utf8')
  assert.match(styles, /\.ps-research-create-page \{ height: auto; max-height: calc\(100dvh - 70px\); padding-bottom: 12px;/)
  assert.match(styles, /\.ps-research-create-page \.ps-step-footer \{ display: flex; gap: 12px; min-height: 56px; padding: 6px 20px;/)
  assert.match(styles, /\.ps-research-create-page \.ps-step-card \{ flex: 0 1 auto;/)
  assert.match(styles, /\.ps-research-create-page \.ps-step-content \{ flex: 0 1 auto; min-height: 0; overflow-y: auto;/)
  assert.match(styles, /\.ps-research-create-page \.ps-step-content \{ min-height: 0; padding: 16px 20px;/)
})

test('digest goes from configuration to confirmation with automatic screening', () => {
  const source = readFileSync(new URL('../src/views/portal/pages/DigestCreateView.vue', import.meta.url), 'utf8')
  const { descriptor } = parse(source)
  assert.deepEqual([...descriptor.template.content.matchAll(/<el-step title="([^"]+)"/g)].map(match => match[1]), ['简报配置', '确认生成'])
  assert.match(source, /@click="confirmGeneration"/)
  assert.match(source, /<DigestScreeningRules v-model:categories="screeningCategories" v-model:prompt="screeningPrompt"/)
  assert.doesNotMatch(source, /toggleCandidate|全选当前页|selectedCandidateIds/)
  assert.match(source, /id="digest-generation-settings"/)
  assert.match(source, /@click="createDigest">提交生成任务/)
  assert.match(source, /:disabled="!canGenerate"/)
})

test('digest confirmation shows automatic progress and settings with no material selection step', () => {
  const source = readFileSync(new URL('../src/views/portal/pages/DigestCreateView.vue', import.meta.url), 'utf8')
  const { descriptor } = parse(source)
  assert.match(descriptor.template.content, /class="ps-step-content ps-digest-confirm"/)
  assert.match(source, /系统正在按提示词自动筛选、分类并打标签/)
  assert.match(source, /screeningProcessed \* 100 \/ screeningTotal/)
  assert.match(source, /label="分类结果"/)
  assert.doesNotMatch(source, /<el-step[^>]*title="筛选结果"|资料复筛结果|candidateItems|resultView|el-pagination/)
})

test('research material tools and tabs stay outside the scrolling rows', () => {
  const source = readFileSync(new URL('../src/views/portal/pages/ResearchCreateView.vue', import.meta.url), 'utf8')
  const { descriptor } = parse(source)
  const hasClass = (node, name) => node.props?.some(prop => prop.name === 'class' && prop.value?.content.split(' ').includes(name))
  const find = (node, predicate) => predicate(node) ? node : (node.children || []).map(child => find(child, predicate)).find(Boolean)
  const materialSource = find(descriptor.template.ast, node => hasClass(node, 'ps-material-source'))
  const rows = materialSource.children.find(node => hasClass(node, 'ps-research-material-scroll'))
  assert.ok(rows)
  assert.ok(materialSource.children.find(node => hasClass(node, 'ps-research-material-toolbar')))
  assert.ok(materialSource.children.find(node => hasClass(node, 'ps-tabs-line')))
  assert.equal(find(rows, node => hasClass(node, 'ps-research-material-toolbar')), undefined)
  assert.equal(find(rows, node => hasClass(node, 'ps-tabs-line')), undefined)
  assert.match(descriptor.styles[0].content, /\.ps-material-step \{[^}]*overflow: hidden;/)
  assert.match(descriptor.styles[0].content, /\.ps-research-material-scroll \{[^}]*min-height: 0; overflow-y: auto;/)
})

test('report sorting is deterministic, keeps missing dates last, and never mutates shared rows', () => {
  const rows = [{ id: 'a', title: 'A', updatedAt: '2026-10-10' }, { id: 'b', title: 'B', updatedAt: '2026-10-14' }, { id: 'c', title: 'C', updatedAt: '未知' }]
  assert.deepEqual(sortResearchReports(rows).map(item => item.id), ['b', 'a', 'c'])
  assert.deepEqual(sortResearchReports(rows, 'updated-asc').map(item => item.id), ['a', 'b', 'c'])
  assert.deepEqual(sortResearchReports(rows, 'title').map(item => item.id), ['a', 'b', 'c'])
  assert.deepEqual(sortResearchReports(rows, 'title-desc').map(item => item.id), ['c', 'b', 'a'])
  assert.deepEqual(rows.map(item => item.id), ['a', 'b', 'c'])
  assert.deepEqual(sortResearchReports([]), [])
})

test('research workspace and shared empty state compile with explicit accessible actions', () => {
  for (const filename of ['pages/ResearchWorkbenchView.vue', 'pages/ResearchCreateView.vue', 'pages/DigestCreateView.vue', 'components/PortalEmptyState.vue']) {
    const source = readFileSync(new URL(`../src/views/portal/${filename}`, import.meta.url), 'utf8')
    const { descriptor, errors } = parse(source)
    assert.deepEqual(errors, [])
    const script = compileScript(descriptor, { id: filename })
    const template = compileTemplate({ source: descriptor.template.content, filename, id: filename, compilerOptions: { bindingMetadata: script.bindings } })
    assert.deepEqual(template.errors, [])
  }
})

test('research creation keeps a compact icon return and groups cancel with next on the right', () => {
  const source = readFileSync(new URL('../src/views/portal/pages/ResearchCreateView.vue', import.meta.url), 'utf8')
  const { descriptor } = parse(source)
  assert.doesNotMatch(descriptor.template.content, /模板版本|v-model="form.version"|<span>科研工作台<\/span>/)
  assert.doesNotMatch(descriptor.template.content, /ps-evidence-status|带入资料的授权核验|重新核验全部选材/)
  assert.doesNotMatch(descriptor.template.content, /管理研究资料|选中后请求授权详情|ps-research-material-link/)
  assert.doesNotMatch(descriptor.template.content, /ps-step-title/)
  assert.doesNotMatch(descriptor.template.content, /ps-create-progress/)
  assert.doesNotMatch(source, /ps-step-note|stepHint|下一步：/)
  assert.equal((descriptor.template.content.match(/<el-step title=/g) || []).length, 4)
  assert.doesNotMatch(descriptor.template.content, /<el-step\b[^>]*description=/)
  assert.match(descriptor.template.content, /@change="uploadResearchMaterial"/)
  assert.doesNotMatch(descriptor.template.content, /ps-selected-basket|待核验|已核验|重试核验/)
  assert.doesNotMatch(descriptor.template.content, /<el-button[^>]*@click="uploadDialogVisible = true"/)
  assert.match(descriptor.styles[0].content, /\.ps-material-picker \{ grid-template-columns: minmax\(0, 1fr\)/)
  assert.match(descriptor.template.content, /<el-dialog v-model="uploadDialogVisible" title="上传资料"/)
  assert.match(descriptor.template.content, /aria-label="研究资料列表分页"/)
  assert.match(descriptor.template.content, /@click="selectCurrentMaterialPage">\{\{ currentMaterialPageSelected \? '取消当前页选择' : '全选当前页'/)
  assert.match(descriptor.template.content, /:page-sizes="\[10, 20, 50\]"/)
  assert.match(source, /searchPipelineResearchMaterials\(\{[\s\S]*?pageNum: materialPage.value/)
  assert.match(descriptor.template.content, /v-if="activeStep === MATERIAL_STEP && !verifying && selectionProblems.length"/)
  assert.match(descriptor.template.content, /:aria-label="activeStep \? '返回上一步' : '返回上一页'" @click="goBack"/)
  assert.match(descriptor.template.content, /class="ps-step-footer-actions"[\s\S]*?>取消<\/el-button>[\s\S]*?>下一步<\/el-button>/)
  assert.match(descriptor.styles[0].content, /\.ps-step-footer-actions\s*\{[^}]*margin-left:\s*auto/)
})
