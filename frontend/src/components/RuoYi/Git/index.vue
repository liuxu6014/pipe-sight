<template>
  <div>
    <svg-icon icon-class="github" @click="goto" />
  </div>
</template>

<script setup>
const url = ref('https://github.com/liuxu6014/pipe-sight');

function goto() {
  window.open(url.value)
}
</script>
