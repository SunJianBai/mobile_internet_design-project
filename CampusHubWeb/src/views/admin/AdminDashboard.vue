<template>
  <div class="admin-page">
    <section class="admin-kpi-grid">
      <button
        v-for="card in kpiCards"
        :key="card.label"
        type="button"
        class="metric-card metric-card-action"
        @click="go(card.path)"
      >
        <span class="metric-icon" :class="card.tone">
          <el-icon><component :is="card.icon" /></el-icon>
        </span>
        <div>
          <p>{{ card.label }}</p>
          <strong>{{ card.value }}</strong>
          <small>{{ card.hint }}</small>
        </div>
      </button>
    </section>

    <section class="admin-grid admin-grid-main">
      <el-card class="admin-panel" shadow="never">
        <template #header>
          <div class="panel-title">
            <span>平台运行概览</span>
            <el-tag type="success" effect="light">实时接口</el-tag>
          </div>
        </template>
        <div class="status-bars">
          <div v-for="item in orderBars" :key="item.label" class="status-row">
            <div class="status-row-meta">
              <span>{{ item.label }}</span>
              <strong>{{ item.value }}</strong>
            </div>
            <div class="bar-track">
              <i :style="{ width: item.percent + '%', background: item.color }"></i>
            </div>
          </div>
        </div>
      </el-card>

      <el-card class="admin-panel" shadow="never">
        <template #header>
          <div class="panel-title">
            <span>最近待处理</span>
            <el-button text type="primary" @click="$router.push('/admin/orders')">查看全部</el-button>
          </div>
        </template>
        <div class="pending-list">
          <button
            v-for="item in pendingItems"
            :key="item.title"
            type="button"
            class="pending-item pending-item-action"
            @click="go(item.path)"
          >
            <span :class="['dot', item.tone]"></span>
            <div>
              <strong>{{ item.title }}</strong>
              <p>{{ item.desc }}</p>
            </div>
            <el-tag size="small" effect="plain">{{ item.count }}</el-tag>
          </button>
        </div>
      </el-card>
    </section>

    <el-card class="admin-panel" shadow="never">
      <template #header>
        <div class="panel-title">
          <span>运营动作</span>
          <el-button type="primary" @click="refresh">刷新数据</el-button>
        </div>
      </template>
      <el-table :data="operationRows" v-loading="loading" class="admin-table">
        <el-table-column prop="module" label="模块" width="140" />
        <el-table-column prop="metric" label="关键指标" />
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="row.type" effect="light">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="action" label="建议动作" />
        <el-table-column label="入口" width="110" align="right">
          <template #default="{ row }">
            <el-button text type="primary" @click.stop="go(row.path)">进入</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="dashboard-mobile-actions">
        <button
          v-for="row in operationRows"
          :key="row.module"
          type="button"
          class="dashboard-action-card"
          @click="go(row.path)"
        >
          <div>
            <strong>{{ row.module }}</strong>
            <el-tag :type="row.type" effect="light" size="small">{{ row.status }}</el-tag>
          </div>
          <p>{{ row.metric }}</p>
          <span>{{ row.action }}</span>
        </button>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ChatDotRound, Collection, Tickets, UserFilled } from '@element-plus/icons-vue'
import { getAdminStatistics } from '../../services/admin'

const router = useRouter()
const loading = ref(false)
const stats = ref({})

const number = (value) => Number(value || 0)
const count = (field) => number(stats.value[field])

const kpiCards = computed(() => [
  {
    label: '总用户',
    value: count('userCount'),
    hint: `今日活跃 ${count('todayActiveUsers')} / 在线 ${count('onlineUserCount')}`,
    icon: UserFilled,
    tone: 'blue',
    path: '/admin/users'
  },
  {
    label: '活动订单',
    value: count('orderCount'),
    hint: `待匹配 ${count('pendingOrderCount')} / 申请待审 ${count('pendingApplicationCount')}`,
    icon: Tickets,
    tone: 'green',
    path: '/admin/orders'
  },
  {
    label: '内容治理',
    value: count('contentCount'),
    hint: `待审 ${count('pendingContentCount')} / 已删 ${count('deletedContentCount')}`,
    icon: Collection,
    tone: 'orange',
    path: '/admin/contents'
  },
  {
    label: 'AI资产',
    value: count('aiConversationCount'),
    hint: `消息 ${count('aiMessageCount')} / 记忆 ${count('aiMemoryCount')}`,
    icon: ChatDotRound,
    tone: 'red',
    path: '/admin/ai'
  }
])

