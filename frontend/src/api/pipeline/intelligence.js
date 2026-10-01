import request, { downloadGet } from '@/utils/request'

export function getPipelineDashboard() {
  return request({
    url: '/pipeline/dashboard',
    method: 'get'
  })
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
    url: `/pipeline/intelligence/${itemId}`,
    method: 'get'
  })
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
    url: `/pipeline/sources/${sourceId}`,
    method: 'put',
    data
  })
}

export function disablePipelineSource(sourceId) {
  return request({
    url: `/pipeline/sources/${sourceId}`,
    method: 'delete'
  })
}

export function listPipelineTemplates(params) {
  return request({
    url: '/pipeline/templates',
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
    url: `/pipeline/templates/${templateKey}`,
    method: 'put',
    data
  })
}

export function publishPipelineTemplate(templateKey) {
  return request({
    url: `/pipeline/templates/${templateKey}/publish`,
    method: 'post'
  })
}

export function retirePipelineTemplate(templateKey) {
  return request({
    url: `/pipeline/templates/${templateKey}`,
    method: 'delete'
  })
}

export function listPipelineTasks() {
  return request({
    url: '/pipeline/tasks',
    method: 'get'
  })
}

export function runPipelineTask(taskId) {
  return request({
    url: `/pipeline/tasks/${taskId}/run`,
    method: 'post'
  })
}

export function dispatchPipelineHandoff(runId) {
  return request({
    url: `/pipeline/tasks/runs/${runId}/handoff`,
    method: 'post'
  })
}

export function syncPipelineHandoff(runId) {
  return request({
    url: `/pipeline/tasks/runs/${runId}/handoff/sync`,
    method: 'post'
  })
}

export function listPipelinePrompts(scene) {
  return request({
    url: '/pipeline/prompts',
    method: 'get',
    params: scene ? { scene } : undefined
  })
}

export function savePipelinePrompt(data) {
  return request({
    url: '/pipeline/prompts',
    method: 'post',
    data
  })
}

export function testPipelinePrompt(promptKey) {
  return request({
    url: `/pipeline/prompts/${promptKey}/test`,
    method: 'post'
  })
}

export function publishPipelinePrompt(promptKey) {
  return request({
    url: `/pipeline/prompts/${promptKey}/publish`,
    method: 'post'
  })
}

export function listPipelineReports() {
  return request({
    url: '/pipeline/reports',
    method: 'get'
  })
}

export function exportPipelineReport(reportId) {
  return request({
    url: `/pipeline/reports/${reportId}/export`,
    method: 'get'
  })
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
    url: `/pipeline/knowledge/documents/${documentId}`,
    method: 'get'
  })
}

export function downloadPipelineKnowledgeDocument(documentId, filename) {
  return downloadGet(`/pipeline/knowledge/documents/${documentId}/download`, {}, filename || '资料文件')
}

export function reparsePipelineKnowledgeDocument(documentId) {
  return request({
    url: `/pipeline/knowledge/documents/${documentId}/retry`,
    method: 'post'
  })
}

export function deletePipelineKnowledgeDocument(documentId) {
  return request({
    url: `/pipeline/knowledge/documents/${documentId}`,
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
    url: `/pipeline/workspace/items/${action}/${itemId}`,
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

export function getPipelineResearchJob(jobId) {
  return request({
    url: `/pipeline/research/jobs/${jobId}`,
    method: 'get'
  })
}

export function cancelPipelineResearchJob(jobId) {
  return request({
    url: `/pipeline/research/jobs/${jobId}/cancel`,
    method: 'post'
  })
}

export function retryPipelineResearchJob(jobId) {
  return request({
    url: `/pipeline/research/jobs/${jobId}/retry`,
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
    url: `/pipeline/research/reports/${reportId}`,
    method: 'get'
  })
}

export function updatePipelineResearchReport(reportId, data) {
  return request({
    url: `/pipeline/research/reports/${reportId}`,
    method: 'put',
    data
  })
}

export function getPipelineResearchReportDiagram(reportId) {
  return request({
    url: `/pipeline/research/reports/${reportId}/diagram`,
    method: 'get'
  })
}

export function updatePipelineResearchReportDiagram(reportId, data) {
  return request({
    url: `/pipeline/research/reports/${reportId}/diagram`,
    method: 'put',
    data
  })
}

export function listPipelineResearchReportVersions(reportId) {
  return request({
    url: `/pipeline/research/reports/${reportId}/versions`,
    method: 'get'
  })
}

export function getPipelineResearchReportVersion(reportId, versionNo) {
  return request({
    url: `/pipeline/research/reports/${reportId}/versions/${versionNo}`,
    method: 'get'
  })
}

export function restorePipelineResearchReportVersion(reportId, versionNo) {
  return request({
    url: `/pipeline/research/reports/${reportId}/versions/${versionNo}/restore`,
    method: 'post'
  })
}

export function exportPipelineResearchReport(reportId) {
  return request({
    url: `/pipeline/research/reports/${reportId}/export`,
    method: 'get'
  })
}
