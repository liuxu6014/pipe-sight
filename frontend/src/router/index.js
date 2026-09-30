import { createWebHistory, createRouter } from 'vue-router'
/* Layout */
import Layout from '@/layout'

/**
 * Note: 路由配置项
 *
 * hidden: true                     // 当设置 true 的时候该路由不会再侧边栏出现 如401，login等页面，或者如一些编辑页面/edit/1
 * alwaysShow: true                 // 当你一个路由下面的 children 声明的路由大于1个时，自动会变成嵌套的模式--如组件页面
 *                                  // 只有一个时，会将那个子路由当做根路由显示在侧边栏--如引导页面
 *                                  // 若你想不管路由下面的 children 声明的个数都显示你的根路由
 *                                  // 你可以设置 alwaysShow: true，这样它就会忽略之前定义的规则，一直显示根路由
 * redirect: noRedirect             // 当设置 noRedirect 的时候该路由在面包屑导航中不可被点击
 * name:'router-name'               // 设定路由的名字，一定要填写不然使用<keep-alive>时会出现各种问题
 * query: '{"id": 1, "name": "ry"}' // 访问路由的默认传递参数
 * roles: ['admin', 'common']       // 访问路由的角色权限
 * permissions: ['a:a:a', 'b:b:b']  // 访问路由的菜单权限
 * meta : {
    noCache: true                   // 如果设置为true，则不会被 <keep-alive> 缓存(默认 false)
    title: 'title'                  // 设置该路由在侧边栏和面包屑中展示的名字
    icon: 'svg-name'                // 设置该路由的图标，对应路径src/assets/icons/svg
    breadcrumb: false               // 如果设置为false，则不会在breadcrumb面包屑中显示
    activeMenu: '/system/user'      // 当路由设置了该属性，则会高亮相对应的侧边栏。
  }
 */

