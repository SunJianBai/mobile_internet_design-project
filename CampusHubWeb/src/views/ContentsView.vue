<template>
  <div class="contents-view">
    <section class="feed-hero">
      <div class="hero-copy">
        <span class="section-kicker">Campus Feed</span>
        <h2>动态广场</h2>
        <p>浏览校园现场、活动返图和同学们正在讨论的新鲜事。</p>
      </div>
      <div class="hero-actions">
        <div class="feed-segmented" role="group" aria-label="动态排序">
          <button
            v-for="item in sortOptions"
            :key="item.value"
            :class="['segment-button', { active: filters.sort === item.value }]"
            type="button"
            @click="filters.sort = item.value"
          >
            {{ item.label }}
          </button>
        </div>
        <el-button :loading="loading" plain @click="fetchContents">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
        <el-button type="primary" @click="goToCreate">
          <el-icon><Plus /></el-icon>
          发布动态
        </el-button>
      </div>
      <div class="hero-stats" aria-label="动态统计">
        <div>
          <strong>{{ total }}</strong>
          <span>全部动态</span>
        </div>
        <div>
          <strong>{{ feedStats.media }}</strong>
          <span>媒体内容</span>
        </div>
        <div>
          <strong>{{ feedStats.comments }}</strong>
          <span>评论互动</span>
        </div>
      </div>
    </section>

    <section class="feed-toolbar">
      <div>
        <strong>{{ filters.sort === 'hot' ? '热门优先' : '最新发布' }}</strong>
        <span>当前展示 {{ sortedContents.length }} 条内容</span>
      </div>
      <el-select v-model="filters.sort" class="mobile-sort" size="large">
        <el-option
          v-for="item in sortOptions"
          :key="item.value"
          :label="item.label"
          :value="item.value"
        />
      </el-select>
    </section>

    <div v-if="loading" class="feed-skeleton">
      <el-skeleton v-for="item in 3" :key="item" animated>
        <template #template>
          <div class="skeleton-card">
            <div class="skeleton-head">
              <el-skeleton-item variant="circle" class="skeleton-avatar" />
              <div>
                <el-skeleton-item variant="text" style="width: 140px" />
                <el-skeleton-item variant="text" style="width: 90px" />
              </div>
            </div>
            <el-skeleton-item variant="p" style="width: 92%" />
            <el-skeleton-item variant="p" style="width: 68%" />
          </div>
        </template>
      </el-skeleton>
    </div>

    <el-empty
      v-else-if="contentsList.length === 0"
      class="feed-empty"
      description="暂无动态"
    >
      <el-button type="primary" @click="goToCreate">发布第一条动态</el-button>
    </el-empty>

    <transition-group v-else name="list-fade" tag="div" class="content-list">
      <article
        v-for="item in sortedContents"
        :key="item.id"
        class="content-card"
        @click="goToDetail(item)"
      >
        <header class="card-header">
          <div class="user-info">
            <el-avatar :size="46" :src="resolveAvatarUrl(item.user?.avatarUrl)" class="user-avatar">
              <span>{{ (item.user?.nickname || '用户').slice(0, 1) }}</span>
            </el-avatar>
            <div class="user-meta">
              <strong>{{ item.user?.nickname || '用户' }}</strong>
              <span>{{ formatTime(item.createdAt) }}</span>
            </div>
          </div>
          <div class="card-tools">
            <el-tag v-if="hasMedia(item)" effect="plain" round>
              <el-icon>
                <VideoCamera v-if="isVideoType(item.mediaType)" />
                <Picture v-else />
              </el-icon>
              {{ mediaLabel(item.mediaType) }}
            </el-tag>
            <el-dropdown v-if="canDelete(item)" @command="(command) => handleMore(command, item)">
              <button class="more-button" type="button" @click.stop>
                更多
                <el-icon><ArrowDown /></el-icon>
              </button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="delete">删除</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </header>

        <div class="card-content">
          <p class="text">{{ item.content }}</p>

          <div
            v-if="isImageType(item.mediaType) && item.mediaUrls && item.mediaUrls.length"
            class="media-grid"
            @click.stop
          >
            <el-image
              v-for="(url, index) in item.mediaUrls"
              :key="index"
              :src="resolveMediaUrl(url)"
              fit="cover"
              class="media-image"
              :preview-src-list="item.mediaUrls.map(resolveMediaUrl)"
              lazy
            />
          </div>

          <div
            v-if="isVideoType(item.mediaType) && item.mediaUrls && item.mediaUrls.length"
            class="media-video"
            @click.stop
          >
            <video
              v-for="(url, index) in item.mediaUrls"
              :key="index"
              :src="resolveMediaUrl(url)"
              controls
              class="video-player"
              preload="metadata"
            ></video>
          </div>

          <button v-if="item.order" class="order-link" type="button" @click.stop="goToOrder(item.order.id)">
            <span>
              <el-icon><Tickets /></el-icon>
              关联活动
            </span>
            <strong>#{{ item.order.id }}</strong>
          </button>
        </div>

        <footer class="card-footer">
          <button
            :class="['action-button', { active: item.liked }]"
            type="button"
            @click.stop="handleLike(item)"
          >
            <el-icon v-if="item.liked"><ThumbFilled /></el-icon>
            <el-icon v-else><ThumbOutline /></el-icon>
            <span>{{ item.likeCount || 0 }}</span>
          </button>
          <button class="action-button" type="button" @click.stop="handleComment(item)">
            <el-icon><ChatDotRound /></el-icon>
            <span>{{ item.commentCount || 0 }}</span>
          </button>
        </footer>
      </article>
    </transition-group>

    <div class="pagination-wrapper" v-if="total > 0">
      <el-pagination
        background
        layout="total, sizes, prev, pager, next, jumper"
        :total="total"
        v-model:current-page="pagination.pageNum"
        v-model:page-size="pagination.pageSize"
        :page-sizes="[5, 10, 20, 50]"
        @size-change="handleSizeChange"
        @current-change="handleCurrentChange"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  ArrowDown,
  ChatDotRound,
  Picture,
  Plus,
  Refresh,
  Tickets,
  VideoCamera
} from '@element-plus/icons-vue'
import ThumbFilled from '../components/ThumbFilled.vue'
import ThumbOutline from '../components/ThumbOutline.vue'
import { useContentStore } from '../stores/content'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const contentStore = useContentStore()
const authStore = useAuthStore()

