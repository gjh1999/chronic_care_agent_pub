<template>
  <view class="record-page">
    <!-- 筛选 -->
    <view class="seg">
      <view
        v-for="t in filters"
        :key="t.value"
        class="seg-item"
        :class="{ active: filter === t.value }"
        @click="switchFilter(t.value)"
      >
        {{ t.label }}
      </view>
    </view>

    <!-- 列表 -->
    <scroll-view class="list" scroll-y @scrolltolower="loadMore">
      <view v-if="loading" class="empty">加载中…</view>
      <view v-else-if="items.length === 0" class="empty">暂无记录,点右下角 + 添加一条吧</view>
      <view v-for="o in items" :key="o.observation_id" class="rec-card" @longpress="confirmDelete(o)">
        <view class="rec-left">
          <view class="rec-icon" :class="'icon-' + o.metric_type">{{ iconOf(o.metric_type) }}</view>
          <view class="rec-main">
            <view class="rec-value-row">
              <text class="rec-value" :class="isHigh(o) ? 'value-high' : ''">{{ displayValue(o) }}</text>
              <text v-if="o.unit" class="rec-unit">{{ o.unit }}</text>
              <text v-if="o.context" class="badge badge-gray rec-period">{{ o.context }}</text>
              <text v-if="isHigh(o)" class="badge badge-red">偏高</text>
            </view>
            <text class="rec-time">{{ fmtDateTime(o.measured_at) }}</text>
          </view>
        </view>
        <!-- #ifdef H5 -->
        <view class="rec-del" @click.stop="confirmDelete(o)">✕</view>
        <!-- #endif -->
      </view>
      <view v-if="items.length < total" class="load-more">{{ loadingMore ? '加载中…' : '上拉加载更多' }}</view>
      <view style="height: 90px"></view>
    </scroll-view>

    <!-- 底部工具条 -->
    <view class="toolbar">
      <button class="btn btn-plain toolbar-btn" @click="goStats">📈 趋势</button>
      <button class="btn btn-primary toolbar-btn" @click="openForm">+ 添加记录</button>
    </view>

    <!-- 录入弹窗 -->
    <view v-if="showForm">
      <view class="mask" @click="showForm = false"></view>
      <view class="sheet">
        <text class="sheet-title">添加健康记录</text>

        <view class="seg seg-inline">
          <view
            v-for="t in formTypes"
            :key="t.value"
            class="seg-item"
            :class="{ active: formType === t.value }"
            @click="formType = t.value"
          >
            {{ t.label }}
          </view>
        </view>

        <!-- 血糖 -->
        <template v-if="formType === 'blood_glucose'">
          <text class="field-label">血糖值(mmol/L)</text>
          <input class="field-input" type="digit" v-model="form.value" placeholder="如 7.2" />
          <text class="field-label">测量时段</text>
          <picker :range="glucosePeriods" @change="form.period = glucosePeriods[$event.detail.value]">
            <view class="field-input">{{ form.period || '请选择时段' }}</view>
          </picker>
        </template>

        <!-- 血压 -->
        <template v-else-if="formType === 'blood_pressure'">
          <text class="field-label">收缩压 / 高压(mmHg)</text>
          <input class="field-input" type="number" v-model="form.sbp" placeholder="如 128" />
          <text class="field-label">舒张压 / 低压(mmHg)</text>
          <input class="field-input" type="number" v-model="form.dbp" placeholder="如 82" />
        </template>

        <!-- 体重 -->
        <template v-else-if="formType === 'weight'">
          <text class="field-label">体重(kg)</text>
          <input class="field-input" type="digit" v-model="form.value" placeholder="如 68.5" />
        </template>

        <!-- 症状 -->
        <template v-else>
          <text class="field-label">症状描述</text>
          <textarea class="field-textarea" v-model="form.value" placeholder="如:偶尔头晕,持续约 5 分钟" />
        </template>

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
import { listObservations, createObservation, deleteObservation } from '../../api/health.js'
import { errMsg, fmtDateTime, nowLocalISO } from '../../utils/request.js'

const filters = [
  { label: '全部', value: 'all' },
  { label: '血糖', value: 'blood_glucose' },
  { label: '血压', value: 'blood_pressure' },
  { label: '体重', value: 'weight' },
  { label: '症状', value: 'symptom' },
]
const formTypes = [
  { label: '血糖', value: 'blood_glucose' },
  { label: '血压', value: 'blood_pressure' },
  { label: '体重', value: 'weight' },
  { label: '症状', value: 'symptom' },
]
const glucosePeriods = ['空腹', '早餐后', '午餐前', '午餐后', '晚餐前', '晚餐后', '睡前']
const PAGE_SIZE = 20

const filter = ref('all')
const items = ref([])
const total = ref(0)
const pageNo = ref(1)
const loading = ref(true)
const loadingMore = ref(false)
const showForm = ref(false)
const saving = ref(false)
const formType = ref('blood_glucose')
const form = ref({ value: '', period: '', sbp: '', dbp: '' })

const iconOf = (t) =>
  ({ blood_glucose: '🩸', blood_pressure: '🫀', weight: '⚖️', symptom: '📝', exercise: '🚶', medication: '💊' }[t] || '📌')

const displayValue = (o) => {
  if (o.metric_type === 'blood_pressure') {
    const s = o.systolic_value != null ? o.systolic_value : '--'
    const d = o.diastolic_value != null ? o.diastolic_value : '--'
    return `${s}/${d}`
  }
  if (o.value_num != null) return String(o.value_num)
  return o.value_text || ''
}

const isHigh = (o) => {
  if (o.metric_type === 'blood_glucose') return o.value_num != null && o.value_num > 7.8
  if (o.metric_type === 'blood_pressure')
    return (o.systolic_value != null && o.systolic_value >= 140) || (o.diastolic_value != null && o.diastolic_value >= 90)
  return false
}

