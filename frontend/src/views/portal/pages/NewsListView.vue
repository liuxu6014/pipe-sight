<template>
  <div class="ps-page">
    <PortalPageHeader title="资讯列表">
      <template #actions><el-button :icon="Collection" @click="router.push('/portal/research/create')">资料篮 {{ portalStore.basketCount }}</el-button></template>
    </PortalPageHeader>
    <div class="ps-toolbar">
      <div class="ps-search-inline"><Search /><input v-model.trim="keyword" placeholder="搜索标题、来源、摘要或标签" /></div>
      <el-select v-model="activeCategory" class="ps-news-category-select" aria-label="资讯分类" style="width: 150px"><el-option v-for="category in categories" :key="category" :label="category === '全部' ? '全部分类' : category" :value="category" /></el-select>
      <el-select v-model="sourceType" style="width: 150px"><el-option label="全部来源" value="全部" /><el-option label="新闻网站" value="新闻网站" /><el-option label="微信公众号" value="微信公众号" /></el-select>
      <el-select v-model="importance" style="width: 130px"><el-option label="全部等级" value="全部" /><el-option label="重点" value="重点" /><el-option label="一般" value="一般" /></el-select>
      <div class="ps-view-switch"><button type="button" :class="{ 'is-active': viewMode === 'list' }" @click="viewMode = 'list'"><List /></button><button type="button" :class="{ 'is-active': viewMode === 'card' }" @click="viewMode = 'card'"><Grid /></button></div>
    </div>
    <div class="ps-content-with-aside">
      <section :class="['ps-news-list', { 'is-card': viewMode === 'card' }]">
        <article v-for="item in pagedNews" :key="item.id" class="ps-news-card">
          <div class="ps-news-card-top"><span class="ps-source-badge">{{ item.sourceType }}</span><time>{{ item.time }}</time><span class="ps-importance" :class="{ 'is-key': item.importance === '重点' }">{{ item.importance }}</span></div>
          <button type="button" class="ps-news-title" @click="router.push(`/portal/news/${item.id}`)">{{ item.title }}</button>
          <p>{{ item.summary }}</p>
          <div class="ps-tag-row"><button v-for="tag in item.tags" :key="tag" type="button" class="ps-tag" @click="keyword = tag">{{ tag }}</button></div>
          <div class="ps-news-card-footer"><span>{{ item.source }} · {{ item.category }}</span><div><el-button text @click="toggleFavorite(item)"><StarFilled v-if="portalStore.isFavorite(item.id)" /><Star v-else />{{ portalStore.isFavorite(item.id) ? '已收藏' : '收藏' }}</el-button><el-button type="primary" plain @click="addToBasket(item)">加入资料篮</el-button></div></div>
        </article>
        <PortalEmptyState v-if="!filteredNews.length" title="没有匹配的资讯" description="请调整分类、来源或搜索关键词。" action-label="重置筛选" @action="resetFilters" />
        <div v-else class="ps-pagination" aria-label="资讯列表分页">
          <el-pagination
            v-model:current-page="currentPage"
            v-model:page-size="pageSize"
            :page-sizes="[5, 10, 20]"
            :total="filteredNews.length"
            layout="total, sizes, prev, pager, next, jumper"
            background
            @size-change="handlePageSizeChange"
            @current-change="handlePageChange"
          />
        </div>
      </section>
      <aside class="ps-news-aside">
        <section class="ps-panel"><h3>热门主题</h3><button v-for="topic in topics.slice(0, 5)" :key="topic.name" type="button" @click="keyword = topic.name"><span>{{ topic.name }}</span><b>{{ topic.heat }}</b></button></section>
        <section class="ps-panel"><h3>重点来源</h3><div class="ps-source-stat" v-for="item in ['能源科技观察', '管道技术前沿', '国际管道研究中心']" :key="item"><span>{{ item }}</span><small>持续更新</small></div></section>
        <section class="ps-panel ps-news-overview"><h3>资讯概览</h3><div v-for="item in overviewStats" :key="item.label" class="ps-overview-stat"><span>{{ item.label }}</span><strong>{{ item.value }}{{ item.unit }}</strong><small>{{ item.note }}</small></div></section>
      </aside>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Collection, Grid, List, Search, Star, StarFilled } from '@element-plus/icons-vue'
import PortalPageHeader from '../components/PortalPageHeader.vue'
import PortalEmptyState from '../components/PortalEmptyState.vue'
import usePortalStore from '@/store/modules/portal'

const router = useRouter()
const portalStore = usePortalStore()
const keyword = ref('')
const sourceType = ref('全部')
const importance = ref('全部')
const activeCategory = ref('全部')
const viewMode = ref('list')
const currentPage = ref(1)
const pageSize = ref(5)
const newsItems = computed(() => portalStore.newsItems)
const topics = computed(() => portalStore.hotTopics)
const categories = ['全部', '管网安全', '检测技术', '腐蚀防护', '应力监测', '智能巡检', '数字孪生']
const filteredNews = computed(() => newsItems.value.filter(item => (activeCategory.value === '全部' || item.category === activeCategory.value) && (sourceType.value === '全部' || item.sourceType === sourceType.value) && (importance.value === '全部' || item.importance === importance.value) && (!keyword.value || `${item.title}${item.summary}${item.source}${(item.tags || []).join('')}`.includes(keyword.value))))
const pagedNews = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return filteredNews.value.slice(start, start + pageSize.value)
})
const overviewStats = computed(() => [
  { label: '当前结果', value: filteredNews.value.length, unit: ' 条', note: '按当前筛选条件' },
  { label: '重点资讯', value: filteredNews.value.filter(item => item.importance === '重点').length, unit: ' 条', note: '建议优先阅读' },
  { label: '关注主题', value: topics.value.length, unit: ' 个', note: '持续跟踪方向' },
  { label: '资料篮', value: portalStore.basketCount, unit: ' 条', note: '可用于科研生成' }
])
watch([keyword, sourceType, importance, activeCategory], () => {
  currentPage.value = 1
})
function addToBasket(item) { ElMessage.success(portalStore.addToBasket(item) ? '已加入资料篮' : '资料已在资料篮中') }
function toggleFavorite(item) { portalStore.toggleFavorite(item.id) }
function handlePageSizeChange(size) {
  pageSize.value = size
  currentPage.value = 1
}
function handlePageChange(page) {
  currentPage.value = page
}
function resetFilters() { keyword.value = ''; sourceType.value = '全部'; importance.value = '全部'; activeCategory.value = '全部' }
</script>
