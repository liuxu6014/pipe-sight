<template>
  <section class="ps-content-insights" :aria-label="title">
    <template v-if="kind === 'paper'">
      <p v-if="paragraph" class="insight-paragraph">{{ paragraph }}</p>
      <p v-else class="insight-empty">暂无 AI 解读</p>
    </template>
    <template v-else>
      <h2>{{ title }}</h2><p class="insight-note">仅展示已保存的解读；缺少证据的机构、效果和场景不作推断。</p>
      <div class="insight-grid"><article v-for="section in sections" :key="section.label"><h3>{{ section.label }}</h3><p :class="{ 'is-empty': !section.content }">{{ section.content || '暂无已保存的解读' }}</p></article></div>
    </template>
  </section>
</template>
<script setup>
import { computed } from 'vue'
import { insightSections, paperInsightParagraph } from '@/utils/portal/contentPresentation'
const props = defineProps({ item: { type: Object, default: () => ({}) }, kind: { type: String, default: 'news' } })
const title = computed(() => props.kind === 'paper' ? 'AI 解读' : '官网洞察')
const sections = computed(() => insightSections(props.item, props.kind))
const paragraph = computed(() => props.kind === 'paper' ? paperInsightParagraph(props.item) : '')
</script>
<style scoped>
.insight-paragraph { margin: 0; color: var(--ps-ink-2); font-size: 15px; line-height: 1.9; overflow-wrap: anywhere; text-indent: 2em; }
.insight-empty { margin: 0; color: var(--ps-muted); font-size: 14px; line-height: 1.9; }
h2 { margin: 0; font-size: 18px; }.insight-note { margin: 8px 0 16px; font-size: 13px; color: var(--ps-muted); line-height: 1.6; }.insight-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px; }.insight-grid article { min-width:0; padding:16px; border:1px solid var(--ps-line); border-radius:8px; }.insight-grid h3 { font-size:14px; margin:0 0 10px; }.insight-grid p { margin:0; font-size:15px; line-height:1.85; white-space:pre-wrap; overflow-wrap:anywhere; }.insight-grid .is-empty { font-size:13px; color:var(--ps-muted); }@media(max-width:600px){.insight-grid{grid-template-columns:minmax(0,1fr)}}
</style>
