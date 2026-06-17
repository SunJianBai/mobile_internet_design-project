<template>
  <AdminLayout v-if="layoutName === 'admin'">
    <RouterView v-slot="{ Component }">
      <Transition name="page-fade" mode="out-in">
        <component :is="Component" />
      </Transition>
    </RouterView>
  </AdminLayout>

  <div v-else-if="layoutName === 'auth'" class="auth-stage">
    <ThemeToggle class="auth-theme-toggle" />
    <div class="auth-stage-shell">
      <section class="auth-copy" aria-label="CampusHub">
        <div class="auth-brand-mark">C</div>
        <h1>CampusHub</h1>
        <p>回到校园活动现场，继续你的预约、动态和协作。</p>
        <div class="auth-signal-grid" aria-hidden="true">
          <span>预约</span>
          <span>动态</span>
          <span>AI</span>
          <span>管理</span>
        </div>
      </section>

      <section class="auth-panel" aria-label="账号入口">
        <RouterView v-slot="{ Component }">
          <Transition name="page-fade" mode="out-in">
            <component :is="Component" />
          </Transition>
        </RouterView>
      </section>
    </div>
  </div>

  <AppShell v-else>
    <RouterView v-slot="{ Component }">
      <Transition name="page-fade" mode="out-in">
        <component :is="Component" />
      </Transition>
    </RouterView>
  </AppShell>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { RouterView, useRoute } from 'vue-router'
import AppShell from './layouts/AppShell.vue'
import AdminLayout from './layouts/AdminLayout.vue'
import ThemeToggle from './components/ThemeToggle.vue'

const route = useRoute()

const layoutName = computed(() => {
  if (route.meta?.layout) return route.meta.layout
  if (route.path.startsWith('/admin')) return 'admin'
  return 'app'
})

onMounted(() => {
  document.documentElement.classList.add('campus-ui-ready')
})
</script>
