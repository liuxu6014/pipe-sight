<template>
  <section v-if="!compact || hasEntities || $slots.prepend" class="ps-content-entities" :class="{ 'is-compact': compact }" aria-label="文章实体信息">
    <div v-if="!compact" class="entity-heading"><h2>核心实体</h2></div>
    <div class="entity-tags">
      <slot name="prepend" />
      <template v-for="group in visibleGroups" :key="group.label">
        <el-tag v-for="value in group.values" :key="`${group.label}:${value}`" :type="tagTypes[group.label]" size="small" :class="{ 'is-location': group.label === '地点' }" :title="`${group.label}：${value}`" :aria-label="`${group.label}：${value}`"><el-icon class="entity-icon" aria-hidden="true"><component :is="entityIcons[group.label]" /></el-icon><span class="entity-value">{{ value }}</span></el-tag>
      </template>
    </div>
    <p v-if="!compact && !hasEntities" class="entity-note">当前记录尚无已保存的实体结果，处理后会在此展示；不从标题推测实体。</p>
  </section>
</template>
<script setup>
import { computed } from 'vue'
import { Location, Clock, Document, User, OfficeBuilding, Cpu } from '@element-plus/icons-vue'
import { entityGroups } from '@/utils/portal/contentPresentation'
const props = defineProps({ entities: { type: Array, default: () => [] }, compact: Boolean })
const tagTypes = { 地点: 'primary', 时间: 'info', 政策: 'warning', 人物: 'danger', 机构: 'success', 技术: 'primary' }
const entityIcons = { 地点: Location, 时间: Clock, 政策: Document, 人物: User, 机构: OfficeBuilding, 技术: Cpu }
const groups = computed(() => entityGroups(props.entities))
const hasEntities = computed(() => groups.value.some(group => group.values.length))
const visibleGroups = computed(() => groups.value.filter(group => group.values.length))
</script>
<style scoped>
.ps-content-entities { margin: 18px 0; padding: 16px; border: 1px solid var(--ps-line); border-radius: 10px; background: var(--ps-surface, #fff); }
.entity-heading { margin-bottom: 14px; }
.entity-heading h2 { margin: 0; font-size: 16px; }
.entity-tags { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; min-width: 0; }
.entity-tags :deep(.el-tag) { max-width: 100%; height: auto; min-height: 26px; padding: 3px 8px; line-height: 18px; white-space: normal; overflow-wrap: anywhere; }
.entity-tags :deep(.el-tag__content) { display: inline-flex; align-items: center; gap: 4px; min-width: 0; white-space: normal; }
.entity-icon { flex: 0 0 12px; width: 12px; height: 12px; font-size: 12px; }
.entity-value { min-width: 0; overflow-wrap: anywhere; }
.entity-tags .is-location { --el-tag-text-color: #7c3aed; --el-tag-bg-color: #f5f3ff; --el-tag-border-color: #ddd6fe; }
.entity-note { margin: 12px 0 0; color: var(--ps-muted); font-size: 13px; line-height: 1.6; }
.is-compact { margin: 10px 0 0; padding: 0; background: transparent; border: 0; }
</style>
