const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api/v1'

export function request({ url, method = 'GET', data, headers = {} }) {
  const token = uni.getStorageSync('access_token')
  return new Promise((resolve, reject) => {
    uni.request({
      url: `${baseURL}${url}`,
      method,
      data,
      header: { ...headers, ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      success(response) {
        if (response.statusCode === 401 || response.data?.code === 40002) {
          uni.removeStorageSync('access_token')
          uni.reLaunch({ url: '/pages/login/login' })
          return reject(new Error('登录已失效'))
        }
        if (response.statusCode >= 400 || response.data?.code !== 0) {
          const message = response.data?.message || '请求失败'
          uni.showToast({ title: message, icon: 'none' })
          return reject(new Error(message))
        }
        resolve(response.data.data)
      },
      fail: reject
    })
  })
}
