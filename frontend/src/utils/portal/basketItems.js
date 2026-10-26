import { getCitationPath } from './citationRouting.js'

export function basketItemLabel(item) {
  const path = basketItemPath(item)
  if (path?.startsWith('/portal/papers/')) return '论文'
  if (path?.startsWith('/portal/news/')) return '新闻资讯'
  if (path?.startsWith('/portal/knowledge/')) return '上传资料'
  return item.type === 'report' ? '报告' : '资料'
}

export function basketItemPath(item) {
  return getCitationPath({ sourceId: item.id, type: item.type })
}

export function validateBasketUpload(file) {
  if (!/\.(pdf|docx|md|txt)$/i.test(file.name)) return '仅支持 PDF、DOCX、MD、TXT 文件'
  if (!file.size) return '文件内容为空'
  if (file.size > 16 * 1024 * 1024) return '单个文件不能超过 16MB'
  return ''
}

// Persist the file in the library first; the basket holds only its source ID.
export async function uploadBasketFile(file, { upload, save, refresh }) {
  const error = validateBasketUpload(file)
  if (error) throw new Error(error)
  const data = new FormData()
  data.append('file', file)
  data.append('category', '内部资料')
  data.append('permissionScope', 'private')
  const response = await upload(data)
  const id = response.data?.id
  if (!id) throw new Error('上传响应缺少资料编号，请到资料库确认保存结果')
  let basketError = false
  try {
    await save({ itemId: String(id), itemType: 'material', action: 'basket', title: file.name })
  } catch { basketError = true }
  await refresh()
  return { id: String(id), basketError }
}
