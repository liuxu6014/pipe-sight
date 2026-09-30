import router from './router'
import { ElMessage } from 'element-plus'
import NProgress from 'nprogress'
import 'nprogress/nprogress.css'
import { getToken } from '@/utils/auth'
import { isHttp } from '@/utils/validate'
import {
  getDefaultLoginPath,
  getLoginRedirect,
  isPortalLoginPath,
  isPortalProtectedPath,
  isPublicAuthPath
} from '@/utils/portal/auth'
import { isRelogin } from '@/utils/request'
import useUserStore from '@/store/modules/user'
import useSettingsStore from '@/store/modules/settings'
import usePermissionStore from '@/store/modules/permission'

NProgress.configure({ showSpinner: false })

function addAccessRoutes(accessRoutes = []) {
  accessRoutes.forEach(route => {
    if (!isHttp(route.path)) {
      router.addRoute(route)
    }
  })
}

function loadCurrentUserRoutes() {
  isRelogin.show = true
  return useUserStore().getInfo().then(() => {
    isRelogin.show = false
    return usePermissionStore().generateRoutes(useUserStore()).then(accessRoutes => {
      addAccessRoutes(accessRoutes)
      return accessRoutes
    })
  }).catch(error => {
    isRelogin.show = false
    throw error
  })
}

router.beforeEach((to, from, next) => {
  NProgress.start()
  if (getToken()) {
    to.meta.title && useSettingsStore().setTitle(to.meta.title)
    /* has token*/
    if (to.path === '/login') {
      if (useUserStore().roles.length === 0) {
        loadCurrentUserRoutes().then(() => {
          next({ path: getDefaultLoginPath(useUserStore()), replace: true })
          NProgress.done()
        }).catch(err => {
          useUserStore().logOut().then(() => {
            ElMessage.error(err)
            next({ path: '/login' })
            NProgress.done()
          })
        })
      } else {
        next({ path: getDefaultLoginPath(useUserStore()), replace: true })
        NProgress.done()
      }
    } else if (isPortalLoginPath(to.path)) {
      next({ path: '/portal' })
      NProgress.done()
    } else if (isPublicAuthPath(to.path)) {
      next()
    } else {
      if (useUserStore().roles.length === 0) {
        // 判断当前用户是否已拉取完user_info信息
        loadCurrentUserRoutes().then(() => {
            // 根据roles权限生成可访问的路由表
            next({ ...to, replace: true }) // hack方法 确保addRoutes已完成
        }).catch(err => {
          useUserStore().logOut().then(() => {
            ElMessage.error(err)
            next({ path: '/' })
          })
        })
      } else {
        next()
      }
    }
  } else {
    // 没有token
    if (isPublicAuthPath(to.path)) {
      // 在免登录白名单，直接进入
      next()
    } else if (isPortalProtectedPath(to.path)) {
      next(getLoginRedirect(to.fullPath))
      NProgress.done()
    } else {
      next(`/login?redirect=${to.fullPath}`) // 否则全部重定向到登录页
      NProgress.done()
    }
  }
})

router.afterEach(() => {
  NProgress.done()
})
