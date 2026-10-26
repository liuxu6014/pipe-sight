<template>
  <div class="pipeline-page intelligence-page">
    <section class="page-heading">
      <div>
        <h1>情报查询</h1>
      </div>
    </section>

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
      <template #default><button type="button" class="intelligence-retry" @click="getList">重新加载列表</button></template>
    </el-alert>
    <el-card v-else shadow="never" class="intelligence-list-card">
      <div v-loading="loading" :aria-busy="loading" class="intelligence-list-region">
        <ul v-if="rows.length" class="intelligence-list" aria-label="情报列表">
          <li v-for="row in rows" :key="row.id" class="intelligence-item">
            <h2 class="item-title"><button type="button" class="title-button" @click="openDetail(row)">{{ row.title }}</button></h2>
            <p v-if="row.summary" class="row-summary">{{ row.summary }}</p>
            <div v-if="row.tags?.length" class="item-tags"><el-tag v-for="tag in row.tags" :key="tag" effect="plain">{{ tag }}</el-tag></div>
            <div class="item-footer">
              <div class="item-meta">
                <el-tag :type="categoryType(row.category)" effect="light">{{ categoryText(row.category) }}</el-tag>
                <span v-if="row.source" class="item-source">{{ row.source }}</span>
                <time v-if="row.publish_time">{{ formatBusinessTime(row.publish_time) }}</time>
              </div>
              <el-button link type="primary" :icon="View" @click="openDetail(row)">查看详情</el-button>
            </div>
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
        @pagination="getList"
      />
    </el-card>

  </div>
</template>
<script setup>
import { formatBusinessTime } from '@/utils/portal/businessTime'
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, Search, View } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import { listPipelineIntelligence } from '@/api/pipeline/intelligence'
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
.intelligence-page .page-heading { padding-bottom: 16px; margin-bottom: 16px; }
.intelligence-page .page-heading h1 { margin: 0; }
.filter-card :deep(.el-card__body) { padding: 14px 16px; }
.intelligence-filters { display: flex; align-items: center; flex-wrap: wrap; gap: 12px 16px; }
.intelligence-filters :deep(.el-form-item) { margin: 0; }
.intelligence-filters .keyword-filter { flex: 1 1 300px; min-width: 0; }
.intelligence-filters .keyword-filter :deep(.el-input) { width: 100%; }
.intelligence-filters .type-filter { flex: 0 0 250px; }
.intelligence-filters :deep(.el-form-item__content) { min-width: 0; }
.intelligence-filters .type-filter :deep(.el-select) { width: 100%; }
.intelligence-filters .filter-actions { flex: 0 0 auto; }
@media (max-width: 640px) {
  .intelligence-filters .keyword-filter,
  .intelligence-filters .type-filter { flex-basis: 100%; }
}
.intelligence-list-card { margin-top: 14px; }
.intelligence-list-card :deep(.el-card__body) { padding: 0 20px 16px; }
.intelligence-list-region { min-height: 140px; }
.intelligence-list { margin: 0; padding: 0; list-style: none; }
.intelligence-item { padding: 18px 0; border-bottom: 1px solid #e5ebf2; }
.item-title { margin: 0; font-size: 16px; font-weight: 600; }
.title-button { display: block; width: 100%; border: 0; background: transparent; color: #005487; font: inherit; padding: 0; text-align: left; white-space: normal; overflow-wrap: anywhere; line-height: 1.6; cursor: pointer; }
.title-button:hover { text-decoration: underline; }
.title-button:focus-visible { outline: 2px solid #7da6c0; outline-offset: 3px; border-radius: 3px; }
.item-footer { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-top: 10px; }
.item-meta { display: flex; align-items: center; flex-wrap: wrap; gap: 8px 14px; min-width: 0; color: #526277; font-size: 13px; }
.item-source { overflow-wrap: anywhere; }
.item-meta time { white-space: nowrap; }
.item-footer > .el-button { flex-shrink: 0; min-height: 44px; }
.item-tags { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
.item-tags :deep(.el-tag) { max-width: 100%; height: auto; white-space: normal; overflow-wrap: anywhere; }
.list-loading { padding: 32px 0; color: #526277; text-align: center; }
@media (max-width: 640px) {
  .intelligence-list-card :deep(.el-card__body) { padding: 0 14px 14px; }
  .item-footer { align-items: flex-start; }
}

.intelligence-load-error { margin-top: 18px; }
.intelligence-retry { padding: 0; border: 0; background: transparent; color: #2764e7; cursor: pointer; font-size: 13px; }

.row-summary {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
  overflow: hidden;
  white-space: normal;
  margin: 8px 0 0;
  color: #667085;
  font-size: 13px;
  line-height: 1.7;
}

.review-title {
  margin: 0 0 16px;
  color: #173d56;
  font-weight: 600;
  line-height: 1.6;
}

.review-meta {
  margin-bottom: 16px;
}

.review-content {
  margin-bottom: 16px;
  padding: 0 4px;
  background: #f8fafc;
}

.review-section-title {
  margin: 12px 0 6px;
  color: #344054;
  font-weight: 600;
}

.review-body {
  margin: 0;
  color: #475467;
  line-height: 1.7;
  white-space: pre-wrap;
}

.review-json {
  margin: 0;
  color: #475467;
  font: 12px/1.6 ui-monospace, SFMono-Regular, Menlo, monospace;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.review-error {
  margin: 0;
  color: #b42318;
  line-height: 1.6;
}

.reprocess-form {
  margin-top: 16px;
}
</style>
