<template>
  <view class="content-detail-container">
    <view v-if="contentDetail" class="detail-content">
      <view class="user-section" @click="toProfile(contentDetail.user)">
        <image
          v-if="contentDetail.user && contentDetail.user.avatarUrl"
          :src="contentDetail.user.avatarUrl"
          class="user-avatar"
          mode="aspectFill"
        />
        <view v-else class="avatar-placeholder">{{ getInitial(contentDetail.user) }}</view>
        <view class="user-info">
          <text class="user-nickname">{{ contentDetail.user ? contentDetail.user.nickname : '匿名用户' }}</text>
          <text class="content-time">{{ formatRelativeTime(contentDetail.createdAt) }}</text>
        </view>
        <button v-if="canDeleteContent" class="delete-content-btn" @click.stop="handleDeleteContent">删除</button>
      </view>

      <text class="content-text">{{ contentDetail.content }}</text>

      <view v-if="linkedOrder" class="linked-order-card" @click="goOrderDetail(linkedOrder.id)">
        <view class="linked-order-head">
          <view class="linked-order-icon">
            <view class="order-icon-line"></view>
            <view class="order-icon-dot-row">
              <view></view><view></view><view></view>
            </view>
          </view>
          <view class="linked-order-title-box">
            <text class="linked-order-label">关联活动</text>
            <text class="linked-order-title">{{ getActivityTypeText(linkedOrder.activityType) }}</text>
          </view>
          <text class="linked-order-status" :class="`order-status-${linkedOrder.status || 'PENDING'}`">
            {{ getOrderStatusText(linkedOrder.status) }}
          </text>
        </view>
        <view class="linked-order-meta">
          <view class="linked-order-meta-item">
            <text class="meta-label">地点</text>
            <text class="meta-value">{{ linkedOrder.location || '未设置地点' }}</text>
          </view>
          <view class="linked-order-meta-item">
            <text class="meta-label">时间</text>
            <text class="meta-value">{{ formatOrderTime(linkedOrder.startTime) }}</text>
          </view>
        </view>
        <view class="linked-order-foot">
          <text>查看活动详情</text>
          <view class="linked-order-arrow"></view>
        </view>
      </view>

      <view v-if="contentDetail.media && contentDetail.media.length > 0" class="media-section">
        <image
          v-for="(media, index) in contentDetail.media"
          :key="index"
          :src="media.url"
          class="media-image"
          mode="widthFix"
          @click="previewImage(media.url, contentDetail.media)"
        />
      </view>

      <view class="action-bar">
        <view class="action-item" @click="handleLike">
          <view :class="['action-icon', 'like-icon', contentDetail.liked ? 'active' : '']"></view>
          <text>{{ contentDetail.likeCount || 0 }}</text>
        </view>
        <view class="action-item" @click="startComment">
          <view class="action-icon comment-icon"></view>
          <text>{{ contentDetail.commentCount || 0 }}</text>
        </view>
      </view>

      <view v-if="showCommentInput" class="comment-input-section">
        <view v-if="replyTarget" class="replying-bar">
          <text class="replying-text">回复 {{ replyTarget.user ? replyTarget.user.nickname : '用户' }}</text>
          <text class="replying-cancel" @click="resetCommentInput">取消回复</text>
        </view>
        <textarea
          v-model="commentText"
          class="comment-input"
          :placeholder="commentPlaceholder"
          maxlength="500"
        />
        <view class="comment-actions">
          <button class="cancel-btn" @click="resetCommentInput">取消</button>
          <button class="submit-btn" @click="handleComment">{{ replyTarget ? '回复' : '发布' }}</button>
        </view>
      </view>

      <view class="comments-section">
        <view class="section-title-row">
          <text class="section-title">评论</text>
          <text class="section-count">{{ flattenedComments.length }}</text>
        </view>
        <view v-if="flattenedComments.length > 0" class="comments-list">
          <view
            v-for="comment in flattenedComments"
            :key="comment.id"
            class="comment-item"
            :class="{ child: comment.level > 0 }"
            :style="getCommentIndent(comment)"
          >
            <image
              v-if="comment.user && comment.user.avatarUrl"
              :src="comment.user.avatarUrl"
              class="comment-avatar"
              mode="aspectFill"
              @click.stop="toProfile(comment.user)"
            />
            <view v-else class="comment-avatar placeholder-avatar" @click.stop="toProfile(comment.user)">{{ getInitial(comment.user) }}</view>
            <view class="comment-content">
              <view class="comment-title-row">
                <view class="comment-title-main">
                  <text class="comment-nickname" @click.stop="toProfile(comment.user)">{{ comment.user ? comment.user.nickname : '匿名用户' }}</text>
                  <text v-if="comment.parentUser" class="comment-reply-to">回复 {{ comment.parentUser.nickname || '用户' }}</text>
                </view>
                <text v-if="canDeleteComment(comment)" class="comment-delete" @click.stop="handleDeleteComment(comment)">删除</text>
              </view>
              <text class="comment-text">{{ comment.content }}</text>
              <view class="comment-bottom-row">
                <text class="comment-time">{{ formatRelativeTime(comment.createdAt) }}</text>
                <text class="comment-reply" @click.stop="startReply(comment)">回复</text>
              </view>
            </view>
          </view>
        </view>
        <view v-else class="empty-state">
          <text class="empty-text">暂时还没有评论</text>
        </view>
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
import { contentApi } from '@/api/index.js'
import { ACTIVITY_TYPE_MAP, ORDER_STATUS_MAP } from '@/utils/constants.js'
import { formatRelativeTime, formatTime, showLoading, hideLoading, showSuccess, showError, normalizeMediaList, resolveFileUrl } from '@/utils/util.js'
import { goUserProfile } from '@/utils/user-navigation.js'

