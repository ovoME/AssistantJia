<script setup lang="ts">
import { onErrorCaptured, ref } from 'vue'
import GlassBackground from '@/components/GlassBackground.vue'
import CuToastHost from '@/components/cu/CuToastHost.vue'

const crash = ref('')

onErrorCaptured((err) => {
  crash.value = err instanceof Error ? err.message : String(err)
  console.error('[全局错误]', err)
  return false
})
</script>

<template>
  <GlassBackground />
  <router-view v-if="!crash" />
  <div v-else class="crash lg-panel">
    <h2>😵 页面出了点问题</h2>
    <p>{{ crash }}</p>
    <button class="cu-btn cu-btn-teal" @click="crash = ''">返回重试</button>
  </div>
  <CuToastHost />
</template>

<style scoped>
.crash {
  position: fixed;
  top: 50%; left: 50%;
  transform: translate(-50%, -50%);
  z-index: 200;
  padding: 28px 32px;
  text-align: center;
  max-width: 420px;
}
.crash h2 { font-size: 18px; font-weight: 700; margin-bottom: 10px; color: var(--ink); }
.crash p { font-size: 13px; color: var(--ink-2); margin-bottom: 18px; word-break: break-word; }
</style>
