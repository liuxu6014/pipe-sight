<template>
  <div v-if="workflow" class="ps-route-context">
    <nav class="ps-context-breadcrumb" aria-label="当前位置">
      <router-link to="/portal">首页</router-link><span aria-hidden="true">/</span>
      <template v-if="route.path !== (workflow.target || workflow.path)">
        <router-link :to="workflow.target || workflow.path">{{ workflow.title }}</router-link><span aria-hidden="true">/</span>
      </template>
      <span aria-current="page">{{ route.path === (workflow.target || workflow.path) ? workflow.title : route.meta.title || '当前页面' }}</span>
    </nav>
    <details :key="route.path" ref="help" class="ps-workflow-help" @keydown.esc="help.open = false">
      <summary><QuestionFilled /><span>使用帮助</span></summary>
      <div class="ps-workflow-popover">
        <header><strong>{{ workflow.title }} · 页面使用流程</strong><button type="button" aria-label="关闭使用帮助" @click="help.open = false"><Close /></button></header>
        <ol><li v-for="step in workflow.steps" :key="step">{{ step }}</li></ol>
        <p>加载失败请重试当前操作；生成完成不等于复核通过，资料与成果始终按当前授权访问。</p>
      </div>
    </details>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { Close, QuestionFilled } from '@element-plus/icons-vue'
import { useRoute } from 'vue-router'
import { getPortalWorkflow } from '../utils/workflows'

const route = useRoute()
const help = ref()
const workflow = computed(() => getPortalWorkflow(route.path))
</script>
