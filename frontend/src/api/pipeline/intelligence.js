import request from '@/utils/request'

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

export function askPipelineKnowledge(question, options = {}) {
  return request({
    url: '/pipeline/knowledge/ask',
    method: 'post',
    data: {
      question,
      documentIds: options.documentIds || [],
      documentTypes: options.documentTypes || []
    }
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