const contentsList = ref([])
const total = ref(0)
const loading = ref(false)

const sortOptions = [
  { label: '最新发布', value: 'latest' },
  { label: '热门优先', value: 'hot' }
]

const filters = reactive({
  sort: 'latest'
})

const pagination = reactive({
  pageNum: 1,
  pageSize: 10
})

const fileBaseUrl =
  import.meta.env.VITE_FILE_BASE_URL || (import.meta.env.PROD ? '' : 'http://localhost:8080')

const resolveMediaUrl = (url) => {
  if (!url) return url
  if (/^https?:\/\//.test(url)) return url
  return `${fileBaseUrl}${url}`
}

// The backend can return either legacy numeric media types or string enums.
const isImageType = (mediaType) => mediaType === 1 || mediaType === 'IMAGE'
const isVideoType = (mediaType) => mediaType === 2 || mediaType === 'VIDEO'

const hasMedia = (item) => Boolean(item?.mediaUrls?.length)

const mediaLabel = (mediaType) => {
  if (isVideoType(mediaType)) return '视频'
  if (isImageType(mediaType)) return '图片'
  return '媒体'
}

const resolveAvatarUrl = (url) => {
  if (!url) return url
  if (/^https?:\/\//.test(url)) return url
  return `${fileBaseUrl}${url}`
}

const currentUser = computed(() => authStore.user)

const feedStats = computed(() => ({
  media: contentsList.value.filter((item) => hasMedia(item)).length,
  comments: contentsList.value.reduce((sum, item) => sum + Number(item.commentCount || 0), 0)
}))

const fetchContents = async () => {
  loading.value = true
  try {
    const params = {
      pageNum: pagination.pageNum,
      pageSize: pagination.pageSize
    }

    const response = await contentStore.getContents(params)
    const data = response.data?.data || response.data || {}
    contentsList.value = data.list || []
    total.value = data.total || 0
  } catch (error) {
    console.error('获取内容列表失败', error)
    ElMessage.error(error.response?.data?.message || '获取内容列表失败')
  } finally {
    loading.value = false
  }
}

const sortedContents = computed(() => {
  const list = [...contentsList.value]
  if (filters.sort === 'hot') {
    return list.sort((a, b) => {
      const la = a.likeCount || 0
      const lb = b.likeCount || 0
      if (lb !== la) return lb - la
      return new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
    })
  }
  return list.sort(
    (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
  )
})

const handleSizeChange = (val) => {
  pagination.pageSize = val
  pagination.pageNum = 1
  fetchContents()
}

const handleCurrentChange = (val) => {
  pagination.pageNum = val
  fetchContents()
}

const formatTime = (time) => {
  if (!time) return ''
  const date = new Date(time)
  return date.toLocaleString()
}

const canDelete = (item) => {
  const user = currentUser.value
  if (!user) return false
  if (user.userType === 1 || user.userType === 'ADMIN') return true
  return item.user && item.user.id === user.id
}

const handleMore = (command, item) => {
  if (command === 'delete') {
    handleDelete(item)
  }
}

const handleDelete = (item) => {
  ElMessageBox.confirm('确定要删除该动态吗？', '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  })
    .then(async () => {
      try {
        await contentStore.deleteContent(item.id)
        ElMessage.success('删除成功')
        fetchContents()
      } catch (error) {
        console.error('删除失败', error)
        ElMessage.error(error.response?.data?.message || '删除失败')
      }
    })
    .catch(() => {})
}

const handleLike = async (item) => {
  try {
    const response = await contentStore.likeContent(item.id)
    const likeData = response.data?.data || {}
    if (Object.prototype.hasOwnProperty.call(likeData, 'liked')) {
      item.liked = likeData.liked
    }
    if (Object.prototype.hasOwnProperty.call(likeData, 'count')) {
      item.likeCount = likeData.count
    }
  } catch (error) {
    console.error('点赞失败', error)
    ElMessage.error(error.response?.data?.message || '点赞失败')
  }
}

const handleComment = (item) => {
  router.push(`/contents/${item.id}`)
}

const goToDetail = (item) => {
  router.push(`/contents/${item.id}`)
}

const goToOrder = (orderId) => {
  if (!orderId) return
  router.push(`/orders/${orderId}`)
}

const goToCreate = () => {
  router.push('/contents/create')
}

onMounted(() => {
  fetchContents()
})
</script>

<style scoped>
.contents-view {
  display: grid;
  gap: 18px;
}

.feed-hero,
.feed-toolbar,
.content-card,
.skeleton-card,
.feed-empty {
  border: 1px solid var(--ch-border);
  background: var(--ch-surface);
  box-shadow: var(--ch-shadow);
  backdrop-filter: blur(22px);
}

.feed-hero {
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 22px;
  overflow: hidden;
  padding: 26px;
  border-radius: 24px;
}

.feed-hero::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background:
    radial-gradient(circle at 88% 12%, rgba(20, 184, 166, 0.18), transparent 30%),
    radial-gradient(circle at 6% 88%, rgba(59, 130, 246, 0.16), transparent 28%);
}

.hero-copy,
.hero-actions,
.hero-stats {
  position: relative;
  z-index: 1;
}

.section-kicker {
  display: inline-flex;
  align-items: center;
  width: max-content;
  margin-bottom: 10px;
  padding: 5px 10px;
  border: 1px solid rgba(20, 184, 166, 0.26);
  border-radius: 999px;
  color: var(--ch-primary);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0;
  background: rgba(20, 184, 166, 0.08);
}

.hero-copy h2 {
  margin: 0;
  color: var(--ch-text);
  font-size: clamp(28px, 4vw, 44px);
  line-height: 1.1;
  letter-spacing: 0;
}

.hero-copy p {
  max-width: 560px;
  margin: 12px 0 0;
  color: var(--ch-muted);
  font-size: 15px;
  line-height: 1.7;
}

.hero-actions {
  display: flex;
  align-items: flex-start;
  justify-content: flex-end;
  gap: 10px;
}

.feed-segmented {
  display: inline-flex;
  flex-shrink: 0;
  gap: 4px;
  padding: 4px;
  border: 1px solid var(--ch-border);
  border-radius: 14px;
  background: var(--ch-bg-soft);
}

.segment-button {
  min-height: 34px;
  padding: 0 14px;
  border: 0;
  border-radius: 10px;
  color: var(--ch-muted);
  font: inherit;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0;
  background: transparent;
  cursor: pointer;
  transition: background 0.18s ease, color 0.18s ease, box-shadow 0.18s ease;
}

.segment-button:hover,
.segment-button.active {
  color: var(--ch-text);
  background: var(--ch-surface-solid);
  box-shadow: 0 8px 18px rgba(15, 23, 42, 0.08);
}

.hero-stats {
  grid-column: 1 / -1;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.hero-stats div {
  min-width: 0;
  padding: 14px;
  border: 1px solid var(--ch-border);
  border-radius: 16px;
  background: var(--ch-surface-solid);
}

.hero-stats strong,
.hero-stats span {
  display: block;
}

.hero-stats strong {
  color: var(--ch-text);
  font-size: 22px;
  line-height: 1.2;
}

.hero-stats span {
  margin-top: 4px;
  color: var(--ch-muted);
  font-size: 12px;
}

.feed-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 14px 16px;
  border-radius: 18px;
}

.feed-toolbar strong,
.feed-toolbar span {
  display: block;
}

.feed-toolbar strong {
  color: var(--ch-text);
  font-size: 15px;
}

.feed-toolbar span {
  margin-top: 3px;
  color: var(--ch-muted);
  font-size: 12px;
}

.mobile-sort {
  display: none;
  width: 160px;
  max-width: 100%;
}

.mobile-sort :deep(.el-select__wrapper) {
  min-width: 150px;
}

.feed-skeleton {
  display: grid;
  gap: 14px;
}

.skeleton-card {
  padding: 18px;
  border-radius: 18px;
}

.skeleton-head {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 18px;
}

.skeleton-avatar {
  width: 46px;
  height: 46px;
}

.feed-empty {
  min-height: 300px;
  border-radius: 22px;
}

.content-list {
  display: grid;
  gap: 16px;
}

.content-card {
  position: relative;
  overflow: hidden;
  padding: 20px;
  border-radius: 22px;
  cursor: pointer;
  transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
}

.content-card::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  opacity: 0;
  background: linear-gradient(135deg, rgba(20, 184, 166, 0.1), rgba(59, 130, 246, 0.08));
  transition: opacity 0.2s ease;
}

.content-card:hover {
  border-color: rgba(20, 184, 166, 0.32);
  box-shadow: 0 24px 70px rgba(15, 23, 42, 0.16);
  transform: translateY(-3px);
}

.content-card:hover::before {
  opacity: 1;
}

.card-header,
.card-content,
.card-footer {
  position: relative;
  z-index: 1;
}

.card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
}

.user-info {
  display: flex;
  align-items: center;
  min-width: 0;
  gap: 12px;
}

.user-avatar {
  flex: 0 0 auto;
  border: 2px solid rgba(255, 255, 255, 0.7);
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.12);
}

