<template>
  <div class="app-shell">
    <header class="app-topbar">
      <router-link to="/" class="brand-lockup" aria-label="CampusHub 首页">
        <span class="brand-mark">C</span>
        <span>
          <strong>CampusHub</strong>
          <small>校园活动预约与分享平台</small>
        </span>
      </router-link>

      <nav class="desktop-nav" aria-label="主导航">
        <router-link v-for="item in navItems" :key="item.path" :to="item.path">
          <el-icon><component :is="item.icon" /></el-icon>
          <span>{{ item.label }}</span>
        </router-link>
      </nav>

      <div class="topbar-actions">
        <el-button class="publish-button" type="primary" @click="router.push('/orders/create')">
          <el-icon><Plus /></el-icon>
          发布活动
        </el-button>
        <ThemeToggle />
        <el-dropdown v-if="isAuthenticated" trigger="click">
          <button class="user-chip">
            <img v-if="navAvatarUrl" :src="navAvatarUrl" alt="avatar" @error="onNavAvatarError" />
            <span v-else class="avatar-fallback">{{ userInitial }}</span>
            <span class="user-name">{{ userInfo?.nickname || '用户' }}</span>
            <el-icon><ArrowDown /></el-icon>
          </button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="router.push('/user/profile')">个人中心</el-dropdown-item>
              <el-dropdown-item @click="router.push('/contents/create')">发布动态</el-dropdown-item>
              <el-dropdown-item v-if="isAdmin" @click="router.push('/admin')">后台管理</el-dropdown-item>
              <el-dropdown-item divided @click="handleLogout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <div v-else class="auth-links">
          <router-link to="/login">登录</router-link>
          <router-link to="/register">注册</router-link>
        </div>
        <el-dropdown class="mobile-nav" trigger="click">
          <el-button circle>
            <el-icon><Menu /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item v-for="item in navItems" :key="item.path" @click="router.push(item.path)">
                {{ item.label }}
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </header>

    <section v-if="maintenanceNotice" class="maintenance-banner" role="status">
      <el-icon><InfoFilled /></el-icon>
      <span>{{ maintenanceNotice }}</span>
    </section>

    <main class="app-main">
      <slot />
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  ArrowDown,
  ChatDotRound,
  Compass,
  House,
  InfoFilled,
  MagicStick,
  Menu,
  Plus,
  Tickets
} from '@element-plus/icons-vue'
import ThemeToggle from '../components/ThemeToggle.vue'
import { getPublicSystemInfo } from '../services/system'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const navItems = [
  { label: '首页', path: '/', icon: House },
  { label: '活动', path: '/orders', icon: Tickets },
  { label: '动态', path: '/contents', icon: ChatDotRound },
  { label: 'AI助手', path: '/ai', icon: MagicStick },
  { label: '我的', path: '/user/profile', icon: Compass }
]

const userInfo = computed(() => authStore.user)
const isAuthenticated = computed(() => authStore.isAuthenticated)
const isAdmin = computed(() => {
  const value = userInfo.value?.userType
  return value === 'ADMIN' || value === 1
})

const navAvatarUrl = ref(null)
const maintenanceNotice = ref('')
const fileBaseUrl =
  import.meta.env.VITE_FILE_BASE_URL || (import.meta.env.PROD ? '' : 'http://localhost:8080')

const resolveUrl = (url) => {
  if (!url) return null
  if (/^https?:\/\//.test(url)) return url
  return `${fileBaseUrl}${url}`
}

const userInitial = computed(() => {
  if (userInfo.value?.nickname) return userInfo.value.nickname.slice(0, 1)
  if (userInfo.value?.email) return userInfo.value.email.slice(0, 1).toUpperCase()
  return '用'
})

watch(
  userInfo,
  (val) => {
    navAvatarUrl.value = val?.avatarUrl ? resolveUrl(val.avatarUrl) : null
  },
  { immediate: true }
)

const onNavAvatarError = () => {
  navAvatarUrl.value = null
}

const handleLogout = async () => {
  await authStore.logout()
  router.push('/login')
}

const loadPublicSystemInfo = async () => {
  try {
    const response = await getPublicSystemInfo()
    maintenanceNotice.value = String(response?.data?.maintenanceNotice || '').trim()
  } catch (error) {
    maintenanceNotice.value = ''
  }
}

onMounted(loadPublicSystemInfo)
</script>
