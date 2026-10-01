<template>
  <div class="ps-page ps-home-page">
    <section class="ps-home-hero">
      <div class="ps-home-welcome">
        <div class="ps-eyebrow">{{ todayLabel }}</div>
        <h1>{{ greeting }}，{{ currentUserName }}</h1>
        <p>从可信情报出发，把分散资料转化为可追溯的科研成果。</p>
        <form class="ps-hero-search" @submit.prevent="submitSearch">
          <Search />
          <input v-model.trim="keyword" placeholder="搜索管网安全、无损检测、腐蚀防护、应力监测……" />
          <el-button native-type="submit" type="primary">搜索</el-button>
        </form>
      </div>
      <aside class="ps-hero-brief">
        <div class="ps-brief-head">
          <span>今日研究简报</span>
          <time>实时汇总</time>
        </div>
        <strong>{{ briefTitle }}</strong>
        <p>{{ briefSummary }}</p>
        <div class="ps-brief-metrics">
          <span v-for="metric in homeMetrics" :key="metric.label"><b>{{ metric.value }}</b>{{ metric.label }}</span>
        </div>
        <el-button text type="primary" @click="router.push('/portal/news')">查看今日情报 <ArrowRight /></el-button>
      </aside>
    </section>

    <section class="ps-quick-grid" aria-label="快捷操作">
      <button v-for="action in quickActions" :key="action.title" type="button" class="ps-quick-card" @click="router.push(action.path)">
        <span class="ps-quick-icon" :style="{ '--accent': action.color }"><component :is="action.icon" /></span>
        <span><strong>{{ action.title }}</strong><small>{{ action.description }}</small></span>
        <ArrowRight />
      </button>
    </section>

    <div class="ps-home-grid">
      <section class="ps-panel ps-my-work">
        <div class="ps-section-head">
          <div><h2>我的工作</h2></div>
          <button class="ps-live-dot" type="button" @click="portalStore.openTaskPanel()"><i></i>{{ portalStore.runningTaskCount }} 项进行中</button>
        </div>
        <button v-for="task in portalStore.tasks.slice(0, 4)" :key="task.id" type="button" class="ps-home-task" @click="openTask(task)">
          <span><strong>{{ task.title }}</strong><small>{{ task.statusLabel }} · {{ task.updatedAt }}</small></span>
          <span class="ps-task-progress" :style="{ '--progress': `${task.progress}%` }" :aria-label="`进度 ${task.progress}%`"><b>{{ task.progress }}%</b></span>
        </button>
        <el-button class="ps-block-action" @click="router.push('/portal/research/create')"><Plus />创建第一份科研报告</el-button>
      </section>

      <section class="ps-panel">
        <div class="ps-section-head">
          <div><h2>最新论文</h2></div>
          <el-button text @click="router.push('/portal/papers')">全部</el-button>
        </div>
        <button v-for="paper in paperItems.slice(0, 3)" :key="paper.id" type="button" class="ps-paper-mini" @click="router.push(`/portal/papers/${paper.id}`)">
          <span class="ps-paper-year">{{ paper.year }}</span>
          <span><strong>{{ paper.titleZh }}</strong><small>{{ paper.journal }} · {{ paper.authors.slice(0, 2).join(', ') }}</small></span>
        </button>
      </section>

      <section class="ps-panel ps-span-2">
        <div class="ps-section-head">
          <div><h2>最新科技资讯</h2></div>
          <el-button text type="primary" @click="router.push('/portal/news')">进入情报流 <ArrowRight /></el-button>
        </div>
        <div class="ps-news-compact-list">
          <article v-for="item in newsItems.slice(0, 5)" :key="item.id" @click="router.push(`/portal/news/${item.id}`)">
            <div class="ps-news-date"><b>{{ item.time.slice(8, 10) }}</b><span>{{ item.time.slice(5, 7) }}月</span></div>
            <div><span class="ps-source-line">{{ item.source }} · {{ item.time.slice(11) }}</span><h3>{{ item.title }}</h3><p>{{ item.summary }}</p></div>
            <span class="ps-importance" :class="{ 'is-key': item.importance === '重点' }">{{ item.importance }}</span>
          </article>
        </div>
      </section>

    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowRight, DocumentAdd, Plus, Search, UploadFilled } from '@element-plus/icons-vue'
import useUserStore from '@/store/modules/user'
import usePortalStore from '@/store/modules/portal'
import { getPortalTaskPath } from '../utils/routing'

const router = useRouter()
const userStore = useUserStore()
const portalStore = usePortalStore()
const keyword = ref('')
const newsItems = computed(() => portalStore.newsItems)
const paperItems = computed(() => portalStore.paperItems)
const parsedDocumentCount = computed(() => portalStore.knowledgeDocuments.filter(item => item.status === '已解析').length)
const homeMetrics = computed(() => portalStore.dashboardMetrics.length
  ? portalStore.dashboardMetrics.slice(0, 3).map(item => ({ label: item.label, value: `${item.value}${item.unit || ''}` }))
  : [
      { label: '科技资讯', value: newsItems.value.length },
      { label: '论文资料', value: paperItems.value.length },
      { label: '已解析资料', value: parsedDocumentCount.value }
    ])
const briefTitle = computed(() => {
  const names = portalStore.hotTopics.slice(0, 2).map(item => item.name).filter(Boolean)
  return names.length ? `${names.join('、')}持续受到关注` : '当前情报与科研资料概览'
})
const briefSummary = computed(() => `当前已加载 ${newsItems.value.length} 条科技资讯、${paperItems.value.length} 篇论文，${parsedDocumentCount.value} 项内部资料可用于检索和生成。`)
const currentUserName = computed(() => userStore.nickName || userStore.name || '管网用户')
const hour = new Date().getHours()
const greeting = computed(() => hour < 11 ? '早上好' : hour < 14 ? '中午好' : hour < 18 ? '下午好' : '晚上好')
const todayLabel = new Intl.DateTimeFormat('zh-CN', { year: 'numeric', month: 'long', day: 'numeric', weekday: 'long' }).format(new Date())
const quickActions = [
  { title: '新建科研报告', description: '从资料篮开始结构化生成', path: '/portal/research/create', icon: DocumentAdd, color: '#2764e7' },
  { title: '新建简报', description: '按日、周或月生成周期情报简报', path: '/portal/digests/create', icon: Plus, color: '#0b8f87' },
  { title: '上传研究资料', description: '解析并纳入授权知识库', path: '/portal/knowledge', icon: UploadFilled, color: '#7357c8' }
]

function submitSearch() {
  if (keyword.value) router.push({ path: '/portal/search', query: { q: keyword.value } })
}
function openTask(task) {
  router.push(getPortalTaskPath(task))
}
</script>
