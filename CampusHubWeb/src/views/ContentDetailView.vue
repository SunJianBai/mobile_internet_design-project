<template>
  <div class="content-detail-view">
    <div class="page-header content-detail-header">
      <el-button type="primary" link @click="handleBack" class="back-btn">
        <el-icon><ArrowLeft /></el-icon>
        <span>返回</span>
      </el-button>
      <h2>动态详情</h2>
    </div>

    <el-skeleton v-if="loading" :rows="6" animated />

    <template v-else>
      <el-card v-if="content" class="content-card" shadow="hover">
          <div class="card-header">
            <div class="user-info">
            <el-avatar
              :size="40"
              :src="resolveAvatarUrl(content.user?.avatarUrl)"
              class="user-avatar"
            >
              <span>{{ (content.user?.nickname || '用').slice(0, 1) }}</span>
            </el-avatar>
            <div class="user-meta">
              <div class="nickname">{{ content.user?.nickname || '用户' }}</div>
              <div class="time">{{ formatTime(content.createdAt) }}</div>
            </div>
            </div>
            <div class="card-actions">
              <el-button v-if="authStore.user && authStore.user.id === content.user?.id" type="danger" text size="small" @click="handleDelete">
                删除
              </el-button>
            </div>
        </div>

        <div class="card-content">
          <p class="text">{{ content.content }}</p>

          <!-- 附加订单信息卡片 -->
          <div
            v-if="content.order"
            class="order-card"
            @click="goToOrder(content.order.id)"
          >
            <div class="order-card-main">
              <div class="order-card-title">
                <div class="order-chip">
                  <el-icon class="order-chip-icon"><Tickets /></el-icon>
                  <span class="order-chip-text">订单 #{{ content.order.id }}</span>
                </div>
                <span class="order-activity">
                  {{ getActivityTypeLabel(content.order.activityType) }} ·
                  {{ content.order.location || '地点待定' }}
                </span>
              </div>
              <div class="order-card-meta">
                <span class="order-status">
                  状态：{{ getStatusLabel(content.order.status) }}
                </span>
                <span class="order-time">
                  开始时间：{{ formatTime(content.order.startTime) }}
                </span>
              </div>
            </div>
            <div class="order-card-arrow">
              <el-icon><ArrowRight /></el-icon>
            </div>
          </div>

          <div
              v-if="isImageType(content.mediaType) && content.mediaUrls && content.mediaUrls.length"
            class="media-grid"
          >
            <el-image
              v-for="(url, index) in content.mediaUrls"
              :key="index"
              :src="resolveMediaUrl(url)"
              fit="cover"
              class="media-image"
              :preview-src-list="content.mediaUrls.map(resolveMediaUrl)"
              lazy
            />
          </div>

          <div
              v-if="isVideoType(content.mediaType) && content.mediaUrls && content.mediaUrls.length"
            class="media-video"
          >
            <video
              v-for="(url, index) in content.mediaUrls"
              :key="index"
              :src="resolveMediaUrl(url)"
              controls
              class="video-player"
              preload="metadata"
            ></video>
          </div>
        </div>

        <div class="card-footer">
          <div class="left">
            <el-button
              text
              size="small"
              :type="content.liked ? 'primary' : 'default'"
              @click="handleLike"
            >
              <el-icon v-if="content.liked"><ThumbFilled /></el-icon>
              <el-icon v-else><ThumbOutline /></el-icon>
              <span>{{ content.liked ? '已点赞' : '点赞' }}（{{ content.likeCount || 0 }}）</span>
            </el-button>
            <span class="stat">评论 {{ content.commentCount || 0 }}</span>
          </div>
        </div>
      </el-card>

      <!-- 评论区 -->
      <el-card class="comment-card" shadow="never">
        <template #header>
          <div class="comment-header">
            <span>评论</span>
            <span class="comment-count">{{ totalComments }} 条</span>
          </div>
        </template>

        <!-- 发表评论（暂不支持附加图片） -->
        <div class="comment-editor">
          <el-input
            v-model="commentText"
            type="textarea"
            :rows="3"
            maxlength="300"
            show-word-limit
            placeholder="友善发言，文明交流～ 支持换行 😊"
          />
          <div class="comment-toolbar">
            <el-button
              type="primary"
              size="small"
              :loading="commentLoading"
              @click="handleSubmitComment"
            >
              发布评论
            </el-button>
          </div>
        </div>

        <!-- 评论列表 -->
        <div class="comment-list" v-if="comments.length">
          <comment-item
            v-for="item in comments"
            :key="item.id"
            :comment="item"
            :level="0"
            @reply="handleReply"
            @delete="handleDeleteComment"
          />
        </div>
        <el-empty v-else description="快来抢沙发~" />
      </el-card>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Tickets, ArrowRight, ArrowLeft } from '@element-plus/icons-vue'
import ThumbFilled from '../components/ThumbFilled.vue'
import ThumbOutline from '../components/ThumbOutline.vue'
import { useContentStore } from '../stores/content'
import { useAuthStore } from '../stores/auth'
import CommentItem from '../components/CommentItem.vue'

