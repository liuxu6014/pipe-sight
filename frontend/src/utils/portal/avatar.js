export function validateAvatarFile(file) {
  if (!file || !['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) return '请选择 JPG、PNG 或 WebP 图片'
  if (!file.size || file.size > 5 * 1024 * 1024) return '图片不能为空，且大小不能超过 5 MB'
  return ''
}

export function avatarUrl(value, base = '') {
  const path = String(value || '').trim()
  if (/^https?:\/\//i.test(path)) return path
  if (!path.startsWith('/') || path.startsWith('//')) return ''
  const prefix = base.replace(/\/$/, '')
  return prefix && !path.startsWith(`${prefix}/`) ? `${prefix}${path}` : path
}
