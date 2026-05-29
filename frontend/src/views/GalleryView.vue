<template>
  <div class="gallery-view">
    <h2>作品库</h2>
    <div v-if="videos.length === 0" class="empty">
      <p>暂无已生成的视频。</p>
      <router-link to="/generate">创建第一个视频</router-link>
    </div>
    <div v-else class="grid">
      <div v-for="v in videos" :key="v.id" class="card" @click="playing = v">
        <div class="thumb">
          <div class="play-icon">&#9654;</div>
        </div>
        <div class="card-info">
          <div class="card-prompt">{{ v.prompt.slice(0, 40) }}</div>
          <div class="card-meta">{{ v.width }}x{{ v.height }} | {{ v.created_at?.slice(0, 10) }}</div>
        </div>
      </div>
    </div>

    <!-- Player modal -->
    <div v-if="playing" class="player-overlay" @click.self="playing = null">
      <div class="player">
        <button class="close-btn" @click="playing = null">x</button>
        <div class="video-container">
          <video
            v-if="playing.output_path"
            :src="getVideoUrl(playing.id)"
            controls
            autoplay
            class="video-player"
            @error="handleVideoError"
          />
          <div v-else class="player-placeholder">
            <div class="play-icon-large">&#9654;</div>
            <p>视频生成中...</p>
          </div>
        </div>
        <div class="player-info">
          <p>{{ playing.prompt }}</p>
          <span>{{ playing.width }}x{{ playing.height }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import type { Task } from '../types/task'
import { getTasks } from '../api/tasks'
import client from '../api/client'

const videos = ref<Task[]>([])
const playing = ref<Task | null>(null)

const getVideoUrl = (taskId: string) => {
  return `${client.defaults.baseURL}/tasks/${taskId}/output`
}

const handleVideoError = (e: Event) => {
  console.error('Video playback error:', e)
}

onMounted(async () => {
  try {
    const tasks = await getTasks({ status: 'done' })
    videos.value = tasks
  } catch {}
})
</script>

<style scoped>
.empty { text-align: center; padding: 48px; color: #666; }
.empty a { color: #e94560; }
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 16px;
  margin-top: 16px;
}
.card {
  background: #1a1a2e;
  border-radius: 8px;
  overflow: hidden;
  cursor: pointer;
  transition: transform 0.2s;
}
.card:hover { transform: translateY(-2px); }
.thumb {
  aspect-ratio: 16 / 9;
  background: #0f0f23;
  display: flex;
  align-items: center;
  justify-content: center;
}
.play-icon { font-size: 32px; color: #333; }
.card-info { padding: 10px 12px; }
.card-prompt { font-size: 13px; color: #ccc; }
.card-meta { font-size: 11px; color: #555; margin-top: 4px; }

.player-overlay {
  position: fixed; inset: 0;
  background: rgba(0,0,0,0.8);
  display: flex; align-items: center; justify-content: center;
  z-index: 100;
}
.player {
  background: #1a1a2e;
  border-radius: 12px;
  width: 700px;
  max-width: 90vw;
  overflow: hidden;
}
.close-btn {
  float: right;
  background: none; border: none; color: #888; font-size: 20px;
  cursor: pointer; padding: 12px;
}
.video-container {
  aspect-ratio: 16 / 9;
  background: #0f0f23;
}
.video-player {
  width: 100%;
  height: 100%;
  object-fit: contain;
}
.player-placeholder {
  aspect-ratio: 16 / 9;
  background: #0f0f23;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #555;
}
.play-icon-large { font-size: 64px; }
.player-info { padding: 16px; }
.player-info p { margin: 0; font-size: 14px; color: #ccc; }
.player-info span { font-size: 12px; color: #666; }
</style>
