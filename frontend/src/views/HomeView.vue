<template>
  <div class="home-view">
    <div class="hero">
      <h2>AI 视频生成</h2>
      <p>在 Apple Silicon 上使用 LTX 2.3 生成高质量视频</p>
      <router-link to="/generate" class="cta-btn">开始生成</router-link>
    </div>

    <div class="stats-row">
      <div class="stat-card">
        <div class="stat-value">{{ systemStore.info?.chip || '...' }}</div>
        <div class="stat-label">芯片</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ systemStore.info?.ram_gb || '...' }} GB</div>
        <div class="stat-label">内存</div>
      </div>
      <div class="stat-card">
        <div class="stat-value tier-badge" :class="systemStore.info?.tier">{{ systemStore.info?.tier?.toUpperCase() || '...' }}</div>
        <div class="stat-label">性能等级</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ queueStats.active || 0 }} / {{ queueStats.total || 0 }}</div>
        <div class="stat-label">任务数</div>
      </div>
    </div>

    <div class="quick-actions">
      <router-link to="/generate?mode=t2v" class="action-card">
        <div class="action-icon">T</div>
        <h3>文本生成视频</h3>
        <p>描述你的场景，让 AI 将其变为现实</p>
      </router-link>
      <router-link to="/generate?mode=i2v" class="action-card">
        <div class="action-icon">I</div>
        <h3>图片生成视频</h3>
        <p>将静态图片转换为动态视频</p>
      </router-link>
      <router-link to="/queue" class="action-card">
        <div class="action-icon">Q</div>
        <h3>任务队列</h3>
        <p>监控运行中和等待中的生成任务</p>
      </router-link>
      <router-link to="/gallery" class="action-card">
        <div class="action-icon">G</div>
        <h3>作品库</h3>
        <p>浏览已生成的视频</p>
      </router-link>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useSystemStore } from '../stores/system'
import client from '../api/client'

const systemStore = useSystemStore()
const queueStats = ref({ active: 0, total: 0 })

onMounted(async () => {
  systemStore.fetchSystemInfo()
  try {
    const res = await client.get('/tasks')
    queueStats.value = {
      total: res.data.total || 0,
      active: res.data.tasks?.filter((t: any) => t.status === 'running').length || 0,
    }
  } catch {}
})
</script>

<style scoped>
.hero {
  text-align: center;
  padding: 48px 0 32px;
}
.hero h2 {
  font-size: 32px;
  margin: 0 0 8px;
  background: linear-gradient(135deg, #e94560, #0f3460);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}
.hero p { color: #888; margin: 0 0 24px; }
.cta-btn {
  display: inline-block;
  background: #e94560;
  color: #fff;
  padding: 12px 32px;
  border-radius: 8px;
  text-decoration: none;
  font-weight: 600;
}

.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 32px;
}
.stat-card {
  background: #1a1a2e;
  border-radius: 8px;
  padding: 16px;
  text-align: center;
}
.stat-value { font-size: 20px; font-weight: 700; color: #fff; }
.stat-label { font-size: 12px; color: #666; margin-top: 4px; }
.tier-badge.ultra { color: #ffd700; }
.tier-badge.high { color: #e94560; }
.tier-badge.medium { color: #0f9; }
.tier-badge.low { color: #888; }

.quick-actions {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 16px;
}
.action-card {
  display: block;
  padding: 24px;
  background: #1a1a2e;
  border-radius: 8px;
  text-decoration: none;
  color: #ccc;
  transition: all 0.2s;
  border: 1px solid transparent;
}
.action-card:hover {
  border-color: #e94560;
  transform: translateY(-2px);
}
.action-icon {
  width: 40px; height: 40px;
  background: #16213e;
  border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  font-size: 18px; font-weight: 700; color: #e94560;
  margin-bottom: 12px;
}
.action-card h3 { margin: 0 0 4px; color: #fff; font-size: 15px; }
.action-card p { margin: 0; font-size: 13px; color: #888; }
</style>
