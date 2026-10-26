import request from './request'
import { requireBusinessId } from '@/utils/portal/businessId'

// Use the authenticated request client, including the configured API prefix.
export const getReportImageBlob = id => request({
  url: `/pipeline/research/assets/${encodeURIComponent(requireBusinessId(id))}/download`, method: 'get', responseType: 'blob'
})
export const retryReportImage = id => request({
  url: `/pipeline/research/assets/${encodeURIComponent(requireBusinessId(id))}/retry`, method: 'post'
})
