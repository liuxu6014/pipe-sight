<template>
  <div class="pipeline-page">
    <section class="page-heading">
      <div>
        <p class="eyebrow">后台管理 · 情报内容</p>
        <h1>新闻 / 公众号 / 论文统一检索</h1>
        <p class="summary">管理员在这里检索、复核、追踪情报条目；用户端阅读入口位于 /portal。</p>
      </div>
      <el-button type="primary" :icon="Search" @click="handleQuery">检索</el-button>
    </section>

    <el-card shadow="never" class="filter-card">
      <el-form :model="queryParams" inline>
        <el-form-item label="关键词">
          <el-input v-model="queryParams.keyword" placeholder="标题、摘要、标签" clearable @keyup.enter="handleQuery" />
        </el-form-item>
        <el-form-item label="类别">
          <el-select v-model="queryParams.category" placeholder="全部" clearable style="width: 150px">
            <el-option label="新闻" value="news" />
            <el-option label="公众号" value="wechat" />
            <el-option label="论文" value="paper" />
          </el-select>
        </el-form-item>
        <el-form-item label="来源类型">
          <el-select v-model="queryParams.sourceType" placeholder="全部" clearable style="width: 150px">
            <el-option label="新闻源" value="news" />
            <el-option label="公众号" value="wechat" />
            <el-option label="论文库" value="paper" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :icon="Search" @click="handleQuery">搜索</el-button>
          <el-button :icon="Refresh" @click="resetQuery">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never" class="table-card">
      <el-table v-loading="loading" :data="rows" border>
        <el-table-column label="标题" min-width="260" show-overflow-tooltip>
          <template #default="{ row }">
            <el-button link type="primary" class="title-button" @click="openDetail(row)">
              {{ row.title }}
            </el-button>
            <div class="row-summary">{{ row.summary }}</div>
          </template>
        </el-table-column>
        <el-table-column prop="category" label="类别" width="100">
          <template #default="{ row }">
            <el-tag :type="categoryType(row.category)" effect="light">{{ categoryText(row.category) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="source" label="来源" width="170" show-overflow-tooltip />
        <el-table-column prop="relevance" label="相关性" width="130" align="right">
          <template #default="{ row }">
            <el-progress :percentage="row.relevance" :stroke-width="8" />
          </template>
        </el-table-column>
        <el-table-column label="标签" min-width="180">
          <template #default="{ row }">
            <el-tag v-for="tag in row.tags" :key="tag" class="tag-item" effect="plain">{{ tag }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)">{{ statusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="publish_time" label="发布时间" width="180" />
        <el-table-column label="操作" width="110" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" :icon="View" @click="openDetail(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
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
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, Search, View } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import { listPipelineIntelligence } from '@/api/pipeline/intelligence'

defineOptions({ name: 'PipelineIntelligence' })

const router = useRouter()
const loading = ref(false)
const rows = ref([])
const total = ref(0)
const queryParams = reactive({
  pageNum: 1,
  pageSize: 10,
  keyword: '',
  category: '',
  sourceType: ''
})

function categoryText(category) {
  return { news: '新闻', wechat: '公众号', paper: '论文' }[category] || category
}

function categoryType(category) {
  return { news: 'primary', wechat: 'success', paper: 'warning' }[category] || 'info'
}

function statusText(status) {
  return { processed: '已处理', reviewing: '待审核' }[status] || status
}

function statusType(status) {
  return status === 'processed' ? 'success' : 'warning'
}

async function getList() {
  loading.value = true
  try {
    const res = await listPipelineIntelligence(queryParams)
    rows.value = res.data.rows
    total.value = res.data.total
  } catch (error) {
    ElMessage.warning('暂时无法获取情报列表')
  } finally {
    loading.value = false
  }
}

function handleQuery() {
  queryParams.pageNum = 1
  getList()
}

function resetQuery() {
  queryParams.keyword = ''
  queryParams.category = ''
  queryParams.sourceType = ''
  handleQuery()
}

function openDetail(row) {
  router.push({ path: '/pipeline/intelligence/detail', query: { id: row.id } })
}

onMounted(getList)
</script>

<style scoped>
.table-card {
  margin-top: 18px;
}

.row-summary {
  margin-top: 6px;
  color: #667085;
  font-size: 13px;
  line-height: 1.5;
}

.tag-item {
  margin: 0 5px 5px 0;
}
</style>
