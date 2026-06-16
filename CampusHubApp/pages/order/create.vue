<template>
  <view class="create-order-container">
    <view class="header-block">
      <text class="page-title">发起活动</text>
      <text class="page-subtitle">把时间、地点和人数说清楚，方便同学快速加入。</text>
    </view>

    <view class="form-panel">
      <view class="form-item">
        <text class="label">活动类型</text>
        <picker mode="selector" :range="activityTypeOptions" range-key="label" @change="onActivityTypeChange">
          <view class="picker-view">
            <text :class="form.activityType ? 'picker-text' : 'placeholder'">
              {{ form.activityType ? getActivityTypeText(form.activityType) : '请选择活动类型' }}
            </text>
            <view class="chevron"></view>
          </view>
        </picker>
      </view>

      <view class="form-item">
        <text class="label">性别要求</text>
        <view class="segmented">
          <view
            v-for="item in genderOptions"
            :key="item.value"
            :class="['segment-item', form.genderRequire === item.value ? 'active' : '']"
            @click="form.genderRequire = item.value"
          >
            {{ item.label }}
          </view>
        </view>
      </view>

      <view class="form-item">
        <text class="label">校区</text>
        <picker mode="selector" :range="campusOptions" range-key="label" @change="onCampusChange">
          <view class="picker-view">
            <text :class="form.campus ? 'picker-text' : 'placeholder'">
              {{ form.campus ? getCampusText(form.campus) : '请选择校区' }}
            </text>
            <view class="chevron"></view>
          </view>
        </picker>
        <view v-if="showMatchingHint" class="matching-hint" @click="goToMatchedOrders">
          <view class="hint-icon search-icon"></view>
          <text>找到 {{ matchingCount }} 个相似活动，点此查看</text>
        </view>
      </view>

      <view class="form-item">
        <text class="label">活动地点</text>
        <input
          v-model.trim="form.location"
          class="input"
          maxlength="100"
          placeholder="例如：良乡体育馆 3 号场"
        />
      </view>

      <view class="form-item">
        <text class="label">开始时间</text>
        <view class="time-row">
          <picker class="time-picker" mode="date" :value="dateValue" :start="minDate" @change="onDateChange">
            <view class="picker-view compact">
              <text :class="dateValue ? 'picker-text' : 'placeholder'">{{ dateValue || '选择日期' }}</text>
            </view>
          </picker>
          <picker class="time-picker" mode="time" :value="timeValue" @change="onTimeChange">
            <view class="picker-view compact">
              <text :class="timeValue ? 'picker-text' : 'placeholder'">{{ timeValue || '选择时间' }}</text>
            </view>
          </picker>
        </view>
        <text class="field-tip">开始时间必须晚于当前时间。</text>
      </view>

      <view class="form-item">
        <text class="label">人数上限</text>
        <view class="stepper-row">
          <button class="stepper-btn" :disabled="form.maxPeople <= 1" @click="adjustMaxPeople(-1)">-</button>
          <input v-model.number="form.maxPeople" class="input number-input" type="number" />
          <button class="stepper-btn" :disabled="form.maxPeople >= 20" @click="adjustMaxPeople(1)">+</button>
        </view>
        <text class="field-tip">支持 1-20 人，发布后待匹配状态下仍可调整。</text>
      </view>

      <view class="form-item">
        <text class="label">备注</text>
        <textarea
          v-model="form.note"
          class="textarea"
          maxlength="200"
          placeholder="可写明集合方式、装备要求或其他补充说明"
        />
        <text class="counter">{{ form.note.length }}/200</text>
      </view>
    </view>

    <view class="bottom-actions">
      <button class="ghost-btn" @click="handleCancel">取消</button>
      <button class="submit-btn" :loading="loading" @click="handleSubmit">发布活动</button>
    </view>
  </view>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { useStore } from 'vuex'
import { orderApi } from '@/api/index.js'
import { showLoading, hideLoading, showSuccess, showError } from '@/utils/util.js'
import { ACTIVITY_TYPE, ACTIVITY_TYPE_MAP, GENDER_REQUIRE, GENDER_REQUIRE_MAP, CAMPUS, CAMPUS_MAP } from '@/utils/constants.js'

const store = useStore()

