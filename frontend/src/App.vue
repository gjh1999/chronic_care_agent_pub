<script>
export default {
  onLaunch() {
    if (!uni.getStorageSync('access_token')) {
      uni.reLaunch({ url: '/pages/login/login' })
    }
  }
}
</script>

<style>
page { background: #f5f7fb; color: #17233d; font-size: 30rpx; }
.page { padding: 28rpx; }
.card { background: #fff; border-radius: 18rpx; padding: 24rpx; margin-bottom: 20rpx; }
.primary { background: #165dff; color: #fff; }
.muted { color: #6b7a92; font-size: 26rpx; }
input, textarea { background: #f5f7fb; border-radius: 12rpx; padding: 18rpx; margin: 12rpx 0; }
</style>
