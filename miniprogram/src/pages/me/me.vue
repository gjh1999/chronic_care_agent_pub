<template>
  <view class="me-page">
    <!-- 资料卡 -->
    <view class="card profile-card">
      <view class="avatar-big">我</view>
      <view class="profile-main">
        <view class="profile-tags">
          <text v-for="t in profile.disease_tags || []" :key="t" class="badge badge-blue">{{ t }}</text>
          <text v-if="!(profile.disease_tags || []).length" class="badge badge-gray">未设置慢病标签</text>
        </view>
        <text class="profile-meta">{{ profile.gender || '性别未设置' }} · {{ profile.birth_date || '出生日期未设置' }}</text>
        <text class="profile-meta">用户 {{ (profile.user_id || '').slice(0, 8) }}</text>
      </view>
      <view class="edit-btn" @click="openEdit">编辑</view>
    </view>

    <!-- 功能入口 -->
    <view class="card menu">
      <view class="menu-item" @click="goReminder">
        <text class="menu-icon">⏰</text>
        <text class="menu-text">提醒管理</text>
        <text class="menu-arrow">›</text>
      </view>
      <view class="menu-item" @click="goStats">
        <text class="menu-icon">📈</text>
        <text class="menu-text">趋势统计</text>
        <text class="menu-arrow">›</text>
      </view>
    </view>

    <!-- 免责声明 -->
    <view class="card disclaim">
      <text class="disclaim-title">免责声明</text>
      <text class="disclaim-text">
        本应用提供的健康管理建议由 AI 生成,仅供日常管理参考,不替代医生诊断与治疗。如有不适,请及时前往医院就诊。
      </text>
    </view>

    <!-- 退出登录 -->
    <view class="logout-bar">
      <button class="btn btn-danger logout-btn" @click="logout">退出登录</button>
    </view>

    <!-- 编辑弹窗 -->
    <view v-if="showEdit">
      <view class="mask" @click="showEdit = false"></view>
      <view class="sheet">
        <text class="sheet-title">编辑资料</text>
        <text class="field-label">性别</text>
        <picker :range="genders" @change="editForm.gender = genders[$event.detail.value]">
          <view class="field-input">{{ editForm.gender || '请选择' }}</view>
        </picker>
        <text class="field-label">出生日期</text>
        <picker mode="date" :value="editForm.birth_date || ''" @change="editForm.birth_date = $event.detail.value">
          <view class="field-input">{{ editForm.birth_date || '请选择' }}</view>
        </picker>
        <text class="field-label">慢病标签</text>
        <view class="tag-picker">
          <text
            v-for="t in tagOptions"
            :key="t"
            class="tag-option"
            :class="{ 'tag-on': (editForm.disease_tags || []).includes(t) }"
            @click="toggleTag(t)"
          >
            {{ t }}
          </text>
        </view>
        <view class="sheet-btns">
          <button class="btn btn-plain sheet-btn" @click="showEdit = false">取消</button>
          <button class="btn btn-primary sheet-btn" :disabled="saving" @click="saveProfile">保存</button>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getProfile, updateProfile } from '../../api/me.js'
import { logout as apiLogout } from '../../api/auth.js'
import { errMsg } from '../../utils/request.js'

const genders = ['男', '女']
const tagOptions = ['2型糖尿病', '1型糖尿病', '高血压', '高血脂', '冠心病', '脑卒中']

const profile = ref({})
const showEdit = ref(false)
const saving = ref(false)
const editForm = ref({})

const openEdit = () => {
  editForm.value = {
    gender: profile.value.gender || '',
    birth_date: profile.value.birth_date || '',
    disease_tags: [...(profile.value.disease_tags || [])],
  }
  showEdit.value = true
}

const toggleTag = (t) => {
  const tags = editForm.value.disease_tags
  const i = tags.indexOf(t)
  if (i >= 0) tags.splice(i, 1)
  else tags.push(t)
}

