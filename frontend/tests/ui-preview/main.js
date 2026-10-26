import { createApp, h, ref } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createWebHistory, RouterView } from 'vue-router'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import '../../src/assets/styles/index.scss'
import './preview.css'
import Portal from '../../src/views/portal/index.vue'
import useUserStore from '../../src/store/modules/user'

const pages = import.meta.glob('../../src/views/portal/pages/*.vue')
const page = name => pages[`../../src/views/portal/pages/${name}.vue`]
const router = createRouter({ history: createWebHistory(), routes: [
  { path: '/', redirect: '/portal' },
  { path: '/portal', component: Portal, children: [
    { path: '', component: page('HomeView') },
    { path: 'news', component: page('NewsListView') },
    { path: 'news/:id', component: page('NewsDetailView') },
    { path: 'papers', component: page('PaperListView') },
    { path: 'papers/:id', component: page('PaperDetailView') },
    { path: 'research', component: page('ResearchWorkbenchView') },
    { path: 'research/create', component: page('ResearchCreateView') },
    { path: 'research/tasks/:id', component: page('ResearchTaskView') },
    { path: 'research/reports/:id', component: page('ReportEditorView') },
    { path: 'digests', component: page('DigestListView') },
    { path: 'digests/create', component: page('DigestCreateView') },
    { path: 'digests/:id', component: page('DigestEditorView') },
    { path: 'knowledge', component: page('KnowledgeView') },
    { path: 'search', component: page('SearchView') },
    { path: 'basket', component: page('MyWorkspaceView'), props: { mode: 'basket' } },
    { path: 'me/basket', redirect: '/portal/basket' },
    { path: 'me/:section', component: page('MyWorkspaceView'), props: route => ({ mode: route.params.section }) }
  ] },
  { path: '/management', component: () => import('../../src/views/pipeline/dashboard/index.vue') },
  { path: '/management/sources', component: () => import('../../src/views/pipeline/source/index.vue') },
  { path: '/management/templates', component: () => import('../../src/views/pipeline/template/index.vue') }
] })
const sidebarOpen = ref(true)
const Root = { render: () => {
  const management = router.currentRoute.value.path.startsWith('/management')
  return h('div', { class: management ? ['ps-management-shell', 'ui-preview-management', { 'has-preview-sidebar': sidebarOpen.value }] : '' }, [
  management ? h('aside', { class: 'ui-preview-sidebar', 'aria-label': '合成管理导航' }, [h('strong', '管理界面验收'), h('a', { href: '/management' }, '运行概览'), h('a', { href: '/management/sources' }, '数据源管理'), h('a', { href: '/management/templates' }, '模板管理')]) : null,
  management ? h('main', { class: 'ps-workspace-surface' }, [h('div', { class: 'ui-preview-shell-toolbar' }, [h('button', { type: 'button', 'aria-expanded': sidebarOpen.value, onClick: () => sidebarOpen.value = !sidebarOpen.value }, sidebarOpen.value ? '收起验收侧栏' : '展开验收侧栏')]), h(RouterView)]) : h(RouterView),
  h('nav', { class: 'ui-preview-banner', 'aria-label': '预览环境说明' }, [
    h('strong', '界面验收预览 · 合成数据 · 不连接业务接口'),
    h('a', { href: '/portal/research/reports/preview-report' }, '报告编辑器'),
    h('a', { href: '/portal/digests/preview-digest' }, '简报编辑器'),
    h('a', { href: '/management' }, '管理概览')
  ])
]) } }
const app = createApp(Root).use(createPinia()).use(router).use(ElementPlus)
const user = useUserStore()
user.name = 'preview-only'; user.nickName = '预览用户'; user.roles = ['admin']; user.permissions = ['*:*:*']
app.mount('#app')