const form = ref({
  activityType: null,
  genderRequire: GENDER_REQUIRE.ANY,
  campus: null,
  location: '',
  startTime: '',
  maxPeople: 2,
  note: ''
})

const dateValue = ref('')
const timeValue = ref('')
const loading = ref(false)
const matchingCount = ref(0)
const matchingLoading = ref(false)
let matchingTimer = null

const activityTypeOptions = Object.keys(ACTIVITY_TYPE).map(key => ({
  value: ACTIVITY_TYPE[key],
  label: ACTIVITY_TYPE_MAP[ACTIVITY_TYPE[key]]
}))

const genderOptions = Object.keys(GENDER_REQUIRE).map(key => ({
  value: GENDER_REQUIRE[key],
  label: GENDER_REQUIRE_MAP[GENDER_REQUIRE[key]]
}))

const campusOptions = Object.keys(CAMPUS).map(key => ({
  value: CAMPUS[key],
  label: CAMPUS_MAP[CAMPUS[key]]
}))

const getMinDate = () => {
  const now = new Date()
  const year = now.getFullYear()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

const minDate = ref(getMinDate())

const showMatchingHint = computed(() => {
  return form.value.activityType && form.value.campus && !matchingLoading.value && matchingCount.value > 0
})

onLoad((options = {}) => {
  if (!store.getters['user/isLogin']) {
    showError('请先登录')
    setTimeout(() => {
      uni.redirectTo({ url: '/pages/auth/login' })
    }, 800)
    return
  }

  applyQueryDefaults(options)
})

watch(
  () => [form.value.activityType, form.value.campus],
  ([activityType, campus]) => {
    if (matchingTimer) clearTimeout(matchingTimer)
    if (!activityType || !campus) {
      matchingCount.value = 0
      return
    }
    matchingTimer = setTimeout(() => {
      fetchMatchingOrdersCount(activityType, campus)
    }, 250)
  }
)

const applyQueryDefaults = (options) => {
  if (options.activityType) form.value.activityType = String(options.activityType)
  if (options.genderRequire) form.value.genderRequire = String(options.genderRequire)
  if (options.campus) form.value.campus = String(options.campus)
  if (options.location) form.value.location = decodeURIComponent(String(options.location))
  if (options.note) form.value.note = decodeURIComponent(String(options.note))
  if (options.maxPeople) {
    const n = Number(options.maxPeople)
    if (Number.isInteger(n) && n >= 1 && n <= 20) form.value.maxPeople = n
  }
  if (options.startTime) {
    const value = decodeURIComponent(String(options.startTime)).replace('T', ' ').slice(0, 19)
    form.value.startTime = value
    dateValue.value = value.slice(0, 10)
    timeValue.value = value.slice(11, 16)
  }
}

const getActivityTypeText = (type) => ACTIVITY_TYPE_MAP[type] || ''
const getGenderText = (gender) => GENDER_REQUIRE_MAP[gender] || ''
const getCampusText = (campus) => CAMPUS_MAP[campus] || ''

const onActivityTypeChange = (e) => {
  form.value.activityType = activityTypeOptions[e.detail.value].value
}

const onGenderChange = (e) => {
  form.value.genderRequire = genderOptions[e.detail.value].value
}

const onCampusChange = (e) => {
  form.value.campus = campusOptions[e.detail.value].value
}

const onDateChange = (e) => {
  dateValue.value = e.detail.value
  updateStartTime()
}

const onTimeChange = (e) => {
  timeValue.value = e.detail.value
  updateStartTime()
}

const updateStartTime = () => {
  if (dateValue.value && timeValue.value) {
    form.value.startTime = `${dateValue.value} ${timeValue.value}:00`
  }
}

const adjustMaxPeople = (delta) => {
  const next = Number(form.value.maxPeople || 0) + delta
  form.value.maxPeople = Math.max(1, Math.min(20, next))
}

const fetchMatchingOrdersCount = async (activityType, campus) => {
  matchingLoading.value = true
  try {
    const result = await orderApi.getOrders({
      page: 1,
      size: 1,
      status: 'PENDING',
      activityType,
      campus
    })
    matchingCount.value = Number(result?.total || 0)
  } catch (error) {
    console.error('加载相似活动数量失败:', error)
    matchingCount.value = 0
  } finally {
    matchingLoading.value = false
  }
}

const goToMatchedOrders = () => {
  if (!form.value.activityType || !form.value.campus) return

  uni.setStorageSync('orderListFilter', {
    mode: 'all',
    activityType: form.value.activityType,
    campus: form.value.campus,
    status: 'PENDING'
  })
  uni.switchTab({ url: '/pages/order/list' })
}

const handleCancel = () => {
  uni.navigateBack()
}

const validateForm = () => {
  if (!form.value.activityType) return '请选择活动类型'
  if (!form.value.genderRequire) return '请选择性别要求'
  if (!form.value.campus) return '请选择校区'
  if (!form.value.location.trim()) return '请输入活动地点'
  if (!form.value.startTime) return '请选择开始时间'

  const maxPeople = Number(form.value.maxPeople)
  if (!Number.isInteger(maxPeople) || maxPeople < 1 || maxPeople > 20) {
    return '人数上限应在 1-20 之间'
  }

  const startTime = new Date(form.value.startTime.replace(' ', 'T'))
  if (Number.isNaN(startTime.getTime())) return '开始时间格式不正确'
  if (startTime.getTime() <= Date.now()) return '开始时间必须晚于当前时间'

  if (form.value.note.length > 200) return '备注不能超过 200 个字'
  return ''
}

const handleSubmit = async () => {
  if (!store.getters['user/isLogin']) {
    showError('请先登录')
    uni.navigateTo({ url: '/pages/auth/login' })
    return
  }

  const error = validateForm()
  if (error) {
    showError(error)
    return
  }

  loading.value = true
  showLoading('发布中...')

  try {
    const payload = {
      activityType: form.value.activityType,
      genderRequire: form.value.genderRequire,
      campus: form.value.campus,
      location: form.value.location.trim(),
      startTime: form.value.startTime,
      note: form.value.note,
      maxPeople: Number(form.value.maxPeople)
    }
    const orderId = await orderApi.createOrder(payload)
    hideLoading()
    showSuccess('发布成功')

    setTimeout(() => {
      if (orderId) {
        uni.redirectTo({ url: `/pages/order/detail?id=${orderId}` })
      } else {
        uni.switchTab({ url: '/pages/order/list' })
      }
    }, 700)
  } catch (error) {
    hideLoading()
    showError(error.message || '发布失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.create-order-container {
  min-height: 100vh;
  background:
    radial-gradient(circle at 16% 0%, rgba(78, 161, 255, 0.16), transparent 34%),
    radial-gradient(circle at 92% 6%, rgba(24, 196, 214, 0.10), transparent 30%),
    linear-gradient(180deg, #f7fbff 0%, #eef4fb 50%, #f8fbff 100%);
  padding: 32rpx 28rpx 148rpx;
  box-sizing: border-box;
}

.header-block {
  margin-bottom: 28rpx;
  padding: 32rpx;
  border-radius: 32rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.74);
  background:
    linear-gradient(145deg, rgba(255, 255, 255, 0.92), rgba(238, 248, 255, 0.72));
  box-shadow:
    0 18rpx 38rpx rgba(22, 47, 84, 0.10),
    inset 0 1rpx 0 rgba(255, 255, 255, 0.92);
}

.page-title {
  display: block;
  font-size: 42rpx;
  font-weight: 800;
  color: #172033;
  line-height: 1.2;
}

.page-subtitle {
  display: block;
  margin-top: 12rpx;
  font-size: 26rpx;
  color: #667085;
  line-height: 1.5;
}

.form-panel {
  background:
    linear-gradient(145deg, rgba(255, 255, 255, 0.94), rgba(244, 250, 255, 0.74));
  border: 1rpx solid rgba(255, 255, 255, 0.74);
  border-radius: 32rpx;
  padding: 28rpx;
  box-shadow:
    0 18rpx 38rpx rgba(22, 47, 84, 0.10),
    inset 0 1rpx 0 rgba(255, 255, 255, 0.92);
  -webkit-backdrop-filter: blur(24rpx) saturate(1.24);
  backdrop-filter: blur(24rpx) saturate(1.24);
}

.form-item {
  margin-bottom: 32rpx;
}

.form-item:last-child {
  margin-bottom: 0;
}

.label {
  display: block;
  margin-bottom: 14rpx;
  font-size: 27rpx;
  font-weight: 700;
  color: #263244;
}

.input,
.textarea,
.picker-view {
  width: 100%;
  box-sizing: border-box;
  border: 1rpx solid rgba(217, 229, 243, 0.92);
  border-radius: 22rpx;
  background: rgba(255, 255, 255, 0.68);
  color: #1f2937;
  font-size: 28rpx;
}

.input {
  height: 88rpx;
  padding: 0 24rpx;
}

.textarea {
  min-height: 180rpx;
  padding: 22rpx 24rpx;
  line-height: 1.6;
}

.picker-view {
  min-height: 88rpx;
  padding: 0 24rpx;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.picker-view.compact {
  justify-content: center;
}

.picker-text {
  color: #1f2937;
}

.placeholder {
  color: #98a2b3;
}

.chevron {
  width: 16rpx;
  height: 16rpx;
  border-right: 3rpx solid #98a2b3;
  border-bottom: 3rpx solid #98a2b3;
  transform: rotate(45deg);
}

.segmented {
  display: flex;
  padding: 6rpx;
  border-radius: 22rpx;
  background: rgba(238, 246, 255, 0.78);
  gap: 6rpx;
}

.segment-item {
  flex: 1;
  height: 72rpx;
  line-height: 72rpx;
  text-align: center;
  border-radius: 18rpx;
  color: #667085;
  font-size: 26rpx;
}

.segment-item.active {
  background: #ffffff;
  color: #1d4ed8;
  font-weight: 700;
  box-shadow: 0 4rpx 12rpx rgba(29, 78, 216, 0.14);
}

.matching-hint {
  margin-top: 14rpx;
  padding: 18rpx 20rpx;
  display: flex;
  align-items: center;
  gap: 14rpx;
  border-radius: 22rpx;
  background: rgba(239, 246, 255, 0.86);
  border: 1rpx solid rgba(191, 216, 247, 0.70);
  color: #1d4ed8;
  font-size: 25rpx;
}

.hint-icon {
  width: 32rpx;
  height: 32rpx;
  flex: 0 0 32rpx;
}

.search-icon {
  position: relative;
  border: 3rpx solid #1d4ed8;
  border-radius: 50%;
  box-sizing: border-box;
}

.search-icon::after {
  content: "";
  position: absolute;
  width: 14rpx;
  height: 3rpx;
  right: -9rpx;
  bottom: -5rpx;
  background: #1d4ed8;
  border-radius: 999rpx;
  transform: rotate(45deg);
}

.time-row,
.stepper-row {
  display: flex;
  align-items: center;
  gap: 16rpx;
}

.time-picker {
  flex: 1;
}

.stepper-btn {
  width: 86rpx;
  height: 86rpx;
  line-height: 86rpx;
  padding: 0;
  border-radius: 24rpx;
  border: 1rpx solid rgba(217, 229, 243, 0.92);
  background: rgba(255, 255, 255, 0.74);
  color: #1f447a;
  font-size: 36rpx;
}

.stepper-btn[disabled] {
  color: #c2cad6;
  background: #f3f5f8;
}

.number-input {
  flex: 1;
  text-align: center;
}

.field-tip,
.counter {
  display: block;
  margin-top: 10rpx;
  color: #8a94a6;
  font-size: 23rpx;
}

.counter {
  text-align: right;
}

.bottom-actions {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  padding: 18rpx 28rpx calc(18rpx + env(safe-area-inset-bottom));
  display: flex;
  gap: 18rpx;
  background: rgba(248, 251, 255, 0.86);
  border-top: 1rpx solid rgba(255, 255, 255, 0.74);
  box-shadow: 0 -12rpx 30rpx rgba(17, 24, 39, 0.08);
  -webkit-backdrop-filter: blur(24rpx) saturate(1.25);
  backdrop-filter: blur(24rpx) saturate(1.25);
}

.ghost-btn,
.submit-btn {
  flex: 1;
  height: 86rpx;
  line-height: 86rpx;
  border-radius: 26rpx;
  font-size: 29rpx;
  font-weight: 700;
  border: none;
  padding: 0;
}

.ghost-btn {
  background: rgba(238, 246, 255, 0.86);
  color: #475467;
}

.submit-btn {
  background: linear-gradient(135deg, #2f7ed8, #1f447a);
  color: #ffffff;
  box-shadow: 0 14rpx 28rpx rgba(31, 68, 122, 0.20);
}
</style>
