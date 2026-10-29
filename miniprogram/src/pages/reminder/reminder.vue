<template>
  <view class="rem-page">
    <!-- 筛选 -->
    <view class="seg">
      <view
        v-for="t in tabs"
        :key="t.value"
        class="seg-item"
        :class="{ active: tab === t.value }"
        @click="switchTab(t.value)"
      >
        {{ t.label }}
      </view>
    </view>

    <!-- 列表 -->
    <scroll-view class="list" scroll-y>
      <view v-if="loading" class="empty">加载中…</view>
      <view v-else-if="items.length === 0" class="empty">暂无提醒,点下方按钮创建一个吧</view>
      <view v-for="r in items" :key="r.reminder_id" class="rem-card" :class="{ 'rem-done': r.status !== 'scheduled' }">
        <view class="rem-icon">⏰</view>
        <view class="rem-main">
          <view class="rem-title-row">
            <text class="rem-title">{{ r.title }}</text>
            <text class="badge" :class="statusBadge(r.status)">{{ statusText(r.status) }}</text>
          </view>
          <text class="rem-time">下次提醒:{{ fmtDateTime(r.next_run_at) }}</text>
        </view>
        <view v-if="r.status === 'scheduled'" class="rem-cancel" @click="confirmCancel(r)">取消</view>
      </view>
      <view style="height: 90px"></view>
    </scroll-view>

    <!-- 新建 -->
    <view class="bottom-bar">
      <button class="btn btn-primary new-btn" @click="openForm">+ 新建提醒</button>
    </view>

    <!-- 新建弹窗 -->
    <view v-if="showForm">
      <view class="mask" @click="showForm = false"></view>
      <view class="sheet">
        <text class="sheet-title">新建提醒</text>
        <text class="field-label">提醒内容</text>
        <input class="field-input" v-model="form.title" placeholder="如:测空腹血糖" maxlength="50" />
        <text class="field-label">提醒日期</text>
        <picker mode="date" :value="form.date" @change="form.date = $event.detail.value">
          <view class="field-input">{{ form.date }}</view>
        </picker>
        <text class="field-label">提醒时间</text>
        <picker mode="time" :value="form.time" @change="form.time = $event.detail.value">
          <view class="field-input">{{ form.time }}</view>
        </picker>
        <view class="sheet-btns">
          <button class="btn btn-plain sheet-btn" @click="showForm = false">取消</button>
          <button class="btn btn-primary sheet-btn" :disabled="saving" @click="submit">保存</button>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { listReminders, createReminder, cancelReminder } from '../../api/reminder.js'
import { errMsg, fmtDateTime } from '../../utils/request.js'

const tabs = [
  { label: '待提醒', value: 'scheduled' },
  { label: '已发送', value: 'sent' },
  { label: '已取消', value: 'cancelled' },
  { label: '全部', value: 'all' },
]

const tab = ref('scheduled')
const items = ref([])
const loading = ref(true)
const showForm = ref(false)
const saving = ref(false)
const form = ref({ title: '', date: '', time: '' })

const statusText = (s) => ({ scheduled: '待提醒', sent: '已发送', cancelled: '已取消' }[s] || s)
const statusBadge = (s) => ({ scheduled: 'badge-green', sent: 'badge-gray', cancelled: 'badge-red' }[s] || 'badge-gray')

const load = async () => {
  loading.value = true
  try {
    items.value = await listReminders(tab.value)
  } catch (e) {
    uni.showToast({ title: errMsg(e), icon: 'none' })
  } finally {
    loading.value = false
  }
}

const switchTab = (v) => {
  tab.value = v
  load()
}

const openForm = () => {
  const d = new Date()
  const p = (n) => String(n).padStart(2, '0')
  form.value = {
    title: '',
    date: `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`,
    time: `${p(d.getHours() + 1)}:00`,
  }
  showForm.value = true
}

const submit = async () => {
  if (!form.value.title.trim()) return uni.showToast({ title: '请填写提醒内容', icon: 'none' })
  saving.value = true
  try {
    await createReminder({
      title: form.value.title.trim(),
      schedule_rule: { time: form.value.time, date: form.value.date },
      timezone: 'Asia/Shanghai',
      channel: 'in_app',
    })
    showForm.value = false
    uni.showToast({ title: '提醒已创建', icon: 'success' })
    if (tab.value !== 'scheduled' && tab.value !== 'all') tab.value = 'scheduled'
    load()
  } catch (e) {
    uni.showToast({ title: errMsg(e), icon: 'none' })
  } finally {
    saving.value = false
  }
}

const confirmCancel = (r) => {
  uni.showModal({
    title: '取消提醒',
    content: `确定取消「${r.title}」吗?`,
    confirmText: '取消提醒',
    confirmColor: '#E53E3E',
    success: async (res) => {
      if (res.confirm) {
        try {
          await cancelReminder(r.reminder_id)
          uni.showToast({ title: '已取消', icon: 'none' })
          load()
        } catch (e) {
          uni.showToast({ title: errMsg(e), icon: 'none' })
        }
      }
    },
  })
}

onMounted(load)
</script>

<style scoped>
.rem-page {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}
.list {
  flex: 1;
  overflow: hidden;
}
.rem-card {
  display: flex;
  align-items: center;
  gap: 12px;
  background: #ffffff;
  border-radius: 12px;
  margin: 10px 16px 0;
  padding: 14px 16px;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.05);
}
.rem-done {
  opacity: 0.65;
}
.rem-icon {
  width: 42px;
  height: 42px;
  line-height: 42px;
  text-align: center;
  background: #ebf4fb;
  border-radius: 12px;
  font-size: 20px;
  flex-shrink: 0;
}
.rem-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.rem-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.rem-title {
  font-size: 16px;
  font-weight: 600;
}
.rem-time {
  font-size: 13px;
  color: #64748b;
}
.rem-cancel {
  font-size: 14px;
  color: #e53e3e;
  border: 1px solid #feb2b2;
  border-radius: 8px;
  padding: 4px 10px;
  flex-shrink: 0;
}
.bottom-bar {
  padding: 12px 16px;
  background: #ffffff;
  border-top: 1px solid #e2e8f0;
}
.new-btn {
  height: 44px;
  line-height: 44px;
  font-size: 16px;
}
.sheet-title {
  font-size: 17px;
  font-weight: 600;
  display: block;
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
