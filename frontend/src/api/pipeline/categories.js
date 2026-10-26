import request from './request'
import { requireBusinessId } from '@/utils/portal/businessId'

export const listPipelineCategories = () => request({ url: '/pipeline/categories', method: 'get' })
export const createPipelineCategory = data => request({ url: '/pipeline/categories', method: 'post', data })
export const updatePipelineCategory = (id, data) => request({ url: `/pipeline/categories/${encodeURIComponent(requireBusinessId(id))}`, method: 'put', data })
export const deletePipelineCategory = id => request({ url: `/pipeline/categories/${encodeURIComponent(requireBusinessId(id))}`, method: 'delete' })
