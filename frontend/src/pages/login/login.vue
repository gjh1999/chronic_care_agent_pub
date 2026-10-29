<template><view class="page"><view class="card"><view class="title">慢病管理助手</view><view class="muted">记录、建议、计划与提醒</view><button class="primary" @click="login">微信一键登录</button></view></view></template>
<script setup>
import { api } from '../../api'
async function login() {
  try {
    let code
    // #ifdef H5
    // H5 不支持 uni.login 静默登录(需微信网页 OAuth),开发环境直接用 dev code 走后端开发登录
    code = import.meta.env.VITE_DEV_LOGIN_CODE || 'dev-alice'
    // #endif
    // #ifndef H5
    const result = await new Promise((resolve, reject) => uni.login({ provider: 'weixin', success: resolve, fail: reject }))
    code = result.code
    // #endif
    const data = await api.login(code)
    uni.setStorageSync('access_token', data.access_token)
    uni.reLaunch({ url: '/pages/index/index' })
  } catch (e) {
    uni.showToast({ title: e.message || '登录失败', icon: 'none' })
  }
}
</script>
<style scoped>.title{font-size:44rpx;font-weight:700;margin-bottom:12rpx}.card{margin-top:180rpx}button{margin-top:40rpx}</style>
