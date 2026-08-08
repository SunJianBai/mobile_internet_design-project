function getLocalIP() {
  // #ifdef H5
  return 'localhost'
  // #endif
  
  // #ifndef H5
  const savedIP = uni.getStorageSync('apiServerIP')
  if (savedIP) {
    return savedIP
  }
  return '10.0.2.2'
  // #endif
}

const localIP = getLocalIP()
// Production mode uses the public server entry point mounted under /CampusHub.
const prodOrigin = 'https://sun227454.online/CampusHub'

const devConfig = {
  baseURL: `http://${localIP}:8080/api/v1`,
  fileBaseURL: `http://${localIP}:8080`,
  debug: true
}

const prodConfig = {
  baseURL: `${prodOrigin}/api/v1`,
  fileBaseURL: prodOrigin,
  debug: false
}

// 环境判断：可以通过 uni.getStorageSync('env') 来切换环境
// 'dev' = 开发环境, 'prod' = 生产环境, 其他或不设置 = 自动判断
const envMode = uni.getStorageSync('env') || 'auto'

let isDev
// #ifdef H5
const h5Host = typeof window !== 'undefined' ? window.location.hostname : ''
const isLocalH5 = ['localhost', '127.0.0.1', '::1'].includes(h5Host)
// H5 本地 dev server 默认连本地后端，线上 H5 默认连公网入口；可用 env 强制切换。
isDev = envMode === 'dev' || (envMode === 'auto' && isLocalH5)
// #endif

// #ifndef H5
// 非H5环境（App）：默认使用生产环境，可通过 env 配置切换
isDev = envMode === 'dev' ? true : false
// #endif

const config = isDev ? devConfig : prodConfig

export default config
