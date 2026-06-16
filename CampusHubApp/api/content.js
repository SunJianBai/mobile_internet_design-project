import { get, post, put, del, upload } from '../utils/request.js'

export default {
  createContent(data) {
    return post('/contents', data)
  },
  getContents(params = {}) {
    return get('/contents', params)
  },
  getContentDetail(contentId) {
    return get(`/contents/${contentId}`)
  },
  updateContent(contentId, data) {
    return put(`/contents/${contentId}`, data)
  },
  deleteContent(contentId) {
    return del(`/contents/${contentId}`)
  },
  uploadMedia(contentId, filePath) {
    return upload(`/contents/${contentId}/media`, filePath, 'media')
  },
  getMedias(contentId) {
    return get(`/contents/${contentId}/medias`)
  },
  createComment(contentId, data) {
    return post(`/contents/${contentId}/comments`, data)
  },
  deleteComment(commentId) {
    return del(`/contents/comments/${commentId}`)
  },
  getComments(contentId, page = 1, size = 20) {
    return get(`/contents/${contentId}/comments`, { page, size })
  },
  likeContent(contentId) {
    return post(`/contents/${contentId}/like`, {})
  },
  searchByKeyword(keyword, page = 1, size = 10, type) {
    return get('/contents/search', { keyword, page, size, type })
  },
  getLikes(contentId) {
    return get(`/contents/${contentId}/likes`)
  }
}
