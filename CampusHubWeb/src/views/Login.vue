<template>
  <div class="login-container">
    <el-card class="login-card">
      <template #header>
        <div class="auth-card-header">
          <h2>欢迎回来</h2>
          <p>登录后继续查看校园活动、动态与后台工作台。</p>
        </div>
      </template>
      <el-form
        ref="loginFormRef"
        :model="loginForm"
        :rules="loginRules"
        label-position="top"
      >
        <el-form-item label="邮箱" prop="identifier">
          <el-input v-model="loginForm.identifier" placeholder="请输入学号或邮箱" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input
            v-model="loginForm.password"
            type="password"
            placeholder="请输入密码"
            show-password
          />
        </el-form-item>
        <div class="login-actions">
          <el-button type="primary" class="auth-primary-btn" @click="handleLogin">登录</el-button>
          <div class="login-links">
            <router-link to="/forgot-password" class="forgot-link">忘记密码？</router-link>
            <router-link to="/register" class="register-link">注册</router-link>
          </div>
        </div>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { ElMessage } from 'element-plus'

const router = useRouter()
const authStore = useAuthStore()

const loginFormRef = ref(null)

const loginForm = reactive({
  identifier: '',
  password: ''
})

const loginRules = {
  identifier: [
    { required: true, message: '请输入学号或邮箱', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' }
  ]
}

const handleLogin = async () => {
  try {
    await authStore.login(loginForm)
    // 登录成功后回跳到最初请求页面（若有）
    const redirect = router.currentRoute.value.query.redirect || '/'
    await router.push(redirect)
  } catch (error) {
    const backendMsg = error?.response?.data?.message
    const storeMsg = authStore.error
    ElMessage.error(storeMsg || backendMsg || error.message || '登录失败')
  }
}
</script>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
}

.login-card {
  width: 100%;
  margin: 0;
}

.login-actions {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-top: 24px;
}

.login-links {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  font-size: 14px;
}

.register-link,
.forgot-link {
  color: var(--ch-primary);
  text-decoration: none;
  font-weight: 700;
}
</style>
