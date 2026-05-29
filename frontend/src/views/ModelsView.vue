<template>
  <div class="models-view">
    <div class="header-row">
      <h2>模型</h2>
      <div class="header-actions">
        <button class="one-click-btn" @click="openWizard">一键下载所需模型</button>
        <button class="download-btn" @click="showManual = true">手动下载</button>
      </div>
    </div>

    <!-- System info -->
    <div v-if="sysInfo" class="sys-banner">
      设备: <strong>{{ sysInfo.chip }}</strong> · {{ sysInfo.ram_gb }}GB · <span class="tier-badge" :class="sysInfo.tier">{{ sysInfo.tier?.toUpperCase() }}</span>
      <span v-if="models.length > 0" class="banner-right">已安装 {{ models.length }} 个模型</span>
    </div>

    <!-- Active downloads -->
    <div v-if="activeDownloads.length > 0" class="downloads-section">
      <h3>下载任务 ({{ activeDownloads.length }})</h3>
      <div v-for="dl in activeDownloads" :key="dl.name" class="download-card" :class="dl.status">
        <div class="dl-left">
          <div class="dl-icon">
            <span v-if="dl.status === 'downloading'" class="spinner"></span>
            <span v-else-if="dl.status === 'queued'">⋯</span>
          </div>
        </div>
        <div class="dl-info">
          <div class="dl-name">{{ dl.name }}</div>
          <div class="dl-meta">
            <span>{{ formatSize(dl.downloaded) }} / {{ formatSize(dl.total) }}</span>
            <span v-if="dl.speed_mbps > 0 && dl.status === 'downloading'">{{ dl.speed_mbps.toFixed(1) }} MB/s</span>
            <span v-if="dl.eta_seconds && dl.status === 'downloading'">剩余 {{ formatEta(dl.eta_seconds) }}</span>
          </div>
          <div class="dl-bar-wrap">
            <div class="dl-bar">
              <div class="dl-fill" :class="dl.status" :style="{ width: (dl.progress * 100).toFixed(1) + '%' }"></div>
            </div>
            <span class="dl-pct">{{ (dl.progress * 100).toFixed(0) }}%</span>
          </div>
        </div>
        <button class="dl-cancel-btn" @click="cancelDownload(dl.name)" title="取消下载">✕</button>
      </div>
    </div>

    <!-- Installed models -->
    <div v-if="models.length > 0" class="installed-section">
      <h3>已安装模型</h3>
      <div class="model-list">
        <div v-for="m in models" :key="m.name" class="model-card">
          <div class="model-icon">{{ typeIcon(m.model_type) }}</div>
          <div class="model-info">
            <div class="model-name">{{ m.name }}</div>
            <div class="model-meta">{{ m.model_type }} · {{ (m.size_bytes / 1024 ** 3).toFixed(1) }} GB</div>
          </div>
          <div class="model-status downloaded">✓</div>
        </div>
      </div>
    </div>

    <div v-else-if="!sysInfo && !loadError" class="empty"><p>加载中...</p></div>
    <div v-else class="empty">
      <p>暂无已安装的模型</p>
      <button class="link-btn" @click="openWizard">一键下载所需模型</button>
    </div>

    <!-- ═══ Wizard ═══ -->
    <div v-if="showWizard" class="overlay" @click.self="showWizard = false">
      <div class="wizard">
        <div class="wizard-header">
          <h3>选择要下载的模型</h3>
          <p class="wizard-sub">根据你的 {{ sysInfo?.chip || 'Mac' }} · {{ sysInfo?.ram_gb || '' }}GB 自动推荐</p>
        </div>
        <div class="wizard-body">
          <div v-for="cat in categories" :key="cat.id" class="cat-section" :class="{ required: cat.required }">
            <div class="cat-head">
              <div class="cat-title">
                <span class="cat-name">{{ cat.name }}</span>
                <span class="cat-required-tag" :class="{ required: cat.required }">{{ cat.required ? '必选' : '可选' }}</span>
              </div>
              <div class="cat-desc">{{ cat.desc }}</div>
            </div>
            <div class="cat-options">
              <div
                v-for="(opt, oi) in cat.options"
                :key="oi"
                class="opt-card"
                :class="{ active: isSelected(cat.id, oi), recommended: opt.recommended, installed: isFullyInstalled(opt.files) }"
                @click="selectOption(cat.id, oi)"
              >
                <div class="opt-radio">
                  <div class="radio-dot" v-if="isSelected(cat.id, oi)"></div>
                </div>
                <div class="opt-body">
                  <div class="opt-label">
                    {{ opt.label }}
                    <span v-if="opt.recommended && !isFullyInstalled(opt.files)" class="opt-recommend-tag">推荐</span>
                    <span v-if="isFullyInstalled(opt.files)" class="opt-installed-tag">已安装</span>
                  </div>
                  <div class="opt-desc">{{ opt.desc }}</div>
                  <div class="opt-files">{{ opt.files.length }} 个文件<span v-if="countInstalled(opt.files) > 0"> · {{ countInstalled(opt.files) }} 已安装</span></div>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div class="wizard-footer">
          <div class="wizard-summary">共 <strong>{{ totalToDownload }}</strong> 个文件待下载</div>
          <div class="wizard-actions">
            <button class="btn-cancel" @click="showWizard = false">取消</button>
            <button class="btn-confirm" @click="startDownload" :disabled="totalToDownload === 0">开始下载</button>
          </div>
        </div>
      </div>
    </div>

    <!-- ═══ Manual Dialog ═══ -->
    <div v-if="showManual" class="overlay" @click.self="showManual = false">
      <div class="dialog">
        <h3>手动下载模型</h3>
        <div class="form-group">
          <label>仓库</label>
          <input v-model="downloadRepo" placeholder="Lightricks/LTX-2" />
        </div>
        <div class="form-group">
          <label>文件</label>
          <div class="repo-input-row">
            <input v-model="downloadFile" placeholder="选择或输入文件名" />
            <button class="browse-btn" @click="fetchAvailable">浏览</button>
          </div>
          <div v-if="availableFiles.length > 0" class="file-list">
            <div v-for="f in sortedFiles" :key="f.name" class="file-item"
              :class="{ selected: downloadFile === f.name, recommended: f.recommended }"
              @click="downloadFile = f.name">
              <div class="file-item-main">
                <span class="file-name">{{ f.name }}</span>
                <span v-if="f.recommended" class="file-badge">{{ f.badge }}</span>
              </div>
              <span class="file-desc" v-if="f.desc">{{ f.desc }}</span>
            </div>
          </div>
        </div>
        <div class="dialog-actions">
          <button class="btn-cancel" @click="showManual = false">取消</button>
          <button class="btn-download" @click="handleSingleDownload">下载</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import type { ModelEntry } from '../types/model'
