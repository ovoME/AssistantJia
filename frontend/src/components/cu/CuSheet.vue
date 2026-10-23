<script setup lang="ts">
import { watch } from 'vue'

const props = defineProps<{
  modelValue: boolean
  title: string
}>()
const emit = defineEmits<{ 'update:modelValue': [v: boolean] }>()

function close() {
  emit('update:modelValue', false)
}
function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') close()
}
watch(
  () => props.modelValue,
  (v) => {
    if (v) {
      window.addEventListener('keydown', onKeydown)
      document.body.style.overflow = 'hidden'
    } else {
      window.removeEventListener('keydown', onKeydown)
      document.body.style.overflow = ''
    }
  }
)
</script>

<template>
  <Teleport to="body">
    <Transition name="sheet">
      <div v-if="modelValue" class="modal-mask">
        <div class="cu-scrim" @click="close"></div>
        <div class="modal lg-panel" role="dialog" aria-modal="true">
          <div class="modal-head">
            <h3>{{ title }}</h3>
            <button class="cu-btn cu-btn-plain" @click="close">关闭</button>
          </div>
          <div class="modal-body">
            <slot />
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
/* 遮罩：全屏 + 居中承载面板 */
.modal-mask {
  position: fixed;
  inset: 0;
  z-index: 90;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}
/* 遮罩：仅变暗，不加背景模糊（避免与面板磨砂嵌套） */
.cu-scrim {
  position: absolute;
  inset: 0;
  z-index: 1;
  background: rgba(20, 30, 38, 0.36);
}
/* 居中模态对话框：四周圆角、悬浮投影 */
.modal {
  position: relative;
  z-index: 2;
  width: min(92vw, 620px);
  max-height: 82vh;
  border-radius: 24px;
  padding: 20px 22px max(22px, env(safe-area-inset-bottom));
  display: flex;
  flex-direction: column;
  box-shadow: 0 24px 64px rgba(20, 45, 58, 0.32);
}
.modal-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
  flex-shrink: 0;
}
.modal-head h3 {
  font-size: 18px;
  font-weight: 700;
  color: var(--ink);
}
.modal-body {
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  padding-bottom: 6px;
}

/* 入场：遮罩淡入，面板轻微缩放淡入（不再从底部滑入） */
.sheet-enter-active .cu-scrim,
.sheet-leave-active .cu-scrim {
  transition: opacity 0.25s ease;
}
.sheet-enter-from .cu-scrim,
.sheet-leave-to .cu-scrim {
  opacity: 0;
}
.sheet-enter-active .modal {
  transition: transform 0.36s cubic-bezier(0.23, 1, 0.32, 1), opacity 0.25s ease;
}
.sheet-leave-active .modal {
  transition: transform 0.2s cubic-bezier(0.4, 0, 1, 1), opacity 0.2s ease;
}
.sheet-enter-from .modal,
.sheet-leave-to .modal {
  opacity: 0;
  transform: scale(0.94) translateY(10px);
}

@media (prefers-reduced-motion: reduce) {
  .sheet-enter-active .modal,
  .sheet-leave-active .modal {
    transition: none;
  }
}
</style>
