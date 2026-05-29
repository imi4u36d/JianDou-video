<template>
  <div class="queue-view">
    <div class="queue-header">
      <h2>任务队列</h2>
      <div class="filter-tabs">
        <button v-for="f in filters" :key="f.value" :class="{ active: activeFilter === f.value }" @click="activeFilter = f.value">
          {{ f.label }} ({{ counts[f.value] || 0 }})
        </button>
      </div>
    </div>

    <div v-if="tasks.length === 0" class="empty">
      <p>暂无任务。</p>
      <router-link to="/generate">创建第一个生成任务</router-link>
    </div>

    <div v-else class="task-list">
      <div v-for="task in tasks" :key="task.id" class="task-card" @click="selected = task">
        <div class="task-left">
          <div class="task-id">{{ task.id.slice(0, 8) }}</div>
          <div class="task-prompt">{{ task.prompt.slice(0, 60) }}{{ task.prompt.length > 60 ? '...' : '' }}</div>
        </div>
        <div class="task-mid">
          <div class="task-mode">{{ task.mode.toUpperCase() }}</div>
          <div class="task-res">{{ task.width }}x{{ task.height }}</div>
        </div>
        <div class="task-right">
          <div class="task-status" :class="task.status">
            <span class="status-dot"></span>
            {{ statusLabel(task.status) }}
          </div>
          <div class="progress-bar" v-if="task.status === 'running'">
            <div class="progress-fill" :style="{ width: task.progress * 100 + '%' }"></div>
          </div>
          <div class="task-step" v-if="task.status === 'running'">
            {{ stageLabel(task.stage) }} {{ task.current_step }}/{{ task.total_steps }}
          </div>
        </div>
      </div>
    </div>

    <!-- Detail panel -->
    <div v-if="selected" class="detail-overlay" @click.self="selected = null">
      <div class="detail-panel">
        <div class="detail-header">
          <h3>任务 {{ selected.id.slice(0, 8) }}</h3>
          <button @click="selected = null" class="close-btn">x</button>
        </div>
        <div class="detail-body">
          <div class="detail-row"><span>模式</span> {{ selected.mode }}</div>
          <div class="detail-row"><span>状态</span> <span :class="selected.status">{{ statusLabel(selected.status) }}</span></div>
          <div class="detail-row"><span>提示词</span> {{ selected.prompt }}</div>
          <div class="detail-row"><span>分辨率</span> {{ selected.width }}x{{ selected.height }}</div>
          <div class="detail-row"><span>时长</span> {{ selected.duration }}s @ {{ selected.fps }}fps</div>
          <div class="detail-row"><span>步数</span> {{ selected.steps }} (CFG: {{ selected.cfg }})</div>
          <div class="detail-row"><span>预设</span> {{ selected.preset }}</div>
          <div class="detail-row" v-if="selected.error_message">
            <span>错误</span> <span class="error">{{ selected.error_message }}</span>
          </div>
        </div>
        <div class="detail-actions">
          <button v-if="selected.status === 'failed'" class="btn-retry" @click="handleRetry(selected.id)">重试</button>
          <button class="btn-delete" @click="handleDelete(selected.id)">删除</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue'
import type { Task } from '../types/task'
import { getTasks, deleteTask, retryTask } from '../api/tasks'
import { WebSocketClient } from '../api/ws'

const tasks = ref<Task[]>([])
const selected = ref<Task | null>(null)
const activeFilter = ref('')
const counts = ref<Record<string, number>>({})
const statusLabel = (s: string) => {
  const map: Record<string, string> = { pending: '等待中', running: '运行中', done: '已完成', failed: '失败', cancelled: '已取消' }
  return map[s] || s
}
const stageLabel = (s: string) => {
  const map: Record<string, string> = { stage1: 'Stage 1 生成', stage2: 'Stage 2 细化', loading: '加载中', encoding: '编码中', decoding: '解码中' }
  return map[s] || s || '推理中'
}

const filters = [
  { value: '', label: '全部' },
  { value: 'pending', label: '等待中' },
  { value: 'running', label: '运行中' },
  { value: 'done', label: '已完成' },
  { value: 'failed', label: '失败' },
]

let ws: WebSocketClient | null = null
let pollTimer: ReturnType<typeof setInterval> | null = null

