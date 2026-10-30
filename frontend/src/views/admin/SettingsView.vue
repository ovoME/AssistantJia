<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useToast } from '@/composables/useToast'
import { http } from '@/api/request'

const router = useRouter()
const toast = useToast()

const apiKey = ref('')
const baseUrl = ref('https://open.bigmodel.cn/api/paas/v4/')
const model = ref('glm-4-flash')
const temperature = ref(0.3)
const saving = ref(false)
const loaded = ref(false)

onMounted(async () => {
  try {
    const cfg = await http.get<unknown, { api_key: string; base_url: string; model: string; temperature: number; is_configured: boolean }>('/admin/config/llm')
    baseUrl.value = cfg.base_url
    model.value = cfg.model
    temperature.value = cfg.temperature
    loaded.value = true
  } catch (e) {
    toast.error((e as Error).message || '加载配置失败')
  }
})

async function save() {
  saving.value = true
  try {
    await http.put<unknown, { message: string }>('/admin/config/llm', {
      api_key: apiKey.value,
      base_url: baseUrl.value,
      model: model.value,
      temperature: temperature.value,
    })
    toast.success('配置已保存，重启后端后生效')
    apiKey.value = ''
  } catch (e) {
    toast.error((e as Error).message || '保存失败')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="settings-page">
    <header class="topbar lg lg-r22">
      <span class="lg-inner"></span>
      <div class="brand">
        <div class="brand-text">
          <div class="brand-name">系统设置</div>
          <div class="brand-sub">LLM 大模型配置</div>
        </div>
      </div>
      <div class="actions">
        <button class="cu-btn cu-btn-plain" @click="router.push('/admin')">返回看板</button>
      </div>
    </header>

    <main class="content">
      <div class="panel lg lg-r18">
        <span class="lg-inner"></span>
        <h2>大模型 API 配置</h2>
        <p class="hint">配置 AI 对话使用的大模型服务。支持 OpenAI 兼容接口（智谱 GLM、DeepSeek、通义千问等）。</p>

        <div class="form-group">
          <label>API Key</label>
          <input
            v-model="apiKey"
            type="password"
            placeholder="输入新的 API Key（留空则不修改）"
            class="cu-input"
          />
        </div>

        <div class="form-group">
          <label>API Base URL</label>
          <input v-model="baseUrl" type="text" class="cu-input" />
          <p class="sub-hint">智谱 GLM: https://open.bigmodel.cn/api/paas/v4/</p>
          <p class="sub-hint">DeepSeek: https://api.deepseek.com</p>
        </div>

        <div class="form-row">
          <div class="form-group">
            <label>模型名称</label>
            <input v-model="model" type="text" class="cu-input" />
            <p class="sub-hint">如 glm-4-flash / glm-4-air / deepseek-chat</p>
          </div>
          <div class="form-group">
            <label>Temperature</label>
            <input v-model.number="temperature" type="number" step="0.1" min="0" max="1" class="cu-input" />
          </div>
        </div>

        <div class="actions-row">
          <button class="cu-btn cu-btn-teal" :disabled="saving" @click="save">
            {{ saving ? '保存中...' : '保存配置' }}
          </button>
        </div>

        <p class="note">⚠️ 保存后需要重启后端服务才能生效。</p>
      </div>
    </main>
  </div>
</template>

<style scoped>
.settings-page {
  max-width: 640px;
  margin: 0 auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
}
.brand-name { font-size: 17px; font-weight: 700; color: var(--ink); }
.brand-sub { font-size: 12px; color: var(--ink-3); margin-top: 2px; }
.content { display: flex; flex-direction: column; gap: 16px; }
.panel {
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
h2 { font-size: 18px; font-weight: 700; color: var(--ink); margin: 0; }
.hint { font-size: 13px; color: var(--ink-3); margin: 0; line-height: 1.5; }
.form-group { display: flex; flex-direction: column; gap: 6px; flex: 1; }
.form-row { display: flex; gap: 16px; }
label { font-size: 13px; font-weight: 600; color: var(--ink-2); }
.cu-input {
  padding: 10px 14px;
  border-radius: 12px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(255, 255, 255, 0.6);
  font-size: 14px;
  outline: none;
  transition: border-color 0.15s;
}
.cu-input:focus { border-color: #007aff; }
.sub-hint { font-size: 11px; color: var(--ink-3); margin: 2px 0 0; }
.actions-row { display: flex; gap: 12px; margin-top: 8px; }
.note { font-size: 12px; color: #f59e0b; margin: 0; }
</style>
