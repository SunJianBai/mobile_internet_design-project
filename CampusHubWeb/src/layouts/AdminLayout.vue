<template>
  <div class="admin-shell" :class="{ 'admin-mobile-menu-open': mobileMenuOpen }">
    <aside class="admin-sidebar" :class="{ collapsed, 'mobile-open': mobileMenuOpen }">
      <router-link to="/admin" class="admin-brand">
        <span class="admin-brand-mark">CH</span>
        <span v-if="showSidebarText">
          <strong>CampusHub</strong>
          <small>Admin Console</small>
        </span>
      </router-link>

      <nav class="admin-menu" aria-label="后台管理导航">
        <router-link v-for="item in menuItems" :key="item.path" :to="item.path" @click="closeMobileMenu">
          <el-icon><component :is="item.icon" /></el-icon>
          <span v-if="showSidebarText">{{ item.label }}</span>
        </router-link>
      </nav>
    </aside>
    <button
      class="admin-sidebar-backdrop"
      :class="{ visible: mobileMenuOpen }"
      type="button"
      aria-label="关闭后台导航"
      @click="closeMobileMenu"
    ></button>

    <section class="admin-workspace">
      <header class="admin-topbar">
        <div class="admin-topbar-left">
          <el-button
            class="icon-button"
            circle
            :aria-label="isMobile ? '打开后台导航' : '折叠后台导航'"
            @click="toggleNavigation"
          >
            <el-icon>
              <MenuIcon v-if="isMobile" />
              <Fold v-else-if="!collapsed" />
              <Expand v-else />
            </el-icon>
          </el-button>
          <div>
            <h1>{{ route.meta.title || '后台管理' }}</h1>
            <p>{{ route.meta.description || '管理 CampusHub 的用户、活动、内容与系统状态' }}</p>
          </div>
        </div>

        <div class="admin-topbar-actions">
          <el-input
            v-model="searchText"
            class="admin-search"
            placeholder="搜索用户 / 活动 / 动态"
            clearable
            @keyup.enter="applyGlobalSearch"
            @clear="clearGlobalSearch"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
          <ThemeToggle />
          <el-popover
            v-model:visible="notificationVisible"
            placement="bottom-end"
            trigger="click"
            width="320"
            popper-class="admin-notification-popper"
          >
            <template #reference>
              <el-button
                class="icon-button admin-notification-trigger"
                circle
                :aria-label="'运营提醒'"
                :title="'运营提醒'"
                @click="loadNotifications"
              >
                <el-badge :value="notificationCount" :hidden="notificationCount === 0" :max="99">
                  <el-icon><Bell /></el-icon>
                </el-badge>
              </el-button>
            </template>
            <div class="admin-notifications">
              <div class="notification-head">
                <strong>运营提醒</strong>
                <el-button link type="primary" :loading="notificationLoading" @click="loadNotifications">刷新</el-button>
              </div>
              <button
                v-for="item in notificationItems"
                :key="item.title"
                class="notification-item"
                type="button"
                :aria-label="`打开${item.title}`"
                @click="goNotification(item.path)"
              >
                <span :class="['dot', item.tone]"></span>
                <span>
                  <strong>{{ item.title }}</strong>
                  <small>{{ item.desc }}</small>
                </span>
                <el-tag size="small" effect="plain">{{ item.count }}</el-tag>
              </button>
            </div>
          </el-popover>
          <el-dropdown trigger="click" @command="handleAdminCommand">
            <button class="admin-user" type="button" aria-label="管理员账号菜单">
              <span>{{ adminInitial }}</span>
              <strong>{{ authStore.user?.nickname || 'Admin' }}</strong>
              <el-icon><ArrowDown /></el-icon>
            </button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="profile">个人中心</el-dropdown-item>
                <el-dropdown-item command="settings">系统设置</el-dropdown-item>
                <el-dropdown-item command="home">返回前台</el-dropdown-item>
                <el-dropdown-item divided command="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </header>

      <main class="admin-main">
        <slot />
      </main>
    </section>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ArrowDown,
  Bell,
  ChatDotRound,
  Collection,
  DataAnalysis,
  Document,
  Expand,
  Files,
  Fold,
  Menu as MenuIcon,
  Operation,
  Search,
  Setting,
  Tickets,
  UserFilled
} from '@element-plus/icons-vue'
import ThemeToggle from '../components/ThemeToggle.vue'
import { getAdminStatistics } from '../services/admin'
import { useAuthStore } from '../stores/auth'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const collapsed = ref(false)
const isMobile = ref(false)
const mobileMenuOpen = ref(false)
const searchText = ref(typeof route.query.q === 'string' ? route.query.q : '')
const notificationLoading = ref(false)
const notificationStats = ref({})
const notificationVisible = ref(false)

