import api from '../utils/axios'

export const getPublicSystemInfo = async () => {
  const response = await api.get('/system/public-info')
  return response.data
}