const orderBars = computed(() => {
  const total = Math.max(count('orderCount'), 1)
  return [
    { label: '待匹配', value: count('pendingOrderCount'), color: '#3b82f6' },
    { label: '进行中', value: count('inProgressOrderCount'), color: '#22c55e' },
    { label: '已完成', value: count('completedOrderCount'), color: '#f59e0b' },
    { label: '已取消', value: count('cancelledOrderCount'), color: '#94a3b8' },
    { label: '已过期', value: count('expiredOrderCount'), color: '#ef4444' }
  ].map((item) => ({ ...item, percent: Math.round((item.value / total) * 100) }))
})

const pendingItems = computed(() => [
  {
    title: '报名申请待审',
    desc: '需要处理活动报名申请',
    count: count('pendingApplicationCount'),
    tone: 'blue',
    path: '/admin/orders'
  },
  {
    title: '内容待审',
    desc: '动态或评论处于待审核状态',
    count: count('pendingContentCount'),
    tone: 'orange',
    path: '/admin/contents'
  },
  {
    title: '封禁账号',
    desc: '账号已被管理员限制登录',
    count: count('bannedUserCount'),
    tone: 'red',
    path: '/admin/users'
  },
  {
    title: '文件资源',
    desc: `图片 ${count('imageFileCount')} / 视频 ${count('videoFileCount')}`,
    count: count('fileCount'),
    tone: 'green',
    path: '/admin/files'
  }
])

const operationRows = computed(() => [
  {
    module: '用户管理',
    metric: `普通 ${count('commonUserCount')} / 管理员 ${count('adminCount')} / 封禁 ${count('bannedUserCount')}`,
    status: count('bannedUserCount') > 0 ? '需关注' : '正常',
    type: count('bannedUserCount') > 0 ? 'warning' : 'success',
    action: '维护管理员权限，排查封禁与异常账号',
    path: '/admin/users'
  },
  {
    module: '活动订单',
    metric: `待匹配 ${count('pendingOrderCount')} / 申请待审 ${count('pendingApplicationCount')}`,
    status: count('pendingApplicationCount') > 0 ? '待处理' : '良好',
    type: count('pendingApplicationCount') > 0 ? 'warning' : 'success',
    action: '处理报名申请，跟进临近开始时间的活动',
    path: '/admin/orders'
  },
  {
    module: '内容治理',
    metric: `正常动态 ${count('postCount')} / 正常评论 ${count('commentCount')} / 待审 ${count('pendingContentCount')}`,
    status: count('pendingContentCount') > 0 ? '待审' : '运行中',
    type: count('pendingContentCount') > 0 ? 'warning' : 'primary',
    action: '审核待审内容，恢复误删内容或驳回违规互动',
    path: '/admin/contents'
  },
  {
    module: '文件资源',
    metric: `总资源 ${count('fileCount')} / 图片 ${count('imageFileCount')} / 视频 ${count('videoFileCount')}`,
    status: count('fileCount') > 0 ? '可巡检' : '空闲',
    type: 'info',
    action: '清理无效资源，核对违规媒体引用',
    path: '/admin/files'
  },
  {
    module: 'AI助手',
    metric: `会话 ${count('aiConversationCount')} / 消息 ${count('aiMessageCount')} / 记忆 ${count('aiMemoryCount')}`,
    status: count('aiConversationCount') > 0 ? '可审计' : '待观察',
    type: count('aiConversationCount') > 0 ? 'success' : 'info',
    action: '抽查长会话、记忆来源与助手回答质量',
    path: '/admin/ai'
  }
])

const go = (path) => {
  if (path) {
    router.push(path)
  }
}

const refresh = async () => {
  loading.value = true
  try {
    const response = await getAdminStatistics()
    stats.value = response.data || {}
  } finally {
    loading.value = false
  }
}

onMounted(refresh)
</script>

<style scoped>
.dashboard-mobile-actions {
  display: none;
}

@media (max-width: 620px) {
  .admin-table {
    display: none;
  }

  .dashboard-mobile-actions {
    display: grid;
    gap: 12px;
  }

  .dashboard-action-card {
    width: 100%;
    padding: 14px;
    border: 1px solid var(--ch-border);
    border-radius: 14px;
    color: inherit;
    text-align: left;
    background: var(--ch-surface-solid);
    cursor: pointer;
    transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
  }

  .dashboard-action-card:hover,
  .dashboard-action-card:focus-visible {
    border-color: color-mix(in srgb, var(--ch-primary) 58%, var(--ch-border));
    box-shadow: 0 14px 30px rgba(37, 99, 235, 0.14);
    outline: none;
    transform: translateY(-1px);
  }

  .dashboard-action-card > div {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
  }

  .dashboard-action-card strong {
    color: var(--ch-text);
    font-size: 15px;
    line-height: 1.35;
  }

  .dashboard-action-card p,
  .dashboard-action-card span {
    display: block;
    margin: 8px 0 0;
    color: var(--ch-muted);
    font-size: 13px;
    line-height: 1.5;
  }

  .dashboard-action-card p {
    color: var(--ch-text);
    font-weight: 700;
  }
}
</style>
