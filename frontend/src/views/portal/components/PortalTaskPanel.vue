<template>
  <el-drawer v-model="store.taskPanelVisible" title="任务进度" size="420px" class="ps-task-drawer">
    <div class="ps-task-panel-head">
      <p>{{ store.runningTaskCount }} 个任务正在处理</p>
      <el-button plain type="primary" @click="router.push('/portal/me/reports')">查看全部</el-button>
    </div>
    <div class="ps-task-list">
      <el-button :auto-insert-space="false" v-for="task in store.tasks" :key="task.id" native-type="button" class="ps-task-row ps-ui-control" @click="openTask(task)">
        <span class="ps-task-status" :class="`is-${task.status}`"></span>
        <span class="ps-task-copy">
          <strong>{{ task.title }}</strong>
          <small>{{ task.type }} · {{ task.statusLabel }} · {{ task.updatedAt }}</small>
          <el-progress :percentage="task.progress" :stroke-width="5" :show-text="false" />
        </span>
        <ArrowRight />
      </el-button>
      <p v-if="!store.tasks.length" class="ps-inspector-empty">当前没有生成任务</p>
    </div>
  </el-drawer>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { ArrowRight } from '@element-plus/icons-vue'
import usePortalStore from '@/store/modules/portal'
import { getPortalTaskPath } from '../utils/routing'

const router = useRouter()
const store = usePortalStore()

function openTask(task) {
  store.taskPanelVisible = false
  router.push(getPortalTaskPath(task))
}
</script>
