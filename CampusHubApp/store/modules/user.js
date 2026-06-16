import { authApi, userApi } from '@/api/index.js'
import { resolveFileUrl } from '@/utils/util.js'

const normalizeUserInfo = (userInfo) => {
  if (!userInfo) return null
  return {
    ...userInfo,
    avatarUrl: resolveFileUrl(userInfo.avatarUrl)
  }
}

const state = {
  token: null,
  userId: null,
  userInfo: null,
  isLogin: false
}

const mutations = {
  SET_TOKEN(state, token) {
    state.token = token || null
    if (token) {
      uni.setStorageSync('token', token)
    } else {
      uni.removeStorageSync('token')
    }
  },
  SET_USER_ID(state, userId) {
    state.userId = userId || null
    if (userId) {
      uni.setStorageSync('userId', userId)
    } else {
      uni.removeStorageSync('userId')
    }
  },
  SET_USER_INFO(state, userInfo) {
    const normalized = normalizeUserInfo(userInfo)
    state.userInfo = normalized
    if (normalized) {
      uni.setStorageSync('userInfo', JSON.stringify(normalized))
    } else {
      uni.removeStorageSync('userInfo')
    }
  },
  SET_LOGIN_STATUS(state, isLogin) {
    state.isLogin = !!isLogin
  },
  CLEAR_ALL(state) {
    state.token = null
    state.userId = null
    state.userInfo = null
    state.isLogin = false
    uni.removeStorageSync('token')
    uni.removeStorageSync('userId')
    uni.removeStorageSync('userInfo')
  }
}

const actions = {
  async login({ commit }, loginData) {
    const response = await authApi.login(loginData)
    if (response && response.userInfo) {
      const userId = response.userInfo.id || response.userInfo.uid
      commit('SET_TOKEN', response.token || null)
      commit('SET_USER_ID', userId)
      commit('SET_USER_INFO', response.userInfo)
      commit('SET_LOGIN_STATUS', true)
    }
    return response
  },
  async logout({ commit }) {
    try {
      await authApi.logout()
    } catch (e) {
      console.error('Logout failed:', e)
    }
    commit('CLEAR_ALL')
  },
  async initUserState({ commit, dispatch }) {
    const token = uni.getStorageSync('token')
    const userId = uni.getStorageSync('userId')
    const userInfoStr = uni.getStorageSync('userInfo')

    if (token) {
      commit('SET_TOKEN', token)
    }
    if (!userId) {
      return null
    }

    commit('SET_USER_ID', userId)
    commit('SET_LOGIN_STATUS', true)

    if (userInfoStr) {
      try {
        const userInfo = typeof userInfoStr === 'string' ? JSON.parse(userInfoStr) : userInfoStr
        commit('SET_USER_INFO', userInfo)
      } catch (e) {
        console.error('Parse cached user info failed:', e)
      }
    }

    return dispatch('refreshUserInfo').catch(() => null)
  },
  async refreshUserInfo({ commit, state }) {
    const userId = state.userId || uni.getStorageSync('userId')
    if (!userId) return null
    const userInfo = await userApi.getUserInfo(userId)
    commit('SET_USER_ID', userInfo.id || userId)
    commit('SET_USER_INFO', userInfo)
    commit('SET_LOGIN_STATUS', true)
    return userInfo
  },
  async updateUserInfo({ commit, state }, newInfo) {
    const userId = state.userId || uni.getStorageSync('userId')
    if (!userId) throw new Error('Please login first')
    const userInfo = await userApi.updateUserInfo(userId, newInfo)
    commit('SET_USER_INFO', userInfo)
    return userInfo
  },
  async uploadAvatar({ commit, state }, filePath) {
    const userId = state.userId || uni.getStorageSync('userId')
    if (!userId) throw new Error('Please login first')
    const avatarUrl = await userApi.uploadAvatar(userId, filePath)
    const nextUserInfo = {
      ...(state.userInfo || {}),
      avatarUrl
    }
    commit('SET_USER_INFO', nextUserInfo)
    return avatarUrl
  }
}

const getters = {
  token: state => state.token,
  userId: state => state.userId,
  userInfo: state => state.userInfo,
  isLogin: state => state.isLogin,
  isAdmin: state => {
    const userType = state.userInfo && state.userInfo.userType
    return userType === 'ADMIN' || userType === 1
  }
}

export default {
  namespaced: true,
  state,
  mutations,
  actions,
  getters
}
