<template>
  <div class="pipeline-page intelligence-page ws-list-page">
    <el-card shadow="never" class="filter-card">
      <el-form :model="queryParams" inline class="intelligence-filters" @submit.prevent="handleQuery">
        <el-form-item class="keyword-filter">
          <el-input v-model="queryParams.keyword" aria-label="搜索标题、摘要或标签" :prefix-icon="Search" placeholder="搜索标题、摘要或标签" clearable />
        </el-form-item>
        <el-form-item label="内容类型" class="type-filter">
          <el-select v-model="queryParams.category" aria-label="内容类型" placeholder="全部类型" clearable>
            <el-option label="新闻" value="news" />
            <el-option label="公众号" value="wechat" />
            <el-option label="论文" value="paper" />
          </el-select>
        </el-form-item>
        <el-form-item class="filter-actions">
          <el-button type="primary" native-type="submit" :icon="Search" :loading="loading">搜索</el-button>
          <el-button :icon="Refresh" @click="resetQuery">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-alert v-if="loadError" type="warning" show-icon :closable="false" class="intelligence-load-error">
      <template #title>{{ loadError }}</template>
      <template #default><el-button class="ps-ui-action intelligence-retry" @click="getList">重新加载列表</el-button></template>
    </el-alert>
    <el-card v-else shadow="never" class="intelligence-list-card ws-list-panel">
      <div v-loading="loading" :aria-busy="loading" class="intelligence-list-region ws-list-scroll" tabindex="0" aria-label="情报列表滚动区">
        <ul v-if="rows.length" class="intelligence-list" aria-label="情报列表">
          <li v-for="row in rows" :key="row.id" class="intelligence-item">
            <div class="item-header">
              <div class="item-meta">
                <el-tag :type="categoryType(row.category)" effect="light" size="small">{{ categoryText(row.category) }}</el-tag>
                <span v-if="row.source" class="item-source">{{ row.source }}</span>
                <time v-if="row.publish_time" class="item-date" title="发布时间"><el-icon aria-hidden="true"><Calendar /></el-icon>{{ formatBusinessTime(row.publish_time) }}</time>
              </div>
              <el-button class="detail-action" plain type="primary" :icon="View" @click="openDetail(row)">查看详情</el-button>
            </div>
            <h2 class="item-title"><el-link underline="never" :href="$router.resolve({ path: '/pipeline/intelligence/detail', query: { id: row.id } }).href" class="title-button" @click.prevent="openDetail(row)">{{ row.title }}</el-link></h2>
            <p v-if="row.summary" class="row-summary">{{ row.summary }}</p>
            <div v-if="row.tags?.length" class="item-tags"><el-tag v-for="tag in row.tags" :key="tag" effect="plain" size="small">{{ tag }}</el-tag></div>
            <ContentEntities :entities="row.entities || []" compact />
          </li>
        </ul>
        <el-empty v-else-if="!loading" description="暂无匹配的情报" :image-size="80" />
        <p v-else class="list-loading" role="status">正在加载资料…</p>
      </div>
      <pagination
        v-show="total > 0"
        v-model:page="queryParams.pageNum"
        v-model:limit="queryParams.pageSize"
        :total="total"
        :auto-scroll="false"
        @pagination="getList"
      />
    </el-card>

  </div>
