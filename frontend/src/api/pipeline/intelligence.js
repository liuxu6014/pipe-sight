import { downloadGet } from '@/utils/request'
import request from './request'
import { requireBusinessId } from '@/utils/portal/businessId'

export function getPipelinePortalOverview() {
  return request({ url: '/pipeline/portal/overview', method: 'get' })
}

export function proposePipelineReportRewrite(reportId, data) {
  return request({ url: `/pipeline/research/reports/${requireBusinessId(reportId)}/rewrite`,
    method: 'post', data, timeout: 150000 })
}

export function getPipelineDashboard() {
  return request({
    url: '/pipeline/dashboard',
    method: 'get'
  })
}

export function listPipelineAdminReports(params) {
  return request({ url: '/pipeline/research/admin/reports', method: 'get', params })
}

export function getPipelineContentFilters() {
  return request({ url: '/pipeline/intelligence/filters', method: 'get' })
}

export function listPipelineIntelligence(query) {
  return request({
    url: '/pipeline/intelligence/list',
    method: 'get',
    params: query
  })
}

export function getPipelineIntelligenceDetail(itemId) {
  return request({
    url: `/pipeline/intelligence/${requireBusinessId(itemId)}`,
    method: 'get'
  })
}

export function searchPipelineIntelligence(params) {
  return request({
    url: '/pipeline/search',
    method: 'get',
    params
  })
}

export function searchPipelineResearchMaterials(params) {
  return request({ url: '/pipeline/research/materials', method: 'get', params })
}

export function listPipelineSources() {
  return request({
    url: '/pipeline/sources',
    method: 'get'
  })
}

export function createPipelineSource(data) {
  return request({
    url: '/pipeline/sources',
    method: 'post',
    data
  })
}

export function updatePipelineSource(sourceId, data) {
  return request({
    url: `/pipeline/sources/${requireBusinessId(sourceId)}`,
    method: 'put',
    data
  })
}

export function disablePipelineSource(sourceId) {
  return request({
    url: `/pipeline/sources/${requireBusinessId(sourceId)}`,
    method: 'delete'
  })
}

export function listPipelineTemplates(params) {
  return request({
    url: params?.publishedOnly === true ? '/pipeline/templates/published' : '/pipeline/templates',
    method: 'get',
    params
  })
}

export function createPipelineTemplate(data) {
  return request({
    url: '/pipeline/templates',
    method: 'post',
    data
  })
}

export function updatePipelineTemplate(templateKey, data) {
  return request({
    url: `/pipeline/templates/${requireBusinessId(templateKey)}`,
    method: 'put',
    data
  })
}

export function retirePipelineTemplate(templateKey) {
  return request({
    url: `/pipeline/templates/${requireBusinessId(templateKey)}`,
    method: 'delete'
  })
}

export function listPipelineTasks() {
  return request({
    url: '/pipeline/tasks',
    method: 'get'
  })
}

export function runPipelineTask(taskId, requestId = `manual:${crypto.randomUUID()}`) {
  return request({
    url: `/pipeline/tasks/${encodeURIComponent(requireBusinessId(taskId))}/run`,
    method: 'post',
    data: { requestId }
  })
}

export function getPipelineCollectionRun(runId) {
  return request({
    url: `/pipeline/tasks/runs/${requireBusinessId(runId)}`,
    method: 'get'
  })
}

export function retryPipelineTask(runId, requestId = `manual:${crypto.randomUUID()}`) {
  return request({
    url: `/pipeline/tasks/runs/${encodeURIComponent(requireBusinessId(runId))}/retry`,
    method: 'post',
    data: { requestId }
  })
}

export function stopPipelineCollectionRun(runId) {
  return request({ url: `/pipeline/tasks/runs/${encodeURIComponent(requireBusinessId(runId))}/stop`, method: 'post' })
}

export function listPipelineReports() {
  return request({
    url: '/pipeline/research/reports',
    method: 'get'
  })
}

export function exportPipelineReport(reportId, params) {
  return request({
    url: `/pipeline/research/reports/${encodeURIComponent(requireBusinessId(reportId))}/export`,
    method: 'get',
    params
  })
}

export function searchPipelineDigestCandidates(data) {
  return request({ url: '/pipeline/research/digest-candidates', method: 'post', data })
}

export function listPipelineKnowledgeDocuments() {
  return request({
    url: '/pipeline/knowledge/documents',
    method: 'get'
  })
}

