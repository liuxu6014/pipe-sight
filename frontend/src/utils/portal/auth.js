import { isPathMatch } from '../validate.js'

export const USER_PORTAL_LOGIN_PATH = '/portal-login'
export const UNIFIED_LOGIN_PATH = '/login'
export const PORTAL_DEFAULT_LOGIN_PATH = '/portal'
export const MANAGEMENT_DEFAULT_LOGIN_PATH = '/system/role'

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

export function getDefaultLoginPath(user = {}) {
  return isManagementIdentity(user.roles || [], user.permissions || [])
    ? MANAGEMENT_DEFAULT_LOGIN_PATH
    : PORTAL_DEFAULT_LOGIN_PATH
}

export function resolvePostLoginPath(user = {}, requestedPath) {
  const defaultPath = getDefaultLoginPath(user)
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
  return isPortalProtectedPath(requestedPath) || isPublicAuthPath(requestedPath) ? defaultPath : requestedPath
}

export function getPublicAuthPaths() {
  return [...PUBLIC_AUTH_PATHS]
}