.user-meta {
  min-width: 0;
}

.user-meta strong {
  display: block;
  overflow: hidden;
  color: var(--ch-text);
  font-size: 15px;
  line-height: 1.35;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user-meta span {
  display: block;
  margin-top: 3px;
  color: var(--ch-muted);
  font-size: 12px;
}

.card-tools {
  display: flex;
  align-items: center;
  gap: 8px;
}

.card-tools :deep(.el-tag) {
  gap: 4px;
  height: 30px;
  border-color: rgba(20, 184, 166, 0.28);
  color: var(--ch-primary);
  background: rgba(20, 184, 166, 0.08);
}

.more-button,
.order-link,
.action-button {
  border: 0;
  font: inherit;
  cursor: pointer;
}

.more-button {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 7px 10px;
  border: 1px solid var(--ch-border);
  border-radius: 999px;
  color: var(--ch-muted);
  background: var(--ch-surface-solid);
}

.card-content {
  margin-top: 16px;
}

.text {
  margin: 0;
  color: var(--ch-text);
  font-size: 16px;
  line-height: 1.75;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.media-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(156px, 1fr));
  gap: 10px;
  margin-top: 14px;
}

.media-image {
  width: 100%;
  height: 156px;
  overflow: hidden;
  border-radius: 16px;
  border: 1px solid var(--ch-border);
  background: var(--ch-bg-soft);
}

