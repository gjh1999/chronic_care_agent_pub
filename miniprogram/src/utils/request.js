// 统一请求封装:契约 {code, data, message, request_id},code===0 成功。
// 40002(认证失败)→ 清 token 跳登录;写操作自动携带 Idempotency-Key。
// 真机调试时把 BASE_URL 改成局域网 IP。

export const BASE_URL = 'http://127.0.0.1:8000/api/v1'

export const getToken = () => uni.getStorageSync('token') || ''

const genIdempotencyKey = () =>
  `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`

export function request({ url, method = 'GET', data, header = {}, timeout = 30000, idempotent = false }) {
  return new Promise((resolve, reject) => {
    const headers = { 'Content-Type': 'application/json', ...header }
    const token = getToken()
    if (token) headers.Authorization = `Bearer ${token}`
    if (idempotent) headers['Idempotency-Key'] = genIdempotencyKey()

    uni.request({
      url: BASE_URL + url,
      method,
      data,
      header: headers,
      timeout,
      success: (res) => {
        const body = res.data || {}
        if (res.statusCode >= 200 && res.statusCode < 300 && body.code === 0) {
          resolve(body.data)
          return
        }
        if (body.code === 40002) {
          uni.removeStorageSync('token')
          uni.removeStorageSync('user_id')
          uni.reLaunch({ url: '/pages/login/login' })
          reject(new Error(body.message || '登录已失效,请重新登录'))
          return
        }
        const err = new Error(body.message || `请求失败(${res.statusCode})`)
        err.code = body.code
        err.httpStatus = res.statusCode
        err.requestId = body.request_id
        reject(err)
      },
      fail: (e) => {
        const err = new Error('网络异常,请检查网络连接')
        err.isNetwork = true
        err.errMsg = e.errMsg
        reject(err)
      },
    })
  })
}

export const get = (url, opts = {}) => request({ url, method: 'GET', ...opts })
export const post = (url, data, opts = {}) => request({ url, method: 'POST', data, ...opts })
export const put = (url, data, opts = {}) => request({ url, method: 'PUT', data, ...opts })
export const del = (url, opts = {}) => request({ url, method: 'DELETE', ...opts })

export const errMsg = (e) => (e && e.message ? e.message : '操作失败,请稍后重试')

// ISO 时间转展示文本:带时区的(服务端 UTC)转中国 +8;无时区的按本地时间原样展示
export const fmtDateTime = (iso) => {
  if (!iso) return ''
  const s = String(iso)
  const hasTz = /Z$|[+-]\d{2}:\d{2}$/.test(s)
  const d = new Date(s)
  if (Number.isNaN(d.getTime())) return s
  const p = (n) => String(n).padStart(2, '0')
  if (!hasTz) {
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
  }
  const dt = new Date(d.getTime() + 8 * 3600 * 1000) // 固定 +8(中国无夏令时)
  return `${dt.getUTCFullYear()}-${p(dt.getUTCMonth() + 1)}-${p(dt.getUTCDate())} ${p(dt.getUTCHours())}:${p(dt.getUTCMinutes())}`
}

// 客户端本地时间 → ISO 文本(不带时区,后端按用户本地语义存储)
export const nowLocalISO = () => {
  const d = new Date()
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
}
