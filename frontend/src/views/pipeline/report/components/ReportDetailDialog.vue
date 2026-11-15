<template>
  <el-dialog :model-value="modelValue" title="成果详情" width="min(1000px, calc(100vw - 32px))" align-center append-to-body class="management-report-dialog" @update:model-value="emit('update:modelValue', $event)">
    <el-skeleton v-if="loading" :rows="8" animated aria-label="正在加载成果详情" />
    <el-alert v-else-if="loadError" :title="loadError" type="error" show-icon :closable="false"><template #default><el-button @click="loadDetail">重新加载</el-button></template></el-alert>
    <article v-else-if="report" class="management-report" aria-label="成果正文，只读">
      <header>
        <h1>{{ report.title }}</h1>
        <div class="management-report-meta">
          <el-tag :type="getReportStatusMeta(report.status).type" effect="light">{{ getReportStatusMeta(report.status).label }}</el-tag>
          <span v-if="report.version">{{ report.version }}</span>
          <span v-if="report.updatedAt || report.updated_at">更新于 {{ report.updatedAt || report.updated_at }}</span>
          <span>只读查看</span>
        </div>
      </header>
      <section v-for="(section, index) in sections" :key="index" class="management-report-section">
        <h2>{{ section.title }}</h2>
        <DigestSectionContent v-if="isDigest" :content="section.content" />
        <template v-else>
          <p v-for="(paragraph, paragraphIndex) in section.content.split(/\n+/).filter(line => line.trim())" :key="paragraphIndex">
            <template v-for="(part, partIndex) in reportCitationParts(paragraph, section.title, report.citations?.length || 0)" :key="partIndex"><sup v-if="part.citation">{{ part.text }}</sup><template v-else>{{ part.text }}</template></template>
          </p>
        </template>
      </section>
      <el-empty v-if="!sections.length" description="该成果尚未生成正文" :image-size="72" />
    </article>
    <template #footer><el-button @click="emit('update:modelValue', false)">关闭</el-button></template>
  </el-dialog>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { getPipelineResearchReport } from '@/api/pipeline/intelligence'
import { getReportStatusMeta } from '@/utils/pipeline/reportPresentation'
import { reportCitationParts } from '@/utils/portal/reportDocument'
import { isDigestType } from '@/views/portal/utils/routing'
import DigestSectionContent from '@/views/portal/components/DigestSectionContent.vue'

const props = defineProps({ modelValue: Boolean, reportId: { type: String, default: '' } })
const emit = defineEmits(['update:modelValue'])
const report = ref(null)
const loading = ref(false)
const loadError = ref('')
let requestVersion = 0
const isDigest = computed(() => isDigestType(report.value?.reportType || report.value?.type))
const sections = computed(() => {
  const current = report.value
  if (!current) return []
  const rows = Array.isArray(current.sections) ? current.sections.filter(section => String(section.content || '').trim()) : []
  if (rows.length) return rows.map(section => ({ title: section.title || '正文', content: String(section.content) }))
  return current.content?.trim() ? [{ title: '正文', content: current.content }] : []
})

async function loadDetail() {
  const request = ++requestVersion
  report.value = null
  loadError.value = ''
  loading.value = false
  if (!props.modelValue || !props.reportId) return
  loading.value = true
  try {
    const response = await getPipelineResearchReport(props.reportId)
    if (request !== requestVersion) return
    if (String(response.data?.id) !== props.reportId) throw new Error('成果详情返回编号不匹配')
    report.value = response.data
  } catch (error) {
    if (request === requestVersion) loadError.value = error?.msg || error?.message || '成果详情暂时无法加载，请重试'
  } finally {
    if (request === requestVersion) loading.value = false
  }
}
watch(() => [props.modelValue, props.reportId], loadDetail, { immediate: true })
onBeforeUnmount(() => { requestVersion++ })
</script>

<style scoped>
.management-report { color: var(--el-text-color-primary); overflow-wrap: anywhere; }
.management-report > header { padding-bottom: 20px; border-bottom: 1px solid var(--el-border-color-lighter); }
.management-report h1 { margin: 0 0 16px; font-size: 24px; line-height: 1.5; }
.management-report-meta { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; color: var(--el-text-color-secondary); font-size: 13px; }
.management-report-section { margin-top: 28px; }
.management-report-section h2 { margin: 0 0 16px; font-size: 18px; line-height: 1.6; }
.management-report-section p { margin: 12px 0; white-space: pre-wrap; line-height: 1.85; font-size: 16px; }
.management-report-section sup { color: var(--el-color-primary); font-size: 12px; }
</style>