.media-video {
  margin-top: 14px;
}

.video-player {
  width: 100%;
  max-height: 420px;
  border: 1px solid var(--ch-border);
  border-radius: 18px;
  background: #020617;
}

.order-link {
  display: inline-flex;
  align-items: center;
  justify-content: space-between;
  max-width: 100%;
  min-height: 40px;
  gap: 18px;
  margin-top: 14px;
  padding: 8px 12px;
  border: 1px solid rgba(59, 130, 246, 0.26);
  border-radius: 14px;
  color: var(--ch-text);
  background: rgba(59, 130, 246, 0.08);
}

.order-link span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  color: var(--ch-muted);
  font-size: 13px;
}

.order-link strong {
  color: var(--ch-primary);
  font-size: 13px;
}

.card-footer {
  display: flex;
  gap: 10px;
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px solid var(--ch-border);
}

.action-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 72px;
  height: 36px;
  gap: 7px;
  padding: 0 12px;
  border: 1px solid var(--ch-border);
  border-radius: 999px;
  color: var(--ch-muted);
  background: var(--ch-surface-solid);
  transition: transform 0.18s ease, border-color 0.18s ease, color 0.18s ease;
}

.action-button:hover,
.action-button.active {
  border-color: rgba(20, 184, 166, 0.35);
  color: var(--ch-primary);
  transform: translateY(-1px);
}

