<template>
  <view class="plan-page">
    <!-- 状态切换 -->
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
      <view v-else-if="items.length === 0" class="empty">
        {{ tab === 'draft' ? '暂无待确认的计划。去对话页让助手为你生成一个吧' : tab === 'confirmed' ? '暂无进行中的计划' : '暂无历史计划' }}
      </view>

      <view v-for="p in items" :key="p.plan_id" class="card plan-card" @click="openDetail(p)">
        <view class="plan-head">
          <text class="plan-summary">{{ p.summary || p.title || '健康计划' }}</text>
          <text class="badge" :class="badgeClass(p.status)">{{ badgeText(p.status) }}</text>
        </view>
        <text class="plan-date">创建于 {{ (p.created_at || '').slice(0, 10) }} · 版本 {{ p.revision }}</text>

        <!-- 计划项预览 -->
        <view class="plan-items-preview">
          <view v-for="(it, i) in (p.items || []).slice(0, 3)" :key="i" class="preview-item">
            <text class="preview-dot"></text>
            <text class="preview-text">{{ it.content }}</text>
          </view>
          <text v-if="(p.items || []).length > 3" class="preview-more">…共 {{ p.items.length }} 项</text>
        </view>

        <!-- 草稿:引导去对话页确认 -->
        <view v-if="p.status === 'draft'" class="draft-hint">
          <text class="draft-hint-text">草稿需在对话页完成确认</text>
          <button class="btn btn-primary draft-btn" @click.stop="goChat">去对话确认</button>
        </view>

        <view v-if="p.status === 'confirmed' || p.status === 'active'" class="plan-foot">
          <text class="foot-link" @click.stop="confirmArchive(p)">归档</text>
          <text class="foot-arrow">详情 ›</text>
        </view>
      </view>
    </scroll-view>
  </view>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { listPlans, archivePlan } from '../../api/plan.js'
import { errMsg } from '../../utils/request.js'

const tabs = [
  { label: '待确认', value: 'draft' },
  { label: '进行中', value: 'confirmed' },
  { label: '历史', value: 'archived' },
]

const tab = ref('draft')
const items = ref([])
const allPlans = ref([])
const loading = ref(true)

const badgeText = (s) => ({ draft: '待确认', confirmed: '进行中', active: '进行中', archived: '已归档', rejected: '已拒绝' }[s] || s)
const badgeClass = (s) =>
  ({ draft: 'badge-orange', confirmed: 'badge-green', active: 'badge-green', archived: 'badge-gray', rejected: 'badge-gray' }[s] || 'badge-gray')

const load = async () => {
  loading.value = true
  try {
    allPlans.value = await listPlans('')
    applyFilter()
  } catch (e) {
    uni.showToast({ title: errMsg(e), icon: 'none' })
  } finally {
    loading.value = false
  }
}

const applyFilter = () => {
  if (tab.value === 'confirmed') {
    items.value = allPlans.value.filter((p) => p.status === 'confirmed' || p.status === 'active')
  } else {
    items.value = allPlans.value.filter((p) => p.status === tab.value)
  }
}

const switchTab = (v) => {
  tab.value = v
  if (allPlans.value.length || loading.value) applyFilter()
  else load()
}

const openDetail = (p) => {
  uni.navigateTo({ url: `/pages/plan-detail/plan-detail?plan_id=${p.plan_id}` })
}

const goChat = () => {
  uni.switchTab({ url: '/pages/index/index' })
}

const confirmArchive = (p) => {
  uni.showModal({
    title: '归档计划',
    content: `确定归档「${p.summary || p.title}」吗?归档后不可恢复。`,
    confirmText: '归档',
    confirmColor: '#DD6B20',
    success: async (res) => {
      if (res.confirm) {
        try {
          await archivePlan(p.plan_id)
          uni.showToast({ title: '已归档', icon: 'none' })
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
.plan-page {
  position: fixed;
  left: 0;
  right: 0;
  top: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
}
/* #ifdef H5 */
.plan-page {
  top: 44px;
  bottom: 50px;
}
/* #endif */

.list {
  flex: 1;
  overflow: hidden;
}
.plan-card {
  margin-top: 4px;
}
.plan-head {
  display: flex;
  align-items: center;
  gap: 8px;
}
.plan-summary {
  font-size: 17px;
  font-weight: 600;
  flex: 1;
}
.plan-date {
  display: block;
  font-size: 13px;
  color: #94a3b8;
  margin-top: 4px;
}
.plan-items-preview {
  margin-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.preview-item {
  display: flex;
  gap: 8px;
  align-items: flex-start;
}
.preview-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #2b6cb0;
  margin-top: 8px;
  flex-shrink: 0;
}
.preview-text {
  font-size: 15px;
  color: #334155;
}
.preview-more {
  font-size: 13px;
  color: #94a3b8;
}
.draft-hint {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fffaf0;
  border-radius: 10px;
  padding: 10px 12px;
  margin-top: 12px;
}
.draft-hint-text {
  font-size: 14px;
  color: #dd6b20;
}
.draft-btn {
  height: 36px;
  line-height: 36px;
  font-size: 14px;
  padding: 0 16px;
}
.plan-foot {
  display: flex;
  justify-content: space-between;
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px solid #f1f5f9;
}
.foot-link {
  font-size: 14px;
  color: #dd6b20;
}
.foot-arrow {
  font-size: 14px;
  color: #94a3b8;
}
</style>