// 公共路由
export const constantRoutes = [
  {
    path: '',
    redirect: '/portal',
    hidden: true
  },
  {
    path: '/redirect',
    component: Layout,
    hidden: true,
    children: [
      {
        path: '/redirect/:path(.*)',
        component: () => import('@/views/redirect/index.vue')
      }
    ]
  },
  {
    path: '/login',
    component: () => import('@/views/login'),
    hidden: true
  },
  {
    path: '/register',
    component: () => import('@/views/register'),
    hidden: true
  },
  {
    path: '/portal-login',
    redirect: to => ({
      path: '/login',
      query: { redirect: to.query?.redirect || '/portal' }
    }),
    hidden: true,
    meta: { title: '国家管网科技情报与科研辅助平台用户端登录' }
  },
  {
    path: '/portal',
    component: () => import('@/views/portal/index.vue'),
    hidden: true,
    meta: { title: '国家管网科技情报与科研辅助平台用户端' },
    children: [
      { path: '', name: 'PortalHome', component: () => import('@/views/portal/pages/HomeView.vue'), meta: { title: '首页' } },
      { path: 'search', name: 'PortalSearch', component: () => import('@/views/portal/pages/SearchView.vue'), meta: { title: '全局搜索' } },
      { path: 'news', name: 'PortalNews', component: () => import('@/views/portal/pages/NewsListView.vue'), meta: { title: '科技资讯' } },
      { path: 'news/:itemId', name: 'PortalNewsDetail', component: () => import('@/views/portal/pages/NewsDetailView.vue'), meta: { title: '资讯详情' } },
      { path: 'papers', name: 'PortalPapers', component: () => import('@/views/portal/pages/PaperListView.vue'), meta: { title: '论文资料' } },
      { path: 'papers/:itemId', name: 'PortalPaperDetail', component: () => import('@/views/portal/pages/PaperDetailView.vue'), meta: { title: '论文详情' } },
      { path: 'research', name: 'PortalResearch', component: () => import('@/views/portal/pages/ResearchWorkbenchView.vue'), meta: { title: '科研工作台' } },
      { path: 'research/create', name: 'PortalResearchCreate', component: () => import('@/views/portal/pages/ResearchCreateView.vue'), meta: { title: '新建科研任务' } },
      { path: 'research/tasks/:id', name: 'PortalResearchTask', component: () => import('@/views/portal/pages/ResearchTaskView.vue'), meta: { title: '任务进度' } },
      { path: 'research/reports/:id', name: 'PortalReportEditor', component: () => import('@/views/portal/pages/ReportEditorView.vue'), meta: { title: '报告编辑器' } },
      { path: 'research/reports/:id/diagram', name: 'PortalDiagramEditor', component: () => import('@/views/portal/pages/DiagramEditorView.vue'), meta: { title: '图形编辑器' } },
      { path: 'digests', name: 'PortalDigests', component: () => import('@/views/portal/pages/DigestListView.vue'), meta: { title: '情报简报' } },
      { path: 'digests/create', name: 'PortalDigestCreate', component: () => import('@/views/portal/pages/DigestCreateView.vue'), meta: { title: '新建简报' } },
      { path: 'digests/:id', name: 'PortalDigestEditor', component: () => import('@/views/portal/pages/DigestEditorView.vue'), meta: { title: '简报编辑' } },
      { path: 'reports/:itemId?', redirect: to => to.params.itemId ? `/portal/digests/${to.params.itemId}` : '/portal/digests' },
      { path: 'knowledge', name: 'PortalKnowledge', component: () => import('@/views/portal/pages/KnowledgeView.vue'), meta: { title: '知识库' } },
      { path: 'knowledge/ask', name: 'PortalKnowledgeAsk', component: () => import('@/views/portal/pages/KnowledgeAskView.vue'), meta: { title: '知识问答' } },
      { path: 'knowledge/:id', name: 'PortalKnowledgeDetail', component: () => import('@/views/portal/pages/KnowledgeDetailView.vue'), meta: { title: '资料详情' } },
      { path: 'me/tasks', name: 'PortalMyTasks', component: () => import('@/views/portal/pages/MyWorkspaceView.vue'), props: { mode: 'tasks' }, meta: { title: '我的任务' } },
      { path: 'me/reports', name: 'PortalMyReports', component: () => import('@/views/portal/pages/MyWorkspaceView.vue'), props: { mode: 'reports' }, meta: { title: '我的报告' } },
      { path: 'me/favorites', name: 'PortalMyFavorites', component: () => import('@/views/portal/pages/MyWorkspaceView.vue'), props: { mode: 'favorites' }, meta: { title: '我的收藏' } }
    ]
  },
  {
    path: '/pipeline/manuscript',
    component: Layout,
    hidden: true,
    children: [
      {
        path: '',
        component: () => import('@/views/pipeline/manuscript/index.vue'),
        name: 'PipelineManuscript',
        meta: { title: '论文生成', icon: 'edit' }
      }
    ]
  },
  {
    path: '/pipeline/governance',
    component: Layout,
    hidden: true,
    children: [{ path: '', component: () => import('@/views/pipeline/governance/index.vue'), name: 'PipelineGovernance', meta: { title: '数据治理', icon: 'build' } }]
  },
  {
    path: '/pipeline/template',
    component: Layout,
    hidden: true,
    children: [{ path: '', component: () => import('@/views/pipeline/template/index.vue'), name: 'PipelineTemplate', meta: { title: '模板管理', icon: 'documentation' } }]
  },
  {
    path: '/pipeline/model',
    component: Layout,
    hidden: true,
    children: [{ path: '', component: () => import('@/views/pipeline/model/index.vue'), name: 'PipelineModel', meta: { title: '模型与 Prompt', icon: 'ai' } }]
  },
  {
    path: "/:pathMatch(.*)*",
    component: () => import('@/views/error/404'),
    hidden: true
  },
  {
    path: '/401',
    component: () => import('@/views/error/401'),
    hidden: true
  },
  {
    path: '/user',
    component: Layout,
    hidden: true,
    redirect: 'noredirect',
    children: [
      {
        path: 'profile/:activeTab?',
        component: () => import('@/views/system/user/profile/index'),
        name: 'Profile',
        meta: { title: '个人中心', icon: 'user' }
      }
    ]
  }
]

// 动态路由，基于用户权限动态去加载
export const dynamicRoutes = [
  {
    path: '/system/user-auth',
    component: Layout,
    hidden: true,
    permissions: ['system:user:edit'],
    children: [
      {
        path: 'role/:userId(\\d+)',
        component: () => import('@/views/system/user/authRole'),
        name: 'AuthRole',
        meta: { title: '分配角色', activeMenu: '/system/user' }
      }
    ]
  },
  {
    path: '/system/role-auth',
    component: Layout,
    hidden: true,
    permissions: ['system:role:edit'],
    children: [
      {
        path: 'user/:roleId(\\d+)',
        component: () => import('@/views/system/role/authUser'),
        name: 'AuthUser',
        meta: { title: '分配用户', activeMenu: '/system/role' }
      }
    ]
  },
  {
    path: '/system/dict-data',
    component: Layout,
    hidden: true,
    permissions: ['system:dict:list'],
    children: [
      {
        path: 'index/:dictId(\\d+)',
        component: () => import('@/views/system/dict/data'),
        name: 'Data',
        meta: { title: '字典数据', activeMenu: '/system/dict' }
      }
    ]
  },
  {
    path: '/monitor/job-log',
    component: Layout,
    hidden: true,
    permissions: ['monitor:job:list'],
    children: [
      {
        path: 'index/:jobId(\\d+)',
        component: () => import('@/views/monitor/job/log'),
        name: 'JobLog',
        meta: { title: '调度日志', activeMenu: '/monitor/job' }
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes: constantRoutes,
  scrollBehavior(to, from, savedPosition) {
    if (savedPosition) {
      return savedPosition
    }
    return { top: 0 }
  },
});

export default router;
