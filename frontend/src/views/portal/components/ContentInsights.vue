<template>
  <section class="ps-content-insights" :aria-label="title">
    <h2><el-icon class="insight-icon"><TrendCharts v-if="kind === 'news'" /><DataAnalysis v-else /></el-icon>{{ title }}</h2>
    <template v-if="kind === 'paper'">
      <p v-if="paragraph" class="insight-paragraph">{{ paragraph }}</p>
      <p v-else class="insight-empty">暂无 AI 解读</p>
    </template>
    <template v-else-if="sections.length">
      <p class="insight-note">仅展示已保存的解读；缺少证据的机构、效果和场景不作推断。</p>
      <div class="insight-grid"><article v-for="section in sections" :key="section.label"><h3>{{ section.label }}</h3><p>{{ section.content }}</p></article></div>
    </template>
    <p v-else class="insight-empty">暂无行业洞察</p>
  </section>
</template>
<script setup>
import { computed } from 'vue'
import { DataAnalysis, TrendCharts } from '@element-plus/icons-vue'
import { insightSections, paperInsightParagraph } from '@/utils/portal/contentPresentation'
const props = defineProps({ item: { type: Object, default: () => ({}) }, kind: { type: String, default: 'news' } })
const title = computed(() => props.kind === 'paper' ? 'AI 解读' : '行业洞察')
const sections = computed(() => insightSections(props.item, props.kind).filter(section => section.content))
const paragraph = computed(() => props.kind === 'paper' ? paperInsightParagraph(props.item) : '')
</script>
<style scoped>
.insight-paragraph { margin: 8px 0 0; color: var(--ps-ink-2); font-size: 15px; line-height: 1.9; overflow-wrap: anywhere; text-indent: 2em; }
.insight-empty { margin: 8px 0 0; color: var(--ps-muted); font-size: 14px; line-height: 1.9; }
h2 { margin: 0; font-size: 17px; display: flex; align-items: center; gap: 6px; }
.insight-icon { color: var(--ps-muted); }
.insight-note { margin: 8px 0 12px; font-size: 13px; color: var(--ps-muted); line-height: 1.6; }
.insight-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.insight-grid article { min-width: 0; padding: 12px; border: 1px solid var(--ps-line); border-radius: 8px; }
.insight-grid h3 { font-size: 14px; margin: 0 0 8px; }
.insight-grid p { margin: 0; font-size: 15px; line-height: 1.85; white-space: pre-wrap; overflow-wrap: anywhere; }
@media (max-width: 600px) { .insight-grid { grid-template-columns: minmax(0, 1fr); } }
</style>
