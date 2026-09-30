<template>
  <div class="ps-page">
    <PortalPageHeader title="全局搜索" description="跨资讯、论文、内部资料和我的报告统一检索。">
      <template #actions><el-button @click="clearFilters">清除筛选</el-button></template>
    </PortalPageHeader>

    <form class="ps-search-hero" @submit.prevent="applyKeyword">
      <Search />
      <input v-model.trim="draftKeyword" autofocus placeholder="输入题名、作者、DOI、标签或资料名称" />
      <el-button native-type="submit" type="primary">搜索</el-button>
    </form>

    <div class="ps-search-summary">找到 <strong>{{ filteredResults.length }}</strong> 条与“{{ queryKeyword || '全部内容' }}”相关的结果</div>

    <div class="ps-search-layout">
      <aside class="ps-filter-panel">
        <h3><Filter />筛选条件</h3>
        <label>时间范围<el-select v-model="dateRange"><el-option label="全部时间" value="all" /><el-option label="近一周" value="week" /><el-option label="近一年" value="year" /></el-select></label>
        <label>内容来源<el-select v-model="source"><el-option label="全部来源" value="all" /><el-option label="公开来源" value="public" /><el-option label="内部资料" value="internal" /></el-select></label>
        <label>技术方向<div class="ps-check-list"><el-checkbox v-for="item in ['检测技术', '应力监测', '完整性管理', '腐蚀防护']" :key="item" v-model="directions" :value="item">{{ item }}</el-checkbox></div></label>
      </aside>

      <section class="ps-results-panel">
        <div class="ps-tabs-line">
          <button v-for="tab in tabs" :key="tab.value" type="button" :class="{ 'is-active': activeType === tab.value }" @click="activeType = tab.value">{{ tab.label }} <span>{{ countByType(tab.value) }}</span></button>
        </div>
        <div v-if="filteredResults.length" class="ps-result-list">
          <article v-for="result in filteredResults" :key="`${result.type}-${result.id}`" class="ps-result-card">
            <div class="ps-result-type">{{ result.typeLabel }}</div>
            <div class="ps-result-body">
              <button type="button" class="ps-result-title" @click="openResult(result)">{{ result.title }}</button>
              <p>{{ result.summary }}</p>
              <div class="ps-meta-row"><span>{{ result.meta }}</span><span v-for="tag in result.tags" :key="tag" class="ps-tag">{{ tag }}</span></div>
            </div>
            <div class="ps-result-actions"><el-button text @click="favorite(result)">{{ portalStore.isFavorite(result.id) ? '已收藏' : '收藏' }}</el-button><el-button type="primary" plain @click="add(result)">加入资料篮</el-button></div>
          </article>
        </div>
        <PortalEmptyState v-else title="没有找到匹配结果" description="请减少筛选条件或尝试同义关键词。" action-label="清除筛选" @action="clearFilters" />
      </section>

      <aside class="ps-related-panel"><h3>相关主题</h3><button v-for="topic in topics.slice(0, 5)" :key="topic.name" type="button" @click="searchTopic(topic.name)"><span>{{ topic.name }}</span><b>{{ topic.count }}</b></button><h3>建议关键词</h3><div class="ps-keyword-cloud"><button v-for="word in ['缺陷智能识别', '磁各向异性', '高后果区', '数字孪生']" :key="word" type="button" @click="searchTopic(word)">{{ word }}</button></div></aside>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Filter, Search } from '@element-plus/icons-vue'
import PortalPageHeader from '../components/PortalPageHeader.vue'
import PortalEmptyState from '../components/PortalEmptyState.vue'
import usePortalStore from '@/store/modules/portal'
import { topics as fallbackTopics } from '../data'
import { getPortalReportPath } from '../utils/routing'

