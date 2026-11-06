<template>
  <div class="pipeline-page">
    <section class="page-heading">
      <div>

        <h1>{{ detail.title || '情报详情' }}</h1>
      </div>
      <el-button :icon="Back" @click="router.back()">返回</el-button>
    </section>

    <el-alert v-if="loadError" :title="loadError" type="error" show-icon :closable="false">
      <template #default><el-button plain type="primary" @click="loadDetail">重新加载</el-button></template>
    </el-alert>
    <el-row v-else :gutter="16">
      <el-col :xs="24" :lg="16">
        <el-card v-loading="loading" shadow="never" class="panel-card">
          <template #header>
            <div class="card-header">
              <span>{{ detail.category === 'paper' ? '论文内容' : '资讯内容' }}</span>
              <el-tag :type="categoryType(detail.category)" effect="light">{{ categoryText(detail.category) }}</el-tag>
            </div>
          </template>
          <el-tabs v-model="activeTab" aria-label="内容切换"><el-tab-pane label="摘要" name="summary"><p class="content-text">{{ detail.category === 'paper' ? detail.abstract || detail.summary || '摘要未提供' : detail.summary || '摘要未提供' }}</p></el-tab-pane><el-tab-pane v-if="detail.category !== 'paper'" label="全文" name="fulltext"><p class="content-text">{{ detail.content_original || detail.contentOriginal || detail.content || '当前记录未提供全文' }}</p></el-tab-pane><el-tab-pane v-if="savedTranslation" label="已保存中文" name="zh"><p class="content-text">{{ savedTranslation }}</p></el-tab-pane><el-tab-pane :label="detail.category === 'paper' ? 'AI 解读' : '管网洞察'" name="insight"><ContentInsights :item="detail" :kind="detail.category === 'paper' ? 'paper' : 'news'" /></el-tab-pane></el-tabs>
          <div class="tag-line">
            <el-tag v-for="tag in detail.tags" :key="tag" effect="plain">{{ tag }}</el-tag>
          </div>
        </el-card>
        <ContentEntities :entities="detail.entities || []" />

      </el-col>

      <el-col :xs="24" :lg="8">
        <el-card shadow="never" class="panel-card">
          <template #header>结构化信息</template>
          <el-descriptions :column="1" border>
            <el-descriptions-item label="来源">{{ detail.source }}</el-descriptions-item>
            <el-descriptions-item label="发布时间">{{ formatBusinessTime(detail.publish_time) }}</el-descriptions-item>
            <el-descriptions-item label="类别">{{ detail.category_name || '类别未提供' }}</el-descriptions-item>
            <el-descriptions-item v-if="detail.category === 'paper'" label="期刊">{{ detail.journal || '当前接口未提供' }}</el-descriptions-item>
            <el-descriptions-item v-if="detail.category === 'paper'" label="作者">{{ Array.isArray(detail.authors) ? detail.authors.join(' · ') : detail.authors || '当前接口未提供' }}</el-descriptions-item>
            <el-descriptions-item label="采集时间">{{ collectionTime(detail) || '当前接口未提供' }}</el-descriptions-item>
          </el-descriptions>
        </el-card>

      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { formatBusinessTime } from '@/utils/portal/businessTime'
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Back } from '@element-plus/icons-vue'
import { useRoute, useRouter } from 'vue-router'
import { getPipelineIntelligenceDetail } from '@/api/pipeline/intelligence'
import ContentEntities from '@/views/portal/components/ContentEntities.vue'
import ContentInsights from '@/views/portal/components/ContentInsights.vue'
import { collectionTime } from '@/utils/portal/contentPresentation'

defineOptions({ name: 'PipelineIntelligenceDetail' })

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const loadError = ref('')
const detail = ref({ tags: [] })
const activeTab = ref('summary')
const savedTranslation = computed(() => detail.value.category === 'paper' ? detail.value.abstractZh || detail.value.abstract_zh : detail.value.contentZh || detail.value.content_zh)

function categoryText(category) {
  return { news: '新闻', wechat: '公众号', paper: '论文' }[category] || category
}

function categoryType(category) {
  return { news: 'primary', wechat: 'success', paper: 'warning' }[category] || 'info'
}

async function loadDetail() {
  loading.value = true
  loadError.value = ''
  try {
    if (!route.query.id) throw new Error('缺少情报编号')
    const res = await getPipelineIntelligenceDetail(route.query.id)
    detail.value = res.data
  } catch (error) {
    detail.value = { tags: [] }
    loadError.value = '暂时无法获取情报详情，请检查编号、权限或稍后重试'
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

.tag-line {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.content-text {
  margin: 0;
  white-space: pre-line;
}
</style>
