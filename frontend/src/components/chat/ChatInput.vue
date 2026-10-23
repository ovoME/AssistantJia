<script setup lang="ts">
import { ref } from 'vue'
import { NButton, NInput } from 'naive-ui'

defineProps<{ loading: boolean }>()
const emit = defineEmits<{
  send: [text: string]
  stop: []
}>()

const text = ref('')

function submit() {
  if (!text.value.trim()) return
  emit('send', text.value)
  text.value = ''
}
</script>

<template>
  <div class="chat-input">
    <NInput
      v-model:value="text"
      type="textarea"
      :autosize="{ minRows: 1, maxRows: 4 }"
      placeholder="想找什么书？或直接问借阅规则，比如：三体在哪个架位？"
      :bordered="false"
      @keydown.enter.exact.prevent="submit"
    />
    <NButton
      v-if="!loading"
      type="primary"
      circle
      class="send-btn"
      @click="submit"
    >
      ↑
    </NButton>
    <NButton v-else type="warning" circle class="send-btn" @click="emit('stop')">
      ■
    </NButton>
  </div>
</template>

<style scoped>
.chat-input {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  padding: 12px 14px;
  background: #fff;
  border-top: 1px solid #eef2f7;
  border-radius: 0 0 16px 16px;
}
.send-btn {
  flex: 0 0 auto;
  width: 40px;
  height: 40px;
  font-size: 16px;
}
</style>
