<template>
  <view class="detail-page">
    <view v-if="loading" class="empty">加载中…</view>
    <template v-else-if="plan">
      <view class="card">
        <view class="plan-head">
          <text class="plan-summary">{{ plan.summary || plan.title || '健康计划' }}</text>
          <text class="badge" :class="badgeClass">{{ badgeText }}</text>
        </view>
        <text class="plan-date">创建于 {{ (plan.created_at || '').slice(0, 10) }} · 版本 {{ plan.revision }}</text>
      </view>

      <view class="card">
        <text class="items-title">计划项时间轴</text>
        <view v-if="(plan.items || []).length === 0" class="empty">暂无计划项</view>
        <view class="timeline">
          <view v-for="(it, i) in plan.items || []" :key="it.item_id || i" class="tl-item">
            <view class="tl-rail">
              <view class="tl-dot" :class="plan.status === 'archived' ? 'tl-dot-done' : ''">{{ i + 1 }}</view>
              <view v-if="i < plan.items.length - 1" class="tl-line"></view>
            </view>
            <view class="tl-body">
              <text class="tl-content">{{ it.content }}</text>
              <text v-if="scheduleText(it)" class="tl-time">⏰ {{ scheduleText(it) }}</text>
            </view>
          </view>
        </view>
      </view>

      <view v-if="plan.status === 'draft'" class="draft-tip card">
        <text class="draft-tip-text">该计划为草稿,请在对话页完成确认。</text>
        <button class="btn btn-primary draft-tip-btn" @click="goChat">去对话确认</button>
      </view>
      <view v-else-if="plan.status === 'confirmed' || plan.status === 'active'" class="archive-bar">
        <button class="btn btn-danger archive-btn" @click="confirmArchive">归档此计划</button>
      </view>
    </template>
    <view v-else class="empty">计划不存在或已删除</view>
  </view>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { listPlans, archivePlan } from '../../api/plan.js'
import { errMsg } from '../../utils/request.js'

const loading = ref(true)
const plan = ref(null)

const badgeText = computed(() =>
  ({ draft: '待确认', confirmed: '进行中', active: '进行中', archived: '已归档', rejected: '已拒绝' }[plan.value.status] || '')
)
const badgeClass = computed(
  () =>
    ({ draft: 'badge-orange', confirmed: 'badge-green', active: 'badge-green', archived: 'badge-gray', rejected: 'badge-gray' }[plan.value.status] || 'badge-gray')
)

const scheduleText = (item) => {
  const s = item.schedule_rule || {}
  if (typeof s === 'string') return s
  if (s.time && s.date) return `${s.date} ${s.time}`
  if (s.time) return `每天 ${s.time}`
  if (s.date) return s.date
  return ''
}

const goChat = () => uni.switchTab({ url: '/pages/index/index' })

const confirmArchive = () => {
  uni.showModal({
    title: '归档计划',
    content: '归档后计划不可恢复,确定吗?',
    confirmText: '归档',
    confirmColor: '#DD6B20',
    success: async (res) => {
      if (res.confirm) {
        try {
          await archivePlan(plan.value.plan_id)
          uni.showToast({ title: '已归档', icon: 'none' })
          setTimeout(() => uni.navigateBack(), 500)
        } catch (e) {
          uni.showToast({ title: errMsg(e), icon: 'none' })
        }
      }
    },
  })
}

onMounted(async () => {
  const pages = getCurrentPages()
  const current = pages[pages.length - 1]
  const opts = (current && current.$page && current.$page.options) || {}
  try {
    const plans = await listPlans('')
    plan.value = (plans || []).find((p) => p.plan_id === opts.plan_id) || null
  } catch (e) {
    uni.showToast({ title: errMsg(e), icon: 'none' })
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.detail-page {
  min-height: 100vh;
  padding-bottom: 24px;
}
.plan-head {
  display: flex;
  align-items: center;
  gap: 8px;
}
.plan-summary {
  font-size: 18px;
  font-weight: 600;
  flex: 1;
}
.plan-date {
  display: block;
  font-size: 13px;
  color: #94a3b8;
  margin-top: 4px;
}
.items-title {
  font-size: 16px;
  font-weight: 600;
  display: block;
  margin-bottom: 12px;
}
.timeline {
  display: flex;
  flex-direction: column;
}
.tl-item {
  display: flex;
  gap: 12px;
}
.tl-rail {
  display: flex;
  flex-direction: column;
  align-items: center;
}
.tl-dot {
  width: 26px;
  height: 26px;
  line-height: 26px;
  text-align: center;
  background: #ebf4fb;
  color: #2b6cb0;
  border-radius: 50%;
  font-size: 13px;
  font-weight: 600;
  flex-shrink: 0;
}
.tl-dot-done {
  background: #f0fff4;
  color: #38a169;
}
.tl-line {
  width: 2px;
  flex: 1;
  background: #e2e8f0;
  margin: 4px 0;
}
.tl-body {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding-bottom: 18px;
  flex: 1;
}
.tl-content {
  font-size: 16px;
  color: #1a202c;
}
.tl-time {
  font-size: 13px;
  color: #dd6b20;
}
.draft-tip {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.draft-tip-text {
  font-size: 14px;
  color: #dd6b20;
}
.draft-tip-btn {
  height: 44px;
  line-height: 44px;
  font-size: 16px;
}
.archive-bar {
  padding: 0 16px;
}
.archive-btn {
  height: 44px;
  line-height: 44px;
  font-size: 16px;
}
</style>