const load = async () => {
  loading.value = true
  pageNo.value = 1
  try {
    const res = await listObservations(filter.value, 1, PAGE_SIZE)
    items.value = res.items || []
    total.value = res.total || 0
  } catch (e) {
    uni.showToast({ title: errMsg(e), icon: 'none' })
  } finally {
    loading.value = false
  }
}

const loadMore = async () => {
  if (loading.value || loadingMore.value || items.value.length >= total.value) return
  loadingMore.value = true
  try {
    const res = await listObservations(filter.value, pageNo.value + 1, PAGE_SIZE)
    items.value = items.value.concat(res.items || [])
    total.value = res.total || 0
    pageNo.value += 1
  } catch (e) {
    uni.showToast({ title: errMsg(e), icon: 'none' })
  } finally {
    loadingMore.value = false
  }
}

const switchFilter = (v) => {
  filter.value = v
  load()
}

const openForm = () => {
  form.value = { value: '', period: '', sbp: '', dbp: '' }
  showForm.value = true
}

const submit = async () => {
  let payload = null
  if (formType.value === 'blood_glucose') {
    if (!form.value.value) return uni.showToast({ title: '请填写血糖值', icon: 'none' })
    payload = {
      metric_type: 'blood_glucose',
      value_num: Number(form.value.value),
      unit: 'mmol/L',
      context: form.value.period || '',
      measured_at: nowLocalISO(),
      source: 'manual',
    }
  } else if (formType.value === 'blood_pressure') {
    if (!form.value.sbp || !form.value.dbp) return uni.showToast({ title: '请填写血压值', icon: 'none' })
    payload = {
      metric_type: 'blood_pressure',
      systolic_value: Number(form.value.sbp),
      diastolic_value: Number(form.value.dbp),
      unit: 'mmHg',
      measured_at: nowLocalISO(),
      source: 'manual',
    }
  } else if (formType.value === 'weight') {
    if (!form.value.value) return uni.showToast({ title: '请填写体重', icon: 'none' })
    payload = {
      metric_type: 'weight',
      value_num: Number(form.value.value),
      unit: 'kg',
      measured_at: nowLocalISO(),
      source: 'manual',
    }
  } else {
    if (!form.value.value) return uni.showToast({ title: '请填写症状描述', icon: 'none' })
    payload = {
      metric_type: 'symptom',
      value_text: String(form.value.value),
      measured_at: nowLocalISO(),
      source: 'manual',
    }
  }
  saving.value = true
  try {
    await createObservation(payload)
    showForm.value = false
    uni.showToast({ title: '已保存', icon: 'success' })
    if (filter.value !== 'all' && filter.value !== payload.metric_type) filter.value = 'all'
    load()
  } catch (e) {
    uni.showToast({ title: errMsg(e), icon: 'none' })
  } finally {
    saving.value = false
  }
}

const confirmDelete = (o) => {
  uni.showModal({
    title: '删除记录',
    content: `确定删除 ${fmtDateTime(o.measured_at)} 的这条记录吗?`,
    confirmText: '删除',
    confirmColor: '#E53E3E',
    success: async (res) => {
      if (res.confirm) {
        try {
          await deleteObservation(o.observation_id)
          uni.showToast({ title: '已删除', icon: 'none' })
          load()
        } catch (e) {
          uni.showToast({ title: errMsg(e), icon: 'none' })
        }
      }
    },
  })
}

const goStats = () => {
  uni.showActionSheet({
    itemList: ['血糖趋势', '血压趋势'],
    success: (res) => {
      const type = res.tapIndex === 0 ? 'blood_glucose' : 'blood_pressure'
      uni.navigateTo({ url: `/pages/stats/stats?metric_type=${type}` })
    },
  })
}

onMounted(load)
</script>

<style scoped>
.record-page {
  position: fixed;
  left: 0;
  right: 0;
  top: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
}
/* #ifdef H5 */
.record-page {
  top: 44px;
  bottom: 50px;
}
/* #endif */

.list {
  flex: 1;
  overflow: hidden;
}
.rec-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #ffffff;
  border-radius: 12px;
  margin: 10px 16px 0;
  padding: 14px 16px;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.05);
}
.rec-left {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
}
.rec-icon {
  width: 42px;
  height: 42px;
  line-height: 42px;
  text-align: center;
  border-radius: 12px;
  font-size: 20px;
  flex-shrink: 0;
}
.icon-blood_glucose {
  background: #fff5f5;
}
.icon-blood_pressure {
  background: #ebf4fb;
}
.icon-weight {
  background: #f0fff4;
}
.icon-symptom {
  background: #faf5ff;
}
.rec-main {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.rec-value-row {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.rec-value {
  font-size: 18px;
  font-weight: 700;
  color: #1a202c;
}
.value-high {
  color: #e53e3e;
}
.rec-unit {
  font-size: 13px;
  color: #64748b;
}
.rec-period {
  margin-left: 2px;
}
.rec-time {
  font-size: 13px;
  color: #94a3b8;
}
.rec-del {
  width: 28px;
  height: 28px;
  line-height: 28px;
  text-align: center;
  color: #cbd5e1;
  font-size: 16px;
}
.load-more {
  text-align: center;
  font-size: 13px;
  color: #94a3b8;
  padding: 14px 0;
}

.toolbar {
  display: flex;
  gap: 12px;
  padding: 12px 16px;
  background: #ffffff;
  border-top: 1px solid #e2e8f0;
}
.toolbar-btn {
  flex: 1;
  height: 44px;
  line-height: 44px;
  font-size: 16px;
  padding: 0;
}

.seg-inline {
  margin: 12px 0 0;
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
