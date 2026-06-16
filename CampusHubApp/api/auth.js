import { post } from '../utils/request.js'

const emailPayload = (value) => {
  return typeof value === 'string' ? { email: value } : value
}

const resetCodePayload = (emailOrPayload, verifyCode) => {
  if (typeof emailOrPayload === 'object') {
    return emailOrPayload
  }
  return { email: emailOrPayload, verifyCode }
}

const resetPasswordPayload = (emailOrPayload, verifyCode, newPassword) => {
  if (typeof emailOrPayload === 'object') {
    return emailOrPayload
  }
  return { email: emailOrPayload, verifyCode, newPassword }
}

export default {
  login(data) {
    return post('/auth/login', data, false)
  },
  register(data) {
    return post('/auth/register', data, false)
  },
  logout() {
    return post('/auth/logout', {})
  },
  refreshToken(refreshToken) {
    return post('/auth/refresh', { refreshToken }, false)
  },
  verifyEmailForReset(emailOrPayload) {
    return post('/auth/forgot/verify-email', emailPayload(emailOrPayload), false)
  },
  sendResetCode(emailOrPayload) {
    return post('/auth/forgot/send-code', emailPayload(emailOrPayload), false)
  },
  verifyResetCode(emailOrPayload, verifyCode) {
    return post('/auth/forgot/verify-code', resetCodePayload(emailOrPayload, verifyCode), false)
  },
  resetPassword(emailOrPayload, verifyCode, newPassword) {
    return post('/auth/forgot/reset-password', resetPasswordPayload(emailOrPayload, verifyCode, newPassword), false)
  },
  forgotPasswordStep1(data) {
    return this.verifyEmailForReset(data)
  },
  forgotPasswordStep2(data) {
    return this.verifyResetCode(data)
  },
  forgotPasswordStep3(data) {
    return this.resetPassword(data)
  }
}
