// API DTO helpers; never infer image generation from image input support.
export function modelCapabilities(model = {}) {
  const value = model.capabilities
  return Array.isArray(value) ? value : Object.keys(value || {}).filter(key => value[key] === true)
}

export function modelEnabled(model = {}) {
  return model.isEnabled ?? model.is_enabled ?? (model.status === '0')
}

export function modelsFor(models, capability) {
  return models.filter(model => modelEnabled(model) && modelCapabilities(model).includes(capability))
}

export function templateGenerationError(template, { images = false } = {}) {
  if (!template) return '请选择可用模板'
  if (!(template.modelId ?? template.model_id) || template.modelConfigured === false) {
    return '当前模板未配置可用的文本生成模型，请联系管理员配置后再生成；仍可浏览资料和选择模板。'
  }
  const imageConfig = template.imageConfig ?? template.image_config ?? {}
  if ((images || imageConfig.enabled === true || imageConfig.isEnabled === true) &&
      (!(template.imageModelId ?? template.image_model_id) || template.imageModelConfigured === false)) {
    return '当前模板未配置可用的图片生成模型，请联系管理员配置后再生成配图。'
  }
  return ''
}

export function sourceEnabled(source = {}) {
  return source.isEnabled ?? source.is_enabled ?? source.enabled ?? (source.status === 'enabled')
}

export function runId(row = {}) {
  return row.latestRunId || row.latest_run_id || row.runId || row.run_id || ''
}

export function collectionStatusText(status) {
  return ({ waiting: '待运行', queued: '排队中', running: '运行中', stopping: '正在停止', success: '成功', failed: '失败', cancelled: '已取消' })[status] || status || '暂无运行'
}

export function stopResultMessage(run = {}) {
  if (run.status === 'cancelled') return '本次采集已取消'
  if (run.status === 'stopping') return '已请求停止，等待采集进程确认退出'
  return `当前运行状态：${collectionStatusText(run.status)}`
}

export function categoryPayload(form) {
  if (!form.name?.trim() || !form.prompt?.trim()) throw new Error('请填写类别名称和分类提示词')
  if (form.isEnabled && !form.modelId) throw new Error('启用类别前请选择文本生成模型；未配置时可保存为停用')
  return { name: form.name.trim(), prompt: form.prompt.trim(), modelId: form.modelId || null,
    appliesTo: form.appliesTo || 'all', sortOrder: form.sortOrder ?? 0, isEnabled: Boolean(form.isEnabled) }
}
