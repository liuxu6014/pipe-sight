<template>
  <div class="pipeline-page">
    <section class="page-heading">
      <div>

        <h1>{{ detail.title || '情报详情' }}</h1>
      </div>
      <el-button :icon="Back" @click="returnToPreviousPage(router, '/pipeline/intelligence')">返回</el-button>
    </section>

    <el-alert v-if="loadError" :title="loadError" type="error" show-icon :closable="false">
      <template #default><el-button v-if="detailId" plain type="primary" :disabled="loading" @click="loadDetail">重新加载</el-button></template>
    </el-alert>
    <el-row v-else :gutter="16">
      <el-col :xs="24" :lg="24">
        <el-card v-loading="loading" shadow="never" class="panel-card">
          <template #header>
            <div class="card-header">
              <span>{{ detail.category === 'paper' ? '论文内容' : '资讯内容' }}</span>
              <div class="card-tags">
                <el-tag :type="categoryType(detail.category)" effect="light">{{ categoryText(detail.category) }}</el-tag>
                <el-tag v-if="detail.category_name" type="info" effect="plain">{{ detail.category_name }}</el-tag>
                <el-tag v-if="sourceLabel(detail)" type="info" effect="plain">{{ sourceLabel(detail) }}</el-tag>
                <el-tag v-if="formatBusinessTime(detail.publish_time)" type="info" effect="plain">{{ formatBusinessTime(detail.publish_time) }}</el-tag>
                <el-tag v-if="detail.category === 'paper' && detail.journal" type="info" effect="plain">{{ detail.journal }}</el-tag>
                <el-tag v-if="detail.category === 'paper' && paperAuthors(detail)" type="info" effect="plain">{{ paperAuthors(detail) }}</el-tag>
              </div>
            </div>
          </template>
          <section class="detail-section">
            <h2 class="section-title"><el-icon class="section-icon"><Memo /></el-icon>摘要</h2>
            <p class="content-text">{{ detail.category === 'paper' ? detail.abstract || detail.summary || '摘要未提供' : detail.summary || '摘要未提供' }}</p>
          </section>
          <section v-if="detail.category !== 'paper'" class="detail-section">
            <h2 class="section-title"><el-icon class="section-icon"><Notebook /></el-icon>全文</h2>
            <p class="content-text">{{ detail.content_original || detail.contentOriginal || detail.content || '当前记录未提供全文' }}</p>
          </section>
          <section v-if="savedTranslation" class="detail-section">
            <h2 class="section-title"><el-icon class="section-icon"><Document /></el-icon>已保存中文</h2>
            <p class="content-text">{{ savedTranslation }}</p>
          </section>
          <section class="detail-section">
            <ContentInsights :item="detail" :kind="detail.category === 'paper' ? 'paper' : 'news'" />
          </section>
        </el-card>
        <ContentEntities :entities="detail.entities || []" />

      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { returnToPreviousPage } from '@/utils/portal/openContent'
import { formatBusinessTime } from '@/utils/portal/businessTime'
import { computed, onActivated, onBeforeUnmount, onDeactivated, onMounted, ref, watch } from 'vue'
import { Back, Document, Memo, Notebook } from '@element-plus/icons-vue'
import { useRoute, useRouter } from 'vue-router'
import { getPipelineIntelligenceDetail } from '@/api/pipeline/intelligence'
import ContentEntities from '@/views/portal/components/ContentEntities.vue'
import ContentInsights from '@/views/portal/components/ContentInsights.vue'

defineOptions({ name: 'PipelineIntelligenceDetail' })

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const loadError = ref('')
const detail = ref({ tags: [] })
const savedTranslation = computed(() => detail.value.category === 'paper' ? detail.value.abstractZh || detail.value.abstract_zh : detail.value.contentZh || detail.value.content_zh)
const detailId = computed(() => typeof route.query.id === 'string' ? route.query.id.trim() : '')
let active = false
let disposed = false
let requestVersion = 0

function isDetailRoute() {
  return route.path === '/pipeline/intelligence/detail'
}

function resetDetail() {
  detail.value = { tags: [] }
  loadError.value = ''
  loading.value = false
}

function invalidateDetail() {
  requestVersion++
  resetDetail()
}

function categoryText(category) {
  return { news: '新闻', wechat: '公众号', paper: '论文' }[category] || category
}

function categoryType(category) {
  return { news: 'primary', wechat: 'success', paper: 'warning' }[category] || 'info'
}

function sourceLabel(item) {
  const source = item?.source
  if (!source) return ''
  try {
    const url = new URL(source)
    return url.hostname || source
  } catch {
    return source
  }
}

function paperAuthors(item) {
  if (!Array.isArray(item?.authors)) return item?.authors || ''
  return item.authors.join(' · ')
}

async function loadDetail() {
  if (disposed || !active || !isDetailRoute()) return
  const version = ++requestVersion
  const id = detailId.value
  resetDetail()
  if (!id) {
    loadError.value = '缺少情报编号，请返回列表重新选择'
    return
  }
  loading.value = true
  const isCurrent = () => !disposed && active && isDetailRoute()
    && version === requestVersion && detailId.value === id
  try {
    const res = await getPipelineIntelligenceDetail(id)
    if (!isCurrent()) return
    if (!res?.data || String(res.data.id) !== id) throw new Error('情报编号不匹配')
    detail.value = { ...res.data, tags: Array.isArray(res.data.tags) ? res.data.tags : [] }
  } catch {
    if (isCurrent()) loadError.value = '暂时无法获取情报详情，请检查编号、权限或稍后重试'
  } finally {
    if (isCurrent()) loading.value = false
  }
}

function activateDetail() {
  if (active || disposed) return
  active = true
  void loadDetail()
}

watch(() => [route.path, route.query.id], () => {
  if (!active || disposed) return
  if (isDetailRoute()) void loadDetail()
  else invalidateDetail()
}, { flush: 'sync' })

onMounted(activateDetail)
onActivated(activateDetail)
onDeactivated(() => { active = false; invalidateDetail() })
onBeforeUnmount(() => { active = false; disposed = true; invalidateDetail() })
</script>

<style scoped>
.summary,
.content-text {
  color: #526b7d;
  line-height: 1.8;
}

.content-text {
  margin: 0;
  white-space: pre-line;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.card-tags {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.detail-section {
  margin-bottom: 24px;
}

.section-title {
  margin: 0 0 10px;
  font-size: 15px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  display: flex;
  align-items: center;
  gap: 6px;
}

.section-icon {
  color: var(--el-text-color-secondary);
}
</style>