const route = useRoute()
const router = useRouter()
const portalStore = usePortalStore()
const draftKeyword = ref(String(route.query.q || ''))
const queryKeyword = ref(draftKeyword.value)
const activeType = ref('all')
const dateRange = ref('all')
const source = ref('all')
const directions = ref([])
const topics = computed(() => portalStore.hotTopics.length ? portalStore.hotTopics : fallbackTopics)
const tabs = [{ label: '全部', value: 'all' }, { label: '资讯', value: 'news' }, { label: '论文', value: 'paper' }, { label: '内部资料', value: 'document' }, { label: '我的报告', value: 'report' }]
const allResults = computed(() => [
  ...portalStore.newsItems.map(item => ({ id: item.id, type: 'news', typeLabel: '科技资讯', title: item.title, summary: item.summary, meta: `${item.source} · ${item.time}`, tags: item.tags || [], sourceKind: 'public', publishedAt: item.publishTime || item.time, path: `/portal/news/${item.id}` })),
  ...portalStore.paperItems.map(item => ({ id: item.id, type: 'paper', typeLabel: '论文', title: item.titleZh, summary: item.abstract, meta: `${item.journal} · ${item.year} · ${item.doi}`, tags: item.keywords || [], sourceKind: 'public', publishedAt: `${item.year}-01-01`, path: `/portal/papers/${item.id}` })),
  ...portalStore.knowledgeDocuments.map(item => ({ id: item.id, type: 'document', typeLabel: '内部资料', title: item.name, summary: item.summary, meta: `${item.owner} · ${item.permission} · ${item.pages}页`, tags: item.tags || [], sourceKind: 'internal', publishedAt: item.updatedAt, path: `/portal/knowledge/${item.id}` })),
  ...portalStore.researchReports.map(item => ({ id: item.id, type: 'report', typeLabel: '我的报告', title: item.title, summary: `${item.type}，当前版本 ${item.version}，共 ${item.words} 字。`, meta: `${item.status} · ${item.updatedAt}`, tags: [item.type], sourceKind: 'internal', publishedAt: item.updatedAt, path: getPortalReportPath(item) })),
  ...portalStore.digestReports.map(item => ({ id: item.id, type: 'report', typeLabel: '情报简报', title: item.title, summary: `${item.type}，当前版本 ${item.version}，覆盖 ${item.sources} 条来源。`, meta: `${item.status} · ${item.updatedAt}`, tags: [item.type], sourceKind: 'internal', publishedAt: item.period || item.updatedAt, path: getPortalReportPath(item) }))
])
const filteredResults = computed(() => {
  return allResults.value.filter(item => (activeType.value === 'all' || item.type === activeType.value) && matchesCommonFilters(item))
})

watch(() => route.query.q, value => { draftKeyword.value = String(value || ''); queryKeyword.value = draftKeyword.value })
function applyKeyword() { queryKeyword.value = draftKeyword.value; router.replace({ query: draftKeyword.value ? { q: draftKeyword.value } : {} }) }
function parseResultDate(value) {
  const text = String(value || '').trim()
  if (!text) return 0
  if (text.includes('今天')) return Date.now()
  if (text.includes('昨天')) return Date.now() - 24 * 60 * 60 * 1000
  const normalized = /^\d{2}-\d{2}/.test(text) ? `${new Date().getFullYear()}-${text}` : text
  const timestamp = new Date(normalized.replace(/\./g, '-')).getTime()
  return Number.isNaN(timestamp) ? 0 : timestamp
}
function matchesCommonFilters(item) {
  const q = queryKeyword.value.toLowerCase()
  const searchText = `${item.title}${item.summary}${item.meta}${item.tags.join('')}`
  if (q && !searchText.toLowerCase().includes(q)) return false
  if (source.value !== 'all' && item.sourceKind !== source.value) return false
  if (directions.value.length && !directions.value.some(value => searchText.includes(value))) return false
  if (dateRange.value !== 'all') {
    const timestamp = parseResultDate(item.publishedAt)
    const days = dateRange.value === 'week' ? 7 : 365
    if (!timestamp || Date.now() - timestamp > days * 24 * 60 * 60 * 1000) return false
  }
  return true
}
function countByType(type) { return allResults.value.filter(item => (type === 'all' || item.type === type) && matchesCommonFilters(item)).length }
function openResult(result) { router.push(result.path) }
function add(result) { ElMessage.success(portalStore.addToBasket(result) ? '已加入资料篮' : '资料已在资料篮中') }
function favorite(result) { portalStore.toggleFavorite(result.id); ElMessage.success(portalStore.isFavorite(result.id) ? '已收藏' : '已取消收藏') }
function clearFilters() { activeType.value = 'all'; dateRange.value = 'all'; source.value = 'all'; directions.value = []; draftKeyword.value = ''; queryKeyword.value = ''; router.replace({ query: {} }) }
function searchTopic(value) { draftKeyword.value = value; applyKeyword() }
</script>
