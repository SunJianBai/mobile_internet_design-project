import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  base: process.env.VITE_PUBLIC_PATH || (process.env.NODE_ENV === 'production' ? '/CampusHub/' : '/'),
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return

          const normalized = id.replace(/\\/g, '/')
          if (normalized.includes('@element-plus/icons-vue')) {
            return 'vendor-element-icons'
          }
          if (normalized.includes('element-plus')) {
            return 'vendor-element-plus'
          }
          if (
            normalized.includes('/vue/') ||
            normalized.includes('/vue-router/') ||
            normalized.includes('/pinia/')
          ) {
            return 'vendor-vue'
          }
          if (normalized.includes('/axios/')) {
            return 'vendor-axios'
          }
          return 'vendor'
        }
      }
    }
  },
  server: {
    port: 5173,
    proxy: {
      // 前端所有以 /api 开头的请求，转发到后端 http://localhost:8080
      // axios 的 baseURL 是 /api/v1，因此在开发环境下会由 Vite 代理到后端 /api/v1
      '/api': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
      '/CampusHub/api': {
        target: 'http://localhost:8080',
        changeOrigin: true,
        rewrite: path => path.replace(/^\/CampusHub/, ''),
      }
    }
  }
})