const route = useRoute()
const router = useRouter()
const contentStore = useContentStore()
const authStore = useAuthStore()

const contentId = Number(route.params.id)

const content = ref(null)
const loading = ref(false)

const comments = ref([])
const totalComments = ref(0)
const commentText = ref('')
const commentLoading = ref(false)
const replyParentId = ref(null)

const fileBaseUrl =
  import.meta.env.VITE_FILE_BASE_URL || (import.meta.env.PROD ? '' : 'http://localhost:8080')

const resolveMediaUrl = (url) => {
  if (!url) return url
  if (/^https?:\/\//.test(url)) return url
  return `${fileBaseUrl}${url}`
}

const resolveAvatarUrl = (url) => {
  if (!url) return url
  if (/^https?:\/\//.test(url)) return url
  return `${fileBaseUrl}${url}`
}

const formatTime = (time) => {
  if (!time) return ''
  const date = new Date(time)
  return date.toLocaleString()
}

// 订单相关展示文案
const activityTypeMap = {
  BASKETBALL: '篮球',
  BADMINTON: '羽毛球',
  MEAL: '吃饭',
  STUDY: '自习',
  MOVIE: '看电影',
  RUNNING: '跑步',
  GAME: '游戏',
  OTHER: '其他'
}

const statusMap = {
  PENDING: '待匹配',
  IN_PROGRESS: '进行中',
  COMPLETED: '已完成',
  CANCELLED: '已取消',
  EXPIRED: '已过期'
}

const getActivityTypeLabel = (type) => {
  if (!type) return '活动'
  if (typeof type === 'number') return '活动'
  return activityTypeMap[type] || '活动'
}

const getStatusLabel = (status) => {
  if (!status) return '未知'
  if (typeof status === 'number') return '状态'
  return statusMap[status] || '状态'
}

// 兼容后端返回的媒体类型：既可能是数字 1/2，也可能是字符串 'IMAGE'/'VIDEO'
const isImageType = (mediaType) => mediaType === 1 || mediaType === 'IMAGE'
const isVideoType = (mediaType) => mediaType === 2 || mediaType === 'VIDEO'

const fetchDetail = async () => {
  loading.value = true
  try {
    const resp = await contentStore.getContentDetail(contentId)
    content.value = resp.data?.data || resp.data || null
  } catch (error) {
    console.error('获取动态详情失败', error)
    ElMessage.error(error.response?.data?.message || '获取动态详情失败')
  } finally {
    loading.value = false
  }
}

const fetchComments = async () => {
  try {
    const resp = await contentStore.getComments(contentId, { page: 1, size: 200 })
    const data = resp.data?.data || resp.data || {}
    comments.value = data.list || []
    totalComments.value = data.total || comments.value.length
  } catch (error) {
    console.error('获取评论失败', error)
    ElMessage.error(error.response?.data?.message || '获取评论失败')
  }
}

const handleLike = async () => {
  if (!content.value) return
  try {
    const resp = await contentStore.likeContent(contentId)
    const likeData = resp.data?.data || {}
    if (Object.prototype.hasOwnProperty.call(likeData, 'liked')) {
      content.value.liked = likeData.liked
    }
    if (Object.prototype.hasOwnProperty.call(likeData, 'count')) {
      content.value.likeCount = likeData.count
    }
  } catch (error) {
    console.error('点赞失败', error)
    ElMessage.error(error.response?.data?.message || '点赞失败')
  }
}

const handleDelete = async () => {
  try {
    await ElMessageBox.confirm('删除后将无法恢复，确定要删除该动态吗？', '确认删除', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning'
    })

    const resp = await contentStore.deleteContent(contentId)
    // success
    ElMessage.success('删除成功')
    router.push('/contents')
  } catch (err) {
    if (err === 'cancel' || err?.message === 'cancel') {
      // 用户取消，不处理
      return
    }
    console.error('删除失败', err)
    ElMessage.error(err?.response?.data?.message || '删除失败')
  }
}

const handleSubmitComment = async () => {
  if (!commentText.value.trim()) {
    ElMessage.info('请输入评论内容')
    return
  }
  if (!authStore.user?.id) {
    ElMessage.warning('请先登录后再评论')
    router.push('/login')
    return
  }

  commentLoading.value = true
  try {
    const payload = {
      content: commentText.value,
      parentId: replyParentId.value
    }
    const resp = await contentStore.createComment(contentId, payload)

    // 从响应中解析评论 ID（后端为 ApiResponse<Long>）
    let commentId = null
    const body = resp?.data || {}
    const rawData = body.data
    if (rawData != null) {
      if (typeof rawData === 'number' || typeof rawData === 'string') {
        commentId = Number(rawData)
      } else if (typeof rawData === 'object') {
        commentId = rawData.commentId ?? rawData.id ?? null
      }
    }

    commentText.value = ''
    replyParentId.value = null
    ElMessage.success('评论发布成功')
    fetchComments()
  } catch (error) {
    console.error('发布评论失败', error)
    ElMessage.error(error.response?.data?.message || '发布评论失败')
  } finally {
    commentLoading.value = false
  }
}

const handleReply = (comment) => {
  replyParentId.value = comment.id
  commentText.value = `@${comment.user?.nickname || '用户'} `
}

const handleDeleteComment = async (comment) => {
  if (!comment || !comment.id) return

  try {
    await ElMessageBox.confirm(
      '删除后该评论及其下所有回复将无法恢复，确定要删除吗？',
      '确认删除',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    await contentStore.deleteComment(comment.id)
    ElMessage.success('删除评论成功')
    fetchComments()
  } catch (err) {
    if (err === 'cancel' || err?.message === 'cancel') {
      return
    }
    console.error('删除评论失败', err)
    ElMessage.error(err?.response?.data?.message || '删除评论失败')
  }
}

const handleBack = () => {
  router.back()
}

const goToOrder = (orderId) => {
  if (!orderId) return
  router.push(`/orders/${orderId}`)
}

onMounted(() => {
  fetchDetail()
  fetchComments()
})
</script>

<style scoped>
.content-detail-view {
  padding: clamp(8px, 2vw, 20px) 0;
  max-width: 920px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 18px;
  border: 1px solid var(--ch-border);
  border-radius: var(--ch-radius-lg);
  padding: 18px 20px;
  background:
    linear-gradient(135deg, rgba(31, 102, 255, 0.07), transparent 44%),
    var(--ch-surface-solid);
}

.page-header h2 {
  margin: 0;
  color: var(--ch-text);
  font-size: 24px;
  line-height: 1.2;
  font-weight: 900;
}

.back-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.content-card {
  margin-bottom: 16px;
  overflow: hidden;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.user-info {
  display: flex;
  align-items: center;
}

.user-avatar {
  margin-right: 10px;
}

.user-meta {
  display: flex;
  flex-direction: column;
}

.nickname {
  color: var(--ch-text);
  font-weight: 800;
}

.time {
  font-size: 12px;
  color: var(--ch-muted);
}

.card-content {
  margin-top: 14px;
}

.text {
  margin: 0 0 14px;
  color: var(--ch-text);
  font-size: 16px;
  line-height: 1.75;
  white-space: pre-wrap;
}

.media-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 8px;
}

.media-image {
  width: 100%;
  height: 140px;
}

.media-video {
  margin-top: 8px;
}

.video-player {
  width: 100%;
  max-height: 400px;
}

.order-card {
  margin-top: 14px;
  padding: 12px 14px;
  border-radius: var(--ch-radius);
  border: 1px solid var(--ch-border);
  background: color-mix(in srgb, var(--ch-bg-soft) 72%, transparent);
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
  transition:
    border-color 0.2s ease,
    background 0.2s ease,
    box-shadow 0.2s ease;
}

.order-card:hover {
  border-color: color-mix(in srgb, var(--ch-primary) 34%, var(--ch-border));
  background: var(--ch-primary-soft);
  box-shadow: 0 10px 24px rgba(31, 66, 115, 0.09);
}

.order-card-main {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.order-card-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.order-chip {
  display: inline-flex;
  align-items: center;
  column-gap: 4px;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 12px;
  background-color: var(--ch-primary-soft);
  color: var(--ch-primary);
  white-space: nowrap;
}

.order-chip-icon {
  font-size: 14px;
}

.order-activity {
  font-size: 13px;
  color: var(--ch-text);
}

.order-card-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  font-size: 12px;
  color: var(--ch-muted);
}

.order-card-arrow {
  color: var(--ch-muted);
}

.card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 12px;
}

.left {
  display: flex;
  gap: 8px;
  align-items: center;
}

.stat {
  font-size: 13px;
  color: var(--ch-muted);
}

.comment-card {
  margin-top: 12px;
  overflow: hidden;
}

.comment-header {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.comment-count {
  font-size: 12px;
  color: var(--ch-muted);
}

.comment-editor {
  margin-bottom: 16px;
}

.comment-toolbar {
  margin-top: 8px;
  display: flex;
  justify-content: flex-end;
  align-items: center;
}

.comment-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.comment-item {
  padding: 10px 0;
  border-bottom: 1px solid var(--ch-border);
}

.comment-main {
  display: flex;
}

.comment-avatar {
  margin-right: 8px;
}

.comment-body {
  flex: 1;
}

.comment-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 2px;
}

.comment-meta .name {
  font-weight: 500;
}

.comment-meta .time {
  font-size: 12px;
  color: var(--ch-muted);
}

.comment-text {
  font-size: 14px;
  margin-bottom: 4px;
  white-space: pre-wrap;
}

.comment-actions {
  display: flex;
  gap: 8px;
}

.comment-children {
  margin-left: 40px;
  margin-top: 6px;
}

@media (max-width: 768px) {
  .content-detail-view {
    padding: 0;
  }

  .page-header {
    padding: 16px;
  }

  .text {
    font-size: 15px;
  }

  .comment-children {
    margin-left: 28px;
  }
}
</style>
