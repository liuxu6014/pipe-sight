import request from '@/utils/request'

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
    url: `/manuscript/jobs/${jobId}`,
    method: 'get'
  })
}

export function exportManuscript(jobId) {
  return request({
    url: `/manuscript/jobs/${jobId}/export`,
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