async function fetchTasks() {
  try {
    const params: Record<string, string> = {}
    if (activeFilter.value) params.status = activeFilter.value
    const data = await getTasks(params)
    tasks.value = data
    // Update counts
    try {
      const all = await getTasks({})
      counts.value = { '': all.length }
      for (const f of filters.slice(1)) {
        counts.value[f.value] = all.filter((t: Task) => t.status === f.value).length
      }
      // Start/stop polling for running tasks
      const hasRunning = all.some((t: Task) => t.status === 'running')
      if (hasRunning && !pollTimer) {
        pollTimer = setInterval(fetchTasks, 1000)
      } else if (!hasRunning && pollTimer) {
        clearInterval(pollTimer)
        pollTimer = null
      }
    } catch {}
  } catch {}
}

async function handleDelete(id: string) {
  await deleteTask(id)
  selected.value = null
  fetchTasks()
}

async function handleRetry(id: string) {
  await retryTask(id)
  fetchTasks()
}

watch(activeFilter, fetchTasks)

onMounted(() => {
  fetchTasks()
  ws = new WebSocketClient('/ws/queue', (data) => {
    if (data.type === 'task.created' || data.type === 'task.completed') {
      fetchTasks()
    }
  })
  ws.connect()
})

onUnmounted(() => {
  ws?.disconnect()
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<style scoped>
.queue-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
}
.filter-tabs { display: flex; gap: 4px; }
.filter-tabs button {
  background: #1a1a2e;
  border: 1px solid #333;
  border-radius: 6px;
  color: #888;
  padding: 4px 12px;
  font-size: 12px;
  cursor: pointer;
}
.filter-tabs button.active { border-color: #e94560; color: #e94560; }

.empty { text-align: center; padding: 48px; color: #666; }
.empty a { color: #e94560; }

.task-list { display: flex; flex-direction: column; gap: 8px; }
.task-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #1a1a2e;
  border-radius: 8px;
  padding: 12px 16px;
  cursor: pointer;
  transition: background 0.15s;
  border: 1px solid transparent;
}
.task-card:hover { border-color: #333; }
.task-left { flex: 1; min-width: 0; }
.task-id { font-size: 11px; color: #555; font-family: monospace; }
.task-prompt { font-size: 14px; color: #ccc; margin-top: 2px; }
.task-mid { text-align: center; padding: 0 16px; }
.task-mode { font-size: 11px; color: #666; }
.task-res { font-size: 12px; color: #888; }
.task-right { text-align: right; min-width: 120px; }
.task-status {
  font-size: 12px;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 4px;
}
.status-dot { width: 6px; height: 6px; border-radius: 50%; display: inline-block; }
.task-status.pending .status-dot { background: #ffa500; }
.task-status.running .status-dot { background: #0af; }
.task-status.done .status-dot { background: #0f9; }
.task-status.failed .status-dot { background: #e94560; }
.task-status.pending { color: #ffa500; }
.task-status.running { color: #0af; }
.task-status.done { color: #0f9; }
.task-status.failed { color: #e94560; }
.task-step { font-size: 11px; color: #555; margin-top: 4px; }
.progress-bar {
  height: 4px;
  background: #0f0f23;
  border-radius: 2px;
  margin-top: 6px;
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  background: #0af;
  border-radius: 2px;
  transition: width 0.3s;
}

/* Detail panel */
.detail-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}
.detail-panel {
  background: #1a1a2e;
  border-radius: 12px;
  width: 480px;
  max-height: 80vh;
  overflow-y: auto;
}
.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid #333;
}
.detail-header h3 { margin: 0; }
.close-btn {
  background: none; border: none; color: #888; font-size: 18px; cursor: pointer;
}
.detail-body { padding: 20px; }
.detail-row {
  margin-bottom: 10px;
  font-size: 13px;
}
.detail-row span:first-child {
  color: #666;
  display: inline-block;
  width: 100px;
}
.error { color: #e94560; }
.detail-actions {
  display: flex; gap: 8px; padding: 16px 20px; border-top: 1px solid #333;
}
.btn-retry {
  background: #0af; color: #fff; border: none; padding: 8px 16px;
  border-radius: 6px; cursor: pointer;
}
.btn-delete {
  background: #333; color: #ccc; border: none; padding: 8px 16px;
  border-radius: 6px; cursor: pointer;
}
</style>