const store = useStore()

const contentDetail = ref(null)
const comments = ref([])
const loading = ref(false)
const showCommentInput = ref(false)
const commentText = ref('')
const contentId = ref(null)
const replyTarget = ref(null)

const currentUserId = computed(() => store.getters['user/userId'])
const isLogin = computed(() => store.getters['user/isLogin'])
const isAdmin = computed(() => store.getters['user/isAdmin'])

const linkedOrder = computed(() => {
  const order = contentDetail.value && contentDetail.value.order
  if (!order) return null
  const id = order.id || order.oid || order.orderId
  if (!id) return null
  return { ...order, id }
})

const flattenedComments = computed(() => {
  const result = []
  const walk = (nodes = []) => {
    nodes.forEach((node) => {
      result.push(node)
      if (node.replies && node.replies.length) {
        walk(node.replies)
      }
    })
  }
  walk(comments.value)
  return result
})

const commentPlaceholder = computed(() => {
  if (!replyTarget.value) return '写评论...'
  const name = replyTarget.value.user ? replyTarget.value.user.nickname : '用户'
  return `回复 ${name}...`
})

const getUserId = (user) => {
  return user ? (user.uid || user.id) : null
}

const getInitial = (user) => {
  const name = user && user.nickname ? user.nickname : '用户'
  return String(name).slice(0, 1)
}

const canDeleteContent = computed(() => {
  if (!contentDetail.value || !isLogin.value) return false
  const ownerId = getUserId(contentDetail.value.user)
  return isAdmin.value || String(ownerId || '') === String(currentUserId.value || '')
})

function canDeleteComment(comment) {
  if (!comment || !isLogin.value) return false
  const ownerId = getUserId(comment.user)
  return isAdmin.value || String(ownerId || '') === String(currentUserId.value || '')
}

const normalizeUser = (user) => {
  if (!user) return user
  return {
    ...user,
    avatarUrl: resolveFileUrl(user.avatarUrl)
  }
}

const getCommentId = (comment) => comment ? (comment.id || comment.pid) : null

const normalizeCommentTree = (list = [], level = 0, parentUser = null) => {
  return list.map((comment) => {
    const user = normalizeUser(comment.user)
    const node = {
      ...comment,
      id: getCommentId(comment),
      user,
      level,
      parentUser,
      replies: []
    }
    node.replies = normalizeCommentTree(comment.replies || [], level + 1, user)
    return node
  })
}

const getCommentIndent = (comment) => {
  const level = Math.min(comment.level || 0, 3)
  if (!level) return {}
  return {
    marginLeft: `${level * 34}rpx`
  }
}

const getActivityTypeText = (type) => ACTIVITY_TYPE_MAP[type] || '活动'

const getOrderStatusText = (status) => ORDER_STATUS_MAP[status] || '待匹配'

const formatOrderTime = (time) => {
  if (!time) return '未设置时间'
  return formatTime(time, 'MM-DD HH:mm')
}

const goOrderDetail = (orderId) => {
  if (!orderId) return
  uni.navigateTo({ url: `/pages/order/detail?id=${orderId}` })
}

const toProfile = (user) => {
  goUserProfile(user)
}

