import dayjs from 'dayjs'
import relativeTime from 'dayjs/plugin/relativeTime'
import 'dayjs/locale/zh-cn'
import config from './config.js'

dayjs.extend(relativeTime)
dayjs.locale('zh-cn')

export function formatTime(time, format = 'YYYY-MM-DD HH:mm:ss') {
  if (!time) return ''
  return dayjs(time).format(format)
}

export function formatRelativeTime(time) {
  if (!time) return ''
  return dayjs(time).fromNow()
}

export function resolveFileUrl(url) {
  if (!url) return ''
  if (/^(https?:|data:|blob:)/.test(url)) return url
  if (/^\/tmp|^wxfile:|^file:/.test(url)) return url
  return `${config.fileBaseURL}${url.startsWith('/') ? url : `/${url}`}`
}

export function normalizeMediaList(content) {
  if (!content) return []
  if (Array.isArray(content.media)) {
    return content.media.map(item => ({
      ...item,
      url: resolveFileUrl(item.url)
    }))
  }
  if (Array.isArray(content.mediaUrls)) {
    return content.mediaUrls.map(url => ({
      url: resolveFileUrl(url),
      mediaType: content.mediaType || 'IMAGE'
    }))
  }
  return []
}

export function showLoading(title = '加载中...') {
  uni.showLoading({ title, mask: true })
}

export function hideLoading() {
  uni.hideLoading()
}

export function showSuccess(title) {
  uni.showToast({ title, icon: 'success', duration: 2000 })
}

export function showError(title) {
  uni.showToast({ title, icon: 'none', duration: 2000 })
}