const number = (value) => Number(value || 0)

const menuItems = [
  { label: '控制台', path: '/admin', icon: DataAnalysis },
  { label: '用户管理', path: '/admin/users', icon: UserFilled },
  { label: '活动订单', path: '/admin/orders', icon: Tickets },
  { label: '动态内容', path: '/admin/contents', icon: Collection },
  { label: '评论审核', path: '/admin/comments', icon: ChatDotRound },
  { label: 'AI会话', path: '/admin/ai', icon: Operation },
  { label: '文件资源', path: '/admin/files', icon: Files },
  { label: '操作日志', path: '/admin/audit-logs', icon: Document },
  { label: '系统设置', path: '/admin/settings', icon: Setting },
  { label: '返回前台', path: '/', icon: Document }
]

const adminInitial = computed(() => {
  const name = authStore.user?.nickname || authStore.user?.email || 'A'
  return name.slice(0, 1).toUpperCase()
})

const showSidebarText = computed(() => !collapsed.value || isMobile.value)

const notificationItems = computed(() => [
  {
    title: '活动待办',
    desc: '处理待匹配订单和报名申请',
    count: number(notificationStats.value.pendingOrderCount) + number(notificationStats.value.pendingApplicationCount),
    tone: 'blue',
    path: '/admin/orders'
  },
  {
    title: '动态待审',
    desc: '审核待发布的用户动态',
    count: number(notificationStats.value.pendingPostCount),
    tone: 'orange',
    path: '/admin/contents'
  },
  {
    title: '评论审核',
    desc: '处理待审核评论与回复互动',
    count: number(notificationStats.value.pendingCommentCount),
    tone: 'green',
    path: '/admin/comments'
  },
  {
    title: 'AI会话巡检',
    desc: '检查助手会话与长期记忆质量',
    count: '巡检',
    tone: 'red',
    path: '/admin/ai'
  }
])

const notificationCount = computed(() => (
  number(notificationStats.value.pendingOrderCount) +
  number(notificationStats.value.pendingApplicationCount) +
  number(notificationStats.value.pendingPostCount) +
  number(notificationStats.value.pendingCommentCount)
))

const loadNotifications = async () => {
  notificationLoading.value = true
  try {
    const response = await getAdminStatistics()
    notificationStats.value = response.data || {}
  } finally {
    notificationLoading.value = false
  }
}

const goNotification = (path) => {
  notificationVisible.value = false
  router.push(path)
}

const handleAdminCommand = async (command) => {
  if (command === 'profile') {
    router.push('/user/profile')
    return
  }
  if (command === 'settings') {
    router.push('/admin/settings')
    return
  }
  if (command === 'home') {
    router.push('/')
    return
  }
  if (command === 'logout') {
    await authStore.logout()
    router.push('/login')
  }
}

const closeMobileMenu = () => {
  mobileMenuOpen.value = false
}

const toggleNavigation = () => {
  if (isMobile.value) {
    mobileMenuOpen.value = !mobileMenuOpen.value
    return
  }
  collapsed.value = !collapsed.value
}

let mobileQuery

const syncMobileState = () => {
  if (!mobileQuery) return
  isMobile.value = mobileQuery.matches
  if (!isMobile.value) {
    mobileMenuOpen.value = false
  }
}

const applyGlobalSearch = () => {
  const q = searchText.value.trim()
  const targetPath = route.path === '/admin' ? '/admin/users' : route.path
  router.push({
    path: targetPath,
    query: {
      ...route.query,
      q: q || undefined
    }
  })
}

const clearGlobalSearch = () => {
  router.push({
    path: route.path,
    query: {
      ...route.query,
      q: undefined
    }
  })
}

watch(
  () => route.query.q,
  (value) => {
    searchText.value = typeof value === 'string' ? value : ''
  }
)

watch(
  () => route.path,
  () => {
    closeMobileMenu()
  }
)

onMounted(() => {
  mobileQuery = window.matchMedia('(max-width: 980px)')
  syncMobileState()
  mobileQuery.addEventListener('change', syncMobileState)
  loadNotifications()
})

onBeforeUnmount(() => {
  mobileQuery?.removeEventListener('change', syncMobileState)
})
</script>
