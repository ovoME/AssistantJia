<script setup lang="ts">
import { toasts } from '@/composables/useToast'
</script>

<template>
  <div class="toast-host" aria-live="polite">
    <TransitionGroup name="toast">
      <div v-for="t in toasts" :key="t.id" class="toast" :class="t.type">
        <span class="ic">
          <svg v-if="t.type === 'success'" viewBox="0 0 24 24" width="15" height="15"><path fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" d="M5 12.5l4.5 4.5L19 7.5"/></svg>
          <svg v-else-if="t.type === 'error'" viewBox="0 0 24 24" width="15" height="15"><path fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" d="M7 7l10 10M17 7L7 17"/></svg>
          <svg v-else viewBox="0 0 24 24" width="15" height="15"><path fill="currentColor" d="M12 2a10 10 0 100 20 10 10 0 000-20zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/></svg>
        </span>
        <span class="txt">{{ t.text }}</span>
      </div>
    </TransitionGroup>
  </div>
</template>

<style scoped>
.toast-host {
  position: fixed;
  top: 92px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 200;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  pointer-events: none;
  width: min(92vw, 460px);
}
.toast {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 12px 18px;
  border-radius: 999px;
  font-size: 14px;
  font-weight: 500;
  color: #fff;
  /* 深色液态玻璃胶囊，在任意浅色背景上都清晰 */
  background: rgba(28, 33, 40, 0.9);
  -webkit-backdrop-filter: blur(20px) saturate(160%);
  backdrop-filter: blur(20px) saturate(160%);
  border: 1px solid rgba(255, 255, 255, 0.14);
  box-shadow:
    inset 0 1px 1px rgba(255, 255, 255, 0.2),
    0 12px 32px rgba(15, 25, 35, 0.38);
  line-height: 1.35;
}
.ic {
  display: flex;
  align-items: center;
  flex-shrink: 0;
}
.success .ic { color: #5ef0a0; }
.error .ic { color: #ff8177; }
.info .ic { color: #6aa9ff; }

.toast-enter-active {
  transition: transform 0.4s var(--ease-spring), opacity 0.25s var(--ease-out);
}
.toast-leave-active {
  transition: transform 0.2s var(--ease-out), opacity 0.2s;
}
.toast-enter-from {
  opacity: 0;
  transform: translateY(-18px) scale(0.92);
}
.toast-leave-to {
  opacity: 0;
  transform: translateY(-12px) scale(0.95);
}
</style>