const loadContentDetail = async () => {
  if (!contentId.value) {
    showError('缺少动态 ID')
    return
  }

  loading.value = true
  showLoading('加载中...')

  try {
    const detail = await contentApi.getContentDetail(contentId.value)
    contentDetail.value = {
      ...detail,
      user: normalizeUser(detail.user),
      media: normalizeMediaList(detail)
    }

    const result = await contentApi.getComments(contentId.value, 1, 50)
    comments.value = normalizeCommentTree(result.list || [])
  } catch (error) {
    showError(error.message || '加载失败')
  } finally {
    loading.value = false
    hideLoading()
  }
}

const handleLike = async () => {
  if (!isLogin.value) {
    uni.navigateTo({ url: '/pages/auth/login' })
    return
  }

  try {
    const result = await contentApi.likeContent(contentId.value)
    contentDetail.value.liked = result.liked
    contentDetail.value.likeCount = result.count || result.likeCount || contentDetail.value.likeCount
  } catch (error) {
    showError(error.message || '操作失败')
  }
}

const startComment = () => {
  replyTarget.value = null
  commentText.value = ''
  showCommentInput.value = true
}

const startReply = (comment) => {
  if (!isLogin.value) {
    uni.navigateTo({ url: '/pages/auth/login' })
    return
  }
  replyTarget.value = comment
  const name = comment.user ? comment.user.nickname : '用户'
  commentText.value = `@${name} `
  showCommentInput.value = true
}

const resetCommentInput = () => {
  commentText.value = ''
  replyTarget.value = null
  showCommentInput.value = false
}

const handleComment = async () => {
  if (!commentText.value.trim()) {
    showError('请输入评论内容')
    return
  }

  if (!isLogin.value) {
    uni.navigateTo({ url: '/pages/auth/login' })
    return
  }

  try {
    const payload = {
      content: commentText.value.trim()
    }
    if (replyTarget.value) {
      payload.parentId = getCommentId(replyTarget.value)
    }
    await contentApi.createComment(contentId.value, payload)
    showSuccess(replyTarget.value ? '回复成功' : '评论成功')
    resetCommentInput()
    await loadContentDetail()
  } catch (error) {
    showError(error.message || '评论失败')
  }
}

const handleDeleteContent = () => {
  uni.showModal({
    title: '删除动态',
    content: '确定删除这条动态吗？此操作不可撤销。',
    success: async (res) => {
      if (!res.confirm) return

      try {
        showLoading('删除中...')
        await contentApi.deleteContent(contentId.value)
        hideLoading()
        showSuccess('已删除')
        setTimeout(() => {
          uni.navigateBack()
        }, 800)
      } catch (error) {
        hideLoading()
        showError(error.message || '删除失败')
      }
    }
  })
}

const handleDeleteComment = (comment) => {
  const commentId = comment.pid || comment.id
  if (!commentId) return

  uni.showModal({
    title: '删除评论',
    content: '确定删除这条评论吗？',
    success: async (res) => {
      if (!res.confirm) return

      try {
        await contentApi.deleteComment(commentId)
        await loadContentDetail()
        showSuccess('已删除')
      } catch (error) {
        showError(error.message || '删除失败')
      }
    }
  })
}

const previewImage = (current, mediaList) => {
  const urls = mediaList.map(item => item.url)
  uni.previewImage({ current, urls })
}

onLoad((options = {}) => {
  if (options.id) {
    contentId.value = options.id
    loadContentDetail()
  } else {
    showError('缺少动态 ID')
  }
})
</script>

<style scoped>
.content-detail-container {
  min-height: 100vh;
  background:
    radial-gradient(circle at 16% 0%, rgba(78, 161, 255, 0.16), transparent 34%),
    radial-gradient(circle at 92% 6%, rgba(24, 196, 214, 0.10), transparent 30%),
    linear-gradient(180deg, #f7fbff 0%, #eef4fb 50%, #f8fbff 100%);
  padding: 28rpx;
  box-sizing: border-box;
}

.detail-content {
  background:
    linear-gradient(145deg, rgba(255, 255, 255, 0.94), rgba(244, 250, 255, 0.74));
  border: 1rpx solid rgba(255, 255, 255, 0.74);
  border-radius: 32rpx;
  padding: 30rpx;
  box-shadow:
    0 18rpx 38rpx rgba(22, 47, 84, 0.10),
    inset 0 1rpx 0 rgba(255, 255, 255, 0.92);
  -webkit-backdrop-filter: blur(24rpx) saturate(1.24);
  backdrop-filter: blur(24rpx) saturate(1.24);
}

.user-section {
  display: flex;
  align-items: center;
  gap: 16rpx;
  margin-bottom: 26rpx;
}

.user-avatar,
.avatar-placeholder {
  width: 84rpx;
  height: 84rpx;
  border-radius: 50%;
  flex: 0 0 84rpx;
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
  font-size: 28rpx;
  font-weight: 800;
}

.user-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}

