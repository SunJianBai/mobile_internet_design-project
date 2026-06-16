<template>
  <view class="order-detail-container">
    <view v-if="order" class="detail-content">
      <view class="hero-card">
        <view class="hero-main">
          <text class="activity-title">{{ getActivityTypeText(order.activityType) }}</text>
          <view :class="['status-pill', `status-${order.status || 'PENDING'}`]">
            {{ getOrderStatusText(order.status) }}
          </view>
        </view>
        <text class="hero-note">{{ order.note || '发布者暂未填写补充说明' }}</text>
        <view class="hero-meta">
          <view class="meta-chip">
            <view class="mini-icon location-icon"></view>
            <text>{{ order.location || '未设置地点' }}</text>
          </view>
          <view class="meta-chip">
            <view class="mini-icon time-icon"></view>
            <text>{{ formatDisplayTime(order.startTime) }}</text>
          </view>
        </view>
      </view>

      <view class="info-section">
        <view class="section-header">
          <text class="section-title">活动信息</text>
          <view v-if="canEditOrder" class="edit-actions">
            <button v-if="!isEditing" class="text-btn" @click="startEdit">编辑</button>
            <template v-else>
              <button class="text-btn muted" @click="cancelEdit">取消</button>
              <button class="text-btn primary" :loading="savingEdit" @click="saveEdit">保存</button>
            </template>
          </view>
        </view>

        <template v-if="!isEditing">
          <view class="info-grid">
            <view class="info-item">
              <text class="info-label">活动类型</text>
              <text class="info-value">{{ getActivityTypeText(order.activityType) }}</text>
            </view>
            <view class="info-item">
              <text class="info-label">性别要求</text>
              <text class="info-value">{{ getGenderText(order.genderRequire) }}</text>
            </view>
            <view class="info-item">
              <text class="info-label">校区</text>
              <text class="info-value">{{ getCampusText(order.campus) }}</text>
            </view>
            <view class="info-item">
              <text class="info-label">人数</text>
              <text class="info-value highlight">{{ order.currentPeople || 0 }}/{{ order.maxPeople || 0 }} 人</text>
            </view>
            <view class="info-item wide">
              <text class="info-label">活动地点</text>
              <text class="info-value">{{ order.location || '未设置' }}</text>
            </view>
            <view class="info-item wide">
              <text class="info-label">开始时间</text>
              <text class="info-value">{{ formatDisplayTime(order.startTime) }}</text>
            </view>
          </view>
        </template>

        <template v-else>
          <view class="edit-form">
            <view class="form-item">
              <text class="label">活动地点</text>
              <input v-model.trim="editForm.location" class="input" maxlength="100" placeholder="请输入活动地点" />
            </view>
            <view class="form-item">
              <text class="label">开始时间</text>
              <view class="time-row">
                <picker class="time-picker" mode="date" :value="editDateValue" :start="minDate" @change="onEditDateChange">
                  <view class="picker-view">{{ editDateValue || '选择日期' }}</view>
                </picker>
                <picker class="time-picker" mode="time" :value="editTimeValue" @change="onEditTimeChange">
                  <view class="picker-view">{{ editTimeValue || '选择时间' }}</view>
                </picker>
              </view>
            </view>
            <view class="form-item">
              <text class="label">人数上限</text>
              <view class="stepper-row">
                <button class="stepper-btn" :disabled="editForm.maxPeople <= minEditablePeople" @click="adjustEditMaxPeople(-1)">-</button>
                <input v-model.number="editForm.maxPeople" class="input number-input" type="number" />
                <button class="stepper-btn" :disabled="editForm.maxPeople >= 20" @click="adjustEditMaxPeople(1)">+</button>
              </view>
              <text class="field-tip">不能小于当前人数 {{ order.currentPeople || 0 }}，上限 20 人。</text>
            </view>
            <view class="form-item">
              <text class="label">备注</text>
              <textarea v-model="editForm.note" class="textarea" maxlength="200" placeholder="补充说明（选填）" />
              <text class="counter">{{ editForm.note.length }}/200</text>
            </view>
          </view>
        </template>
      </view>

      <view class="info-section">
        <view class="section-header">
          <text class="section-title">发布者</text>
        </view>
        <view class="user-row" @click="toProfile(publisher)">
          <image
            v-if="publisher && publisher.avatarUrl"
            :src="publisher.avatarUrl"
            class="user-avatar"
            mode="aspectFill"
          />
          <view v-else class="avatar-placeholder">{{ getInitial(publisher) }}</view>
          <view class="user-meta">
            <text class="user-name">{{ publisher ? publisher.nickname : '匿名用户' }}</text>
            <text v-if="publisherEmail" class="user-extra">邮箱：{{ publisherEmail }}</text>
            <text class="user-extra">发布于 {{ formatDisplayTime(order.createdAt) }}</text>
          </view>
        </view>
      </view>

      <view v-if="isOwner" class="info-section">
        <view class="section-header">
          <text class="section-title">申请列表</text>
          <text class="section-count">{{ visibleApplications.length }} 人</text>
        </view>
        <view v-if="visibleApplications.length > 0" class="application-list">
          <view
            v-for="app in visibleApplications"
            :key="app.apid || app.id"
            class="application-item"
          >
            <view class="application-user" @click.stop="toProfile(app.user)">
              <image
                v-if="app.user && app.user.avatarUrl"
                :src="app.user.avatarUrl"
                class="small-avatar"
                mode="aspectFill"
              />
              <view v-else class="small-avatar placeholder-avatar">{{ getInitial(app.user) }}</view>
              <view class="application-meta">
                <text class="application-name">{{ app.user ? app.user.nickname : '匿名用户' }}</text>
                <text v-if="app.status === 'APPROVED' && getApplicantEmail(getUserId(app.user))" class="application-email">
                  邮箱：{{ getApplicantEmail(getUserId(app.user)) }}
                </text>
                <text class="application-time">{{ formatDisplayTime(app.createdAt) }}</text>
              </view>
            </view>
            <view class="application-actions">
              <text :class="['apply-status', `apply-${app.status || 'PENDING_REVIEW'}`]">
                {{ getApplyStatusText(app.status) }}
              </text>
              <view v-if="canAuditApply(app)" class="audit-row">
                <button class="audit-btn approve" :disabled="isOrderFull" @click="handleAudit(app.apid || app.id, 'APPROVED')">通过</button>
                <button class="audit-btn reject" @click="handleAudit(app.apid || app.id, 'REJECTED')">拒绝</button>
              </view>
            </view>
          </view>
        </view>
        <view v-else class="empty-state">
          <text class="empty-text">暂时还没有申请</text>
        </view>
      </view>

      <view v-else-if="myApplication" class="info-section">
        <view class="section-header">
          <text class="section-title">我的申请</text>
        </view>
        <view class="my-apply-card">
          <text class="apply-label">当前状态</text>
          <text :class="['apply-status', `apply-${myApplication.status || 'PENDING_REVIEW'}`]">
            {{ getApplyStatusText(myApplication.status) }}
          </text>
        </view>
      </view>

      <view class="action-bar">
        <template v-if="isOwner">
          <button class="bottom-btn" @click="toMessages">查看消息</button>
          <button v-if="canCancelOrder" class="bottom-btn danger" @click="handleCancelOrder">取消活动</button>
          <button v-if="canCompleteOrder" class="bottom-btn primary" @click="handleComplete">完成活动</button>
        </template>
        <template v-else>
          <button v-if="canCancelApply" class="bottom-btn danger" @click="handleCancelApply">撤销申请</button>
          <button
            v-else
            class="bottom-btn primary"
            :disabled="isLogin && !canApply"
            @click="handleApply"
          >
            {{ actionText }}
          </button>
        </template>
      </view>
    </view>

    <view v-else-if="loading" class="loading-state">
      <text class="loading-text">加载中...</text>
    </view>
  </view>
