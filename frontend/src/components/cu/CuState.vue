<script setup lang="ts">
/**
 * 通用状态占位：加载中 / 空数据 / 加载失败（带重试）。
 * 用法：
 *   <CuState type="loading" message="正在加载…" />
 *   <CuState type="empty" message="暂无借阅记录" />
 *   <CuState type="error" :message="err" @retry="load" />
 */
withDefaults(
  defineProps<{
    type?: 'loading' | 'error' | 'empty'
    message?: string
  }>(),
  { type: 'loading', message: '' },
)
defineEmits<{ retry: [] }>()
</script>

<template>
  <div class="cu-state" :class="type">
    <div v-if="type === 'loading'" class="state-line">
      <span class="cu-spinner"><span></span><span></span><span></span></span>
      <span class="state-text">{{ message || '加载中…' }}</span>
    </div>
    <template v-else>
      <div class="state-icon">{{ type === 'error' ? '⚠️' : '🫙' }}</div>
      <div class="state-text">{{ message || (type === 'error' ? '加载失败，请稍后重试' : '暂无数据') }}</div>
      <button v-if="type === 'error'" class="cu-btn cu-btn-teal cu-btn-sm" @click="$emit('retry')">
        重新加载
      </button>
    </template>
  </div>
</template>

<style scoped>
.cu-state {
  padding: 40px 24px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 14px;
  text-align: center;
}
.cu-state.error {
  background: rgba(255, 255, 255, 0.75);
  border: 1px solid rgba(255, 159, 10, 0.35);
  border-radius: 20px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.05);
  max-width: 480px;
  margin: 30px auto;
}
.state-line {
  display: flex;
  align-items: center;
  gap: 10px;
}
.state-icon {
  font-size: 40px;
  line-height: 1;
}
.state-text {
  font-size: 15px;
  font-weight: 500;
  line-height: 1.6;
  max-width: 380px;
  color: #16262e;
}
</style>
