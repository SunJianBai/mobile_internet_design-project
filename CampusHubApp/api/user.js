import { get, put, upload } from '../utils/request.js'

const passwordPayload = (oldPasswordOrPayload, newPassword) => {
  if (typeof oldPasswordOrPayload === 'object') {
    return oldPasswordOrPayload
  }
  return { oldPassword: oldPasswordOrPayload, newPassword }
}

export default {
  getUserInfo(userId) {
    return get(`/users/${userId}`)
  },
  updateUserInfo(userId, data) {
    return put(`/users/${userId}`, data)
  },
  changePassword(userId, oldPasswordOrPayload, newPassword) {
    return put(`/users/${userId}/password`, passwordPayload(oldPasswordOrPayload, newPassword))
  },
  uploadAvatar(userId, filePath) {
    return upload(`/users/${userId}/avatar`, filePath, 'avatar')
  },
  searchUsers(keyword, page = 1, size = 10) {
    return get('/users/search', { keyword, page, size })
  }
}