</template>

<script setup>
import { computed, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { useStore } from 'vuex'
import { orderApi, userApi } from '@/api/index.js'
import { formatTime, showLoading, hideLoading, showSuccess, showError, resolveFileUrl } from '@/utils/util.js'
import { ACTIVITY_TYPE_MAP, CAMPUS_MAP, APPLY_STATUS_MAP, ORDER_STATUS_MAP, GENDER_REQUIRE_MAP } from '@/utils/constants.js'
import { goUserProfile } from '@/utils/user-navigation.js'

const store = useStore()

const orderDetail = ref(null)
const applications = ref([])
const loading = ref(false)
const orderId = ref(null)

const isEditing = ref(false)
const savingEdit = ref(false)
const editDateValue = ref('')
const editTimeValue = ref('')
const editForm = ref({
  location: '',
  startTime: '',
  maxPeople: 1,
  note: ''
})

const publisherEmail = ref('')
const applicantEmails = ref({})

const order = computed(() => orderDetail.value && orderDetail.value.order ? orderDetail.value.order : null)
const publisher = computed(() => order.value ? order.value.user : null)
const isLogin = computed(() => store.getters['user/isLogin'])
const currentUserId = computed(() => store.getters['user/userId'])
const isAdmin = computed(() => store.getters['user/isAdmin'])

const getMinDate = () => {
  const now = new Date()
  const year = now.getFullYear()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

const minDate = ref(getMinDate())

const visibleApplications = computed(() => {
  return applications.value.filter(app => app.status !== 'CANCELLED_APPLY')
})

const isOwner = computed(() => {
  if (!order.value || !isLogin.value) return false
  if (isAdmin.value) return true
  const publisherId = getUserId(order.value.user)
  return String(publisherId || '') === String(currentUserId.value || '')
})

const myApplication = computed(() => {
  if (!isLogin.value) return null
  return applications.value.find(app => String(getUserId(app.user) || '') === String(currentUserId.value || '')) || null
})

const hasActiveApplication = computed(() => {
  return Boolean(myApplication.value && myApplication.value.status !== 'CANCELLED_APPLY')
})

const isOrderFull = computed(() => {
  if (!order.value) return false
  return Number(order.value.currentPeople || 0) >= Number(order.value.maxPeople || 0)
})

const minEditablePeople = computed(() => {
  return Math.max(1, Number(order.value?.currentPeople || 0))
})

const canEditOrder = computed(() => {
  return Boolean(isOwner.value && order.value && order.value.status === 'PENDING')
})

const canCancelOrder = computed(() => {
  return Boolean(isOwner.value && order.value && ['PENDING', 'IN_PROGRESS'].includes(order.value.status))
})

const canCompleteOrder = computed(() => {
  return Boolean(isOwner.value && order.value && order.value.status === 'IN_PROGRESS')
})

const canCancelApply = computed(() => {
  return Boolean(myApplication.value && myApplication.value.status === 'PENDING_REVIEW' && order.value?.status === 'PENDING')
})

const canApply = computed(() => {
  if (!order.value || isOwner.value) return false
  if (hasActiveApplication.value) return false
  if (isOrderFull.value) return false
  return order.value.status === 'PENDING'
})

const actionText = computed(() => {
  if (!isLogin.value) return '登录后申请'
  if (isOwner.value) return ''
  if (hasActiveApplication.value) return '已申请'
  if (!order.value) return '申请加入'
  if (order.value.status === 'EXPIRED') return '已过期'
  if (order.value.status === 'IN_PROGRESS') return '进行中'
  if (order.value.status === 'COMPLETED') return '已完成'
  if (order.value.status === 'CANCELLED') return '已取消'
  if (isOrderFull.value) return '人数已满'
  return '申请加入'
})

const getUserId = (user) => {
  return user ? (user.id || user.uid) : null
}

const getInitial = (user) => {
  const name = user && user.nickname ? user.nickname : '用户'
  return String(name).slice(0, 1)
}

const getActivityTypeText = (type) => ACTIVITY_TYPE_MAP[type] || '其他'
const getCampusText = (campus) => CAMPUS_MAP[campus] || '其他校区'
const getGenderText = (gender) => GENDER_REQUIRE_MAP[gender] || '不限'
const getApplyStatusText = (status) => APPLY_STATUS_MAP[status] || '待审核'
const getOrderStatusText = (status) => ORDER_STATUS_MAP[status] || '待匹配'

const formatDisplayTime = (value) => {
  if (!value) return '未设置'
  return formatTime(value, 'YYYY-MM-DD HH:mm')
}

const getApplicantEmail = (userId) => {
  if (!userId) return ''
  return applicantEmails.value[userId] || ''
}

const loadOrderDetail = async () => {
  if (!orderId.value) {
    showError('缺少活动 ID')
    return
  }

  loading.value = true
  showLoading('加载中...')

  try {
    const detail = await orderApi.getOrderDetail(orderId.value)
    if (!detail || !detail.order) {
      showError('活动数据格式错误')
      return
    }

    orderDetail.value = {
      ...detail,
      order: {
        ...detail.order,
        user: normalizeUser(detail.order.user)
      }
    }

    await loadApplications()
    await loadRelatedUserEmails()
  } catch (error) {
    console.error('加载活动详情失败:', error)
    showError(error.message || '加载失败')
  } finally {
    loading.value = false
    hideLoading()
  }
}

const normalizeUser = (user) => {
  if (!user) return user
  return {
    ...user,
    avatarUrl: resolveFileUrl(user.avatarUrl)
  }
}

const loadApplications = async () => {
  try {
    const apps = await orderApi.getApplications(orderId.value)
    const normalizedApps = (apps || []).map(app => ({
      ...app,
      user: normalizeUser(app.user)
    }))

    if (!isOwner.value && isLogin.value) {
      applications.value = normalizedApps.filter(app => String(getUserId(app.user) || '') === String(currentUserId.value || ''))
      return
    }

    applications.value = normalizedApps.sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
  } catch (error) {
    console.error('加载申请列表失败:', error)
    applications.value = []
  }
}

const fetchUserEmailById = async (userId) => {
  if (!userId) return ''
  if (applicantEmails.value[userId]) return applicantEmails.value[userId]

  try {
    const user = await userApi.getUserInfo(userId)
    const email = user && user.email ? user.email : ''
    if (email) {
      applicantEmails.value = {
        ...applicantEmails.value,
        [userId]: email
      }
    }
    return email
  } catch (error) {
    console.error('加载用户邮箱失败:', userId, error)
    return ''
  }
}

const loadRelatedUserEmails = async () => {
  const publisherId = getUserId(publisher.value)
  if (publisherId) {
    publisherEmail.value = await fetchUserEmailById(publisherId)
  }

  if (!isOwner.value) return
  const approvedIds = Array.from(new Set(
    visibleApplications.value
      .filter(app => app.status === 'APPROVED')
      .map(app => getUserId(app.user))
      .filter(Boolean)
  ))
  await Promise.all(approvedIds.map(id => fetchUserEmailById(id)))
}

const canAuditApply = (app) => {
  if (!isOwner.value || !order.value) return false
  return order.value.status === 'PENDING' && app.status === 'PENDING_REVIEW'
}

const initEditForm = () => {
  if (!order.value) return
  const start = buildStartTimeString(order.value.startTime)
  editForm.value = {
    location: order.value.location || '',
    startTime: start,
    maxPeople: Number(order.value.maxPeople || minEditablePeople.value),
    note: order.value.note || ''
  }
  editDateValue.value = start.slice(0, 10)
  editTimeValue.value = start.slice(11, 16)
}

const buildStartTimeString = (value) => {
  if (!value) return ''
  if (typeof value === 'string') {
    return value.replace('T', ' ').slice(0, 19)
  }
  return formatTime(value, 'YYYY-MM-DD HH:mm:ss')
}

const startEdit = () => {
  if (!canEditOrder.value) return
  initEditForm()
  isEditing.value = true
}

const cancelEdit = () => {
  isEditing.value = false
}

const onEditDateChange = (e) => {
  editDateValue.value = e.detail.value
  updateEditStartTime()
}

const onEditTimeChange = (e) => {
  editTimeValue.value = e.detail.value
  updateEditStartTime()
}

const updateEditStartTime = () => {
  if (editDateValue.value && editTimeValue.value) {
    editForm.value.startTime = `${editDateValue.value} ${editTimeValue.value}:00`
  }
}

const adjustEditMaxPeople = (delta) => {
  const next = Number(editForm.value.maxPeople || 0) + delta
  editForm.value.maxPeople = Math.max(minEditablePeople.value, Math.min(20, next))
}

const validateEditForm = () => {
  if (!editForm.value.location.trim()) return '请输入活动地点'
  if (!editForm.value.startTime) return '请选择开始时间'

  const startTime = new Date(editForm.value.startTime.replace(' ', 'T'))
  if (Number.isNaN(startTime.getTime())) return '开始时间格式不正确'
  if (startTime.getTime() <= Date.now()) return '开始时间必须晚于当前时间'

  const maxPeople = Number(editForm.value.maxPeople)
  if (!Number.isInteger(maxPeople) || maxPeople < minEditablePeople.value || maxPeople > 20) {
    return `人数上限应在 ${minEditablePeople.value}-20 之间`
  }

  if (editForm.value.note.length > 200) return '备注不能超过 200 个字'
  return ''
}

const saveEdit = () => {
  if (!canEditOrder.value || !order.value) return

  const error = validateEditForm()
  if (error) {
    showError(error)
    return
  }

  uni.showModal({
    title: '保存修改',
    content: '确定要更新这次活动的信息吗？',
    success: async (res) => {
      if (!res.confirm) return
      savingEdit.value = true
      try {
        const payload = {
          activityType: order.value.activityType,
          genderRequire: order.value.genderRequire || 'ANY',
          campus: order.value.campus,
          location: editForm.value.location.trim(),
          startTime: editForm.value.startTime,
          note: editForm.value.note || '',
          maxPeople: Number(editForm.value.maxPeople)
        }
        await orderApi.updateOrder(orderId.value, payload)
        showSuccess('活动信息已更新')
        isEditing.value = false
        await loadOrderDetail()
      } catch (error) {
        showError(error.message || '保存失败')
      } finally {
        savingEdit.value = false
      }
    }
  })
}

const handleApply = () => {
  if (!isLogin.value) {
    uni.navigateTo({ url: '/pages/auth/login' })
    return
  }
  if (!canApply.value) return

  uni.showModal({
    title: '申请加入',
    content: '确定要申请加入这个活动吗？',
    success: async (res) => {
      if (!res.confirm) return
      try {
        await orderApi.applyOrder(orderId.value, '')
        showSuccess('申请成功')
        await loadOrderDetail()
      } catch (error) {
        showError(error.message || '申请失败')
      }
    }
  })
}

const handleCancelApply = () => {
  if (!canCancelApply.value) return

  uni.showModal({
    title: '撤销申请',
    content: '确定要撤销这次申请吗？',
    success: async (res) => {
      if (!res.confirm) return
      try {
        await orderApi.cancelApply(orderId.value)
        showSuccess('已撤销申请')
        await loadOrderDetail()
      } catch (error) {
        showError(error.message || '撤销失败')
      }
    }
  })
}

const handleAudit = (applyId, status) => {
  if (!applyId) return
  const actionText = status === 'APPROVED' ? '通过' : '拒绝'

  uni.showModal({
    title: `${actionText}申请`,
    content: `确定要${actionText}这位同学的申请吗？`,
    success: async (res) => {
      if (!res.confirm) return
      try {
        await orderApi.auditApply(applyId, status)
        showSuccess(`已${actionText}`)
        await loadOrderDetail()
      } catch (error) {
        showError(error.message || '操作失败')
      }
    }
  })
}

const handleCancelOrder = () => {
  if (!canCancelOrder.value) return

  uni.showModal({
    title: '取消活动',
    content: '确定要取消这个活动吗？此操作不可撤销。',
    success: async (res) => {
      if (!res.confirm) return
      try {
        showLoading('取消中...')
        await orderApi.deleteOrder(orderId.value)
        hideLoading()
        showSuccess('活动已取消')
        setTimeout(() => {
          uni.navigateBack()
        }, 800)
      } catch (error) {
        hideLoading()
        showError(error.message || '取消失败')
      }
    }
  })
}

const handleComplete = () => {
  if (!canCompleteOrder.value) return

  uni.showModal({
    title: '完成活动',
    content: '确认这次活动已经完成了吗？',
    success: async (res) => {
      if (!res.confirm) return
      try {
        await orderApi.completeOrder(orderId.value)
        showSuccess('活动已完成')
        await loadOrderDetail()
      } catch (error) {
        showError(error.message || '操作失败')
      }
    }
  })
}

const toMessages = () => {
  uni.navigateTo({
    url: `/pages/order/messages?orderId=${orderId.value}`
  })
}

const toProfile = (user) => {
  goUserProfile(user)
}

onLoad((options = {}) => {
  if (options.id) {
    orderId.value = options.id
    loadOrderDetail()
  } else {
    showError('缺少活动 ID')
  }
})
</script>

<style scoped>
.order-detail-container {
  min-height: 100vh;
  background:
    radial-gradient(circle at 16% 0%, rgba(78, 161, 255, 0.16), transparent 34%),
    radial-gradient(circle at 92% 6%, rgba(24, 196, 214, 0.10), transparent 30%),
    linear-gradient(180deg, #f7fbff 0%, #eef4fb 50%, #f8fbff 100%);
  padding-bottom: 148rpx;
}

.detail-content {
  padding: 28rpx;
}

.hero-card,
.info-section {
  background:
    linear-gradient(145deg, rgba(255, 255, 255, 0.94), rgba(244, 250, 255, 0.74));
  border: 1rpx solid rgba(255, 255, 255, 0.74);
  border-radius: 32rpx;
  box-shadow:
    0 18rpx 38rpx rgba(22, 47, 84, 0.10),
    inset 0 1rpx 0 rgba(255, 255, 255, 0.92);
  -webkit-backdrop-filter: blur(24rpx) saturate(1.24);
  backdrop-filter: blur(24rpx) saturate(1.24);
}

.hero-card {
  padding: 30rpx;
  margin-bottom: 22rpx;
}

.hero-main {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20rpx;
}

.activity-title {
  font-size: 42rpx;
  font-weight: 800;
  color: #172033;
}

.status-pill {
  padding: 8rpx 18rpx;
  border-radius: 999rpx;
  font-size: 23rpx;
  font-weight: 700;
  background: rgba(238, 246, 255, 0.88);
  color: #475467;
}

.status-PENDING {
  background: #eff6ff;
  color: #1d4ed8;
}

.status-IN_PROGRESS {
  background: #ecfdf3;
  color: #047857;
}

.status-COMPLETED {
  background: #f0fdf4;
  color: #15803d;
}

.status-CANCELLED,
.status-EXPIRED {
  background: #fef2f2;
  color: #b42318;
}

.hero-note {
  display: block;
  margin-top: 18rpx;
  color: #667085;
  font-size: 27rpx;
  line-height: 1.6;
}

.hero-meta {
  margin-top: 22rpx;
  display: flex;
  flex-direction: column;
  gap: 12rpx;
}

.meta-chip {
  display: flex;
  align-items: center;
  gap: 12rpx;
  color: #475467;
  font-size: 25rpx;
}

.mini-icon {
  position: relative;
  width: 30rpx;
  height: 30rpx;
  flex: 0 0 30rpx;
}

.location-icon {
  border: 3rpx solid #1d4ed8;
  border-radius: 50% 50% 50% 0;
  transform: rotate(-45deg);
  box-sizing: border-box;
}

.location-icon::after {
  content: "";
  position: absolute;
  width: 8rpx;
  height: 8rpx;
  left: 8rpx;
  top: 8rpx;
  border-radius: 50%;
  background: #1d4ed8;
}

.time-icon {
  border: 3rpx solid #1d4ed8;
  border-radius: 50%;
  box-sizing: border-box;
}

.time-icon::before {
  content: "";
  position: absolute;
  width: 3rpx;
  height: 9rpx;
  left: 12rpx;
  top: 6rpx;
  background: #1d4ed8;
}

.time-icon::after {
  content: "";
  position: absolute;
  width: 9rpx;
  height: 3rpx;
  left: 12rpx;
  top: 14rpx;
  background: #1d4ed8;
}

.info-section {
  padding: 28rpx;
  margin-bottom: 22rpx;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24rpx;
}

.section-title {
  font-size: 31rpx;
  font-weight: 800;
  color: #172033;
}

.section-count {
  font-size: 24rpx;
  color: #667085;
}

.edit-actions {
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.text-btn {
  height: 54rpx;
  line-height: 54rpx;
  padding: 0 20rpx;
  border: none;
  border-radius: 18rpx;
  background: rgba(239, 246, 255, 0.88);
  color: #1f447a;
  font-size: 24rpx;
}

.text-btn.primary {
  background: linear-gradient(135deg, #2f7ed8, #1f447a);
  color: #ffffff;
}

.text-btn.muted {
  background: #eef3f8;
  color: #667085;
}

.info-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 22rpx;
}

.info-item {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}

.info-item.wide {
  grid-column: 1 / span 2;
}

.info-label,
.label {
  color: #8a94a6;
  font-size: 23rpx;
}

.info-value {
  color: #1f2937;
  font-size: 28rpx;
  font-weight: 650;
  line-height: 1.45;
  word-break: break-word;
}

.info-value.highlight {
  color: #1d4ed8;
}

.edit-form {
  display: flex;
  flex-direction: column;
  gap: 26rpx;
}

.form-item {
  display: flex;
  flex-direction: column;
  gap: 12rpx;
}

.input,
.textarea,
.picker-view {
  width: 100%;
  box-sizing: border-box;
  border: 1rpx solid rgba(217, 229, 243, 0.92);
  border-radius: 22rpx;
  background: rgba(255, 255, 255, 0.68);
  color: #1f2937;
  font-size: 28rpx;
}

.input,
.picker-view {
  height: 84rpx;
  line-height: 84rpx;
  padding: 0 22rpx;
}

.textarea {
  min-height: 160rpx;
  padding: 20rpx 22rpx;
  line-height: 1.6;
}

.time-row,
.stepper-row {
  display: flex;
  align-items: center;
  gap: 16rpx;
}

.time-picker {
  flex: 1;
}

.stepper-btn {
  width: 82rpx;
  height: 82rpx;
  line-height: 82rpx;
  padding: 0;
  border-radius: 22rpx;
  border: 1rpx solid rgba(217, 229, 243, 0.92);
  background: rgba(255, 255, 255, 0.74);
  color: #1f447a;
  font-size: 34rpx;
}

.stepper-btn[disabled] {
  color: #c2cad6;
  background: #f3f5f8;
}

.number-input {
  flex: 1;
  text-align: center;
}

.field-tip,
.counter {
  display: block;
  color: #8a94a6;
  font-size: 23rpx;
}

.counter {
  text-align: right;
}

.user-row,
.application-user {
  display: flex;
  align-items: center;
  gap: 16rpx;
}

.user-avatar,
.avatar-placeholder {
  width: 86rpx;
  height: 86rpx;
  border-radius: 50%;
  flex: 0 0 86rpx;
}

.avatar-placeholder,
.placeholder-avatar {
  display: flex;
  align-items: center;
  justify-content: center;
  background:
    radial-gradient(circle at 30% 18%, rgba(255, 255, 255, 0.92), transparent 42%),
    linear-gradient(145deg, rgba(237, 247, 255, 0.96), rgba(210, 231, 255, 0.78));
  color: #1f447a;
  font-size: 30rpx;
  font-weight: 800;
}

.user-meta,
.application-meta {
  min-width: 0;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6rpx;
}

.user-name,
.application-name {
  color: #1f2937;
  font-size: 28rpx;
  font-weight: 750;
}

.user-extra,
.application-email,
.application-time {
  color: #8a94a6;
  font-size: 23rpx;
  line-height: 1.35;
}

.application-list {
  display: flex;
  flex-direction: column;
  gap: 18rpx;
}

.application-item {
  padding: 20rpx;
  display: flex;
  justify-content: space-between;
  gap: 16rpx;
  background: rgba(255, 255, 255, 0.58);
  border: 1rpx solid rgba(229, 237, 247, 0.84);
  border-radius: 24rpx;
}

.small-avatar {
  width: 64rpx;
  height: 64rpx;
  border-radius: 50%;
  flex: 0 0 64rpx;
  font-size: 24rpx;
}

.application-actions {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 12rpx;
}

.apply-status {
  padding: 6rpx 14rpx;
  border-radius: 999rpx;
  background: #eef3f8;
  color: #475467;
  font-size: 22rpx;
  font-weight: 700;
  white-space: nowrap;
}

.apply-PENDING_REVIEW {
  background: #fff7ed;
  color: #c2410c;
}

.apply-APPROVED {
  background: #ecfdf3;
  color: #047857;
}

.apply-REJECTED,
.apply-CANCELLED_APPLY {
  background: #fef2f2;
  color: #b42318;
}

.audit-row {
  display: flex;
  gap: 10rpx;
}

.audit-btn {
  height: 48rpx;
  line-height: 48rpx;
  padding: 0 16rpx;
  border: none;
  border-radius: 16rpx;
  color: #ffffff;
  font-size: 22rpx;
}

.audit-btn.approve {
  background: #12b76a;
}

.audit-btn.reject {
  background: #f04438;
}

.audit-btn[disabled] {
  background: #c2cad6;
}

.my-apply-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 22rpx;
  border-radius: 24rpx;
  background: rgba(255, 255, 255, 0.58);
  border: 1rpx solid rgba(229, 237, 247, 0.84);
}

.apply-label {
  color: #667085;
  font-size: 26rpx;
}

.empty-state,
.loading-state {
  text-align: center;
  padding: 110rpx 0;
}

.empty-text,
.loading-text {
  color: #98a2b3;
  font-size: 27rpx;
}

.action-bar {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 20;
  padding: 18rpx 28rpx calc(18rpx + env(safe-area-inset-bottom));
  display: flex;
  gap: 16rpx;
  background: rgba(248, 251, 255, 0.86);
  border-top: 1rpx solid rgba(255, 255, 255, 0.74);
  box-shadow: 0 -12rpx 30rpx rgba(17, 24, 39, 0.08);
  -webkit-backdrop-filter: blur(24rpx) saturate(1.25);
  backdrop-filter: blur(24rpx) saturate(1.25);
}

.bottom-btn {
  flex: 1;
  height: 84rpx;
  line-height: 84rpx;
  padding: 0;
  border: none;
  border-radius: 26rpx;
  background: rgba(238, 246, 255, 0.86);
  color: #475467;
  font-size: 27rpx;
  font-weight: 700;
}

.bottom-btn.primary {
  background: linear-gradient(135deg, #2f7ed8, #1f447a);
  color: #ffffff;
  box-shadow: 0 14rpx 28rpx rgba(31, 68, 122, 0.20);
}

.bottom-btn.danger {
  background: #fef2f2;
  color: #b42318;
}

.bottom-btn[disabled] {
  background: #eef3f8;
  color: #98a2b3;
}
</style>
