<template>
  <view class="login-page">
    <view class="hero">
      <view class="logo">康</view>
      <text class="app-name">慢性病管理助手</text>
      <text class="slogan">对话式记录 · 智能建议 · 健康计划 · 用药提醒</text>
    </view>

    <view class="login-box">
      <!-- #ifdef H5 -->
      <input
        v-model="devNickname"
        class="dev-input"
        placeholder="测试昵称(不同昵称 = 不同账号)"
        :disabled="loading"
      />
      <!-- #endif -->
      <button class="btn btn-primary login-btn" :disabled="loading" @click="doLogin">
        {{ loading ? '登录中…' : '微信一键登录' }}
      </button>
      <text v-if="devModeTip" class="mock-tip">{{ devModeTip }}</text>
    </view>

    <view class="disclaimer">
      <text>本应用提供的健康管理建议不替代医生诊断与治疗。</text>
      <text>如有不适,请及时前往医院就诊。</text>
    </view>
  </view>
</template>

<script setup>
import { ref } from 'vue'
import { wechatLogin, getUserInfo } from '../../api/auth.js'
import { errMsg } from '../../utils/request.js'

const loading = ref(false)
// #ifdef H5
const devModeTip = ref('开发模式:输入昵称模拟不同微信账号')
const devNickname = ref(uni.getStorageSync('dev_nickname') || import.meta.env.VITE_DEV_LOGIN_CODE || 'dev-alice')
// #endif
// #ifndef H5
const devModeTip = ref('')
// #endif

const doLogin = async () => {
  if (loading.value) return
  loading.value = true
  try {
    let code = ''
    // #ifdef MP-WEIXIN
    code = await new Promise((resolve, reject) =>
      uni.login({ success: (r) => resolve(r.code || ''), fail: reject })
    )
    // #endif
    // #ifndef MP-WEIXIN
    const nickname = (devNickname.value || '').trim() || 'dev-alice'
    uni.setStorageSync('dev_nickname', nickname)
    code = 'dev-' + nickname
    // #endif
    if (!code) throw new Error('获取微信登录凭证失败')

    const res = await wechatLogin(code)
    uni.setStorageSync('token', res.access_token)
    try {
      const info = await getUserInfo()
      uni.setStorageSync('user_id', info.user_id || '')
    } catch (e) {
      /* userinfo 失败不阻断登录 */
    }
    uni.showToast({ title: '登录成功', icon: 'success' })
    setTimeout(() => uni.switchTab({ url: '/pages/index/index' }), 400)
  } catch (e) {
    uni.showToast({ title: errMsg(e), icon: 'none' })
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: space-between;
  background: linear-gradient(180deg, #e8f1fa 0%, #f5f7fa 55%);
  padding: 0 32px;
}
.hero {
  margin-top: 22vh;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.logo {
  width: 88px;
  height: 88px;
  line-height: 88px;
  text-align: center;
  background: #2b6cb0;
  color: #ffffff;
  font-size: 28px;
  font-weight: 700;
  border-radius: 24px;
  box-shadow: 0 6px 16px rgba(43, 108, 176, 0.3);
}
.app-name {
  margin-top: 20px;
  font-size: 20px;
  font-weight: 600;
  color: #1a202c;
}
.slogan {
  margin-top: 8px;
  font-size: 14px;
  color: #64748b;
}
.login-box {
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-bottom: 4vh;
}
.login-btn {
  width: 100%;
  height: 48px;
  line-height: 48px;
  font-size: 17px;
}
.dev-input {
  width: 100%;
  height: 44px;
  line-height: 44px;
  margin-bottom: 16px;
  padding: 0 16px;
  box-sizing: border-box;
  background: #ffffff;
  border: 1px solid #d8e2ee;
  border-radius: 10px;
  font-size: 15px;
  color: #1a202c;
  text-align: center;
}
.mock-tip {
  margin-top: 12px;
  font-size: 13px;
  color: #94a3b8;
}
.disclaimer {
  display: flex;
  flex-direction: column;
  align-items: center;
  font-size: 12px;
  color: #94a3b8;
  line-height: 1.7;
  margin-bottom: 24px;
}
</style>
