<script setup lang="ts">
import { ref, nextTick, watch } from 'vue'

defineProps<{ loading: boolean }>()
const emit = defineEmits<{ send: [text: string]; stop: [] }>()

const text = ref('')
const textarea = ref<HTMLTextAreaElement | null>(null)

function autosize() {
  const ta = textarea.value
  if (!ta) return
  ta.style.height = 'auto'
  ta.style.height = Math.min(ta.scrollHeight, 120) + 'px'
}
watch(text, () => nextTick(autosize))

function submit() {
  const t = text.value.trim()
  if (!t) return
  emit('send', t)
  text.value = ''
  nextTick(autosize)
}
function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
    e.preventDefault()
    submit()
  }
}
</script>

<template>
  <div class="composer lg">
    <span class="lg-inner"></span>
    <textarea
      ref="textarea"
      v-model="text"
      class="field"
      rows="1"
      placeholder="想找什么书？或直接问借阅规则，比如：三体在哪个架位？"
      @keydown="onKeydown"
      @input="autosize"
    ></textarea>
    <button v-if="!loading" class="lg-dot" :disabled="!text.trim()" @click="submit">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
        <path d="M12 19V5M5 12l7-7 7 7" stroke="currentColor" stroke-width="2.2"
          stroke-linecap="round" stroke-linejoin="round" />
      </svg>
    </button>
    <button v-else class="lg-dot stop" @click="emit('stop')">
      <span class="stop-square"></span>
    </button>
  </div>
</template>

<style scoped>
.composer {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  padding: 8px 10px 8px 18px;
  border-radius: 999px;
}
.field {
  flex: 1;
  resize: none;
  border: none;
  outline: none;
  background: transparent;
  font-size: 16px;
  line-height: 1.5;
  color: var(--ink);
  padding: 10px 0;
  max-height: 120px;
  caret-color: var(--ios-teal);
}
.field::placeholder { color: var(--ink-3); }
.lg-dot.stop { background: #1c1c1c; }
.stop-square { width: 14px; height: 14px; background: #fff; border-radius: 3px; }
</style>
