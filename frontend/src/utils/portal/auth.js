import { isPathMatch } from '../validate.js'

export const USER_PORTAL_LOGIN_PATH = '/portal-login'
export const UNIFIED_LOGIN_PATH = '/login'
export const PORTAL_DEFAULT_LOGIN_PATH = '/portal'
export const MANAGEMENT_DEFAULT_LOGIN_PATH = '/pipeline/dashboard'

const MANAGEMENT_ROLES = new Set(['admin'])
const MANAGEMENT_PERMISSIONS = new Set(['*:*:*'])
const PUBLIC_AUTH_PATHS = [UNIFIED_LOGIN_PATH, '/register', USER_PORTAL_LOGIN_PATH]
const LEGACY_MANAGEMENT_DEFAULT_LOGIN_PATH = '/index'
const PIPELINE_MANAGEMENT_DEFAULT_LOGIN_PATH = '/pipeline/dashboard'

export function isPortalLoginPath(path = '') {
  return path === USER_PORTAL_LOGIN_PATH
}

export function isPortalProtectedPath(path = '') {
  return path === '/portal' || path.startsWith('/portal/')
}

export function isPublicAuthPath(path = '') {
  return PUBLIC_AUTH_PATHS.some(pattern => isPathMatch(pattern, path))
}

export function getLoginRedirect(fullPath = '/portal') {
  return `${UNIFIED_LOGIN_PATH}?redirect=${encodeURIComponent(fullPath || '/portal')}`
}

export function isManagementIdentity(roles = [], permissions = []) {
  return roles.some(role => MANAGEMENT_ROLES.has(role)) || permissions.some(permission => MANAGEMENT_PERMISSIONS.has(permission))
}

export function canAccessApplicationPath(user = {}, path = '') {
  return isManagementIdentity(user.roles || [], user.permissions || [])
    || isPortalProtectedPath(path)
    || path === '/user/profile' || path.startsWith('/user/profile/')
    || isPublicAuthPath(path)
}

export function getDefaultLoginPath(user = {}) {
  return isManagementIdentity(user.roles || [], user.permissions || [])
    ? MANAGEMENT_DEFAULT_LOGIN_PATH
    : PORTAL_DEFAULT_LOGIN_PATH
}

export function resolvePostLoginPath(user = {}, requestedPath) {
  const defaultPath = getDefaultLoginPath(user)
  // 仅接受站内路径，保留报告等明确目的地，管理员也可以访问用户门户。
  if (typeof requestedPath !== 'string' || !requestedPath.startsWith('/') || requestedPath.startsWith('//') || requestedPath.includes('\\')) {
    return defaultPath
  }
  if (
    !requestedPath ||
    requestedPath === UNIFIED_LOGIN_PATH ||
    requestedPath === USER_PORTAL_LOGIN_PATH ||
    requestedPath === LEGACY_MANAGEMENT_DEFAULT_LOGIN_PATH ||
    requestedPath === PIPELINE_MANAGEMENT_DEFAULT_LOGIN_PATH
  ) {
    return defaultPath
  }
  if (defaultPath === PORTAL_DEFAULT_LOGIN_PATH) {
    return isPortalProtectedPath(requestedPath) ? requestedPath : defaultPath
  }
  return isPublicAuthPath(requestedPath.split(/[?#]/)[0]) ? defaultPath : requestedPath
}

export function getPublicAuthPaths() {
  return [...PUBLIC_AUTH_PATHS]
}