.pagination-wrapper {
  display: flex;
  justify-content: flex-end;
  overflow: hidden;
}

.list-fade-enter-active,
.list-fade-leave-active {
  transition: all 0.25s ease;
}

.list-fade-enter-from,
.list-fade-leave-to {
  opacity: 0;
  transform: translateY(8px);
}

@media (max-width: 980px) {
  .feed-hero {
    grid-template-columns: 1fr;
  }

  .hero-actions {
    justify-content: flex-start;
    flex-wrap: wrap;
  }
}

@media (max-width: 720px) {
  .feed-hero {
    padding: 20px;
    border-radius: 20px;
  }

  .feed-segmented {
    display: none;
  }

  .hero-stats {
    grid-template-columns: 1fr;
  }

  .mobile-sort {
    display: block;
  }

  .content-card {
    padding: 16px;
    border-radius: 18px;
  }

  .card-header {
    display: grid;
  }

  .card-tools {
    justify-content: space-between;
  }

  .media-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .media-image {
    height: 128px;
  }

  .pagination-wrapper {
    justify-content: center;
  }

  .pagination-wrapper :deep(.el-pagination) {
    justify-content: center;
    max-width: 100%;
  }
}

@media (max-width: 480px) {
  .feed-toolbar {
    align-items: stretch;
    display: grid;
  }

  .mobile-sort {
    width: 170px;
  }

  .hero-actions {
    display: grid;
    grid-template-columns: 1fr 1fr;
  }

  .hero-actions :deep(.el-button) {
    width: 100%;
  }
}
</style>