import { getModels } from '../api/models'
import client from '../api/client'

interface CatOption { label: string; files: string[]; recommended: boolean; desc: string }
interface Category { id: string; name: string; desc: string; required: boolean; options: CatOption[] }

const models = ref<ModelEntry[]>([])
const sysInfo = ref<any>(null)
const categories = ref<Category[]>([])
const selections = ref<Record<string, number>>({})
const showWizard = ref(false)
const loadError = ref(false)

// Active downloads
const activeDownloads = ref<any[]>([])
let pollTimer: ReturnType<typeof setInterval> | null = null

// Manual
const showManual = ref(false)
const downloadRepo = ref('Lightricks/LTX-2')
const downloadFile = ref('')
const availableFiles = ref<string[]>([])

// ── helpers ──
function typeIcon(t: string) { return t === 'transformer' ? 'T' : t === 'text_encoder' ? 'E' : t === 'vae' ? 'V' : '?' }

function formatSize(bytes: number): string {
  if (!bytes || bytes <= 0) return '0 B'
  if (bytes >= 1024 ** 3) return (bytes / 1024 ** 3).toFixed(1) + ' GB'
  if (bytes >= 1024 ** 2) return (bytes / 1024 ** 2).toFixed(1) + ' MB'
  return (bytes / 1024).toFixed(0) + ' KB'
}

function formatEta(s: number): string {
  if (!s || s <= 0) return ''
  if (s < 60) return Math.round(s) + '秒'
  if (s < 3600) return Math.round(s / 60) + '分钟'
  return (s / 3600).toFixed(1) + '小时'
}

function isFileDownloaded(filename: string) {
  return models.value.some(m => m.filename === filename && m.downloaded)
}
function isFullyInstalled(files: string[]) {
  return files.every(f => isFileDownloaded(f))
}
function countInstalled(files: string[]) {
  return files.filter(f => isFileDownloaded(f)).length
}

