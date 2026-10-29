<template>
  <view class="stats-page">
    <view v-if="loading" class="empty">加载中…</view>

    <template v-else-if="count === 0">
      <view class="empty">暂无数据,先去「记录」页添加几条记录吧</view>
    </template>

    <template v-else>
      <!-- 摘要卡片 -->
      <view class="card summary">
        <template v-if="isBp">
          <view class="sum-item">
            <text class="sum-label">平均血压</text>
            <text class="sum-value">{{ sbpAvg }}/{{ dbpAvg }}</text>
          </view>
          <view class="sum-item">
            <text class="sum-label">最高收缩压</text>
            <text class="sum-value" :class="sbpMax >= 140 ? 'sum-high' : ''">{{ sbpMax }}</text>
          </view>
          <view class="sum-item">
            <text class="sum-label">超标次数</text>
            <text class="sum-value" :class="overCount > 0 ? 'sum-high' : ''">{{ overCount }} 次</text>
          </view>
        </template>
        <template v-else>
          <view class="sum-item">
            <text class="sum-label">平均血糖</text>
            <text class="sum-value">{{ average }}</text>
          </view>
          <view class="sum-item">
            <text class="sum-label">最高 / 最低</text>
            <text class="sum-value">{{ gluMax }} / {{ gluMin }}</text>
          </view>
          <view class="sum-item">
            <text class="sum-label">超标次数</text>
            <text class="sum-value" :class="overCount > 0 ? 'sum-high' : ''">{{ overCount }} 次</text>
          </view>
        </template>
        <text class="sum-unit">单位:{{ isBp ? 'mmHg' : 'mmol/L' }} · 共 {{ count }} 条记录</text>
      </view>

      <!-- 图表 -->
      <view class="card chart-card">
        <view v-if="isBp" class="legend">
          <text class="legend-item"><text class="legend-line line-sbp"></text>收缩压</text>
          <text class="legend-item"><text class="legend-line line-dbp"></text>舒张压</text>
          <text class="legend-item"><text class="legend-line line-thr"></text>正常上限</text>
        </view>
        <view v-else class="legend">
          <text class="legend-item"><text class="legend-line line-glu"></text>血糖</text>
          <text class="legend-item">绿色区域为正常范围</text>
        </view>

        <view class="svg-wrap">
          <svg :viewBox="`0 0 ${W} ${H}`" class="chart-svg">
            <!-- 正常区间 -->
            <template v-if="isBp">
              <rect :x="padL" :y="y(140)" :width="plotW" :height="y(40) - y(140)" fill="#f0fff4" />
            </template>
            <template v-else>
              <rect :x="padL" :y="y(7.8)" :width="plotW" :height="y(3.9) - y(7.8)" fill="#f0fff4" />
            </template>

            <!-- 网格与 y 轴刻度 -->
            <template v-for="t in yTicks" :key="'y' + t">
              <line :x1="padL" :x2="W - padR" :y1="y(t)" :y2="y(t)" stroke="#edf2f7" stroke-width="1" />
              <text :x="padL - 6" :y="y(t) + 3" text-anchor="end" class="tick-text">{{ t }}</text>
            </template>

            <!-- x 轴标签 -->
            <template v-for="(d, i) in dates" :key="'x' + i">
              <text v-if="i % Math.max(1, Math.floor(dates.length / 7)) === 0" :x="x(i)" :y="H - 8" text-anchor="middle" class="tick-text">{{ d }}</text>
            </template>

            <!-- 阈值线 -->
            <template v-if="isBp">
              <line :x1="padL" :x2="W - padR" :y1="y(140)" :y2="y(140)" stroke="#e53e3e" stroke-width="1.5" stroke-dasharray="5,4" />
              <text :x="W - padR" :y="y(140) - 4" text-anchor="end" class="thr-text">140</text>
              <line :x1="padL" :x2="W - padR" :y1="y(90)" :y2="y(90)" stroke="#e53e3e" stroke-width="1.5" stroke-dasharray="5,4" />
              <text :x="W - padR" :y="y(90) - 4" text-anchor="end" class="thr-text">90</text>
            </template>

            <!-- 折线 -->
            <template v-if="isBp">
              <polyline :points="linePoints(sbpSeries)" fill="none" stroke="#2b6cb0" stroke-width="2.5" />
              <polyline :points="linePoints(dbpSeries)" fill="none" stroke="#38a169" stroke-width="2.5" stroke-dasharray="4,3" />
              <template v-for="(v, i) in sbpSeries" :key="'p' + i">
                <circle :cx="x(i)" :cy="y(v)" r="3" :fill="v >= 140 ? '#e53e3e' : '#2b6cb0'" />
              </template>
              <template v-for="(v, i) in dbpSeries" :key="'d' + i">
                <circle :cx="x(i)" :cy="y(v)" r="3" :fill="v >= 90 ? '#e53e3e' : '#38a169'" />
              </template>
            </template>
            <template v-else>
              <polyline :points="linePoints(gluSeries)" fill="none" stroke="#2b6cb0" stroke-width="2.5" />
              <template v-for="(v, i) in gluSeries" :key="'p' + i">
                <circle :cx="x(i)" :cy="y(v)" r="3.5" :fill="v > 7.8 ? '#e53e3e' : '#2b6cb0'" />
                <text v-if="gluSeries.length <= 20" :x="x(i)" :y="y(v) - 8" text-anchor="middle" class="val-text" :fill="v > 7.8 ? '#e53e3e' : '#2b6cb0'">{{ v }}</text>
              </template>
            </template>
          </svg>
        </view>
      </view>

      <view class="tips card">
        <text class="tips-title">📌 指标参考</text>
        <text v-if="isBp" class="tips-line">· 正常血压:< 140/90 mmHg(家庭自测)</text>
        <text v-else class="tips-line">· 空腹血糖正常:3.9-6.1 mmol/L;餐后 2 小时:< 7.8 mmol/L</text>
        <text class="tips-line">· 连续超标请及时联系医生</text>
      </view>
    </template>
  </view>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { getStats } from '../../api/health.js'
