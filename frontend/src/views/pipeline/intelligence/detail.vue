<template>
  <div class="pipeline-page">
    <section class="page-heading">
      <div>
        <p class="eyebrow">后台管理 · 情报详情</p>
        <h1>{{ detail.title || '情报详情' }}</h1>
        <p class="summary">{{ detail.summary }}</p>
      </div>
      <el-button :icon="Back" @click="router.back()">返回</el-button>
    </section>

    <el-row :gutter="16">
      <el-col :xs="24" :lg="16">
        <el-card v-loading="loading" shadow="never" class="panel-card">
          <template #header>
            <div class="card-header">
              <span>正文摘要</span>
              <el-tag :type="categoryType(detail.category)" effect="light">{{ categoryText(detail.category) }}</el-tag>
            </div>
          </template>
          <p class="content-text">{{ detail.category === 'paper' ? (detail.abstractZh || detail.abstract_zh || detail.abstract || detail.summary || '摘要未提供') : (detail.contentZh || detail.content || '正文未提供') }}</p>
          <div class="tag-line">
            <el-tag v-for="tag in detail.tags" :key="tag" effect="plain">{{ tag }}</el-tag>
          </div>
        </el-card>

        <el-card shadow="never" class="panel-card">
          <template #header>处理时间线</template>
          <el-timeline>
            <el-timeline-item v-for="item in detail.timeline" :key="item.time" :timestamp="item.time">
              {{ item.label }}
            </el-timeline-item>
          </el-timeline>
        </el-card>
      </el-col>

      <el-col :xs="24" :lg="8">
        <el-card shadow="never" class="panel-card">
          <template #header>结构化信息</template>
          <el-descriptions :column="1" border>
            <el-descriptions-item label="来源">{{ detail.source }}</el-descriptions-item>
            <el-descriptions-item label="发布时间">{{ formatBusinessTime(detail.publish_time) }}</el-descriptions-item>
            <el-descriptions-item label="相关性">{{ detail.relevance }}%</el-descriptions-item>
            <el-descriptions-item label="类别">{{ detail.categoryName || '未分类' }}</el-descriptions-item>
          </el-descriptions>
        </el-card>

        <el-card shadow="never" class="panel-card">
          <template #header>实体与主题</template>
          <div class="entity-list">
            <el-tag v-for="entity in detail.entities" :key="`${entity.type}-${entity.name}`" effect="light">
              {{ entity.name }}
            </el-tag>
          </div>
          <el-divider />
          <div class="topic-list">
            <el-tag v-for="topic in detail.related_topics" :key="topic" type="success" effect="plain">
              {{ topic }}
            </el-tag>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { formatBusinessTime } from '@/utils/portal/businessTime'
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Back } from '@element-plus/icons-vue'
import { useRoute, useRouter } from 'vue-router'
import { getPipelineIntelligenceDetail } from '@/api/pipeline/intelligence'

defineOptions({ name: 'PipelineIntelligenceDetail' })

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const detail = ref({
  tags: [],
  entities: [],
  related_topics: [],
  timeline: []
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

async function loadDetail() {
  loading.value = true
  try {
    if (!route.query.id) throw new Error('缺少情报编号')
    const res = await getPipelineIntelligenceDetail(route.query.id)
    detail.value = res.data
  } catch (error) {
    ElMessage.warning('暂时无法获取情报详情')
  } finally {
    loading.value = false
  }
}

onMounted(loadDetail)
</script>

<style scoped>
.summary,
.content-text {
  color: #526b7d;
  line-height: 1.8;
}

.tag-line,
.entity-list,
.topic-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.content-text {
  margin: 0;
  white-space: pre-line;
}
</style>
