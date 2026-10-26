<template>
  <div class="pipeline-page manuscript-page">
    <section class="page-heading">
      <div>
        <p class="eyebrow">后台管理 · 论文生成</p>
        <h1>管网科研论文生成</h1>
        <p class="summary">基于项目描述、关键词、参考文献和自定义章节，生成可编辑的 Markdown 论文草稿。</p>
      </div>
      <div class="heading-actions">
        <el-button :icon="Refresh" :loading="loadingJobs" @click="loadJobs">刷新任务</el-button>
        <el-button type="primary" :icon="DocumentChecked" :loading="generating" @click="handleGenerate">生成论文</el-button>
      </div>
    </section>

    <section class="manuscript-workbench">
      <el-card shadow="never" class="form-card">
        <template #header>
          <div class="card-header">
            <span>生成参数</span>
            <el-tag effect="plain">MANUSCRIPT</el-tag>
          </div>
        </template>

        <el-form label-position="top">
          <el-form-item label="论文题目">
            <div class="title-field">
              <el-input v-model="form.topic" maxlength="120" show-word-limit placeholder="例如：管道本体应力监测技术研究" />
              <el-button :icon="MagicStick" :loading="suggesting" @click="handleSuggestTitles">标题建议</el-button>
            </div>
          </el-form-item>

          <div v-if="suggestedTitles.length" class="title-suggestions">
            <button v-for="title in suggestedTitles" :key="title" type="button" @click="form.topic = title">{{ title }}</button>
          </div>

          <el-row :gutter="12">
            <el-col :xs="24" :sm="12">
              <el-form-item label="模板类型">
                <el-select v-model="form.templateType" class="full-width">
                  <el-option label="综述论文" value="review" />
                  <el-option label="基金申请" value="fund" />
                  <el-option label="重点研发" value="key_research" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :xs="24" :sm="12">
              <el-form-item label="关键词">
                <el-input v-model="keywordText" placeholder="应力监测，磁各向异性，现场验证" />
              </el-form-item>
            </el-col>
          </el-row>

          <el-form-item label="研究描述">
            <el-input
              v-model="form.description"
              type="textarea"
              :rows="5"
              maxlength="1200"
              show-word-limit
              placeholder="说明研究背景、科学问题、工程场景、技术路线和预期成果。"
            />
          </el-form-item>

          <el-form-item label="参考文献">
            <el-input
              v-model="referenceText"
              type="textarea"
              :rows="4"
              placeholder="每行一条参考线索；提交后会随任务保存，正式引用仍需关联平台资料并人工核验。"
            />
          </el-form-item>

          <el-form-item label="生成选项">
            <el-checkbox v-model="form.customOptions.generateFigures">补充图表建议</el-checkbox>
          </el-form-item>
        </el-form>
      </el-card>

      <el-card shadow="never" class="jobs-card">
        <template #header>
          <div class="card-header">
            <span>生成任务</span>
            <small>{{ jobs.length }} 项</small>
          </div>
        </template>

        <el-table v-loading="loadingJobs" :data="jobs" height="360" border @row-click="selectJob">
          <el-table-column prop="topic" label="题目" min-width="210" show-overflow-tooltip />
          <el-table-column prop="status" label="状态" width="95">
            <template #default="{ row }">
              <el-tag :type="row.status === 'completed' ? 'success' : 'warning'" effect="light">{{ statusText(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="progress_pct" label="进度" width="78" align="right">
            <template #default="{ row }">{{ row.progress_pct }}%</template>
          </el-table-column>
          <el-table-column label="操作" width="96" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" :icon="Download" @click.stop="handleExport(row)">导出</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </section>

    <section class="preview-panel">
      <div class="preview-toolbar">
        <div>
          <span>草稿预览</span>
          <small>{{ selectedJob?.job_id || '暂无任务' }}</small>
        </div>
        <el-button :icon="Download" :disabled="!selectedJob" :loading="exporting" @click="handleExport(selectedJob)">导出 Markdown</el-button>
      </div>
      <pre v-if="selectedContent" class="markdown-preview">{{ selectedContent }}</pre>
      <el-empty v-else description="生成论文后在这里查看 Markdown 草稿" />
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { DocumentChecked, Download, MagicStick, Refresh } from '@element-plus/icons-vue'
import {
  exportManuscript,
  generateManuscript,
  getManuscriptJob,
  listManuscriptJobs,
  suggestManuscriptTitles
} from '@/api/pipeline/manuscript'

defineOptions({ name: 'PipelineManuscript' })

const generating = ref(false)
const loadingJobs = ref(false)
const suggesting = ref(false)
const exporting = ref(false)
const jobs = ref([])
const selectedJob = ref(null)
const selectedContent = ref('')
const suggestedTitles = ref([])
const keywordText = ref('应力监测，磁各向异性，现场验证')
const referenceText = ref('')
const form = reactive({
  topic: '管道本体应力监测技术研究',
  description: '围绕长输管道本体应力监测、磁各向异性传感和现场验证形成论文草稿。',
  templateType: 'review',
  customOptions: {
    generateFigures: true
  }
})

const requestPayload = computed(() => ({
  topic: form.topic,
  description: form.description,
  keywords: splitText(keywordText.value),
  providedReferences: splitLines(referenceText.value),
  templateType: form.templateType,
  language: 'zh',
  visualMode: 'direct',
  customOptions: {
    generate_figures: form.customOptions.generateFigures
  }
}))

function splitText(value) {
  return String(value || '')
    .split(/[,，\n]/)
    .map(item => item.trim())
    .filter(Boolean)
}

function splitLines(value) {
  return String(value || '')
    .split(/\n/)
    .map(item => item.trim())
    .filter(Boolean)
}

function statusText(status) {
  return { completed: '已完成', running: '生成中', queued: '排队中', failed: '失败' }[status] || status
}

async function loadJobs() {
  loadingJobs.value = true
  try {
    const res = await listManuscriptJobs({ pageNum: 1, pageSize: 20 })
    jobs.value = res.data.rows || []
    if (!selectedJob.value && jobs.value.length) await selectJob(jobs.value[0])
  } catch (error) {
    ElMessage.warning('暂时无法获取论文生成任务')
  } finally {
    loadingJobs.value = false
  }
}

async function handleGenerate() {
  if (!form.topic.trim()) {
    ElMessage.warning('请先填写论文题目')
    return
  }
  generating.value = true
  try {
    const res = await generateManuscript(requestPayload.value)
    selectedJob.value = res.data
    selectedContent.value = ''
    const finishedJob = await waitForJob(res.data.job_id || res.data.jobId)
    await loadJobs()
    if (finishedJob?.status === 'completed') {
      ElMessage.success('论文草稿已生成')
    } else if (finishedJob?.status === 'failed') {
      ElMessage.warning('论文生成失败，请查看任务状态后重试')
    } else {
      ElMessage.info('论文任务已进入后台队列，可在任务列表中查看进度')
    }
  } catch (error) {
    ElMessage.warning('论文生成失败，请稍后重试')
  } finally {
    generating.value = false
  }
}

async function waitForJob(jobId) {
  if (!jobId) return null
  let latest = selectedJob.value
  for (let attempt = 0; attempt < 30; attempt += 1) {
    const res = await getManuscriptJob(jobId)
    latest = res.data
    selectedJob.value = latest
    selectedContent.value = latest.content || ''
    if (['completed', 'failed', 'cancelled'].includes(latest.status)) return latest
    await new Promise(resolve => window.setTimeout(resolve, 1000))
  }
  return latest
}

async function handleSuggestTitles() {
  suggesting.value = true
  try {
    const res = await suggestManuscriptTitles({
      description: form.description,
      keywords: splitText(keywordText.value)
    })
    suggestedTitles.value = res.data.titles || []
  } catch (error) {
    ElMessage.warning('暂时无法生成标题建议')
  } finally {
    suggesting.value = false
  }
}

async function selectJob(row) {
  if (!row) return
  try {
    const res = await getManuscriptJob(row.job_id)
    selectedJob.value = res.data
    selectedContent.value = res.data.content
  } catch (error) {
    ElMessage.warning('暂时无法读取论文草稿')
  }
}

async function handleExport(row) {
  if (!row) return
  exporting.value = true
  try {
    const res = await exportManuscript(row.job_id)
    downloadMarkdown(res.data.file_name, res.data.content)
    ElMessage.success('论文 Markdown 已导出')
  } catch (error) {
    ElMessage.warning('论文导出失败，请稍后重试')
  } finally {
    exporting.value = false
  }
}

function downloadMarkdown(fileName, content) {
  const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = fileName || '管网科研论文.md'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

onMounted(loadJobs)
</script>

<style scoped>
.heading-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.manuscript-workbench {
  display: grid;
  grid-template-columns: minmax(0, 0.95fr) minmax(420px, 1.05fr);
  gap: 16px;
  margin-bottom: 16px;
}

.form-card,
.jobs-card,
.preview-panel {
  border: 1px solid #d9e2e9;
}

.title-field {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 10px;
  width: 100%;
}

.title-suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: -4px 0 16px;
}

.title-suggestions button {
  max-width: 100%;
  padding: 7px 10px;
  border: 1px solid #cbd9e4;
  background: #f7fafc;
  color: #173d56;
  cursor: pointer;
  font-size: 13px;
}

.full-width {
  width: 100%;
}

.preview-panel {
  background: #fff;
}

.preview-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 16px 18px;
  border-bottom: 1px solid #e2e8ee;
}

.preview-toolbar span,
.preview-toolbar small {
  display: block;
}

.preview-toolbar span {
  color: #173d56;
  font-weight: 700;
}

.preview-toolbar small {
  margin-top: 4px;
  color: #7a8796;
  font-size: 13px;
}

.markdown-preview {
  min-height: 420px;
  max-height: 620px;
  margin: 0;
  padding: 22px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
  color: #243849;
  background: #fbfdff;
  font-family: "Microsoft YaHei", Arial, sans-serif;
  font-size: 14px;
  line-height: 1.85;
}

@media (max-width: 1080px) {
  .manuscript-workbench {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .title-field {
    grid-template-columns: 1fr;
  }

  .preview-toolbar {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
