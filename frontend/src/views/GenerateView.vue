<template>
  <div class="generate-view">
    <h2>生成视频</h2>

    <div class="generate-layout">
      <div class="main-panel">
        <div class="section">
          <label class="section-label">模式</label>
          <div class="mode-tabs">
            <button
              v-for="m in modes"
              :key="m.value"
              :class="{ active: form.mode === m.value }"
              @click="form.mode = m.value"
            >
              {{ m.label }}
            </button>
          </div>
        </div>

        <div class="section" v-if="form.mode === 'i2v' || form.mode === 'fflf'">
          <label class="section-label">输入图片</label>
          <ImageUpload v-model="form.image" />
        </div>

        <div class="section">
          <label class="section-label">提示词</label>
          <textarea
            v-model="form.prompt"
            placeholder="描述你想生成的视频..."
            rows="4"
            class="prompt-input"
          />
        </div>

        <button class="generate-btn" @click="handleGenerate" :disabled="!form.prompt || submitting">
          {{ submitting ? '提交中...' : '生成' }}
        </button>
        <p v-if="error" class="error-msg">{{ error }}</p>
      </div>

      <div class="side-panel">
        <div class="section">
          <label class="section-label">预设</label>
          <div class="preset-tabs">
            <button
              v-for="p in presets"
              :key="p.value"
              :class="{ active: form.preset === p.value }"
              @click="applyPreset(p.value)"
            >
              {{ p.label }}
              <span class="preset-desc">{{ p.desc }}</span>
            </button>
          </div>
        </div>

        <div class="section">
          <label class="section-label">时长: {{ form.duration }}s</label>
          <input type="range" v-model.number="form.duration" min="1" max="15" step="0.5" />
        </div>

        <div class="section">
          <label class="section-label">分辨率: {{ form.width }}x{{ form.height }}</label>
          <select v-model="resolutionPreset" @change="applyResolution">
            <option v-for="r in resolutions" :key="r.label" :value="r.label">{{ r.label }}</option>
          </select>
        </div>

        <div class="section">
          <label class="section-label">步数: {{ form.steps }}</label>
          <input type="range" v-model.number="form.steps" min="1" max="20" />
        </div>

        <div class="section">
          <label class="section-label">CFG: {{ form.cfg }}</label>
          <input type="range" v-model.number="form.cfg" min="0" max="10" step="0.5" />
        </div>

        <div class="section">
          <label class="section-label">种子 (-1 = 随机)</label>
          <input type="number" v-model.number="form.seed" class="num-input" />
        </div>

        <div class="section">
          <label class="checkbox-label">
            <input type="checkbox" v-model="form.fp16" /> FP16
          </label>
          <label class="checkbox-label">
            <input type="checkbox" v-model="form.lowMemory" /> 低内存
          </label>
          <label class="checkbox-label">
            <input type="checkbox" v-model="form.generateAudio" /> 生成音频
          </label>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import ImageUpload from '../components/generate/ImageUpload.vue'
import { useGenerationStore } from '../stores/generation'

const router = useRouter()
const store = useGenerationStore()
const submitting = ref(false)
const error = ref('')

const modes = [
  { value: 't2v', label: '文本生成视频' },
  { value: 'i2v', label: '图片生成视频' },
  { value: 'fflf', label: '关键帧插值' },
]

const presets = [
  { value: 'fast', label: '快速', desc: '512x288, 4 步' },
  { value: 'balanced', label: '均衡', desc: '768x512, 8 步' },
  { value: 'quality', label: '高质量', desc: '1024x576, 12 步' },
]

const resolutions = [
  { label: '512x288 (快速)', w: 512, h: 288 },
  { label: '768x512 (标准)', w: 768, h: 512 },
  { label: '1024x576 (HD)', w: 1024, h: 576 },
  { label: '1280x720 (HD+)', w: 1280, h: 720 },
]

const resolutionPreset = ref('768x512 (标准)')