import { errMsg } from '../../utils/request.js'

const loading = ref(true)
const metricType = ref('blood_glucose')
const count = ref(0)
const average = ref('--')
const points = ref([])

const W = 340
const H = 200
const padL = 34
const padR = 12
const padT = 16
const padB = 24
const plotW = W - padL - padR
const plotH = H - padT - padB

const isBp = computed(() => metricType.value === 'blood_pressure')

const dateOf = (p) => (p.measured_at || '').slice(5, 10) || '-'
const dates = computed(() =>
  isBp.value
    ? points.value.filter((p) => p.systolic_value != null && p.diastolic_value != null).map(dateOf)
    : points.value.filter((p) => p.value_num != null).map(dateOf)
)

const gluSeries = computed(() => points.value.filter((p) => p.value_num != null).map((p) => p.value_num))
const sbpSeries = computed(() => points.value.filter((p) => p.systolic_value != null && p.diastolic_value != null).map((p) => p.systolic_value))
const dbpSeries = computed(() => points.value.filter((p) => p.systolic_value != null && p.diastolic_value != null).map((p) => p.diastolic_value))

const sbpAvg = computed(() => (sbpSeries.value.length ? Math.round(sbpSeries.value.reduce((a, b) => a + b, 0) / sbpSeries.value.length) : '--'))
const dbpAvg = computed(() => (dbpSeries.value.length ? Math.round(dbpSeries.value.reduce((a, b) => a + b, 0) / dbpSeries.value.length) : '--'))
const sbpMax = computed(() => (sbpSeries.value.length ? Math.max(...sbpSeries.value) : 0))
const gluMax = computed(() => (gluSeries.value.length ? Math.max(...gluSeries.value) : '--'))
const gluMin = computed(() => (gluSeries.value.length ? Math.min(...gluSeries.value) : '--'))
const overCount = computed(() =>
  isBp.value
    ? sbpSeries.value.filter((v) => v >= 140).length + dbpSeries.value.filter((v) => v >= 90).length
    : gluSeries.value.filter((v) => v > 7.8).length
)

