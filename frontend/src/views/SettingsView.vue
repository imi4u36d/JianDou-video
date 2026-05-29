<template>
  <div class="settings-view">
    <h2>设置</h2>

    <div class="settings-section">
      <h3>服务器</h3>
      <div class="setting-row">
        <label>主机</label>
        <input v-model="config.server.host" disabled />
      </div>
      <div class="setting-row">
        <label>端口</label>
        <input v-model.number="config.server.port" disabled />
      </div>
    </div>

    <div class="settings-section">
      <h3>引擎</h3>
      <div class="setting-row">
        <label>模型版本</label>
        <select v-model="config.engine.model_version" disabled>
          <option>2.0</option>
          <option>2.3</option>
        </select>
      </div>
      <div class="setting-row">
        <label>流水线</label>
        <select v-model="config.engine.pipeline" disabled>
          <option>auto</option>
          <option>distilled</option>
          <option>one-stage</option>
          <option>two-stage</option>
        </select>
      </div>
      <div class="setting-row">
        <label>
          <input type="checkbox" v-model="config.engine.fp16" disabled /> FP16
        </label>
      </div>
      <div class="setting-row">
        <label>
          <input type="checkbox" v-model="config.engine.low_memory" disabled /> 低内存模式
        </label>
      </div>
    </div>

    <div class="settings-section">
      <h3>队列</h3>
      <div class="setting-row">
        <label>最大并发数</label>
        <input v-model.number="config.queue.max_workers" disabled />
      </div>
    </div>

    <div class="settings-section">
      <h3>硬件信息</h3>
      <div v-if="systemInfo" class="hw-grid">
        <div class="hw-item"><span>芯片</span> {{ systemInfo.chip }}</div>
        <div class="hw-item"><span>内存</span> {{ systemInfo.ram_gb }} GB</div>
        <div class="hw-item"><span>GPU 核心</span> {{ systemInfo.gpu_cores }}</div>
        <div class="hw-item"><span>性能等级</span> {{ systemInfo.tier?.toUpperCase() }}</div>
        <div class="hw-item"><span>最大分辨率</span> {{ systemInfo.max_resolution?.join('x') }}</div>
        <div class="hw-item"><span>最大帧数</span> {{ systemInfo.max_frames }}</div>
        <div class="hw-item"><span>MLX</span> {{ systemInfo.mlx_version }}</div>
        <div class="hw-item"><span>ffmpeg</span> {{ systemInfo.ffmpeg_available ? '是' : '否' }}</div>
      </div>
      <p v-else class="muted">加载中...</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import type { SystemInfo } from '../types/system'
import client from '../api/client'

const config = reactive({
  server: { host: '0.0.0.0', port: 8000 },
  engine: { model_version: '2.3', pipeline: 'auto', fp16: true, low_memory: false },
  queue: { max_workers: 1 },
})

const systemInfo = ref<SystemInfo | null>(null)

onMounted(async () => {
  try {
    const res = await client.get('/system/config')
    Object.assign(config, res.data)
  } catch {}
  try {
    const res = await client.get('/system/info')
    systemInfo.value = res.data
  } catch {}
})
</script>

<style scoped>
.settings-section {
  background: #1a1a2e;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 16px;
}
.settings-section h3 {
  margin: 0 0 14px;
  font-size: 14px;
  color: #e94560;
  text-transform: uppercase;
}
.setting-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
  font-size: 13px;
}
.setting-row label { color: #888; }
.setting-row input, .setting-row select {
  background: #0f0f23;
  border: 1px solid #333;
  border-radius: 4px;
  color: #eee;
  padding: 4px 10px;
  font-size: 13px;
  width: 200px;
}
.hw-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}
.hw-item { font-size: 13px; }
.hw-item span { color: #666; margin-right: 8px; }
.muted { color: #666; font-size: 13px; }
</style>
