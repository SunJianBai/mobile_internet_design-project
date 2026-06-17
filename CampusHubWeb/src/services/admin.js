import api from '../utils/axios'

export const getAdminStatistics = async () => {
  const response = await api.get('/admin/statistics')
  return response.data
}

export const getAdminUsers = async (params = {}) => {
  const response = await api.get('/admin/users', { params })
  return response.data
}

export const getAdminAuditLogs = async (params = {}) => {
  const response = await api.get('/admin/audit-logs', { params })
  return response.data
}

export const updateAdminUserType = async (userId, userType) => {
  const response = await api.put(`/admin/users/${userId}/type`, null, {
    params: { userType }
  })
  return response.data
}

export const updateAdminUserStatus = async (userId, userStatus) => {
  const response = await api.put(`/admin/users/${userId}/status`, null, {
    params: { userStatus }
  })
  return response.data
}

export const getAdminOrders = async (params = {}) => {
  const response = await api.get('/admin/orders', { params })
  return response.data
}

export const updateAdminOrderStatus = async (orderId, status) => {
  const response = await api.put(`/admin/orders/${orderId}`, null, {
    params: { status }
  })
  return response.data
}

export const getAdminOrderApplications = async (params = {}) => {
  const response = await api.get('/admin/order-applications', { params })
  return response.data
}

export const auditAdminOrderApplication = async (applyId, status) => {
  const response = await api.put(`/admin/order-applications/${applyId}`, null, {
    params: { status }
  })
  return response.data
}

export const getAdminContents = async (params = {}) => {
  const response = await api.get('/admin/contents', { params })
  return response.data
}

export const updateAdminContentStatus = async (contentId, status) => {
  const response = await api.put(`/admin/contents/${contentId}/status`, null, {
    params: { status }
  })
  return response.data
}

export const deleteAdminContent = async (contentId) => {
  const response = await api.delete(`/admin/contents/${contentId}`)
  return response.data
}

export const getAdminAiAuditConversations = async (params = {}) => {
  const response = await api.get('/admin/ai/conversations', { params })
  return response.data
}

export const getAdminAiAuditItems = async (params = {}) => {
  const response = await api.get('/admin/ai/audit', { params })
  return response.data
}

export const getAdminAiConversationMessages = async (conversationId) => {
  const response = await api.get(`/admin/ai/conversations/${conversationId}/messages`)
  return response.data
}

export const deleteAdminAiConversation = async (conversationId) => {
  const response = await api.delete(`/admin/ai/conversations/${conversationId}`)
  return response.data
}

export const getAdminAiAuditMemories = async (params = {}) => {
  const response = await api.get('/admin/ai/memories', { params })
  return response.data
}

export const deleteAdminAiMemory = async (memoryId) => {
  const response = await api.delete(`/admin/ai/memories/${memoryId}`)
  return response.data
}

export const getAdminFiles = async (params = {}) => {
  const response = await api.get('/admin/files', { params })
  return response.data
}

export const deleteAdminFile = async (pmid) => {
  const response = await api.delete(`/admin/files/${pmid}`)
  return response.data
}

export const getAdminSettings = async () => {
  const response = await api.get('/admin/settings')
  return response.data
}

export const updateAdminSettings = async (settings) => {
  const response = await api.put('/admin/settings', settings)
  return response.data
}