.user-nickname {
  color: #1f2937;
  font-size: 29rpx;
  font-weight: 750;
}

.content-time {
  color: #8a94a6;
  font-size: 23rpx;
}

.delete-content-btn {
  width: 96rpx;
  height: 56rpx;
  line-height: 56rpx;
  padding: 0;
  border: none;
  border-radius: 8rpx;
  background: #fef2f2;
  color: #b42318;
  font-size: 24rpx;
}

.content-text {
  display: block;
  color: #263244;
  font-size: 30rpx;
  line-height: 1.75;
  margin-bottom: 24rpx;
  white-space: pre-wrap;
  word-break: break-word;
}

.linked-order-card {
  margin: 0 0 26rpx;
  padding: 24rpx;
  border-radius: 28rpx;
  background:
    radial-gradient(circle at 18% 0%, rgba(255, 255, 255, 0.92), transparent 34%),
    linear-gradient(145deg, rgba(244, 250, 255, 0.96), rgba(255, 255, 255, 0.76));
  border: 1rpx solid rgba(255, 255, 255, 0.82);
  box-shadow:
    0 14rpx 32rpx rgba(31, 68, 122, 0.10),
    inset 0 1rpx 0 rgba(255, 255, 255, 0.86);
}

.linked-order-head {
  display: flex;
  align-items: center;
  gap: 16rpx;
}

