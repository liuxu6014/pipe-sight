<template>
  <header class="ps-page-header" :class="{ 'is-compact': !description, 'is-actions-only': !showTitle }">
    <div v-if="showTitle">
      <h1>{{ title }}</h1>
      <p v-if="description">{{ description }}</p>
    </div>
    <div v-if="$slots.actions" class="ps-page-actions">
      <slot name="actions" />
    </div>
  </header>
</template>

<script setup>
defineProps({
  title: { type: String, required: true },
  showTitle: { type: Boolean, default: true },
  description: { type: String, default: '' }
})
</script>

<style scoped>
.ps-page-header.is-actions-only { min-height: 44px; margin-bottom: 16px; justify-content: flex-end; }
.ps-page-header.is-actions-only > .ps-page-actions { flex: 0 1 auto; }
</style>