const saveProfile = async () => {
  saving.value = true
  try {
    const res = await updateProfile({
      gender: editForm.value.gender || null,
      birth_date: editForm.value.birth_date || null,
      timezone: 'Asia/Shanghai',
      disease_tags: editForm.value.disease_tags,
    })
    profile.value = res
    showEdit.value = false
    uni.showToast({ title: '已保存', icon: 'success' })
  } catch (e) {
    uni.showToast({ title: errMsg(e), icon: 'none' })
  } finally {
    saving.value = false
  }
}

const goReminder = () => uni.navigateTo({ url: '/pages/reminder/reminder' })
const goStats = () =>
  uni.showActionSheet({
    itemList: ['血糖趋势', '血压趋势'],
    success: (res) => {
      const type = res.tapIndex === 0 ? 'blood_glucose' : 'blood_pressure'
      uni.navigateTo({ url: `/pages/stats/stats?metric_type=${type}` })
    },
  })

const logout = () => {
  uni.showModal({
    title: '退出登录',
    content: '确定退出当前账号吗?',
    confirmText: '退出',
    confirmColor: '#E53E3E',
    success: async (res) => {
      if (!res.confirm) return
      try {
        await apiLogout()
      } catch (e) {
        /* 后端登出失败也继续本地清理 */
      }
      uni.removeStorageSync('token')
      uni.removeStorageSync('user_id')
      uni.removeStorageSync('conversation_id')
      uni.reLaunch({ url: '/pages/login/login' })
    },
  })
}

onMounted(async () => {
  try {
    profile.value = await getProfile()
  } catch (e) {
    uni.showToast({ title: errMsg(e), icon: 'none' })
  }
})
</script>

<style scoped>
.me-page {
  position: fixed;
  left: 0;
  right: 0;
  top: 0;
  bottom: 0;
  overflow-y: auto;
  padding-bottom: 24px;
}
/* #ifdef H5 */
.me-page {
  top: 44px;
  bottom: 50px;
}
/* #endif */

.profile-card {
  display: flex;
  align-items: center;
  gap: 14px;
}
.avatar-big {
  width: 60px;
  height: 60px;
  line-height: 60px;
  text-align: center;
  background: #2b6cb0;
  color: #ffffff;
  font-size: 24px;
  font-weight: 600;
  border-radius: 50%;
  flex-shrink: 0;
}
.profile-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.profile-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.badge-blue {
  background: #ebf4fb;
  color: #2b6cb0;
}
.profile-meta {
  font-size: 13px;
  color: #64748b;
}
.edit-btn {
  font-size: 14px;
  color: #2b6cb0;
  border: 1px solid #bee3f8;
  border-radius: 8px;
  padding: 5px 14px;
  flex-shrink: 0;
}

.menu {
  padding: 4px 16px;
}
.menu-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 0;
  border-bottom: 1px solid #f1f5f9;
}
.menu-item:last-child {
  border-bottom: none;
}
.menu-icon {
  font-size: 20px;
}
.menu-text {
  flex: 1;
  font-size: 16px;
}
.menu-arrow {
  font-size: 20px;
  color: #cbd5e1;
}

.disclaim {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.disclaim-title {
  font-size: 15px;
  font-weight: 600;
}
.disclaim-text {
  font-size: 13px;
  color: #64748b;
  line-height: 1.7;
}

.logout-bar {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  margin-top: 8px;
}
.logout-btn {
  width: calc(100% - 32px);
  height: 44px;
  line-height: 44px;
  font-size: 16px;
}

.sheet-title {
  font-size: 17px;
  font-weight: 600;
  display: block;
}
.tag-picker {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 4px;
}
.tag-option {
  font-size: 14px;
  padding: 5px 14px;
  border-radius: 16px;
  background: #f1f5f9;
  color: #64748b;
}
.tag-on {
  background: #ebf4fb;
  color: #2b6cb0;
  border: 1px solid #90cdf4;
}
.sheet-btns {
  display: flex;
  gap: 12px;
  margin-top: 16px;
}
.sheet-btn {
  flex: 1;
  height: 44px;
  line-height: 44px;
  font-size: 16px;
  padding: 0;
}
</style>
