// 仅投影后端已授权菜单，不参与路由注册或接口授权。
const MODULES = [
  { key: 'home', title: '管理首页', icon: 'dashboard', direct: true },
  { key: 'users', title: '用户管理', icon: 'user' },
  { key: 'collection', title: '采集管理', icon: 'link' },
  { key: 'data', title: '数据管理', icon: 'documentation' },
  { key: 'knowledge', title: '资料库管理', icon: 'documentation', direct: true },
  { key: 'reports', title: '报告管理', icon: 'documentation', direct: true },
  { key: 'digests', title: '简报管理', icon: 'documentation', direct: true },
  { key: 'templates', title: '模板管理', icon: 'documentation', direct: true },
  { key: 'settings', title: '系统配置', icon: 'system' },
  { key: 'logs', title: '运行日志', icon: 'log' }
]

// 未列出的合法页面仍保留在系统配置下；映射本身不会创建任何入口。
const ENTRIES = {
  '/index': ['home', '管理首页'],
  '/pipeline/dashboard': ['home', '管理首页'],
  '/system/user': ['users', '账号管理'],
  '/system/role': ['users', '角色与授权'],
  '/pipeline/source': ['collection', '数据源管理'],
  '/pipeline/task': ['collection', '采集任务'],
  '/pipeline/intelligence': ['data', '情报查询'],
  '/pipeline/knowledge': ['knowledge', '资料库管理'],
  '/pipeline/report': ['reports', '科研报告'],
  '/pipeline/manuscript': ['reports', '论文生成'],
  '/pipeline/digest': ['digests', '简报管理'],
  '/pipeline/template': ['templates', '模板管理'],
  '/pipeline/model': ['settings', '模型与类别提示词'],
  '/ai/model': ['settings', '模型管理'],
  '/system/menu': ['settings', '菜单配置'],
  '/system/config': ['settings', '系统参数'],
  '/system/dict': ['settings', '字典管理']
}

// 仅整理可见导航；这些上游模板入口仍保留在原路由注册树中。
const TEMPLATE_MENU_PATHS = new Set(['/tool/swagger', '/monitor/druid'])
// Reject stale backend snapshots; the retired components and routes no longer exist.
const RETIRED_PIPELINE_PATHS = new Set(['/pipeline/filter', '/pipeline/governance', '/ai/chat'])
const SETTINGS_ENTRY_ORDER = ['/pipeline/model', '/ai/model', '/system/config', '/system/dict', '/system/menu']

function isTemplateLink(path = '') {
  if (!/^https?:\/\//i.test(path)) return false
  try {
    return new URL(path).hostname === 'ruoyi.vip'
  } catch {
    return false
  }
}

function isExternal(path = '') {
  return /^(https?:|mailto:|tel:)/.test(path)
}

export function resolveNavigationPath(basePath = '', routePath = '') {
  if (isExternal(routePath)) return routePath
  if (isExternal(basePath)) return basePath
  const path = routePath.startsWith('/') ? routePath : `${basePath}/${routePath}`
  return path.replace(/\/{2,}/g, '/').replace(/\/$/, '') || '/'
}

function cloneNavigationValue(value) {
  if (Array.isArray(value)) return value.map(cloneNavigationValue)
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, cloneNavigationValue(item)]))
  }
  return value
}

// 组件引用保持不变；可被菜单组件消费的路径、meta、query 和子树各自独立。
export function cloneNavigationRoutes(routes = [], basePath = '') {
  return routes.map(route => {
    const path = resolveNavigationPath(basePath, route.path)
    const clone = { ...route, path }
    for (const key of ['meta', 'query', 'roles', 'permissions']) {
      if (route[key] !== undefined) clone[key] = cloneNavigationValue(route[key])
    }
    if (route.children) clone.children = cloneNavigationRoutes(route.children, path)
    return clone
  })
}

function queryKey(query) {
  const value = typeof query === 'string' ? (query.trim() ? JSON.parse(query) : {}) : (query || {})
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new TypeError('Invalid menu query')
  return JSON.stringify(value, (_key, item) => {
    if (item && typeof item === 'object' && !Array.isArray(item)) {
      return Object.fromEntries(Object.keys(item).sort().map(key => [key, item[key]]))
    }
    return item
  })
}

