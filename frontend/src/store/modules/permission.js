import auth from '@/plugins/auth'
import router, { constantRoutes, dynamicRoutes } from '@/router'
import { getRouters } from '@/api/menu'
import Layout from '@/layout/index'
import ParentView from '@/components/ParentView'
import InnerLink from '@/layout/components/InnerLink'
import { isManagementIdentity } from '@/utils/portal/auth'
import { buildManagementNavigation, cloneNavigationRoutes } from '@/utils/management-navigation'

// 匹配views里面所有的.vue文件
const modules = import.meta.glob('./../../views/**/*.vue')
const PIPELINE_VISIBLE_ROOTS = new Set(['', 'index', 'pipeline'])
const BACKEND_ONLY_ROOTS = new Set(['system', 'monitor', 'tool', 'ai'])

const usePermissionStore = defineStore(
  'permission',
  {
    state: () => ({
      routes: [],
      addRoutes: [],
      defaultRoutes: [],
      navigationRoutes: [],
      topbarRouters: [],
      sidebarRouters: []
    }),
    actions: {
      setRoutes(routes) {
        this.addRoutes = routes
        this.routes = constantRoutes.concat(routes)
      },
      setDefaultRoutes(routes) {
        this.defaultRoutes = constantRoutes.concat(routes)
      },
      setTopbarRoutes(routes) {
        this.topbarRouters = routes
      },
      setSidebarRouters(routes) {
        this.sidebarRouters = routes
      },
      setNavigationRoutes(routes) {
        this.navigationRoutes = cloneNavigationRoutes(routes)
        this.setTopbarRoutes(cloneNavigationRoutes(this.navigationRoutes))
        this.restoreSidebarRouters()
      },
      restoreSidebarRouters() {
        this.setSidebarRouters(cloneNavigationRoutes(this.navigationRoutes))
      },
      selectNavigationGroup(path) {
        const group = this.navigationRoutes.find(menu => menu.path === path && !menu.hidden)
        if (!group?.children?.length) return false
        this.setSidebarRouters(cloneNavigationRoutes(group.children))
        return true
      },
      async generateRoutes(user = {}) {
        // 返回 API 调用本身的 Promise，使失败能传递到登录页和路由守卫。
        const res = await getRouters()
        const sdata = JSON.parse(JSON.stringify(res.data))
        const rdata = JSON.parse(JSON.stringify(res.data))
        const sidebarRoutes = filterAsyncRouter(sdata)
        const rewriteRoutes = filterAsyncRouter(rdata, false, true)
        const asyncRoutes = filterDynamicRoutes(dynamicRoutes)
        asyncRoutes.forEach(route => { router.addRoute(route) })
        this.setRoutes(rewriteRoutes)
        // 明确标记的真实动态入口也须先通过原有权限过滤；静态隐藏路由不提升。
        const managementEntries = asyncRoutes.filter(route => route.meta?.managementEntry === true)
        this.setNavigationRoutes(isManagementIdentity(user.roles || [], user.permissions || [])
          ? buildManagementNavigation(sidebarRoutes.concat(managementEntries), {
            isContainer: route => route.component === Layout || route.component === ParentView
          })
          : filterPipelineUserMenus(constantRoutes.concat(sidebarRoutes)))
        this.setDefaultRoutes(resolveVisibleMenus(sidebarRoutes, user))
        return rewriteRoutes
      }
    }
  })

// 遍历后台传来的路由字符串，转换为组件对象
function filterAsyncRouter(asyncRouterMap, lastRouter = false, type = false) {
  return asyncRouterMap.filter(route => {
    if (['pipeline/governance/index', 'pipeline/filter/index', 'ai/chat/index'].includes(route.component) || ['/pipeline/governance', '/pipeline/filter', '/ai/chat'].includes(route.path)) return false
    if (type && route.children) {
      route.children = filterChildren(route.children)
    }
    if (route.component) {
      // Layout ParentView 组件特殊处理
      if (route.component === 'Layout') {
        route.component = Layout
      } else if (route.component === 'ParentView') {
        route.component = ParentView
      } else if (route.component === 'InnerLink') {
        route.component = InnerLink
      } else {
        route.component = loadView(route.component)
      }
    }
    if (route.children != null && route.children && route.children.length) {
      route.children = filterAsyncRouter(route.children, route, type)
      if (!route.children.length) return false
    } else {
      delete route['children']
      delete route['redirect']
    }
    return true
  })
}

function routeRoot(path = '') {
  return String(path).replace(/^\/+/, '').split('/')[0]
}

function filterMenuTree(routes = [], isChild = false) {
  return routes
    .filter(route => {
      const root = routeRoot(route.path)
      if (!isChild && BACKEND_ONLY_ROOTS.has(root)) return false
      if (isChild || route.hidden) return true
      return PIPELINE_VISIBLE_ROOTS.has(root)
    })
    .map(route => ({
      ...route,
      children: route.children ? filterMenuTree(route.children, isChild || routeRoot(route.path) === 'pipeline' || route.path === '') : route.children
    }))
}

function filterPipelineUserMenus(routes = []) {
  return filterMenuTree(routes)
}

function resolveVisibleMenus(routes = [], user = {}) {
  return isManagementIdentity(user.roles || [], user.permissions || [])
    ? routes
    : filterPipelineUserMenus(routes)
}

function filterChildren(childrenMap, lastRouter = false) {
  var children = []
  childrenMap.forEach(el => {
    el.path = lastRouter ? lastRouter.path + '/' + el.path : el.path
    if (el.children && el.children.length && el.component === 'ParentView') {
      children = children.concat(filterChildren(el.children, el))
    } else {
      children.push(el)
    }
  })
  return children
}

// 动态路由遍历，验证是否具备权限
export function filterDynamicRoutes(routes) {
  const res = []
  routes.forEach(route => {
    if (route.permissions) {
      if (auth.hasPermiOr(route.permissions)) {
        res.push(route)
      }
    } else if (route.roles) {
      if (auth.hasRoleOr(route.roles)) {
        res.push(route)
      }
    }
  })
  return res
}

export const loadView = (view) => {
  let res;
  for (const path in modules) {
    const dir = path.split('views/')[1].split('.vue')[0];
    if (dir === view) {
      res = () => modules[path]();
    }
  }
  return res
}

export default usePermissionStore
