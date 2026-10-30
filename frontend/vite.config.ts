import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    host: true,
    proxy: {
      // 所有后端接口转发到 FastAPI（默认8000）
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    // vendor-echarts 按需后约 540KB（gzip 约182KB），仅在管理端懒加载，属预期体积
    chunkSizeWarningLimit: 600,
    rollupOptions: {
      output: {
        // 第三方库单独分包，利于长期缓存；echarts 仅在管理端路由用到
        manualChunks(id) {
          if (id.includes('node_modules')) {
            if (id.includes('echarts') || id.includes('zrender')) return 'vendor-echarts'
            if (id.includes('vue') || id.includes('pinia') || id.includes('@vue')) return 'vendor-vue'
          }
        },
      },
    },
  },
})
