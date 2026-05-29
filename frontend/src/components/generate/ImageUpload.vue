<template>
  <div class="image-upload" :class="{ 'has-image': preview }">
    <input
      type="file"
      ref="inputRef"
      accept="image/*"
      @change="handleFile"
      hidden
    />
    <div v-if="!preview" class="upload-zone" @click="inputRef?.click()" @dragover.prevent @drop.prevent="handleDrop">
      <div class="upload-icon">+</div>
      <p>拖拽图片或点击上传</p>
    </div>
    <div v-else class="preview-box">
      <img :src="preview" alt="Preview" />
      <button class="remove-btn" @click="remove">x</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const model = defineModel<File | null>()
const inputRef = ref<HTMLInputElement | null>(null)
const preview = ref<string | null>(null)

function handleFile(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (file) readFile(file)
}

function handleDrop(e: DragEvent) {
  const file = e.dataTransfer?.files?.[0]
  if (file) readFile(file)
}

function readFile(file: File) {
  model.value = file
  const reader = new FileReader()
  reader.onload = () => { preview.value = reader.result as string }
  reader.readAsDataURL(file)
}

function remove() {
  model.value = null
  preview.value = null
  if (inputRef.value) inputRef.value.value = ''
}
</script>

<style scoped>
.image-upload { width: 100%; }
.upload-zone {
  border: 2px dashed #333;
  border-radius: 8px;
  padding: 32px;
  text-align: center;
  cursor: pointer;
  transition: border-color 0.2s;
}
.upload-zone:hover { border-color: #e94560; }
.upload-icon { font-size: 32px; color: #555; }
.upload-zone p { font-size: 13px; color: #666; margin: 8px 0 0; }

.preview-box {
  position: relative;
  border-radius: 8px;
  overflow: hidden;
}
.preview-box img {
  width: 100%;
  max-height: 200px;
  object-fit: contain;
  background: #0f0f23;
}
.remove-btn {
  position: absolute;
  top: 8px; right: 8px;
  background: rgba(0,0,0,0.6);
  color: #fff;
  border: none;
  border-radius: 50%;
  width: 24px; height: 24px;
  cursor: pointer;
  font-size: 12px;
}
</style>