</template>
<script setup>
import { formatBusinessTime } from '@/utils/portal/businessTime'
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Calendar, Refresh, Search, View } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import { listPipelineIntelligence } from '@/api/pipeline/intelligence'
import ContentEntities from '@/views/portal/components/ContentEntities.vue'
defineOptions({ name: 'PipelineIntelligence' })
const router = useRouter()
const loading = ref(false), loadError = ref(''), rows = ref([]), total = ref(0)
const queryParams = reactive({ pageNum: 1, pageSize: 10, keyword: '', category: '' })
function categoryText(category) { return { news: '新闻', wechat: '公众号', paper: '论文' }[category] || category }
function categoryType(category) { return { news: 'primary', wechat: 'success', paper: 'warning' }[category] || 'info' }
async function getList() {
 loading.value = true; loadError.value = ''
 try { const res = await listPipelineIntelligence(queryParams); rows.value = res.data.rows; total.value = res.data.total }
 catch (error) { rows.value = []; total.value = 0; loadError.value = error?.msg || error?.message || '情报列表加载失败，请重试'; ElMessage.warning(loadError.value) }
 finally { loading.value = false }
}
function handleQuery() { queryParams.pageNum = 1; getList() }
function resetQuery() { queryParams.keyword = ''; queryParams.category = ''; handleQuery() }
function openDetail(row) { router.push({ path: '/pipeline/intelligence/detail', query: { id: row.id } }) }
onMounted(getList)
</script>
<style scoped>
/* Scope the override to these cards; RuoYi sets card padding with !important. */
.filter-card :deep(.el-card__body) { padding: 12px 16px !important; }
.intelligence-filters { display: flex; flex-direction: row; align-items: center; flex-wrap: wrap; gap: 12px 16px; }
.intelligence-filters :deep(.el-form-item) { margin: 0; }
.intelligence-filters .keyword-filter { flex: 1 1 300px; min-width: 0; }
.intelligence-filters .keyword-filter :deep(.el-input) { width: 100%; }
.intelligence-filters .type-filter { flex: 0 0 240px; }
.intelligence-filters :deep(.el-form-item__content) { min-width: 0; }
.intelligence-filters .type-filter :deep(.el-select) { width: 100%; }
.intelligence-filters .filter-actions { flex: 0 0 auto; }
.intelligence-list-card :deep(.el-card__body) { padding: 0 !important; }
.intelligence-list-region { min-height: 0; }
.intelligence-list { margin: 0; padding: 0; list-style: none; }
.intelligence-item { padding: 16px 20px; border-bottom: 1px solid var(--el-border-color-lighter); }
.intelligence-item:last-child { border-bottom: 0; }
.intelligence-item:hover { background: var(--el-fill-color-extra-light); }
.item-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 8px; }
.item-meta { display: flex; align-items: center; flex-wrap: wrap; gap: 6px 14px; min-width: 0; color: var(--el-text-color-secondary); font-size: 13px; line-height: 1.6; }
.item-meta > .el-tag { flex-shrink: 0; }
.item-source { overflow-wrap: anywhere; color: var(--el-text-color-regular); }
.item-date { display: inline-flex; align-items: center; gap: 5px; white-space: nowrap; font-variant-numeric: tabular-nums; }
.detail-action { flex-shrink: 0; margin: 0; }
.item-title { margin: 0; font-size: 16px; font-weight: 600; }
.title-button { display: block; width: 100%; color: var(--el-text-color-primary); font: inherit; padding: 0; text-align: left; white-space: normal; overflow-wrap: anywhere; line-height: 1.6; }
.title-button :deep(.el-link__inner) { display: inline; }
.title-button:hover { color: var(--el-color-primary); }
.title-button:focus-visible { outline: 2px solid var(--el-color-primary); outline-offset: 3px; border-radius: 3px; }
.row-summary {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
  overflow: hidden;
  white-space: normal;
  overflow-wrap: anywhere;
  margin: 8px 0 0;
  color: var(--el-text-color-regular);
  font-size: 14px;
  line-height: 1.8;
}
.item-tags { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
.item-tags :deep(.el-tag) { max-width: 100%; height: auto; white-space: normal; overflow-wrap: anywhere; }
.intelligence-list-card :deep(.pagination-container) { padding: 12px 20px; border-top: 1px solid var(--el-border-color-lighter); }
.list-loading { padding: 32px 16px; color: var(--el-text-color-secondary); text-align: center; }
.intelligence-load-error { margin-top: 12px; }
.intelligence-retry { margin-top: 8px; }
@media (max-width: 760px) {
  .intelligence-filters { gap: 10px; }
  .intelligence-filters .keyword-filter { flex-basis: 100%; }
  .intelligence-filters .type-filter { flex: 1 1 180px; }
  .intelligence-item { padding: 14px; }
  .item-header { align-items: flex-start; gap: 8px; }
  .item-meta { gap: 6px 10px; }
  .item-source { flex-basis: 100%; order: 1; }
  .item-meta .item-date { white-space: normal; }
  .intelligence-list-card :deep(.pagination-container) { padding: 10px 14px; }
  .intelligence-list-card :deep(.el-pagination) { flex-wrap: wrap; justify-content: flex-end; gap: 8px; }
  .intelligence-list-card :deep(.el-pagination__jump) { display: none; }
}
</style>