const totalToDownload = computed(() => {
  let count = 0
  for (const cat of categories.value) {
    const idx = selections.value[cat.id]
    if (idx !== undefined && cat.options[idx]) {
      for (const f of cat.options[idx].files) {
        if (!isFileDownloaded(f)) count++
      }
    }
  }
  return count
})

function isSelected(catId: string, oi: number) { return selections.value[catId] === oi }
function selectOption(catId: string, oi: number) { selections.value[catId] = oi }

// ── API calls ──
async function fetchModels() { try { models.value = await getModels() } catch { } }

async function pollDownloads() {
  try {
    const res = await client.get('/models/download/progress')
    activeDownloads.value = res.data.downloads || []
  } catch { }
}

async function cancelDownload(name: string) {
  try {
    await client.delete(`/models/download/${encodeURIComponent(name)}`)
    await pollDownloads()
  } catch { }
}

async function openWizard() {
  showWizard.value = true
  try {
    const [recRes] = await Promise.all([
      client.get('/models/recommended'),
      fetchModels(),
    ])
    categories.value = recRes.data.categories || []
    sysInfo.value = recRes.data.system || null
    const sel: Record<string, number> = {}
    for (const cat of categories.value) {
      // Prefer first not-fully-installed recommended, else first recommended, else first
      let idx = cat.options.findIndex(o => o.recommended && !isFullyInstalled(o.files))
      if (idx < 0) idx = cat.options.findIndex(o => o.recommended)
      if (idx < 0) idx = 0
      sel[cat.id] = idx
    }
    selections.value = sel
  } catch { }
}

// ── Start download (parallel files) ──
async function startDownload() {
  showWizard.value = false

  // Collect all files to download
  const queue: string[] = []
  for (const cat of categories.value) {
    const idx = selections.value[cat.id]
    if (idx === undefined) continue
    for (const f of cat.options[idx].files) {
      if (!isFileDownloaded(f)) queue.push(f)
    }
  }

  // Download in parallel batches of 4
  const BATCH = 4
  for (let i = 0; i < queue.length; i += BATCH) {
    const batch = queue.slice(i, i + BATCH)
    await Promise.all(
      batch.map(f =>
        client.post('/models/download', { repo: 'Lightricks/LTX-2', filename: f }).catch(() => {})
      )
    )
    await pollDownloads()
  }
  await fetchModels()
  await pollDownloads()
}

// ── Manual ──
const recommendRules = [
  { match: 'ltx-2-19b-distilled.safetensors', badge: '优先', desc: '主模型：蒸馏版，最佳平衡' },
  { match: 'vae/diffusion_pytorch_model', badge: '必选', desc: 'VAE 编解码器' },
  { match: 'text_encoder/diffusion', badge: '必选', desc: '文本编码器 (Diffusers 格式)' },
]

const sortedFiles = computed(() =>
  availableFiles.value.map(name => {
    for (const r of recommendRules) { if (name.includes(r.match)) return { name, recommended: true, badge: r.badge, desc: r.desc } }
    return { name, recommended: false, badge: '', desc: '' }
  }).sort((a, b) => {
    if (a.recommended !== b.recommended) return a.recommended ? -1 : 1
    return a.name.localeCompare(b.name)
  })
)

async function fetchAvailable() {
  try {
    const res = await client.get('/models/available', { params: { repo: downloadRepo.value } })
    availableFiles.value = res.data.files || []
  } catch { }
}

async function handleSingleDownload() {
  try {
    await client.post('/models/download', { repo: downloadRepo.value, filename: downloadFile.value })
    await pollDownloads()
    showManual.value = false
  } catch { }
}

// ── Lifecycle ──
onMounted(async () => {
  await fetchModels()
  await pollDownloads()
  pollTimer = setInterval(pollDownloads, 2000)
  try {
    const res = await client.get('/system/info')
    sysInfo.value = res.data
  } catch { loadError.value = true }
})

onUnmounted(() => { if (pollTimer) clearInterval(pollTimer) })
</script>