export function uploadPipelineKnowledgeDocument(data) {
  return request({
    url: '/pipeline/knowledge/documents',
    method: 'post',
    data,
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

export function getPipelineKnowledgeDocument(documentId) {
  return request({
    url: `/pipeline/knowledge/documents/${requireBusinessId(documentId)}`,
    method: 'get'
  })
}

export function updatePipelineKnowledgeDocument(documentId, data) {
  return request({
    url: `/pipeline/knowledge/documents/${requireBusinessId(documentId)}`,
    method: 'put',
    data
  })
}

export function downloadPipelineKnowledgeDocument(documentId, filename) {
  return downloadGet(`/pipeline/knowledge/documents/${requireBusinessId(documentId)}/download`, {}, filename || '资料文件')
}

export function reparsePipelineKnowledgeDocument(documentId) {
  return request({
    url: `/pipeline/knowledge/documents/${requireBusinessId(documentId)}/retry`,
    method: 'post'
  })
}

export function deletePipelineKnowledgeDocument(documentId) {
  return request({
    url: `/pipeline/knowledge/documents/${requireBusinessId(documentId)}`,
    method: 'delete'
  })
}

export function getPipelineWorkspace() {
  return request({
    url: '/pipeline/workspace',
    method: 'get'
  })
}

export function savePipelineWorkspaceItem(data) {
  return request({
    url: '/pipeline/workspace/items',
    method: 'post',
    data
  })
}

export function deletePipelineWorkspaceItem(action, itemId) {
  return request({
    url: `/pipeline/workspace/items/${action}/${requireBusinessId(itemId)}`,
    method: 'delete'
  })
}

export function listPipelineResearchJobs() {
  return request({
    url: '/pipeline/research/jobs',
    method: 'get'
  })
}

export function createPipelineResearchJob(data) {
  return request({
    url: '/pipeline/research/jobs',
    method: 'post',
    data
  })
}

export function listPipelineDigestSchedules() {
  return request({
    url: '/pipeline/research/digest-schedules',
    method: 'get'
  })
}

export function createPipelineDigestSchedule(data) {
  return request({
    url: '/pipeline/research/digest-schedules',
    method: 'post',
    data
  })
}

export function updatePipelineDigestSchedule(scheduleId, data) {
  return request({
    url: `/pipeline/research/digest-schedules/${requireBusinessId(scheduleId)}`,
    method: 'put',
    data
  })
}

export function savePipelineDigestScheduleConfig(scheduleId, data) {
  return request({ url: `/pipeline/research/digest-schedules/${requireBusinessId(scheduleId)}/config`, method: 'put', data })
}

export function runPipelineDigestSchedule(scheduleId) {
  return request({
    url: `/pipeline/research/digest-schedules/${requireBusinessId(scheduleId)}/run`,
    method: 'post'
  })
}

export function deletePipelineDigestSchedule(scheduleId) {
  return request({
    url: `/pipeline/research/digest-schedules/${requireBusinessId(scheduleId)}`,
    method: 'delete'
  })
}

export function getPipelineResearchJob(jobId) {
  return request({
    url: `/pipeline/research/jobs/${requireBusinessId(jobId)}`,
    method: 'get'
  })
}

export function cancelPipelineResearchJob(jobId) {
  return request({
    url: `/pipeline/research/jobs/${requireBusinessId(jobId)}/cancel`,
    method: 'post'
  })
}

export function retryPipelineResearchJob(jobId) {
  return request({
    url: `/pipeline/research/jobs/${requireBusinessId(jobId)}/retry`,
    method: 'post'
  })
}

export function listPipelineResearchReports() {
  return request({
    url: '/pipeline/research/reports',
    method: 'get'
  })
}

export function getPipelineResearchReport(reportId) {
  return request({
    url: `/pipeline/research/reports/${requireBusinessId(reportId)}`,
    method: 'get'
  })
}

export function updatePipelineResearchReport(reportId, data) {
  return request({
    url: `/pipeline/research/reports/${requireBusinessId(reportId)}`,
    method: 'put',
    data
  })
}

export function listPipelineResearchReportPublications(reportId) {
  return request({
    url: `/pipeline/research/reports/${requireBusinessId(reportId)}/publications`,
    method: 'get'
  })
}

export function finalizePipelineResearchReport(reportId, data) {
  return request({
    url: '/pipeline/research/reports/' + requireBusinessId(reportId) + '/finalize',
    method: 'post',
    data
  })
}

export function getPipelineResearchReportDiagram(reportId) {
  return request({
    url: `/pipeline/research/reports/${requireBusinessId(reportId)}/diagram`,
    method: 'get'
  })
}

export function updatePipelineResearchReportDiagram(reportId, data) {
  return request({
    url: `/pipeline/research/reports/${requireBusinessId(reportId)}/diagram`,
    method: 'put',
    data
  })
}

export function listPipelineResearchReportVersions(reportId) {
  return request({
    url: `/pipeline/research/reports/${requireBusinessId(reportId)}/versions`,
    method: 'get'
  })
}

export function getPipelineResearchReportVersion(reportId, versionNo) {
  return request({
    url: `/pipeline/research/reports/${requireBusinessId(reportId)}/versions/${versionNo}`,
    method: 'get'
  })
}

export function restorePipelineResearchReportVersion(reportId, versionNo) {
  return request({
    url: `/pipeline/research/reports/${requireBusinessId(reportId)}/versions/${versionNo}/restore`,
    method: 'post'
  })
}

export function exportPipelineResearchReport(reportId, params) {
  return request({
    url: `/pipeline/research/reports/${requireBusinessId(reportId)}/export`,
    method: 'get',
    params
  })
}

export function downloadPipelineResearchReport(reportId, format, params, filename) {
  return downloadGet(`/pipeline/research/reports/${requireBusinessId(reportId)}/export`, {
    ...(params || {}),
    format
  }, filename)
}

export function createPipelineResearchReportExport(reportId, data) {
  return request({
    url: `/pipeline/research/reports/${requireBusinessId(reportId)}/exports`,
    method: 'post',
    data
  })
}

export function listPipelineResearchReportExports(reportId) {
  return request({
    url: `/pipeline/research/reports/${requireBusinessId(reportId)}/exports`,
    method: 'get'
  })
}

export function downloadPipelineResearchReportExport(exportId, filename) {
  return downloadGet(`/pipeline/research/exports/${requireBusinessId(exportId)}/download`, {}, filename)
}
