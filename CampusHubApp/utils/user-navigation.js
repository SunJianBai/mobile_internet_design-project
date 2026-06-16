export const getUserId = (user) => {
  if (!user) return ''
  return user.uid || user.id || user.userId || ''
}

export const goUserProfile = (userOrId) => {
  const targetId = typeof userOrId === 'object' ? getUserId(userOrId) : userOrId
  if (!targetId) return

  const currentUserId = uni.getStorageSync('userId')
  if (currentUserId && String(currentUserId) === String(targetId)) {
    uni.switchTab({ url: '/pages/user/info' })
    return
  }

  uni.navigateTo({ url: `/pages/user/profile?id=${targetId}` })
}