<style scoped>
.header-row { display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; }
.header-actions { display: flex; gap: 8px; }
.one-click-btn { background: linear-gradient(135deg, #0f9, #0af); color: #0f0f23; border: none; padding: 8px 20px; border-radius: 6px; cursor: pointer; font-size: 13px; font-weight: 600; }
.one-click-btn:hover { opacity: 0.85; }
.download-btn { background: #e94560; color: #fff; border: none; padding: 8px 20px; border-radius: 6px; cursor: pointer; font-size: 13px; }
.empty { text-align: center; padding: 48px; color: #666; }
.link-btn { background: none; border: none; color: #e94560; cursor: pointer; font-size: 13px; }

.sys-banner { font-size: 13px; color: #888; padding: 10px 14px; background: #1a1a2e; border-radius: 8px; margin-bottom: 20px; display: flex; align-items: center; }
.sys-banner strong { color: #ccc; }
.banner-right { margin-left: auto; }
.tier-badge.ultra { color: #ffd700; }
.tier-badge.high { color: #e94560; }
.tier-badge.medium { color: #0f9; }

/* Downloads */
.downloads-section { margin-bottom: 24px; }
.downloads-section h3 { font-size: 14px; margin: 0 0 10px; color: #aaa; }
.download-card { display: flex; align-items: center; gap: 12px; background: #1a1a2e; border-radius: 8px; padding: 12px 14px; margin-bottom: 6px; }
.dl-left { flex-shrink: 0; }
.dl-icon { width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; font-size: 16px; color: #666; }
.spinner { width: 16px; height: 16px; border: 2px solid #333; border-top-color: #0af; border-radius: 50%; display: inline-block; animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.dl-info { flex: 1; min-width: 0; }
.dl-name { font-size: 12px; color: #ccc; font-family: monospace; margin-bottom: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.dl-meta { font-size: 11px; color: #666; display: flex; gap: 12px; margin-bottom: 6px; }
.dl-bar-wrap { display: flex; align-items: center; gap: 8px; }
.dl-bar { flex: 1; height: 3px; background: #0f0f23; border-radius: 2px; overflow: hidden; }
.dl-fill { height: 100%; border-radius: 2px; transition: width 0.3s; }
.dl-fill.downloading, .dl-fill.queued { background: #0af; }
.dl-pct { font-size: 11px; color: #888; min-width: 30px; }
.dl-cancel-btn { background: none; border: none; color: #555; cursor: pointer; font-size: 14px; padding: 4px 8px; border-radius: 4px; transition: all 0.15s; }
.dl-cancel-btn:hover { color: #e94560; background: rgba(233,69,96,0.1); }

/* Installed */
.installed-section { margin-bottom: 24px; }
.installed-section h3 { font-size: 14px; margin: 0 0 10px; color: #aaa; }
.model-list { display: flex; flex-direction: column; gap: 4px; }
.model-card { display: flex; align-items: center; gap: 10px; background: #1a1a2e; border-radius: 8px; padding: 10px 14px; }
.model-icon { width: 32px; height: 32px; background: #16213e; border-radius: 6px; display: flex; align-items: center; justify-content: center; font-weight: 700; color: #e94560; font-size: 13px; flex-shrink: 0; }
.model-name { font-size: 13px; color: #ccc; }
.model-meta { font-size: 11px; color: #555; margin-top: 2px; }
.model-status { margin-left: auto; font-size: 14px; color: #555; }
.model-status.downloaded { color: #0f9; }

/* Wizard */
.overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.6); display: flex; align-items: center; justify-content: center; z-index: 100; }
.wizard { background: #1a1a2e; border-radius: 12px; width: 620px; max-height: 85vh; display: flex; flex-direction: column; }
.wizard-header { padding: 20px 24px 12px; border-bottom: 1px solid #2a2a3e; }
.wizard-header h3 { margin: 0 0 4px; font-size: 16px; }
.wizard-sub { font-size: 12px; color: #666; margin: 0; }
.wizard-body { flex: 1; overflow-y: auto; padding: 16px 24px; }
.wizard-footer { padding: 14px 24px; border-top: 1px solid #2a2a3e; display: flex; align-items: center; justify-content: space-between; }
.wizard-summary { font-size: 13px; color: #888; }
.wizard-summary strong { color: #0f9; }
.wizard-actions { display: flex; gap: 8px; }

.cat-section { margin-bottom: 18px; }
.cat-head { margin-bottom: 6px; }
.cat-title { display: flex; align-items: center; gap: 8px; }
.cat-name { font-size: 14px; color: #eee; font-weight: 600; }
.cat-required-tag { font-size: 10px; padding: 1px 6px; border-radius: 3px; }
.cat-required-tag.required { background: rgba(233,69,96,0.12); color: #e94560; }
.cat-required-tag:not(.required) { background: rgba(0,170,255,0.1); color: #0af; }
.cat-desc { font-size: 12px; color: #666; margin-top: 2px; }
.cat-options { display: flex; flex-direction: column; gap: 4px; }

.opt-card { display: flex; align-items: flex-start; gap: 10px; background: #0f0f23; border: 1px solid #222; border-radius: 8px; padding: 10px 12px; cursor: pointer; transition: all 0.15s; }
.opt-card:hover { border-color: #333; }
.opt-card.active { border-color: #0af; background: rgba(0,170,255,0.05); }
.opt-card.recommended { background: rgba(0,255,153,0.02); }
.opt-card.active.recommended { border-color: #0f9; background: rgba(0,255,153,0.06); }
.opt-card.installed { opacity: 0.6; }
.opt-radio { width: 18px; height: 18px; border-radius: 50%; border: 2px solid #444; display: flex; align-items: center; justify-content: center; flex-shrink: 0; margin-top: 1px; }
.opt-card.active .opt-radio { border-color: #0af; }
.opt-card.active.recommended .opt-radio { border-color: #0f9; }
.radio-dot { width: 8px; height: 8px; border-radius: 50%; background: #0af; }
.opt-card.active.recommended .radio-dot { background: #0f9; }
.opt-body { flex: 1; min-width: 0; }
.opt-label { font-size: 13px; color: #ccc; display: flex; align-items: center; gap: 6px; }
.opt-recommend-tag { font-size: 10px; background: rgba(0,255,153,0.12); color: #0f9; padding: 1px 5px; border-radius: 3px; }
.opt-installed-tag { font-size: 10px; background: rgba(0,255,153,0.12); color: #0f9; padding: 1px 5px; border-radius: 3px; }
.opt-desc { font-size: 11px; color: #666; margin-top: 2px; }
.opt-files { font-size: 10px; color: #444; margin-top: 2px; }

/* Manual */
.dialog { background: #1a1a2e; border-radius: 12px; width: 500px; max-height: 85vh; overflow-y: auto; padding: 24px; }
.dialog h3 { margin: 0 0 16px; }
.form-group { margin-bottom: 14px; }
.form-group label { display: block; font-size: 12px; color: #888; margin-bottom: 4px; }
.form-group input { width: 100%; background: #0f0f23; border: 1px solid #333; border-radius: 6px; color: #eee; padding: 8px; font-size: 13px; box-sizing: border-box; }
.repo-input-row { display: flex; gap: 8px; }
.repo-input-row input { flex: 1; }
.browse-btn { background: #16213e; color: #ccc; border: 1px solid #333; padding: 8px 14px; border-radius: 6px; cursor: pointer; font-size: 12px; white-space: nowrap; }
.browse-btn:hover { border-color: #e94560; color: #e94560; }
.file-list { max-height: 220px; overflow-y: auto; background: #0f0f23; border: 1px solid #333; border-radius: 6px; margin-top: 8px; }
.file-item { padding: 7px 10px; cursor: pointer; border-bottom: 1px solid #1a1a2e; }
.file-item:last-child { border-bottom: none; }
.file-item:hover { background: #16213e; }
.file-item.selected { background: rgba(233,69,96,0.1); }
.file-item.recommended { background: rgba(0,255,153,0.02); }
.file-item-main { display: flex; align-items: center; gap: 8px; }
.file-name { font-size: 12px; font-family: monospace; color: #ccc; }
.file-badge { font-size: 10px; padding: 1px 5px; border-radius: 3px; background: rgba(0,255,153,0.12); color: #0f9; }
.file-desc { font-size: 11px; color: #555; margin-top: 2px; }

/* Buttons */
.btn-cancel { background: #333; color: #ccc; border: none; padding: 8px 20px; border-radius: 6px; cursor: pointer; font-size: 13px; }
.btn-download { background: #e94560; color: #fff; border: none; padding: 8px 20px; border-radius: 6px; cursor: pointer; font-size: 13px; }
.btn-confirm { background: linear-gradient(135deg, #0f9, #0af); color: #0f0f23; border: none; padding: 10px 28px; border-radius: 6px; cursor: pointer; font-size: 14px; font-weight: 600; }
.btn-confirm:hover { opacity: 0.85; }
.btn-confirm:disabled { opacity: 0.4; cursor: not-allowed; }
</style>
