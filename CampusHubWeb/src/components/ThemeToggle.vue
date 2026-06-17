<template>
  <el-button class="theme-toggle" circle :aria-label="label" @click="toggleTheme">
    <el-icon>
      <Moon v-if="isDark" />
      <Sunny v-else />
    </el-icon>
  </el-button>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { Moon, Sunny } from '@element-plus/icons-vue'

const STORAGE_KEY = 'campushub-theme'
const isDark = ref(false)

const label = computed(() => (isDark.value ? '切换到亮色模式' : '切换到暗色模式'))

const applyTheme = (dark) => {
  isDark.value = dark
  document.documentElement.dataset.theme = dark ? 'dark' : 'light'
  document.documentElement.classList.toggle('dark', dark)
  localStorage.setItem(STORAGE_KEY, dark ? 'dark' : 'light')
}

const toggleTheme = () => {
  applyTheme(!isDark.value)
}

onMounted(() => {
  const saved = localStorage.getItem(STORAGE_KEY)
  if (saved) {
    applyTheme(saved === 'dark')
    return
  }
  applyTheme(window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false)
})
</script>