const yMin = computed(() => {
  if (isBp.value) return Math.min(50, Math.floor((Math.min(...dbpSeries.value, 80) - 10) / 10) * 10)
  return Math.max(0, Math.floor((Math.min(...gluSeries.value, 3.9) - 0.6) * 2) / 2)
})
const yMax = computed(() => {
  if (isBp.value) return Math.max(150, Math.ceil((Math.max(...sbpSeries.value, 140) + 10) / 10) * 10)
  return Math.max(8.5, Math.ceil((Math.max(...gluSeries.value, 7.8) + 0.6) * 2) / 2)
})
const yTicks = computed(() => {
  const n = 4
  const arr = []
  for (let i = 0; i <= n; i++) {
    const v = yMin.value + ((yMax.value - yMin.value) * i) / n
    arr.push(isBp.value ? Math.round(v) : Math.round(v * 10) / 10)
  }
  return arr
})

const x = (i) => padL + (dates.value.length <= 1 ? 0 : (plotW * i) / (dates.value.length - 1))
const y = (v) => padT + plotH - ((v - yMin.value) / (yMax.value - yMin.value || 1)) * plotH
const linePoints = (arr) => (arr || []).map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ')

onMounted(async () => {
  const pages = getCurrentPages()
  const current = pages[pages.length - 1]
  const opts = (current && current.$page && current.$page.options) || {}
  metricType.value = opts.metric_type || 'blood_glucose'
  uni.setNavigationBarTitle({ title: metricType.value === 'blood_pressure' ? '血压趋势' : '血糖趋势' })
  try {
    const res = await getStats(metricType.value)
    count.value = res.count || 0
    average.value = res.average != null ? res.average : '--'
    points.value = res.points || []
  } catch (e) {
    uni.showToast({ title: errMsg(e), icon: 'none' })
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.stats-page {
  min-height: 100vh;
  padding-bottom: 24px;
}
.summary {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 0;
}
.sum-item {
  width: 33.3%;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.sum-label {
  font-size: 13px;
  color: #64748b;
}
.sum-value {
  font-size: 20px;
  font-weight: 700;
  color: #1a202c;
}
.sum-high {
  color: #e53e3e;
}
.sum-unit {
  width: 100%;
  font-size: 12px;
  color: #94a3b8;
  margin-top: 4px;
}

.chart-card {
  padding: 14px;
}
.legend {
  display: flex;
  gap: 14px;
  font-size: 12px;
  color: #64748b;
  flex-wrap: wrap;
  margin-bottom: 6px;
}
.legend-item {
  display: flex;
  align-items: center;
  gap: 4px;
}
.legend-line {
  display: inline-block;
  width: 18px;
  height: 3px;
  border-radius: 2px;
}
.line-sbp {
  background: #2b6cb0;
}
.line-dbp {
  background: #38a169;
}
.line-thr {
  background: repeating-linear-gradient(90deg, #e53e3e 0 4px, transparent 4px 7px);
}
.line-glu {
  background: #2b6cb0;
}
.svg-wrap {
  width: 100%;
}
.chart-svg {
  width: 100%;
  display: block;
}
.tick-text {
  font-size: 9px;
  fill: #94a3b8;
}
.val-text {
  font-size: 9px;
}
.thr-text {
  font-size: 9px;
  fill: #e53e3e;
}

.tips {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.tips-title {
  font-size: 15px;
  font-weight: 600;
}
.tips-line {
  font-size: 14px;
  color: #64748b;
}
</style>
