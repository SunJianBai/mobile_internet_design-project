import { createRouter, createWebHistory } from 'vue-router'
import logger from '../utils/logger'

import ContentDetailView from '../views/ContentDetailView.vue'
import AdminDashboard from '../views/admin/AdminDashboard.vue'
import AdminManagement from '../views/admin/AdminManagement.vue'
const routes = [
  {
    path: '/',
    name: 'Home',
    component: () => import('../views/Home.vue'),
    meta: { title: '首页', requiresAuth: true }
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/Login.vue'),
    meta: { title: '登录', layout: 'auth' }
  },
  {
    path: '/forgot-password',
    name: 'ForgotPassword',
    component: () => import('../views/ForgotPasswordView.vue'),
    meta: { title: '忘记密码', layout: 'auth' }
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('../views/RegisterView.vue'),
    meta: { title: '注册', layout: 'auth' }
  },
  {
    path: '/orders',
    name: 'Orders',
    component: () => import('../views/OrdersView.vue'),
    meta: { title: '订单列表', requiresAuth: true }
  },
  {
    path: '/orders/create',
    name: 'CreateOrder',
    component: () => import('../views/CreateOrderView.vue'),
    meta: { title: '发布订单', requiresAuth: true }
  },
  {
    path: '/orders/:id',
    name: 'OrderDetail',
    component: () => import('../views/OrderDetailView.vue'),
    meta: { title: '订单详情', requiresAuth: true }
  },
  {
    path: '/contents',
    name: 'Contents',
    component: () => import('../views/ContentsView.vue'),
    meta: { title: '动态列表', requiresAuth: true }
  },
  {
    path: '/contents/create',
    name: 'CreateContent',
    component: () => import('../views/CreateContentView.vue'),
    meta: { title: '发布动态', requiresAuth: true }
  },
  {
    path: '/ai',
    name: 'AI',
    component: () => import('../views/AIView.vue'),
    meta: { title: 'AI问询', requiresAuth: true }
  },
  {
    path: '/contents/:id',
    name: 'ContentDetail',
    component: ContentDetailView,
    meta: { requiresAuth: true, title: '动态详情' }
  },
  {
    path: '/user/profile',
    name: 'UserProfile',
    component: () => import('../views/UserProfileView.vue'),
    meta: { title: '个人中心', requiresAuth: true }
  },
  {
    path: '/admin',
    name: 'AdminDashboard',
    component: AdminDashboard,
    meta: {
      title: '控制台',
      description: '平台数据、运营状态与待处理任务总览',
      requiresAuth: true,
      requiresAdmin: true,
      layout: 'admin'
    }
  },
  {
    path: '/admin/users',
    name: 'AdminUsers',
    component: AdminManagement,
    meta: {
      title: '用户管理',
      description: '维护用户资料、权限与账号状态',
      requiresAuth: true,
      requiresAdmin: true,
      layout: 'admin',
      adminMode: 'users'
    }
  },
  {
    path: '/admin/orders',
    name: 'AdminOrders',
    component: AdminManagement,
    meta: {
      title: '活动订单',
      description: '管理活动预约生命周期与运营状态',
      requiresAuth: true,
      requiresAdmin: true,
      layout: 'admin',
      adminMode: 'orders'
    }
  },
  {
    path: '/admin/contents',
    name: 'AdminContents',
    component: AdminManagement,
    meta: {
      title: '动态内容',
      description: '巡检动态内容与媒体发布',
      requiresAuth: true,
      requiresAdmin: true,
      layout: 'admin',
      adminMode: 'contents'
    }
  },
  {
    path: '/admin/comments',
    name: 'AdminComments',
    component: AdminManagement,
    meta: {
      title: '评论审核',
      description: '集中审核用户评论与回复',
      requiresAuth: true,
      requiresAdmin: true,
      layout: 'admin',
      adminMode: 'comments'
    }
  },
  {
    path: '/admin/ai',
    name: 'AdminAI',
    component: AdminManagement,
    meta: {
      title: 'AI会话',
      description: '审计全量 AI 会话、记忆与服务状态',
      requiresAuth: true,
      requiresAdmin: true,
      layout: 'admin',
      adminMode: 'ai'
    }
  },
  {
    path: '/admin/files',
    name: 'AdminFiles',
    component: AdminManagement,
    meta: {
      title: '文件资源',
      description: '管理上传图片、视频与资源引用',
      requiresAuth: true,
      requiresAdmin: true,
      layout: 'admin',
      adminMode: 'files'
    }
  },
  {
    path: '/admin/audit-logs',
    name: 'AdminAuditLogs',
    component: AdminManagement,
    meta: {
      title: '操作日志',
      description: '追踪后台关键操作、操作者与目标对象',
      requiresAuth: true,
      requiresAdmin: true,
      layout: 'admin',
      adminMode: 'logs'
    }
  },
  {
    path: '/admin/settings',
    name: 'AdminSettings',
    component: AdminManagement,
    meta: {
      title: '系统设置',
      description: '配置后台主题、运维偏好与系统策略',
      requiresAuth: true,
      requiresAdmin: true,
      layout: 'admin',
      adminMode: 'settings'
    }
  }
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes
})

// 路由守卫
router.beforeEach((to, from, next) => {
  // 设置页面标题
  document.title = to.meta.title ? `${to.meta.title} - CampusHub` : 'CampusHub'
  
  // 检查是否需要认证
  if (to.meta.requiresAuth) {
    const token = localStorage.getItem('token')
    if (token) {
      if (to.meta.requiresAdmin) {
        const userType = localStorage.getItem('userType')
        const isAdmin = userType === 'ADMIN' || userType === '1'
        if (!isAdmin) {
          next({ name: 'Home' })
          return
        }
      }
      next()
    } else {
      // 带上当前目标路径，登录后可回跳
      next({ name: 'Login', query: { redirect: to.fullPath } })
    }
  } else {
    next()
  }
})

// 路由跳转完成后记录导航日志
router.afterEach((to, from) => {
  logger.event('ROUTE_NAVIGATE', {
    from: from.fullPath,
    to: to.fullPath,
    requiresAuth: to.meta?.requiresAuth || false
  })
})

export default router
