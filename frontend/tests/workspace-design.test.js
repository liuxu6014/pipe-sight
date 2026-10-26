import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync } from 'node:fs'
import { compileString } from 'sass-embedded'
import { parse, compileTemplate } from '@vue/compiler-sfc'

const read = path => readFileSync(new URL(path, import.meta.url), 'utf8')
const portal = read('../src/assets/styles/portal.scss')
const workspace = read('../src/assets/styles/workspace.scss')

test('news toolbar keeps desktop search and filters on one row while narrow screens retain wrapping', () => {
  const { descriptor } = parse(read('../src/views/portal/pages/NewsListView.vue'))
  const css = compileString(descriptor.styles[0].content).css
  assert.match(css, /@media \(min-width: 1051px\)[\s\S]*?\.ps-toolbar \{\s*flex-wrap: nowrap;/)
  assert.match(css, /flex: 1 1 280px;\s*min-width: 180px;/)
  assert.match(css, /flex: 0 0 160px;/)
  assert.match(css, /\.ps-toolbar > \.ps-search-inline \{\s*flex: 1 1 100%;/)
})

test('portal searches share one subtle outer focus without suppressing form or button focus', () => {
  const css = compileString(workspace).css
  const containers = '.ps-header-search, .ps-search-inline, .ps-hero-search, .ps-search-hero, .ps-home-search, .ps-discovery-search'
  assert.ok(css.includes(`.ps-portal[data-page] :is(${containers}, .ps-search-input) input:focus-visible`))
  assert.match(css, /input:focus-visible\s*\{\s*outline: none;\s*box-shadow: none;/)
  assert.ok(css.includes(`.ps-portal[data-page] :is(${containers}):focus-within`))
  assert.match(workspace, /box-shadow: 0 0 0 2px #00548712;/)
  assert.match(css, /\.ps-search-input \.el-input__wrapper.is-focus/)
  assert.match(css, /:is\(button, a, input, summary\):focus-visible/)
  for (const page of ['ResearchWorkbenchView', 'MyReportsView', 'MyWorkspaceView']) {
    const source = read(`../src/views/portal/pages/${page}.vue`)
    assert.doesNotMatch(source, /<el-input(?! class="ps-search-input")[^>]*aria-label="搜索/)
  }
})

test('news composite inputs use one outer focus indicator without changing other routes', () => {
  const css = compileString(workspace).css
  assert.match(css, /\.ps-portal\[data-page=PortalNews\] \.ps-page :is\(\.ps-search-inline input, \.el-select__input, \.el-input__inner\):focus-visible\s*\{\s*outline: none;/)
  assert.match(css, /\.ps-portal\[data-page=PortalNews\] \.ps-page :is\(button, \.el-pager li\):focus-visible\s*\{[^}]*outline-offset: -2px;/)
  assert.match(css, /\.ps-portal\[data-page=PortalNews\] \.ps-page \.ps-tag\[aria-pressed=true\]/)
})

test('content adaptation is shared by both shells and never attached to login', () => {
  assert.match(read('../src/views/portal/index.vue'), /class="ps-portal-main ps-workspace-surface"/)
  assert.match(read('../src/layout/components/AppMain.vue'), /class="app-main ps-workspace-surface"/)
  assert.doesNotMatch(read('../src/views/login.vue'), /ps-workspace-surface/)
  const css = compileString(workspace).css
  assert.match(css, /container-name: workspace/)
  assert.match(css, /@container workspace \(max-width: 900px\)/)
  assert.match(css, /--ws-content-max: 1600px/)
  assert.match(css, /\.ps-workspace-surface :is\(\.ps-page, \.pipeline-page\) \.ws-card-grid/)
  assert.match(css, /repeat\(auto-fit, minmax\(min\(100%, var\(--ws-card-min, 280px\)\), 1fr\)\)/)
  assert.doesNotMatch(workspace, /(?:^|\n)\s*(?:body|:root|\.pipeline-user-login)\s*\{/)
})

test('login keeps its existing visual layout outside the workspace redesign', () => {
  const login = read('../src/views/login.vue')
  assert.doesNotMatch(login, /class="calm-nav-link"|class="calm-start-secondary"/)
  assert.match(login, /class="calm-start-primary"/)
  assert.match(login, /height: clamp\(270px, 43vh, 430px\)/)
  assert.match(login, /\.calm-value-grid \{[^}]*grid-template-columns: repeat\(4, minmax\(0, 1fr\)\)/)
  assert.doesNotMatch(login, /class="calm-intro"|class="calm-brand-copy"|class="calm-access-note"/)
})

test('portal Vue templates compile without malformed or duplicate attributes', () => {
  const dir = new URL('../src/views/portal/pages/', import.meta.url)
  for (const file of readdirSync(dir).filter(name => name.endsWith('.vue'))) {
    const { descriptor, errors } = parse(readFileSync(new URL(file, dir), 'utf8'), { filename: file })
    assert.deepEqual(errors, [], file)
    const template = compileTemplate({ source: descriptor.template.content, filename: file, id: file })
    assert.deepEqual(template.errors, [], file)
  }
})
function luminance(hex) {
  const rgb = hex.match(/[a-f0-9]{2}/gi).map(channel => parseInt(channel, 16) / 255)
  const linear = rgb.map(value => value <= .04045 ? value / 12.92 : ((value + .055) / 1.055) ** 2.4)
  return linear[0] * .2126 + linear[1] * .7152 + linear[2] * .0722
}

test('primary, muted and status text tokens meet AA contrast on their surfaces', () => {
  for (const name of ['ink', 'ink-2', 'muted', 'blue', 'teal', 'orange', 'green', 'danger']) {
    const color = portal.match(new RegExp(`--ps-${name}: (#[a-f0-9]{6})`))[1]
    for (const surface of ['ffffff', 'f4f6f9']) {
      const ratio = (luminance(surface) + .05) / (luminance(color) + .05)
      assert.ok(ratio >= 4.5, `${name} on ${surface}: ${ratio.toFixed(2)}`)
    }
  }
})

test('user workspace avoids unreadable fixed font sizes and global semantic-element styling', () => {
  assert.ok([...portal.matchAll(/font-size:\s*(\d+)px/g)].every(match => Number(match[1]) >= 13))
  assert.doesNotMatch(read('../src/assets/styles/index.scss'), /^aside\s*\{/m)
  assert.match(workspace, /font-size: 16px/)
  assert.match(portal, /\.ps-knowledge-table > article > span\[data-label\] \{ grid-column: 1 \/ -1;/)
  assert.match(portal, /@media \(max-width: 1050px\) \{\s*\.ps-knowledge-table \{ overflow-x: auto;/)
})

test('shared workspace SCSS compiles with touch, focus and narrow-screen controls intact', () => {
  const css = compileString(workspace).css
  assert.match(css, /\.ps-portal \.ps-user-button \.ps-user-name\s*\{\s*display: none/)
  assert.match(css, /\.ps-portal \.ps-save-state\s*\{[^}]*display: flex/)
  assert.match(css, /\.ps-skip-link:focus/)
  assert.match(css, /max-width: calc\(100vw - 32px\)/)
  assert.match(css, /min-height: 44px/)
})

test('home search highlights its rounded container rather than nesting a square input outline', () => {
  const css = compileString(workspace).css
  assert.match(css, /\.ps-portal \.ps-home-hero--discovery \.ps-home-welcome \.ps-hero-search input:focus-visible\s*\{\s*outline: none;/)
  assert.match(css, /\.ps-portal \.ps-home-hero--discovery \.ps-home-welcome \.ps-hero-search:focus-within\s*\{[^}]*border-color: var\(--ps-blue\);[^}]*box-shadow:/)
})

test('navigation exposes current location and mobile expanded state without a second desktop menu', () => {
  const header = read('../src/views/portal/components/PortalHeader.vue')
  assert.match(header, /:aria-current=/)
  assert.match(header, /:aria-expanded="mobileOpen"/)
  assert.match(header, /搜索平台内容（移动端）/)
  assert.match(header, /watch\(\(\) => route.fullPath/)
})

test('home-only button states keep focus inset in scroll panels and separate input from submit focus', () => {
  const css = compileString(workspace).css
  assert.match(css, /\.ps-portal \.ps-home-page button:not\(:disabled\):focus-visible[^}]*outline: 2px solid var\(--ps-blue\);[^}]*outline-offset: -2px;/)
  assert.match(css, /\.ps-portal \.ps-home-page :is\([^}]*\):active\s*\{\s*background-color: #d8eaf4;/)
  assert.match(css, /\.ps-portal \.ps-home-hero--discovery \.ps-home-welcome \.ps-hero-search:has\(button:focus-visible\)\s*\{\s*box-shadow: none;/)
})

test('home separates personal work and authorized reading from management metrics', () => {
  const home = read('../src/views/portal/pages/HomeView.vue')
  assert.doesNotMatch(home, /授权资料概览|dashboardMetrics/)
  assert.doesNotMatch(home, /我的最近成果|我的进行中任务|ps-search-mode|待接入/)
  assert.doesNotMatch(home, /当前使用关键词检索，语义检索将在模型配置完成后启用/)
  assert.doesNotMatch(home, /今日研究简报/)
  assert.doesNotMatch(home, /ps-home-timeline|newsTimeline|paperTimeline/)
  assert.match(home, /ps-home-statistics/)
  assert.match(home, /metric.value.toLocaleString\(\)/)
  assert.match(home, /ps-home-latest-list/)
  assert.doesNotMatch(home, /查找管网研究资料|greeting|todayLabel/)
  assert.doesNotMatch(home, /ps-workflow-strip|aria-label="科研工作流程"/)
})

test('desktop workspaces prioritize reports and keep guidance in an on-demand popover', () => {
  const reports = read('../src/views/portal/pages/ResearchWorkbenchView.vue')
  assert.doesNotMatch(reports, /class="ps-research-lead"|模板推荐|class="ps-template-grid"/)
  assert.match(reports, /v-for="report in pagedReports"/)
  assert.doesNotMatch(reports, /unfinishedTasks|ps-report-side|生成任务|研究选材/)
  const help = read('../src/views/portal/components/PortalWorkflowGuide.vue')
  assert.match(help, /class="ps-workflow-popover"/)
  assert.match(help, /关闭使用帮助/)
  const css = compileString(workspace).css
  assert.match(css, /\.ps-portal \.ps-research-create-page \.ps-step-content\s*\{[^}]*overflow-y: auto/)
  assert.match(css, /\.ps-portal \.ps-editor-page \.ps-editor-layout\s*\{[^}]*min-height: 0/)
  assert.match(portal, /\.ps-inspector-tabs.has-exports-tab \{ grid-template-columns: repeat\(4, minmax\(0, 1fr\)\)/)
})

test('editor export formats share one action and resource selection remains labelled', () => {
  for (const page of ['ReportEditorView', 'DigestEditorView']) {
    const source = read(`../src/views/portal/pages/${page}.vue`)
    assert.match(source, /<el-dropdown trigger="click" @command="export/)
    for (const format of ['markdown', 'docx', 'pdf']) assert.match(source, new RegExp(`command="${format}"`))
    assert.match(source, /:loading="versionSaving"/)
  }
  assert.match(read('../src/views/portal/pages/ResearchCreateView.vue'), /章目标字数/)
  assert.match(read('../src/views/portal/pages/NewsListView.vue'), /aria-label="卡片视图"/)
})

test('synthetic visual QA stays localhost-only and separate from production authentication', () => {
  const config = read('./ui-preview/vite.config.js')
  assert.match(config, /host: '127.0.0.1'/)
  assert.doesNotMatch(config, /proxy:/)
  assert.match(read('./ui-preview/fixtures.js'), /throw new Error\('合成数据预览不执行/)
  assert.match(read('./ui-preview/main.js'), /不连接业务接口/)
  assert.match(read('../.env.docker'), /VITE_PORTAL_DEMO_DATA=false/)
})