const presetDefaults: Record<string, any> = {
  fast: { duration: 3, width: 512, height: 288, steps: 4, fps: 16, cfg: 1, fp16: true, lowMemory: true },
  balanced: { duration: 5, width: 768, height: 512, steps: 8, fps: 24, cfg: 2, fp16: true, lowMemory: false },
  quality: { duration: 5, width: 1024, height: 576, steps: 12, fps: 24, cfg: 3, fp16: false, lowMemory: false },
}

const form = reactive({
  mode: 't2v',
  prompt: '',
  image: null as File | null,
  duration: 5,
  width: 768,
  height: 512,
  fps: 24,
  steps: 8,
  cfg: 2,
  seed: -1,
  preset: 'balanced',
  fp16: true,
  lowMemory: false,
  generateAudio: false,
})

function applyPreset(name: string) {
  const p = presetDefaults[name]
  if (!p) return
  form.preset = name
  form.duration = p.duration
  form.width = p.width
  form.height = p.height
  form.steps = p.steps
  form.fps = p.fps
  form.cfg = p.cfg
  form.fp16 = p.fp16
  form.lowMemory = p.lowMemory
  resolutionPreset.value = resolutions.find(r => r.w === p.width)?.label || resolutionPreset.value
}

function applyResolution() {
  const r = resolutions.find(r => r.label === resolutionPreset.value)
  if (r) { form.width = r.w; form.height = r.h }
}

async function handleGenerate() {
  if (!form.prompt || submitting.value) return
  submitting.value = true
  error.value = ''
  try {
    await store.createGeneration({
      mode: form.mode,
      prompt: form.prompt,
      duration: form.duration,
      width: form.width,
      height: form.height,
      fps: form.fps,
      steps: form.steps,
      cfg: form.cfg,
      seed: form.seed,
      preset: form.preset,
    })
    router.push('/queue')
  } catch (e: any) {
    error.value = e?.response?.data?.detail || '创建任务失败，请检查后端服务'
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.generate-view { max-width: 1100px; }
.generate-layout {
  display: grid;
  grid-template-columns: 1fr 300px;
  gap: 24px;
  margin-top: 16px;
}
.section { margin-bottom: 20px; }
.section-label { display: block; font-size: 12px; color: #888; text-transform: uppercase; margin-bottom: 8px; }

.mode-tabs, .preset-tabs {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.mode-tabs button, .preset-tabs button {
  background: #1a1a2e;
  border: 1px solid #333;
  border-radius: 6px;
  color: #ccc;
  padding: 8px 16px;
  cursor: pointer;
  font-size: 13px;
  transition: all 0.2s;
}
.mode-tabs button.active, .preset-tabs button.active {
  border-color: #e94560;
  color: #e94560;
  background: rgba(233, 69, 96, 0.1);
}
.preset-desc { display: block; font-size: 11px; color: #666; }

.prompt-input {
  width: 100%;
  background: #1a1a2e;
  border: 1px solid #333;
  border-radius: 8px;
  color: #eee;
  padding: 12px;
  font-size: 14px;
  font-family: inherit;
  resize: vertical;
  box-sizing: border-box;
}
.prompt-input:focus { border-color: #e94560; outline: none; }

.generate-btn {
  width: 100%;
  background: #e94560;
  color: #fff;
  border: none;
  padding: 14px;
  border-radius: 8px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s;
}
.generate-btn:hover:not(:disabled) { background: #c73e54; }
.generate-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.error-msg { color: #e94560; font-size: 13px; margin-top: 8px; }

input[type="range"] { width: 100%; accent-color: #e94560; }
.num-input {
  width: 100%;
  background: #1a1a2e;
  border: 1px solid #333;
  border-radius: 6px;
  color: #eee;
  padding: 6px 10px;
  font-size: 13px;
  box-sizing: border-box;
}
select {
  width: 100%;
  background: #1a1a2e;
  border: 1px solid #333;
  border-radius: 6px;
  color: #eee;
  padding: 6px 10px;
  font-size: 13px;
}
.checkbox-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #aaa;
  margin-bottom: 6px;
}
</style>