.linked-order-icon {
  position: relative;
  width: 58rpx;
  height: 58rpx;
  flex: 0 0 58rpx;
  border-radius: 18rpx;
  background:
    radial-gradient(circle at 30% 18%, rgba(255, 255, 255, 0.92), transparent 42%),
    linear-gradient(145deg, #ffffff, #dcecff);
  box-shadow: inset 0 1rpx 0 rgba(255, 255, 255, 0.92), 0 8rpx 20rpx rgba(31, 68, 122, 0.12);
}

.order-icon-line {
  position: absolute;
  left: 15rpx;
  top: 14rpx;
  width: 28rpx;
  height: 24rpx;
  border: 3rpx solid #1f447a;
  border-top-width: 8rpx;
  border-radius: 18rpx;
  box-sizing: border-box;
}

.order-icon-dot-row {
  position: absolute;
  left: 20rpx;
  top: 32rpx;
  display: flex;
  gap: 4rpx;
}

.order-icon-dot-row view {
  width: 5rpx;
  height: 5rpx;
  border-radius: 50%;
  background: rgba(31, 68, 122, 0.68);
}

.linked-order-title-box {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4rpx;
}

.linked-order-label {
  color: #667085;
  font-size: 22rpx;
}

.linked-order-title {
  color: #172033;
  font-size: 30rpx;
  font-weight: 800;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.linked-order-status {
  padding: 8rpx 16rpx;
  border-radius: 999rpx;
  background: #edf4ff;
  color: #1f447a;
  font-size: 22rpx;
  font-weight: 700;
  white-space: nowrap;
}

.order-status-COMPLETED,
.order-status-IN_PROGRESS {
  background: #e8f7ef;
  color: #087443;
}

.order-status-CANCELLED,
.order-status-EXPIRED {
  background: #fff1f0;
  color: #b42318;
}

.linked-order-meta {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14rpx;
  margin-top: 20rpx;
}

.linked-order-meta-item {
  padding: 16rpx;
  border-radius: 22rpx;
  background: rgba(255, 255, 255, 0.62);
  border: 1rpx solid rgba(229, 237, 247, 0.9);
  display: flex;
  flex-direction: column;
  gap: 6rpx;
}

.meta-label {
  color: #98a2b3;
  font-size: 21rpx;
}

.meta-value {
  color: #344054;
  font-size: 24rpx;
  font-weight: 650;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.linked-order-foot {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10rpx;
  margin-top: 18rpx;
  color: #1f447a;
  font-size: 24rpx;
  font-weight: 700;
}

.linked-order-arrow {
  width: 13rpx;
  height: 13rpx;
  border-right: 3rpx solid #1f447a;
  border-bottom: 3rpx solid #1f447a;
  transform: rotate(-45deg);
}

.media-section {
  margin-bottom: 26rpx;
}

.media-image {
  width: 100%;
  border-radius: 28rpx;
  margin-bottom: 12rpx;
  background: #eef3f8;
  box-shadow: 0 14rpx 28rpx rgba(22, 47, 84, 0.10);
}

.action-bar {
  display: flex;
  gap: 40rpx;
  padding: 18rpx;
  border: 1rpx solid rgba(229, 237, 247, 0.84);
  border-radius: 26rpx;
  background: rgba(255, 255, 255, 0.58);
  margin-bottom: 26rpx;
}

.action-item {
  display: flex;
  align-items: center;
  gap: 10rpx;
  color: #667085;
  font-size: 27rpx;
}

.action-icon {
  position: relative;
  width: 34rpx;
  height: 34rpx;
  flex: 0 0 34rpx;
}

.like-icon::before,
.like-icon::after {
  content: "";
  position: absolute;
  background: #98a2b3;
}

.like-icon::before {
  width: 16rpx;
  height: 22rpx;
  left: 8rpx;
  top: 7rpx;
  border-radius: 8rpx 8rpx 4rpx 4rpx;
  transform: rotate(-18deg);
}

.like-icon::after {
  width: 22rpx;
  height: 16rpx;
  left: 10rpx;
  top: 13rpx;
  border-radius: 5rpx;
}

.like-icon.active::before,
.like-icon.active::after {
  background: #f04438;
}

.comment-icon {
  border: 3rpx solid #98a2b3;
  border-radius: 10rpx;
  box-sizing: border-box;
}

.comment-icon::after {
  content: "";
  position: absolute;
  left: 7rpx;
  bottom: -7rpx;
  width: 12rpx;
  height: 12rpx;
  border-left: 3rpx solid #98a2b3;
  border-bottom: 3rpx solid #98a2b3;
  background: #ffffff;
  transform: rotate(-35deg);
}

.comment-input-section {
  margin-bottom: 28rpx;
}

.replying-bar {
  margin-bottom: 14rpx;
  padding: 14rpx 18rpx;
  border-radius: 22rpx;
  background: rgba(237, 247, 255, 0.86);
  border: 1rpx solid rgba(191, 216, 247, 0.70);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18rpx;
}

.replying-text {
  color: #1f447a;
  font-size: 24rpx;
  font-weight: 700;
}

.replying-cancel {
  color: #667085;
  font-size: 23rpx;
}

.comment-input {
  width: 100%;
  min-height: 190rpx;
  padding: 20rpx;
  border: 1rpx solid rgba(217, 229, 243, 0.92);
  border-radius: 24rpx;
  box-sizing: border-box;
  background: rgba(255, 255, 255, 0.68);
  color: #1f2937;
  font-size: 28rpx;
  line-height: 1.6;
  margin-bottom: 18rpx;
}

.comment-actions {
  display: flex;
  justify-content: flex-end;
  gap: 18rpx;
}

.cancel-btn,
.submit-btn {
  height: 66rpx;
  line-height: 66rpx;
  padding: 0 34rpx;
  border: none;
  border-radius: 22rpx;
  font-size: 26rpx;
}

.cancel-btn {
  background: rgba(238, 246, 255, 0.86);
  color: #667085;
}

.submit-btn {
  background: linear-gradient(135deg, #2f7ed8, #1f447a);
  color: #ffffff;
}

.comments-section {
  margin-top: 10rpx;
}

.section-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 22rpx;
}

.section-title {
  color: #172033;
  font-size: 31rpx;
  font-weight: 800;
}

.section-count {
  color: #8a94a6;
  font-size: 24rpx;
}

.comments-list {
  display: flex;
  flex-direction: column;
  gap: 24rpx;
}

.comment-item {
  display: flex;
  gap: 16rpx;
}

.comment-item.child {
  position: relative;
  padding-left: 20rpx;
  border-left: 4rpx solid rgba(31, 68, 122, 0.14);
}

.comment-avatar {
  width: 62rpx;
  height: 62rpx;
  border-radius: 50%;
  flex: 0 0 62rpx;
  font-size: 24rpx;
}

.comment-content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}

.comment-title-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16rpx;
}

.comment-title-main {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 8rpx;
}

.comment-nickname {
  color: #1f2937;
  font-size: 26rpx;
  font-weight: 750;
}

.comment-reply-to {
  color: #667085;
  font-size: 22rpx;
}

.comment-delete {
  color: #b42318;
  font-size: 23rpx;
  flex-shrink: 0;
}

.comment-text {
  color: #475467;
  font-size: 27rpx;
  line-height: 1.6;
  word-break: break-word;
}

.comment-time {
  color: #98a2b3;
  font-size: 23rpx;
}

.comment-bottom-row {
  display: flex;
  align-items: center;
  gap: 20rpx;
}

.comment-reply {
  color: #1f447a;
  font-size: 23rpx;
  font-weight: 700;
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
</style>