export function buildManagementNavigation(routes = [], {
  isContainer = route => ['Layout', 'ParentView'].includes(route.component)
} = {}) {
  const entries = []
  const destinations = new Set()

  function visit(nodes, basePath = '') {
    for (const route of nodes) {
      // 隐藏父目录的子项也不能意外出现在导航中。
      if (route.hidden) continue
      const path = resolveNavigationPath(basePath, route.path)
      if (RETIRED_PIPELINE_PATHS.has(path) || TEMPLATE_MENU_PATHS.has(path) || isTemplateLink(path) || isTemplateLink(route.meta?.link)) continue
      if (route.children?.length) {
        visit(route.children, path)
        continue
      }
      // 缺失组件、空目录、带必填参数的详情页均不是可点击的菜单入口。
      if ((!route.component || isContainer(route)) && !isExternal(path)) continue
      if (!isExternal(path) && /:[^/]+/.test(path)) continue
      if (!route.meta?.title) continue
      let destination
      try {
        destination = `${path}?${queryKey(route.query)}`
      } catch {
        continue
      }
      if (destinations.has(destination)) continue
      destinations.add(destination)
      const [module, title] = ENTRIES[path] || [path.startsWith('/monitor/') || /\/(operlog|logininfor)$/.test(path) ? 'logs' : 'settings', route.meta.title]
      entries.push({
        module,
        route: {
          ...route,
          path,
          // 后端无参数菜单默认 query=''；导航副本统一为空，注册树保留原值。
          query: typeof route.query === 'string' && !route.query.trim() ? undefined : route.query,
          meta: { ...route.meta, title }
        }
      })
    }
  }
  visit(routes)

  // 两个现有模型页维护相同模型数据，优先综合配置页；旧路由仍由原路由树注册。
  const model = entries.find(entry => entry.route.path === '/pipeline/model')
  const legacyModel = entries.find(entry => entry.route.path === '/ai/model')
  if (model && legacyModel) {
    model.route.meta.navigationAliases = ['/ai/model']
  }

  return MODULES.flatMap(module => {
    const children = entries
      .filter(entry => entry.module === module.key && !(model && legacyModel && entry === legacyModel))
      .map(entry => entry.route)
    if (module.key === 'settings') {
      const priority = path => {
        const index = SETTINGS_ENTRY_ORDER.indexOf(path)
        return index === -1 ? SETTINGS_ENTRY_ORDER.length : index
      }
      children.sort((a, b) => priority(a.path) - priority(b.path))
    }
    if (!children.length) return []
    if (module.direct && children.length === 1) {
      return [{ ...children[0], meta: { ...children[0].meta, title: module.title } }]
    }
    // 分组只供 el-sub-menu 展示，不添加到 Vue Router，也不是链接。
    return [{
      path: `/_management/${module.key}`,
      alwaysShow: true,
      meta: { title: module.title, icon: module.icon, navigationGroup: true },
      children
    }]
  })
}

export function resolveActiveNavigation(route, menus = []) {
  const links = []
  function visit(nodes, basePath = '') {
    for (const node of nodes) {
      if (node.hidden) continue
      const path = resolveNavigationPath(basePath, node.path)
      if (node.children?.length) visit(node.children, path)
      else links.push({ path, aliases: node.meta?.navigationAliases || [] })
    }
  }
  visit(menus)
  const target = route.meta?.activeMenu || route.path
  const match = links
    .flatMap(link => [link.path, ...link.aliases].map(path => ({ path, active: link.path })))
    .filter(link => !isExternal(link.path) && (target === link.path || target?.startsWith(`${link.path}/`)))
    .sort((a, b) => b.path.length - a.path.length)[0]
  return match?.active || target
}

export function findNavigationGroup(route, menus = []) {
  const active = resolveActiveNavigation(route, menus)
  let match
  let length = -1
  function visit(nodes, root, basePath = '') {
    for (const node of nodes) {
      if (node.hidden) continue
      const path = resolveNavigationPath(basePath, node.path)
      if (!isExternal(path) && (path === active || active?.startsWith(`${path}/`)) && path.length > length) {
        match = root
        length = path.length
      }
      if (node.children) visit(node.children, root, path)
    }
  }
  for (const menu of menus) visit([menu], menu)
  return match
}

export function splitNavigationMenus(menus = [], visibleNumber = 5) {
  const visibleMenus = menus.filter(menu => !menu.hidden)
  const count = Math.max(0, Math.floor(Number(visibleNumber) || 0))
  return { visible: visibleMenus.slice(0, count), more: visibleMenus.slice(count) }
}
