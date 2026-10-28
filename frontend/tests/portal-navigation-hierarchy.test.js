import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { portalNavigation, isBasketPath } from '../src/views/portal/data.js'

const read = name => fs.readFileSync(new URL(`../src/views/portal/${name}`, import.meta.url), 'utf8')

test('research owns reports while uploaded materials belong to the basket navigation', () => {
  assert.deepEqual(portalNavigation.map(x => x.label), ['首页', '新闻资讯', '科研论文', '科研报告', '情报简报'])
  assert.equal(portalNavigation.some(x => x.label === '我的报告'), false)
  const research = portalNavigation.find(x => x.label === '科研报告')
  for (const path of ['/portal/knowledge', '/portal/knowledge/54']) {
    assert.equal(research.match(path), false)
    assert.equal(isBasketPath(path), true)
  }
  assert.equal(isBasketPath('/portal/basket'), true)
  for (const path of ['/portal/research/reports/33', '/portal/papers/26', '/portal/knowledge-other']) assert.equal(isBasketPath(path), false)
  assert.equal(portalNavigation.some(x => x.match('/portal/me/tasks')), false)
})

test('account actions remain in avatar menu and basket has one global destination', () => {
  const header = read('components/PortalHeader.vue')
  assert.match(header, /command="logout"/)
  assert.doesNotMatch(header, /command="reports"|我的报告/)
  assert.doesNotMatch(header, /command="favorites"|我的收藏/)
  assert.doesNotMatch(header, /command="tasks"/)
  assert.match(header, /个人资料/)
  assert.doesNotMatch(header, /个人资料设置/)
  assert.match(header, /command="profile"/)
  assert.match(header, /command === 'profile'[\s\S]*?router\.push\('\/portal\/profile'\)/)
  assert.match(header, /<el-dropdown trigger="click"[^>]*>\s*<button class="ps-user-button"[^>]*账户菜单[^>]*>\s*<PortalUserAvatar/)
  assert.doesNotMatch(header, /ps-account-trigger|ArrowDown|@click="router.push\('\/portal\/profile'\)"/)
  assert.equal((header.match(/router\.push\('\/portal\/basket'\)/g) || []).length, 1)
  for (const page of ['SearchView', 'ResearchWorkbenchView']) {
    assert.doesNotMatch(read(`pages/${page}.vue`), /router\.push\('\/portal\/basket'\)/)
  }
  assert.doesNotMatch(read('pages/KnowledgeView.vue'), /返回资料库|管理上传资料/)
})

test('research workspace keeps report entry points without a duplicate material management link in creation', () => {
  const workbench = read('pages/ResearchWorkbenchView.vue')
  assert.doesNotMatch(workbench, /ps-report-side|ps-report-workspace-grid|生成任务|研究选材/)
  assert.match(workbench, /ps-report-workspace-content/)
  assert.match(workbench, /新建报告/)
  assert.match(workbench, /buildPersonalReports/)
  assert.match(workbench, /科研报告列表分页/)
  assert.doesNotMatch(workbench, /ps-research-list-heading|<h2>报告列表/)
  assert.doesNotMatch(workbench, /我的报告/)
  assert.doesNotMatch(read('pages/ResearchCreateView.vue'), /ps-research-material-link|管理研究资料/)
  assert.match(read('pages/KnowledgeView.vue'), /title="资料库"/)
  const home = read('pages/HomeView.vue')
  assert.match(home, /path: '\/portal\/research\/create', action: '创建报告'/)
  assert.match(home, /path: '\/portal\/digests\/create', action: '生成简报'/)
})
