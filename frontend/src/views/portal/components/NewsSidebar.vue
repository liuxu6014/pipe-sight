<template>
  <aside class="news-feed-sidebar news-sidebar" aria-label="新闻资讯导航">
    <button class="news-side-primary" type="button" @click="$emit('open-news')">
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M4 10.5 12 4l8 6.5"></path>
        <path d="M6.5 10v9h11v-9"></path>
        <path d="M10 19v-5h4v5"></path>
      </svg>
      <span>资讯情报</span>
    </button>

    <div class="news-side-section">
      <strong>我的工作区</strong>
      <button type="button" @click="$emit('coming-soon', '历史记录')">
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M4 12a8 8 0 1 0 2.3-5.7"></path>
          <path d="M4 5v5h5"></path>
          <path d="M12 8v5l3 2"></path>
        </svg>
        <span>历史记录</span>
      </button>
    </div>

    <div class="news-side-section news-focus-list">
      <strong>我的关注领域</strong>
      <button v-for="topic in topics" :key="topic.name" type="button" @click="$emit('topic-select', topic.name)">
        <span>{{ topic.name }}</span>
      </button>
    </div>

    <div class="news-side-bottom">
      <strong>今日概览</strong>
      <div v-for="item in stats.slice(0, 3)" :key="item.label" class="news-side-stat">
        <span>{{ item.label }}</span>
        <em>{{ item.value }}{{ item.unit }}</em>
      </div>
    </div>
  </aside>
</template>

<script setup>
defineProps({
  topics: {
    type: Array,
    default: () => [],
  },
  stats: {
    type: Array,
    default: () => [],
  },
})

defineEmits(['open-news', 'coming-soon', 'topic-select'])
</script>
