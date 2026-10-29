<script>
export default {
  onLaunch() {
    console.log('测试界面启动(未连接后端,数据均为本地 Mock)')
  },
}
</script>

<style>
/* 全局样式:慢病人群可读性优先 */
page {
  background-color: #f5f7fa;
  color: #1a202c;
  font-size: 16px;
  line-height: 1.6;
  font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Helvetica Neue',
    'Microsoft YaHei', sans-serif;
}

/* H5 端 uni-app 默认在 html/body 上设 user-select:none(模拟 App 手感),
   覆盖为可选中,方便复制回复文字 */
body,
uni-page-body {
  -webkit-user-select: text;
  user-select: text;
}

view,
text,
button,
input,
textarea {
  box-sizing: border-box;
}

/* 通用卡片 */
.card {
  background: #ffffff;
  border-radius: 12px;
  padding: 16px;
  margin: 12px 16px;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.06);
}

/* 通用按钮 */
.btn {
  height: 44px;
  line-height: 44px;
  border-radius: 10px;
  font-size: 16px;
  text-align: center;
  border: none;
  padding: 0 20px;
}
.btn::after {
  border: none;
}
.btn-primary {
  background: #2b6cb0;
  color: #ffffff;
}
.btn-primary[disabled] {
  background: #a0c4e8;
  color: #ffffff;
}
.btn-danger {
  background: #ffffff;
  color: #e53e3e;
  border: 1px solid #e53e3e;
}
.btn-plain {
  background: #ffffff;
  color: #2b6cb0;
  border: 1px solid #2b6cb0;
}

/* 分段选择器 */
.seg {
  display: flex;
  background: #edf2f7;
  border-radius: 10px;
  padding: 3px;
  margin: 12px 16px;
}
.seg-item {
  flex: 1;
  height: 38px;
  line-height: 38px;
  text-align: center;
  font-size: 15px;
  color: #64748b;
  border-radius: 8px;
}
.seg-item.active {
  background: #ffffff;
  color: #2b6cb0;
  font-weight: 600;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.1);
}

/* 徽标 */
.badge {
  display: inline-block;
  padding: 1px 8px;
  border-radius: 8px;
  font-size: 12px;
  line-height: 18px;
}
.badge-red {
  background: #fff5f5;
  color: #e53e3e;
}
.badge-green {
  background: #f0fff4;
  color: #38a169;
}
.badge-orange {
  background: #fffaf0;
  color: #dd6b20;
}
.badge-gray {
  background: #f1f5f9;
  color: #64748b;
}

/* 弹层 */
.mask {
  position: fixed;
  left: 0;
  top: 0;
  right: 0;
  bottom: 0;
  background: rgba(15, 23, 42, 0.5);
  z-index: 90;
}
.sheet {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  background: #ffffff;
  border-radius: 16px 16px 0 0;
  padding: 20px 16px 28px;
  z-index: 91;
  max-height: 80vh;
  overflow-y: auto;
}

/* 表单 */
.field-label {
  font-size: 14px;
  color: #64748b;
  margin: 12px 0 6px;
}
.field-input {
  background: #f5f7fa;
  border-radius: 10px;
  height: 44px;
  line-height: 44px;
  padding: 0 12px;
  font-size: 16px;
  width: 100%;
}
.field-textarea {
  background: #f5f7fa;
  border-radius: 10px;
  padding: 10px 12px;
  font-size: 16px;
  width: 100%;
  min-height: 72px;
}

.empty {
  text-align: center;
  color: #94a3b8;
  font-size: 14px;
  padding: 60px 0;
}
</style>
