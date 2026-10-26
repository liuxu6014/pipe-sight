import request from './request'
import { requireBusinessId } from '@/utils/portal/businessId'

export function generateManuscript(data) {
  return request({
    url: '/manuscript/generate',
    method: 'post',
    data
  })
}

export function listManuscriptJobs(query) {
  return request({
    url: '/manuscript/jobs',
    method: 'get',
    params: query
  })
}

export function getManuscriptJob(jobId) {
  return request({
    url: `/manuscript/jobs/${requireBusinessId(jobId)}`,
    method: 'get'
  })
}

export function exportManuscript(jobId) {
  return request({
    url: `/manuscript/jobs/${requireBusinessId(jobId)}/export`,
    method: 'get'
  })
}

export function suggestManuscriptTitles(data) {
  return request({
    url: '/manuscript/titles/suggest',
    method: 'post',
    data
  })
}
