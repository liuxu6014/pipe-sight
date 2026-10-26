import request from '@/utils/request'
import { requireBusinessId, validateBusinessInput, normalizeBusinessData } from '@/utils/portal/businessId'
import { normalizeBusinessTimes } from '@/utils/portal/businessTime'

export default async function pipelineRequest(options) {
  // Every dynamic resource segment in these APIs is a business entity key;
  // version numbers are decimal too. UUID request/execution tokens stay in bodies.
  const parts = options.url.split('/')
  for (let index = 0; index < parts.length; index++) {
    if (['intelligence', 'sources', 'categories', 'templates', 'jobs', 'tasks', 'reports', 'runs', 'digest-schedules', 'documents', 'assets', 'exports'].includes(parts[index]) && parts[index + 1] && !['list', 'published', 'materials', 'digest-candidates', 'items', 'runs'].includes(parts[index + 1])) {
      parts[index + 1] = requireBusinessId(decodeURIComponent(parts[index + 1]))
    }
    if (parts[index] === 'items' && parts[index + 2]) parts[index + 2] = requireBusinessId(decodeURIComponent(parts[index + 2]))
  }
  const response = await request({ ...options, url: parts.join('/'), data: validateBusinessInput(options.data), params: validateBusinessInput(options.params) })
  return options.responseType === 'blob' ? response : normalizeBusinessTimes(normalizeBusinessData(response))
}
