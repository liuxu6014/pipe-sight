<template>
  <span class="ps-user-avatar">
    <img v-if="src && !failed" :src="src" alt="个人头像" @error="failed = true" />
    <template v-else>{{ initial }}</template>
  </span>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import useUserStore from '@/store/modules/user'
import defaultAvatar from '@/assets/images/profile.jpg'

const userStore = useUserStore()
const failed = ref(false)
const src = computed(() => userStore.avatar === defaultAvatar ? '' : userStore.avatar)
const initial = computed(() => (userStore.nickName || userStore.name || '管网用户').slice(0, 1))
watch(src, () => { failed.value = false })
</script>

<style scoped>
.ps-user-avatar { overflow: hidden; }
.ps-user-avatar img { display: block; width: 100%; height: 100%; object-fit: cover; }
</style>
