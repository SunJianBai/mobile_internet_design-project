<template>
  <div class="register-container">
    <el-card class="register-card">
      <template #header>
        <div class="auth-card-header">
          <h2>创建账号</h2>
          <p>填写邮箱验证码和基础资料，进入 CampusHub。</p>
        </div>
      </template>
      <el-form
        ref="registerFormRef"
        :model="registerForm"
        :rules="registerRules"
        label-position="top"
      >
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="registerForm.email" placeholder="请输入邮箱" />
        </el-form-item>
        <el-form-item label="验证码" prop="verifycode">
          <div class="verify-row">
            <el-input
              v-model="registerForm.verifycode"
              placeholder="请输入邮箱验证码"
              maxlength="6"
            />
            <el-button
              class="verify-btn"
              type="primary"
              plain
              :disabled="sendingCode || countdown > 0"
              @click="handleSendCode"
            >
              <span v-if="countdown === 0">获取验证码</span>
              <span v-else>{{ countdown }}s 后重试</span>
            </el-button>
          </div>
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input
            v-model="registerForm.password"
            type="password"
            placeholder="请输入密码"
            show-password
          />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirmPassword">
          <el-input
            v-model="registerForm.confirmPassword"
            type="password"
            placeholder="请确认密码"
            show-password
          />
        </el-form-item>
        <el-form-item label="昵称" prop="nickname">
          <el-input v-model="registerForm.nickname" placeholder="请输入昵称" />
        </el-form-item>
        <el-form-item label="学号" prop="studentId">
          <el-input v-model="registerForm.studentId" placeholder="请输入学号（选填）" />
        </el-form-item>
        <div class="register-actions">
          <el-button type="primary" class="auth-primary-btn" @click="handleRegister">注册</el-button>
          <router-link to="/login" class="login-link">登录</router-link>
        </div>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { ElMessage } from 'element-plus'
import { sendRegisterCode } from '../services/auth'

const router = useRouter()
const authStore = useAuthStore()

const registerFormRef = ref(null)

const registerForm = reactive({
  email: '',
  verifycode: '',
  password: '',
  confirmPassword: '',
  nickname: '',
  studentId: ''
})

const sendingCode = ref(false)
const countdown = ref(0)
let countdownTimer = null

const registerRules = {
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '请输入正确的邮箱格式', trigger: 'blur' }
  ],
  verifycode: [
    { required: true, message: '请输入验证码', trigger: 'blur' },
    { min: 6, max: 6, message: '验证码为6位数字', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码长度不能少于6个字符', trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    {
      validator: (rule, value, callback) => {
        if (value !== registerForm.password) {
          callback(new Error('两次输入密码不一致'))
        } else {
          callback()
        }
      },
      trigger: 'blur'
    }
  ],
  nickname: [
    { required: true, message: '请输入昵称', trigger: 'blur' }
  ]
}

const startCountdown = () => {
  countdown.value = 60
  countdownTimer = setInterval(() => {
    if (countdown.value > 0) {
      countdown.value -= 1
    } else {
      clearInterval(countdownTimer)
      countdownTimer = null
    }
  }, 1000)
}

const handleSendCode = async () => {
  if (!registerFormRef.value) return

  // 只校验邮箱字段
  await registerFormRef.value.validateField('email').catch(() => {
    return
  })

  if (!registerForm.email) return

  try {
    sendingCode.value = true
    await sendRegisterCode(registerForm.email)
    ElMessage.success('验证码已发送，请查收邮箱')
    if (!countdownTimer) {
      startCountdown()
    }
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || '发送验证码失败')
  } finally {
    sendingCode.value = false
  }
}

const handleRegister = async () => {
  try {
    const { confirmPassword, ...registerData } = registerForm
    await authStore.register(registerData)
    ElMessage.success('注册成功，请登录')
    router.push('/login')
  } catch (error) {
    const backendMsg = error?.response?.data?.message
    const storeMsg = authStore.error
    ElMessage.error(storeMsg || backendMsg || error.message || '注册失败')
  }
}

onBeforeUnmount(() => {
  if (countdownTimer) {
    clearInterval(countdownTimer)
  }
})
</script>

<style scoped>
.register-container {
  display: flex;
  justify-content: center;
  align-items: center;
}

.register-card {
  width: 100%;
  margin: 0;
}

.register-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin-top: 24px;
}

.login-link {
  color: var(--ch-primary);
  text-decoration: none;
  font-weight: 700;
}

.verify-row {
  display: flex;
  gap: 8px;
  width: 100%;
}

.verify-btn {
  flex: 0 0 auto;
  white-space: nowrap;
}

@media (max-width: 520px) {
  .verify-row {
    flex-direction: column;
  }

  .verify-btn {
    width: 100%;
  }
}
</style>
